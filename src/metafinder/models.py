from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BookMetadata:
    title: str | None = None
    subtitle: str | None = None
    authors: list[str] = field(default_factory=list)
    translators: list[str] = field(default_factory=list)
    publisher: str | None = None
    published_date: str | None = None
    isbn: str | None = None
    eisbn: str | None = None
    language: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    awards: list[dict[str, Any]] = field(default_factory=list)
    cover_url: str | None = None

    def completeness_score(self) -> int:
        score = 0
        for value in [
            self.title,
            self.publisher,
            self.published_date,
            self.isbn or self.eisbn,
            self.description,
            self.cover_url,
        ]:
            if value:
                score += 1
        score += min(len(self.authors), 2)
        score += min(len(self.tags), 3)
        return score

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "authors": self.authors,
            "translators": self.translators,
            "publisher": self.publisher,
            "published_date": self.published_date,
            "isbn": self.isbn,
            "eisbn": self.eisbn,
            "language": self.language,
            "description": self.description,
            "tags": self.tags,
            "awards": self.awards,
            "cover_url": self.cover_url,
        }


@dataclass
class BookCandidate:
    source_name: str
    source_url: str
    source_kind: str
    metadata: BookMetadata
    score: float = 0
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "source_kind": self.source_kind,
            "score": round(self.score, 2),
            "evidence": self.evidence,
            "cover_url": self.metadata.cover_url,
            "metadata": self.metadata.as_dict(),
        }
