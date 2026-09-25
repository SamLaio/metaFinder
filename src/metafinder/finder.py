from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from urllib.parse import urlparse

from metafinder.models import BookCandidate, BookMetadata
from metafinder.normalize import clean_title, normalize_isbn, to_simplified_for_search, to_traditional
from metafinder.source_rules import source_info
from metafinder.sources import GenericPageParser, search_web
from metafinder.sources.openlibrary import lookup_openlibrary_isbn
from metafinder.sources.site_search import search_source_candidates, search_source_sites


DEFAULT_SOURCE_QUERIES = [
    "site:books.com.tw",
    "site:readmoo.com",
    "site:pubu.com.tw",
    "site:kobo.com",
    "site:bookwalker.com.tw",
    "site:sanmin.com.tw",
    "site:tdtb.org/library",
    "site:cite.com.tw",
    "site:tongli.com.tw",
    "site:kingstone.com.tw",
    "site:jjwxc.net",
    "site:m.jjwxc.net",
    "site:qidian.com",
    "site:ubook.reader.qq.com",
    "site:ching-win.com.tw",
    "site:crown.com.tw",
    "site:eslite.com",
    "site:book.moc.gov.tw",
]

QUERY_HINTS = [
    "晉江文學城",
    "晋江文学城",
    "jjwxc",
    "番茄小說",
    "番茄小说",
    "fanqienovel",
]


