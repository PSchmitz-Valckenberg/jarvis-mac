"""Central config — everything tunable lives in .env, loaded once here."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (parent of this package), if present.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


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

    @classmethod
    def load(cls) -> "Config":
        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
            temperature=float(os.getenv("TEMPERATURE", "0.6")),
            max_tokens=int(os.getenv("MAX_TOKENS", "1024")),
            hotkey=os.getenv("HOTKEY", "alt").strip().lower(),
            tts_enabled=_bool(os.getenv("TTS_ENABLED"), default=False),
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.groq_api_key)


config = Config.load()
