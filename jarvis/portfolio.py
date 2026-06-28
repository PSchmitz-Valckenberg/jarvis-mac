"""Portfolio polling via IBKR's Flex Web Service — no TWS/IB Gateway/local
session required, just periodic HTTPS calls (see ibkr_flex.py).

The trade-off for not needing a live broker session is that Flex reports
are generated on demand, not streamed — so "day change" here isn't IBKR's
own intraday P&L, it's computed by comparing each new snapshot against the
previous cached one (both for the total and per-position), which is the
only data we actually have on this poll interval.

Every successful poll is cached to SQLite (current snapshot + a
per-symbol value history for sparklines) so the dashboard still has
something to show — clearly marked as stale — when a poll fails.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .fx import fetch_rate
from .ibkr_flex import FlexError, fetch_statement_xml, parse_positions

BASE_CURRENCY = "EUR"


class PortfolioService:
    def __init__(
        self,
        db_path: str,
        flex_token: str,
        flex_query_id: str,
        poll_interval_minutes: int,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.db_path = db_path
        self.flex_token = flex_token
        self.flex_query_id = flex_query_id
        self.poll_interval_seconds = max(1, poll_interval_minutes) * 60
        self.on_update = on_update

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._init_db()
        self._latest: dict[str, Any] = self._load_cache() or {
            "connected": False,
            "positions": [],
            "total_value": None,
            "day_pnl_pct": None,
            "currency": BASE_CURRENCY,
            "updated_at": None,
        }

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS portfolio_cache (id INTEGER PRIMARY KEY CHECK (id = 1), "
            "data TEXT NOT NULL, updated_at REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS portfolio_history (symbol TEXT NOT NULL, "
            "value REAL NOT NULL, recorded_at REAL NOT NULL)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_portfolio_history_symbol_time "
            "ON portfolio_history (symbol, recorded_at)"
        )
        conn.commit()
        conn.close()

    def _load_cache(self) -> dict[str, Any] | None:
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT data FROM portfolio_cache WHERE id = 1").fetchone()
            conn.close()
        except Exception:  # noqa: BLE001 — degrade to "no cache" rather than crash startup
            return None
        if row is None:
            return None
        try:
            data = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        data["connected"] = False  # this is the cached/stale flavor by definition
        return data

    def _save_cache(self, data: dict[str, Any]) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO portfolio_cache (id, data, updated_at) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                (json.dumps(data), time.time()),
            )
            now = time.time()
            conn.executemany(
                "INSERT INTO portfolio_history (symbol, value, recorded_at) VALUES (?, ?, ?)",
                [(pos["symbol"], pos["market_value"], now) for pos in data.get("positions", [])],
            )
            conn.commit()
            conn.close()
        except Exception:  # noqa: BLE001 — caching failures shouldn't break a live poll
            pass

    def _last_value(self, symbol: str | None = None) -> float | None:
        """Most recent cached value for a symbol, or the total portfolio
        value if symbol is None — the baseline "day change" is computed
        against, since Flex gives us snapshots, not a live P&L feed."""
        try:
            conn = sqlite3.connect(self.db_path)
            if symbol is None:
                row = conn.execute(
                    "SELECT data FROM portfolio_cache WHERE id = 1"
                ).fetchone()
                conn.close()
                if row is None:
                    return None
                return json.loads(row[0]).get("total_value")
            row = conn.execute(
                "SELECT value FROM portfolio_history WHERE symbol = ? ORDER BY recorded_at DESC LIMIT 1",
                (symbol,),
            ).fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:  # noqa: BLE001
            return None

    def sparkline(self, symbol: str, days: int = 7) -> list[float]:
        try:
            conn = sqlite3.connect(self.db_path)
            cutoff = time.time() - days * 86400
            rows = conn.execute(
                "SELECT value FROM portfolio_history WHERE symbol = ? AND recorded_at >= ? "
                "ORDER BY recorded_at ASC",
                (symbol, cutoff),
            ).fetchall()
            conn.close()
        except Exception:  # noqa: BLE001
            return []
        return [r[0] for r in rows]

    def latest(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            data = self._fetch_once()
            with self._lock:
                self._latest = data
            if data.get("connected"):
                self._save_cache(data)
            if self.on_update is not None:
                self.on_update(data)
            self._stop.wait(self.poll_interval_seconds)

    def _fetch_once(self) -> dict[str, Any]:
        if not self.flex_token or not self.flex_query_id:
            stale = self._load_cache() or self.latest()
            stale["connected"] = False
            stale["error"] = "IBKR_FLEX_TOKEN/IBKR_FLEX_QUERY_ID not configured"
            return stale
        try:
            xml_text = fetch_statement_xml(self.flex_token, self.flex_query_id)
            raw_positions = parse_positions(xml_text)
            return self._build_payload(raw_positions)
        except (FlexError, Exception) as exc:  # noqa: BLE001 — a failed poll degrades to cache, never crashes
            stale = self._load_cache() or self.latest()
            stale["connected"] = False
            stale["error"] = str(exc)
            return stale

    def _build_payload(self, raw_positions: list[dict[str, Any]]) -> dict[str, Any]:
        positions = []
        total_value = 0.0
        for raw in raw_positions:
            # IBKR includes its own fxRateToBase on every position when that
            # field is selected in the Flex Query — prefer it (it's exactly
            # the rate IBKR itself used to value the position) and only fall
            # back to an independent FX lookup if it's missing.
            rate = raw.get("fx_rate_to_base")
            if rate is None:
                rate = fetch_rate(raw.get("currency", BASE_CURRENCY), BASE_CURRENCY)
            rate = rate if rate is not None else 1.0  # best-effort: unconverted rather than dropped

            market_value = raw.get("market_value", 0.0) * rate
            avg_cost = raw.get("avg_cost", 0.0) * rate
            unrealized_pnl = raw.get("unrealized_pnl", 0.0) * rate
            total_value += market_value

            previous_value = self._last_value(raw["symbol"])
            day_pnl = (market_value - previous_value) if previous_value is not None else None
            day_change_pct = (day_pnl / previous_value * 100) if previous_value else None

            positions.append(
                {
                    "symbol": raw["symbol"],
                    "position": raw.get("position", 0.0),
                    "market_value": market_value,
                    "avg_cost": avg_cost,
                    "unrealized_pnl": unrealized_pnl,
                    "day_pnl": day_pnl,
                    "day_change_pct": day_change_pct,
                    "currency": BASE_CURRENCY,
                }
            )

        previous_total = self._last_value()
        day_pnl_total = (total_value - previous_total) if previous_total is not None else None
        day_pnl_pct = (day_pnl_total / previous_total * 100) if previous_total else None

        return {
            "connected": True,
            "currency": BASE_CURRENCY,
            "positions": positions,
            "total_value": total_value,
            "day_pnl": day_pnl_total,
            "day_pnl_pct": day_pnl_pct,
            "updated_at": time.time(),
        }