@dataclass
class MetadataFinder:
    parser: GenericPageParser = field(default_factory=GenericPageParser)
    per_query_results: int = 5
    request_timeout: float = 3.0
    max_search_seconds: float = 12.0
    max_web_queries: int = 4

    def search(self, query: str, limit: int = 8) -> list[BookCandidate]:
        query = query.replace("\x00", " ")
        if re.fullmatch(r"[xX]+(?:[\s-]+[xX]+)*", query.strip()):
            return []
        direct_url = _looks_like_url(query)
        expected_isbn = None if direct_url else normalize_isbn(query)
        deadline = time.monotonic() + self.max_search_seconds if self.max_search_seconds > 0 else None
        candidates: list[BookCandidate] = []
        if expected_isbn:
            openlibrary = lookup_openlibrary_isbn(expected_isbn, timeout=_request_timeout(self.request_timeout, deadline))
            if openlibrary:
                candidates.append(openlibrary)
        if not direct_url:
            # 明示官方書系時，泛用書店卡可能先命中同名改編版。
            source_candidates = [] if _is_kadokawa_query(query) else search_source_candidates(
                query,
                limit=3,
                timeout=min(_request_timeout(self.request_timeout, deadline), 2.0),
                expected_isbn=expected_isbn,
            )
            candidates.extend(self._hydrate_source_candidate(source_candidates, query, expected_isbn, deadline))
            if not candidates and not expected_isbn:
                candidates.extend(self._first_matching_site_candidates(_query_variants(query)[0], expected_isbn, deadline))
                if candidates:
                    candidates.sort(key=lambda c: (_candidate_query_rank_any_variant(c, query), c.score), reverse=True)
                    return candidates[:limit]
            # Only a product detail page has enough evidence to end an ISBN
            # lookup. Search cards often carry an ISBN and cover but omit the
            # publisher, date, translators, description and tags.
            if expected_isbn and any(
                expected_isbn in {c.metadata.isbn, c.metadata.eisbn}
                and not any(item.endswith("-search-result") for item in c.evidence)
                for c in candidates
            ):
                candidates.sort(key=lambda c: (_candidate_query_rank_any_variant(c, query), c.score), reverse=True)
                return candidates[:limit]
        collection_deadline = deadline
        if deadline and not direct_url:
            collection_deadline -= min(self.request_timeout * 2, self.max_search_seconds / 3)
        urls = self._collect_urls(query, expected_isbn=expected_isbn, deadline=collection_deadline)
        seen: set[str] = set()
        parser_timeout = self.parser.timeout
        for url in urls:
            if _deadline_expired(deadline):
                break
            if url in seen:
                continue
            seen.add(url)
            try:
                if deadline:
                    self.parser.timeout = max(0.1, min(parser_timeout, self.request_timeout, _remaining_seconds(deadline)))
                candidate = self.parser.parse_url(url, query=query, expected_isbn=expected_isbn)
            except Exception as exc:
                continue
            if not candidate.metadata.title and not candidate.metadata.isbn:
                continue
            if not direct_url and not expected_isbn and _is_low_evidence_other_page(candidate):
                continue
            candidates.append(candidate)
        self.parser.timeout = parser_timeout
        if expected_isbn:
            exact = [c for c in candidates if expected_isbn in {c.metadata.isbn, c.metadata.eisbn}]
            candidates = exact
        elif not direct_url:
            relevant = [c for c in candidates if _candidate_matches_any_query_variant(c, query)]
            candidates = relevant
            if not candidates:
                candidates = self._search_result_fallback(query, limit, deadline)
        candidates = _deduplicate_candidates(candidates)
        candidates.sort(key=lambda c: (_candidate_query_rank_any_variant(c, query), c.score), reverse=True)
        return candidates[:limit]

    def _first_matching_site_candidates(
        self, query: str, expected_isbn: str | None, deadline: float | None
    ) -> list[BookCandidate]:
        """Parse a direct store hit before spending the time budget on variants."""
        if _deadline_expired(deadline):
            return []
        urls = search_source_sites(
            query,
            limit=2,
            timeout=min(_request_timeout(self.request_timeout, deadline), 2.0),
            stop_after_first_hit=True,
        )
        parser_timeout = self.parser.timeout
        try:
            for url in urls:
                if _deadline_expired(deadline):
                    break
                self.parser.timeout = max(0.1, min(parser_timeout, self.request_timeout, _remaining_seconds(deadline))) if deadline else parser_timeout
                try:
                    candidate = self.parser.parse_url(url, query=query, expected_isbn=expected_isbn)
                except Exception:
                    continue
                if candidate.metadata.title and _candidate_matches_any_query_variant(candidate, query):
                    return [candidate]
        finally:
            self.parser.timeout = parser_timeout
        return []

    def _search_result_fallback(self, query: str, limit: int, deadline: float | None) -> list[BookCandidate]:
        """Keep a matching store link visible when its product page is temporarily blocked."""
        try:
            results = search_web(query, limit=limit, timeout=max(0.1, _request_timeout(self.request_timeout, deadline)))
        except Exception:
            return []
        candidates: list[BookCandidate] = []
        for result in results:
            if not _is_probably_book_page(result.url):
                continue
            source_name, source_kind = source_info(result.url)
            if source_kind not in {"store", "publisher", "government"}:
                continue
            title = clean_title(result.title)
            candidate = BookCandidate(
                source_name=source_name,
                source_url=result.url,
                source_kind=source_kind,
                metadata=BookMetadata(title=title, description=result.snippet),
                score=18,
                evidence=["web-search-result"],
            )
            if title and _candidate_matches_any_query_variant(candidate, query):
                candidates.append(candidate)
        return candidates[:limit]

    def _hydrate_source_candidate(
        self,
        candidates: list[BookCandidate],
        query: str,
        expected_isbn: str | None,
        deadline: float | None,
    ) -> list[BookCandidate]:
        """Replace the first terse store-search result with its real product page.

        Store search result cards often contain only title and author, while the
        linked product page provides ISBN, publisher, date and tags.  Hydrating
        one result keeps the batch time budget bounded and avoids treating a
        skeletal search card as completed metadata.
        """
        if not candidates or _deadline_expired(deadline):
            return candidates
        first = candidates[0]
        # 搜尋卡片即使已有 ISBN 與封面，也不含商品詳頁的出版資料。
        is_search_result = any(item.endswith("-search-result") for item in first.evidence)
        if first.source_kind != "store" or (first.metadata.completeness_score() >= 5 and not is_search_result):
            return candidates
        parser_timeout = self.parser.timeout
        try:
            self.parser.timeout = max(0.1, min(parser_timeout, self.request_timeout, _remaining_seconds(deadline))) if deadline else min(parser_timeout, self.request_timeout)
            hydrated = self.parser.parse_url(first.source_url, query=query, expected_isbn=expected_isbn)
        except Exception:
            return candidates
        finally:
            self.parser.timeout = parser_timeout
        if not hydrated.metadata.title or not _candidate_matches_any_query_variant(hydrated, query):
            return candidates
        if hydrated.metadata.completeness_score() <= first.metadata.completeness_score():
            return candidates
        return [hydrated, *candidates[1:]]

    def parse_url(self, url: str, query: str | None = None) -> BookCandidate:
        return self.parser.parse_url(url, query=query, expected_isbn=normalize_isbn(query or ""))

    def _collect_urls(self, query: str, expected_isbn: str | None = None, deadline: float | None = None) -> list[str]:
        if _looks_like_url(query):
            return [query]
        urls: list[str] = []
        query_variants = _query_variants(query)
        query_volume = _leading_query_volume(query)
        site_variant_limit = 6 if query_volume else 4
        site_query_variants = query_variants if expected_isbn else _site_query_variants(query, query_variants, site_variant_limit)
        per_variant_limit = self.per_query_results if query_volume else self.per_query_results * 2
        source_url_cap = max(self.per_query_results * 4, 12)

        for variant in site_query_variants:
            if _deadline_expired(deadline):
                return urls
            timeout = min(_request_timeout(self.request_timeout, deadline), 2.0)
            for url in search_source_sites(
                variant,
                limit=per_variant_limit,
                timeout=timeout,
                stop_after_first_hit=bool(expected_isbn),
            ):
                if url not in urls:
                    urls.append(url)
                if len(urls) >= source_url_cap:
                    break
            if len(urls) >= source_url_cap:
                break
        queries = _web_queries(query_variants, expected_isbn=expected_isbn, max_queries=self.max_web_queries)
        for search_query in queries:
            if _deadline_expired(deadline):
                break
            try:
                results = search_web(search_query, limit=self.per_query_results, timeout=_request_timeout(self.request_timeout, deadline))
            except Exception:
                continue
            for result in results:
                if result.url not in urls and _is_probably_book_page(result.url):
                    urls.append(result.url)
        return urls


