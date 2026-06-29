# Jarvis (macOS) — Command Center

A full-screen "command center" dashboard (React, served by the Python
backend itself — open it in any browser) backed by a Python service: hold
the hotkey and talk, or type in the dashboard — Groq answers, speaks back
in German, remembers the conversation across restarts, and shows a live
IBKR portfolio, calendar, GitHub PRs, weather, and news.

```
                      ┌─────────────────────────────┐
hold hotkey (Option)  │   jarvis/server.py          │   ws+http
   → mic → Whisper    │   (Brain · Memory · Voice   │ ───────────▶  browser at
   → Groq → reply     │    · TTS · Portfolio        │               /dashboard
   → TTS              │    · Calendar/GitHub/etc.)  │               (React, built)
                       └─────────────────────────────┘
```

The Python backend (`jarvis/`) owns everything: the global hotkey, the
mic, Whisper, Groq, SQLite memory, TTS, IBKR portfolio polling, and the
calendar/GitHub/weather/news pulls for the dashboard. It broadcasts state
and data over a local WebSocket, and also serves the built dashboard
itself at `/dashboard` — no separate Electron process.

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

Dashboard (React, built once and served by the Python backend):

```bash
cd dashboard
npm install
npm run build
```

## IBKR setup (portfolio data)

The portfolio panel uses IBKR's **Flex Web Service** — no TWS or IB
Gateway needs to be installed or running. It's plain HTTPS calls
(`jarvis/ibkr_flex.py`) against a Flex Query you set up once in IBKR's
Client Portal. The trade-off: Flex reports are generated on demand, not
streamed, so this is a periodic snapshot (`IBKR_FLEX_POLL_MINUTES`, default
2h) rather than real-time — "day change" is computed by comparing each new
snapshot against the previous cached one, not IBKR's own intraday P&L.

