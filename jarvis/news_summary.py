"""On-demand "what/where/when + sources" summary for a single headline,
shown when the user clicks a headline in the dashboard. Two calls: Tavily
for a handful of articles covering the story, then a cheap Groq call to
condense them — both billed per click, not pre-fetched for every headline.
"""

from __future__ import annotations

import json
from typing import Any

from groq import Groq

from .config import config

MAX_SEARCH_RESULTS = 5
SUMMARY_SYSTEM_PROMPT = (
    "You summarize a news story from a handful of search results, in German. "
    'Respond with JSON only: {"what": "<2-3 sentences, what happened>", '
    '"where": "<location>", "when": "<when this happened/was reported, in '
    'relative or absolute terms>"}. Base it only on the given excerpts — if '
    "they don't agree or are too thin, say so briefly instead of guessing."
)


def summarize_headline(headline: str) -> dict[str, Any]:
    """Returns {"what", "where", "when", "sources": [{"title", "url"}]} —
    or {"error": "..."} if search/summarization isn't available right now."""
    if not config.tavily_api_key:
        return {"error": "Web-Suche ist nicht konfiguriert (TAVILY_API_KEY fehlt)."}

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=config.tavily_api_key)
        response = client.search(query=headline, max_results=MAX_SEARCH_RESULTS)
        results = response.get("results", [])
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Web-Suche fehlgeschlagen: {exc}"}

    if not results:
        return {"error": "Keine weiteren Quellen gefunden."}

    sources = [{"title": r.get("title", ""), "url": r.get("url", "")} for r in results]
    excerpts = "\n\n".join(f"{r.get('title', '')}\n{(r.get('content') or '')[:600]}" for r in results)

    if not config.has_api_key:
        return {"what": None, "where": None, "when": None, "sources": sources}

    try:
        client = Groq(api_key=config.groq_api_key)
        completion = client.chat.completions.create(
            model=config.profile_extraction_model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Headline: {headline}\n\n{excerpts}"},
            ],
            temperature=0.2,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(completion.choices[0].message.content or "{}")
    except Exception as exc:  # noqa: BLE001 — sources alone are still useful without a summary
        return {"what": None, "where": None, "when": None, "sources": sources, "error": str(exc)}

    # Despite the prompt specifying English keys, richer/longer German
    # context sometimes pulls the model into answering with German keys
    # instead ("was"/"wo"/"wann") — accept either rather than silently
    # dropping a perfectly good summary.
    return {
        "what": parsed.get("what") or parsed.get("was"),
        "where": parsed.get("where") or parsed.get("wo"),
        "when": parsed.get("when") or parsed.get("wann"),
        "sources": sources,
    }
