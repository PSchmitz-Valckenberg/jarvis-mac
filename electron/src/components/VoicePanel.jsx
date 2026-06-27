import { useEffect, useState } from "react";
import { Panel } from "./Panel.jsx";

const VOICES_URL = "http://127.0.0.1:8765/api/voices";
const VOICE_URL = "http://127.0.0.1:8765/api/voice";

export default function VoicePanel() {
  const [data, setData] = useState(null);

  useEffect(() => {
    function load() {
      fetch(VOICES_URL)
        .then((r) => r.json())
        .then(setData)
        .catch(() => {});
      // Deliberately don't clear data on a failed fetch — a single dropped
      // request (e.g. the backend was still starting up) shouldn't flash
      // the panel to "not configured"; the next poll will correct it.
    }
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!data || !data.enabled) {
    return (
      <Panel title="VOICE">
        <div className="voice-disabled">ElevenLabs not configured</div>
      </Panel>
    );
  }

  function handleChange(e) {
    const voice_id = e.target.value;
    setData((d) => ({ ...d, active: voice_id }));
    fetch(VOICE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice_id }),
    }).catch(() => {});
  }

  return (
    <Panel title="VOICE">
      <select className="voice-select" value={data.active ?? ""} onChange={handleChange}>
        {data.presets.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name} — {v.label}
          </option>
        ))}
      </select>
    </Panel>
  );
}
