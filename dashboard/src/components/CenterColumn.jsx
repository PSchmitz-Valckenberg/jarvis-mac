import PositionRow from "./PositionRow.jsx";

const CANONICAL_SYMBOLS = ["ISDW", "HIWS", "HIPS", "HIJS", "TSM", "NVDA", "META"];

const fmtMoney = (v, currency) =>
  v == null ? "—" : v.toLocaleString("de-DE", { style: "currency", currency: currency || "EUR" });
const fmtPct = (v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);

export default function CenterColumn({ portfolio, fetchSparkline }) {
  const positions = portfolio?.positions || [];
  const currency = portfolio?.currency || "EUR";
  const bySymbol = Object.fromEntries(positions.map((p) => [p.symbol, p]));
  const extras = positions.filter((p) => !CANONICAL_SYMBOLS.includes(p.symbol));

  const dayPct = portfolio?.day_pnl_pct;
  const positive = (dayPct ?? 0) >= 0;
  const stale = portfolio && portfolio.connected === false;

  return (
    <div className="column">
      <div className="panel gauge">
        <p className="panel__title">
          <span>PORTFOLIO</span>
          <span className="accent">{stale ? "CACHED — IBKR OFFLINE" : portfolio ? "LIVE" : "…"}</span>
        </p>
        <div className="gauge__value">{fmtMoney(portfolio?.total_value, currency)}</div>
        <div className={`gauge__pct ${positive ? "up" : "down"}`}>{fmtPct(dayPct)} heute</div>
      </div>

      <div className="panel" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <p className="panel__title">
          <span>POSITIONEN</span>
        </p>
        <div className="positions">
          {CANONICAL_SYMBOLS.map((symbol) => (
            <PositionRow
              key={symbol}
              symbol={symbol}
              position={bySymbol[symbol]}
              currency={currency}
              fetchSparkline={fetchSparkline}
            />
          ))}
          {extras.map((p) => (
            <PositionRow key={p.symbol} symbol={p.symbol} position={p} currency={currency} fetchSparkline={fetchSparkline} />
          ))}
        </div>
      </div>
    </div>
  );
}
