import { useEffect, useRef, useState } from "react";
import Globe from "react-globe.gl";

const PRIORITY_COLOR = {
  high: "#ff3b4e",
  medium: "#ff6a00",
  low: "#00ff88",
};

const PRIORITY_SIZE = {
  high: 0.9,
  medium: 0.65,
  low: 0.45,
};

export default function NewsGlobe({ points }) {
  const wrapRef = useRef(null);
  const globeRef = useRef(null);
  const [size, setSize] = useState({ width: 320, height: 200 });

  useEffect(() => {
    if (!wrapRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setSize({ width, height });
    });
    observer.observe(wrapRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;
    globe.controls().autoRotate = true;
    globe.controls().autoRotateSpeed = 0.6;
    globe.controls().enableZoom = false;
    globe.pointOfView({ lat: 20, lng: 10, altitude: 2.2 });
  }, []);

  const data = (points || []).map((p) => ({
    ...p,
    color: PRIORITY_COLOR[p.priority] || PRIORITY_COLOR.low,
    size: PRIORITY_SIZE[p.priority] || PRIORITY_SIZE.low,
  }));

  return (
    <div ref={wrapRef} className="globe-wrap">
      <Globe
        ref={globeRef}
        width={size.width}
        height={size.height}
        backgroundColor="rgba(0,0,0,0)"
        globeImageUrl="https://unpkg.com/three-globe/example/img/earth-night.jpg"
        bumpImageUrl="https://unpkg.com/three-globe/example/img/earth-topology.png"
        atmosphereColor="#00ff88"
        atmosphereAltitude={0.18}
        pointsData={data}
        pointLat="lat"
        pointLng="lon"
        pointColor="color"
        pointAltitude={0.02}
        pointRadius="size"
        pointResolution={12}
        pointLabel={(p) => `${p.title}\n${p.location}`}
      />
    </div>
  );
}
