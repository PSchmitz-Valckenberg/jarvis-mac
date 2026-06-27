"""Persistent conversation memory via SQLite.

Every turn gets appended to a local SQLite file, so Jarvis can pick a
conversation back up after a restart instead of starting blank each time.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class MemoryStore:
    """Append-only log of chat turns, backed by a local SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.commit()

    def add_turn(self, user_content: str, assistant_content: str) -> None:
        """Insert a user+assistant pair as a single transaction.

        Writing them separately would commit twice per turn and risk a
        partial write (user saved, assistant insert fails) if anything goes
        wrong in between.
        """
        now = time.time()
        with self._lock:
            self._conn.executemany(
                "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
                [("user", user_content, now), ("assistant", assistant_content, now)],
            )
            self._conn.commit()

    def recent(self, limit: int) -> list[dict[str, str]]:
        """Return up to `limit` most recent messages, oldest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def clear(self) -> None:
        """Forget everything — used when the user explicitly resets memory."""
        with self._lock:
            self._conn.execute("DELETE FROM messages")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
