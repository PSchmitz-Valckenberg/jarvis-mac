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

## Layout

```
jarvis/
  config.py    load .env into one typed Config
  llm.py       Groq client + working-memory window, seeded from MemoryStore
  memory.py    persistent conversation log (SQLite)
  hotkey.py    global Option-key listener (press/release for hold-to-talk)
  voice.py     mic capture (sounddevice) + local STT (faster-whisper)
  tts.py       speech output: ElevenLabs, falling back to edge-tts
  server.py    FastAPI + WebSocket bridge — the dashboard's only way in
electron/
  main.js      Electron main process; spawns the Python backend
  src/         React dashboard (orb, chat log, waveform, status panels)
start.sh       launches Electron (which spawns the backend) — used by launchd
com.jarvis.app.plist   launchd LaunchAgent (not installed automatically)
```

## Roadmap (next phases)

- Tools: clipboard, web search, app launcher, screen capture, browser control
