"""Collects tools and dispatches LLM-issued calls to them."""

from __future__ import annotations

from typing import Any

from .base import Tool, ToolError


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def run(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'."
        try:
            return tool.run(**arguments)
        except ToolError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # noqa: BLE001 — a buggy tool shouldn't crash the chat turn
            return f"Error running tool '{name}': {exc}"
