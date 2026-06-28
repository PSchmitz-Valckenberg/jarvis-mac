import { useEffect, useRef, useState } from "react";

const WIDTH = 80;
const HEIGHT = 24;

export default function Sparkline({ values, positive }) {
  const pathRef = useRef(null);
  const [length, setLength] = useState(0);

  const points = values && values.length > 1 ? values : null;

  useEffect(() => {
    if (pathRef.current) {
      setLength(pathRef.current.getTotalLength());
    }
  }, [points]);

  if (!points) {
    return <svg className="sparkline" width={WIDTH} height={HEIGHT} />;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const step = WIDTH / (points.length - 1);

  const d = points
    .map((v, i) => `${i === 0 ? "M" : "L"} ${(i * step).toFixed(1)} ${(HEIGHT - ((v - min) / range) * HEIGHT).toFixed(1)}`)
    .join(" ");

  return (
    <svg className="sparkline" width={WIDTH} height={HEIGHT}>
      <path
        ref={pathRef}
        d={d}
        fill="none"
        stroke={positive ? "var(--green)" : "var(--red)"}
        strokeWidth="1.5"
        style={{
          strokeDasharray: length,
          strokeDashoffset: length,
          animation: "sparkline-draw 0.6s ease forwards",
        }}
      />
      <style>{`@keyframes sparkline-draw { to { stroke-dashoffset: 0; } }`}</style>
    </svg>
  );
}
