from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str | None = None


def _unwrap_duckduckgo_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com"):
        qs = parse_qs(parsed.query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
    return url


def search_web(query: str, limit: int = 10, timeout: float = 15.0) -> list[SearchResult]:
    """Search the web through public HTML result pages.

    This avoids requiring API keys. Search engines change markup from time to
    time, so callers should treat an empty result as a recoverable condition.
    """

    results = _search_duckduckgo(query, limit=limit, timeout=timeout)
    if len(results) < limit:
        for result in _search_bing(query, limit=limit, timeout=timeout):
            if result.url not in {r.url for r in results}:
                results.append(result)
            if len(results) >= limit:
                break
    return results[:limit]


def _search_duckduckgo(query: str, limit: int, timeout: float) -> list[SearchResult]:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    results: list[SearchResult] = []
    for item in soup.select(".result"):
        link = item.select_one(".result__a")
        if not link:
            continue
        href = link.get("href")
        if not href:
            continue
        snippet_el = item.select_one(".result__snippet")
        result = SearchResult(
            title=link.get_text(" ", strip=True),
            url=_unwrap_duckduckgo_url(href),
            snippet=snippet_el.get_text(" ", strip=True) if snippet_el else None,
        )
        if result.url not in {r.url for r in results}:
            results.append(result)
        if len(results) >= limit:
            break
    return results


def _search_bing(query: str, limit: int, timeout: float) -> list[SearchResult]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    results: list[SearchResult] = []
    for item in soup.select("li.b_algo"):
        link = item.select_one("h2 a")
        if not link or not link.get("href"):
            continue
        snippet = item.select_one(".b_caption p")
        result = SearchResult(
            title=link.get_text(" ", strip=True),
            url=link["href"],
            snippet=snippet.get_text(" ", strip=True) if snippet else None,
        )
        if result.url not in {r.url for r in results}:
            results.append(result)
        if len(results) >= limit:
            break
    return results
