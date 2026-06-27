"""Central config — everything tunable lives in .env, loaded once here."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the project root, if present.
load_dotenv(_PROJECT_ROOT / ".env")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    groq_api_key: str
    groq_model: str
    temperature: float
    max_tokens: int
    hotkey: str
    tts_enabled: bool
    tts_voice: str
    whisper_model: str
    whisper_language: str | None
    min_record_seconds: float
    memory_enabled: bool
    memory_db_path: str

    @classmethod
    def load(cls) -> "Config":
        db_path = os.getenv("MEMORY_DB_PATH", "").strip() or "jarvis_memory.db"
        db_path = Path(db_path).expanduser()
        if not db_path.is_absolute():
            db_path = _PROJECT_ROOT / db_path
        db_path = str(db_path)

        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
            temperature=float(os.getenv("TEMPERATURE", "0.6")),
            max_tokens=int(os.getenv("MAX_TOKENS", "1024")),
            hotkey=os.getenv("HOTKEY", "alt").strip().lower(),
            tts_enabled=_bool(os.getenv("TTS_ENABLED"), default=False),
            tts_voice=os.getenv("TTS_VOICE", "en-US-AriaNeural").strip(),
            whisper_model=os.getenv("WHISPER_MODEL", "base").strip(),
            whisper_language=os.getenv("WHISPER_LANGUAGE", "").strip() or None,
            min_record_seconds=float(os.getenv("MIN_RECORD_SECONDS", "0.35")),
            memory_enabled=_bool(os.getenv("MEMORY_ENABLED"), default=True),
            memory_db_path=db_path,
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.groq_api_key)


config = Config.load()
