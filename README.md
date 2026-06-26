# Jarvis (macOS) — Phase 1

A minimal, Mac-style AI overlay. Tap a hotkey, a dark glass panel pops up,
you type, and Groq answers. Voice, memory and tools come in later phases.

```
hotkey (Option)  →  overlay  →  text  →  Groq LLM  →  reply
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then add your GROQ_API_KEY
```

Get a free key at <https://console.groq.com/keys>.

## macOS permission (required)

Global key capture needs Accessibility access. Go to
**System Settings → Privacy & Security → Accessibility** and enable your
terminal (e.g. Terminal/iTerm) or the Python launcher. Restart the app after.

## Run

```bash
python run.py
```

Tap **Option** to summon the overlay. Type a question, **Enter** to send,
**Esc** to dismiss. Tap Option again to toggle it away.

## Config (`.env`)

| Key             | Default                     | Notes                        |
|-----------------|-----------------------------|------------------------------|
| `GROQ_API_KEY`  | —                           | required                     |
| `GROQ_MODEL`    | `llama-3.3-70b-versatile`   | swap freely                  |
| `TEMPERATURE`   | `0.6`                       |                              |
| `MAX_TOKENS`    | `1024`                      |                              |
| `HOTKEY`        | `alt`                       | `alt`=Option, also `cmd`, `f9`… |
| `TTS_ENABLED`   | `false`                     | Phase 2                      |

## Layout

```
jarvis/
  config.py    load .env into one typed Config
  llm.py       Groq client + short session history
  hotkey.py    global Option-key listener (press/release split for voice)
  overlay.py   frameless translucent Qt panel
  app.py       wires hotkey → overlay → LLM
run.py         entry point
```

## Roadmap (next phases)

- Voice in (local Whisper STT, hold-Option-to-record)
- Persistent memory (SQLite)
- Optional TTS (edge-tts)
- Tools: clipboard, web search, app launcher, screen capture, browser control
