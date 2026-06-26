# Jarvis (macOS) — Phase 2

A minimal, Mac-style AI overlay. Hold the hotkey and talk, or tap it and
type — a dark glass panel pops up, Groq answers. Memory and tools come in
later phases.

```
hold hotkey (Option)  →  overlay "Listening…"  →  release
    →  local Whisper STT  →  Groq LLM  →  reply

tap hotkey  →  overlay opens for typed text  →  Groq LLM  →  reply
```

## Setup

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
- **Microphone** — voice input needs it. macOS will prompt the first time
  you hold the hotkey; if you miss it, add your terminal under System
  Settings → Privacy & Security → Microphone.

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
| `TTS_ENABLED`          | `false`                     | Phase 3                             |

## Layout

```
jarvis/
  config.py    load .env into one typed Config
  llm.py       Groq client + short session history
  hotkey.py    global Option-key listener (press/release for hold-to-talk)
  voice.py     mic capture (sounddevice) + local STT (faster-whisper)
  overlay.py   frameless translucent Qt panel (text + listening states)
  app.py       wires hotkey → voice/text → LLM
run.py         entry point
```

## Roadmap (next phases)

- Persistent memory (SQLite)
- Optional TTS (edge-tts)
- Tools: clipboard, web search, app launcher, screen capture, browser control