1. Log into **IBKR Client Portal** (the web app at
   <https://www.interactivebrokers.com> → Log In).
2. **Performance & Reports → Flex Queries** → create a new "Activity Flex
   Query" → in the **Open Positions** section, select at least: `Symbol`,
   `CurrencyPrimary`, `Position`, `PositionValue`, `CostBasisPrice`,
   `FifoPnlUnrealized`. Save it and note the **Query ID** shown in the list.
3. **Settings → Flex Web Service** → generate a **token** (this is what
   authenticates the HTTPS calls — treat it like a password, never share it).
4. Put both in `.env`:
   ```
   IBKR_FLEX_TOKEN=<your token>
   IBKR_FLEX_QUERY_ID=<your query id>
   ```
5. Restart the backend. `PortfolioService` polls on its own background
   thread every `IBKR_FLEX_POLL_MINUTES` and caches every successful
   result to SQLite, so a failed poll falls back to the last known
   portfolio instead of showing nothing.

Once configured, `GET /api/portfolio` should show `"connected": true`
with real positions (in EUR — converted from each position's own currency
via a free FX lookup, `jarvis/fx.py`) instead of the cached/offline
fallback.

## Camera (Phase 4)

`see_camera` opens the webcam for a single frame, then releases it — no
continuous monitoring. The first call triggers macOS's Camera permission
prompt for whichever app/binary is running the backend (same per-app
caveat as Accessibility/Input Monitoring below); grant it under System
Settings > Privacy & Security > Camera.

## macOS permissions (required)

The hotkey listener (pynput) runs *inside the Python backend process* —
that's the binary that needs Accessibility + Input Monitoring. Find it
with:

```bash
.venv/bin/python3 -c "import sys; print(sys.executable)"
```

(On Homebrew's framework build this resolves to a `Python.app` bundle
inside the framework, not a bare `python3` binary — add *that* `.app`.)

- **Accessibility** — System Settings → Privacy & Security →
  Accessibility → add the `Python.app` from above.
- **Input Monitoring** — same app, under System Settings → Privacy &
  Security → Input Monitoring. Without this, hold-to-talk can look like
  it's "working" but only ever fire the press, never the release.
- **Microphone** — voice input needs it. macOS prompts the first time the
  app opens the mic (at startup). There's no manual "+" here — it only
  populates after a real access attempt, so if it's missing, just (re)launch
  Jarvis once.

Each of these is granted **per app/binary** — switching how you launch
Jarvis (Terminal vs. VS Code vs. a packaged build) means granting all of
them again for that app. Restart after granting.

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
# terminal 1
python3 -m jarvis.server

# terminal 2
cd dashboard && npm run dev
```

The Vite dev server proxies `/api` and `/ws` to the backend (see
`dashboard/vite.config.js`), so open <http://127.0.0.1:5174> while developing.

**Production-style** (built dashboard, single process):

```bash
cd dashboard && npm run build && cd ..
./start.sh
```

Then open <http://127.0.0.1:8765/dashboard>. The Python backend serves the
built dashboard itself — no second process needed.

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
| `DASHBOARD_DB_PATH`    | `jarvis_dashboard.db`       | SQLite file: portfolio cache/history, morning score |
| `IBKR_FLEX_TOKEN`      | —                           | Flex Web Service token (Client Portal → Settings) |
| `IBKR_FLEX_QUERY_ID`   | —                           | Flex Query ID (Client Portal → Performance & Reports → Flex Queries) |
| `IBKR_FLEX_POLL_MINUTES` | `120`                     | how often to re-poll — IBKR generates reports on demand, not live |

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

> **⚠️ Security:** Jarvis runs arbitrary shell commands and file writes
> with your own user permissions — there is no sandbox. This is only safe
> as a single-user tool running locally on your own Mac. Never run it
> with a shared/public `GROQ_API_KEY`, never expose its server (port
> `8765`) beyond `127.0.0.1`, and don't let untrusted input reach it
> (e.g. don't wire it up to anything that lets a stranger send it a
> prompt). `read_file`/`write_file`/`list_files` block a denylist of
> obviously sensitive paths (`.ssh`, `.aws`, `.env`, keychains, …), but
> that's a basic guardrail, not a security boundary — `run_shell` can
> still reach anything those tools block.

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

## Dashboard data (Command Center)

The dashboard (`dashboard/`, React + Vite, built to `dashboard/dist` and
served by the backend at `/dashboard`) shows:

| Panel | Source | Refresh |
|-------|--------|---------|
| Portfolio gauge + positions | IBKR Flex Web Service (`jarvis/portfolio.py`), SQLite-cached between polls | `IBKR_FLEX_POLL_MINUTES`, own background thread |
| Position sparklines | 7-day history from `portfolio_history` in `DASHBOARD_DB_PATH` | on demand |
| Calendar | macOS Calendar via AppleScript (`jarvis/tools/calendar.py`) | 5min |
| GitHub PRs | `gh` CLI against `GITHUB_REPOS` (`jarvis/github_status.py`) | `GITHUB_WATCH_INTERVAL_MINUTES` |
| Weather | Open-Meteo (`jarvis/weather.py`) | 15min |
| News + world globe | Tagesschau RSS (`jarvis/news.py`), geotagged/prioritized by a cheap Groq call (`jarvis/news_geo.py`) | 10min |
| Morning energy score | manual 1–10 slider, persisted per day in SQLite | — |

The news panel asks Groq (`PROFILE_EXTRACTION_MODEL`, the same cheap model
used for profile extraction) to map each headline to a country/city and a
low/medium/high priority — no external geocoding API. That's plotted as
colored points (red=high, orange=medium, green=low) on a rotating 3D globe
(`react-globe.gl`) next to the plain headline list, both fed by the same
`news_update` WebSocket event.

All of the above push updates over the same `/ws` WebSocket the voice
pipeline uses; the dashboard also does one REST fetch per panel on load
so it isn't empty before the first push.

## Layout

```
jarvis/
  config.py        load .env into one typed Config
  llm.py            Groq client + working-memory window, seeded from MemoryStore
  memory.py         persistent conversation log + structured profile (SQLite)
  profile.py        per-turn structured-profile extraction (Phase 3)
  hotkey.py         global Option-key listener (press/release for hold-to-talk)
  voice.py          mic capture (sounddevice) + local STT (faster-whisper)
  tts.py            speech output: ElevenLabs, falling back to edge-tts
  tools/            real system access via Groq function calling (see Tools above)
  proactive.py      background jobs: morning brief, GitHub watcher, idle nudge
  portfolio.py      IBKR Flex Web Service polling + SQLite cache/history for the dashboard
  ibkr_flex.py / fx.py   Flex Web Service client + free FX-rate lookup, used only by portfolio.py
  dashboard.py      calendar/GitHub/weather/news polling + morning score (SQLite)
  weather.py / news.py / github_status.py   small shared fetch helpers
  server.py         FastAPI + WebSocket bridge, REST endpoints, serves /dashboard
dashboard/
  src/              React dashboard (orb, chat log, portfolio, calendar, etc.)
  dist/             built output served by server.py at /dashboard (run `npm run build`)
start.sh            launches the Python backend — used by launchd
com.jarvis.app.plist   launchd LaunchAgent (not installed automatically)
```

