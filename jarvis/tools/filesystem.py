"""File system access — read, write, and search files on this machine.

There's no sandboxing here either (see run_shell) — these tools just block
a denylist of paths that are obviously never meant to be read or
overwritten by an LLM (SSH/cloud credentials, secrets, login keychains).
That's a basic guardrail against the model wandering somewhere it
shouldn't on a routine request, not a security boundary: run_shell has the
same filesystem access and isn't restricted by it.
"""

from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolError

# Caps how much file content/listing text gets fed back to the LLM — a huge
# log file or a directory with thousands of entries would otherwise blow
# past the model's context window on a single tool call, and on Groq's free
# tier (12k tokens/minute) a single oversized tool result can eat the whole
# budget for the next few turns.
MAX_READ_CHARS = 4_000
MAX_LIST_ENTRIES = 80
MAX_LIST_CHARS = 3_000

# Directories/files commonly holding credentials or secrets — off-limits to
# read_file/write_file/list_files regardless of how they're reached (~, an
# absolute path, or a relative path that resolves into one of these).
_BLOCKED_PATH_PARTS = {
    ".ssh",
    ".aws",
    ".gnupg",
    ".kube",
    ".docker",
    "Keychains",
}
_BLOCKED_NAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials",
}


def _is_blocked(target: Path) -> bool:
    parts = target.expanduser().parts
    if any(part in _BLOCKED_PATH_PARTS for part in parts):
        return True
    name = target.name
    return name in _BLOCKED_NAMES or name.startswith(".env")


def _resolve(path: str) -> Path:
    expanded = Path(path).expanduser()
    target = expanded if expanded.is_absolute() else (Path.cwd() / expanded)
    if _is_blocked(target):
        raise ToolError(f"Access to {target} is blocked (looks like a credentials/secrets path)")
    return target


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the contents of a text file on this Mac. Give an absolute "
        "path or one starting with ~. Large files are truncated."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file, e.g. ~/Documents/notes.txt"},
        },
        "required": ["path"],
    }

    def run(self, path: str) -> str:
        target = _resolve(path)
        if not target.exists():
            raise ToolError(f"File not found: {target}")
        if not target.is_file():
            raise ToolError(f"Not a file: {target}")
        try:
            text = target.read_text(errors="replace")
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Couldn't read {target}: {exc}") from exc
        if len(text) > MAX_READ_CHARS:
            text = text[:MAX_READ_CHARS] + f"\n…(truncated, {len(text)} chars total)"
        return text


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Create or overwrite a text file on this Mac with the given content. "
        "Give an absolute path or one starting with ~. Creates parent "
        "directories if needed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file, e.g. ~/Desktop/todo.txt"},
            "content": {"type": "string", "description": "The full text content to write"},
        },
        "required": ["path", "content"],
    }

    def run(self, path: str, content: str) -> str:
        target = _resolve(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Couldn't write {target}: {exc}") from exc
        return f"Wrote {len(content)} characters to {target}"


class ListFilesTool(Tool):
    name = "list_files"
    description = (
        "List files in a directory, optionally filtered by a glob pattern "
        "(e.g. '*.pdf'). Useful for finding a file when you don't know the "
        "exact path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Directory to list, e.g. ~/Downloads"},
            "pattern": {
                "type": "string",
                "description": "Glob pattern, default '*'. Use '**/*.ext' to search recursively.",
            },
        },
        "required": ["directory"],
    }

    def run(self, directory: str, pattern: str = "*") -> str:
        target = _resolve(directory)
        if not target.is_dir():
            raise ToolError(f"Not a directory: {target}")
        try:
            matches = sorted(target.glob(pattern))
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Bad pattern '{pattern}': {exc}") from exc
        if not matches:
            return f"No files matching '{pattern}' in {target}"
        shown = matches[:MAX_LIST_ENTRIES]
        lines = [f"{'d' if p.is_dir() else 'f'}  {p}" for p in shown]
        suffix = "" if len(matches) <= MAX_LIST_ENTRIES else f"\n…({len(matches)} total, truncated)"
        output = "\n".join(lines) + suffix
        if len(output) > MAX_LIST_CHARS:
            output = output[:MAX_LIST_CHARS] + f"\n…(truncated, {len(matches)} entries total)"
        return output
