"""Geotags and prioritizes news headlines for the dashboard's news globe.

No external geocoding API — a cheap Groq call does both the "which
country/city is this about" lookup and the priority call in one shot,
using the model's own world knowledge.
"""

from __future__ import annotations

import json
from typing import Any

from groq import Groq

from .config import config

GEO_SYSTEM_PROMPT = (
    "You tag news headlines (German or English) for a map widget. For each "
    "headline, identify the single most relevant country/city it's about and "
    "estimate its priority for someone skimming a dashboard. Respond with "
    'JSON: {"points": [{"index": <int>, "location": "<city, country>", '
    '"lat": <float>, "lon": <float>, "priority": "low"|"medium"|"high"}]}. '
    "priority=high for wars, disasters, deaths, major political upheaval; "
    "medium for notable political/economic news; low for everything else. "
    "EVERY point object MUST include its source headline's \"index\" field — "
    "never omit it. Only skip a headline entirely (no point object for it) if "
    "it has no clear geographic location. Example for 2 headlines, the second "
    'with no location: {"points": [{"index": 0, "location": "Berlin, '
    'Deutschland", "lat": 52.52, "lon": 13.40, "priority": "low"}]}. '
    "Output JSON only, no prose."
)

GEOTAG_TIMEOUT_MAX_TOKENS = 1024


def geotag_headlines(headlines: list[str]) -> list[dict[str, Any]]:
    if not headlines or not config.has_api_key:
        return []

    numbered = "\n".join(f"{i}: {headline}" for i, headline in enumerate(headlines))
    try:
        client = Groq(api_key=config.groq_api_key)
        completion = client.chat.completions.create(
            model=config.profile_extraction_model,
            messages=[
                {"role": "system", "content": GEO_SYSTEM_PROMPT},
                {"role": "user", "content": numbered},
            ],
            temperature=0,
            max_tokens=GEOTAG_TIMEOUT_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        data = json.loads(completion.choices[0].message.content or "{}")
    except Exception as exc:  # noqa: BLE001 — geotagging is a nice-to-have, never raise
        print(f"⚠️  News geotagging failed: {exc}")
        return []

    raw_points = data.get("points")
    if not isinstance(raw_points, list):
        return []

    points = []
    for position, raw in enumerate(raw_points):
        try:
            lat = float(raw["lat"])
            lon = float(raw["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        # The model occasionally drops "index" despite the prompt; falling
        # back to list position still lines up correctly as long as it
        # didn't *also* skip an earlier headline in the same response.
        try:
            index = int(raw["index"]) if raw.get("index") is not None else position
        except (TypeError, ValueError):
            index = position
        if not (0 <= index < len(headlines)):
            continue
        priority = str(raw.get("priority", "low")).lower()
        if priority not in {"low", "medium", "high"}:
            priority = "low"
        points.append(
            {
                "title": headlines[index],
                "location": str(raw.get("location", "")),
                "lat": lat,
                "lon": lon,
                "priority": priority,
            }
        )
    return points
