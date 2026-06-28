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


def _optional_float(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def _csv_list(value: str | None) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_db_path(value: str | None, default_name: str) -> str:
    path = Path((value or "").strip() or default_name).expanduser()
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return str(path)


@dataclass(frozen=True)
class Config:
    groq_api_key: str
    groq_model: str
    temperature: float
    max_tokens: int
    hotkey: str
    tts_enabled: bool
    tts_voice: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_stability: float
    elevenlabs_similarity_boost: float
    whisper_model: str
    whisper_language: str | None
    min_record_seconds: float
    memory_enabled: bool
    memory_db_path: str
    tools_enabled: bool
    tavily_api_key: str
    vision_model: str
    proactivity_enabled: bool
    morning_brief_enabled: bool
    morning_brief_time: str
    github_watch_enabled: bool
    github_repos: list[str]
    github_watch_interval_minutes: int
    idle_nudge_enabled: bool
    idle_nudge_minutes: int
    weather_latitude: float | None
    weather_longitude: float | None
    tasks_file: str | None
    profile_enabled: bool
    profile_extraction_model: str
    camera_index: int
    dashboard_db_path: str
    ibkr_flex_token: str
    ibkr_flex_query_id: str
    ibkr_flex_poll_minutes: int

    @classmethod
    def load(cls) -> "Config":
        db_path = _resolve_db_path(os.getenv("MEMORY_DB_PATH", ""), "jarvis_memory.db")
        dashboard_db_path = _resolve_db_path(os.getenv("DASHBOARD_DB_PATH", ""), "jarvis_dashboard.db")

        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
            temperature=float(os.getenv("TEMPERATURE", "0.6")),
            max_tokens=int(os.getenv("MAX_TOKENS", "1024")),
            hotkey=os.getenv("HOTKEY", "alt").strip().lower(),
            tts_enabled=_bool(os.getenv("TTS_ENABLED"), default=False),
            # Deep, male, German edge-tts voice — used whenever ElevenLabs
            # isn't configured, and as its runtime fallback.
            tts_voice=os.getenv("TTS_VOICE", "de-DE-KillianNeural").strip(),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", "").strip(),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "").strip(),
            # Higher stability = more monotone/consistent; higher similarity
            # = closer to the original voice sample. 0.75/0.85 leans toward
            # a steady, deep delivery rather than an expressive one.
            elevenlabs_stability=float(os.getenv("ELEVENLABS_STABILITY", "0.75")),
            elevenlabs_similarity_boost=float(
                os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.85")
            ),
            whisper_model=os.getenv("WHISPER_MODEL", "base").strip(),
            whisper_language=os.getenv("WHISPER_LANGUAGE", "").strip() or None,
            min_record_seconds=float(os.getenv("MIN_RECORD_SECONDS", "0.35")),
            memory_enabled=_bool(os.getenv("MEMORY_ENABLED"), default=True),
            memory_db_path=db_path,
            tools_enabled=_bool(os.getenv("TOOLS_ENABLED"), default=True),
            tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
            vision_model=os.getenv(
                "VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
            ).strip(),
            proactivity_enabled=_bool(os.getenv("PROACTIVITY_ENABLED"), default=True),
            morning_brief_enabled=_bool(os.getenv("MORNING_BRIEF_ENABLED"), default=True),
            morning_brief_time=os.getenv("MORNING_BRIEF_TIME", "07:30").strip(),
            github_watch_enabled=_bool(os.getenv("GITHUB_WATCH_ENABLED"), default=True),
            github_repos=_csv_list(os.getenv("GITHUB_REPOS")),
            github_watch_interval_minutes=int(os.getenv("GITHUB_WATCH_INTERVAL_MINUTES", "30")),
            idle_nudge_enabled=_bool(os.getenv("IDLE_NUDGE_ENABLED"), default=True),
            idle_nudge_minutes=int(os.getenv("IDLE_NUDGE_MINUTES", "120")),
            weather_latitude=_optional_float(os.getenv("WEATHER_LATITUDE")),
            weather_longitude=_optional_float(os.getenv("WEATHER_LONGITUDE")),
            tasks_file=os.getenv("TASKS_FILE", "").strip() or None,
            profile_enabled=_bool(os.getenv("PROFILE_ENABLED"), default=True),
            profile_extraction_model=os.getenv(
                "PROFILE_EXTRACTION_MODEL", "llama-3.1-8b-instant"
            ).strip(),
            camera_index=int(os.getenv("CAMERA_INDEX", "0")),
            dashboard_db_path=dashboard_db_path,
            ibkr_flex_token=os.getenv("IBKR_FLEX_TOKEN", "").strip(),
            ibkr_flex_query_id=os.getenv("IBKR_FLEX_QUERY_ID", "").strip(),
            ibkr_flex_poll_minutes=int(os.getenv("IBKR_FLEX_POLL_MINUTES", "120")),
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.groq_api_key)


config = Config.load()
