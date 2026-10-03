from __future__ import annotations

from collections.abc import Iterable

import httpx

from deep_research.models import SearchHit
from deep_research.urls import DEFAULT_DENYLIST, canonical_url, is_denied


class SearchError(Exception):
    pass


class SearxngSearch:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client,
        denylist: Iterable[str] = DEFAULT_DENYLIST,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.denylist = tuple(denylist)

    def __call__(self, query: str, max_results: int) -> list[SearchHit]:
        try:
            resp = self.client.get(
                f"{self.base_url}/search",
                params={"q": query, "format": "json", "safesearch": 0},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise SearchError(f"search request failed: {exc}") from exc
        if resp.status_code != 200:
            raise SearchError(f"search returned HTTP {resp.status_code}")
        try:
            data = resp.json()
            results = data["results"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SearchError("search returned invalid JSON") from exc
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for r in results:
            url = str(r.get("url", ""))
            if not url.startswith(("http://", "https://")) or is_denied(url, self.denylist):
                continue
            canon = canonical_url(url)
            if canon in seen:
                continue
            seen.add(canon)
            hits.append(
                SearchHit(
                    url=url,
                    canonical_url=canon,
                    title=str(r.get("title") or ""),
                    snippet=str(r.get("content") or ""),
                    engine=str(r.get("engine") or ""),
                )
            )
            if len(hits) >= max_results:
                break
        return hits
