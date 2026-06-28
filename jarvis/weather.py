"""Open-Meteo current-weather lookup — no API key needed."""

from __future__ import annotations

from typing import Any

import requests

WEATHER_TIMEOUT_SECONDS = 10


def fetch_current_weather(latitude: float, longitude: float) -> dict[str, Any] | None:
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": latitude, "longitude": longitude, "current_weather": "true"},
            timeout=WEATHER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["current_weather"]
    except Exception:  # noqa: BLE001 — weather is a nice-to-have, never raise on it
        return None
