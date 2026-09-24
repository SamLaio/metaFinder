from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from metafinder.models import BookCandidate, BookMetadata
from metafinder.normalize import clean_title, normalize_isbn, split_people, to_simplified_for_search
from metafinder.source_rules import BOOK_URL_PATTERNS as BOOK_URL_PATTERN_TEXTS
from metafinder.sources.web_search import USER_AGENT, polite_get


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


def search_source_sites(query: str, limit: int = 12, timeout: float = 15.0, stop_after_first_hit: bool = False) -> list[str]:
    if _is_kadokawa_query(query):
        return _search_kadokawa(query, timeout, limit)

    urls = _search_sanmin(query, timeout, limit)
    if len(urls) >= limit or (stop_after_first_hit and urls):
        return urls
    for href in _search_tdtb_library(query, timeout=timeout):
        if href not in urls:
            urls.append(href)
        if len(urls) >= limit:
            return urls
    for template in SITE_SEARCHES:
        search_url = template.url_template.format(query=quote_plus(query))
        try:
            response = polite_get(search_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
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
        if stop_after_first_hit and urls:
            return urls
    # Qidian is useful for web novels, but its broad CJK search produces
    # unrelated results for ordinary bookstore titles.  Use it only after the
    # dedicated bookstore searches had no usable URL.
    if not urls:
        for href in _search_qidian_mobile(query, timeout=timeout, limit=limit):
            if href not in urls:
                urls.append(href)
            if len(urls) >= limit:
                return urls
    return urls


def _is_kadokawa_query(query: str) -> bool:
    return "カドカワBOOKS" in query or "kadokawa" in query.lower()


def _search_kadokawa(query: str, timeout: float, limit: int) -> list[str]:
    """Use KADOKAWA's JSON search endpoint for explicitly marked imprints."""

    title = re.sub(r"\s*[（(](?:カドカワBOOKS|KADOKAWA)[)）].*$", "", query, flags=re.IGNORECASE).strip()
    if not title:
        return []
    data = {
        "pageno": "1",
        "pageno_book": "1",
        "pageno_media": "1",
        # 先取一頁再按冊次／媒體類型排序，不能把呼叫端筆數直接交給站方截斷。
        "size": "20",
        "itemIdKbn": "",
        "item_type": "",
        "kw": title,
    }
    try:
        response = requests.post(
            "https://www.kadokawa.co.jp/product/search/",
            data=data,
            headers={"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest"},
            timeout=timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", {})
    except Exception:
        return []

    items = results.get("book", results.get("all", []))
    requested_volume = _kadokawa_query_volume(query)
    is_kadokawa_books = "カドカワBOOKS" in query
    if requested_volume is not None:
        items = sorted(
            items,
            key=lambda item: (
                _kadokawa_result_volume(str(item.get("title", ""))) != requested_volume,
                is_kadokawa_books and item.get("subgenre_name") == "コミックス",
            ),
        )

    urls: list[str] = []
    for item in items:
        item_code = str(item.get("itemCode", ""))
        if item_code.isdigit():
            urls.append(f"https://www.kadokawa.co.jp/product/{item_code}/")
        if len(urls) >= limit:
            break
    return urls


def _kadokawa_query_volume(query: str) -> int | None:
    match = re.search(r"[\s　]([0-9０-９]{1,3})\s*[（(](?:カドカワBOOKS|KADOKAWA)[)）]", query, re.IGNORECASE)
    return int(match.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))) if match else None


def _kadokawa_result_volume(title: str) -> int | None:
    match = re.search(r"[\s　]([0-9０-９]{1,3})\s*$", title)
    return int(match.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))) if match else None


