import re

KEYWORDS = (
    "today",
    "tonight",
    "tomorrow",
    "tmrw",
    "tmr",
    "yesterday",
    "kal",
    "aaj",
    "parso",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
    "week",
    "weekend",
    "meet",
    "meeting",
    "practice",
    "prac",
    "session",
    "rehearsal",
    "match",
    "class",
    "lecture",
    "lab",
    "workshop",
    "event",
    "call",
    "deadline",
    "due",
    "submission",
    "cancel",
    "cancelled",
    "canceled",
    "postpone",
    "postponed",
    "prepone",
    "preponed",
    "shift",
    "shifted",
    "moved",
    "reschedule",
    "rescheduled",
    "delay",
    "delayed",
    "baje",
    "bje",
    "noon",
    "morning",
    "evening",
    "night",
    "shaam",
    "subah",
)

_KEYWORD_RE = re.compile(r"\b(" + "|".join(KEYWORDS) + r")\w*\b", re.IGNORECASE)
_TIME_RE = re.compile(r"\b\d{1,2}([:.]\d{2})?\s*(am|pm|a\.m\.|p\.m\.|hrs)\b|\b\d{1,2}[:.]\d{2}\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b\d{1,2}(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|\b\d{1,2}/\d{1,2}\b", re.IGNORECASE
)


def might_be_schedule(text: str) -> bool:
    """Cheap check so the model only sees messages that could be about an event."""
    if not text or len(text.strip()) < 3:
        return False
    return bool(_KEYWORD_RE.search(text) or _TIME_RE.search(text) or _DATE_RE.search(text))
