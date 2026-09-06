"""
Google Programmable Search (Custom Search JSON API) — grounding + last-resort
fallback for questions the rule-based NLU and the optional LLM can't answer.

Uses the *same* two credentials every Google Custom Search Engine setup
produces:

  GOOGLE_API_KEY  -> API key from Google Cloud Console
  GOOGLE_CSE_ID   -> the Search Engine ID (cx) from programmablesearchengine.google.com

Both are OPTIONAL, same philosophy as the rest of this app: with no key set,
`search_available()` returns False and every caller degrades gracefully to
whatever fallback it already had (LLM answer, or the "please tell me a
location" prompt).

Two ways this is used (see composer.py):
  1. Grounding — when an LLM key IS configured, the top result snippets are
     folded into the LLM prompt so answers cite real, current web content
     instead of only the model's training data.
  2. Direct fallback — when NO LLM key is configured, `answer_from_search`
     stitches the top snippets into a short, attributed answer on its own,
     plus a list of source links the frontend can render.

This is a plain REST call (no Google client library needed), so it costs
nothing extra to deploy.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("google_search")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_SEARCH_ENGINE_ID")

SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


def search_available() -> bool:
    return bool(GOOGLE_API_KEY and GOOGLE_CSE_ID)


async def web_search(query: str, num: int = 5) -> list[dict[str, Any]]:
    """Returns up to `num` results: [{title, snippet, link, source}, ...].
    Empty list on any failure or when no key is configured — callers should
    treat that the same as "no results", not as an error to surface.
    """
    if not search_available():
        return []
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": max(1, min(num, 10)),
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(SEARCH_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.info("Google Custom Search request failed: %s", exc)
        return []

    items = data.get("items") or []
    results = []
    for item in items:
        results.append({
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "link": item.get("link"),
            "source": item.get("displayLink"),
        })
    return results


async def answer_from_search(query: str, lang_name: str = "English") -> dict[str, Any] | None:
    """Direct fallback when no LLM is configured: build a short, attributed
    answer purely from Custom Search snippets. Returns None if search is
    unavailable or returned nothing usable.

    Result shape: {"text": "...", "sources": [{"title", "link", "source"}, ...]}
    """
    results = await web_search(query, num=4)
    if not results:
        return None

    lines = [r["snippet"] for r in results if r.get("snippet")]
    if not lines:
        return None

    # Keep this genuinely short and clearly attributed — this is a stitched
    # summary of search snippets, not a generated essay, so it should read
    # like one (a couple of sentences + "according to" + a source list).
    text = " ".join(lines[:2])
    top_source = results[0].get("source") or "web search"
    text = f"{text} (via {top_source} and {len(results)} other source(s) below)"

    return {
        "text": text,
        "sources": [
            {"title": r.get("title"), "link": r.get("link"), "source": r.get("source")}
            for r in results
            if r.get("link")
        ],
    }


async def grounding_snippets(query: str, num: int = 3) -> str:
    """Short block of 'Title — snippet (source)' lines to paste into an LLM
    prompt so it can ground its answer in current web content. Empty string
    when search isn't configured or returns nothing.
    """
    results = await web_search(query, num=num)
    if not results:
        return ""
    lines = [
        f"- {r.get('title')}: {r.get('snippet')} ({r.get('source')})"
        for r in results
        if r.get("snippet")
    ]
    return "\n".join(lines)
