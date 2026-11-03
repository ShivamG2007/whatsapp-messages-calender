import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from .calendars import Calendar, format_description, parse_description
from .config import Settings
from .dataset import Dataset
from .dates import ResolvedTime, resolve_when
from .memory import ShortTermMemory
from .models import CalendarEvent, Decision, IncomingMessage
from .prefilter import might_be_schedule
from .prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt, format_candidates, format_context

log = logging.getLogger(__name__)

MAX_CANDIDATES = 10


@dataclass
class Outcome:
    status: str
    reason: str = ""
    event: str = ""
    event_id: str = ""
    resolved: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in ("", {}, None)}


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _resolved_dict(when: ResolvedTime | None) -> dict:
    if when is None:
        return {}
    return {"start": when.start.isoformat(), "end": when.end.isoformat(), "all_day": when.all_day}


class Processor:
    def __init__(self, settings: Settings, memory: ShortTermMemory, dataset: Dataset, calendar: Calendar, extractor):
        self.settings = settings
        self.memory = memory
        self.dataset = dataset
        self.calendar = calendar
        self.extractor = extractor

    def handle(self, msg: IncomingMessage) -> Outcome:
        tz = self.settings.tz
        sent_at = datetime.fromtimestamp(msg.timestamp, tz)
        if not self.memory.add(msg):
            return Outcome("duplicate")
        if not might_be_schedule(msg.body):
            return Outcome("filtered")

        context_text = format_context(self.memory.recent(msg.chat_id, msg.timestamp, self.settings.context_messages), tz)
        try:
            candidates = self._candidates(msg, sent_at)
        except Exception as exc:
            log.error("Could not read the calendar: %s", exc)
            return Outcome("error", reason=f"calendar_read_failed: {exc}")
        candidates_text = format_candidates(candidates)
        user_prompt = build_user_prompt(msg.chat_name, msg.sender, msg.body, sent_at, context_text, candidates_text)

        try:
            decision, raw = self.extractor.extract(user_prompt)
        except Exception as exc:
            log.error("Model call failed: %s", exc)
            return Outcome("error", reason=f"model_failed: {exc}")

        try:
            outcome = self._apply(decision, msg, sent_at, candidates)
        except Exception as exc:
            log.exception("Applying the decision failed")
            outcome = Outcome("error", reason=f"apply_failed: {exc}")

        self.dataset.add(
            message_id=msg.id,
            chat_id=msg.chat_id,
            chat_name=msg.chat_name,
            sender=msg.sender,
            message=msg.body,
            sent_at=sent_at.isoformat(),
            mode=self.settings.mode,
            model=getattr(self.extractor, "model", "unknown"),
            prompt_version=PROMPT_VERSION,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            context_text=context_text,
            candidates_text=candidates_text,
            raw_output=raw,
            decision=decision.to_dict(),
            resolved=outcome.resolved,
            result=outcome.to_dict(),
        )
        log.info("[%s] %s -> %s %s", msg.chat_name, msg.body[:60].replace("\n", " "), decision.action, outcome.to_dict())
        return outcome

    def _candidates(self, msg: IncomingMessage, sent_at: datetime) -> list[CalendarEvent]:
        events = self.calendar.list_events(sent_at - timedelta(days=1), sent_at + timedelta(days=self.settings.lookahead_days))
        events.sort(key=lambda e: (e.chat_id != msg.chat_id, e.start))
        return events[:MAX_CANDIDATES]

    def _find_target(self, decision: Decision, msg: IncomingMessage, candidates: list[CalendarEvent]) -> CalendarEvent | None:
        same_chat = [c for c in candidates if c.chat_id == msg.chat_id]
        if 1 <= decision.target <= len(candidates) and candidates[decision.target - 1].chat_id == msg.chat_id:
            return candidates[decision.target - 1]
        if decision.event:
            scored = sorted(((_similar(decision.event, c.title), c) for c in same_chat), key=lambda x: -x[0])
            if scored and scored[0][0] >= 0.6:
                return scored[0][1]
        if len(same_chat) == 1:
            return same_chat[0]
        return None

    def _description(self, msg: IncomingMessage, sent_at: datetime, history: list[str], base: CalendarEvent | None = None) -> str:
        if base is not None:
            info = parse_description(base.description)
            return format_description(
                self.settings.calendar_tag,
                info.get("chat_id", msg.chat_id),
                info.get("chat", msg.chat_name),
                info.get("source_message_id", msg.id),
                info.get("source_message", msg.body),
                datetime.strptime(info["sent_at"], "%Y-%m-%d %H:%M").replace(tzinfo=sent_at.tzinfo)
                if "sent_at" in info
                else sent_at,
                history,
            )
        return format_description(self.settings.calendar_tag, msg.chat_id, msg.chat_name, msg.id, msg.body, sent_at, history)

    def _history_line(self, sent_at: datetime, what: str, msg: IncomingMessage) -> str:
        who = "me" if msg.from_me else (msg.sender or "someone")
        return f"{sent_at:%Y-%m-%d %H:%M} {what} (message from {who}: {' '.join(msg.body.split())[:120]})"

    def _apply(self, decision: Decision, msg: IncomingMessage, sent_at: datetime, candidates: list[CalendarEvent]) -> Outcome:
        if decision.action == "none":
            return Outcome("no_action")
        if decision.confidence < self.settings.min_confidence:
            return Outcome("skipped", reason=f"low_confidence ({decision.confidence:.2f})")

        if decision.action == "cancel":
            target = self._find_target(decision, msg, candidates)
            if target is None:
                return Outcome("skipped", reason="no_matching_event_to_cancel")
            self.calendar.delete(target.id)
            return Outcome("deleted", event=target.summary(), event_id=target.id)

        if decision.action == "reschedule":
            target = self._find_target(decision, msg, candidates)
            if target is not None:
                return self._reschedule(decision, msg, sent_at, target)

        return self._add(decision, msg, sent_at, candidates, fallback=decision.action == "reschedule")

    def _reschedule(self, decision: Decision, msg: IncomingMessage, sent_at: datetime, target: CalendarEvent) -> Outcome:
        when = resolve_when(
            decision.date_text,
            decision.time_text,
            decision.end_time_text,
            sent_at,
            self.settings.default_event_minutes,
            keep_from=target.start,
            keep_all_day=target.all_day,
        )
        if when is None and not decision.place:
            return Outcome("skipped", reason="reschedule_without_new_time_or_place", event=target.summary())
        before = target.summary()
        if when is not None:
            duration = target.end - target.start
            target.start, target.all_day = when.start, when.all_day
            target.end = when.end if (when.explicit_end or when.all_day or target.all_day) else when.start + duration
        if decision.place:
            target.place = decision.place
        target.history.append(self._history_line(sent_at, f"changed from [{before}]", msg))
        target.description = self._description(msg, sent_at, target.history, base=target)
        self.calendar.update(target)
        return Outcome("updated", event=target.summary(), event_id=target.id, resolved=_resolved_dict(when))

    def _add(
        self, decision: Decision, msg: IncomingMessage, sent_at: datetime, candidates: list[CalendarEvent], fallback: bool
    ) -> Outcome:
        when = resolve_when(
            decision.date_text, decision.time_text, decision.end_time_text, sent_at, self.settings.default_event_minutes
        )
        if when is None:
            return Outcome("skipped", reason="no_date_or_time_found")
        if when.end <= sent_at:
            return Outcome("skipped", reason="event_already_over", resolved=_resolved_dict(when))

        title = decision.event or msg.chat_name or "WhatsApp event"
        title = title[0].upper() + title[1:]
        for existing in candidates:
            if (
                existing.chat_id == msg.chat_id
                and existing.start.date() == when.start.date()
                and _similar(existing.title, title) >= 0.75
            ):
                if existing.start == when.start:
                    return Outcome("skipped", reason="duplicate", event=existing.summary(), event_id=existing.id)
                return self._reschedule(decision, msg, sent_at, existing)

        history = [self._history_line(sent_at, "added" + (" (reschedule with no earlier event)" if fallback else ""), msg)]
        event = CalendarEvent(
            title=title,
            start=when.start,
            end=when.end,
            place=decision.place,
            all_day=when.all_day,
            chat_id=msg.chat_id,
            chat_name=msg.chat_name,
            history=history,
        )
        event.description = self._description(msg, sent_at, history)
        created = self.calendar.create(event)
        return Outcome("created", event=created.summary(), event_id=created.id, resolved=_resolved_dict(when))
