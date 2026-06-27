"""Persistent conversation memory via SQLite.

Every turn gets appended to a local SQLite file, so Jarvis can pick a
conversation back up after a restart instead of starting blank each time.

Also holds the structured user profile (Phase 3) — projects, goals,
patterns, preferences — in the same file, since it's small, single-row,
and tied to the same lifetime as the raw conversation log.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DEFAULT_PROFILE: dict[str, Any] = {
    "projects": {},
    "goals": [],
    "daily_patterns": {},
    "preferences": {},
}


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
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    data TEXT NOT NULL
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

    def get_profile(self) -> dict[str, Any]:
        """The structured profile (projects/goals/patterns/preferences)."""
        with self._lock:
            row = self._conn.execute("SELECT data FROM profile WHERE id = 1").fetchone()
        if row is None:
            return json.loads(json.dumps(DEFAULT_PROFILE))  # deep copy, not the shared default
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return json.loads(json.dumps(DEFAULT_PROFILE))

    def set_profile(self, profile: dict[str, Any]) -> None:
        payload = json.dumps(profile, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO profile (id, data) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                (payload,),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
