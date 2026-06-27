import { useEffect, useRef } from "react";

const POINT_COUNT = 60;
const RADIUS = 70;
const LINK_DISTANCE = 30;

const STATE_COLORS = {
  idle: "#39e6ff",
  listening: "#ff2e4d",
  transcribing: "#ff2e4d",
  thinking: "#ffaa33",
  speaking: "#39e6ff",
};

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Evenly distributes points on a sphere via the golden-angle spiral. */
function generateSpherePoints(count) {
  const points = [];
  const phi = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = phi * i;
    points.push({ x: Math.cos(theta) * r, y, z: Math.sin(theta) * r });
  }
  return points;
}

export default function Orb({ state }) {
  const canvasRef = useRef(null);
  const pointsRef = useRef(generateSpherePoints(POINT_COUNT));
  const angleRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    let raf;

    function draw() {
      ctx.clearRect(0, 0, w, h);
      const color = STATE_COLORS[state] || STATE_COLORS.idle;
      const speed = state === "idle" ? 0.004 : 0.018;
      angleRef.current += speed;
      const angle = angleRef.current;
      const cosA = Math.cos(angle);
      const sinA = Math.sin(angle);

      const projected = pointsRef.current.map((p) => {
        const x = p.x * cosA - p.z * sinA;
        const z = p.x * sinA + p.z * cosA;
        const scale = 220 / (220 + z * RADIUS);
        return {
          x: cx + x * RADIUS * scale,
          y: cy + p.y * RADIUS * scale,
          scale,
        };
      });

      ctx.lineWidth = 1;
      for (let i = 0; i < projected.length; i++) {
        for (let j = i + 1; j < projected.length; j++) {
          const a = projected[i];
          const b = projected[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < LINK_DISTANCE) {
            const opacity = (1 - dist / LINK_DISTANCE) * 0.45 * ((a.scale + b.scale) / 2);
            ctx.strokeStyle = hexToRgba(color, opacity);
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      for (const p of projected) {
        const r = 1.4 * p.scale + 0.4;
        ctx.fillStyle = hexToRgba(color, 0.4 + 0.5 * p.scale);
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      }

      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, RADIUS * 0.65);
      glow.addColorStop(0, hexToRgba(color, 0.3));
      glow.addColorStop(1, hexToRgba(color, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cx, cy, RADIUS * 0.65, 0, Math.PI * 2);
      ctx.fill();

      raf = requestAnimationFrame(draw);
    }

    draw();
    return () => cancelAnimationFrame(raf);
  }, [state]);

  return (
    <div className="orb-column">
      <canvas ref={canvasRef} width={220} height={220} className="orb-canvas" />
      <div className="state-label">{state.toUpperCase()}</div>
    </div>
  );
}
