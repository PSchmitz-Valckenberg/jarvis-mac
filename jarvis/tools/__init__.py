"""Tool system — gives the LLM real access to the machine it runs on.

Each tool is a small class with a name, a description (read by the LLM to
decide when to use it), a JSON-schema `parameters` dict, and a `run()`
method. `build_default_registry()` wires up every tool that's configured
(some need an API key) and is the only thing callers outside this package
need.
"""

from __future__ import annotations

from .app_launcher import AppLauncherTool
from .base import Tool
from .browser import OpenUrlTool, SearchWebBrowserTool
from .calendar import AddCalendarEventTool, ListCalendarEventsTool
from .camera import SeeCameraTool
from .clipboard import ReadClipboardTool, WriteClipboardTool
from .filesystem import ListFilesTool, ReadFileTool, WriteFileTool
from .registry import ToolRegistry
from .shell import RunShellTool
from .vision import SeeScreenTool
from .web_search import WebSearchTool


def build_default_registry() -> ToolRegistry:
    """Assemble every tool that's available given the current config."""
    from ..config import config

    tools: list[Tool] = [
        ReadFileTool(),
        WriteFileTool(),
        ListFilesTool(),
        RunShellTool(),
        AppLauncherTool(),
        ReadClipboardTool(),
        WriteClipboardTool(),
        OpenUrlTool(),
        SearchWebBrowserTool(),
        ListCalendarEventsTool(),
        AddCalendarEventTool(),
        SeeScreenTool(),
        SeeCameraTool(),
    ]
    if config.tavily_api_key:
        tools.append(WebSearchTool())

    return ToolRegistry(tools)


__all__ = ["Tool", "ToolRegistry", "build_default_registry"]
