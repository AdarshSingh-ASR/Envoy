"""Research tools for Envoy's strategy phase."""
from __future__ import annotations

import json

from strands import tool

from ..config import TAVILY_API_KEY


@tool
def web_search(query: str, max_results: int = 4) -> str:
    """Search the web for consumer-rights regulations, company policy norms,
    and settlement benchmarks relevant to a dispute."""
    if not TAVILY_API_KEY:
        return json.dumps({
            "results": [],
            "note": "web search unavailable in this environment (no TAVILY_API_KEY); rely on general knowledge",
        })
    import httpx

    resp = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": TAVILY_API_KEY, "query": query, "max_results": max_results},
        timeout=20,
    )
    data = resp.json()
    return json.dumps([
        {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content", "")[:350]}
        for r in data.get("results", [])
    ])
