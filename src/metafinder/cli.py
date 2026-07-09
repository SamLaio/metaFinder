from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

from metafinder.finder import MetadataFinder
from metafinder.sources.web_search import USER_AGENT


def main(argv: list[str] | None = None) -> int:
    _prefer_utf8_stdio()
    parser = argparse.ArgumentParser(prog="metafinder")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="search metadata candidates by title, author, ISBN, or URL")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.add_argument("--json", action="store_true", help="print JSON instead of a compact table")
    search.add_argument("--download-cover", type=Path, help="download the best candidate cover to this path")

    args = parser.parse_args(argv)
    if args.command == "search":
        return _search(args)
    return 2


def _prefer_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def _search(args: argparse.Namespace) -> int:
    finder = MetadataFinder()
    candidates = finder.search(args.query, limit=args.limit)
    if args.json:
        print(json.dumps([c.as_dict() for c in candidates], ensure_ascii=False, indent=2))
    else:
        _print_table(candidates)
    if args.download_cover:
        _download_best_cover(candidates, args.download_cover)
    return 0 if candidates else 1


def _print_table(candidates) -> None:
    if not candidates:
        print("No candidates found.")
        return
    for index, candidate in enumerate(candidates, 1):
        meta = candidate.metadata
        authors = "、".join(meta.authors) if meta.authors else "-"
        ids = " / ".join(v for v in [meta.isbn, meta.eisbn] if v) or "-"
        print(f"[{index}] score={candidate.score:.1f} {candidate.source_name} ({candidate.source_kind})")
        print(f"    title: {meta.title or '-'}")
        print(f"    authors: {authors}")
        print(f"    publisher/date: {meta.publisher or '-'} / {meta.published_date or '-'}")
        print(f"    isbn: {ids}")
        print(f"    tags: {'、'.join(meta.tags) if meta.tags else '-'}")
        if meta.awards:
            awards = "、".join(f"{a.get('name')}:{a.get('status')}" for a in meta.awards)
            print(f"    awards: {awards}")
        print(f"    cover: {meta.cover_url or '-'}")
        print(f"    url: {candidate.source_url}")


def _download_best_cover(candidates, output: Path) -> None:
    for candidate in candidates:
        cover_url = candidate.metadata.cover_url
        if not cover_url:
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(cover_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        output.write_bytes(response.content)
        print(f"Downloaded cover: {output}", file=sys.stderr)
        return
    raise SystemExit("No cover URL found in candidates.")


if __name__ == "__main__":
    raise SystemExit(main())
