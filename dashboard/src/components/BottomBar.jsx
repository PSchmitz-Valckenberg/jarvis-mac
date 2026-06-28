import ErrorBoundary from "./ErrorBoundary.jsx";
import NewsGlobe from "./NewsGlobe.jsx";

const PRIORITY_LABEL = { high: "HOCH", medium: "MITTEL", low: "NIEDRIG" };

function StatusLight({ label, on }) {
  return (
    <div className={`status-light ${on ? "on" : ""}`}>
      <span className="status-light__dot" />
      <span>{label}</span>
    </div>
  );
}

function HeadlineList({ headlines, points }) {
  const byTitle = new Map(points.map((p) => [p.title, p]));
  const rows = headlines.map((title) => ({ title, point: byTitle.get(title) }));

  return (
    <ul className="list-widget headline-list">
      {rows.length === 0 && <div className="empty-hint">Keine Nachrichten geladen.</div>}
      {rows.map(({ title, point }, i) => (
        <li key={i}>
          <span
            className="priority-dot"
            style={{ background: point ? `var(--prio-${point.priority})` : "var(--text-dim)" }}
          />
          <span className="headline-list__title">{title}</span>
          {point && (
            <span className="headline-list__meta">
              {point.location} · {PRIORITY_LABEL[point.priority]}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function BottomBar({ headlines, points, status }) {
  return (
    <div className="bottom-bar">
      <div className="news-section">
        <div className="panel news-section__globe-panel">
          <p className="panel__title">
            <span>WELTGESCHEHEN</span>
            <span className="accent">{points.length} VERORTET</span>
          </p>
          <ErrorBoundary fallback={<div className="empty-hint">Globus nicht verfügbar (WebGL fehlt).</div>}>
            <NewsGlobe points={points} />
          </ErrorBoundary>
        </div>
        <div className="panel news-section__list-panel">
          <p className="panel__title">
            <span>SCHLAGZEILEN</span>
            <span className="accent">{headlines.length}</span>
          </p>
          <HeadlineList headlines={headlines} points={points} />
        </div>
      </div>
      <div className="system-status">
        <StatusLight label="MEMORY" on={!!status?.memory_enabled} />
        <StatusLight label="TOOLS" on={!!status?.tools_enabled} />
        <StatusLight label="TTS" on={!!status?.tts_enabled} />
      </div>
    </div>
  );
}
