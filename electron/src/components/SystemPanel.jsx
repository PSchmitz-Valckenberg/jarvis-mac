import { Panel, Row } from "./Panel.jsx";

export default function SystemPanel({ status, connected }) {
  return (
    <Panel title="SYSTEM">
      <Row label="LINK" value={connected ? "ONLINE" : "OFFLINE"} />
      <Row label="MODEL" value={status?.model ?? "—"} />
      <Row label="VOICE INPUT" value={status?.voice_available ? "READY" : "UNAVAILABLE"} />
      <Row label="TTS" value={status?.tts_enabled ? "ENABLED" : "DISABLED"} />
      <Row label="API KEY" value={status?.has_api_key ? "SET" : "MISSING"} />
    </Panel>
  );
}
