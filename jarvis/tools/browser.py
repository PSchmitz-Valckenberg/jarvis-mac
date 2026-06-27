"""Browser control — open URLs/searches in the user's default browser.

Uses macOS's `open` command rather than driving the browser via Playwright:
no extra download, and "open this site" / "search for X" cover the vast
majority of what gets asked for. Deeper automation (clicking, scraping)
isn't supported here.
"""

from __future__ import annotations

import subprocess
from urllib.parse import quote

from .base import Tool, ToolError


def _open(url: str) -> None:
    try:
        result = subprocess.run(["open", url], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        raise ToolError("Timed out opening the browser") from None
    if result.returncode != 0:
        raise ToolError((result.stderr or f"Couldn't open {url}").strip())


class OpenUrlTool(Tool):
    name = "open_url"
    description = "Open a URL in the user's default web browser."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to open, e.g. https://github.com"},
        },
        "required": ["url"],
    }

    def run(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        _open(url)
        return f"Opened {url}"


class SearchWebBrowserTool(Tool):
    name = "search_web_browser"
    description = (
        "Open a search for a query in the user's default web browser (Google). "
        "Use this when the user wants to *see* search results themselves, as "
        "opposed to web_search which reads results back to you directly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for"},
        },
        "required": ["query"],
    }

    def run(self, query: str) -> str:
        url = f"https://www.google.com/search?q={quote(query)}"
        _open(url)
        return f"Opened a browser search for: {query}"
