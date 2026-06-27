"""Optional text-to-speech via edge-tts.

Synthesizes speech with Microsoft Edge's free online TTS service, then
plays it back with macOS's built-in `afplay` — no local audio-decoding
dependency needed beyond that system command.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import threading
from pathlib import Path

import edge_tts

from .config import config


class TTSError(Exception):
    """Raised when speech synthesis or playback fails."""


class Speaker:
    """Synthesizes text to speech and plays it back, one utterance at a time."""

    def __init__(self) -> None:
        # Two replies arriving close together (e.g. quick follow-up voice
        # questions) would otherwise start overlapping afplay processes.
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        with self._lock:
            audio_path = self._synthesize(text)
            try:
                subprocess.run(["afplay", str(audio_path)], check=True)
            except Exception as exc:  # noqa: BLE001 — surface any playback error cleanly
                raise TTSError(f"Couldn't play audio: {exc}") from exc
            finally:
                audio_path.unlink(missing_ok=True)

    def _synthesize(self, text: str) -> Path:
        fd, path_str = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        path = Path(path_str)
        try:
            asyncio.run(self._save(text, path))
        except Exception as exc:  # noqa: BLE001 — surface any network/synthesis error cleanly
            path.unlink(missing_ok=True)
            raise TTSError(f"Couldn't synthesize speech: {exc}") from exc
        return path

    async def _save(self, text: str, path: Path) -> None:
        communicate = edge_tts.Communicate(text, config.tts_voice)
        await communicate.save(str(path))
