from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from metafinder.models import BookCandidate, BookMetadata
from metafinder.normalize import clean_text, clean_title, normalize_isbn, normalize_publisher, short_tags, split_people
from metafinder.series import infer_series_from_title
from metafinder.source_rules import source_info as _source_info, source_rule_for_url
from metafinder.sources.web_search import USER_AGENT, polite_get
from metafinder.tags import apply_awards_to_tags, awards_as_dict, infer_awards_from_trusted_record, infer_tags


BASE_SOURCE_SCORE = {
    "publisher": 40,
    "government": 34,
    "store": 30,
    "catalog": 24,
    "web-novel": 18,
    "other": 8,
}


@dataclass
class GenericPageParser:
    timeout: float = 20.0

    def fetch(self, url: str) -> str:
        response = polite_get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"},
            timeout=self.timeout,
        )
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

        self._extract_common_metadata(soup, url, metadata, evidence)
        self._apply_site_patch(soup, url, metadata, evidence)
        self._extract_fallback_metadata(soup, url, metadata, evidence)
        self._cleanup(metadata)

        source_name, source_kind = source_info(url)
        page_text = soup.get_text("\n", strip=True)
        tag_info = infer_tags(metadata)
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

    def _extract_common_metadata(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        self._from_json_ld(soup, metadata, evidence)
        self._from_meta_tags(soup, url, metadata, evidence)

    def _apply_site_patch(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        rule = source_rule_for_url(url)
        if not rule or not rule.patch:
            return
        patch = getattr(self, f"_patch_{rule.patch}", None)
        if patch:
            patch(soup, url, metadata, evidence)

    def _extract_fallback_metadata(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        self._from_visible_labels(soup, metadata, evidence)
        self._from_images(soup, url, metadata, evidence)

    def _from_json_ld(self, soup: BeautifulSoup, metadata: BookMetadata, evidence: list[str]) -> None:
        for script in soup.find_all("script", type=lambda t: t and "ld+json" in t):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    data = json.loads(raw, strict=False)
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
                metadata.language = metadata.language or clean_text(_string(item.get("inLanguage")))
                isbn = normalize_isbn(_string(item.get("isbn")))
                metadata.isbn = metadata.isbn or isbn
                image = _image_value(item.get("image"))
                if image:
                    metadata.cover_url = metadata.cover_url or image
                authors = _names_field(item.get("author"))
                if authors:
                    metadata.authors = metadata.authors or authors
                evidence.append("json-ld")

    def _from_meta_tags(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        title = _meta_content(soup, ["og:title", "twitter:title", "title"])
        description = _meta_content(soup, ["og:description", "description", "twitter:description"])
        image = _meta_content(soup, ["og:image", "og:image:secure_url", "twitter:image", "twitter:image:src", "image"])
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

    def _patch_fanqie(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        host = urlparse(url).netloc.lower()
        if not (host == "fanqienovel.com" or host.endswith(".fanqienovel.com")):
            return

        found = False
        title = soup.select_one("h1")
        if title:
            metadata.title = clean_title(title.get_text(" ", strip=True)) or metadata.title
            found = True

        author = soup.select_one(".author-name-text")
        if author:
            metadata.authors = split_people(author.get_text(" ", strip=True)) or metadata.authors
            found = True

        labels = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(".info-label span, .info-label-grey, .info-label-yellow")]
        if labels:
            metadata.tags = short_tags([label for label in labels if label and label not in {"已完結", "連載中"}]) or metadata.tags
            found = True

        updated = soup.select_one(".info-last-time")
        if updated and not metadata.published_date:
            metadata.published_date = clean_text(updated.get_text(" ", strip=True))
            found = True

        abstract = soup.select_one(".page-abstract-content")
        if abstract:
            metadata.description = clean_text(abstract.get_text(" ", strip=True)) or metadata.description
            found = True

        if not metadata.cover_url:
            image = _fanqie_cover_url(soup)
            if image:
                metadata.cover_url = image
                found = True

        if found:
            evidence.append("fanqie-page")

    def _patch_jjwxc(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        host = urlparse(url).netloc.lower()
        if not (host == "jjwxc.net" or host.endswith(".jjwxc.net")):
            return

        found = False
        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
        match = re.search(r"《([^》]+)》\s*([^_《》]+)?_?(?:晋江文学城|晉江文學城)", page_title)
        if match:
            metadata.title = clean_title(match.group(1)) or metadata.title
            author = clean_text(match.group(2))
            if author and not metadata.authors:
                metadata.authors = split_people(author)
            found = True

        text = soup.get_text("\n", strip=True)
        if not metadata.authors:
            author_match = re.search(r"作者\s*[:：]\s*([^\n\r]+)", text)
            if author_match:
                metadata.authors = split_people(author_match.group(1))
                found = True
        if not metadata.publisher:
            metadata.publisher = "晉江文學城"
            found = True

        if not metadata.cover_url:
            for img in soup.find_all("img"):
                src = _image_src(img)
                if src and "imgdb.cn" in src:
                    metadata.cover_url = urljoin(url, src)
                    found = True
                    break

        if found:
            evidence.append("jjwxc-page")

    def _patch_pubu(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        host = urlparse(url).netloc.lower()
        if not (host == "pubu.com.tw" or host.endswith(".pubu.com.tw")):
            return

        found = False
        raw_title = _meta_content(soup, ["og:title", "twitter:title", "title"]) or (soup.title.get_text(" ", strip=True) if soup.title else "")
        title_match = re.search(r"\|\s*(.*?)\s*\|\s*Pubu\b", raw_title)
        if title_match:
            title = clean_title(title_match.group(1))
            if title:
                metadata.title = title
                found = True

        raw_description = _meta_content(soup, ["og:description", "description", "twitter:description"])
        pubu_meta = _pubu_description_parts(raw_description)
        if pubu_meta:
            publisher, authors, description = pubu_meta
            if publisher and not metadata.publisher:
                metadata.publisher = publisher
                found = True
            if authors and not metadata.authors:
                metadata.authors = authors
                found = True
            if description:
                metadata.description = description
                found = True

        published_date = _pubu_visible_field(soup, "發行")
        if published_date and not metadata.published_date:
            metadata.published_date = published_date
            found = True

        language = _pubu_visible_field(soup, "語言")
        if language and not metadata.language:
            metadata.language = language
            found = True

        if found:
            evidence.append("pubu-page")

    def _patch_anobii(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        host = urlparse(url).netloc.lower()
        if not (host == "anobii.com" or host.endswith(".anobii.com")):
            return

        found = False
        match = re.search(r"/books/[^/]+/([0-9Xx-]{10,17})/", url)
        if match and not metadata.isbn:
            metadata.isbn = normalize_isbn(match.group(1))
            found = True

        if metadata.title and "anobii" in metadata.title.lower() and "passion" in metadata.title.lower():
            metadata.title = None
            found = True

        if found:
            evidence.append("anobii-url")

    def _patch_sanmin(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        host = urlparse(url).netloc.lower()
        if not (host == "sanmin.com.tw" or host.endswith(".sanmin.com.tw")):
            return

        found = False
        text = soup.get_text("\n", strip=True)
        title = _first_text(soup, ["h1", ".prod_title", ".product-title", ".book-title"])
        if title and not metadata.title:
            metadata.title = clean_title(title)
            found = True

        fields = _label_values(text)
        if not metadata.isbn:
            metadata.isbn = normalize_isbn(fields.get("ISBN13") or fields.get("ISBN"))
            found = found or bool(metadata.isbn)
        if not metadata.publisher:
            metadata.publisher = fields.get("出版社")
            found = found or bool(metadata.publisher)
        if not metadata.authors and fields.get("作者"):
            metadata.authors = split_people(fields["作者"])
            found = found or bool(metadata.authors)
        if not metadata.translators and fields.get("譯者"):
            metadata.translators = split_people(fields["譯者"])
            found = found or bool(metadata.translators)
        if not metadata.published_date:
            metadata.published_date = fields.get("出版日") or fields.get("出版日期")
            found = found or bool(metadata.published_date)

        if not metadata.description:
            description = _section_after_heading(soup, ["內容簡介", "商品簡介", "書籍簡介"])
            if description:
                metadata.description = description
                found = True

        if found:
            evidence.append("sanmin-page")

    def _patch_tdtb(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        host = urlparse(url).netloc.lower()
        if not (host == "tdtb.org" or host.endswith(".tdtb.org")):
            return

        found = False
        title = _tdtb_title(soup)
        clean_library_title = clean_title(re.sub(r"\s*@\s*本館館藏\s*$", "", title or ""))
        if clean_library_title and (not metadata.title or "本館館藏" in metadata.title):
            metadata.title = clean_library_title
            found = True

        text = soup.get_text("\n", strip=True)
        fields = _label_values(text)
        if not metadata.authors and fields.get("作者"):
            metadata.authors = split_people(fields["作者"])
            found = found or bool(metadata.authors)
        if not metadata.publisher:
            metadata.publisher = fields.get("出版單位") or fields.get("出版社")
            found = found or bool(metadata.publisher)
        if not metadata.published_date:
            metadata.published_date = fields.get("出版年份") or fields.get("出版日期")
            found = found or bool(metadata.published_date)
        if not metadata.description:
            description = _tdtb_description(text)
            if description:
                metadata.description = description
                found = True

        if found:
            evidence.append("tdtb-library-page")

    def _from_images(self, soup: BeautifulSoup, url: str, metadata: BookMetadata, evidence: list[str]) -> None:
        if metadata.cover_url:
            metadata.cover_url = urljoin(url, metadata.cover_url)
            return
        candidates: list[str] = []
        for img in soup.find_all("img"):
            alt = img.get("alt") or ""
            src = _image_src(img)
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
        metadata.publisher = normalize_publisher(metadata.publisher)
        metadata.published_date = clean_text(metadata.published_date)
        metadata.isbn = normalize_isbn(metadata.isbn)
        metadata.eisbn = normalize_isbn(metadata.eisbn)
        metadata.language = clean_text(metadata.language)
        metadata.description = clean_text(metadata.description)
        if _looks_like_catalog_fact_sheet(metadata.description):
            metadata.description = None
        metadata.tags = short_tags(metadata.tags)
        if metadata.title and not metadata.series:
            series = infer_series_from_title(metadata.title)
            if series:
                metadata.series = series.name
                metadata.series_index = series.index

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
    return _source_info(url)


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


def _image_value(value: Any) -> str | None:
    if isinstance(value, dict):
        return _string(value.get("url") or value.get("contentUrl") or value.get("@id") or value.get("name"))
    return _string(value)


def _image_src(img) -> str | None:
    for attr in ["src", "data-src", "data-original", "data-lazy-src", "data-lazyload", "data-actualsrc", "data-url"]:
        value = img.get(attr)
        if value:
            return value
    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        first = srcset.split(",", 1)[0].strip()
        if first:
            return first.split()[0]
    return None


def _looks_like_catalog_fact_sheet(value: str | None) -> bool:
    """Reject bookstore fact sheets that are metadata, not book descriptions."""

    text = clean_text(value)
    if not text:
        return False
    labels = ["書名", "原文名稱", "語言", "ISBN", "頁數", "出版社", "作者", "譯者", "出版日期", "類別"]
    label_hits = sum(1 for label in labels if re.search(rf"{re.escape(label)}\s*[:：]", text, flags=re.I))
    if label_hits >= 4:
        return True
    return bool(text.startswith("書名：") and label_hits >= 2)


def _pubu_description_parts(value: str | None) -> tuple[str | None, list[str], str | None] | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.match(
        r"^(?:出版|Publisher)\s*[:：]\s*(?P<publisher>[^，,]+)[，,]\s*"
        r"(?:作者|Author)\s*[:：]\s*(?P<authors>[^，,]+)[，,]\s*(?P<description>.+)$",
        text,
        flags=re.I,
    )
    if not match:
        return None
    description = clean_text(re.sub(r"^(?:內容簡介|簡介)\s*[:：]\s*", "", match.group("description")))
    return (
        normalize_publisher(match.group("publisher")),
        split_people(match.group("authors")),
        description,
    )


def _pubu_visible_field(soup: BeautifulSoup, label: str) -> str | None:
    lines = [line for line in (clean_text(part) for part in soup.get_text("\n", strip=True).split("\n")) if line]
    for index, line in enumerate(lines[:-1]):
        if line == label:
            return lines[index + 1]
    return None


def _fanqie_cover_url(soup: BeautifulSoup) -> str | None:
    text = "\n".join(script.get_text() or "" for script in soup.find_all("script"))
    for pattern in [r'"thumbUrl"\s*:\s*"([^"]+)"', r'"image"\s*:\s*\[\s*"([^"]+)"']:
        match = re.search(pattern, text)
        if match:
            return unescape(match.group(1)).replace("\\u002F", "/")
    return None


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            value = clean_text(node.get_text(" ", strip=True))
            if value:
                return value
    return None


def _tdtb_title(soup: BeautifulSoup) -> str | None:
    title = _first_text(soup, [".title"])
    if title:
        return title
    for node in soup.select("main h2, h2"):
        value = clean_text(node.get_text(" ", strip=True))
        if value and value not in {"本館館藏", "你可能也想要看...", "最新消息", "關於我們", "服務項目", "精選內容", "學習資源"}:
            return value
    return None


def _label_values(text: str) -> dict[str, str]:
    labels = {
        "作者",
        "譯者",
        "译者",
        "出版社",
        "出版單位",
        "出版年份",
        "出版日期",
        "出版日",
        "ISBN13",
        "ISBN",
    }
    field_labels = labels | {"格式類型", "書籍類型", "錄音者", "內容簡介"}
    values: dict[str, str] = {}
    lines = [clean_text(line) or "" for line in text.splitlines()]
    for index, line in enumerate(lines):
        if not line:
            continue
        match = re.match(r"^(作者|譯者|译者|出版社|出版單位|出版年份|出版日期|出版日|ISBN13|ISBN)\s*[:：]?\s*(.*)$", line)
        if not match:
            continue
        label, value = match.group(1), clean_text(match.group(2)) or ""
        if not value and index + 1 < len(lines):
            value = clean_text(lines[index + 1]) or ""
        if value in field_labels:
            value = ""
        if value:
            values["譯者" if label == "译者" else label] = value
    return {label: value for label, value in values.items() if label in labels and value}


def _section_after_heading(soup: BeautifulSoup, headings: list[str]) -> str | None:
    for node in soup.find_all(string=lambda s: bool(s and clean_text(str(s)) in headings)):
        parent = node.parent
        if not parent:
            continue
        chunks: list[str] = []
        for sibling in parent.find_all_next():
            name = (sibling.name or "").lower()
            if name in {"h2", "h3", "h4"} and clean_text(sibling.get_text(" ", strip=True)) not in headings:
                break
            text = clean_text(sibling.get_text(" ", strip=True))
            if text and text not in headings:
                chunks.append(text)
            if len(" ".join(chunks)) >= 80:
                break
        description = clean_text(" ".join(chunks))
        if description:
            return description
    return None


def _tdtb_description(text: str) -> str | None:
    lines = [clean_text(line) or "" for line in text.splitlines()]
    skip_prefixes = ("作者", "出版單位", "出版年份", "格式類型", "書籍類型")
    chunks: list[str] = []
    for line in lines:
        if not line or line in {"前往登入", "回頂端"}:
            continue
        if line.startswith(skip_prefixes) or line.startswith(("客服信箱", "地址：")):
            continue
        line = re.split(r"\s*(?:客服信箱|地址：|©\s*\d{4})", line, maxsplit=1)[0]
        if len(line) < 20:
            continue
        chunks.append(line)
    return clean_text(" ".join(chunks[:3]))


def _name_field(value: Any) -> str | None:
    return clean_text(_string(value))


def _names_field(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return split_people([_string(v) or "" for v in value])
    raw = _string(value)
    if raw and "," in raw and re.search(r"[\u3400-\u9fff\u3040-\u30ff]", raw):
        raw = raw.replace(",", "、")
    return split_people(raw)
