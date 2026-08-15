from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceRule:
    domains: tuple[str, ...]
    source_name: str
    source_kind: str
    book_url_patterns: tuple[str, ...] = ()
    patch: str | None = None


SOURCE_RULES = (
    SourceRule(("ching-win.com.tw",), "青文出版社", "publisher", ("https?://(?:www\\.)?ching-win\\.com\\.tw/product-detail/[A-Za-z0-9_-]+",)),
    SourceRule(("crown.com.tw",), "皇冠文化", "publisher", ("https?://(?:www\\.)?crown\\.com\\.tw/view\\.aspx\\?bc=[0-9A-Za-z_-]+",)),
    SourceRule(("cite.com.tw",), "城邦讀書花園", "publisher", ("https?://(?:www\\.)?cite\\.com\\.tw/book\\?id=[0-9A-Za-z_-]+",)),
    SourceRule(("books.com.tw",), "博客來", "store", ("https?://(?:www\\.)?books\\.com\\.tw/products/[A-Za-z0-9]+",)),
    SourceRule(("readmoo.com",), "Readmoo", "store", ("https?://readmoo\\.com/book/[0-9A-Za-z]+",)),
    SourceRule(("pubu.com.tw",), "Pubu", "store", ("https?://(?:www\\.)?pubu\\.com\\.tw/ebook/[0-9A-Za-z_-]+",)),
    SourceRule(("kobo.com",), "Kobo", "store"),
    SourceRule(("bookwalker.com.tw",), "BOOKWALKER", "store"),
    SourceRule(("eslite.com",), "誠品線上", "store", ("https?://(?:www\\.)?eslite\\.com/product/[0-9A-Za-z_-]+",)),
    SourceRule(("anobii.com",), "Anobii", "other", ("https?://(?:www\\.)?anobii\\.com/[^/]+/books/[^/]+/[0-9Xx-]{10,17}/[A-Za-z0-9_-]+",), patch="anobii"),
    SourceRule(("shogakukan.co.jp",), "小學館", "publisher"),
    SourceRule(("gagagabunko.jp",), "小學館 Gagaga", "publisher"),
    SourceRule(("book.moc.gov.tw",), "文化部", "government", ("https?://book\\.moc\\.gov\\.tw/book/new/books-detail/\\?id=\\d+",)),
    SourceRule(("ncl.edu.tw",), "國家圖書館", "government"),
    SourceRule(("qidian.com",), "起點中文網", "web-novel", ("https?://(?:www\\.)?qidian\\.com/book/\\d+/?",)),
    SourceRule(("reader.qq.com",), "QQ閱讀", "web-novel", ("https?://ubook\\.reader\\.qq\\.com/book-detail/\\d+",)),
    SourceRule(("ttkan.co",), "天天看小說", "web-novel"),
    SourceRule(("ixdzs.com",), "愛下電子書", "web-novel", ("https?://ixdzs8?\\.com/read/\\d+/?",)),
    SourceRule(("ixdzs8.com",), "愛下電子書", "web-novel", ("https?://ixdzs8?\\.com/read/\\d+/?",)),
    SourceRule(
        ("jjwxc.net",),
        "晉江文學城",
        "web-novel",
        (
            "https?://(?:www\\.)?jjwxc\\.net/onebook\\.php\\?novelid=\\d+",
            "https?://m\\.jjwxc\\.net/book2/\\d+/?",
            "https?://wap\\.jjwxc\\.net/book2/\\d+/?",
        ),
        patch="jjwxc",
    ),
    SourceRule(("fanqienovel.com",), "番茄小說", "web-novel", ("https?://fanqienovel\\.com/page/\\d+/?",), patch="fanqie"),
)

BOOK_URL_PATTERNS = tuple(pattern for rule in SOURCE_RULES for pattern in rule.book_url_patterns)


def source_rule_for_url(url: str) -> SourceRule | None:
    host = urlparse(url).netloc.lower()
    for rule in SOURCE_RULES:
        if _host_matches(host, rule.domains):
            return rule
    return None


def source_info(url: str) -> tuple[str, str]:
    rule = source_rule_for_url(url)
    if rule:
        return rule.source_name, rule.source_kind
    host = urlparse(url).netloc.lower()
    return host or "unknown", "other"


def _host_matches(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)
