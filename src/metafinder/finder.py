from __future__ import annotations

from dataclasses import dataclass, field
import re
from urllib.parse import urlparse

from metafinder.models import BookCandidate
from metafinder.normalize import clean_title, normalize_isbn
from metafinder.sources import GenericPageParser, search_web
from metafinder.sources.site_search import search_source_sites


DEFAULT_SOURCE_QUERIES = [
    "site:books.com.tw",
    "site:readmoo.com",
    "site:pubu.com.tw",
    "site:kobo.com",
    "site:bookwalker.com.tw",
    "site:jjwxc.net",
    "site:m.jjwxc.net",
    "site:ching-win.com.tw",
    "site:eslite.com",
    "site:book.moc.gov.tw",
]

QUERY_HINTS = [
    "晉江文學城",
    "晋江文学城",
    "jjwxc",
]


@dataclass
class MetadataFinder:
    parser: GenericPageParser = field(default_factory=GenericPageParser)
    per_query_results: int = 5

    def search(self, query: str, limit: int = 8) -> list[BookCandidate]:
        expected_isbn = normalize_isbn(query)
        direct_url = _looks_like_url(query)
        urls = self._collect_urls(query)
        candidates: list[BookCandidate] = []
        seen: set[str] = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            try:
                candidate = self.parser.parse_url(url, query=query, expected_isbn=expected_isbn)
            except Exception as exc:
                continue
            if not candidate.metadata.title and not candidate.metadata.isbn:
                continue
            candidates.append(candidate)
        if expected_isbn:
            exact = [c for c in candidates if expected_isbn in {c.metadata.isbn, c.metadata.eisbn}]
            if exact:
                candidates = exact
        elif not direct_url:
            relevant = [c for c in candidates if _candidate_matches_query(c, query)]
            candidates = relevant
        candidates.sort(key=lambda c: (_candidate_query_rank(c, query), c.score), reverse=True)
        return candidates[:limit]

    def parse_url(self, url: str, query: str | None = None) -> BookCandidate:
        return self.parser.parse_url(url, query=query, expected_isbn=normalize_isbn(query or ""))

    def _collect_urls(self, query: str) -> list[str]:
        if _looks_like_url(query):
            return [query]
        urls = search_source_sites(query, limit=self.per_query_results * 2)
        queries = [query]
        queries.extend(f"{query} {hint}" for hint in QUERY_HINTS)
        queries.extend(f"{query} {source}" for source in DEFAULT_SOURCE_QUERIES)
        for search_query in queries:
            try:
                results = search_web(search_query, limit=self.per_query_results)
            except Exception:
                continue
            for result in results:
                if result.url not in urls and _is_probably_book_page(result.url):
                    urls.append(result.url)
        return urls


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_probably_book_page(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    blocked = {"youtube.com", "youtu.be", "facebook.com", "instagram.com", "threads.com", "bilibili.com"}
    return not any(host == domain or host.endswith("." + domain) for domain in blocked)


def _candidate_matches_query(candidate: BookCandidate, query: str) -> bool:
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", query)
        if len(token) > 1 and token.lower() not in {"isbn", "epub", "ebook", "電子書", "小說", "封面"}
    }
    if not tokens:
        return True
    haystack = " ".join(
        value
        for value in [candidate.metadata.title, *candidate.metadata.authors, candidate.metadata.publisher]
        if value
    ).lower()
    matched_tokens = [token for token in tokens if token in haystack]
    if len(tokens) >= 2:
        return _candidate_query_rank(candidate, query) > 0 or len(matched_tokens) >= 2
    return bool(matched_tokens)


def _candidate_query_rank(candidate: BookCandidate, query: str) -> int:
    """Prefer exact title+author matches over loose token matches."""

    title = (clean_title(candidate.metadata.title) or "").lower()
    core_title = _core_title(title)
    authors = " ".join(candidate.metadata.authors).lower()
    query_text = (clean_title(query) or query).lower()
    query_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", query_text)
        if len(token) > 1 and token.lower() not in {"isbn", "epub", "ebook", "電子書", "小說", "封面"}
    ]
    if not query_tokens:
        return 0

    rank = 0
    if core_title and core_title in query_text:
        rank += 30
    if core_title and any(token == core_title for token in query_tokens):
        rank += 30
    if any(author and author in query_text for author in candidate.metadata.authors):
        rank += 20
    if core_title and query_tokens and not any(token in core_title for token in query_tokens):
        rank -= 20
    return rank


def _core_title(title: str) -> str:
    match = re.search(r"《([^》]+)》", title)
    if match:
        return match.group(1).strip().lower()
    return title
