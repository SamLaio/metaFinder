from __future__ import annotations

from typing import Any

import requests

from metafinder.models import BookCandidate, BookMetadata
from metafinder.normalize import clean_text, clean_title, normalize_isbn, split_people
from metafinder.sources.web_search import USER_AGENT


def lookup_openlibrary_isbn(isbn: str, timeout: float = 5.0) -> BookCandidate | None:
    isbn = normalize_isbn(isbn) or ""
    if not isbn:
        return None
    url = f"https://openlibrary.org/isbn/{isbn}.json"
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    metadata = BookMetadata(
        title=clean_title(data.get("title")),
        subtitle=clean_text(data.get("subtitle")),
        authors=_authors(data, timeout=timeout),
        publisher=clean_text(_first(data.get("publishers"))),
        published_date=clean_text(data.get("publish_date")),
        isbn=isbn,
        cover_url=_cover_url(data),
    )
    if not metadata.title:
        return None
    score = 34 + metadata.completeness_score() * 4
    return BookCandidate(
        source_name="Open Library",
        source_url=f"https://openlibrary.org/isbn/{isbn}",
        source_kind="catalog",
        metadata=metadata,
        score=float(score),
        evidence=["openlibrary-isbn"],
    )


def _authors(data: dict[str, Any], timeout: float) -> list[str]:
    names: list[str] = []
    for item in data.get("authors") or []:
        key = item.get("key") if isinstance(item, dict) else None
        if not key:
            continue
        try:
            response = requests.get(f"https://openlibrary.org{key}.json", headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
            name = clean_text(response.json().get("name"))
        except Exception:
            name = None
        if name:
            names.append(name)
    return split_people(names)


def _cover_url(data: dict[str, Any]) -> str | None:
    cover = _first(data.get("covers"))
    if cover:
        return f"https://covers.openlibrary.org/b/id/{cover}-L.jpg"
    return None


def _first(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value
