from metafinder.series import infer_series_from_title, series_evidence_priority


def assert_series(title: str, name: str, index: float) -> None:
    series = infer_series_from_title(title)
    assert series is not None
    assert series.name == name
    assert series.index == index


def test_tilde_chinese_ordinal_series():
    assert_series("巧玉玲瓏～鳳凰奇俠之五", "鳳凰奇俠", 5.0)


def test_latin_no_series():
    assert_series("木頭猛男追新娘～City Hunter NO.4（2022電子版）", "City Hunter", 4.0)


def test_bracket_part_series():
    assert_series("寶貝大猛男(下)【小肥肥的猛男日記 PART9】", "小肥肥的猛男日記", 9.0)


def test_title_part_series():
    assert_series("黑魔王傳說 Part 2", "黑魔王傳說", 2.0)


def test_split_volume_series():
    assert_series("龍王(下)", "龍王", 3.0)


def test_parenthesized_direct_series_volume():
    assert_series("賊頭大老板 (小肥肥的猛男日記1)", "小肥肥的猛男日記", 1.0)


def test_series_evidence_priority_prefers_bibliography_over_weak_split():
    assert series_evidence_priority("小肥肥的猛男日記", "millionbook-black") > series_evidence_priority(
        "寶貝大猛男", "title:split-volume"
    )


def test_series_evidence_priority_demotes_generic_external_category():
    assert series_evidence_priority("一家都是寶", "title:trailing-volume") > series_evidence_priority(
        "溫馨", "cxyqw-guling"
    )
