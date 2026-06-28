import Orb from "./Orb.jsx";
import Waveform from "./Waveform.jsx";
import ChatLog from "./ChatLog.jsx";
import PortfolioCompact from "./PortfolioCompact.jsx";

export default function LeftColumn({ state, ticker, log, status, portfolio }) {
  return (
    <div className="column">
      <div className="panel orb-wrap" style={{ flex: "0 0 auto" }}>
        <Orb state={state} />
        <Waveform state={state} />
        <div className="voice-status">{ticker}</div>
      </div>

      <PortfolioCompact portfolio={portfolio} />

      <ChatLog log={log} />

      <div className="panel" style={{ flex: "0 0 auto" }}>
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
