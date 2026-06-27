import { useEffect, useRef } from "react";

/** Animated bar waveform. Reacts to `active` rather than real audio levels —
 * streaming raw amplitude over the WebSocket isn't worth the complexity for
 * a status indicator that's mostly decorative. */
export default function Waveform({ active }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const bars = 56;
    let phase = 0;
    let raf;

    function draw() {
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      const barWidth = width / bars;
      for (let i = 0; i < bars; i++) {
        const t = phase + i * 0.35;
        const amp = active
          ? Math.sin(t) * 0.35 + 0.45 + Math.random() * 0.2
          : 0.04;
        const barHeight = Math.max(2, amp * height);
        ctx.fillStyle = active ? "#39e6ff" : "#1c3a44";
        ctx.fillRect(i * barWidth + 1, (height - barHeight) / 2, barWidth - 2, barHeight);
      }
      phase += active ? 0.22 : 0.02;
      raf = requestAnimationFrame(draw);
    }
    draw();
    return () => cancelAnimationFrame(raf);
  }, [active]);

  return <canvas ref={canvasRef} width={900} height={64} className="waveform" />;
}
