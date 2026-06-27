"""Proactivity layer — Jarvis acts without being asked.

Three background jobs on an APScheduler BackgroundScheduler (its own
thread pool, so a slow job — e.g. a flaky GitHub call — never blocks the
hotkey/voice/HTTP path):

- morning_brief: once a day at a configured time, summarizes today's
  calendar, open GitHub PRs, and the weather, then speaks it.
- github_watch: polls configured repos every N minutes; only announces
  PRs that are new or changed since the last poll, not the same state
  twice.
- idle_nudge: after a configurable idle stretch with no user activity,
  suggests a break — re-arms the next time the user interacts.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from .config import config
from .tools.calendar import ListCalendarEventsTool

GITHUB_TIMEOUT_SECONDS = 15


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_str, _, minute_str = value.partition(":")
    try:
        return int(hour_str), int(minute_str or "0")
    except ValueError:
        return 7, 30  # fall back to a sane default rather than crash a background job


class ProactivityEngine:
    """Owns the scheduled jobs and the idle-activity clock."""

    def __init__(
        self,
        speak: Callable[[str], None],
        broadcast: Callable[[dict[str, Any]], None],
    ) -> None:
        self._speak = speak
        self._broadcast = broadcast
        self._scheduler = BackgroundScheduler(daemon=True)
        self._calendar = ListCalendarEventsTool()

        self._activity_lock = threading.Lock()
        self._last_activity = time.monotonic()
        self._idle_nudge_armed = True  # only fires once per idle stretch

        # repo -> {"number:updatedAt", ...} from the previous poll, so we
        # only announce what actually changed, not the same PRs every 30min.
        self._known_pr_state: dict[str, set[str]] = {}

    def note_activity(self) -> None:
        """Call this on every real user interaction — resets the idle clock."""
        with self._activity_lock:
            self._last_activity = time.monotonic()
            self._idle_nudge_armed = True

    def start(self) -> None:
        if config.morning_brief_enabled:
            hour, minute = _parse_hhmm(config.morning_brief_time)
            self._scheduler.add_job(
                self._run_morning_brief,
                "cron",
                hour=hour,
                minute=minute,
                id="morning_brief",
            )
        if config.github_watch_enabled and config.github_repos:
            self._scheduler.add_job(
                self._run_github_watch,
                "interval",
                minutes=config.github_watch_interval_minutes,
                id="github_watch",
            )
        if config.idle_nudge_enabled:
            self._scheduler.add_job(self._check_idle, "interval", minutes=5, id="idle_check")
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    # ── announcing ───────────────────────────────────────────────────
    def _announce(self, text: str, event_type: str) -> None:
        self._broadcast({"type": event_type, "text": text})
        self._speak(text)

    # ── morning brief ────────────────────────────────────────────────
    def _run_morning_brief(self) -> None:
        sections = [self._calendar_summary(), self._github_summary(), self._weather_summary(), self._tasks_summary()]
        body = "\n".join(s for s in sections if s)
        brief = f"Guten Morgen, Meister. {body}" if body else "Guten Morgen, Meister."
        self._announce(brief, event_type="morning_brief")

    def _calendar_summary(self) -> str | None:
        try:
            events = self._calendar.run(days_ahead=1)
        except Exception as exc:  # noqa: BLE001 — a broken job shouldn't kill the brief
            return f"Kalender konnte nicht geladen werden: {exc}"
        if events.startswith("No events"):
            return "Heute stehen keine Termine an."
        return f"Heutige Termine: {events}"

    def _github_summary(self) -> str | None:
        if not config.github_repos:
            return None
        lines = []
        for repo in config.github_repos:
            prs = self._fetch_open_prs(repo)
            if prs is None:
                continue
            if prs:
                titles = ", ".join(f"#{pr['number']} {pr['title']}" for pr in prs)
                lines.append(f"{repo}: {len(prs)} offene PR(s) — {titles}")
            else:
                lines.append(f"{repo}: keine offenen PRs")
        return "GitHub: " + " | ".join(lines) if lines else None

    def _weather_summary(self) -> str | None:
        if config.weather_latitude is None or config.weather_longitude is None:
            return None
        try:
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": config.weather_latitude,
                    "longitude": config.weather_longitude,
                    "current_weather": "true",
                },
                timeout=10,
            )
            response.raise_for_status()
            weather = response.json()["current_weather"]
        except Exception:  # noqa: BLE001 — weather is a nice-to-have, never block the brief on it
            return None
        return f"Wetter: {weather['temperature']}°C, Wind {weather['windspeed']} km/h."

    def _tasks_summary(self) -> str | None:
        if not config.tasks_file:
            return None
        path = Path(config.tasks_file).expanduser()
        if not path.is_file():
            return None
        open_items = [
            line.strip().removeprefix("- [ ]").strip()
            for line in path.read_text(errors="replace").splitlines()
            if line.strip().startswith("- [ ]")
        ]
        if not open_items:
            return "Keine offenen Aufgaben."
        preview = "; ".join(open_items[:3])
        suffix = f" und {len(open_items) - 3} weitere" if len(open_items) > 3 else ""
        return f"Offene Aufgaben: {preview}{suffix}."

    # ── GitHub watcher ───────────────────────────────────────────────
    def _fetch_open_prs(self, repo: str) -> list[dict[str, Any]] | None:
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--repo", repo, "--state", "open", "--json", "number,title,updatedAt"],
                capture_output=True,
                text=True,
                timeout=GITHUB_TIMEOUT_SECONDS,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return None

    def _run_github_watch(self) -> None:
        for repo in config.github_repos:
            prs = self._fetch_open_prs(repo)
            if prs is None:
                continue
            current_state = {f"{pr['number']}:{pr['updatedAt']}" for pr in prs}
            previous_state = self._known_pr_state.get(repo)
            self._known_pr_state[repo] = current_state

            if previous_state is None:
                continue  # first poll just establishes a baseline — nothing to announce yet

            changed = current_state - previous_state
            if not changed:
                continue
            changed_numbers = sorted({item.split(":")[0] for item in changed}, key=int)
            text = f"{repo}: Update an PR {', '.join('#' + n for n in changed_numbers)}."
            self._announce(text, event_type="github_update")

    # ── idle nudge ───────────────────────────────────────────────────
    def _check_idle(self) -> None:
        with self._activity_lock:
            idle_seconds = time.monotonic() - self._last_activity
            armed = self._idle_nudge_armed

        if not armed or idle_seconds < config.idle_nudge_minutes * 60:
            return

        with self._activity_lock:
            self._idle_nudge_armed = False  # don't repeat until the user interacts again

        hours = idle_seconds / 3600
        text = f"Sie sind seit {hours:.1f} Stunden inaktiv, Meister. Wollen Sie eine Pause einlegen?"
        self._announce(text, event_type="idle_nudge")
