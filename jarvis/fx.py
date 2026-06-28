"""Free, no-key FX rate lookup (Frankfurter, ECB-sourced) — used to convert
multi-currency IBKR positions into one base currency for display."""

from __future__ import annotations

import requests

FX_TIMEOUT_SECONDS = 10


def fetch_rate(from_currency: str, to_currency: str) -> float | None:
    """Returns how many units of to_currency one unit of from_currency buys."""
    if from_currency == to_currency:
        return 1.0
    try:
        response = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": from_currency, "to": to_currency},
            timeout=FX_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return float(response.json()["rates"][to_currency])
    except Exception:  # noqa: BLE001 — caller falls back to no conversion
        return None
