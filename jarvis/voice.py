"""Local speech-to-text: microphone capture + Whisper transcription.

Recording and transcription are deliberately separate steps (`Recorder` vs.
`Transcriber`) so the hold-to-talk UX can stop the mic the instant the hotkey
is released, while the (slower) transcription runs after, off the GUI thread.

NOTE: macOS requires Microphone permission for the first recording attempt.
Grant it under System Settings -> Privacy & Security -> Microphone for your
terminal / Python launcher, then try again.
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from .config import config

SAMPLE_RATE = 16_000  # Whisper expects 16kHz mono


class VoiceError(Exception):
    """Raised when recording or transcription fails."""


class Recorder:
    """Captures mono 16kHz audio for the duration of a hold."""

    def __init__(self) -> None:
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []

    def start(self) -> None:
        self._chunks = []
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._on_audio,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001 — surface any audio/device error cleanly
            self._stream = None
            raise VoiceError(f"Couldn't open microphone: {exc}") from exc

    def _on_audio(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        self._chunks.append(indata.copy())

    def stop(self) -> np.ndarray:
        """Stop capture and return the recorded audio as a flat float32 array."""
        if self._stream is None:
            return np.empty(0, dtype="float32")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._chunks:
            return np.empty(0, dtype="float32")
        return np.concatenate(self._chunks, axis=0).reshape(-1)

    @property
    def is_recording(self) -> bool:
        return self._stream is not None


class Transcriber:
    """Thin wrapper around faster-whisper, loaded once and reused."""

    def __init__(self) -> None:
        try:
            self._model = WhisperModel(
                config.whisper_model, device="cpu", compute_type="int8"
            )
        except Exception as exc:  # noqa: BLE001 — surface any model load error cleanly
            raise VoiceError(f"Couldn't load Whisper model: {exc}") from exc

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=config.whisper_language,
                vad_filter=True,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:  # noqa: BLE001 — surface any transcription error cleanly
            raise VoiceError(f"Transcription failed: {exc}") from exc
