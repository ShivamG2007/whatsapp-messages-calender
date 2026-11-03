import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    message_id TEXT UNIQUE NOT NULL,
    chat_id TEXT,
    chat_name TEXT,
    sender TEXT,
    message TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    mode TEXT,
    model TEXT,
    prompt_version TEXT,
    system_prompt TEXT,
    user_prompt TEXT,
    context_text TEXT,
    candidates_text TEXT,
    raw_output TEXT,
    decision TEXT,
    resolved TEXT,
    result TEXT,
    label_status TEXT NOT NULL DEFAULT 'unlabeled',
    label TEXT,
    labeled_at TEXT,
    split TEXT NOT NULL
);
"""

JSON_FIELDS = ("decision", "resolved", "result", "label")


def split_for(message_id: str, test_share: int = 5) -> str:
    """Stable 80/20 split: the same message always lands in the same split."""
    digest = int(hashlib.sha1(message_id.encode()).hexdigest(), 16)
    return "test" if digest % test_share == 0 else "train"


class Dataset:
    """Permanent store of every decision the bot made. Never pruned: this is the training data."""

    def __init__(self, path: Path):
        self.path = path
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, **fields) -> int | None:
        fields = dict(fields)
        fields.setdefault("created_at", datetime.now().astimezone().isoformat(timespec="seconds"))
        fields.setdefault("split", split_for(fields["message_id"]))
        for key in JSON_FIELDS:
            if key in fields and not isinstance(fields[key], str) and fields[key] is not None:
                fields[key] = json.dumps(fields[key], ensure_ascii=False)
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(f"INSERT OR IGNORE INTO records ({cols}) VALUES ({marks})", tuple(fields.values()))
            return cur.lastrowid if cur.rowcount else None

    def update_result(self, record_id: int, result: dict) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE records SET result = ? WHERE id = ?", (json.dumps(result, ensure_ascii=False), record_id))

    def set_label(self, record_id: int, label: dict, status: str) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE records SET label = ?, label_status = ?, labeled_at = ? WHERE id = ?",
                (json.dumps(label, ensure_ascii=False), status, now, record_id),
            )

    def records(self, labeled_only: bool = False, split: str | None = None) -> list[dict]:
        query = "SELECT * FROM records WHERE 1=1"
        params: list = []
        if labeled_only:
            query += " AND label_status IN ('correct', 'corrected')"
        if split:
            query += " AND split = ?"
            params.append(split)
        with closing(self._connect()) as conn:
            rows = conn.execute(query + " ORDER BY id", params).fetchall()
        return [self._decode(row) for row in rows]

    def get(self, record_id: int) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        return self._decode(row) if row else None

    def stats(self) -> dict:
        with closing(self._connect()) as conn:
            total = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            by_status = dict(conn.execute("SELECT label_status, COUNT(*) FROM records GROUP BY label_status").fetchall())
            by_action = dict(
                conn.execute(
                    "SELECT json_extract(COALESCE(label, decision), '$.action'), COUNT(*) FROM records GROUP BY 1"
                ).fetchall()
            )
        return {"total": total, "by_label_status": by_status, "by_action": by_action}

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict:
        item = dict(row)
        for key in JSON_FIELDS:
            if item.get(key):
                item[key] = json.loads(item[key])
        return item
