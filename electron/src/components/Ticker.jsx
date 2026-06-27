export default function Ticker({ message, status }) {
  const items = [
    message,
    status ? `MODEL: ${status.model}` : null,
    status ? `MEMORY: ${status.memory_turns} TURNS` : null,
    status ? `TTS: ${status.tts_enabled ? "ENABLED" : "DISABLED"}` : null,
    status ? `VOICE: ${status.voice_available ? "READY" : "OFFLINE"}` : null,
    "JARVIS COMMAND CENTER",
  ].filter(Boolean);

  const text = items.join("   //   ");

  return (
    <div className="ticker hud-frame">
      <span className="ticker-tag">STATUS</span>
      <div className="ticker-track">
        <span className="ticker-text">{text}</span>
        <span className="ticker-text">{text}</span>
      </div>
    </div>
  );
}
