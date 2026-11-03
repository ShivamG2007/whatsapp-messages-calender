from datetime import datetime
from typing import Protocol

from ..models import CalendarEvent

MARKER = "auto-added from WhatsApp, edits to the text below may confuse the bot"


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def format_description(
    tag: str, chat_id: str, chat_name: str, message_id: str, message: str, sent_at: datetime, history: list[str]
) -> str:
    """The calendar description doubles as the bot's long-term memory, so it is written in a fixed, parseable format."""
    lines = [
        f"[{tag}] {MARKER}",
        f"chat: {_one_line(chat_name)}",
        f"chat_id: {chat_id}",
        f"source_message_id: {message_id}",
        f"source_message: {_one_line(message)[:500]}",
        f"sent_at: {sent_at.strftime('%Y-%m-%d %H:%M')}",
        "history:",
    ]
    lines += [f"- {_one_line(entry)}" for entry in history]
    return "\n".join(lines)


def parse_description(text: str) -> dict:
    info: dict = {"history": []}
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("- "):
            info["history"].append(line[2:])
        elif ": " in line and not line.startswith("["):
            key, value = line.split(": ", 1)
            info[key.strip()] = value.strip()
    return info


def is_bot_description(text: str, tag: str) -> bool:
    return (text or "").lstrip().startswith(f"[{tag}]")


def fill_from_description(event: CalendarEvent) -> CalendarEvent:
    info = parse_description(event.description)
    event.chat_id = info.get("chat_id", "")
    event.chat_name = info.get("chat", "")
    event.history = info.get("history", [])
    return event


class Calendar(Protocol):
    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]: ...

    def create(self, event: CalendarEvent) -> CalendarEvent: ...

    def update(self, event: CalendarEvent) -> CalendarEvent: ...

    def delete(self, event_id: str) -> None: ...
