"""Web search via the Tavily API — only registered when TAVILY_API_KEY is set."""

from __future__ import annotations

from .base import Tool, ToolError

MAX_RESULTS = 4
MAX_CONTENT_CHARS = 500


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web and get back a few relevant results with short "
        "summaries — use this for current events, facts you're unsure "
        "about, or anything that needs up-to-date information."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        from ..config import config

        from tavily import TavilyClient

        self._client = TavilyClient(api_key=config.tavily_api_key)

    def run(self, query: str) -> str:
        try:
            response = self._client.search(query=query, max_results=MAX_RESULTS)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Web search failed: {exc}") from exc

        results = response.get("results", [])
        if not results:
            return "No results found."

        lines = []
        for item in results:
            title = item.get("title", "")
            url = item.get("url", "")
            content = (item.get("content", "") or "").strip()[:MAX_CONTENT_CHARS]
            lines.append(f"{title}\n{url}\n{content}")
        return "\n\n".join(lines)
