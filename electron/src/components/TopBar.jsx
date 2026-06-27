export default function TopBar({ connected, status }) {
  return (
    <div className="top-bar">
      <div className="brand">JARVIS // COMMAND CENTER</div>
      <div className="status-indicators">
        <span className={`dot ${connected ? "ok" : "bad"}`} />
        <span>{connected ? "LINK OK" : "LINK DOWN"}</span>
        <span className="sep">·</span>
        <span>{status?.model ?? "—"}</span>
        <span className="sep">·</span>
        <span>HOTKEY: {status?.hotkey ? status.hotkey.toUpperCase() : "—"}</span>
      </div>
    </div>
  );
}