def _query_variants(query: str) -> list[str]:
    variants = []
    for value in [
        *_trailing_creator_role_variants(query),
        *_trailing_series_ordinal_variants(query),
        *_trailing_promotional_parenthetical_variants(query),
        query,
        *_trailing_parenthetical_alias_variants(query),
        *_volume_query_variants(query),
    ]:
        for candidate in [value, *_bilingual_title_order_variants(value)]:
            for orthographic in _orthographic_query_variants(candidate):
                if orthographic and orthographic not in variants:
                    variants.append(orthographic)
                traditional = to_traditional(orthographic or "")
                if traditional and traditional not in variants:
                    variants.append(traditional)
                simplified = to_simplified_for_search(orthographic or "")
                if simplified and simplified not in variants:
                    variants.append(simplified)
    return variants


def _trailing_creator_role_variants(query: str) -> list[str]:
    """Remove imported author-role suffixes that stores do not index."""
    value = re.sub(r"\s+(?:著|譯|译|繪|绘)(?:\s*[；;].*|\s*)$", "", query).strip()
    return [value] if value and value != query else []


def _trailing_promotional_parenthetical_variants(query: str) -> list[str]:
    """Remove a trailing quoted marketing blurb while retaining an author."""
    match = re.fullmatch(
        r"(.+?)\s*[（(][「『][^」』]+[」』][^()（）]*[）)](?:\s+(.+))?",
        query.strip(),
    )
    if not match:
        return []
    title, author = match.groups()
    variant = " ".join(part for part in (title.strip(), (author or "").strip()) if part)
    return [variant] if variant and variant != query else []


def _candidate_matches_any_query_variant(candidate: BookCandidate, query: str) -> bool:
    # Search variants may deliberately drop a volume marker to find stores with
    # inconsistent indexing, but that must never make another volume acceptable.
    query_volume = _query_volume(query)
    if query_volume is not None and _candidate_volume(candidate) != query_volume:
        return False
    return any(_candidate_matches_query(candidate, variant) for variant in _query_variants(query))


