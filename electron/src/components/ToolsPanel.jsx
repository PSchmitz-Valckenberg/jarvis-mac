import { Panel, Row } from "./Panel.jsx";

// Placeholders for the next phase's tools (clipboard, web search, app
// launcher, screen capture, browser control) — wired up once they exist.
const TOOLS = ["Clipboard", "Web Search", "App Launcher", "Screen Capture", "Browser Control"];

export default function ToolsPanel() {
  return (
    <Panel title="ACTIVE TOOLS">
      {TOOLS.map((name) => (
        <Row key={name} label={name.toUpperCase()} value="—" />
      ))}
    </Panel>
  );
}
