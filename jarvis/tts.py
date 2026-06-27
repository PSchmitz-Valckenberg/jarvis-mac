"""Optional text-to-speech: ElevenLabs first, edge-tts as a free fallback.

Both backends just need to produce an mp3 file; playback is shared via
macOS's built-in `afplay` — no local audio-decoding dependency needed.
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


class _EdgeTTSBackend:
    """Free, no API key — used by default and as the ElevenLabs fallback."""

    def synthesize(self, text: str, path: Path) -> None:
        try:
            asyncio.run(self._save(text, path))
        except Exception as exc:  # noqa: BLE001 — surface any network/synthesis error cleanly
            raise TTSError(f"Couldn't synthesize speech (edge-tts): {exc}") from exc

    async def _save(self, text: str, path: Path) -> None:
        communicate = edge_tts.Communicate(text, config.tts_voice)
        await communicate.save(str(path))


class _ElevenLabsBackend:
    """Higher-quality voices; free tier is ~10k characters/month."""

    def __init__(self, api_key: str, voice_id: str) -> None:
        from elevenlabs.client import ElevenLabs

        self._client = ElevenLabs(api_key=api_key)
        self._voice_id = voice_id

    def synthesize(self, text: str, path: Path) -> None:
        try:
            chunks = self._client.text_to_speech.convert(
                voice_id=self._voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            with path.open("wb") as f:
                for chunk in chunks:
                    f.write(chunk)
        except Exception as exc:  # noqa: BLE001 — surface any API/network error cleanly
            raise TTSError(f"Couldn't synthesize speech (ElevenLabs): {exc}") from exc


def _build_backend():
    """Pick ElevenLabs if configured, otherwise edge-tts.

    Also falls back to edge-tts if ElevenLabs synthesis ever fails at
    runtime (e.g. the free quota runs out mid-month) — see Speaker.speak().
    """
    if config.elevenlabs_api_key and config.elevenlabs_voice_id:
        return _ElevenLabsBackend(config.elevenlabs_api_key, config.elevenlabs_voice_id)
    return _EdgeTTSBackend()


class Speaker:
    """Synthesizes text to speech and plays it back, one utterance at a time."""

    def __init__(self) -> None:
        # Two replies arriving close together (e.g. quick follow-up voice
        # questions) would otherwise start overlapping afplay processes.
        self._lock = threading.Lock()
        self._backend = _build_backend()
        self._fallback = _EdgeTTSBackend()

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
            try:
                self._backend.synthesize(text, path)
            except TTSError:
                if isinstance(self._backend, _EdgeTTSBackend):
                    raise
                # ElevenLabs failed (quota exhausted, network, bad key) —
                # don't let that silence Jarvis entirely, drop back to the
                # free tier.
                self._fallback.synthesize(text, path)
        except TTSError:
            # mkstemp already created this file on disk; if synthesis never
            # succeeds (both backends failed), nothing downstream ever gets
            # a chance to unlink it — clean up here instead of leaking it.
            path.unlink(missing_ok=True)
            raise
        return path
