#!/bin/bash
# Launches the Jarvis Python backend, which also serves the dashboard
# (built React app) at http://127.0.0.1:8765/dashboard.
# Used directly, or by the launchd agent for auto-start on login.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# launchd's environment can be unusually bare; make sure Homebrew's bin dirs
# (portaudio, etc.) are reachable even if launchd's default PATH omits them.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

exec "$DIR/.venv/bin/python3" -m jarvis.server
