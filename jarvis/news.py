"""RSS headline fetcher for the dashboard's news ticker."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

NEWS_TIMEOUT_SECONDS = 10


def fetch_headlines(rss_url: str, limit: int = 12) -> list[str]:
    try:
        response = requests.get(rss_url, timeout=NEWS_TIMEOUT_SECONDS)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception:  # noqa: BLE001 — news is a nice-to-have, never raise on it
        return []

    titles = (item.findtext("title") for item in root.findall("./channel/item"))
    return [title.strip() for title in titles if title and title.strip()][:limit]
