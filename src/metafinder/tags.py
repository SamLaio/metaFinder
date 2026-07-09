from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from metafinder.models import BookMetadata
from metafinder.normalize import clean_text, short_tags


@dataclass(frozen=True)
class AwardMatch:
    name: str
    status: str
    evidence: str
    international: bool = True
    source_name: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class TagInference:
    tags: list[str]
    awards: list[AwardMatch]


REGION_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("臺灣", ("臺灣", "台灣", "台北", "臺北", "Taiwan")),
    ("日本", ("日本", "日籍", "Japanese", "Japan")),
    ("韓國", ("韓國", "南韓", "Korea", "Korean")),
    ("中國", ("中國", "大陸", "Chinese author", "China")),
    ("香港", ("香港", "Hong Kong")),
    ("美國", ("美國", "American", "United States", "USA")),
    ("英國", ("英國", "British", "United Kingdom", "UK")),
    ("法國", ("法國", "French", "France")),
    ("德國", ("德國", "German", "Germany")),
    ("義大利", ("義大利", "Italian", "Italy")),
    ("西班牙", ("西班牙", "Spanish", "Spain")),
    ("加拿大", ("加拿大", "Canadian", "Canada")),
    ("澳洲", ("澳洲", "澳大利亞", "Australian", "Australia")),
    ("愛爾蘭", ("愛爾蘭", "Irish", "Ireland")),
    ("瑞典", ("瑞典", "Swedish", "Sweden")),
    ("挪威", ("挪威", "Norwegian", "Norway")),
    ("丹麥", ("丹麥", "Danish", "Denmark")),
    ("芬蘭", ("芬蘭", "Finnish", "Finland")),
    ("波蘭", ("波蘭", "Polish", "Poland")),
    ("俄羅斯", ("俄羅斯", "Russian", "Russia")),
]


GENRE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("輕小說", ("輕小說", "ライトノベル", "light novel")),
    ("漫畫", ("漫畫", "コミック", "comic", "manga")),
    ("小說", ("小說", "fiction", "novel")),
    ("文學", ("文學", "literary fiction", "literature")),
    ("推理", ("推理", "本格", "mystery")),
    ("懸疑", ("懸疑", "懸疑小說", "suspense")),
    ("犯罪", ("犯罪", "crime")),
    ("驚悚", ("驚悚", "thriller")),
    ("恐怖", ("恐怖", "horror")),
    ("科幻", ("科幻", "science fiction", "sci-fi", "sf")),
    ("奇幻", ("奇幻", "fantasy")),
    ("冒險", ("冒險", "adventure")),
    ("異能", ("異能", "超能力", "特殊能力")),
    ("言情", ("言情", "愛情小說", "romance")),
    ("BL", ("BL", "耽美", "boy's love", "boys love")),
    ("百合", ("百合", "GL", "girls love")),
    ("歷史", ("歷史", "史實", "historical")),
    ("戰記", ("戰記", "戰爭", "war story")),
    ("軍事", ("軍事", "military")),
    ("傳記", ("傳記", "回憶錄", "memoir", "biography")),
    ("散文", ("散文", "essay", "essays")),
    ("詩", ("詩集", "poetry", "poem")),
    ("科普", ("科普", "popular science")),
    ("心理", ("心理", "psychology")),
    ("商管", ("商管", "business", "management")),
    ("政治", ("政治", "politics")),
    ("社會", ("社會", "society")),
    ("經濟", ("經濟", "economics")),
    ("兒童", ("童書", "兒童", "children")),
    ("青少年", ("青少年", "young adult", "YA")),
]


