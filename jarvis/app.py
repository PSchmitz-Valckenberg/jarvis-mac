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
from .overlay import Overlay
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
        try:
            brain = Brain()
            return brain.ask
        except LLMError as exc:
            message = str(exc)

            def _broken(_prompt: str) -> str:
                raise LLMError(message)

            return _broken

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
        try:
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


def main() -> int:
    return JarvisApp().run()
