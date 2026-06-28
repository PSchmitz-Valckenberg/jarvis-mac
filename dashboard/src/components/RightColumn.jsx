import { useState } from "react";

const WEATHER_ICONS = {
  0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
  45: "🌫", 48: "🌫",
  51: "🌦", 53: "🌦", 55: "🌦",
  61: "🌧", 63: "🌧", 65: "🌧",
  71: "🌨", 73: "🌨", 75: "🌨",
  80: "🌦", 81: "🌧", 82: "🌧",
  95: "⛈", 96: "⛈", 99: "⛈",
};

function CalendarPanel({ events }) {
  return (
    <div className="panel" style={{ flex: 1 }}>
      <p className="panel__title">
        <span>HEUTE — TERMINE</span>
        <span className="accent">{events.length}</span>
      </p>
      {events.length === 0 ? (
        <div className="empty-hint">Keine Termine heute.</div>
      ) : (
        <ul className="list-widget">
          {events.map((e, i) => (
            <li key={i}>
              <span>{e.title}</span>
              <span style={{ color: "var(--text-dim)" }}>{e.start}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function GithubPanel({ repos }) {
  const entries = Object.entries(repos || {});
  const totalOpen = entries.reduce((sum, [, prs]) => sum + prs.length, 0);
  return (
    <div className="panel" style={{ flex: 1 }}>
      <p className="panel__title">
        <span>GITHUB — OFFENE PRs</span>
        <span className="accent">{totalOpen}</span>
      </p>
      {entries.length === 0 ? (
        <div className="empty-hint">Keine Repos konfiguriert.</div>
      ) : (
        <ul className="list-widget">
          {entries.flatMap(([repo, prs]) =>
            prs.length === 0
              ? [
                  <li key={repo}>
                    <span style={{ color: "var(--text-dim)" }}>{repo}</span>
                    <span style={{ color: "var(--text-dim)" }}>—</span>
                  </li>,
                ]
              : prs.map((pr) => (
                  <li key={`${repo}#${pr.number}`}>
                    <span>#{pr.number} {pr.title}</span>
                    <span style={{ color: "var(--orange)" }}>{repo}</span>
                  </li>
                ))
          )}
        </ul>
      )}
    </div>
  );
}

function WeatherPanel({ weather, fetchForecast }) {
  const [expanded, setExpanded] = useState(false);
  const [forecast, setForecast] = useState(null);

  const toggle = () => {
    if (!expanded && !forecast) {
      fetchForecast().then(setForecast);
    }
    setExpanded((e) => !e);
  };

  return (
    <div className="panel" onClick={toggle} style={{ cursor: "pointer" }}>
      <p className="panel__title">
        <span>WETTER — MÜNCHEN</span>
        <span className="accent">{expanded ? "WENIGER" : "MEHR"}</span>
      </p>
      {weather ? (
        <div className="weather-row">
          <span style={{ fontSize: 28 }}>{WEATHER_ICONS[weather.weathercode] || "🌡"}</span>
          <span className="weather-row__temp">{Math.round(weather.temperature)}°C</span>
          <span style={{ color: "var(--text-dim)" }}>Wind {weather.windspeed} km/h</span>
        </div>
      ) : (
        <div className="empty-hint">Keine Wetterdaten.</div>
      )}

      {expanded && (
        <div onClick={(e) => e.stopPropagation()}>
          {!forecast && <div className="empty-hint">Lade Vorhersage…</div>}
          {forecast && (
            <>
              <div className="forecast-hourly">
                {forecast.hourly.map((h, i) => (
                  <div key={i} className="forecast-hourly__item">
                    <div>{h.time.slice(11, 16)}</div>
                    <div>{WEATHER_ICONS[h.weathercode] || "🌡"}</div>
                    <div className="forecast-hourly__temp">{Math.round(h.temperature)}°</div>
                  </div>
                ))}
              </div>
              <div className="forecast-daily">
                {forecast.daily.map((d, i) => (
                  <div key={i} className="forecast-daily__row">
                    <span>{d.date}</span>
                    <span>{WEATHER_ICONS[d.weathercode] || "🌡"}</span>
                    <span>
                      {Math.round(d.temp_min)}° / {Math.round(d.temp_max)}°
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function MorningScorePanel({ score, setScore }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(score ?? 5);

  return (
    <div className="panel">
      <p className="panel__title">
        <span>MORGEN-ENERGIE</span>
        <span className="accent" style={{ cursor: "pointer" }} onClick={() => setEditing((e) => !e)}>
          {editing ? "FERTIG" : "ÄNDERN"}
        </span>
      </p>
      {editing ? (
        <div className="morning-score">
          <div className="morning-score__value">{draft}/10</div>
          <input
            type="range"
            min="1"
            max="10"
            value={draft}
            onChange={(e) => {
              const v = Number(e.target.value);
              setDraft(v);
              setScore(v);
            }}
          />
        </div>
      ) : (
        <div className="morning-score__value">{score ?? "—"}/10</div>
      )}
    </div>
  );
}

export default function RightColumn({
  calendarEvents,
  githubRepos,
  weather,
  fetchWeatherForecast,
  morningScore,
  setMorningScore,
}) {
  return (
    <div className="column">
      <CalendarPanel events={calendarEvents} />
      <GithubPanel repos={githubRepos} />
      <WeatherPanel weather={weather} fetchForecast={fetchWeatherForecast} />
      <MorningScorePanel score={morningScore} setScore={setMorningScore} />
    </div>
  );
}
