"""Minimal dark Mac-style overlay.

A frameless, translucent, rounded window that pops up near the top of the
screen, takes a text query, and shows Jarvis's reply. The LLM call runs in a
background thread so typing/animation never freezes.
"""

from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QFontMetrics, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

# Mac-style dark glass look. Colors kept in one place for easy theming.
_STYLE = """
#card {
    background-color: rgba(28, 28, 30, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
}
#input {
    background: transparent;
    border: none;
    color: #f5f5f7;
    font-size: 20px;
    padding: 6px 2px;
}
#input::placeholder { color: rgba(235, 235, 245, 0.35); }
#reply {
    color: #e3e3e6;
    font-size: 15px;
    line-height: 1.4em;
    padding: 2px;
}
#hint { color: rgba(235, 235, 245, 0.30); font-size: 11px; }
#status { color: rgba(235, 235, 245, 0.55); font-size: 14px; padding: 6px 2px; }
"""


class Overlay(QWidget):
    """The pop-up window. Owns a text input and a reply area."""

    # Emitted from the worker thread; delivered on the GUI thread (queued).
    _reply_ready = Signal(str)
    _error = Signal(str)

    def __init__(self, ask: Callable[[str], str]) -> None:
        super().__init__()
        self._ask = ask

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(620)

        self._build_ui()
        self._reply_ready.connect(self._on_reply)
        self._error.connect(self._on_error)

    # ── UI construction ────────────────────────────────────────────
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(_STYLE)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(10)

        self._input = QLineEdit(card)
        self._input.setObjectName("input")
        self._input.setPlaceholderText("Ask Jarvis…")
        self._input.returnPressed.connect(self._submit)
        layout.addWidget(self._input)

        self._status = QLabel(card)
        self._status.setObjectName("status")
        self._status.hide()
        layout.addWidget(self._status)

        self._reply = QLabel(card)
        self._reply.setObjectName("reply")
        self._reply.setWordWrap(True)
        self._reply.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Fix the wrap width up front. QLabel's wrapped-text height depends on
        # its width, and without this it can report a stale (too small)
        # sizeHint right after show(), before the layout has settled —
        # causing the reply to overlap the hint line below it.
        margins = layout.contentsMargins()
        self._reply.setFixedWidth(self.width() - margins.left() - margins.right())
        self._reply.hide()
        layout.addWidget(self._reply)

        self._hint = QLabel("Enter to send · Esc to close · hold ⌥ to talk", card)
        self._hint.setObjectName("hint")
        layout.addWidget(self._hint)

    # ── Behaviour ──────────────────────────────────────────────────
    def _submit(self) -> None:
        prompt = self._input.text().strip()
        if not prompt:
            return
        self._input.setEnabled(False)
        self._show_reply("…thinking")

        # Run the (blocking) network call off the GUI thread.
        threading.Thread(target=self._worker, args=(prompt,), daemon=True).start()

    # ── Voice (hold-to-talk) ───────────────────────────────────────
    def show_listening(self) -> None:
        """Hold started: show the overlay in a recording state."""
        self._reply.hide()
        self._input.clear()
        self._input.setEnabled(False)
        self._status.setText("🔴 Listening…")
        self._status.show()
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self.activateWindow()

    def show_transcribing(self) -> None:
        """Hold released: recording stopped, now running STT."""
        self._status.setText("Transcribing…")

    def cancel_listening(self) -> None:
        """Hold was too short — drop back to normal text-input mode."""
        self._status.hide()
        self._input.setEnabled(True)
        self._input.setFocus()

    def submit_voice_text(self, text: str) -> None:
        """Transcription succeeded: show what was heard, then send it."""
        text = text.strip()
        self._input.setEnabled(True)
        if not text:
            self._status.hide()
            self._show_reply("(didn't catch that — try again)")
            self._input.setFocus()
            return
        # Keep the heard text visible (it survives the reply lifecycle, so
        # you can tell whether the STT misheard you instead of just getting
        # a confusing reply with no context).
        self._status.setText(f"🎤 “{text}”")
        self._status.show()
        self._input.setText(text)
        self._submit()

    def show_voice_error(self, message: str) -> None:
        self._status.hide()
        self._input.setEnabled(True)
        self._show_reply(f"⚠️  {message}")
        self._input.setFocus()

    def _worker(self, prompt: str) -> None:
        try:
            self._reply_ready.emit(self._ask(prompt))
        except Exception as exc:  # noqa: BLE001 — report any failure in the UI
            self._error.emit(str(exc))

    def _on_reply(self, text: str) -> None:
        self._show_reply(text or "(no response)")
        self._input.setEnabled(True)
        self._input.clear()
        self._input.setFocus()

    def _on_error(self, message: str) -> None:
        self._show_reply(f"⚠️  {message}")
        self._input.setEnabled(True)
        self._input.setFocus()

    def _show_reply(self, text: str) -> None:
        self._reply.setText(text)
        # Compute the wrapped height directly from font metrics instead of
        # trusting QLabel's sizeHint() — on a label that's never been
        # painted yet, sizeHint() can report a stale, too-short height,
        # which made multi-line replies overlap the hint line below them.
        # ensurePolished() makes the stylesheet's font-size actually land on
        # self._reply.font() before we measure it — without it, the very
        # first measurement on a real (non-offscreen) platform can still be
        # using the pre-stylesheet default font and undershoot.
        self._reply.ensurePolished()
        metrics = QFontMetrics(self._reply.font())
        bounds = metrics.boundingRect(
            QRect(0, 0, self._reply.width(), 0),
            Qt.TextFlag.TextWordWrap,
            text,
        )
        # Generous safety margin: real-platform font rendering (Retina,
        # ligatures, the CSS padding) has measured a bit taller than plain
        # font-metrics math predicts.
        self._reply.setFixedHeight(int(bounds.height() * 1.25) + 16)
        self._reply.show()
        self.adjustSize()
        self._reposition()

    # ── Window placement / focus ───────────────────────────────────
    def _reposition(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + int(screen.height() * 0.22)
        self.move(x, y)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt override
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
