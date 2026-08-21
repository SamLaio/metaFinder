from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Iterable

try:
    from opencc import OpenCC
except Exception:
    OpenCC = None

zhtranslate_src = Path(r"D:\github\zhTranslate\src")
if zhtranslate_src.exists() and str(zhtranslate_src) not in sys.path:
    sys.path.insert(0, str(zhtranslate_src))

try:
    from s2tw_converter import Converter as ZhTranslateConverter
except Exception:
    ZhTranslateConverter = None

_traditional_converter = None
_simplified_converter = None


def _get_converter():
    global _traditional_converter
    if _traditional_converter is not None:
        return _traditional_converter
    if ZhTranslateConverter is None:
        _traditional_converter = False
        return _traditional_converter
    try:
        _traditional_converter = ZhTranslateConverter()
    except Exception:
        _traditional_converter = False
    return _traditional_converter


def _get_simplified_converter():
    global _simplified_converter
    if _simplified_converter is not None:
        return _simplified_converter
    if OpenCC is None:
        _simplified_converter = False
        return _simplified_converter
    try:
        _simplified_converter = OpenCC("tw2s")
    except Exception:
        _simplified_converter = False
    return _simplified_converter


def to_traditional(text: str | None) -> str | None:
    if not text:
        return text
    converter = _get_converter()
    if converter:
        try:
            return converter.convert(text)
        except Exception:
            pass
    return text


def to_simplified_for_search(text: str | None) -> str | None:
    """Create a Simplified Chinese query variant for sources that index that way."""
    if not text:
        return text
    converter = _get_simplified_converter()
    if not converter:
        return text
    try:
        return converter.convert(text)
    except Exception:
        return text


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" \t\r\n:：|｜-—")
    return to_traditional(text) if text else None


def clean_title(text: str | None) -> str | None:
    text = clean_text(text)
    if not text:
        return None
    text = re.sub(r"\s*[-|｜]\s*(Readmoo|博客來|誠品線上|Kobo|Pubu).*$", "", text, flags=re.I)
    text = re.sub(r"^《(.+)》$", r"\1", text)
    return clean_text(text)


PUBLISHER_ALIASES = {
    "聯經出版公司": "聯經出版",
    "東立出版社": "東立出版",
    "東立": "東立出版",
}


def normalize_publisher(text: str | None) -> str | None:
    text = clean_text(text)
    if not text:
        return None
    return PUBLISHER_ALIASES.get(text, text)


def split_people(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[/／、；;]|(?:\s+和\s+)|(?:\s*&\s+)", value)
    else:
        raw_items = list(value)
    people: list[str] = []
    for item in raw_items:
        item = clean_text(str(item))
        if not item:
            continue
        item = re.sub(r"^(作者|作家|譯者|译者|繪者|绘者)\s*[:：]\s*", "", item)
        item = re.sub(r"[_｜|]\s*(愛下電子書|爱下电子书|Readmoo|博客來|誠品線上|Kobo|Pubu)$", "", item, flags=re.I)
        item = clean_text(item)
        if item and item not in people:
            people.append(item)
    return people


def normalize_isbn(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"[^0-9Xx]", "", value)
    if len(value) in {10, 13}:
        return value.upper()
    return None


def short_tags(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    stop = {"電子書", "書籍", "中文書", "繁體中文", "簡體中文", "一般小說"}
    for value in values:
        value = clean_text(value)
        if not value or value in stop:
            continue
        for part in re.split(r"[,，/／、>|｜\s]+", value):
            part = clean_text(part)
            if not part or part in stop:
                continue
            if len(part) > 8:
                continue
            if part not in result:
                result.append(part)
    return result[:12]


@dataclass(frozen=True)
class VolumeTitle:
    display_title: str
    series_title: str
    series_index: float


def volume_title_from_trailing_number(title: str | None) -> VolumeTitle | None:
    """Convert titles like '書名12' or '書名(12)' to '12 書名'."""

    title = clean_title(title)
    if not title:
        return None
    match = re.match(r"^(.+?)\s*[\(（]?\s*(\d{1,3})(?:\s*[\)）])?\s*$", title)
    if not match:
        return None
    series_title = clean_title(match.group(1))
    if not series_title:
        return None
    volume = int(match.group(2))
    return VolumeTitle(
        display_title=f"{volume:02d} {series_title}",
        series_title=series_title,
        series_index=float(volume),
    )
