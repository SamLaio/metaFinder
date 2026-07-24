from __future__ import annotations

import re
from dataclasses import dataclass


CHINESE_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass(frozen=True)
class SeriesInfo:
    name: str
    index: float
    evidence: str


GENERIC_EXTERNAL_SERIES = {"溫馨"}


def infer_series_from_title(title: str | None) -> SeriesInfo | None:
    """Infer reusable series metadata from common Chinese romance title formats."""

    if not title:
        return None
    value = _normalize_spaces(title)

    patterns = [
        (r"～\s*([A-Za-z][A-Za-z ]+?)\s*NO\.?\s*([0-9]+)", "latin-no"),
        (r"[【\[]\s*([^】\]]+?)\s*PART\s*([0-9]+)\s*[】\]]", "bracket-part"),
        (r"[（(]\s*([^）)]+?)\s*(?:PART|之)\s*([0-9一二兩三四五六七八九十]+)\s*[）)]", "paren-part"),
        (r"[（(]\s*([^）)0-9一二兩三四五六七八九十]+?)\s*([0-9一二兩三四五六七八九十]+)\s*[）)]", "paren-direct-volume"),
        (r"～\s*([^～【】\[\]（）()]+?)(?:系列)?之([一二兩三四五六七八九十]+)", "tilde-zh-ordinal"),
        (r"([^～【】\[\]（）()]+?)系列之([一二兩三四五六七八九十]+)", "series-zh-ordinal"),
    ]
    for pattern, evidence in patterns:
        match = re.search(pattern, value, flags=re.I)
        if not match:
            continue
        series = _clean_series_name(match.group(1))
        index = _number(match.group(2))
        if series and index:
            return SeriesInfo(series, float(index), evidence)

    match = re.fullmatch(r"(.+?)\s*Part\s*([0-9]+|[IVXLC]+)", value, flags=re.I)
    if match:
        index = _number(match.group(2))
        series = _clean_series_name(match.group(1))
        if series and index:
            return SeriesInfo(series, float(index), "title-part")

    match = re.fullmatch(r"(.+?)([0-9１２３４５６７８９]|[一二兩三四五六七八九十])", value)
    if match:
        series = _clean_series_name(match.group(1))
        index = _number(match.group(2))
        if series and index and len(series) >= 3:
            return SeriesInfo(series, float(index), "trailing-volume")

    match = re.fullmatch(r"(.+?)[（(](上|中|下|上、下)[）)]", value)
    if match:
        base = _clean_series_name(match.group(1))
        marker = match.group(2)
        index = {"上": 1.0, "中": 2.0, "下": 3.0, "上、下": 1.0}.get(marker)
        if base and index:
            return SeriesInfo(base, index, "split-volume")

    return None


def series_evidence_priority(series_name: str, evidence: str) -> int:
    """Rank reusable series evidence so weak title splits do not override sources."""

    if evidence.startswith("manual"):
        return 100
    if any(
        evidence.endswith(marker)
        for marker in (
            "bracket-part",
            "paren-part",
            "paren-direct-volume",
            "tilde-zh-ordinal",
            "series-zh-ordinal",
            "latin-no",
            "title-part",
        )
    ):
        return 90
    if evidence.startswith(("millionbook", "wrn", "cxyqw")):
        if series_name in GENERIC_EXTERNAL_SERIES:
            return 60
        return 85
    if evidence.startswith("content-title"):
        return 80
    if any(evidence.endswith(marker) for marker in ("trailing-volume", "split-volume")):
        return 70
    return 0


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("　", " ")).strip()


def _clean_series_name(value: str) -> str:
    value = _normalize_spaces(value)
    value = re.sub(r"^(?:《|「|『|【)", "", value)
    value = re.sub(r"(?:》|」|』|】)$", "", value)
    value = re.sub(r"(?:電子版|流式版面|再版|典藏版)$", "", value).strip()
    value = re.sub(r"系列$", "", value).strip()
    return value


def _number(value: str) -> int | None:
    value = value.strip().upper()
    fullwidth = str.maketrans("０１２３４５６７８９", "0123456789")
    value = value.translate(fullwidth)
    if value.isdigit():
        return int(value)
    if re.fullmatch(r"[IVXLC]+", value):
        return _roman(value)
    if value in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[value]
    if value.startswith("十") and len(value) == 2:
        return 10 + CHINESE_NUMBERS.get(value[1:], 0)
    if value.endswith("十") and len(value) == 2:
        return CHINESE_NUMBERS.get(value[:1], 0) * 10
    if "十" in value and len(value) == 3:
        return CHINESE_NUMBERS.get(value[0], 0) * 10 + CHINESE_NUMBERS.get(value[2], 0)
    return None


def _roman(value: str) -> int | None:
    table = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    prev = 0
    for char in reversed(value):
        current = table.get(char)
        if current is None:
            return None
        if current < prev:
            total -= current
        else:
            total += current
            prev = current
    return total or None
