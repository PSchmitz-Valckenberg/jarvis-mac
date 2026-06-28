import { useJarvisDashboard } from "./hooks/useJarvisDashboard.js";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import TopBar from "./components/TopBar.jsx";
import LeftColumn from "./components/LeftColumn.jsx";
import CenterColumn from "./components/CenterColumn.jsx";
import RightColumn from "./components/RightColumn.jsx";
import BottomBar from "./components/BottomBar.jsx";

export default function App() {
  const {
    connected,
    state,
    log,
    status,
    ticker,
    portfolio,
    calendarEvents,
    githubRepos,
    weather,
    newsHeadlines,
    newsPoints,
    morningScore,
    setMorningScore,
    fetchWeatherForecast,
    fetchHeadlineSummary,
  } = useJarvisDashboard();

  return (
    <div className="app-shell">
      <TopBar connected={connected} />
      <div className="main-grid">
        <ErrorBoundary>
          <LeftColumn state={state} ticker={ticker} log={log} status={status} portfolio={portfolio} />
        </ErrorBoundary>
        <ErrorBoundary>
          <CenterColumn
            newsHeadlines={newsHeadlines}
            newsPoints={newsPoints}
            fetchHeadlineSummary={fetchHeadlineSummary}
          />
        </ErrorBoundary>
        <ErrorBoundary>
          <RightColumn
            calendarEvents={calendarEvents}
            githubRepos={githubRepos}
            weather={weather}
            fetchWeatherForecast={fetchWeatherForecast}
            morningScore={morningScore}
            setMorningScore={setMorningScore}
          />
        </ErrorBoundary>
      </div>
      <ErrorBoundary>
        <BottomBar status={status} />
      </ErrorBoundary>
    </div>
  );
}
