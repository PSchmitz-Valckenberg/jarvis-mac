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
    """Higher-quality voices; free tier is ~10k characters/month.

    eleven_multilingual_v2 (not eleven_monolingual_v1 — that model is
    English-only and can't speak the German replies/greeting this app uses).

    Only "premade" voices work on the free tier — the Voice Library's
    shared/community voices return 402 payment_required via the API even
    though they preview fine on the website. PRESET_VOICES below are all
    premade and confirmed to work.
    """

    def __init__(self, api_key: str, voice_id: str) -> None:
        from elevenlabs.client import ElevenLabs
        from elevenlabs.types.voice_settings import VoiceSettings

        self._client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self._voice_settings = VoiceSettings(
            stability=config.elevenlabs_stability,
            similarity_boost=config.elevenlabs_similarity_boost,
        )

    def synthesize(self, text: str, path: Path) -> None:
        try:
            chunks = self._client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                voice_settings=self._voice_settings,
            )
            with path.open("wb") as f:
                for chunk in chunks:
                    f.write(chunk)
        except Exception as exc:  # noqa: BLE001 — surface any API/network error cleanly
            raise TTSError(f"Couldn't synthesize speech (ElevenLabs): {exc}") from exc


# Premade voices confirmed to work on the free API tier — surfaced in the
# dashboard's voice switcher. (Library/community voices like "Roderich"
# look identical in the UI but 402 on synthesis without a paid plan.)
PRESET_VOICES = [
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "label": "Dominant, Firm"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel", "label": "Steady Broadcaster"},
    {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian", "label": "Deep, Resonant, Comforting"},
    {"id": "IKne3meq5aSn9XLyUdCD", "name": "Charlie", "label": "Deep, Confident, Energetic"},
    {"id": "pqHfZKP75CvOlQylNhV4", "name": "Bill", "label": "Wise, Mature, Balanced"},
    {"id": "cjVigY5qzO86Huf0OWal", "name": "Eric", "label": "Smooth, Trustworthy"},
]


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
        self._proc: subprocess.Popen | None = None
        self._proc_lock = threading.Lock()

    def speak(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        with self._lock:
            audio_path = self._synthesize(text)
            try:
                proc = subprocess.Popen(["afplay", str(audio_path)])
                with self._proc_lock:
                    self._proc = proc
                proc.wait()
                # A non-zero return code here just means interrupt() killed
                # it on purpose (barge-in) — that's not a playback failure.
            except Exception as exc:  # noqa: BLE001 — surface any playback error cleanly
                raise TTSError(f"Couldn't play audio: {exc}") from exc
            finally:
                with self._proc_lock:
                    self._proc = None
                audio_path.unlink(missing_ok=True)

    def interrupt(self) -> None:
        """Stop whatever is currently playing — used for barge-in: holding
        the hotkey while Jarvis is talking should cut it off immediately."""
        with self._proc_lock:
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()

    def is_elevenlabs_active(self) -> bool:
        return isinstance(self._backend, _ElevenLabsBackend)

    def current_voice_id(self) -> str | None:
        if isinstance(self._backend, _ElevenLabsBackend):
            return self._backend.voice_id
        return None

    def set_voice(self, voice_id: str) -> bool:
        """Switch the active ElevenLabs voice for this session.

        Returns False if ElevenLabs isn't the active backend (nothing to
        switch — edge-tts voices are chosen via TTS_VOICE in .env instead).
        """
        if not isinstance(self._backend, _ElevenLabsBackend):
            return False
        with self._lock:
            self._backend.voice_id = voice_id
        return True

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
