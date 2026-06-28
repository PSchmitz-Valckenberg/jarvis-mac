import Orb from "./Orb.jsx";
import Waveform from "./Waveform.jsx";
import ChatLog from "./ChatLog.jsx";

export default function LeftColumn({ state, ticker, log, status }) {
  return (
    <div className="column">
      <div className="panel orb-wrap">
        <Orb state={state} />
        <Waveform state={state} />
        <div className="voice-status">{ticker}</div>
      </div>

      <ChatLog log={log} />

      <div className="panel">
        <p className="panel__title">
          <span>VOICE INPUT</span>
        </p>
        <div className="status-light-grid" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11 }}>
          <span>
            Mikrofon: <strong style={{ color: status?.voice_available ? "var(--green)" : "var(--red)" }}>
              {status?.voice_available ? "VERFÜGBAR" : "NICHT VERFÜGBAR"}
            </strong>
          </span>
          <span>
            Hotkey: <strong style={{ color: "var(--orange)" }}>{(status?.hotkey || "alt").toUpperCase()}</strong>
          </span>
          <span>
            Modell: <span style={{ color: "var(--text-dim)" }}>{status?.model || "—"}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
