# Jarvis (macOS) — Phase 5

A full-screen "command center" dashboard (Electron + React) backed by a
Python service: hold the hotkey and talk, or type in the dashboard — Groq
answers, speaks back in German, and remembers the conversation across
restarts.

```
                      ┌─────────────────────────────┐
hold hotkey (Option)  │   jarvis/server.py          │   ws+http
   → mic → Whisper    │   (Brain · Memory · Voice   │ ───────────▶  Electron + React
   → Groq → reply     │    · TTS, same as before)   │                dashboard (UI only)
   → TTS              └─────────────────────────────┘
```

The Python backend (`jarvis/`) owns everything it always did — the global
hotkey, the mic, Whisper, Groq, SQLite memory, TTS. It no longer drives a
Qt popup; instead it broadcasts state over a local WebSocket, and the
Electron dashboard renders it.

## Setup

`sounddevice` needs the system PortAudio library to talk to the microphone:

```bash
brew install portaudio
```

Python backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then add your GROQ_API_KEY
```

Get a free Groq key at <https://console.groq.com/keys>.

Dashboard (Electron + React):

```bash
cd electron
npm install
```

## Camera (Phase 4)

`see_camera` opens the webcam for a single frame, then releases it — no
continuous monitoring. The first call triggers macOS's Camera permission
prompt for whichever app/binary is running the backend (same per-app
caveat as Accessibility/Input Monitoring below); grant it under System
Settings > Privacy & Security > Camera.

## macOS permissions (required)

Electron spawns the Python backend as its own OS process, and the hotkey
listener (pynput) runs *inside that Python process* — so both **Electron**
and the actual Python binary need Accessibility + Input Monitoring, not
just Electron. Find the real Python binary with:

```bash
.venv/bin/python3 -c "import sys; print(sys.executable)"
```

(On Homebrew's framework build this resolves to a `Python.app` bundle
inside the framework, not a bare `python3` binary — add *that* `.app`.)

- **Accessibility** — System Settings → Privacy & Security →
  Accessibility → add both `Electron.app`
  (`electron/node_modules/electron/dist/Electron.app`) and the `Python.app`
  from above.
- **Input Monitoring** — same two apps, under System Settings → Privacy &
  Security → Input Monitoring. Without this, hold-to-talk can look like
  it's "working" but only ever fire the press, never the release.
- **Microphone** — voice input needs it. macOS prompts the first time the
  app opens the mic (at startup). There's no manual "+" here — it only
  populates after a real access attempt, so if it's missing, just (re)launch
  Jarvis once.

Each of these is granted **per app/binary** — switching how you launch
Jarvis (Terminal vs. VS Code vs. Electron vs. a packaged build) means
granting all of them again for that app. Restart after granting.

**If you've granted everything and it still doesn't work** (warning
persists, only `PRESS` ever fires, never `RELEASE`): the TCC database
itself can get into a stale state where the UI shows a permission as
granted but it isn't actually honored. Reset and re-grant from scratch:

```bash
tccutil reset Accessibility
tccutil reset ListenEvent
```

This wipes *every* app's grant for both permissions (Terminal, VS Code,
Discord, everything) — you'll need to re-add all of them, but it forces a
real, fresh system prompt instead of a stale cached decision.

## Run

**Development** (hot-reloading dashboard, two processes):

```bash
cd electron
npm run dev
```

This starts the Vite dev server and Electron together, pointed at the
local dev build. The Electron main process spawns the Python backend
(`python3 -m jarvis.server`) for you.

**Production-style** (built dashboard, single command):

```bash
cd electron && npm run build && cd ..
./start.sh
```

- **Hold Option** to talk. Release when done — Jarvis transcribes locally
  and sends it to Groq. The first hold downloads the Whisper model
  (one-time, a few hundred MB depending on `WHISPER_MODEL`).
- **Type in the dashboard's input** instead, if you'd rather not talk.
- On startup, Jarvis greets you out loud before anything else activates.

## Auto-start on login (launchd)

`com.jarvis.app.plist` runs `start.sh` via a per-user LaunchAgent. It's
**not installed automatically** — review the paths (hardcoded to this
checkout) before enabling:

```bash
cp com.jarvis.app.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jarvis.app.plist
```

To undo:

```bash
launchctl unload ~/Library/LaunchAgents/com.jarvis.app.plist
rm ~/Library/LaunchAgents/com.jarvis.app.plist
```

Logs go to `jarvis.log` / `jarvis.err.log` in the project root.

## Config (`.env`)

| Key                   | Default                     | Notes                              |
|------------------------|-----------------------------|-------------------------------------|
| `GROQ_API_KEY`         | —                           | required                            |
| `GROQ_MODEL`           | `llama-3.3-70b-versatile`   | swap freely                         |
| `TEMPERATURE`          | `0.6`                       |                                      |
| `MAX_TOKENS`           | `1024`                      |                                      |
| `HOTKEY`               | `alt`                       | `alt`=Option, also `cmd`, `f9`…     |
| `WHISPER_MODEL`        | `base`                      | `tiny`/`base`/`small`/`medium`/`large-v3` |
| `WHISPER_LANGUAGE`     | (auto-detect)               | e.g. `en`, `de` — skips detection   |
| `MIN_RECORD_SECONDS`   | `0.35`                      | holds shorter than this are ignored |
| `MEMORY_ENABLED`       | `true`                      | persist conversations across restarts |
| `MEMORY_DB_PATH`       | `jarvis_memory.db`          | SQLite file, relative to project root |
| `TTS_ENABLED`          | `false`                     | speak every reply + startup greeting |
| `TTS_VOICE`            | `de-DE-KillianNeural`       | edge-tts fallback voice            |
| `ELEVENLABS_API_KEY`   | —                           | optional, better quality           |
| `ELEVENLABS_VOICE_ID`  | —                           | required if using ElevenLabs       |
| `TOOLS_ENABLED`        | `true`                      | gives the LLM real system access (see below) |
| `TAVILY_API_KEY`       | —                           | enables `web_search`; get a free key at tavily.com |
| `VISION_MODEL`         | `meta-llama/llama-4-scout-17b-16e-instruct` | used only by `see_screen` |
| `PROACTIVITY_ENABLED`  | `true`                      | morning brief / GitHub watcher / idle nudge |
| `MORNING_BRIEF_TIME`   | `07:30`                     |                                      |
| `GITHUB_REPOS`         | —                           | comma-separated `owner/repo` list  |
| `IDLE_NUDGE_MINUTES`   | `120`                       |                                      |
| `WEATHER_LATITUDE` / `_LONGITUDE` | — | for the morning brief's weather section |
| `PROFILE_ENABLED`      | `true`                      | structured profile (see below), needs `MEMORY_ENABLED=true` |
| `PROFILE_EXTRACTION_MODEL` | `llama-3.1-8b-instant` | cheap model for per-turn extraction |
| `CAMERA_INDEX`         | `0`                         | which webcam `see_camera` opens     |

## Tools (Phase 1)

With `TOOLS_ENABLED=true` (default), the model decides on its own — via
Groq function calling — when to use real system access instead of just
talking. Implemented in `jarvis/tools/`, one class per tool:

| Tool | What it does |
|------|---------------|
| `read_file` / `write_file` / `list_files` | Read, create/overwrite, and search files |
| `run_shell` | Run a shell command (zsh), 30s timeout |
| `open_app` | Launch a macOS app by name (`open -a`) |
| `read_clipboard` / `write_clipboard` | Get/set the clipboard (`pbpaste`/`pbcopy`) |
| `open_url` / `search_web_browser` | Open a URL or a Google search in the default browser |
| `list_calendar_events` / `add_calendar_event` | Query/add macOS Calendar events via AppleScript |
| `see_screen` | Screenshot the screen and describe it via a vision-capable Groq model |
| `see_camera` | Capture one webcam frame and describe it via the same vision model |
| `web_search` | Web search via Tavily — only registered if `TAVILY_API_KEY` is set |

Every tool call (name, arguments, result) is broadcast to the dashboard as
a `tool_call` WebSocket event and shown in the chat log, so you can see
what Jarvis actually did.

**`run_shell` and `write_file` execute with this process's full
permissions and have no sandboxing or confirmation step** — by design,
for a single trusted user on their own machine. Set `TOOLS_ENABLED=false`
if you'd rather Jarvis stay a plain chatbot.

## Proactivity (Phase 2)

With `PROACTIVITY_ENABLED=true` (default), `jarvis/proactive.py` runs
three background jobs on an APScheduler scheduler — Jarvis can speak up
without being asked:

| Job | Behavior |
|-----|----------|
| Morning brief | Once a day (`MORNING_BRIEF_TIME`), summarizes today's calendar, open GitHub PRs, the weather, and (optionally) a tasks checklist file — spoken aloud and shown in the dashboard. |
| GitHub watcher | Polls `GITHUB_REPOS` every `GITHUB_WATCH_INTERVAL_MINUTES` via the `gh` CLI; only announces PRs that are new or changed since the last poll. |
| Idle nudge | After `IDLE_NUDGE_MINUTES` with no hotkey/typed interaction, suggests a break. Re-arms as soon as you interact again. |

The GitHub watcher needs `gh auth login` already done — it shells out to
the CLI rather than managing its own token. Weather uses Open-Meteo
(`WEATHER_LATITUDE`/`WEATHER_LONGITUDE`), no API key required.

## Structured memory (Phase 3)

With `PROFILE_ENABLED=true` (default, needs `MEMORY_ENABLED=true` too),
Jarvis keeps a small structured JSON profile instead of just replaying
raw chat history:

```json
{
  "projects": {"cosinuss": {"status": "in_progress", "priority": 1}},
  "goals": ["IU Madinah"],
  "daily_patterns": {"produktivster Zeitraum": "9-13 Uhr"},
  "preferences": {"response_style": "direkt"}
}
```

After every turn, a cheap/fast model (`PROFILE_EXTRACTION_MODEL`, default
`llama-3.1-8b-instant`) reads the exchange in the background and returns
a JSON *patch* — only what's new or changed. The patch is merged
additively into the profile (`jarvis/profile.py`) stored in the same
SQLite file as the chat log (`memory.py`'s `profile` table) — nothing
gets deleted just because a later turn didn't mention it. The current
profile is injected into every system prompt (`llm.py`'s `Brain.ask`), so
Jarvis has persistent context about you without re-reading the whole
conversation history. Inspect it directly via `GET /api/profile`.

## Layout

```
jarvis/
  config.py    load .env into one typed Config
  llm.py       Groq client + working-memory window, seeded from MemoryStore
  memory.py    persistent conversation log + structured profile (SQLite)
  profile.py   per-turn structured-profile extraction (Phase 3)
  hotkey.py    global Option-key listener (press/release for hold-to-talk)
  voice.py     mic capture (sounddevice) + local STT (faster-whisper)
  tts.py       speech output: ElevenLabs, falling back to edge-tts
  tools/       real system access via Groq function calling (see Tools above)
  proactive.py background jobs: morning brief, GitHub watcher, idle nudge
  server.py    FastAPI + WebSocket bridge — the dashboard's only way in
electron/
  main.js      Electron main process; spawns the Python backend
  src/         React dashboard (orb, chat log, waveform, status panels)
start.sh       launches Electron (which spawns the backend) — used by launchd
com.jarvis.app.plist   launchd LaunchAgent (not installed automatically)
```

