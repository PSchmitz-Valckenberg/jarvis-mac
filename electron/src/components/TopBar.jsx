import { useEffect, useState } from "react";

function useClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

// Cosmetic only — drifts slowly around a fixed base point for the
// "command center" feel, not a real location.
function useDriftingCoords() {
  const [coords, setCoords] = useState({ lat: 52.52, lon: 13.405 });
  useEffect(() => {
    const id = setInterval(() => {
      setCoords((c) => ({
        lat: c.lat + (Math.random() - 0.5) * 0.0008,
        lon: c.lon + (Math.random() - 0.5) * 0.0008,
      }));
    }, 1500);
    return () => clearInterval(id);
  }, []);
  return coords;
}

function pad(n) {
  return String(n).padStart(2, "0");
}

export default function TopBar({ connected, status }) {
  const time = useClock();
  const coords = useDriftingCoords();

  return (
    <div className="top-bar hud-frame">
      <div className="brand">JARVIS // COMMAND CENTER</div>
      <div className="coords">
        {coords.lat.toFixed(4)}°N {coords.lon.toFixed(4)}°E
      </div>
      <div className="status-indicators">
        <span className="live-indicator">
          <span className="live-dot" />
          LIVE
        </span>
        <span className="sep">·</span>
        <span className="clock">
          {pad(time.getHours())}:{pad(time.getMinutes())}:{pad(time.getSeconds())}
        </span>
        <span className="sep">·</span>
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
