"""Non-portfolio dashboard data: calendar, GitHub PRs, weather, news,
and the manual morning-energy score. Polls on its own APScheduler
scheduler and pushes updates over the WebSocket hub; the matching
GET endpoints in server.py are just synchronous reads of the same calls,
used for the dashboard's first load before any push has arrived.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date
from pathlib import Path
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler

from .config import config
from .github_status import fetch_open_prs
from .news import fetch_headlines
from .news_geo import geotag_headlines
from .news_summary import summarize_headline
from .tools.calendar import list_calendar_events_structured
from .weather import fetch_current_weather, fetch_weather_with_forecast

NEWS_RSS_URL = "https://www.tagesschau.de/xml/rss2/"
CALENDAR_INTERVAL_MINUTES = 5
WEATHER_INTERVAL_MINUTES = 15
NEWS_INTERVAL_MINUTES = 10


class DashboardService:
    def __init__(self, db_path: str, broadcast: Callable[[dict[str, Any]], None]) -> None:
        self.db_path = db_path
        self._broadcast = broadcast
        self._scheduler = BackgroundScheduler(daemon=True)
        self._init_db()

        # AppleScript calendar queries reliably take 25-30s+ (Calendar.app's
        # own scripting bridge is just slow, not something we control) — far
        # too slow to do on every dashboard load or every chat turn that
        # asks about today. Cached here, refreshed only by the periodic job.
        self._calendar_lock = threading.Lock()
        self._calendar_cache: list[dict[str, Any]] = []

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS morning_score (day TEXT PRIMARY KEY, score INTEGER NOT NULL)")
        conn.commit()
        conn.close()

    def start(self) -> None:
        self._scheduler.add_job(self._push_calendar, "interval", minutes=CALENDAR_INTERVAL_MINUTES, id="dash_calendar")
        if config.github_repos:
            self._scheduler.add_job(
                self._push_github,
                "interval",
                minutes=config.github_watch_interval_minutes,
                id="dash_github",
            )
        if config.weather_latitude is not None and config.weather_longitude is not None:
            self._scheduler.add_job(self._push_weather, "interval", minutes=WEATHER_INTERVAL_MINUTES, id="dash_weather")
        self._scheduler.add_job(self._push_news, "interval", minutes=NEWS_INTERVAL_MINUTES, id="dash_news")
        self._scheduler.start()

        # Fire each once immediately, off the request thread, so the
        # dashboard isn't empty until the first scheduled interval fires.
        for job in (self._push_calendar, self._push_github, self._push_weather, self._push_news):
            threading.Thread(target=job, daemon=True).start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    # ── reads (used by both the GET endpoints and the push jobs) ───────
    def get_calendar(self) -> list[dict[str, Any]]:
        with self._calendar_lock:
            return list(self._calendar_cache)

    def _fetch_calendar_fresh(self) -> list[dict[str, Any]]:
        try:
            return list_calendar_events_structured(days_ahead=1)
        except Exception:  # noqa: BLE001 — Calendar.app hiccups shouldn't break the refresh job
            return []

    def get_github(self) -> dict[str, list[dict[str, Any]]]:
        return {repo: (fetch_open_prs(repo) or []) for repo in config.github_repos}

    def get_weather(self) -> dict[str, Any] | None:
        if config.weather_latitude is None or config.weather_longitude is None:
            return None
        return fetch_current_weather(config.weather_latitude, config.weather_longitude)

    def get_weather_forecast(self) -> dict[str, Any] | None:
        if config.weather_latitude is None or config.weather_longitude is None:
            return None
        return fetch_weather_with_forecast(config.weather_latitude, config.weather_longitude)

    def get_headline_summary(self, headline: str) -> dict[str, Any]:
        return summarize_headline(headline)

    def get_news(self) -> list[str]:
        return fetch_headlines(NEWS_RSS_URL)

    def get_news_with_points(self) -> dict[str, Any]:
        headlines = self.get_news()
        return {"headlines": headlines, "points": geotag_headlines(headlines)}

    def get_morning_score(self) -> int | None:
        today = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT score FROM morning_score WHERE day = ?", (today,)).fetchone()
        conn.close()
        return row[0] if row else None

    def set_morning_score(self, score: int) -> None:
        today = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO morning_score (day, score) VALUES (?, ?) "
            "ON CONFLICT(day) DO UPDATE SET score = excluded.score",
            (today, score),
        )
        conn.commit()
        conn.close()

    # ── push jobs ────────────────────────────────────────────────────
    def _push_calendar(self) -> None:
        events = self._fetch_calendar_fresh()
        with self._calendar_lock:
            self._calendar_cache = events
        self._broadcast({"type": "calendar_update", "events": events})

    def _push_github(self) -> None:
        self._broadcast({"type": "github_prs_update", "repos": self.get_github()})

    def _push_weather(self) -> None:
        weather = self.get_weather()
        if weather is not None:
            self._broadcast({"type": "weather_update", "weather": weather})

    def _push_news(self) -> None:
        self._broadcast({"type": "news_update", **self.get_news_with_points()})
