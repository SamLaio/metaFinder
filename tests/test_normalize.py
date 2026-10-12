from metafinder.normalize import (
    clean_description,
    clean_text,
    normalize_isbn,
    extract_labeled_isbns,
    normalize_publisher,
    short_tags,
    split_people,
    volume_title_from_trailing_number,
)
from metafinder.models import BookMetadata
from metafinder.tags import (
    author_region_tags,
    apply_awards_to_tags,
    detect_awards,
    infer_awards_from_trusted_record,
    infer_tags,
)


def test_normalize_isbn():
    assert normalize_isbn("ISBN：978-626-315-175-8") == "9786263151758"
    assert normalize_isbn("4717702110444") is None
    assert normalize_isbn("1230004974352") is None
    assert normalize_isbn("978626315175X") is None
    assert normalize_isbn("9577417477") == "9577417477"


def test_explicit_eisbn_labels_formats_and_ambiguity():
    assert extract_labeled_isbns("ISBN 978-626-7428-59-7 EISBN 978-6267428566（PDF） EISBN 978-6267428573（EPUB）") == {
        "isbn": "9786267428597", "eisbn": "9786267428573"}
    for text in ("EISBN (EPUB)：9786269754168", "電子書ISBN　9786269754168", "電子版 ISBN：9786269754168"):
        assert extract_labeled_isbns(text) == {"eisbn": "9786269754168"}
    assert extract_labeled_isbns("EISBN：9786269754168 EISBN：9786269817740") == {}
    assert extract_labeled_isbns("ISBN：4717702110444") == {}
    assert extract_labeled_isbns("EISBN (PDF)：9786269754168 (EPUB)") == {}
    assert extract_labeled_isbns("ISBN：9789863845829 (EPUB) ISBN：9789863845782 ( EPUB ) ISBN：9789863845812 ( PDF )") == {}


def test_linking_publisher_company_aliases():
    for name in ("聯經出版事業股份有限公司", "聯經出版社", "聯經"):
        assert normalize_publisher(name) == "聯經出版"


def test_split_people():
    assert split_people("作者：九井諒子／譯者：望") == ["九井諒子", "望"]


def test_short_tags():
    assert short_tags(["都市異能、特種兵、保鏢"]) == ["都市異能", "特種兵", "保鏢"]


def test_clean_text_decodes_html_entities():
    assert clean_text("&#x6211;&#x7368;&#x81EA;&#x5347;&#x7D1A;") == "我獨自升級"
    assert clean_text("Head\x00First") == "Head First"


def test_split_people_normalizes_middle_dot_for_chinese_author_names():
    assert split_people("戴維·王") == ["戴維．王"]
    assert split_people("羅蘭・巴特") == ["羅蘭．巴特"]
    assert split_people("夏洛特‧亨利") == ["夏洛特．亨利"]
    assert split_people("J · W · 奧克") == ["J．W．奧克"]


def test_custom_replacements_apply_after_opencc():
    assert clean_text("一出") == "一出"
    assert clean_text("实时") == "即時"
    assert clean_text("信息") == "信息"


def test_already_traditional_published_names_are_not_reconverted():
    for text in ('三采文化', '采藝出版', '簡郁璇', '許郁文', '杜筑生', '山本周五郎賞', '安東尼．聖修伯里'):
        assert clean_text(text) == text
    assert clean_description('帶回祕密\n\n三采文化') == '帶回祕密\n\n三采文化'


def test_normalize_publisher_aliases_match_calibre_db():
    assert normalize_publisher("聯經出版公司") == "聯經出版"
    assert normalize_publisher("東立出版社") == "東立出版"
    assert normalize_publisher("東立") == "東立出版"
    assert normalize_publisher("城邦出版集團 麥田") == "麥田出版"
    assert normalize_publisher("英屬維京群島商高寶國際有限公司台灣分公司") == "高寶"


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
        tags=["韓國"],
    )
    result = infer_tags(meta)
    assert "韓國" in result.tags
    assert "奇幻" in result.tags
    assert "冒險" in result.tags
    assert "異能" in result.tags
    assert "小說" in result.tags


def test_clean_description_preserves_paragraph_breaks():
    assert clean_description("第一段\n\n第二段\r\n第三段") == "第一段\n\n第二段\n第三段"


def test_region_tags_do_not_come_from_description_places():
    meta = BookMetadata(description="故事橫跨美國、英國與義大利，是一部懸疑小說。")
    result = infer_tags(meta)
    assert "美國" not in result.tags
    assert "英國" not in result.tags
    assert "義大利" not in result.tags
    assert "懸疑" in result.tags
    assert "小說" in result.tags


def test_infer_portugal_region_from_source_tags():
    meta = BookMetadata(tags=["葡萄牙"], description="諾貝爾文學獎得主的小說。")
    result = infer_tags(meta)
    assert "葡萄牙" in result.tags
    assert "小說" in result.tags


def test_author_region_tags_use_confirmed_names_and_unambiguous_scripts():
    assert author_region_tags(["棚架ユウ", "김영하", "王小明"]) == ["日本", "韓國"]
    assert author_region_tags(["原作：貞本義行"]) == ["日本"]
    assert author_region_tags(["岡田和人"]) == ["日本"]
    assert author_region_tags(["蔡小雀", "陳鴻圖", "藤井太洋"]) == ["臺灣", "日本"]
    assert "美國" in infer_tags(BookMetadata(authors=["娥蘇拉．勒瑰恩"])).tags
    assert author_region_tags(["清水晴木", "作者：蒼葵", "愛德華．狄波諾"]) == ["日本", "臺灣", "馬爾他"]
    assert author_region_tags(["蝸牛"]) == []


def test_region_tags_do_not_come_from_local_publisher():
    meta = BookMetadata(
        title="LV999的村民",
        publisher="臺灣角川",
        description="日本輕小說譯本，職業雖弱卻強到極致的小村民展開冒險。",
    )
    result = infer_tags(meta)
    assert "臺灣" not in result.tags
    assert "日本" not in result.tags
    assert "輕小說" in result.tags
    assert "冒險" in result.tags


def test_confirmed_batch_author_regions_preserve_ambiguous_names():
    assert author_region_tags(["鈴木央", "佐島勤", "佐島 勤"]) == ["日本"]
    assert author_region_tags(["薛西斯", "史邁", "莎莉．索恩"]) == ["臺灣", "中國", "澳洲"]
    assert author_region_tags(["張貴興", "卡爾．古斯塔夫．榮格", "加布列．賈西亞．馬奎斯"]) == ["馬來西亞", "瑞士", "哥倫比亞"]
    assert author_region_tags(["R．A．薩爾瓦多", "丹尼斯．鄧肯", "王小明", "小手"]) == ["美國", "英國"]
    assert infer_tags(BookMetadata(tags=["Swiss", "Malaysian", "Colombian"])).tags[-3:] == ["瑞士", "哥倫比亞", "馬來西亞"]


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


def test_bare_bl_from_store_chrome_does_not_become_tag():
    meta = BookMetadata(
        title="金牌得主",
        description="出版社：東立出版社。花式滑冰漫畫。頁面導覽包含 BL 大哉問。",
    )
    result = infer_tags(meta)
    assert "漫畫" in result.tags
    assert "BL" not in result.tags


def test_incidental_military_word_does_not_create_military_tag():
    result = infer_tags(BookMetadata(description="中秋烤肉萬家香，卻有軍事狂兔下凡來炸場。"))
    assert "軍事" not in result.tags


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
