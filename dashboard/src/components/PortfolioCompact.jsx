const CANONICAL_SYMBOLS = ["ISDW", "HIWS", "HIPS", "HIJS", "TSM", "NVDA", "META"];

const fmtMoney = (v, currency) =>
  v == null ? "—" : v.toLocaleString("de-DE", { style: "currency", currency: currency || "EUR", maximumFractionDigits: 0 });
const fmtPct = (v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);

export default function PortfolioCompact({ portfolio }) {
  const positions = portfolio?.positions || [];
  const currency = portfolio?.currency || "EUR";
  const bySymbol = Object.fromEntries(positions.map((p) => [p.symbol, p]));
  const extras = positions.filter((p) => !CANONICAL_SYMBOLS.includes(p.symbol));

  const dayPct = portfolio?.day_pnl_pct;
  const positive = (dayPct ?? 0) >= 0;
  const stale = portfolio && portfolio.connected === false;

  return (
    <div className="panel portfolio-compact">
      <p className="panel__title">
        <span>PORTFOLIO</span>
        <span className="accent">{stale ? "CACHED" : portfolio ? "LIVE" : "…"}</span>
      </p>
      <div className="portfolio-compact__total">{fmtMoney(portfolio?.total_value, currency)}</div>
      <div className={`portfolio-compact__pct ${positive ? "up" : "down"}`}>{fmtPct(dayPct)} heute</div>
      {CANONICAL_SYMBOLS.map((symbol) => {
        const p = bySymbol[symbol];
        const changePct = p?.day_change_pct;
        const trendClass = changePct == null ? "" : changePct >= 0 ? "up" : "down";
        return (
          <div key={symbol} className="portfolio-compact-row">
            <span className="portfolio-compact-row__symbol">{symbol}</span>
            <span className="portfolio-compact-row__value">{p ? fmtMoney(p.market_value, currency) : "—"}</span>
            <span className={`portfolio-compact-row__change ${trendClass}`}>{p ? fmtPct(changePct) : "—"}</span>
          </div>
        );
      })}
      {extras.map((p) => (
        <div key={p.symbol} className="portfolio-compact-row">
          <span className="portfolio-compact-row__symbol">{p.symbol}</span>
          <span className="portfolio-compact-row__value">{fmtMoney(p.market_value, currency)}</span>
          <span className={`portfolio-compact-row__change ${(p.day_change_pct ?? 0) >= 0 ? "up" : "down"}`}>
            {fmtPct(p.day_change_pct)}
          </span>
        </div>
      ))}
    </div>
  );
}
