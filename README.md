# Jarvis (macOS) — Phase 4

A minimal, Mac-style AI overlay. Hold the hotkey and talk, or tap it and
type — a dark glass panel pops up, Groq answers (out loud too, if you
want), and it remembers your conversation across restarts. Tools come in
a later phase.

```
hold hotkey (Option)  →  overlay "Listening…"  →  release
    →  local Whisper STT  →  Groq LLM  →  reply

tap hotkey  →  overlay opens for typed text  →  Groq LLM  →  reply
```

## Setup

`sounddevice` needs the system PortAudio library to talk to the microphone:

```bash
brew install portaudio
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then add your GROQ_API_KEY
```

Get a free key at <https://console.groq.com/keys>.

## macOS permissions (required)

- **Accessibility** — global key capture needs it. System Settings →
  Privacy & Security → Accessibility → enable your terminal (e.g.
  Terminal/iTerm) or the Python launcher.
- **Input Monitoring** — a *separate* permission global hotkey listeners
  also need on macOS. System Settings → Privacy & Security → Input
  Monitoring → enable the same app. Without this, hold-to-talk can look
  like it's "working" but get the press/release timing wrong.
- **Microphone** — voice input needs it. macOS prompts the first time the
  app opens the mic (at startup); if you miss it, add your terminal under
  System Settings → Privacy & Security → Microphone.

Each of these is granted **per app** — if you run Jarvis from a different
terminal (e.g. switching from Terminal.app to VS Code's integrated
terminal), you'll need to grant all three again for that app.

Restart the app after granting either permission.

## Run

```bash
python run.py
```

- **Hold Option** to talk. Release when done — Jarvis transcribes locally
  and sends it to Groq. The first hold downloads the Whisper model
  (one-time, a few hundred MB depending on `WHISPER_MODEL`).
- **Tap Option** (quick press) to open the overlay for typed input instead.
  **Enter** to send, **Esc** to dismiss.

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
| `TTS_ENABLED`          | `false`                     | speak every reply out loud           |
| `TTS_VOICE`            | `en-US-AriaNeural`          | see `edge-tts --list-voices`         |

## Layout

```
jarvis/
  config.py    load .env into one typed Config
  llm.py       Groq client + working-memory window, seeded from MemoryStore
  memory.py    persistent conversation log (SQLite)
  hotkey.py    global Option-key listener (press/release for hold-to-talk)
  voice.py     mic capture (sounddevice) + local STT (faster-whisper)
  tts.py       optional speech output (edge-tts + afplay)
  overlay.py   frameless translucent Qt panel (text + listening states)
  app.py       wires hotkey → voice/text → LLM (→ TTS)
run.py         entry point
```

## Roadmap (next phases)

- Tools: clipboard, web search, app launcher, screen capture, browser control
