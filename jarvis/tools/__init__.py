"""Tool system — gives the LLM real access to the machine it runs on.

Each tool is a small class with a name, a description (read by the LLM to
decide when to use it), a JSON-schema `parameters` dict, and a `run()`
method. `build_default_registry()` wires up every tool that's configured
(some need an API key) and is the only thing callers outside this package
need.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .app_launcher import AppLauncherTool
from .base import Tool
from .browser import OpenUrlTool, SearchWebBrowserTool
from .calendar import AddCalendarEventTool, ListCalendarEventsTool
from .camera import SeeCameraTool
from .clipboard import ReadClipboardTool, WriteClipboardTool
from .dashboard_data import ReadNewsTool, ReadPortfolioTool, ReadWeatherTool
from .filesystem import ListFilesTool, ReadFileTool, WriteFileTool
from .registry import ToolRegistry
from .shell import RunShellTool
from .vision import SeeScreenTool
from .web_search import WebSearchTool

if TYPE_CHECKING:
    from ..dashboard import DashboardService
    from ..portfolio import PortfolioService


def build_default_registry(
    portfolio: "PortfolioService | None" = None,
    dashboard: "DashboardService | None" = None,
) -> ToolRegistry:
    """Assemble every tool that's available given the current config.

    `portfolio`/`dashboard` are optional because tools can be built before
    those services exist (e.g. tests) — without them, the assistant just
    won't have read_portfolio/read_news/read_weather registered.
    """
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
    if portfolio is not None:
        tools.append(ReadPortfolioTool(portfolio))
    if dashboard is not None:
        tools.append(ReadNewsTool(dashboard))
        tools.append(ReadWeatherTool(dashboard))

    return ToolRegistry(tools)


__all__ = ["Tool", "ToolRegistry", "build_default_registry"]
