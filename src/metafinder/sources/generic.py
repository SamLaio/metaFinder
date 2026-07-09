from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from metafinder.models import BookCandidate, BookMetadata
from metafinder.normalize import clean_text, clean_title, normalize_isbn, short_tags, split_people
from metafinder.sources.web_search import USER_AGENT
from metafinder.tags import apply_awards_to_tags, awards_as_dict, infer_awards_from_trusted_record, infer_tags


SOURCE_HINTS = {
    "ching-win.com.tw": ("青文出版社", "publisher"),
    "books.com.tw": ("博客來", "store"),
    "readmoo.com": ("Readmoo", "store"),
    "pubu.com.tw": ("Pubu", "store"),
    "kobo.com": ("Kobo", "store"),
    "bookwalker.com.tw": ("BOOKWALKER", "store"),
    "eslite.com": ("誠品線上", "store"),
    "shogakukan.co.jp": ("小學館", "publisher"),
    "gagagabunko.jp": ("小學館 Gagaga", "publisher"),
    "book.moc.gov.tw": ("文化部", "government"),
    "ncl.edu.tw": ("國家圖書館", "government"),
    "ttkan.co": ("天天看小說", "web-novel"),
    "ixdzs.com": ("愛下電子書", "web-novel"),
    "ixdzs8.com": ("愛下電子書", "web-novel"),
}

BASE_SOURCE_SCORE = {
    "publisher": 40,
    "government": 34,
    "store": 30,
    "web-novel": 18,
    "other": 8,
}


