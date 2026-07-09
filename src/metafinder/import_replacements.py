from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path

from metafinder.normalize import CUSTOM_REPLACEMENTS_FILE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="metafinder-import-replacements",
        description="Import tab-separated custom replacements into the bundled TSV file.",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="one or more prepared txt/tsv files")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=CUSTOM_REPLACEMENTS_FILE,
        help="destination TSV file",
    )
    args = parser.parse_args(argv)

    replacements = load_replacements([args.output, *args.inputs])
    write_replacements(args.output, replacements)
    print(f"Imported {len(replacements)} replacements into {args.output}")
    return 0


def load_replacements(paths: list[Path]) -> OrderedDict[str, str]:
    replacements: OrderedDict[str, str] = OrderedDict()
    for path in paths:
        if not path.exists():
            continue
        for source, target in _iter_replacement_lines(path):
            if source in replacements:
                del replacements[source]
            replacements[source] = target
    return replacements


def write_replacements(path: Path, replacements: OrderedDict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(f"{source}\t{target}\n" for source, target in replacements.items())
    path.write_text(content, encoding="utf-8")


def _iter_replacement_lines(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "\t" not in line:
                continue
            source, target = line.split("\t", 1)
            source = source.strip()
            target = target.strip().split()[0] if target.strip() else ""
            if not source or not target:
                continue
            yield source, target


if __name__ == "__main__":
    raise SystemExit(main())
