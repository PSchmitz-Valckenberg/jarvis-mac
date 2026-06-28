"""FastAPI backend: WebSocket/HTTP bridge for the React dashboard, which
this same process serves at /dashboard.

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
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import config
from .dashboard import DashboardService
from .hotkey import HotkeyListener
from .llm import Brain, LLMError
from .memory import MemoryStore
from .portfolio import PortfolioService
from .proactive import ProactivityEngine
from .profile import ProfileExtractor
from .tools import build_default_registry
from .tts import PRESET_VOICES, Speaker, TTSError
from .voice import Recorder, Transcriber, VoiceError

DASHBOARD_DIST_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "dist"

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

        self.tools = build_default_registry() if config.tools_enabled else None

        # Structured profile extraction needs somewhere to persist the
        # profile — without MemoryStore there's nothing to build on.
        self.profile_extractor = (
            ProfileExtractor(self.memory)
            if config.profile_enabled and self.memory is not None
            else None
        )

        self.brain: Brain | None = None
        self.brain_error: str | None = None
        try:
            self.brain = Brain(memory=self.memory, tools=self.tools, profile_extractor=self.profile_extractor)
        except LLMError as exc:
            self.brain_error = str(exc)

        self.recorder, self.recorder_error = self._build_recorder()
        self.transcriber: Transcriber | None = None  # lazy: model load is slow
        self._transcribe_lock = threading.Lock()
        self._recording_started_at: float | None = None

        # Bumped on every new turn (press, or a fresh ask). Lets an
        # in-flight ask/speak notice it's been superseded — e.g. the user
        # barges in while Jarvis is still talking — and skip its trailing
        # state broadcasts instead of clobbering the new "listening" state.
        self._generation_lock = threading.Lock()
        self._generation = 0

        self.listener = HotkeyListener(
            hotkey=config.hotkey,
            on_press=self._on_press,
            on_release=self._on_release,
        )

        self.proactivity = (
            ProactivityEngine(speak=self._speak_proactive, broadcast=hub.broadcast)
            if config.proactivity_enabled
            else None
        )

        self.portfolio = PortfolioService(
            db_path=config.dashboard_db_path,
            host=config.ibkr_host,
            port=config.ibkr_port,
            client_id=config.ibkr_client_id,
            on_update=lambda data: hub.broadcast({"type": "portfolio_update", "portfolio": data}),
        )
        self.dashboard = DashboardService(db_path=config.dashboard_db_path, broadcast=hub.broadcast)

    def _build_memory(self) -> MemoryStore | None:
        if not config.memory_enabled:
            return None
        try:
            return MemoryStore(config.memory_db_path)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully, don't crash startup
            print(f"⚠️  Persistent memory unavailable: {exc}")
            return None

    def _speak_proactive(self, text: str) -> None:
        """TTS for proactive announcements — a no-op if TTS isn't configured;
        the dashboard still gets the text via the broadcast in ProactivityEngine."""
        if self.speaker is None:
            return
        try:
            self.speaker.speak(text)
        except TTSError as exc:
            print(f"⚠️  Proactive TTS failed: {exc}")

    def _build_recorder(self):
        try:
            return Recorder(), None
        except VoiceError as exc:
            return None, str(exc)

    def _bump_generation(self) -> int:
        with self._generation_lock:
            self._generation += 1
            return self._generation

    def _is_current(self, generation: int) -> bool:
        with self._generation_lock:
            return self._generation == generation

    def status(self) -> dict[str, Any]:
        return {
            "has_api_key": config.has_api_key,
            "model": config.groq_model,
            "hotkey": config.hotkey,
            "memory_enabled": self.memory is not None,
            "memory_turns": len(self.memory.recent(10_000)) if self.memory else 0,
            "tts_enabled": self.speaker is not None,
            "voice_available": self.recorder is not None,
            "tools_enabled": self.tools is not None,
            "tools": self.tools.names() if self.tools else [],
            "proactivity_enabled": self.proactivity is not None,
            "profile_enabled": self.profile_extractor is not None,
        }

    # ── Hotkey handlers (pynput thread) ─────────────────────────────
    def _on_press(self) -> None:
        if self.proactivity is not None:
            self.proactivity.note_activity()
        # Barge-in: holding the hotkey while Jarvis is still talking cuts
        # the speech off immediately instead of waiting for it to finish.
        self._bump_generation()
        if self.speaker is not None:
            self.speaker.interrupt()

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
        if self.proactivity is not None:
            self.proactivity.note_activity()
        threading.Thread(target=self._ask_and_reply, args=(prompt,), daemon=True).start()

    def _ask_and_reply(self, prompt: str) -> None:
        generation = self._bump_generation()
        hub.broadcast({"type": "state", "state": "thinking"})
        def _on_tool_call(name: str, arguments: dict[str, Any], result: str) -> None:
            hub.broadcast({"type": "tool_call", "name": name, "arguments": arguments, "result": result})

        try:
            if self.brain is None:
                raise LLMError(self.brain_error or "LLM not configured")
            reply = self.brain.ask(prompt, on_tool_call=_on_tool_call)
        except LLMError as exc:
            hub.broadcast({"type": "error", "message": str(exc)})
            if self._is_current(generation):
                hub.broadcast({"type": "state", "state": "idle"})
            return
        except Exception as exc:  # noqa: BLE001 — never leave the dashboard stuck "thinking"
            hub.broadcast({"type": "error", "message": f"Unexpected error: {exc}"})
            if self._is_current(generation):
                hub.broadcast({"type": "state", "state": "idle"})
            return

        hub.broadcast({"type": "reply", "text": reply})

        # If a newer turn has started since (e.g. the user already barged
        # in again), don't start talking over it or stomp its state with
        # our own trailing "idle".
        if self.speaker is not None and reply and self._is_current(generation):
            hub.broadcast({"type": "state", "state": "speaking"})
            try:
                self.speaker.speak(reply)
            except TTSError as exc:
                print(f"⚠️  TTS failed: {exc}")

        if self._is_current(generation):
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
        if self.proactivity is not None:
            self.proactivity.start()
        self.portfolio.start()
        self.dashboard.start()

    def shutdown(self) -> None:
        self.listener.stop()
        if self.proactivity is not None:
            self.proactivity.shutdown()
        self.portfolio.stop()
        self.dashboard.shutdown()
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

# In dev, the dashboard runs from Vite's localhost:5174, a different
# origin than this server (127.0.0.1:8765) — without this, the browser
# silently drops every /api/* response and the dashboard's status panels
# show nothing despite the server logging 200s. In production the
# dashboard is served from this same origin (/dashboard), so this is only
# load-bearing in dev — but it's only ever bound to 127.0.0.1, so a
# permissive origin policy here is low-risk either way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    return backend.status()


@app.get("/api/profile")
async def get_profile() -> dict[str, Any]:
    if backend.memory is None:
        return {"enabled": False, "profile": None}
    return {"enabled": True, "profile": backend.memory.get_profile()}


@app.get("/api/voices")
async def get_voices() -> dict[str, Any]:
    if backend.speaker is None:
        return {"enabled": False, "active": None, "presets": []}
    return {
        "enabled": backend.speaker.is_elevenlabs_active(),
        "active": backend.speaker.current_voice_id(),
        "presets": PRESET_VOICES,
    }


@app.post("/api/voice")
async def post_voice(payload: dict[str, Any]) -> dict[str, Any]:
    voice_id = (payload.get("voice_id") or "").strip()
    if backend.speaker is None or not voice_id:
        return {"ok": False}
    return {"ok": backend.speaker.set_voice(voice_id)}


@app.post("/api/ask")
async def post_ask(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = (payload.get("prompt") or "").strip()
    if prompt:
        backend.ask_text(prompt)
    return {"ok": True}


@app.get("/api/portfolio")
async def get_portfolio() -> dict[str, Any]:
    return backend.portfolio.latest()


@app.get("/api/portfolio/sparkline/{symbol}")
async def get_portfolio_sparkline(symbol: str) -> dict[str, Any]:
    return {"symbol": symbol, "values": backend.portfolio.sparkline(symbol)}


# These four call blocking I/O (AppleScript, the `gh` CLI, HTTP requests)
# that can take anywhere from a couple seconds to tens of seconds. Defined
# as plain `def`, not `async def`, on purpose — Starlette runs sync route
# handlers in a thread pool automatically, whereas blocking inside an
# `async def` would freeze the *entire* event loop (every other request,
# including the WebSocket) for as long as the slowest of these takes.
@app.get("/api/calendar")
def get_calendar() -> dict[str, Any]:
    return {"events": backend.dashboard.get_calendar()}


@app.get("/api/github")
def get_github() -> dict[str, Any]:
    return {"repos": backend.dashboard.get_github()}


@app.get("/api/weather")
def get_weather() -> dict[str, Any]:
    return {"weather": backend.dashboard.get_weather()}


@app.get("/api/news")
def get_news() -> dict[str, Any]:
    return backend.dashboard.get_news_with_points()


@app.get("/api/morning-score")
async def get_morning_score() -> dict[str, Any]:
    return {"score": backend.dashboard.get_morning_score()}


@app.post("/api/morning-score")
async def post_morning_score(payload: dict[str, Any]) -> dict[str, Any]:
    score = max(1, min(int(payload.get("score", 0)), 10))
    backend.dashboard.set_morning_score(score)
    return {"ok": True, "score": score}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    hub.register(ws)
    try:
        while True:
            await ws.receive_text()  # no inbound messages expected; just keep it open
    except WebSocketDisconnect:
        hub.unregister(ws)


# Serves the built dashboard (dashboard/dist, produced by `npm run build`)
# at /dashboard — mounted last so it never shadows a more specific /api/*
# route. Absent in dev (before the first build), so this is conditional.
if DASHBOARD_DIST_DIR.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIST_DIR), html=True), name="dashboard")


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
