function StatusLight({ label, on }) {
  return (
    <div className={`status-light ${on ? "on" : ""}`}>
      <span className="status-light__dot" />
      <span>{label}</span>
    </div>
  );
}

export default function BottomBar({ status }) {
  return (
    <div className="bottom-bar">
      <div className="system-status">
        <StatusLight label="MEMORY" on={!!status?.memory_enabled} />
        <StatusLight label="TOOLS" on={!!status?.tools_enabled} />
        <StatusLight label="TTS" on={!!status?.tts_enabled} />
      </div>
    </div>
  );
}
