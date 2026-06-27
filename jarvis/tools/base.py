"""Base interface every tool implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolError(Exception):
    """Raised by a tool when it can't complete — the message is shown to the LLM."""


class Tool(ABC):
    """A single capability the LLM can invoke via function calling.

    `name` and `description` are read by the LLM to decide *when* to use
    the tool; `parameters` is a JSON-schema object describing its
    arguments, in the shape the Groq/OpenAI-style function-calling API
    expects. `run()` does the actual work and returns a string — there's no
    structured return type because the only consumer is the LLM's next
    turn, which just wants text.
    """

    name: str
    description: str
    parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """Execute the tool and return a result the LLM can read."""

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
