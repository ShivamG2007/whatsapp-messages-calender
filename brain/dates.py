import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import dateparser

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WEEKDAY_SHORT = {d[:3]: d for d in WEEKDAYS} | {"tues": "tuesday", "thur": "thursday", "thurs": "thursday"}

_DATE_WORDS = [
    (r"\bday after tomorrow\b", "in 2 days"),
    (r"\bparso\b", "in 2 days"),
    (r"\b(kal|tmrw|tmr|tomo|tom)\b", "tomorrow"),
    (r"\b(aaj|tonight|tonite|abhi)\b", "today"),
    (r"\bagle hafte\b", "next week"),
    (r"\b(this|coming|upcoming|on|by|before|till|until|from)\b", " "),
]

_PM_RE = re.compile(r"(\d\s*|\b)(pm|p\.m)|\b(evening|night|shaam|raat|afternoon|dopahar)\b")
_AM_RE = re.compile(r"(\d\s*|\b)(am|a\.m)\b|\b(morning|subah)\b")
_TIME_RE = re.compile(r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.?|p\.m\.?)?", re.IGNORECASE)
_RANGE_RE = re.compile(
    r"(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm|a\.m\.?|p\.m\.?)?)\s*(?:-|–|to|till|until)\s*"
    r"(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm|a\.m\.?|p\.m\.?)?)",
    re.IGNORECASE,
)


@dataclass
class ResolvedTime:
    start: datetime
    end: datetime
    all_day: bool
    explicit_end: bool = False


def _normalize_date_text(text: str) -> str:
    text = text.lower().strip()
    for pattern, repl in _DATE_WORDS:
        text = re.sub(pattern, repl, text)
    text = re.sub(r"\bnext\s+(" + "|".join(WEEKDAYS) + r"|" + "|".join(_WEEKDAY_SHORT) + r")\b", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_date(date_text: str, base: datetime) -> date | None:
    """Turn words like 'tomorrow', 'kal', 'friday', '5 nov' into a date, relative to when the message was sent."""
    text = _normalize_date_text(date_text)
    if not text:
        return None
    word = _WEEKDAY_SHORT.get(text, text)
    if word in WEEKDAYS and WEEKDAYS.index(word) == base.weekday():
        return base.date()
    naive_base = base.replace(tzinfo=None)
    settings = {
        "RELATIVE_BASE": naive_base,
        "PREFER_DATES_FROM": "future",
        "DATE_ORDER": "DMY",
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    parsed = dateparser.parse(text, settings=settings, languages=["en"])
    return parsed.date() if parsed else None


def _clean_time_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\b(baje|bje|o'?clock|hrs|hours|ke baad|tak|around|approx|sharp|at)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _hint(text: str) -> str | None:
    if _PM_RE.search(text):
        return "pm"
    if _AM_RE.search(text):
        return "am"
    return None


def _to_24h(hour: int, minute: int, meridiem: str | None) -> time | None:
    if minute > 59 or hour > 23:
        return None
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    elif meridiem is None and 1 <= hour <= 7:
        hour += 12
    return time(hour, minute)


def _parse_single(text: str, fallback_meridiem: str | None) -> time | None:
    if "noon" in text or "dopahar 12" in text:
        return time(12, 0)
    if "midnight" in text:
        return time(0, 0)
    match = _TIME_RE.search(text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    meridiem = match.group(3)
    meridiem = meridiem.replace(".", "")[:2].lower() if meridiem else None
    if hour > 12:
        meridiem = None
    return _to_24h(hour, minute, meridiem or fallback_meridiem)


def parse_time_range(text: str) -> tuple[time | None, time | None]:
    """Parse '7pm', '19:00', '7 baje', 'shaam 6', '6-8pm', '5:30 to 7' into (start, end)."""
    text = _clean_time_text(text)
    if not text:
        return None, None
    hint = _hint(text)
    ranged = _RANGE_RE.search(text)
    if ranged:
        end_hint = _hint(ranged.group(2)) or hint
        start_hint = _hint(ranged.group(1)) or end_hint
        return _parse_single(ranged.group(1), start_hint), _parse_single(ranged.group(2), end_hint)
    return _parse_single(text, hint), None


def resolve_when(
    date_text: str,
    time_text: str,
    end_time_text: str,
    base: datetime,
    default_minutes: int,
    keep_from: datetime | None = None,
    keep_all_day: bool = False,
) -> ResolvedTime | None:
    """Combine date and time words into a start/end. keep_from fills in whatever part the message didn't change."""
    tz = base.tzinfo
    day = resolve_date(date_text, base) if date_text else None
    start_t, end_t = parse_time_range(time_text) if time_text else (None, None)
    if end_t is None and end_time_text:
        end_t, _ = parse_time_range(end_time_text)

    if day is None and start_t is None:
        return None

    if day is None:
        if keep_from is not None:
            day = keep_from.date()
        else:
            day = base.date()
            if datetime.combine(day, start_t, tz) < base - timedelta(minutes=30):
                day += timedelta(days=1)

    if start_t is None:
        if keep_from is not None and not keep_all_day:
            start_t = keep_from.timetz().replace(tzinfo=None)
        else:
            start = datetime.combine(day, time(0, 0), tz)
            return ResolvedTime(start, start + timedelta(days=1), True, True)

    start = datetime.combine(day, start_t, tz)
    if end_t is not None:
        end = datetime.combine(day, end_t, tz)
        if end <= start:
            end += timedelta(days=1)
        return ResolvedTime(start, end, False, True)
    return ResolvedTime(start, start + timedelta(minutes=default_minutes), False, False)