def _candidate_query_rank_any_variant(candidate: BookCandidate, query: str) -> int:
    return max((_candidate_query_rank(candidate, variant) for variant in _query_variants(query)), default=0)


def _trailing_parenthetical_alias_variants(query: str) -> list[str]:
    """Try the local-language name without a trailing Latin author alias."""
    value = re.sub(r"\s*[（(][A-Za-z][^()（）]*[）)]\s*$", "", query).strip()
    return [value] if value and value != query else []


def _trailing_series_ordinal_variants(query: str) -> list[str]:
    """Try a title without a trailing ``～系列之第幾冊`` marker."""
    value = re.sub(r"\s+", " ", (clean_title(query) or query or "")).strip()
    match = re.fullmatch(
        r"(.+?)\s*[～~]\s*.+?(?:系列)?之(?:第)?[0-9一二兩三四五六七八九十]+(?:\s+(.+))?",
        value,
    )
    if not match:
        return []
    title, author = match.groups()
    variant = " ".join(part for part in (title.strip(), (author or "").strip()) if part)
    return [variant] if variant and variant != value else []


def _site_query_variants(query: str, query_variants: list[str], limit: int) -> list[str]:
    if not _leading_query_volume(query):
        return query_variants[:limit]
    # Some stores recognize a volume only when it stays at the query start.
    # Keep this single literal query first, then retain the established variant order.
    variants: list[str] = [query]
    for value in _volume_query_variants(query):
        candidates = [value, *_bilingual_title_order_variants(value), to_simplified_for_search(value or "")]
        for candidate in candidates:
            for candidate in _orthographic_query_variants(candidate):
                if candidate and candidate not in variants:
                    variants.append(candidate)
    for candidate in [query, *query_variants]:
        for candidate in _orthographic_query_variants(candidate):
            if candidate and candidate not in variants:
                variants.append(candidate)
    return variants[:limit]


def _orthographic_query_variants(query: str | None) -> list[str]:
    """Try common Taiwan title glyph variants that store search treats literally."""

    value = query or ""
    if not value:
        return []
    variants = [value]
    replacements = [
        ("櫃檯", "櫃臺"),
        ("櫃檯", "櫃台"),
        ("櫃臺", "櫃檯"),
        ("櫃台", "櫃檯"),
    ]
    for old, new in replacements:
        if old in value:
            candidate = value.replace(old, new)
            if candidate not in variants:
                variants.append(candidate)
    return variants


def _volume_query_variants(query: str) -> list[str]:
    stripped, volume = _strip_leading_volume_prefix(query)
    if not stripped or volume is None:
        return []
    values = [stripped]
    number = str(volume)
    zh = _chinese_number(volume)
    if " " in stripped:
        title, author = stripped.rsplit(" ", 1)
        for marker in [number, f"{volume:02d}", f"第{number}集", f"第{zh}集", f"vol.{number}", f"({number})", f"（{number}）"]:
            sep = "" if marker.startswith(("(", "（")) else " "
            values.append(f"{title}{sep}{marker} {author}")
    else:
        for marker in [number, f"{volume:02d}", f"第{number}集", f"第{zh}集", f"vol.{number}", f"({number})", f"（{number}）"]:
            sep = "" if marker.startswith(("(", "（")) else " "
            values.append(f"{stripped}{sep}{marker}")
    return values