@dataclass
class GenericPageParser:
    timeout: float = 20.0

    def fetch(self, url: str) -> str:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=self.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        return response.text

    def parse_url(self, url: str, query: str | None = None, expected_isbn: str | None = None) -> BookCandidate:
        html = self.fetch(url)
        return self.parse_html(url, html, query=query, expected_isbn=expected_isbn)

    def parse_html(
        self,
        url: str,
        html: str,
        query: str | None = None,
        expected_isbn: str | None = None,
    ) -> BookCandidate:
        soup = BeautifulSoup(html, "lxml")
        metadata = BookMetadata()
        evidence: list[str] = []

        self._from_json_ld(soup, metadata, evidence)
        self._from_meta_tags(soup, url, metadata, evidence)
        self._from_visible_labels(soup, metadata, evidence)
        self._from_images(soup, url, metadata, evidence)
        self._cleanup(metadata)

        source_name, source_kind = source_info(url)
        page_text = soup.get_text("\n", strip=True)
        tag_info = infer_tags(metadata, extra_text=page_text)
        metadata.tags = tag_info.tags
        awards = infer_awards_from_trusted_record(url, metadata, page_text)
        metadata.awards = awards_as_dict(awards)
        metadata.tags = apply_awards_to_tags(metadata.tags, awards)
        if awards:
            evidence.append("verified-award-record")
        if tag_info.tags:
            evidence.append("inferred-tags")
        score = self._score(metadata, source_kind, query=query, expected_isbn=expected_isbn)
        return BookCandidate(
            source_name=source_name,
            source_url=url,
            source_kind=source_kind,
            metadata=metadata,
            score=score,
            evidence=evidence,
        )

    def _from_json_ld(self, soup: BeautifulSoup, metadata: BookMetadata, evidence: list[str]) -> None:
        for script in soup.find_all("script", type=lambda t: t and "ld+json" in t):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for item in _walk_jsonld(data):
                item_type = item.get("@type") or item.get("type")
                types = item_type if isinstance(item_type, list) else [item_type]
                if not any(str(t).lower() in {"book", "product"} for t in types if t):
                    continue
                metadata.title = metadata.title or clean_title(_string(item.get("name")))
                metadata.description = metadata.description or clean_text(_string(item.get("description")))
                metadata.publisher = metadata.publisher or _name_field(item.get("publisher"))
                date = item.get("datePublished") or item.get("dateCreated")
                metadata.published_date = metadata.published_date or clean_text(_string(date))
                isbn = normalize_isbn(_string(item.get("isbn")))
                metadata.isbn = metadata.isbn or isbn
                image = _string(item.get("image"))
                if image:
                    metadata.cover_url = metadata.cover_url or image
                authors = _names_field(item.get("author"))
                if authors:
                    metadata.authors = metadata.authors or authors
                evidence.append("json-ld")

    def _from_meta_tags(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        title = _meta_content(soup, ["og:title", "twitter:title", "title"])
        description = _meta_content(soup, ["og:description", "description", "twitter:description"])
        image = _meta_content(soup, ["og:image", "twitter:image"])
        metadata.title = metadata.title or clean_title(title or (soup.title.get_text(" ", strip=True) if soup.title else None))
        metadata.description = metadata.description or clean_text(description)
        if image and not metadata.cover_url:
            metadata.cover_url = urljoin(url, image)
        if title or description or image:
            evidence.append("meta-tags")

    def _from_visible_labels(self, soup: BeautifulSoup, metadata: BookMetadata, evidence: list[str]) -> None:
        text = soup.get_text("\n", strip=True)
        label_map = {
            "authors": [r"(?:作者|作家|著者)\s*[:：]\s*(.+)"],
            "translators": [r"(?:譯者|译者)\s*[:：]\s*(.+)"],
            "publisher": [r"(?:出版社|出版者|出版)\s*[:：]\s*(.+)"],
            "published_date": [r"(?:出版日期|出版日|出版時間|更新)\s*[:：]\s*([0-9]{4}[-/.年][0-9]{1,2}(?:[-/.月][0-9]{1,2}日?)?)"],
            "isbn": [r"(?<![A-Za-z])(?:ISBN13|ISBN)\s*[:：]\s*([0-9Xx-]{10,17})"],
            "eisbn": [r"(?:eISBN|電子ISBN)\s*[:：]\s*([0-9Xx-]{10,17})"],
            "tags": [r"(?:標籤|标签|類別|类别|分類|分类)\s*[:：]\s*(.+)"],
        }
        found = False
        for field, patterns in label_map.items():
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.I)
                if not match:
                    continue
                value = clean_text(match.group(1))
                if not value:
                    continue
                found = True
                if field == "authors" and not metadata.authors:
                    metadata.authors = split_people(value)
                elif field == "translators" and not metadata.translators:
                    metadata.translators = split_people(value)
                elif field == "publisher" and not metadata.publisher:
                    metadata.publisher = value
                elif field == "published_date" and not metadata.published_date:
                    metadata.published_date = value
                elif field == "isbn" and not metadata.isbn:
                    metadata.isbn = normalize_isbn(value)
                elif field == "eisbn" and not metadata.eisbn:
                    metadata.eisbn = normalize_isbn(value)
                elif field == "tags" and not metadata.tags:
                    metadata.tags = short_tags([value])
                break
        h1 = soup.find("h1")
        if h1 and not metadata.title:
            metadata.title = clean_title(h1.get_text(" ", strip=True))
            found = True
        if found:
            evidence.append("visible-labels")

    def _from_images(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        if metadata.cover_url:
            metadata.cover_url = urljoin(url, metadata.cover_url)
            return
        candidates: list[str] = []
        for img in soup.find_all("img"):
            alt = img.get("alt") or ""
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue
            haystack = f"{alt} {src}".lower()
            if any(word in haystack for word in ["cover", "封面", "book"]):
                candidates.append(urljoin(url, src))
        if candidates:
            metadata.cover_url = candidates[0]
            evidence.append("image-heuristic")

    def _cleanup(self, metadata: BookMetadata) -> None:
        metadata.title = clean_title(metadata.title)
        metadata.subtitle = clean_text(metadata.subtitle)
        metadata.authors = split_people(metadata.authors)
        metadata.translators = split_people(metadata.translators)
        metadata.publisher = clean_text(metadata.publisher)
        metadata.published_date = clean_text(metadata.published_date)
        metadata.isbn = normalize_isbn(metadata.isbn)
        metadata.eisbn = normalize_isbn(metadata.eisbn)
        metadata.language = clean_text(metadata.language)
        metadata.description = clean_text(metadata.description)
        metadata.tags = short_tags(metadata.tags)

    def _score(
        self,
        metadata: BookMetadata,
        source_kind: str,
        query: str | None = None,
        expected_isbn: str | None = None,
    ) -> float:
        score = BASE_SOURCE_SCORE.get(source_kind, BASE_SOURCE_SCORE["other"])
        score += metadata.completeness_score() * 4
        if expected_isbn and expected_isbn in {metadata.isbn, metadata.eisbn}:
            score += 25
        if query and metadata.title:
            query_tokens = {t.lower() for t in re.findall(r"[\w\u4e00-\u9fff]+", query) if len(t) > 1}
            title_lower = metadata.title.lower()
            score += sum(3 for token in query_tokens if token in title_lower)
        if metadata.cover_url:
            score += 5
        return float(score)


def source_info(url: str) -> tuple[str, str]:
    host = urlparse(url).netloc.lower()
    for domain, info in SOURCE_HINTS.items():
        if host == domain or host.endswith("." + domain):
            return info
    return host or "unknown", "other"


def _meta_content(soup: BeautifulSoup, names: list[str]) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def _walk_jsonld(data: Any):
    if isinstance(data, dict):
        if "@graph" in data:
            for item in _walk_jsonld(data["@graph"]):
                yield item
        yield data
    elif isinstance(data, list):
        for item in data:
            yield from _walk_jsonld(item)


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _string(value[0])
    if isinstance(value, dict):
        return _string(value.get("name") or value.get("@id") or value.get("url"))
    return str(value)


def _name_field(value: Any) -> str | None:
    return clean_text(_string(value))


def _names_field(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return split_people([_string(v) or "" for v in value])
    return split_people(_string(value))
