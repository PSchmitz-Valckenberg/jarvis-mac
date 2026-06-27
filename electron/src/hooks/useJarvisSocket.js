import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL = "ws://127.0.0.1:8765/ws";
const STATUS_URL = "http://127.0.0.1:8765/api/status";
const ASK_URL = "http://127.0.0.1:8765/api/ask";

function tickerFor(state) {
  switch (state) {
    case "listening":
      return "LISTENING…";
    case "transcribing":
      return "TRANSCRIBING AUDIO…";
    case "thinking":
      return "QUERYING GROQ…";
    case "speaking":
      return "SPEAKING…";
    default:
      return "STANDBY";
  }
}

/** Owns the live connection to the Python backend: WebSocket events for
 * state/chat, polled HTTP status, and the ask() command for typed input. */
export function useJarvisSocket() {
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState("idle");
  const [log, setLog] = useState([]);
  const [status, setStatus] = useState(null);
  const [ticker, setTicker] = useState("STANDBY");
  const wsRef = useRef(null);

  useEffect(() => {
    let retryTimer;
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setTicker("LINK ESTABLISHED");
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          setTicker("LINK LOST — RECONNECTING");
          retryTimer = setTimeout(connect, 1500);
        }
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "state") {
          setState(data.state);
          setTicker(tickerFor(data.state));
        } else if (data.type === "transcript") {
          setLog((prev) => [...prev, { role: "user", text: data.text }]);
        } else if (data.type === "reply") {
          setLog((prev) => [...prev, { role: "assistant", text: data.text }]);
        } else if (data.type === "error") {
          setLog((prev) => [...prev, { role: "system", text: data.message }]);
          setTicker(`ERROR: ${data.message}`);
        } else if (data.type === "tool_call") {
          const resultPreview =
            data.result.length > 200 ? `${data.result.slice(0, 200)}…` : data.result;
          setLog((prev) => [
            ...prev,
            { role: "tool", text: `⚙ ${data.name}(${JSON.stringify(data.arguments)}) → ${resultPreview}` },
          ]);
        } else if (
          data.type === "morning_brief" ||
          data.type === "idle_nudge" ||
          data.type === "github_update"
        ) {
          // Jarvis speaking up on its own, not in response to a question —
          // shown as an assistant message so it reads naturally in the log.
          setLog((prev) => [...prev, { role: "assistant", text: data.text }]);
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const res = await fetch(STATUS_URL);
      setStatus(await res.json());
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 5000);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  const ask = useCallback(async (prompt) => {
    setLog((prev) => [...prev, { role: "user", text: prompt }]);
    try {
      await fetch(ASK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
    } catch {
      setTicker("BACKEND UNREACHABLE");
    }
  }, []);

  return { connected, state, log, status, ticker, ask };
}
