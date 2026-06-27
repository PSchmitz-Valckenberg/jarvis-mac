"""Launch macOS applications by name.

`open -a` needs the app's actual (usually English) bundle name — but the
model often hears/says the German name instead (e.g. "Taschenrechner").
A small translation table covers the common built-in apps; for anything
else, `mdfind` searches Spotlight's metadata for a display-name match
regardless of language, which catches localized third-party apps too.
"""

from __future__ import annotations

import subprocess

from .base import Tool, ToolError

# Common macOS built-in apps the model is likely to hear/say in German.
_TRANSLATIONS = {
    "taschenrechner": "Calculator",
    "notizen": "Notes",
    "notizblock": "Notes",
    "kalender": "Calendar",
    "nachrichten": "Messages",
    "einstellungen": "System Settings",
    "systemeinstellungen": "System Settings",
    "fotos": "Photos",
    "erinnerungen": "Reminders",
    "vorschau": "Preview",
    "musik": "Music",
    "karten": "Maps",
    "kontakte": "Contacts",
    "mail": "Mail",
    "nachrichtenzentrale": "Notification Center",
    "systemmonitor": "Activity Monitor",
    "aktivitätsanzeige": "Activity Monitor",
    "terminkalender": "Calendar",
    "taschenlampe": "Flashlight",
}


def _try_open(target: str) -> bool:
    try:
        result = subprocess.run(["open", "-a", target], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _find_via_spotlight(name: str) -> str | None:
    escaped = name.replace("'", "")
    query = f"kMDItemContentType == 'com.apple.application-bundle' && kMDItemDisplayName == '*{escaped}*'cd"
    try:
        result = subprocess.run(["mdfind", query], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return None
    paths = [line for line in result.stdout.splitlines() if line.strip()]
    return paths[0] if paths else None


class AppLauncherTool(Tool):
    name = "open_app"
    description = (
        "Open/launch a macOS application by name, e.g. 'Safari', 'Calendar', 'Mail'. "
        "Works with German names too (e.g. 'Taschenrechner')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "The application's name, e.g. 'Spotify'"},
        },
        "required": ["app_name"],
    }

    def run(self, app_name: str) -> str:
        candidates = [app_name]
        translated = _TRANSLATIONS.get(app_name.strip().lower())
        if translated:
            candidates.append(translated)

        for candidate in candidates:
            if _try_open(candidate):
                return f"Opened {candidate}"

        found_path = _find_via_spotlight(app_name)
        if found_path and _try_open(found_path):
            return f"Opened {found_path}"

        raise ToolError(f"Couldn't find or open an app matching '{app_name}'")
