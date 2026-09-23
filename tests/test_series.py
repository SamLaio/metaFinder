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
def test_trailing_multi_digit_volume_is_not_split_into_series_name():
    assert_series("百鍊霸王與聖約女武神16", "百鍊霸王與聖約女武神", 16.0)
    assert_series("百鍊霸王與聖約女武神０６", "百鍊霸王與聖約女武神", 6.0)
    assert infer_series_from_title("東京1984") is None


def test_chinese_juan_volume_strips_juan_and_accepts_final_marker():
    assert_series("裏八仙 卷三", "裏八仙", 3.0)
    assert_series("裏八仙 卷四（終）", "裏八仙", 4.0)
