import { useState } from "react";
import ErrorBoundary from "./ErrorBoundary.jsx";
import NewsGlobe from "./NewsGlobe.jsx";
import HeadlineModal from "./HeadlineModal.jsx";

function HeadlinePanel({ headlines, points, onSelect }) {
  const byTitle = new Map(points.map((p) => [p.title, p]));
  return (
    <div className="panel headline-panel">
      <p className="panel__title">
        <span>SCHLAGZEILEN</span>
        <span className="accent">{headlines.length}</span>
      </p>
      <ul className="list-widget headline-list">
        {headlines.length === 0 && <div className="empty-hint">Keine Nachrichten geladen.</div>}
        {headlines.map((title, i) => {
          const point = byTitle.get(title);
          return (
            <li key={i} onClick={() => onSelect(title)}>
              <span
                className="priority-dot"
                style={{ background: point ? `var(--prio-${point.priority})` : "var(--text-dim)" }}
              />
              <span className="headline-list__title">{title}</span>
              {point && <span className="headline-list__meta">{point.location}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function CenterColumn({ newsHeadlines, newsPoints, fetchHeadlineSummary }) {
  const [selectedHeadline, setSelectedHeadline] = useState(null);

  return (
    <div className="column">
      <div className="panel globe-stage" style={{ flex: "0 0 55%" }}>
        <p className="panel__title">
          <span>WELTGESCHEHEN</span>
          <span className="accent">{newsPoints.length} VERORTET</span>
        </p>
        <ErrorBoundary fallback={<div className="empty-hint">Globus nicht verfügbar (WebGL fehlt).</div>}>
          <NewsGlobe points={newsPoints} onPointClick={setSelectedHeadline} />
        </ErrorBoundary>
      </div>

      <HeadlinePanel headlines={newsHeadlines} points={newsPoints} onSelect={setSelectedHeadline} />

      {selectedHeadline && (
        <HeadlineModal
          headline={selectedHeadline}
          fetchSummary={fetchHeadlineSummary}
          onClose={() => setSelectedHeadline(null)}
        />
      )}
    </div>
  );
}