AWARD_PATTERNS: list[tuple[str, tuple[str, ...], bool]] = [
    ("諾貝爾文學獎", ("諾貝爾文學獎", "Nobel Prize in Literature"), True),
    ("布克獎", ("布克獎", "Booker Prize"), True),
    ("國際布克獎", ("國際布克獎", "International Booker Prize"), True),
    ("普立茲獎", ("普立茲獎", "Pulitzer Prize"), True),
    ("美國國家圖書獎", ("美國國家圖書獎", "National Book Award"), True),
    ("國際都柏林文學獎", ("國際都柏林文學獎", "Dublin Literary Award", "IMPAC Dublin"), True),
    ("女性小說獎", ("女性小說獎", "Women's Prize for Fiction", "Orange Prize"), True),
    ("龔古爾獎", ("龔古爾獎", "Prix Goncourt", "Goncourt"), True),
    ("費米娜獎", ("費米娜獎", "Prix Femina", "Femina"), True),
    ("勒諾多獎", ("勒諾多獎", "Prix Renaudot", "Renaudot"), True),
    ("雨果獎", ("雨果獎", "Hugo Award"), True),
    ("星雲獎", ("星雲獎", "Nebula Award"), True),
    ("軌跡獎", ("軌跡獎", "Locus Award"), True),
    ("世界奇幻獎", ("世界奇幻獎", "World Fantasy Award"), True),
    ("愛倫坡獎", ("愛倫坡獎", "Edgar Award"), True),
    ("匕首獎", ("匕首獎", "Dagger Award", "Gold Dagger"), True),
    ("紐伯瑞獎", ("紐伯瑞獎", "Newbery Medal", "Newbery Honor"), True),
    ("凱迪克獎", ("凱迪克獎", "Caldecott Medal", "Caldecott Honor"), True),
    ("卡內基獎", ("卡內基獎", "Carnegie Medal"), True),
    ("安徒生獎", ("安徒生獎", "Hans Christian Andersen Award"), True),
    ("林格倫紀念獎", ("林格倫紀念獎", "Astrid Lindgren Memorial Award"), True),
    ("芥川獎", ("芥川獎", "芥川賞", "Akutagawa Prize"), False),
    ("直木獎", ("直木獎", "直木賞", "Naoki Prize"), False),
    ("本屋大賞", ("本屋大賞", "Japan Booksellers' Award"), False),
]


TRUSTED_AWARD_RECORD_DOMAINS = {
    "wikipedia.org": "Wikipedia",
    "wikidata.org": "Wikidata",
    "nobelprize.org": "Nobel Prize",
    "thebookerprizes.com": "The Booker Prizes",
    "pulitzer.org": "The Pulitzer Prizes",
    "nationalbook.org": "National Book Foundation",
    "dublinliteraryaward.ie": "Dublin Literary Award",
    "womensprize.com": "Women's Prize",
    "academiegoncourt.com": "Académie Goncourt",
    "thehugoawards.org": "Hugo Awards",
    "sfwa.org": "SFWA Nebula Awards",
    "nebulas.sfwa.org": "SFWA Nebula Awards",
    "theedgars.com": "Edgar Awards",
    "thecwa.co.uk": "Crime Writers' Association",
    "ala.org": "American Library Association",
    "ibby.org": "IBBY",
    "alma.se": "Astrid Lindgren Memorial Award",
    "carnegiegreenaway.org.uk": "Carnegie Greenaway",
}


WINNER_WORDS = (
    "得獎",
    "獲獎",
    "獲得",
    "榮獲",
    "奪得",
    "摘下",
    "winner",
    "won",
    "award-winning",
)
FINALIST_WORDS = (
    "入圍",
    "決選",
    "短名單",
    "長名單",
    "提名",
    "入選",
    "finalist",
    "shortlisted",
    "longlisted",
    "nominee",
)


