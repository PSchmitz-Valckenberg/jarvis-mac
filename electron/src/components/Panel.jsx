import { useGlitchOnChange } from "../hooks/useGlitchOnChange.js";

export function Panel({ title, children }) {
  return (
    <div className="panel hud-frame">
      <div className="panel-title">{title}</div>
      <div className="panel-body">{children}</div>
    </div>
  );
}

export function Row({ label, value }) {
  const glitching = useGlitchOnChange(value);
  return (
    <div className="panel-row">
      <span className="panel-row-label">{label}</span>
      <span className={`panel-row-value${glitching ? " glitch" : ""}`}>{value}</span>
    </div>
  );
}
