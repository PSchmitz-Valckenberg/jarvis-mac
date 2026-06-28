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


def fetch_weather_with_forecast(latitude: float, longitude: float) -> dict[str, Any] | None:
    """Current weather plus an hourly (next 24h) and daily (7-day) outlook,
    for the weather widget's click-to-expand view."""
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": "true",
                "hourly": "temperature_2m,weathercode",
                "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                "timezone": "auto",
                "forecast_days": 7,
            },
            timeout=WEATHER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:  # noqa: BLE001 — weather is a nice-to-have, never raise on it
        return None

    hourly = data.get("hourly", {})
    daily = data.get("daily", {})
    current_time = (data.get("current_weather") or {}).get("time", "")
    hourly_times = hourly.get("time", [])
    # Start the hourly outlook from "now" rather than midnight — current_time
    # is truncated to the hour by Open-Meteo, so an exact match is reliable.
    start = next((i for i, t in enumerate(hourly_times) if t >= current_time), 0)
    end = start + 24

    return {
        "current": data.get("current_weather"),
        "hourly": [
            {"time": t, "temperature": temp, "weathercode": code}
            for t, temp, code in zip(
                hourly_times[start:end],
                hourly.get("temperature_2m", [])[start:end],
                hourly.get("weathercode", [])[start:end],
            )
        ],
        "daily": [
            {"date": d, "temp_max": tmax, "temp_min": tmin, "weathercode": code}
            for d, tmax, tmin, code in zip(
                daily.get("time", []),
                daily.get("temperature_2m_max", []),
                daily.get("temperature_2m_min", []),
                daily.get("weathercode", []),
            )
        ],
    }
