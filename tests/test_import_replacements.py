from pathlib import Path

from metafinder.import_replacements import load_replacements, write_replacements


def test_load_replacements_merges_and_overrides(tmp_path: Path):
    existing = tmp_path / "existing.tsv"
    existing.write_text("舊詞\t舊譯\n", encoding="utf-8")

    prepared = tmp_path / "prepared.txt"
    prepared.write_text(
        "# comment\n"
        "\n"
        "原詞\t翻譯 其他\n"
        "舊詞\t新譯\n",
        encoding="utf-8",
    )

    replacements = load_replacements([existing, prepared])
    assert list(replacements.items()) == [("原詞", "翻譯"), ("舊詞", "新譯")]


def test_write_replacements_round_trips(tmp_path: Path):
    output = tmp_path / "out.tsv"
    write_replacements(output, {"原詞": "翻譯", "另一詞": "另一譯"})
    assert output.read_text(encoding="utf-8") == "原詞\t翻譯\n另一詞\t另一譯\n"
