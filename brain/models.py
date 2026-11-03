from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ACTIONS = ("add", "reschedule", "cancel", "none")
Action = Literal["add", "reschedule", "cancel", "none"]


class IncomingMessage(BaseModel):
    id: str
    chat_id: str
    chat_name: str = ""
    sender: str = ""
    body: str
    timestamp: int = Field(description="Unix seconds, as sent by WhatsApp")
    from_me: bool = False


@dataclass
class Decision:
    action: Action = "none"
    event: str = ""
    date_text: str = ""
    time_text: str = ""
    end_time_text: str = ""
    place: str = ""
    target: int = 0
    confidence: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "Decision":
        action = str(data.get("action", "none")).strip().lower()
        if action not in ACTIONS:
            action = "none"
        try:
            target = int(data.get("target") or 0)
        except (TypeError, ValueError):
            target = 0
        try:
            confidence = float(data.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        return cls(
            action=action,
            event=str(data.get("event") or "").strip(),
            date_text=str(data.get("date_text") or "").strip(),
            time_text=str(data.get("time_text") or "").strip(),
            end_time_text=str(data.get("end_time_text") or "").strip(),
            place=str(data.get("place") or "").strip(),
            target=max(target, 0),
            confidence=min(max(confidence, 0.0), 1.0),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    place: str = ""
    all_day: bool = False
    description: str = ""
    id: str = ""
    chat_id: str = ""
    chat_name: str = ""
    history: list[str] = field(default_factory=list)

    def summary(self) -> str:
        when = self.start.strftime("%a %Y-%m-%d") if self.all_day else self.start.strftime("%a %Y-%m-%d %H:%M")
        parts = [self.title, when]
        if self.place:
            parts.append(self.place)
        if self.chat_name:
            parts.append(f"chat: {self.chat_name}")
        return " | ".join(parts)
