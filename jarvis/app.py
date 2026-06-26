"""Wires the pieces together into the core loop.

    hold hotkey (Option) ──▶ overlay shows "Listening…" ──▶ release
        ──▶ transcribe (local Whisper) ──▶ Groq ──▶ reply

    tap hotkey ──▶ overlay opens for typed text ──▶ Groq ──▶ reply

The hotkey listener runs in its own thread; it can't touch the GUI directly,
so it emits Qt signals that are delivered on the main thread.
"""

from __future__ import annotations

import sys
import threading
import time

from PySide6.QtCore import QObject, Qt, Signal
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
        self.recorder = Recorder()
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

    # ── Hotkey handlers (GUI thread) ────────────────────────────────
    def _on_press(self) -> None:
        if self.overlay.isVisible():
            # Second tap while open: close it and abandon any recording.
            if self._recording_started_at is not None:
                self.recorder.stop()
                self._recording_started_at = None
            self.overlay.hide()
            return

        self._recording_started_at = time.monotonic()
        self.overlay.show_listening()
        try:
            self.recorder.start()
        except VoiceError as exc:
            self._recording_started_at = None
            self.overlay.show_voice_error(str(exc))

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
        try:
            return self.qt.exec()
        finally:
            self.listener.stop()


def main() -> int:
    return JarvisApp().run()
