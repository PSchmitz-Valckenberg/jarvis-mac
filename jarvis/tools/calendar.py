"""macOS Calendar integration via AppleScript (osascript).

Dates are passed in as ISO strings and converted into AppleScript date
literals by setting numeric components one at a time — parsing a string
date directly in AppleScript is locale-dependent and fragile.
"""

from __future__ import annotations

import subprocess
from datetime import datetime

from .base import Tool, ToolError


# Calendar.app can take a surprisingly long time to enumerate events
# (tens of seconds) when it hasn't been queried recently — not a bug, just
# how AppleEvents to it behaves, so this timeout is generous on purpose.
CALENDAR_TIMEOUT_SECONDS = 45


def _run_applescript(script: str) -> str:
    try:
        result = subprocess.run(
            ["osascript"], input=script, capture_output=True, text=True, timeout=CALENDAR_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        raise ToolError("Calendar request timed out") from None
    if result.returncode != 0:
        raise ToolError((result.stderr or "AppleScript failed").strip())
    return result.stdout.strip()


def _applescript_date_var(var: str, dt: datetime) -> str:
    return (
        f"set {var} to current date\n"
        f"set year of {var} to {dt.year}\n"
        f"set month of {var} to {dt.month}\n"
        f"set day of {var} to {dt.day}\n"
        f"set hours of {var} to {dt.hour}\n"
        f"set minutes of {var} to {dt.minute}\n"
        f"set seconds of {var} to 0\n"
    )


def _parse_iso(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ToolError(f"Couldn't parse {field} '{value}' — use ISO format, e.g. 2026-06-27T14:00") from None


def list_calendar_events_structured(days_ahead: int = 1) -> list[dict[str, str]]:
    """Same lookup as ListCalendarEventsTool, but as structured rows for the
    dashboard instead of a single text blob — uses a control character as
    the field separator since titles can contain "—" or commas."""
    days_ahead = max(1, min(int(days_ahead), 30))
    sep = "␟"
    script = (
        "set rangeStart to current date\n"
        "set hours of rangeStart to 0\n"
        "set minutes of rangeStart to 0\n"
        "set seconds of rangeStart to 0\n"
        f"set rangeEnd to rangeStart + ({days_ahead} * days)\n"
        "set output to \"\"\n"
        "tell application \"Calendar\"\n"
        "  repeat with cal in calendars\n"
        "    set theseEvents to (events of cal whose start date ≥ rangeStart and start date < rangeEnd)\n"
        "    repeat with evt in theseEvents\n"
        f"      set output to output & (summary of evt) & \"{sep}\" & ((start date of evt) as string) & \"{sep}\" & (name of cal) & linefeed\n"
        "    end repeat\n"
        "  end repeat\n"
        "end tell\n"
        "return output\n"
    )
    output = _run_applescript(script)
    events = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split(sep)
        if len(parts) != 3:
            continue
        title, start, calendar = parts
        events.append({"title": title, "start": start, "calendar": calendar})
    return events


class ListCalendarEventsTool(Tool):
    name = "list_calendar_events"
    description = "List calendar events starting from today, across all calendars."
    parameters = {
        "type": "object",
        "properties": {
            "days_ahead": {
                "type": "integer",
                "description": "How many days ahead to include, starting from today. Default 1 (today only).",
            },
        },
        "required": [],
    }

    def run(self, days_ahead: int = 1) -> str:
        days_ahead = max(1, min(int(days_ahead), 30))
        script = (
            "set rangeStart to current date\n"
            "set hours of rangeStart to 0\n"
            "set minutes of rangeStart to 0\n"
            "set seconds of rangeStart to 0\n"
            f"set rangeEnd to rangeStart + ({days_ahead} * days)\n"
            "set output to \"\"\n"
            "tell application \"Calendar\"\n"
            "  repeat with cal in calendars\n"
            "    set theseEvents to (events of cal whose start date ≥ rangeStart and start date < rangeEnd)\n"
            "    repeat with evt in theseEvents\n"
            "      set output to output & (summary of evt) & \" — \" & ((start date of evt) as string) & \" (\" & (name of cal) & \")\" & linefeed\n"
            "    end repeat\n"
            "  end repeat\n"
            "end tell\n"
            "return output\n"
        )
        output = _run_applescript(script)
        return output or "No events found in that range."


class AddCalendarEventTool(Tool):
    name = "add_calendar_event"
    description = "Add a new event to the default macOS calendar."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title"},
            "start": {"type": "string", "description": "Start, ISO format, e.g. 2026-06-27T14:00"},
            "end": {
                "type": "string",
                "description": "End, ISO format. Defaults to start + 1 hour if omitted.",
            },
            "calendar": {
                "type": "string",
                "description": "Calendar name to add to. Defaults to the first calendar.",
            },
        },
        "required": ["title", "start"],
    }

    def run(self, title: str, start: str, end: str | None = None, calendar: str | None = None) -> str:
        start_dt = _parse_iso(start, "start")
        end_dt = _parse_iso(end, "end") if end else start_dt.replace(hour=(start_dt.hour + 1) % 24)

        safe_title = title.replace('"', '\\"')
        target_calendar = (
            f'calendar "{calendar.replace(chr(34), chr(92) + chr(34))}"' if calendar else "first calendar"
        )

        script = (
            _applescript_date_var("theStart", start_dt)
            + _applescript_date_var("theEnd", end_dt)
            + "tell application \"Calendar\"\n"
            f"  tell {target_calendar}\n"
            f'    make new event with properties {{summary:"{safe_title}", start date:theStart, end date:theEnd}}\n'
            "  end tell\n"
            "end tell\n"
            f'return "ok"\n'
        )
        _run_applescript(script)
        return f"Added '{title}' to the calendar at {start_dt.isoformat()}"
