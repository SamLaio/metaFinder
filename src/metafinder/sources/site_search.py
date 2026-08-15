from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from metafinder.models import BookCandidate, BookMetadata
from metafinder.normalize import clean_title, normalize_isbn, split_people
from metafinder.source_rules import BOOK_URL_PATTERNS as BOOK_URL_PATTERN_TEXTS
from metafinder.sources.web_search import USER_AGENT


@dataclass(frozen=True)
class SiteSearchTemplate:
    name: str
    url_template: str


SITE_SEARCHES = [
    SiteSearchTemplate("博客來", "https://search.books.com.tw/search/query/key/{query}/cat/all"),
    SiteSearchTemplate("Readmoo", "https://readmoo.com/search/keyword?q={query}"),
    SiteSearchTemplate("Pubu", "https://www.pubu.com.tw/search?q={query}"),
    SiteSearchTemplate("誠品線上", "https://www.eslite.com/Search?keyword={query}"),
]

BOOK_URL_PATTERNS = [re.compile(pattern) for pattern in BOOK_URL_PATTERN_TEXTS]


def search_source_sites(query: str, limit: int = 12, timeout: float = 15.0) -> list[str]:
    urls: list[str] = []
    for template in SITE_SEARCHES:
        search_url = template.url_template.format(query=quote_plus(query))
        try:
            response = requests.get(search_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(response.text, "lxml")
        for link in soup.find_all("a", href=True):
            href = urljoin(response.url, link["href"])
            href = _strip_tracking(href)
            if _matches_book_url(href) and href not in urls:
                urls.append(href)
            if len(urls) >= limit:
                return urls
    return urls


def search_source_candidates(query: str, limit: int = 3, timeout: float = 15.0, expected_isbn: str | None = None) -> list[BookCandidate]:
    candidates: list[BookCandidate] = []
    search_url = SITE_SEARCHES[0].url_template.format(query=quote_plus(query))
    try:
        response = requests.get(search_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return candidates
    soup = BeautifulSoup(response.text, "lxml")
    count = _books_result_count(soup)
    if count != 1:
        return candidates
    for item in soup.select("[id^='prod-itemlist-']"):
        title_link = item.select_one("h4 a[title]")
        if not title_link:
            continue
        href = urljoin(response.url, title_link.get("href", ""))
        href = _strip_tracking(href)
        if not _matches_book_url(href):
            continue
        title = clean_title(title_link.get("title") or title_link.get_text(" ", strip=True))
        authors = split_people([a.get("title") or a.get_text(" ", strip=True) for a in item.select(".author a")])
        image = item.select_one("img[data-src], img[src]")
        cover_url = urljoin(response.url, image.get("data-src") or image.get("src")) if image else None
        metadata = BookMetadata(title=title, authors=authors, isbn=normalize_isbn(expected_isbn), cover_url=cover_url)
        candidates.append(
            BookCandidate(
                source_name="博客來",
                source_url=href,
                source_kind="store",
                metadata=metadata,
                score=float(30 + metadata.completeness_score() * 4),
                evidence=["books-search-result"],
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def _matches_book_url(url: str) -> bool:
    return any(pattern.match(url) for pattern in BOOK_URL_PATTERNS)


def _strip_tracking(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("books.com.tw"):
        redirect_match = re.search(r"/redirect/move/.+/item/([A-Za-z0-9]+)/", url)
        if redirect_match:
            return f"https://www.books.com.tw/products/{redirect_match.group(1)}"
        match = re.search(r"(https?://(?:www\.)?books\.com\.tw/products/[A-Za-z0-9]+)", url)
        if match:
            return match.group(1)
    if parsed.fragment:
        return url.split("#", 1)[0]
    return url


def _books_result_count(soup: BeautifulSoup) -> int | None:
    node = soup.select_one(".search_results p")
    if not node:
        return None
    match = re.search(r"搜尋結果共\s*([0-9]+)\s*筆", node.get_text(" ", strip=True))
    return int(match.group(1)) if match else None
