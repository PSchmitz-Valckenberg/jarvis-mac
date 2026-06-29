import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL = `ws://${window.location.hostname}:8765/ws`;
const API = (path) => `http://${window.location.hostname}:8765${path}`;

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

/** Owns every live connection the dashboard needs: the voice/chat WebSocket
 * (state, transcript, replies, proactive announcements, and the dashboard
 * data pushes from PortfolioService/DashboardService), plus the initial
 * REST fetch for each panel so it isn't empty before the first push. */
export function useJarvisDashboard() {
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState("idle");
  const [log, setLog] = useState([]);
  const [status, setStatus] = useState(null);
  const [ticker, setTicker] = useState("STANDBY");

  const [portfolio, setPortfolio] = useState(null);
  const [calendarEvents, setCalendarEvents] = useState([]);
  const [githubRepos, setGithubRepos] = useState({});
  const [weather, setWeather] = useState(null);
  const [newsHeadlines, setNewsHeadlines] = useState([]);
  const [newsPoints, setNewsPoints] = useState([]);
  const [morningScore, setMorningScore] = useState(null);

  const wsRef = useRef(null);

  // One-shot REST fetch per panel — called on mount AND every time the
  // WebSocket (re)connects, so a panel that loaded empty (backend was
  // briefly down, request raced a restart, ...) self-heals on reconnect
  // instead of staying empty until the user manually reloads the page.
  const refreshAllPanels = useCallback(() => {
    fetch(API("/api/portfolio")).then((r) => r.json()).then(setPortfolio).catch(() => {});
    fetch(API("/api/calendar")).then((r) => r.json()).then((d) => setCalendarEvents(d.events)).catch(() => {});
    fetch(API("/api/github")).then((r) => r.json()).then((d) => setGithubRepos(d.repos)).catch(() => {});
    fetch(API("/api/weather")).then((r) => r.json()).then((d) => setWeather(d.weather)).catch(() => {});
    fetch(API("/api/news"))
      .then((r) => r.json())
      .then((d) => {
        setNewsHeadlines(d.headlines);
        setNewsPoints(d.points || []);
      })
      .catch(() => {});
    fetch(API("/api/morning-score")).then((r) => r.json()).then((d) => setMorningScore(d.score)).catch(() => {});
  }, []);

  useEffect(() => {
    let retryTimer;
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setTicker("LINK ESTABLISHED");
        refreshAllPanels();
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
        switch (data.type) {
          case "state":
            setState(data.state);
            setTicker(tickerFor(data.state));
            break;
          case "transcript":
            setLog((prev) => [...prev, { role: "user", text: data.text }].slice(-5));
            break;
          case "reply_chunk":
            setLog((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === "assistant" && last.streaming) {
                return [...prev.slice(0, -1), { ...last, text: last.text + data.text }].slice(-5);
              }
              return [...prev, { role: "assistant", text: data.text, streaming: true }].slice(-5);
            });
            break;
          case "reply":
            setLog((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === "assistant" && last.streaming) {
                return [...prev.slice(0, -1), { role: "assistant", text: data.text }].slice(-5);
              }
              return [...prev, { role: "assistant", text: data.text }].slice(-5);
            });
            break;
          case "error":
            setLog((prev) => [...prev, { role: "system", text: data.message }].slice(-5));
            setTicker(`ERROR: ${data.message}`);
            break;
          case "tool_call": {
            const preview = data.result.length > 160 ? `${data.result.slice(0, 160)}…` : data.result;
            setLog((prev) =>
              [...prev, { role: "tool", text: `⚙ ${data.name}(${JSON.stringify(data.arguments)}) → ${preview}` }].slice(-5)
            );
            break;
          }
          case "morning_brief":
          case "idle_nudge":
            setLog((prev) => [...prev, { role: "assistant", text: data.text }].slice(-5));
            break;
          case "github_update":
            setLog((prev) => [...prev, { role: "system", text: data.text }].slice(-5));
            break;
          case "portfolio_update":
            setPortfolio(data.portfolio);
            break;
          case "calendar_update":
            setCalendarEvents(data.events);
            break;
          case "github_prs_update":
            setGithubRepos(data.repos);
            break;
          case "weather_update":
            setWeather(data.weather);
            break;
          case "news_update":
            setNewsHeadlines(data.headlines);
            setNewsPoints(data.points || []);
            break;
          default:
            break;
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [refreshAllPanels]);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await (await fetch(API("/api/status"))).json());
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
    setLog((prev) => [...prev, { role: "user", text: prompt }].slice(-5));
    try {
      await fetch(API("/api/ask"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
    } catch {
      setTicker("BACKEND UNREACHABLE");
    }
  }, []);

  const setMorningScoreRemote = useCallback(async (score) => {
    setMorningScore(score);
    try {
      await fetch(API("/api/morning-score"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score }),
      });
    } catch {
      /* optimistic update stands even if the write fails */
    }
  }, []);

  const fetchSparkline = useCallback(async (symbol) => {
    try {
      const res = await fetch(API(`/api/portfolio/sparkline/${encodeURIComponent(symbol)}`));
      const data = await res.json();
      return data.values || [];
    } catch {
      return [];
    }
  }, []);

  const fetchWeatherForecast = useCallback(async () => {
    try {
      const res = await fetch(API("/api/weather/forecast"));
      const data = await res.json();
      return data.forecast;
    } catch {
      return null;
    }
  }, []);

  const fetchHeadlineSummary = useCallback(async (headline) => {
    try {
      const res = await fetch(API(`/api/news/summary?headline=${encodeURIComponent(headline)}`));
      return await res.json();
    } catch {
      return { error: "Zusammenfassung konnte nicht geladen werden." };
    }
  }, []);

  return {
    connected,
    state,
    log,
    status,
    ticker,
    ask,
    portfolio,
    calendarEvents,
    githubRepos,
    weather,
    newsHeadlines,
    newsPoints,
    morningScore,
    setMorningScore: setMorningScoreRemote,
    fetchSparkline,
    fetchWeatherForecast,
    fetchHeadlineSummary,
  };
}
