"""Structured user profile extraction (Phase 3).

Instead of just replaying the last N raw turns, Jarvis keeps a small
structured JSON profile — projects, goals, daily patterns, preferences —
that's fed back into every prompt as context (see Brain.ask in llm.py).

After each turn, a lightweight/cheap Groq model reads the exchange and
returns a *patch*: only what's new or changed, omitting anything the
exchange gives no evidence for. The patch is merged additively — nothing
gets deleted automatically, since "the model didn't mention it this turn"
isn't evidence it stopped being true.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from .memory import MemoryStore

EXTRACTION_SYSTEM_PROMPT = (
    "You maintain a long-term structured profile of the user from chat "
    "exchanges. Given one exchange, output a JSON *patch* — only new or "
    "changed information from this exchange, in this shape:\n"
    '{"projects": {"<name>": {"status": "...", "priority": <1-5>, "notes": "..."}}, '
    '"goals": ["..."], "daily_patterns": {"<key>": "..."}, "preferences": {"<key>": "..."}}\n'
    "Omit any top-level key entirely if this exchange gives no evidence for "
    "it. If there's nothing worth remembering, output {}. Never invent "
    "facts not actually present in the exchange. Output JSON only, no prose."
)


def _apply_patch(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "projects": dict(current.get("projects") or {}),
        "goals": list(current.get("goals") or []),
        "daily_patterns": dict(current.get("daily_patterns") or {}),
        "preferences": dict(current.get("preferences") or {}),
    }

    patched_projects = patch.get("projects")
    if isinstance(patched_projects, dict):
        for name, info in patched_projects.items():
            if isinstance(name, str) and isinstance(info, dict):
                result["projects"].setdefault(name, {}).update(info)

    patched_goals = patch.get("goals")
    if isinstance(patched_goals, list):
        existing_lower = {g.lower() for g in result["goals"] if isinstance(g, str)}
        for goal in patched_goals:
            if isinstance(goal, str) and goal.lower() not in existing_lower:
                result["goals"].append(goal)
                existing_lower.add(goal.lower())

    patched_patterns = patch.get("daily_patterns")
    if isinstance(patched_patterns, dict):
        result["daily_patterns"].update(patched_patterns)

    patched_prefs = patch.get("preferences")
    if isinstance(patched_prefs, dict):
        result["preferences"].update(patched_prefs)

    return result


class ProfileExtractor:
    """Runs the per-turn extraction call and merges the result into MemoryStore."""

    def __init__(self, memory: MemoryStore) -> None:
        from .config import config
        from groq import Groq

        self._memory = memory
        self._client = Groq(api_key=config.groq_api_key)
        self._model = config.profile_extraction_model
        # Read-modify-write of the profile must be serialized, or two
        # concurrent turns (voice + typed) could both read the same
        # baseline and one's patch would clobber the other's.
        self._lock = threading.Lock()

    def update_from_turn(self, user_text: str, assistant_text: str) -> None:
        """Best-effort — call this from a background thread, never the request path."""
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"User: {user_text}\nAssistant: {assistant_text}",
                    },
                ],
                temperature=0,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            patch = json.loads(completion.choices[0].message.content or "{}")
        except Exception as exc:  # noqa: BLE001 — extraction failing must never break the chat turn
            print(f"⚠️  Profile extraction failed: {exc}")
            return

        if not isinstance(patch, dict) or not patch:
            return

        with self._lock:
            current = self._memory.get_profile()
            self._memory.set_profile(_apply_patch(current, patch))
