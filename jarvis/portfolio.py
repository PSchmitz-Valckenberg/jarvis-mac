"""IBKR portfolio polling via ib_insync.

Runs its own background thread with a dedicated asyncio loop — ib_insync's
synchronous API (`ib.connect()`, `ib.sleep()`) needs an event loop bound to
the calling thread, and we don't want portfolio polling sharing the
FastAPI/uvicorn loop or blocking the hotkey/voice pipeline.

Every successful poll is cached to SQLite (current snapshot + a
per-symbol value history for sparklines) so the dashboard still has
something to show — clearly marked as stale — when TWS isn't reachable.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

POLL_INTERVAL_SECONDS = 60
PNL_SETTLE_SECONDS = 1.5


class PortfolioService:
    def __init__(
        self,
        db_path: str,
        host: str,
        port: int,
        client_id: int,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.db_path = db_path
        self.host = host
        self.port = port
        self.client_id = client_id
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
        asyncio.set_event_loop(asyncio.new_event_loop())
        while not self._stop.is_set():
            data = self._fetch_once()
            with self._lock:
                self._latest = data
            if data.get("connected"):
                self._save_cache(data)
            if self.on_update is not None:
                self.on_update(data)
            self._stop.wait(POLL_INTERVAL_SECONDS)

    def _fetch_once(self) -> dict[str, Any]:
        try:
            from ib_insync import IB
        except ImportError:
            stale = self._load_cache() or self.latest()
            stale["connected"] = False
            stale["error"] = "ib_insync not installed"
            return stale

        ib = IB()
        try:
            ib.connect(self.host, self.port, clientId=self.client_id, timeout=4)
            return self._build_payload(ib)
        except Exception as exc:  # noqa: BLE001 — TWS down/unreachable is expected, not exceptional
            stale = self._load_cache() or self.latest()
            stale["connected"] = False
            stale["error"] = str(exc)
            return stale
        finally:
            if ib.isConnected():
                ib.disconnect()

    def _build_payload(self, ib: Any) -> dict[str, Any]:
        accounts = ib.managedAccounts()
        account = accounts[0] if accounts else ""

        portfolio_items = ib.portfolio()

        # IBKR reports each position's marketValue/unrealizedPNL in *that
        # contract's own currency* (e.g. USD for NVDA, EUR for an EU-listed
        # ETF) — summing those raw numbers across positions is meaningless
        # once more than one currency is involved. $LEDGER-ExchangeRate
        # gives the live rate from each currency into the account's base
        # currency, which accountSummary's NetLiquidation is already in.
        base_currency = "EUR"
        net_liq_total: float | None = None
        fx_rates: dict[str, float] = {}
        try:
            for value in ib.accountValues(account):
                if value.tag == "$LEDGER-ExchangeRate" and value.currency != "BASE":
                    fx_rates[value.currency] = float(value.value)
            net_liq_row = next((v for v in ib.accountSummary(account) if v.tag == "NetLiquidation"), None)
            if net_liq_row is not None:
                base_currency = net_liq_row.currency
                net_liq_total = float(net_liq_row.value)
        except Exception:  # noqa: BLE001 — fall back to base_currency="EUR", rate 1.0 below
            pass

        # Account- and position-level *daily* P&L needs a live subscription
        # (portfolio().unrealizedPNL is lifetime-since-open, not daily) — give
        # the callbacks a moment to populate before reading them back.
        daily_pnl_total: float | None = None
        daily_pnl_by_con_id: dict[int, float] = {}
        try:
            ib.reqPnL(account)
            for item in portfolio_items:
                ib.reqPnLSingle(account, "", item.contract.conId)
            ib.sleep(PNL_SETTLE_SECONDS)
            account_pnl = ib.pnl()
            if account_pnl:
                daily_pnl_total = float(account_pnl[0].dailyPnL)
            for single in ib.pnlSingle:
                if single.dailyPnL is not None:
                    daily_pnl_by_con_id[single.conId] = float(single.dailyPnL)
        except Exception:  # noqa: BLE001 — fall back to unrealizedPNL-based estimates below
            pass

        positions = []
        total_value_from_positions = 0.0
        for item in portfolio_items:
            currency = item.contract.currency
            fx_rate = 1.0 if currency == base_currency else fx_rates.get(currency, 1.0)

            market_value = float(item.marketValue) * fx_rate
            unrealized_pnl = float(item.unrealizedPNL) * fx_rate
            avg_cost = float(item.averageCost) * fx_rate
            total_value_from_positions += market_value

            # TWS sometimes refuses reqPnLSingle (e.g. in Read-Only API mode)
            # — when that happens, leave day_pnl/day_change_pct as None rather
            # than silently substituting lifetime unrealizedPNL, which would
            # masquerade as a daily figure and can be wildly wrong (a position
            # held for months showing as "+47% today").
            raw_daily_pnl = daily_pnl_by_con_id.get(item.contract.conId)
            daily_pnl = raw_daily_pnl * fx_rate if raw_daily_pnl is not None else None
            day_base_value = market_value - daily_pnl if daily_pnl is not None else None
            day_change_pct = (daily_pnl / day_base_value * 100) if day_base_value else None

            positions.append(
                {
                    "symbol": item.contract.symbol,
                    "position": float(item.position),
                    "market_value": market_value,
                    "avg_cost": avg_cost,
                    "unrealized_pnl": unrealized_pnl,
                    "day_pnl": daily_pnl,
                    "day_change_pct": day_change_pct,
                    "currency": base_currency,
                }
            )

        if daily_pnl_total is None:
            known_daily_pnls = [p["day_pnl"] for p in positions if p["day_pnl"] is not None]
            daily_pnl_total = sum(known_daily_pnls) if known_daily_pnls else None
        # accountSummary's NetLiquidation is IBKR's own authoritative total in
        # the base currency (matches what TWS/the web portal show) — prefer
        # it over summing converted positions, which omits cash and any
        # rounding in our own FX conversion above.
        total_value = net_liq_total if net_liq_total is not None else total_value_from_positions
        base_total = total_value - daily_pnl_total if daily_pnl_total is not None else None
        day_pnl_pct = (daily_pnl_total / base_total * 100) if base_total else None

        return {
            "connected": True,
            "account": account,
            "currency": base_currency,
            "positions": positions,
            "total_value": total_value,
            "day_pnl": daily_pnl_total,
            "day_pnl_pct": day_pnl_pct,
            "updated_at": time.time(),
        }
