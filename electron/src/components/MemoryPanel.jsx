import { Panel, Row } from "./Panel.jsx";

export default function MemoryPanel({ status }) {
  return (
    <Panel title="MEMORY">
      <Row label="STATUS" value={status?.memory_enabled ? "ACTIVE" : "DISABLED"} />
      <Row label="STORED TURNS" value={status ? status.memory_turns : "—"} />
    </Panel>
  );
}
