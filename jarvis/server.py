"""WebSocket/HTTP bridge between the Python backend and the Electron dashboard.

Runs the same hotkey → recorder → transcriber → Brain → Speaker pipeline
that the old PySide6 overlay used, but broadcasts state over a WebSocket
instead of driving a Qt widget — the React dashboard renders it.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .hotkey import HotkeyListener
from .llm import Brain, LLMError
from .memory import MemoryStore
from .tts import Speaker, TTSError
from .voice import Recorder, Transcriber, VoiceError

GREETING = "Ich habe Sie gehört, Meister. Alle Systeme sind jetzt online."


class Hub:
    """Tracks connected WebSocket clients and broadcasts JSON events to all of them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def register(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    def broadcast(self, event: dict[str, Any]) -> None:
        """Thread-safe: called from the pynput hotkey thread and worker threads."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast_async(event), self._loop)

    async def _broadcast_async(self, event: dict[str, Any]) -> None:
        message = json.dumps(event)
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001 — a dead socket shouldn't break the broadcast
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


hub = Hub()


class JarvisBackend:
    """Owns every long-lived piece: Brain, memory, mic, transcriber, speaker."""

    def __init__(self) -> None:
        self.memory = self._build_memory()
        self.speaker = Speaker() if config.tts_enabled else None

        self.brain: Brain | None = None
        self.brain_error: str | None = None
        try:
            self.brain = Brain(memory=self.memory)
        except LLMError as exc:
            self.brain_error = str(exc)

        self.recorder, self.recorder_error = self._build_recorder()
        self.transcriber: Transcriber | None = None  # lazy: model load is slow
        self._transcribe_lock = threading.Lock()
        self._recording_started_at: float | None = None

        self.listener = HotkeyListener(
            hotkey=config.hotkey,
            on_press=self._on_press,
            on_release=self._on_release,
        )

    def _build_memory(self) -> MemoryStore | None:
        if not config.memory_enabled:
            return None
        try:
            return MemoryStore(config.memory_db_path)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully, don't crash startup
            print(f"⚠️  Persistent memory unavailable: {exc}")
            return None

    def _build_recorder(self):
        try:
            return Recorder(), None
        except VoiceError as exc:
            return None, str(exc)

    def status(self) -> dict[str, Any]:
        return {
            "has_api_key": config.has_api_key,
            "model": config.groq_model,
            "hotkey": config.hotkey,
            "memory_enabled": self.memory is not None,
            "memory_turns": len(self.memory.recent(10_000)) if self.memory else 0,
            "tts_enabled": self.speaker is not None,
            "voice_available": self.recorder is not None,
        }

    # ── Hotkey handlers (pynput thread) ─────────────────────────────
    def _on_press(self) -> None:
        if self.recorder is None:
            hub.broadcast({"type": "error", "message": self.recorder_error})
            return
        self._recording_started_at = time.monotonic()
        hub.broadcast({"type": "state", "state": "listening"})
        self.recorder.start()

    def _on_release(self) -> None:
        if self._recording_started_at is None:
            return  # recording wasn't running (e.g. mic failed to open)

        held_for = time.monotonic() - self._recording_started_at
        self._recording_started_at = None
        audio = self.recorder.stop()

        if held_for < config.min_record_seconds:
            hub.broadcast({"type": "state", "state": "idle"})
            return

        hub.broadcast({"type": "state", "state": "transcribing"})
        threading.Thread(target=self._transcribe_worker, args=(audio,), daemon=True).start()

    def _transcribe_worker(self, audio) -> None:
        # A follow-up hold can start a second worker while one is still
        # transcribing; the model isn't safe for concurrent use.
        try:
            with self._transcribe_lock:
                if self.transcriber is None:
                    self.transcriber = Transcriber()
                text = self.transcriber.transcribe(audio)
        except VoiceError as exc:
            hub.broadcast({"type": "error", "message": str(exc)})
            hub.broadcast({"type": "state", "state": "idle"})
            return

        if not text:
            hub.broadcast({"type": "error", "message": "(didn't catch that — try again)"})
            hub.broadcast({"type": "state", "state": "idle"})
            return

        hub.broadcast({"type": "transcript", "text": text})
        self._ask_and_reply(text)

    def ask_text(self, prompt: str) -> None:
        """Entry point for typed input coming from the dashboard via HTTP."""
        threading.Thread(target=self._ask_and_reply, args=(prompt,), daemon=True).start()

    def _ask_and_reply(self, prompt: str) -> None:
        hub.broadcast({"type": "state", "state": "thinking"})
        try:
            if self.brain is None:
                raise LLMError(self.brain_error or "LLM not configured")
            reply = self.brain.ask(prompt)
        except LLMError as exc:
            hub.broadcast({"type": "error", "message": str(exc)})
            hub.broadcast({"type": "state", "state": "idle"})
            return
        except Exception as exc:  # noqa: BLE001 — never leave the dashboard stuck "thinking"
            hub.broadcast({"type": "error", "message": f"Unexpected error: {exc}"})
            hub.broadcast({"type": "state", "state": "idle"})
            return

        hub.broadcast({"type": "reply", "text": reply})

        if self.speaker is not None and reply:
            hub.broadcast({"type": "state", "state": "speaking"})
            try:
                self.speaker.speak(reply)
            except TTSError as exc:
                print(f"⚠️  TTS failed: {exc}")

        hub.broadcast({"type": "state", "state": "idle"})

    def speak_greeting(self) -> None:
        if self.speaker is None:
            return
        try:
            self.speaker.speak(GREETING)
        except TTSError as exc:
            print(f"⚠️  Greeting TTS failed: {exc}")

    def start(self) -> None:
        self.listener.start()

    def shutdown(self) -> None:
        self.listener.stop()
        if self.recorder is not None:
            self.recorder.close()
        if self.memory is not None:
            self.memory.close()


backend = JarvisBackend()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    hub.bind_loop(asyncio.get_running_loop())

    def _startup_sequence() -> None:
        # Greet before the hotkey listener goes live (so a hold during the
        # greeting can't race with it), but do this in the background:
        # blocking the lifespan itself here would hold up uvicorn's startup,
        # leaving the dashboard's first WebSocket/HTTP calls hanging for
        # however long TTS synthesis + playback takes.
        backend.speak_greeting()
        backend.start()

    threading.Thread(target=_startup_sequence, daemon=True).start()
    try:
        yield
    finally:
        backend.shutdown()


app = FastAPI(lifespan=lifespan)

# The dashboard runs from a different origin (Vite's localhost:5173 in dev,
# file:// once built) than this server (127.0.0.1:8765) — without this,
# the browser silently drops every /api/* response and the dashboard's
# status panels show nothing despite the server logging 200s. Only ever
# bound to 127.0.0.1, so a permissive origin policy here is low-risk.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    return backend.status()


@app.post("/api/ask")
async def post_ask(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = (payload.get("prompt") or "").strip()
    if prompt:
        backend.ask_text(prompt)
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    hub.register(ws)
    try:
        while True:
            await ws.receive_text()  # no inbound messages expected; just keep it open
    except WebSocketDisconnect:
        hub.unregister(ws)


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
