import { Panel, Row } from "./Panel.jsx";

function label(toolName) {
  return toolName.replace(/_/g, " ").toUpperCase();
}

export default function ToolsPanel({ status }) {
  if (!status?.tools_enabled) {
    return (
      <Panel title="ACTIVE TOOLS">
        <Row label="STATUS" value="DISABLED" />
      </Panel>
    );
  }

  const tools = status.tools ?? [];
  return (
    <Panel title="ACTIVE TOOLS">
      {tools.length === 0 ? (
        <Row label="STATUS" value="NONE" />
      ) : (
        tools.map((name) => <Row key={name} label={label(name)} value="ON" />)
      )}
    </Panel>
  );
}
