from metafinder.normalize import (
    clean_text,
    normalize_isbn,
    short_tags,
    split_people,
    volume_title_from_trailing_number,
)
from metafinder.models import BookMetadata
from metafinder.tags import (
    apply_awards_to_tags,
    detect_awards,
    infer_awards_from_trusted_record,
    infer_tags,
)


def test_normalize_isbn():
    assert normalize_isbn("ISBN：978-626-315-175-8") == "9786263151758"


def test_split_people():
    assert split_people("作者：九井諒子／譯者：望") == ["九井諒子", "望"]


def test_short_tags():
    assert short_tags(["都市異能、特種兵、保鏢"]) == ["都市異能", "特種兵", "保鏢"]


def test_clean_text_decodes_html_entities():
    assert clean_text("&#x6211;&#x7368;&#x81EA;&#x5347;&#x7D1A;") == "我獨自升級"


def test_custom_replacements_apply_after_opencc():
    assert clean_text("一出") == "一齣"


def test_volume_title_from_trailing_number():
    info = volume_title_from_trailing_number("瞬間治癒卻被當成廢物踢出隊伍的天才治療師，改當無照治療師快樂過活8")
    assert info is not None
    assert info.display_title == "08 瞬間治癒卻被當成廢物踢出隊伍的天才治療師，改當無照治療師快樂過活"
    assert info.series_title == "瞬間治癒卻被當成廢物踢出隊伍的天才治療師，改當無照治療師快樂過活"
    assert info.series_index == 8.0


def test_infer_tags_from_metadata_text():
    meta = BookMetadata(
        title="我獨自升級",
        authors=["Chugong"],
        publisher="知翎文化",
        description="韓國奇幻冒險小說，描述獵人與地下城的異能戰鬥。",
    )
    result = infer_tags(meta)
    assert "韓國" in result.tags
    assert "奇幻" in result.tags
    assert "冒險" in result.tags
    assert "異能" in result.tags
    assert "小說" in result.tags


def test_detect_international_award_winner():
    awards = detect_awards("本書榮獲 International Booker Prize，並入圍多項年度選書。")
    assert awards
    assert awards[0].name == "國際布克獎"
    assert awards[0].status == "winner"
    assert awards[0].international is True


def test_award_name_without_award_context_is_not_enough():
    assert detect_awards("作者曾擔任 Booker Prize 評審，本書討論文學獎制度。") == []


def test_award_words_in_store_text_do_not_become_tags():
    meta = BookMetadata(description="入圍 Hugo Award 短名單的科幻小說。")
    result = infer_tags(meta)
    assert "科幻" in result.tags
    assert "雨果獎" not in result.tags
    assert "國際大獎" not in result.tags
    assert "得獎作品" not in result.tags


def test_awards_require_current_source_to_be_trusted_record():
    meta = BookMetadata(title="Example Book", authors=["Example Author"])
    text = "Example Book by Example Author won Hugo Award."
    assert infer_awards_from_trusted_record("https://example.com/book", meta, text) == []
    awards = infer_awards_from_trusted_record(
        "https://www.thehugoawards.org/hugo-history/",
        meta,
        text,
    )
    assert awards
    tags = apply_awards_to_tags(["科幻"], awards)
    assert "雨果獎" in tags
    assert "國際大獎" in tags
    assert "得獎作品" in tags
