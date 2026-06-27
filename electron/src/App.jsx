import { useState } from "react";
import TopBar from "./components/TopBar.jsx";
import Orb from "./components/Orb.jsx";
import ChatLog from "./components/ChatLog.jsx";
import Waveform from "./components/Waveform.jsx";
import MemoryPanel from "./components/MemoryPanel.jsx";
import ToolsPanel from "./components/ToolsPanel.jsx";
import SystemPanel from "./components/SystemPanel.jsx";
import Ticker from "./components/Ticker.jsx";
import { useJarvisSocket } from "./hooks/useJarvisSocket.js";

export default function App() {
  const { connected, state, log, status, ticker, ask } = useJarvisSocket();
  const [draft, setDraft] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    const prompt = draft.trim();
    if (!prompt) return;
    ask(prompt);
    setDraft("");
  }

  return (
    <div className="app">
      <TopBar connected={connected} status={status} />

      <div className="main-grid">
        <div className="panel-left">
          <Orb state={state} />
        </div>

        <div className="panel-center">
          <ChatLog log={log} />
          <Waveform active={state === "listening" || state === "speaking"} />
          <form className="input-row" onSubmit={handleSubmit}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Tippe einen Befehl, oder halte die Hotkey zum Sprechen…"
            />
            <button type="submit">SENDEN</button>
          </form>
        </div>

        <div className="panel-right">
          <SystemPanel status={status} connected={connected} />
          <MemoryPanel status={status} />
          <ToolsPanel />
        </div>
      </div>

      <Ticker message={ticker} />
    </div>
  );
}
