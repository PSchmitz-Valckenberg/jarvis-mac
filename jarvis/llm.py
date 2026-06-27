"""Groq LLM connection — the brain of Jarvis."""

from __future__ import annotations

from groq import Groq

from .config import config
from .memory import MemoryStore

SYSTEM_PROMPT = (
    "You are Jarvis, a concise, fast macOS assistant. "
    "Answer directly and briefly unless asked to elaborate. "
    "You run as a small overlay on the user's screen, so keep responses "
    "tight and skimmable. Use plain text, no markdown headers."
)


class LLMError(Exception):
    """Raised when the LLM call fails for any reason."""


class Brain:
    """Thin wrapper around the Groq chat API.

    Keeps a short working-memory window for the live session. When a
    MemoryStore is given, that window is seeded from the most recent turns
    on disk at startup, and every turn is persisted back to it — so a
    conversation survives an app restart instead of starting blank.
    """

    def __init__(self, max_history: int = 12, memory: MemoryStore | None = None) -> None:
        if not config.has_api_key:
            raise LLMError(
                "GROQ_API_KEY is missing. Copy .env.example to .env and add your key."
            )
        self._client = Groq(api_key=config.groq_api_key)
        self._max_history = max_history
        self._memory = memory
        self._history: list[dict[str, str]] = (
            memory.recent(max_history) if memory is not None else []
        )

    def ask(self, prompt: str) -> str:
        """Send a user prompt, return the assistant's reply text."""
        prompt = prompt.strip()
        if not prompt:
            return ""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self._history,
            {"role": "user", "content": prompt},
        ]

        try:
            completion = self._client.chat.completions.create(
                model=config.groq_model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 — surface any Groq/network error cleanly
            raise LLMError(str(exc)) from exc

        reply = (completion.choices[0].message.content or "").strip()

        # Remember this exchange, trimming to the most recent messages
        # (max_history is a message-entry count, not a turn count — each
        # turn adds two entries, user + assistant).
        self._history.append({"role": "user", "content": prompt})
        self._history.append({"role": "assistant", "content": reply})
        self._history = self._history[-self._max_history:]

        if self._memory is not None:
            self._memory.add("user", prompt)
            self._memory.add("assistant", reply)

        return reply

    def reset(self) -> None:
        """Forget the conversation — current session and persisted history."""
        self._history.clear()
        if self._memory is not None:
            self._memory.clear()
