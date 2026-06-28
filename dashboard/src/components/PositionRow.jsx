import { useEffect, useState } from "react";
import Sparkline from "./Sparkline.jsx";

const fmtMoney = (v, currency) =>
  v == null ? "—" : v.toLocaleString("de-DE", { style: "currency", currency: currency || "EUR", maximumFractionDigits: 0 });
const fmtPct = (v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);

export default function PositionRow({ symbol, position, currency, fetchSparkline }) {
  const [expanded, setExpanded] = useState(false);
  const [sparkline, setSparkline] = useState(null);

  useEffect(() => {
    fetchSparkline(symbol).then(setSparkline);
  }, [symbol, fetchSparkline]);

  const changePct = position?.day_change_pct;
  const trendClass = changePct == null ? "" : changePct >= 0 ? "up" : "down";

  return (
    <div className="fade-in">
      <div className="position-row" onClick={() => setExpanded((e) => !e)}>
        <span className="position-row__symbol">{symbol}</span>
        <Sparkline values={sparkline} positive={changePct == null || changePct >= 0} />
        <span className="position-row__value">
          {position ? fmtMoney(position.market_value, currency) : "kein Bestand"}
        </span>
        <span className={`position-row__change ${trendClass}`}>{position ? fmtPct(changePct) : "—"}</span>
      </div>
      {expanded && position && (
        <div className="position-detail">
          <span>Stück: {position.position}</span>
          <span>Ø Einstand: {fmtMoney(position.avg_cost, currency)}</span>
          <span>Tages-P&amp;L: {fmtMoney(position.day_pnl, currency)}</span>
          <span>Unrealisiert: {fmtMoney(position.unrealized_pnl, currency)}</span>
        </div>
      )}
    </div>
  );
}
