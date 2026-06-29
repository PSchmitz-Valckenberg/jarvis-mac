"""Direct, reliable access to the dashboard's own live data — portfolio,
news, weather — so the assistant can answer questions about what's on
screen without resorting to see_screen (slow, imprecise for exact numbers,
and prone to looping when the model isn't satisfied with what it "saw").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Tool

if TYPE_CHECKING:
    from ..dashboard import DashboardService
    from ..portfolio import PortfolioService


class ReadPortfolioTool(Tool):
    name = "read_portfolio"
    description = (
        "Get the current IBKR portfolio: total value, today's change, and "
        "every position's value and change. Use this whenever asked about "
        "the portfolio, depot, or specific positions — never guess the "
        "numbers from memory."
    )

    def __init__(self, portfolio: "PortfolioService") -> None:
        self._portfolio = portfolio

    def run(self) -> str:
        data = self._portfolio.latest()
        positions = data.get("positions") or []
        if not positions:
            return "Keine Portfolio-Daten verfügbar."

        currency = data.get("currency", "EUR")
        status = "live" if data.get("connected") else "zwischengespeichert, nicht live"
        total_value = data.get("total_value")
        day_pnl_pct = data.get("day_pnl_pct")

        lines = [f"Status: {status}"]
        if total_value is not None:
            total_line = f"Gesamtwert: {total_value:.2f} {currency}"
            if day_pnl_pct is not None:
                total_line += f" ({day_pnl_pct:+.2f}% heute)"
            lines.append(total_line)

        for position in positions:
            value = position.get("market_value")
            change = position.get("day_change_pct")
            piece = f"{position['symbol']}: {value:.2f} {currency}" if value is not None else f"{position['symbol']}: —"
            if change is not None:
                piece += f" ({change:+.2f}%)"
            lines.append(piece)

        return "\n".join(lines)


class ReadCalendarTool(Tool):
    name = "read_calendar"
    description = (
        "Get today's calendar events from the dashboard's cache — instant, "
        "unlike list_calendar_events which queries Calendar.app directly "
        "and can take 30+ seconds. Use this for 'what's on today' "
        "questions; fall back to list_calendar_events only for other days "
        "or to add an event."
    )

    def __init__(self, dashboard: "DashboardService") -> None:
        self._dashboard = dashboard

    def run(self) -> str:
        events = self._dashboard.get_calendar()
        if not events:
            return "Keine Termine heute."
        return "\n".join(f"{e['title']} — {e['start']} ({e['calendar']})" for e in events)


class ReadNewsTool(Tool):
    name = "read_news"
    description = "Get the current news headlines shown on the dashboard."

    def __init__(self, dashboard: "DashboardService") -> None:
        self._dashboard = dashboard

    def run(self) -> str:
        headlines = self._dashboard.get_news()
        if not headlines:
            return "Keine aktuellen Nachrichten verfügbar."
        return "\n".join(f"- {headline}" for headline in headlines)


class ReadWeatherTool(Tool):
    name = "read_weather"
    description = "Get the current weather shown on the dashboard."

    def __init__(self, dashboard: "DashboardService") -> None:
        self._dashboard = dashboard

    def run(self) -> str:
        weather = self._dashboard.get_weather()
        if not weather:
            return "Keine Wetterdaten verfügbar."
        return f"{weather['temperature']}°C, Wind {weather['windspeed']} km/h"
