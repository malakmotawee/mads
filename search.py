"""Free web search through the ddgs library (no API key)."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    query: str


class WebSearch:
    def __init__(self, max_results: int = 8, pause_seconds: float = 1.5):
        self.max_results = max_results
        self.pause_seconds = pause_seconds

    def search(self, query: str) -> list[SearchResult]:
        from ddgs import DDGS

        for attempt in range(2):
            try:
                rows = DDGS().text(query, max_results=self.max_results)
                time.sleep(self.pause_seconds)
                return [
                    SearchResult(
                        title=(r.get("title") or "").strip(),
                        url=(r.get("href") or r.get("url") or "").strip(),
                        snippet=(r.get("body") or "").strip(),
                        query=query,
                    )
                    for r in rows
                    if (r.get("href") or r.get("url") or "").startswith("http")
                ]
            except Exception as exc:  # ddgs raises several exception types
                print(f"[search] '{query}' failed (attempt {attempt + 1}): {exc}", file=sys.stderr)
                time.sleep(self.pause_seconds * 3)
        return []
