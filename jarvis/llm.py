"""Groq LLM connection — the brain of Jarvis."""

from __future__ import annotations

import json
import re
import threading
from typing import Any, Callable

from groq import BadRequestError, Groq, RateLimitError

from .config import config
from .memory import MemoryStore
from .profile import ProfileExtractor
from .tools import ToolRegistry

SYSTEM_PROMPT = (
    "You are Jarvis, a calm, precise AI assistant running in a command-center "
    "dashboard. Replies may be read aloud via text-to-speech, so keep them "
    "concise and speakable: short sentences, plain text, no markdown, no "
    "bullet lists unless asked. Reply in the same language the user wrote "
    "in; in German, address the user formally as \"Sie\". You have tools for "
    "real actions on the user's Mac (files, shell, apps, clipboard, browser, "
    "calendar, web search, screen, camera) — use them whenever they'd answer "
    "the request better than just talking, but only when the request "
    "actually calls for one. If the input is unclear, garbled, off-topic, or "
    "in a language/script you're not confident about, ask a short "
    "clarifying question instead of guessing or repeating a previous tool call."
)

# Caps how many tool round-trips a single ask() can take before forcing a
# final answer — without this, a model that keeps calling tools could loop
# indefinitely on one user turn.
MAX_TOOL_ITERATIONS = 6

# Llama models occasionally emit a malformed tool call (e.g. a literal
# "<function=...>" tag instead of proper JSON) when many tools are
# registered; Groq rejects that server-side with a `tool_use_failed` 400.
# It's transient — retrying the same request usually succeeds — so this
# is worth a couple of automatic retries before surfacing an error.
TOOL_USE_FAILED_RETRIES = 2

ToolCallback = Callable[[str, dict[str, Any], str], None]


def _groq_error_message(exc: Exception) -> str:
    """Pull just the human-readable message out of a Groq API error body,
    instead of showing the user the raw {'error': {...}} dict."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = (body.get("error") or {}).get("message")
        if message:
            return str(message)
    return str(exc)


class LLMError(Exception):
    """Raised when the LLM call fails for any reason."""


class Brain:
    """Thin wrapper around the Groq chat API.

    Keeps a short working-memory window for the live session. When a
    MemoryStore is given, that window is seeded from the most recent turns
    on disk at startup, and every turn is persisted back to it — so a
    conversation survives an app restart instead of starting blank.
    """

    def __init__(
        self,
        max_history: int = 12,
        memory: MemoryStore | None = None,
        tools: ToolRegistry | None = None,
        profile_extractor: ProfileExtractor | None = None,
    ) -> None:
        if not config.has_api_key:
            raise LLMError(
                "GROQ_API_KEY is missing. Copy .env.example to .env and add your key."
            )
        self._client = Groq(api_key=config.groq_api_key)
        self._max_history = max_history
        self._memory = memory
        self._tools = tools
        self._profile_extractor = profile_extractor
        # A voice turn and a typed turn can land on self._history from two
        # different threads close enough together to corrupt the list
        # (lost/duplicated entries) without this — guards the read and the
        # append+trim, not the network call itself, so requests still run
        # concurrently.
        self._lock = threading.Lock()
        self._history: list[dict[str, str]] = (
            memory.recent(max_history) if memory is not None else []
        )

    def _create_completion(self, messages: list[dict[str, Any]], tool_kwargs: dict[str, Any]) -> Any:
        attempt = 0
        while True:
            try:
                return self._client.chat.completions.create(
                    model=config.groq_model,
                    messages=messages,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    **tool_kwargs,
                )
            except BadRequestError as exc:
                body = exc.body if isinstance(exc.body, dict) else {}
                code = (body.get("error") or {}).get("code")
                if code == "tool_use_failed" and attempt < TOOL_USE_FAILED_RETRIES:
                    attempt += 1
                    continue
                raise LLMError(_groq_error_message(exc)) from exc
            except RateLimitError as exc:
                message = _groq_error_message(exc)
                wait_match = re.search(r"try again in ([\d.]+)s", message)
                if wait_match:
                    message = f"Rate-Limit bei Groq erreicht. Bitte in {float(wait_match.group(1)):.0f} Sekunden erneut versuchen."
                else:
                    message = "Rate-Limit bei Groq erreicht. Bitte kurz warten und erneut versuchen."
                raise LLMError(message) from exc
            except Exception as exc:  # noqa: BLE001 — surface any other Groq/network error cleanly
                raise LLMError(_groq_error_message(exc)) from exc

    def ask(self, prompt: str, on_tool_call: ToolCallback | None = None) -> str:
        """Send a user prompt, return the assistant's reply text.

        If tools are configured, the model can issue tool calls first; each
        one is executed and fed back before the model gives its final
        answer. Only the user prompt and the final reply are kept in
        history/memory — the intermediate tool-call exchange is scoped to
        this single ask() call, since MemoryStore's schema is plain
        role/content turns.
        """
        prompt = prompt.strip()
        if not prompt:
            return ""

        system_content = SYSTEM_PROMPT
        if self._memory is not None:
            profile = self._memory.get_profile()
            if any(profile.get(key) for key in profile):
                system_content += (
                    "\n\nKnown profile of the user, built up over past conversations — "
                    "use it as context, don't recite it verbatim unless asked:\n"
                    + json.dumps(profile, ensure_ascii=False)
                )

        with self._lock:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_content},
                *self._history,
                {"role": "user", "content": prompt},
            ]

        tool_schemas = self._tools.schemas() if self._tools else None
        tool_kwargs: dict[str, Any] = {}
        if tool_schemas:
            tool_kwargs = {"tools": tool_schemas, "tool_choice": "auto"}

        for _ in range(MAX_TOOL_ITERATIONS):
            completion = self._create_completion(messages, tool_kwargs)

            message = completion.choices[0].message
            tool_calls = message.tool_calls or []
            if not tool_calls:
                reply = (message.content or "").strip()
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                if not isinstance(arguments, dict):
                    # The model occasionally emits a literal `null` or a
                    # non-object value instead of omitting arguments entirely.
                    arguments = {}
                result = self._tools.run(call.function.name, arguments)
                if on_tool_call is not None:
                    try:
                        on_tool_call(call.function.name, arguments, result)
                    except Exception:  # noqa: BLE001 — a broadcast failure shouldn't break the turn
                        pass
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        else:
            reply = "(Stopped after too many tool calls — please try rephrasing.)"

        # Remember this exchange, trimming to the most recent messages
        # (max_history is a message-entry count, not a turn count — each
        # turn adds two entries, user + assistant).
        with self._lock:
            self._history.append({"role": "user", "content": prompt})
            self._history.append({"role": "assistant", "content": reply})
            self._history = self._history[-self._max_history:]

        if self._memory is not None:
            # Best-effort: a reply the user already has shouldn't turn into
            # an error just because the disk write behind it failed.
            try:
                self._memory.add_turn(prompt, reply)
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️  Couldn't persist this turn to memory: {exc}")

        if self._profile_extractor is not None:
            # Runs an extra Groq call — kept off the request path entirely
            # so it can never add latency to the reply the user is waiting on.
            threading.Thread(
                target=self._profile_extractor.update_from_turn,
                args=(prompt, reply),
                daemon=True,
            ).start()

        return reply

    def reset(self) -> None:
        """Forget the conversation — current session and persisted history."""
        with self._lock:
            self._history.clear()
        if self._memory is not None:
            try:
                self._memory.clear()
            except Exception as exc:  # noqa: BLE001 — best-effort, see ask()
                print(f"⚠️  Couldn't clear persisted memory: {exc}")
