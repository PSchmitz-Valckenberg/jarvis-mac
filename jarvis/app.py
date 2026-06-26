"""Wires the pieces together into the core loop.

    hotkey (Option)  ──▶  overlay pops up  ──▶  text  ──▶  Groq  ──▶  reply

The hotkey listener runs in its own thread; it can't touch the GUI directly,
so it emits a Qt signal that is delivered on the main thread.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from .config import config
from .hotkey import HotkeyListener
from .llm import Brain, LLMError
from .overlay import Overlay


class _Bridge(QObject):
    """Marshals the background hotkey thread onto the GUI thread."""

    activate = Signal()


class JarvisApp:
    def __init__(self) -> None:
        self.qt = QApplication(sys.argv)
        # Overlay hides instead of quitting, so don't exit when it disappears.
        self.qt.setQuitOnLastWindowClosed(False)

        ask = self._build_ask()
        self.overlay = Overlay(ask=ask)

        self.bridge = _Bridge()
        self.bridge.activate.connect(self._toggle, Qt.ConnectionType.QueuedConnection)

        self.listener = HotkeyListener(
            hotkey=config.hotkey,
            on_press=self.bridge.activate.emit,
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

    def _toggle(self) -> None:
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.pop_up()

    def run(self) -> int:
        self.listener.start()
        print(f"Jarvis ready — tap [{config.hotkey}] to summon. (Ctrl+C to quit)")
        if not config.has_api_key:
            print("⚠️  No GROQ_API_KEY set — copy .env.example to .env and add your key.")
        try:
            return self.qt.exec()
        finally:
            self.listener.stop()


def main() -> int:
    return JarvisApp().run()
