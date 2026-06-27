"""Wires the pieces together into the core loop.

    hold hotkey (Option) ──▶ overlay shows "Listening…" ──▶ release
        ──▶ transcribe (local Whisper) ──▶ Groq ──▶ reply

    tap hotkey ──▶ overlay opens for typed text ──▶ Groq ──▶ reply

The hotkey listener runs in its own thread; it can't touch the GUI directly,
so it emits Qt signals that are delivered on the main thread.
"""

from __future__ import annotations

import signal
import sys
import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication

from .config import config
from .hotkey import HotkeyListener
from .llm import Brain, LLMError
from .memory import MemoryStore
from .overlay import Overlay
from .tts import Speaker, TTSError
from .voice import Recorder, Transcriber, VoiceError


class _Bridge(QObject):
    """Marshals background-thread events onto the GUI thread."""

    pressed = Signal()
    released = Signal()
    transcribed = Signal(str)
    transcribe_error = Signal(str)


class JarvisApp:
    def __init__(self) -> None:
        self.qt = QApplication(sys.argv)
        # Overlay hides instead of quitting, so don't exit when it disappears.
        self.qt.setQuitOnLastWindowClosed(False)

        ask = self._build_ask()
        self.overlay = Overlay(ask=ask)
        self.recorder, self._recorder_error = self._build_recorder()
        self._transcriber: Transcriber | None = None  # lazy: model load is slow
        self._transcribe_lock = threading.Lock()  # the model isn't thread-safe
        self._recording_started_at: float | None = None

        self.bridge = _Bridge()
        self.bridge.pressed.connect(self._on_press, Qt.ConnectionType.QueuedConnection)
        self.bridge.released.connect(self._on_release, Qt.ConnectionType.QueuedConnection)
        self.bridge.transcribed.connect(self.overlay.submit_voice_text)
        self.bridge.transcribe_error.connect(self.overlay.show_voice_error)

        self.listener = HotkeyListener(
            hotkey=config.hotkey,
            on_press=self.bridge.pressed.emit,
            on_release=self.bridge.released.emit,
        )

    def _build_ask(self):
        """Return an ask(prompt)->str callable, or one that reports setup errors."""
        self.memory = self._build_memory()
        self.speaker = Speaker() if config.tts_enabled else None

        try:
            brain = Brain(memory=self.memory)
            ask = brain.ask
        except LLMError as exc:
            message = str(exc)

            def ask(_prompt: str) -> str:
                raise LLMError(message)

        if self.speaker is None:
            return ask

        def ask_and_speak(prompt: str) -> str:
            reply = ask(prompt)
            if reply:
                threading.Thread(target=self._speak, args=(reply,), daemon=True).start()
            return reply

        return ask_and_speak

    def _speak(self, text: str) -> None:
        # Best-effort: a TTS hiccup (network down, edge-tts service issue)
        # shouldn't disrupt the text reply the user already has.
        try:
            self.speaker.speak(text)
        except TTSError as exc:
            print(f"⚠️  TTS failed: {exc}")

    def _build_memory(self) -> MemoryStore | None:
        """Return a MemoryStore, or None if memory is disabled/unavailable.

        Persistence is best-effort: a broken DB file shouldn't stop the app
        from working, just mean it starts each session with a blank slate.
        """
        if not config.memory_enabled:
            return None
        try:
            return MemoryStore(config.memory_db_path)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully, don't crash startup
            print(f"⚠️  Persistent memory unavailable: {exc}")
            return None

    def _build_recorder(self):
        """Return (Recorder, None) or (None, error message) if the mic can't open."""
        try:
            return Recorder(), None
        except VoiceError as exc:
            return None, str(exc)

    # ── Hotkey handlers (GUI thread) ────────────────────────────────
    def _on_press(self) -> None:
        # Every press (re)starts a fresh recording, even if the overlay is
        # already open showing a previous reply — that's how follow-up
        # questions work. Esc is the only way to dismiss the overlay.
        if self.recorder is None:
            self.overlay.show_voice_error(self._recorder_error)
            return
        self._recording_started_at = time.monotonic()
        self.overlay.show_listening()
        self.recorder.start()

    def _on_release(self) -> None:
        if self._recording_started_at is None:
            return  # recording wasn't running (e.g. mic failed to open)

        held_for = time.monotonic() - self._recording_started_at
        self._recording_started_at = None
        audio = self.recorder.stop()

        if held_for < config.min_record_seconds:
            # Treat as a quick tap: stay open for typed input, no transcription.
            self.overlay.cancel_listening()
            return

        self.overlay.show_transcribing()
        threading.Thread(target=self._transcribe_worker, args=(audio,), daemon=True).start()

    def _transcribe_worker(self, audio) -> None:
        # A follow-up hold can start a second worker while one is still
        # transcribing; the model isn't safe for concurrent use, so only
        # one transcription runs at a time.
        try:
            with self._transcribe_lock:
                if self._transcriber is None:
                    self._transcriber = Transcriber()
                text = self._transcriber.transcribe(audio)
            self.bridge.transcribed.emit(text)
        except VoiceError as exc:
            self.bridge.transcribe_error.emit(str(exc))

    def run(self) -> int:
        self.listener.start()
        print(f"Jarvis ready — hold [{config.hotkey}] to talk, tap it to type. (Ctrl+C to quit)")
        if not config.has_api_key:
            print("⚠️  No GROQ_API_KEY set — copy .env.example to .env and add your key.")
        if self.recorder is None:
            print(f"⚠️  Voice input unavailable: {self._recorder_error}")

        # Qt's native event loop swallows SIGINT; a recurring no-op timer
        # hands control back to the Python interpreter often enough for
        # Ctrl+C to actually register.
        signal.signal(signal.SIGINT, lambda *_: self.qt.quit())
        keepalive = QTimer()
        keepalive.timeout.connect(lambda: None)
        keepalive.start(200)

        try:
            return self.qt.exec()
        finally:
            self.listener.stop()
            if self.recorder is not None:
                self.recorder.close()
            if self.memory is not None:
                self.memory.close()


def main() -> int:
    return JarvisApp().run()
