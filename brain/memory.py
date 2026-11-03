import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from .models import IncomingMessage

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    chat_name TEXT,
    sender TEXT,
    body TEXT NOT NULL,
    ts INTEGER NOT NULL,
    from_me INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, ts);
"""


class ShortTermMemory:
    """Last few days of chat messages, used only as context. Old rows are deleted by prune()."""

    def __init__(self, path: Path, keep_days: int):
        self.path = path
        self.keep_days = keep_days
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, msg: IncomingMessage) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO messages (id, chat_id, chat_name, sender, body, ts, from_me) VALUES (?,?,?,?,?,?,?)",
                (msg.id, msg.chat_id, msg.chat_name, msg.sender, msg.body, msg.timestamp, int(msg.from_me)),
            )
            return cur.rowcount == 1

    def recent(self, chat_id: str, before_ts: int, limit: int) -> list[sqlite3.Row]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE chat_id = ? AND ts < ? ORDER BY ts DESC LIMIT ?",
                (chat_id, before_ts, limit),
            ).fetchall()
        return list(reversed(rows))

    def prune(self, now: datetime | None = None) -> int:
        now = now or datetime.now().astimezone()
        cutoff = int((now - timedelta(days=self.keep_days)).timestamp())
        with closing(self._connect()) as conn, conn:
            return conn.execute("DELETE FROM messages WHERE ts < ?", (cutoff,)).rowcount

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
