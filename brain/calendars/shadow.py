import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

from ..models import CalendarEvent
from .base import fill_from_description, is_bot_description

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    place TEXT,
    all_day INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    deleted INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


class ShadowCalendar:
    """A pretend calendar in a local SQLite file. Shadow mode writes here instead of Outlook,
    so add -> reschedule -> cancel chains can be checked before the bot touches your real calendar."""

    def __init__(self, path: Path, tag: str):
        self.path = path
        self.tag = tag
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_event(self, row: sqlite3.Row) -> CalendarEvent:
        event = CalendarEvent(
            id=row["id"],
            title=row["title"],
            start=datetime.fromisoformat(row["start"]),
            end=datetime.fromisoformat(row["end"]),
            place=row["place"] or "",
            all_day=bool(row["all_day"]),
            description=row["description"] or "",
        )
        return fill_from_description(event)

    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM events WHERE deleted = 0 ORDER BY start").fetchall()
        events = [self._row_to_event(row) for row in rows]
        return [e for e in events if e.end > start and e.start < end and is_bot_description(e.description, self.tag)]

    def create(self, event: CalendarEvent) -> CalendarEvent:
        event.id = event.id or f"shadow-{uuid.uuid4().hex[:12]}"
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO events (id, title, start, end, place, all_day, description, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    event.id,
                    event.title,
                    event.start.isoformat(),
                    event.end.isoformat(),
                    event.place,
                    int(event.all_day),
                    event.description,
                    datetime.now().astimezone().isoformat(),
                ),
            )
        return event

    def update(self, event: CalendarEvent) -> CalendarEvent:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE events SET title=?, start=?, end=?, place=?, all_day=?, description=?, updated_at=? WHERE id=?",
                (
                    event.title,
                    event.start.isoformat(),
                    event.end.isoformat(),
                    event.place,
                    int(event.all_day),
                    event.description,
                    datetime.now().astimezone().isoformat(),
                    event.id,
                ),
            )
        return event

    def delete(self, event_id: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE events SET deleted = 1, updated_at = ? WHERE id = ?", (datetime.now().astimezone().isoformat(), event_id)
            )
