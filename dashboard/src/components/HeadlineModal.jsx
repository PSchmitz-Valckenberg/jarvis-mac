import { useEffect, useState } from "react";

export default function HeadlineModal({ headline, fetchSummary, onClose }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchSummary(headline).then((data) => {
      if (!cancelled) {
        setSummary(data);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [headline, fetchSummary]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ position: "relative" }}>
        <span className="modal-box__close" onClick={onClose}>
          ✕
        </span>
        <p className="modal-box__title">{headline}</p>

        {loading && <div className="empty-hint">Lade Zusammenfassung…</div>}

        {!loading && summary?.error && <div className="empty-hint">{summary.error}</div>}

        {!loading && !summary?.error && (
          <>
            {summary?.what && (
              <div className="modal-box__field">
                <span className="modal-box__field-label">WAS</span>
                {summary.what}
              </div>
            )}
            {summary?.where && (
              <div className="modal-box__field">
                <span className="modal-box__field-label">WO</span>
                {summary.where}
              </div>
            )}
            {summary?.when && (
              <div className="modal-box__field">
                <span className="modal-box__field-label">WANN</span>
                {summary.when}
              </div>
            )}
            {summary?.sources?.length > 0 && (
              <div className="modal-box__sources">
                {summary.sources.map((s, i) => (
                  <a key={i} href={s.url} target="_blank" rel="noreferrer">
                    {s.title || s.url}
                  </a>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