def _bilingual_title_order_variants(query: str | None) -> list[str]:
    """Try Chinese-title-first variants for bilingual titles imported in reverse order."""

    value = re.sub(r"\s+", " ", (query or "").replace("　", " ")).strip()
    if not value:
        return []
    tokens = value.split(" ")
    first_han = next((index for index, token in enumerate(tokens) if re.search(r"[\u4e00-\u9fff]", token)), None)
    if not first_han or first_han <= 0:
        return []
    latin = " ".join(tokens[:first_han]).strip()
    rest = tokens[first_han:]
    if not latin or not rest or not re.search(r"[A-Za-z]", latin):
        return []

    author = ""
    if len(rest) >= 2 and _looks_like_short_cjk_name(rest[-1]):
        author = rest.pop()

    marker = ""
    if len(rest) >= 2 and _looks_like_volume_marker(rest[-1]):
        marker = rest.pop()
    title = " ".join(rest).strip()
    if not title:
        return []

    variants: list[str] = []

    def add(text: str) -> None:
        text = re.sub(r"\s+", " ", text).strip()
        if text and text != value and text not in variants:
            variants.append(text)

    suffix = f" {author}" if author else ""
    if marker:
        number = _volume_number(marker)
        if number:
            for formatted in [f"{number:02d}", str(number)]:
                add(f"{title} {latin}({formatted}){suffix}")
                add(f"{title}{latin}({formatted}){suffix}")
                add(f"{title} {latin}（{formatted}）{suffix}")
                add(f"{title}{latin}（{formatted}）{suffix}")
        add(f"{title} {latin} {marker}{suffix}")
        add(f"{title}{latin} {marker}{suffix}")
    else:
        add(f"{title} {latin}{suffix}")
        add(f"{title}{latin}{suffix}")
    return variants


def _looks_like_short_cjk_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u3040-\u30ff\u3400-\u9fff々〆ヵヶA-Za-z·．・]{2,8}", value or ""))


def _looks_like_volume_marker(value: str) -> bool:
    text = (value or "").strip()
    if _volume_number(text):
        return True
    return bool(re.fullmatch(r"(?:第\s*)?[0-9０-９一二兩三四五六七八九十百]{1,4}\s*(?:集|卷|冊|部)", text))


def _strip_leading_volume_prefix(query: str) -> tuple[str | None, int | None]:
    value = re.sub(r"\s+", " ", query.replace("　", " ")).strip()
    if not value:
        return None, None
    number = r"([0-9０-９]{1,3}|[一二兩三四五六七八九十百]+)"
    patterns = [
        rf"^[（(【\[]\s*{number}\s*[）)】\]]\s*(\S.*)$",
        rf"^(?:第\s*)?{number}\s*(?:集|卷|冊|部)\s+(\S.*)$",
        rf"^{number}(?:[、:：]\s*|[.．]\s+|\s+)(\S.*)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            volume = _volume_number(match.group(1))
            stripped = match.group(2).strip()
            if volume and stripped and stripped != value:
                return stripped, volume
    return None, None


def _volume_number(value: str) -> int | float | None:
    text = value.strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,2}", text):
        return float(text)
    if text.isdigit():
        return int(text)
    table = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if text in table:
        return table[text]
    if text.startswith("十") and len(text) == 2:
        return 10 + table.get(text[1:], 0)
    if text.endswith("十") and len(text) == 2:
        return table.get(text[:1], 0) * 10
    if "十" in text and len(text) == 3:
        return table.get(text[0], 0) * 10 + table.get(text[2], 0)
    return None


def _chinese_number(value: int) -> str:
    digits = "零一二三四五六七八九"
    if 0 <= value <= 10:
        return "十" if value == 10 else digits[value]
    if value < 20:
        return "十" + digits[value % 10]
    if value < 100:
        tens, ones = divmod(value, 10)
        return digits[tens] + "十" + (digits[ones] if ones else "")
    return str(value)


def _web_queries(query_variants: list[str], expected_isbn: str | None = None, max_queries: int = 8) -> list[str]:
    queries: list[str] = []
    if expected_isbn:
        preferred_sources = [
            "site:books.com.tw",
            "site:books.com.tw/products/E",
            "site:readmoo.com",
            "site:crown.com.tw",
            "site:cite.com.tw",
            "site:eslite.com",
            "site:anobii.com",
            "site:bookrep.com.tw",
            "site:books.google.com",
            "site:ebook.nlpi.edu.tw",
        ]
        for variant in query_variants:
            queries.append(variant)
            queries.extend(f"{variant} {source}" for source in preferred_sources)
        return queries[:max_queries]
    has_kadokawa_imprint = any("カドカワBOOKS" in variant or "kadokawa" in variant.lower() for variant in query_variants)
    for variant in query_variants:
        queries.append(variant)
        # 書名明示 KADOKAWA 書系時，優先保留官方頁配額，避免被網文提示或變體耗盡。
        if has_kadokawa_imprint:
            queries.append(f"{variant} site:kadokawa.co.jp")
    if max_queries <= 4:
        # Batch mode commonly allows only two queries.  Use its remaining
        # budget on a trustworthy store instead of a niche web-novel hint.
        for variant in query_variants:
            queries.extend(f"{variant} {source}" for source in DEFAULT_SOURCE_QUERIES)
        for variant in query_variants:
            queries.extend(f"{variant} {hint}" for hint in QUERY_HINTS)
    else:
        # Keep the established hint-first ordering when callers have enough
        # budget to search both web-novel sources and general bookstores.
        for variant in query_variants:
            queries.extend(f"{variant} {hint}" for hint in QUERY_HINTS)
        for variant in query_variants:
            queries.extend(f"{variant} {source}" for source in DEFAULT_SOURCE_QUERIES)
    return queries[:max_queries]


