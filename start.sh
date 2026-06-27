#!/bin/bash
# Launches the Jarvis dashboard (Electron) + Python backend.
# Used directly, or by the launchd agent for auto-start on login.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# launchd's environment can be unusually bare; make sure Homebrew's bin dirs
# (portaudio, etc.) are reachable even if launchd's default PATH omits them.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Irrelevant outside this project's own dev/sandbox tooling, but unset it
# just in case — it forces Electron into plain-Node mode with no GUI.
unset ELECTRON_RUN_AS_NODE

exec "$DIR/electron/node_modules/.bin/electron" "$DIR/electron"