def infer_tags(metadata: BookMetadata, extra_text: str | None = None) -> TagInference:
    """Infer concise Calibre tags from metadata and page text.

    Award words in store blurbs are intentionally ignored here. Award tags are
    only added by infer_awards_from_trusted_record() when the current source is
    itself a trusted award-record page.
    """

    text = _join_text(
        [
            metadata.title,
            metadata.subtitle,
            *metadata.authors,
            *metadata.translators,
            metadata.publisher,
            metadata.description,
            *(metadata.tags or []),
            extra_text,
        ]
    )
    tags = _dedupe(short_tags(metadata.tags))

    for tag, needles in REGION_PATTERNS:
        if _contains_any(text, needles):
            _append(tags, tag)

    for tag, needles in GENRE_PATTERNS:
        if _contains_any(text, needles):
            _append(tags, tag)

    return TagInference(tags=tags[:12], awards=[])


def infer_awards_from_trusted_record(
    source_url: str,
    metadata: BookMetadata,
    page_text: str | None,
) -> list[AwardMatch]:
    source_name = trusted_award_record_source(source_url)
    if not source_name:
        return []
    text = clean_text(page_text)
    if not text or not _mentions_work(metadata, text):
        return []
    awards = []
    for award in detect_awards(text):
        awards.append(
            AwardMatch(
                name=award.name,
                status=award.status,
                evidence=award.evidence,
                international=award.international,
                source_name=source_name,
                source_url=source_url,
            )
        )
    return awards


def detect_awards(text: str | None) -> list[AwardMatch]:
    text = clean_text(text)
    if not text:
        return []
    matches: list[AwardMatch] = []
    seen: set[tuple[str, str]] = set()
    used_spans: list[tuple[int, int]] = []
    patterns = sorted(AWARD_PATTERNS, key=lambda item: max(len(alias) for alias in item[1]), reverse=True)
    for award_name, aliases, international in patterns:
        for alias in sorted(aliases, key=len, reverse=True):
            for match in re.finditer(re.escape(alias), text, flags=re.I):
                span = match.span()
                if any(_overlaps(span, used) for used in used_spans):
                    continue
                evidence = _window(text, match.start(), match.end())
                status = _award_status(evidence)
                if not status:
                    continue
                key = (award_name, status)
                if key in seen:
                    continue
                seen.add(key)
                used_spans.append(span)
                matches.append(
                    AwardMatch(
                        name=award_name,
                        status=status,
                        evidence=evidence,
                        international=international,
                    )
                )
    return matches


def awards_as_dict(awards: Iterable[AwardMatch]) -> list[dict[str, object]]:
    return [
        {
            "name": award.name,
            "status": award.status,
            "international": award.international,
            "evidence": award.evidence,
            "source_name": award.source_name,
            "source_url": award.source_url,
        }
        for award in awards
    ]


def apply_awards_to_tags(tags: list[str], awards: Iterable[AwardMatch]) -> list[str]:
    for award in awards:
        if award.status == "winner":
            _append(tags, "得獎作品")
        elif award.status in {"finalist", "longlist"}:
            _append(tags, "入圍作品")
        if award.international:
            _append(tags, "國際大獎")
        _append(tags, award.name)
    return tags[:12]


def trusted_award_record_source(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, name in TRUSTED_AWARD_RECORD_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def _award_status(evidence: str) -> str | None:
    lowered = evidence.lower()
    if any(word.lower() in lowered for word in WINNER_WORDS):
        return "winner"
    if any(word.lower() in lowered for word in FINALIST_WORDS):
        if any(word in evidence for word in ("長名單", "longlisted")):
            return "longlist"
        return "finalist"
    return None


def _join_text(values: Iterable[str | None]) -> str:
    return " ".join(value for value in (clean_text(v) for v in values if v) if value)


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    text_lower = text.lower()
    return any(needle.lower() in text_lower for needle in needles)


def _mentions_work(metadata: BookMetadata, text: str) -> bool:
    text_lower = text.lower()
    if metadata.title and metadata.title.lower() in text_lower:
        return True
    return any(author.lower() in text_lower for author in metadata.authors)


def _append(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _window(text: str, start: int, end: int, size: int = 40) -> str:
    return text[max(0, start - size) : min(len(text), end + size)]


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]