def _remaining_seconds(deadline: float) -> float:
    return deadline - time.monotonic()


def _deadline_expired(deadline: float | None) -> bool:
    return bool(deadline is not None and _remaining_seconds(deadline) <= 0.1)


def _request_timeout(default: float, deadline: float | None) -> float:
    if deadline is None:
        return default
    return max(0.1, min(default, _remaining_seconds(deadline)))


def _is_kadokawa_query(query: str) -> bool:
    return "カドカワBOOKS" in query or "kadokawa" in query.lower()


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_probably_book_page(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    blocked = {"youtube.com", "youtu.be", "facebook.com", "instagram.com", "threads.com", "bilibili.com", "gamer.com.tw", "wikipedia.org"}
    return not any(host == domain or host.endswith("." + domain) for domain in blocked)


def _deduplicate_candidates(candidates: list[BookCandidate]) -> list[BookCandidate]:
    """Keep the richest parse when several search paths resolve to one URL."""
    unique: dict[str, BookCandidate] = {}
    for candidate in candidates:
        key = candidate.source_url.rstrip("/")
        current = unique.get(key)
        if current is None or (
            candidate.metadata.completeness_score(),
            candidate.score,
        ) > (
            current.metadata.completeness_score(),
            current.score,
        ):
            unique[key] = candidate
    return list(unique.values())


def _is_low_evidence_other_page(candidate: BookCandidate) -> bool:
    if candidate.source_kind != "other":
        return False
    meta = candidate.metadata
    return not any([meta.isbn, meta.eisbn, meta.authors, meta.publisher, meta.cover_url])


def _candidate_matches_query(candidate: BookCandidate, query: str) -> bool:
    query_volume = _query_volume(query)
    candidate_title = candidate.metadata.title or ""
    if re.search(r"[＆&]", candidate_title) and not re.search(r"[＆&]", query):
        return False
    bundle_pattern = r"套[書书]|合[輯集]|全\s*[0-9０-９一二三四五六七八九十百兩两]+\s*[冊册]"
    if (query_volume and not re.search(bundle_pattern, query)
            and re.search(bundle_pattern, candidate.metadata.title or "")):
        return False
    candidate_volume = _candidate_volume(candidate)
    if query_volume and not candidate_volume:
        return False
    if query_volume and candidate_volume and query_volume != candidate_volume:
        return False
    expected_author = _trailing_query_author(query)
    if (
        expected_author
        and "漫畫" not in query
        and "漫畫" in candidate.metadata.tags
        and any(expected_author in author and "原作" in author for author in candidate.metadata.authors)
    ):
        return False
    if (
        expected_author
        and candidate.metadata.authors
        and not _author_matches(expected_author, candidate.metadata.authors)
    ):
        return False

    query_texts = _matching_text_variants(query)
    tokens = {
        token.lower()
        for text in query_texts
        for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", text)
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
    title = _title_for_matching(candidate)
    core_title = _core_title(title)
    title_variants = _matching_text_variants(title)
    core_title_variants = _matching_text_variants(core_title)
    if _candidate_volume(candidate):
        unnumbered_title = re.sub(r"\s*0*[1-9][0-9]{0,2}\s*$", "", core_title).strip()
        core_title_variants.extend(
            value for value in _matching_text_variants(unnumbered_title)
            if value not in core_title_variants
        )
    author_matches = [
        author.lower()
        for author in candidate.metadata.authors
        if author and any(author.lower() in text for text in query_texts)
    ]
    title_tokens = [token for token in tokens if token not in set(author_matches)]
    matched_title_tokens = [
        token
        for token in title_tokens
        if any(token in text for text in [*title_variants, *core_title_variants])
    ]
    matched_non_numeric_title_tokens = [token for token in matched_title_tokens if not token.isdigit()]
    long_query_title_tokens = [token for token in title_tokens if not token.isdigit() and len(token) >= 4]
    if len(tokens) >= 2:
        if author_matches and not matched_non_numeric_title_tokens and not (core_title and any(core_title in text for text in query_texts)):
            return False
        if not author_matches and long_query_title_tokens and not any(token in matched_non_numeric_title_tokens for token in long_query_title_tokens):
            return False
        return _candidate_query_rank(candidate, query) > 0 or len(matched_tokens) >= 2
    return bool(matched_tokens)


def _trailing_query_author(query: str) -> str | None:
    value = re.sub(r"\s+", " ", (clean_title(query) or query or "")).strip()
    value = re.sub(r"\s*[（(][A-Za-z][^()（）]*[）)]\s*$", "", value).strip()
    if " " not in value:
        return None
    author = value.rsplit(" ", 1)[1].strip()
    if not author or author.isdigit():
        return None
    if re.fullmatch(r"(?:第)?[0-9一二三四五六七八九十百]+(?:集|卷|冊)?", author):
        return None
    if re.fullmatch(r"(?:全\s*[0-9一二三四五六七八九十百兩两]+\s*[冊册]|套[書书]|合[輯集])", author):
        return None
    if not re.search(r"[A-Za-z\u3400-\u9fff]", author):
        return None
    return author


def _author_matches(expected_author: str, candidate_authors: list[str]) -> bool:
    expected_variants = _matching_text_variants(expected_author)
    author_variants = [
        variant
        for author in candidate_authors
        for variant in _matching_text_variants(author)
    ]
    return any(
        expected and author and (expected in author or author in expected)
        for expected in expected_variants
        for author in author_variants
    )


def _candidate_query_rank(candidate: BookCandidate, query: str) -> int:
    """Prefer exact title+author matches over loose token matches."""

    title = _title_for_matching(candidate)
    core_title = _core_title(title)
    authors = " ".join(candidate.metadata.authors).lower()
    query_text = (clean_title(query) or query).lower()
    expected_author = _trailing_query_author(query)
    query_title = query_text
    if expected_author:
        query_title = query_title[: -len(expected_author)].strip()
    query_texts = _matching_text_variants(query_title)
    core_title_variants = _matching_text_variants(core_title)
    if _candidate_volume(candidate):
        unnumbered_title = re.sub(r"\s*0*[1-9][0-9]{0,2}\s*$", "", core_title).strip()
        core_title_variants.extend(
            value for value in _matching_text_variants(unnumbered_title)
            if value not in core_title_variants
        )
    query_tokens = [
        token.lower()
        for text in query_texts
        for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", text)
        if len(token) > 1 and token.lower() not in {"isbn", "epub", "ebook", "電子書", "小說", "封面"}
    ]
    if not query_tokens:
        return 0

    rank = 0
    query_volume = _query_volume(query)
    candidate_volume = _candidate_volume(candidate)
    if query_volume and candidate_volume:
        rank += 25 if query_volume == candidate_volume else -80
    if core_title_variants and any(core in text for core in core_title_variants for text in query_texts):
        rank += 30
    if core_title and any(token in variant for token in query_tokens for variant in core_title_variants):
        rank += 30
    if any(author and any(author in text for text in query_texts) for author in candidate.metadata.authors):
        rank += 20
    if core_title and query_tokens and not any(any(token in variant for variant in core_title_variants) for token in query_tokens):
        rank -= 20
    return rank


def _matching_text_variants(text: str | None) -> list[str]:
    value = (clean_title(text or "") or text or "")
    value = re.sub(r"\s*[（(][A-Za-z][^()（）]*[）)]\s*$", "", value).strip()
    value = value.replace("·", "．").replace("・", "．").replace("‧", "．").lower()
    variants = [value] if value else []
    for candidate in list(variants):
        for orthographic in _orthographic_query_variants(candidate):
            if orthographic and orthographic.lower() not in variants:
                variants.append(orthographic.lower())
            simplified = to_simplified_for_search(orthographic)
            if simplified and simplified.lower() not in variants:
                variants.append(simplified.lower())
    for candidate in list(variants):
        compact = re.sub(r"(?<=[\u4e00-\u9fff])\s*0*([1-9][0-9]{0,2})\s*$", r"\1", candidate)
        if compact and compact not in variants:
            variants.append(compact)
    return variants


def _leading_query_volume(query: str) -> int | None:
    _, volume = _strip_leading_volume_prefix(query)
    return volume


def _query_volume(query: str) -> int | float | None:
    leading = _leading_query_volume(query)
    if leading:
        return leading
    value = re.sub(r"\s+", " ", query.replace("　", " ")).strip()
    if not value:
        return None
    author = _trailing_query_author(value)
    title = value[: -len(author)].strip() if author else value
    title_volume = _title_volume(title)
    if title_volume is not None:
        return title_volume
    decimal_volume = re.search(r"(?<=[\u4e00-\u9fff])\s*([0-9]{1,2}\.[0-9]{1,2})(?=\s|$)", title)
    if decimal_volume:
        return _volume_number(decimal_volume.group(1))
    tokens = value.split(" ")
    for index in [len(tokens) - 1, len(tokens) - 2]:
        if index < 0:
            continue
        if index == len(tokens) - 2 and not _looks_like_short_cjk_name(tokens[-1]):
            continue
        if not re.fullmatch(r"[0-9０-９]{1,3}|[一二兩三四五六七八九十百]{1,4}", tokens[index]):
            continue
        return _volume_number(tokens[index])
    return None


def _candidate_volume(candidate: BookCandidate) -> int | float | None:
    if candidate.metadata.series_index:
        value = float(candidate.metadata.series_index)
        return int(value) if value.is_integer() else value
    return _title_volume(candidate.metadata.title or "")


def _title_volume(title: str) -> int | float | None:
    circled = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
    match = re.search(f"[{circled}]", title)
    if match:
        return circled.index(match.group(0)) + 1
    for pattern in [
        r"(?:第\s*)?([0-9０-９]{1,3}(?:\.[0-9]{1,2})?|[一二兩三四五六七八九十百]+)\s*(?:集|卷|冊|部)",
        r"(?:全集|系列)\s*([0-9０-９]{1,3}|[一二兩三四五六七八九十百]+)",
        r"(?:vol\.?|volume|no\.?)\s*([0-9０-９]{1,3})",
        r"[（(]\s*([0-9０-９]{1,3}|[一二兩三四五六七八九十百]+)\s*[）)]",
        r"(?:^|\s)([0-9０-９]{1,3}(?:\.[0-9]{1,2})?|[一二兩三四五六七八九十百]+)\s*$",
        r"(?<=[\u4e00-\u9fff])\s*0*([1-9][0-9]{0,2}(?:\.[0-9]{1,2})?)\s*$",
    ]:
        match = re.search(pattern, title, flags=re.I)
        if match:
            return _volume_number(match.group(1))
    return None


def _core_title(title: str) -> str:
    match = re.search(r"《([^》]+)》", title)
    if match:
        return match.group(1).strip().lower()
    return title


def _title_for_matching(candidate: BookCandidate) -> str:
    title = (clean_title(candidate.metadata.title) or "").lower()
    # Store subtitles often cite another work (for example, 《賈伯斯傳》作者); it is not this book's title.
    title = re.sub(r"[（(][^()（）]*《[^》]+》[^()（）]*[）)]", "", title)
    for author in candidate.metadata.authors:
        author_text = (clean_title(author) or author).lower()
        if author_text and title.endswith(f" - {author_text}"):
            title = title[: -(len(author_text) + 3)].strip()
    return title
