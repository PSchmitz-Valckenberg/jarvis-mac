"""Open-PR lookup via the `gh` CLI — shared by the proactivity engine and
the dashboard's GitHub widget so both poll the exact same way.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

GITHUB_TIMEOUT_SECONDS = 15


def fetch_open_prs(repo: str) -> list[dict[str, Any]] | None:
    """None means the lookup failed (gh missing, timeout, auth) — distinct
    from an empty list, which means it succeeded and there are no open PRs."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--repo", repo, "--state", "open", "--json", "number,title,updatedAt,url,author"],
            capture_output=True,
            text=True,
            timeout=GITHUB_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
