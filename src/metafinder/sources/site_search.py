from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

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

BOOK_URL_PATTERNS = [
    re.compile(r"https?://(?:www\.)?books\.com\.tw/products/[A-Za-z0-9]+"),
    re.compile(r"https?://readmoo\.com/book/[0-9A-Za-z]+"),
    re.compile(r"https?://(?:www\.)?pubu\.com\.tw/ebook/[0-9A-Za-z_-]+"),
    re.compile(r"https?://(?:www\.)?eslite\.com/product/[0-9A-Za-z_-]+"),
    re.compile(r"https?://(?:www\.)?ching-win\.com\.tw/product-detail/[0-9A-Za-z_-]+"),
    re.compile(r"https?://book\.moc\.gov\.tw/book/new/books-detail/\?id=\d+"),
    re.compile(r"https?://ixdzs8?\.com/read/\d+/?"),
    re.compile(r"https?://(?:www\.)?jjwxc\.net/onebook\.php\?novelid=\d+"),
    re.compile(r"https?://m\.jjwxc\.net/book2/\d+/?"),
    re.compile(r"https?://wap\.jjwxc\.net/book2/\d+/?"),
    re.compile(r"https?://fanqienovel\.com/page/\d+/?"),
]


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


def _matches_book_url(url: str) -> bool:
    return any(pattern.match(url) for pattern in BOOK_URL_PATTERNS)


def _strip_tracking(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("books.com.tw"):
        match = re.search(r"(https?://(?:www\.)?books\.com\.tw/products/[A-Za-z0-9]+)", url)
        if match:
            return match.group(1)
    if parsed.fragment:
        return url.split("#", 1)[0]
    return url
