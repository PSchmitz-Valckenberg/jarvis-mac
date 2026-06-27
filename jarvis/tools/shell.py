"""Shell command execution — the most powerful (and most dangerous) tool.

Runs whatever the LLM asks for with the same permissions as this process.
There's no sandboxing here: it's deliberately scoped to a single trusted
user running Jarvis on their own machine, not a multi-tenant or untrusted
context.
"""

from __future__ import annotations

import subprocess

from .base import Tool, ToolError

TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 3_000


class RunShellTool(Tool):
    name = "run_shell"
    description = (
        "Run a shell command on this Mac (zsh) and return its stdout/stderr. "
        f"Times out after {TIMEOUT_SECONDS}s. Use this for things like "
        "checking processes, git status, disk usage, or quick scripting — "
        "not for long-running or interactive commands."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run"},
        },
        "required": ["command"],
    }

    def run(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise ToolError(f"Command timed out after {TIMEOUT_SECONDS}s") from None

        output = (result.stdout or "") + (result.stderr or "")
        output = output.strip() or "(no output)"
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n…(truncated)"
        return f"exit code {result.returncode}\n{output}"
