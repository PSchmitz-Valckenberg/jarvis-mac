"""Read/write the macOS clipboard via pbcopy/pbpaste."""

from __future__ import annotations

import subprocess

from .base import Tool, ToolError


class ReadClipboardTool(Tool):
    name = "read_clipboard"
    description = "Read the current contents of the macOS clipboard."

    def run(self) -> str:
        try:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Couldn't read clipboard: {exc}") from exc
        return result.stdout or "(clipboard is empty)"


class WriteClipboardTool(Tool):
    name = "write_clipboard"
    description = "Write text to the macOS clipboard, replacing whatever's there."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to copy to the clipboard"},
        },
        "required": ["text"],
    }

    def run(self, text: str) -> str:
        try:
            subprocess.run(["pbcopy"], input=text, text=True, timeout=5, check=True)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Couldn't write clipboard: {exc}") from exc
        return "Copied to clipboard"
