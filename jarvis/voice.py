"""Local speech-to-text: microphone capture + Whisper transcription.

Recording and transcription are deliberately separate steps (`Recorder` vs.
`Transcriber`) so the hold-to-talk UX can stop the mic the instant the hotkey
is released, while the (slower) transcription runs after, off the GUI thread.

NOTE: macOS requires Microphone permission for the first recording attempt.
Grant it under System Settings -> Privacy & Security -> Microphone for your
terminal / Python launcher, then try again.
"""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from .config import config

SAMPLE_RATE = 16_000  # Whisper expects 16kHz mono


class VoiceError(Exception):
    """Raised when recording or transcription fails."""


class Recorder:
    """Captures mono 16kHz audio for the duration of a hold.

    Opens the microphone stream once and keeps it open for the app's whole
    lifetime instead of reopening it per hold. CoreAudio can silently hand
    back a beat of zeros right after (re)opening an input device — closing
    and reopening per hold made that happen on nearly every hold. Staying
    open and just toggling capture on/off avoids that entirely.
    """

    def __init__(self) -> None:
        self._armed = False
        self._chunks: list[np.ndarray] = []
        # _chunks is written from PortAudio's callback thread and read/swapped
        # from the GUI thread in start()/stop() — guard it against a chunk
        # landing mid-swap at a press/release boundary.
        self._lock = threading.Lock()
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                latency="low",
                callback=self._on_audio,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001 — surface any audio/device error cleanly
            raise VoiceError(f"Couldn't open microphone: {exc}") from exc

    def _on_audio(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if self._armed:
            with self._lock:
                self._chunks.append(indata.copy())

    def start(self) -> None:
        with self._lock:
            self._chunks = []
        self._armed = True

    def stop(self) -> np.ndarray:
        """Stop capture and return the recorded audio as a flat float32 array."""
        self._armed = False
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.empty(0, dtype="float32")
        return np.concatenate(chunks, axis=0).reshape(-1)

    def close(self) -> None:
        """Release the microphone — call once, on app shutdown."""
        self._stream.stop()
        self._stream.close()

    @property
    def is_recording(self) -> bool:
        return self._armed


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
            # No VAD filter: these clips are already bounded by the hold
            # duration, and VAD's silence heuristics can strip short or
            # quiet speech entirely on clips this brief.
            segments, _info = self._model.transcribe(
                audio,
                language=config.whisper_language,
                vad_filter=False,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:  # noqa: BLE001 — surface any transcription error cleanly
            raise VoiceError(f"Transcription failed: {exc}") from exc
