import { useEffect, useRef, useState } from "react";

const BAR_COUNT = 16;
const ACTIVE_STATES = new Set(["listening", "speaking"]);

export default function Waveform({ state }) {
  const [heights, setHeights] = useState(Array(BAR_COUNT).fill(4));
  const frameRef = useRef(null);

  useEffect(() => {
    if (!ACTIVE_STATES.has(state)) {
      setHeights(Array(BAR_COUNT).fill(4));
      return;
    }
    function tick() {
      setHeights(Array.from({ length: BAR_COUNT }, () => 4 + Math.random() * 24));
      frameRef.current = setTimeout(tick, 90);
    }
    tick();
    return () => clearTimeout(frameRef.current);
  }, [state]);

  return (
    <div className="waveform">
      {heights.map((h, i) => (
        <div key={i} className="waveform__bar" style={{ height: `${h}px` }} />
      ))}
    </div>
  );
}
