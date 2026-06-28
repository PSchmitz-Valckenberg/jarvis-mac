import { useEffect, useState } from "react";

export default function TopBar({ connected }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const time = now.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const date = now.toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });

  return (
    <div className="top-bar">
      <div className="top-bar__title">JARVIS // COMMAND CENTER</div>
      <div className="top-bar__clock">
        <span className="top-bar__time">{time}</span>
        <span className="top-bar__date">{date}</span>
        <span style={{ color: connected ? "var(--green)" : "var(--red)" }}>
          {connected ? "● LINK" : "○ OFFLINE"}
        </span>
      </div>
    </div>
  );
}
