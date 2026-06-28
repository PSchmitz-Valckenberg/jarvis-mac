"""IBKR Flex Web Service — pulls portfolio snapshots via plain HTTPS using a
Flex Query token, no TWS/IB Gateway/local session required. The trade-off:
IBKR generates these reports on demand rather than streaming live data, so
this is a periodic snapshot (poll interval is a config setting, not
real-time) — see PortfolioService for how that's smoothed into a "day
change" by comparing against the previous cached snapshot instead of
relying on IBKR's own intraday P&L fields.

Setup (done once, in IBKR's Client Portal — see README "IBKR setup"):
  Performance & Reports -> Flex Queries -> create an "Open Positions" query
  with at least: Symbol, CurrencyPrimary, Position, PositionValue,
  CostBasisPrice. Then Settings -> Flex Web Service -> generate a token.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

SEND_REQUEST_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest"
REQUEST_TIMEOUT_SECONDS = 20
POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 12  # ~1 minute total — IBKR usually generates within seconds
STATEMENT_IN_PROGRESS_ERROR_CODE = "1019"


class FlexError(Exception):
    """Raised when IBKR's Flex Web Service rejects the request or never finishes generating."""


def fetch_statement_xml(token: str, query_id: str) -> str:
    """Runs the two-step SendRequest/GetStatement dance and returns the raw
    <FlexQueryResponse> XML once IBKR finishes generating it."""
    send_response = requests.get(
        SEND_REQUEST_URL, params={"t": token, "q": query_id, "v": "3"}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    send_response.raise_for_status()
    send_root = ET.fromstring(send_response.content)

    if send_root.findtext("Status") != "Success":
        raise FlexError(
            f"SendRequest failed ({send_root.findtext('ErrorCode')}): {send_root.findtext('ErrorMessage')}"
        )
    reference_code = send_root.findtext("ReferenceCode")
    statement_url = send_root.findtext("Url")
    if not reference_code or not statement_url:
        raise FlexError("SendRequest succeeded but didn't return a reference code/URL")

    for _ in range(MAX_POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL_SECONDS)
        get_response = requests.get(
            statement_url, params={"q": reference_code, "t": token, "v": "3"}, timeout=REQUEST_TIMEOUT_SECONDS
        )
        get_response.raise_for_status()
        text = get_response.text
        if not text.lstrip().startswith("<FlexStatementResponse"):
            return text  # the actual <FlexQueryResponse> report

        error_root = ET.fromstring(get_response.content)
        error_code = error_root.findtext("ErrorCode")
        if error_code == STATEMENT_IN_PROGRESS_ERROR_CODE:
            continue  # still generating — keep polling
        raise FlexError(f"GetStatement failed ({error_code}): {error_root.findtext('ErrorMessage')}")

    raise FlexError("Timed out waiting for IBKR to generate the Flex statement")


def parse_positions(xml_text: str) -> list[dict[str, Any]]:
    """Extracts <OpenPosition> rows. Field availability depends on which
    columns were selected when the Flex Query was created — anything
    missing is left out rather than guessed at."""
    root = ET.fromstring(xml_text)
    positions = []
    for element in root.iter("OpenPosition"):
        symbol = element.get("symbol")
        if not symbol:
            continue
        position: dict[str, Any] = {"symbol": symbol, "currency": element.get("currency") or "USD"}
        for key, attr in (
            ("position", "position"),
            ("market_value", "positionValue"),
            ("avg_cost", "costBasisPrice"),
            ("unrealized_pnl", "fifoPnlUnrealized"),
            ("fx_rate_to_base", "fxRateToBase"),
        ):
            value = element.get(attr)
            if value is not None:
                try:
                    position[key] = float(value)
                except ValueError:
                    pass
        positions.append(position)
    return positions