def search_source_candidates(query: str, limit: int = 3, timeout: float = 15.0, expected_isbn: str | None = None) -> list[BookCandidate]:
    candidates: list[BookCandidate] = []
    search_url = SITE_SEARCHES[0].url_template.format(query=quote_plus(query))
    try:
        response = polite_get(search_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return candidates
    soup = BeautifulSoup(response.text, "lxml")
    count = _books_result_count(soup)
    if count != 1 and not expected_isbn:
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


def _search_tdtb_library(query: str, timeout: float) -> list[str]:
    attempts: list[dict[str, str]] = []
    cleaned = clean_title(query) or query
    attempts.append({"Title": cleaned})
    parts = cleaned.rsplit(maxsplit=1)
    if len(parts) == 2:
        title, author = parts
        attempts.append({"Title": title, "Author": author})
        stripped_title = clean_title(re.sub(r"^(?:第?[0-9０-９一二三四五六七八九十百]+[集卷冊部]?|[0-9０-９]{1,3})\s*", "", title))
        if stripped_title and stripped_title != title:
            attempts.append({"Title": stripped_title, "Author": author})

    urls: list[str] = []
    for params in attempts:
        search_url = "https://tdtb.org/library?" + urlencode(params)
        try:
            response = polite_get(search_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(response.text, "lxml")
        for link in soup.find_all("a", href=True):
            href = urljoin(response.url, link["href"])
            if _matches_book_url(href) and href not in urls:
                urls.append(href)
    return urls


def _search_qidian_mobile(query: str, timeout: float, limit: int) -> list[str]:
    if not re.search(r"[\u3400-\u9fff]", query or ""):
        return []
    attempts: list[str] = []
    cleaned = clean_title(query) or query
    for value in [cleaned, cleaned.rsplit(maxsplit=1)[0] if " " in cleaned else ""]:
        value = value.strip()
        if value and value not in attempts:
            attempts.append(value)

    urls: list[str] = []
    for value in attempts:
        search_url = f"https://m.qidian.com/search?kw={quote_plus(value)}"
        try:
            response = polite_get(search_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(response.text, "lxml")
        query_key = re.sub(r"\W+", "", to_simplified_for_search(value) or value)
        for link in soup.select("a[data-bid], a[href*='/chapter/']"):
            title_node = link.select_one("h2, h3, .book-title")
            title = title_node.get_text(" ", strip=True) if title_node else link.get("title", "")
            title = re.sub(r"(?:在线阅读|線上閱讀)$", "", title)
            title_key = re.sub(r"\W+", "", to_simplified_for_search(title) or title)
            if not title_key or title_key not in query_key:
                continue
            bid = link.get("data-bid", "")
            if not bid.isdigit():
                match = re.search(r"/chapter/(\d+)/", link.get("href", ""))
                if not match:
                    continue
                bid = match.group(1)
            href = f"https://m.qidian.com/book/{bid}/"
            if href not in urls:
                urls.append(href)
            if len(urls) >= limit:
                return urls
    return urls


def _search_sanmin(query: str, timeout: float, limit: int) -> list[str]:
    volume = re.match(r"^(\d{1,3})\s+", query.strip())
    value = re.sub(r"^\d{1,3}\s+", "", query.strip())
    if " " in value and not normalize_isbn(value):
        value = value.rsplit(maxsplit=1)[0]
    if not volume:
        trailing = re.search(r"\s+0*([1-9][0-9]{0,2})$", value)
        if trailing:
            volume = trailing
            value = value[:trailing.start()].strip()
    if volume:
        value += f"{int(volume.group(1)):02d}"
    try:
        response = polite_get("https://www.sanmin.com.tw/search/index/?ct=K&qu=" + quote_plus(value),
                              headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(response.text, "lxml")
    matches: list[tuple[str, str]] = []
    expected = re.sub(r"[\W\d]+", "", to_simplified_for_search(value) or value)
    isbn = normalize_isbn(value)
    for link in soup.select("a[href*='/product/index/']"):
        title = re.sub(r"^\d+\.\s*", "", link.get_text(" ", strip=True))
        actual = re.sub(r"[\W\d]+", "", to_simplified_for_search(title) or title)
        if not title or (not isbn and (not expected or not actual or not (actual in expected or expected in actual))):
            continue
        # ISBN 搜尋只收編號結果列，避免頁首推薦商品。
        if isbn and not re.match(r"^\d+\.\s*", link.get_text(" ", strip=True)):
            continue
        url = urljoin("https://www.sanmin.com.tw", link["href"])
        if (title, url) not in matches:
            matches.append((title, url))

    # 三民以新集數優先；先篩同集，避免較舊的目標集被前幾筆結果截掉。
    if volume:
        requested_volume = int(volume.group(1))
        exact = [(title, url) for title, url in matches if _sanmin_title_volume(title) == requested_volume]
        if exact:
            matches = exact
        if "漫畫" not in query:
            prose = [(title, url) for title, url in matches if "漫畫" not in title]
            if prose:
                matches = prose
    return [url for _, url in matches[:limit]]


def _sanmin_title_volume(title: str) -> int | None:
    """Return the trailing Arabic volume label from a Sanmin result title."""

    match = re.search(r"(?:第\s*)?0*([0-9]{1,3})(?:\s*[（(]|\s*$)", title)
    return int(match.group(1)) if match else None


def _books_result_count(soup: BeautifulSoup) -> int | None:
    node = soup.select_one(".search_results p")
    if not node:
        return None
    match = re.search(r"搜尋結果共\s*([0-9]+)\s*筆", node.get_text(" ", strip=True))
    return int(match.group(1)) if match else None
