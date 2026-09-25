from metafinder.finder import MetadataFinder, _candidate_matches_any_query_variant, _candidate_matches_query, _candidate_query_rank, _is_probably_book_page, _query_variants, _site_query_variants, _web_queries
from metafinder.models import BookCandidate, BookMetadata
from metafinder.sources.generic import GenericPageParser
from metafinder.sources.site_search import _matches_book_url, _strip_tracking, search_source_candidates
from metafinder.sources import web_search
from metafinder.sources.web_search import SearchResult


def candidate(title: str, authors: list[str], score: float) -> BookCandidate:
    return BookCandidate(
        source_name="test",
        source_url="https://example.invalid/book",
        source_kind="other",
        metadata=BookMetadata(title=title, authors=authors),
        score=score,
    )


def test_default_search_budget_is_safe_for_batch_use():
    finder = MetadataFinder()

    assert finder.request_timeout == 3.0
    assert finder.max_search_seconds == 12.0
    assert finder.max_search_seconds < 20
    assert finder.max_web_queries == 4


def test_placeholder_identifier_does_not_search_for_an_unrelated_book(monkeypatch):
    finder = MetadataFinder()
    monkeypatch.setattr(finder, "_collect_urls", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不應搜尋")))

    assert finder.search("xxxx-xxxx") == []


def test_query_variants_strip_trailing_latin_author_alias():
    assert "集合體 娜塔夏‧ 布朗" in _query_variants("集合體 娜塔夏‧ 布朗（Natasha Brown）")


def test_query_variants_strip_trailing_quoted_marketing_blurb():
    variants = _query_variants("龍與地下鐵（「文字鬼才」馬伯庸大開腦洞之作） 馬伯庸")
    assert variants[0] == "龍與地下鐵 馬伯庸"


def test_query_variants_strip_trailing_series_ordinal_and_keep_author():
    variants = _query_variants("泥老虎～三人成虎之一 蔡小雀")
    assert variants[0] == "泥老虎 蔡小雀"
    assert "泥老虎 蔡小雀" in variants


def test_series_ordinal_query_variant_is_used_for_candidate_filtering():
    found = candidate("泥老虎", ["蔡小雀"], 70)
    assert _candidate_matches_any_query_variant(found, "泥老虎～三人成虎之一 蔡小雀")


def test_author_alias_and_middle_dot_variants_match_candidate():
    candidate_with_taiwan_name = candidate("集合體", ["娜塔夏．布朗"], 70)

    assert _candidate_matches_query(candidate_with_taiwan_name, "集合體 娜塔夏‧ 布朗（Natasha Brown）")


def test_ranking_prefers_a_substantive_description_over_a_truncated_preview():
    parser = GenericPageParser()
    common = dict(title="怪島奇譚 2", publisher="蓋亞文化", isbn="9786263843578", cover_url="https://example.invalid/cover.jpg")
    preview = BookMetadata(**common, description="與島共生，妖異為伴……")
    full = BookMetadata(**common, description="完整故事簡介。" * 40)

    assert parser._score(full, "store") > parser._score(preview, "store")


def test_compact_trailing_volume_matches_spaced_query_volume():
    compact = candidate("怪島奇譚02", ["張季雅"], 75)
    spaced = candidate("怪島奇譚 2", ["張季雅"], 70)

    assert _candidate_query_rank(compact, "怪島奇譚 2 張季雅") >= _candidate_query_rank(spaced, "怪島奇譚 2 張季雅")


def test_trailing_volume_before_author_rejects_other_volume_candidates():
    assert _candidate_matches_query(candidate("農林14", ["白鳥士郎"], 75), "農林14 白鳥士郎")
    assert not _candidate_matches_query(candidate("農林12", ["白鳥士郎"], 75), "農林14 白鳥士郎")
    assert not _candidate_matches_query(
        candidate("帶著外掛轉生為公會櫃臺小姐06", ["夏にコタツ"], 75),
        "帶著外掛轉生為公會櫃台小姐2.5 Fateful Encounter 夏にコタツ",
    )
    assert not _candidate_matches_any_query_variant(
        candidate("農林12", ["白鳥士郎"], 75), "農林14 白鳥士郎"
    )


def test_single_volume_does_not_match_bundle_with_same_count():
    for title in ("神鵰俠侶(全四冊)", "神鵰俠侶 全4册", "神鵰俠侶 套書"):
        assert not _candidate_matches_query(candidate(title, ["金庸"], 100), "04 神鵰俠侶 金庸")
    assert _candidate_matches_query(candidate("神鵰俠侶(4)", ["金庸"], 100), "04 神鵰俠侶 金庸")
    assert _candidate_matches_query(candidate("神鵰俠侶(全四冊)", ["金庸"], 100), "神鵰俠侶 全四冊")


def test_books_requests_are_throttled(monkeypatch):
    sleeps = []
    requested = []

    class Response:
        pass

    monkeypatch.setattr(web_search, "_last_books_request_at", 10.0)
    monkeypatch.setattr(web_search.time, "monotonic", lambda: 11.0)
    monkeypatch.setattr(web_search.time, "sleep", sleeps.append)
    monkeypatch.setattr(web_search.requests, "get", lambda url, **kwargs: requested.append(url) or Response())

    web_search.polite_get("https://www.books.com.tw/products/0010912143")

    assert sleeps == [2.0]
    assert requested == ["https://www.books.com.tw/products/0010912143"]


def test_non_books_requests_are_not_throttled(monkeypatch):
    sleeps = []

    class Response:
        pass

    monkeypatch.setattr(web_search, "_last_books_request_at", 10.0)
    monkeypatch.setattr(web_search.time, "sleep", sleeps.append)
    monkeypatch.setattr(web_search.requests, "get", lambda url, **kwargs: Response())

    web_search.polite_get("https://readmoo.com/book/210213305000101")

    assert sleeps == []


def test_store_search_result_is_hydrated_with_product_page_metadata(monkeypatch):
    summary = BookCandidate(
        source_name="博客來",
        source_url="https://www.books.com.tw/products/0010767953",
        source_kind="store",
        metadata=BookMetadata(
            title="世界史聞不出的藥水味",
            authors=["譚健鍬"],
            isbn="9789571371801",
            cover_url="https://example.test/cover.jpg",
        ),
        score=42,
        evidence=["books-search-result"],
    )
    detail = BookCandidate(
        source_name="博客來",
        source_url=summary.source_url,
        source_kind="store",
        metadata=BookMetadata(
            title="世界史聞不出的藥水味：那些外國名人的生老病死",
            authors=["譚健鍬"],
            publisher="時報出版",
            isbn="9789571371801",
            tags=["人文社科"],
        ),
        score=70,
        evidence=["json-ld", "meta-tags"],
    )
    finder = MetadataFinder(max_search_seconds=3)
    monkeypatch.setattr("metafinder.finder.lookup_openlibrary_isbn", lambda *args, **kwargs: None)
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [summary])
    monkeypatch.setattr(finder, "_collect_urls", lambda *args, **kwargs: [])
    monkeypatch.setattr(finder.parser, "parse_url", lambda *args, **kwargs: detail)

    result = finder.search("世界史聞不出的藥水味 譚健鍬")

    assert result == [detail]
    assert result[0].metadata.tags == ["人文社科"]
    assert result[0].metadata.publisher == "時報出版"


def test_isbn_search_card_continues_to_product_detail_sources(monkeypatch):
    summary = BookCandidate(
        source_name="博客來",
        source_url="https://www.books.com.tw/products/0010767953",
        source_kind="store",
        metadata=BookMetadata(title="世界史聞不出的藥水味", isbn="9789571371801"),
        score=42,
        evidence=["books-search-result"],
    )
    detail = BookCandidate(
        source_name="三民網路書店",
        source_url="https://www.sanmin.com.tw/product/index/0010767953",
        source_kind="store",
        metadata=BookMetadata(
            title="世界史聞不出的藥水味：那些外國名人的生老病死",
            authors=["譚健鍬"],
            isbn="9789571371801",
            publisher="時報出版",
        ),
        score=70,
        evidence=["sanmin-page"],
    )
    finder = MetadataFinder(max_search_seconds=3)
    monkeypatch.setattr("metafinder.finder.lookup_openlibrary_isbn", lambda *args, **kwargs: None)
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [summary])
    monkeypatch.setattr(finder, "_collect_urls", lambda *args, **kwargs: [detail.source_url])
    monkeypatch.setattr(
        finder.parser,
        "parse_url",
        lambda url, **kwargs: summary if url == summary.source_url else detail,
    )

    result = finder.search("9789571371801")

    assert detail in result
    assert next(candidate for candidate in result if candidate.source_url == detail.source_url).metadata.publisher == "時報出版"


def test_direct_store_hit_is_parsed_before_slow_query_variants(monkeypatch):
    detail = BookCandidate(
        source_name="三民網路書店",
        source_url="https://www.sanmin.com.tw/product/index/008541880",
        source_kind="store",
        metadata=BookMetadata(title="迷宮飯02", authors=["九井諒子"], publisher="青文", series_index=2),
        score=70,
    )
    finder = MetadataFinder(max_search_seconds=3)
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda *args, **kwargs: [detail.source_url])
    monkeypatch.setattr(finder.parser, "parse_url", lambda *args, **kwargs: detail)
    monkeypatch.setattr(finder, "_collect_urls", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不應進入慢速變體搜尋")))

    assert finder.search("迷宮飯 02 九井諒子") == [detail]


def test_same_product_url_from_store_and_web_search_is_returned_once(monkeypatch):
    detail = BookCandidate(
        source_name="博客來",
        source_url="https://www.books.com.tw/products/0010767953",
        source_kind="store",
        metadata=BookMetadata(
            title="世界史聞不出的藥水味：那些外國名人的生老病死",
            authors=["譚健鍬"],
            isbn="9789571371801",
            tags=["人文社科"],
        ),
        score=70,
        evidence=["json-ld", "meta-tags"],
    )
    finder = MetadataFinder(max_search_seconds=3)
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [detail])
    monkeypatch.setattr(finder, "_collect_urls", lambda *args, **kwargs: [detail.source_url])
    monkeypatch.setattr(finder.parser, "parse_url", lambda *args, **kwargs: detail)

    assert finder.search("世界史聞不出的藥水味 譚健鍬") == [detail]


def test_exact_title_and_author_match_ranks_above_loose_title_token_match():
    query = "新時代，新魔法 衝鴨小程程"
    loose = candidate("小資女向前衝：新時代女性，好命靠自己", ["蘇妃"], 70)
    exact = candidate("新時代，新魔法", ["衝鴨小程程"], 41)

    ranked = sorted([loose, exact], key=lambda c: (_candidate_query_rank(c, query), c.score), reverse=True)

    assert ranked[0] is exact


def test_loose_single_token_match_is_not_relevant_for_title_author_query():
    query = "新時代，新魔法 衝鴨小程程"
    loose = candidate("小資女向前衝：新時代女性，好命靠自己", ["蘇妃"], 70)

    assert not _candidate_matches_query(loose, query)


def test_author_only_match_is_not_relevant_for_title_author_query():
    query = "不及格男佣 黑潔明"
    same_author_other_book = candidate("幸運女郎上錯床～City Hunter NO.2（2022電子版）", ["黑潔明"], 66)

    assert not _candidate_matches_query(same_author_other_book, query)


def test_web_novel_candidate_must_match_trailing_author_when_title_is_short():
    query = "02 異形 艾倫．狄恩．佛斯特"
    wrong_web_novel = BookCandidate(
        source_name="起點中文網",
        source_url="https://m.qidian.com/book/1046552678/",
        source_kind="web-novel",
        metadata=BookMetadata(title="異形", authors=["作者不符"]),
        score=70,
    )

    assert not _candidate_matches_query(wrong_web_novel, query)


def test_store_candidate_must_match_trailing_author():
    wrong_book = candidate("第一次寫劇本就上手", ["衣笠竜屯"], 63)
    wrong_edition = candidate("精靈幻想記02", ["みなづきふたご"], 73)
    manga = candidate("精靈幻想記02", ["北山結莉-原作；みなづきふたご-漫畫"], 73)
    manga.metadata.tags = ["漫畫"]

    assert not _candidate_matches_query(wrong_book, "第一次寫Linux Driver就上手 JOJO")
    assert not _candidate_matches_query(wrong_edition, "02 精靈幻想記 精靈的祝福 北山結莉")
    assert not _candidate_matches_query(manga, "02 精靈幻想記 精靈的祝福 北山結莉")


def test_same_author_and_volume_number_only_is_not_relevant():
    query = "滅亡後的世界06 sing N song"
    same_author_same_volume_other_series = candidate("全知讀者視角06 - sing N song", ["sing N song"], 69)

    assert not _candidate_matches_query(same_author_same_volume_other_series, query)


def test_title_author_suffix_does_not_make_wrong_same_author_book_relevant():
    query = "盲眼刺客（下） 瑪格麗特．愛特伍"
    same_author_other_book = candidate("使女的故事 - 瑪格麗特．愛特伍", ["瑪格麗特．愛特伍"], 73)

    assert not _candidate_matches_query(same_author_other_book, query)


def test_short_title_wrong_same_author_book_is_not_relevant():
    query = "紅王子 提摩希．史奈德"
    same_author_other_book = candidate("血色大地：夾在希特勒與史達林之間的東歐 - 提摩希．史奈德", ["提摩希．史奈德"], 81)

    assert not _candidate_matches_query(same_author_other_book, query)


def test_parenthetical_referenced_book_title_does_not_match_query():
    query = "賈伯斯傳 華特．艾薩克森"
    referenced = candidate("班傑明．富蘭克林：美國心靈的原型（《賈伯斯傳》作者經典鉅作）", ["華特．艾薩克森"], 80)

    assert not _candidate_matches_query(referenced, query)


def test_shared_number_and_generic_title_tokens_are_not_enough():
    query = "21世紀的21位思想家"
    loose = candidate("21世紀的21堂課 - 哈拉瑞", ["哈拉瑞"], 63)

    assert not _candidate_matches_query(loose, query)


def test_author_match_with_title_token_is_relevant_for_title_author_query():
    query = "魔影魅靈5荼蘼香 黑潔明"
    same_author_matching_book = candidate("荼蘼香（上）～魔影魅靈之五", ["黑潔明"], 66)

    assert _candidate_matches_query(same_author_matching_book, query)


def test_traditional_query_matches_simplified_official_title_candidate():
    query = "女神的煩惱 林綿綿"
    official = candidate("女神的烦恼", ["林绵绵"], 40)

    assert _candidate_matches_query(official, query)
    assert _candidate_query_rank(official, query) > 0


def test_jjwxc_wrapped_title_matches_core_title_and_author():
    query = "新時代，新魔法 衝鴨小程程"
    wrapped = candidate("《新時代，新魔法》衝鴨小程程_晉江文學城_【原創小說|言情小說】", ["衝鴨小程程"], 37)
    loose = candidate("小資女向前衝：新時代女性，好命靠自己", ["蘇妃"], 70)

    ranked = sorted([loose, wrapped], key=lambda c: (_candidate_query_rank(c, query), c.score), reverse=True)

    assert ranked[0] is wrapped


def test_collect_urls_searches_with_jjwxc_query_hints(monkeypatch):
    queries: list[str] = []

    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda query, limit, timeout, stop_after_first_hit=False: [])

    def fake_search_web(query: str, limit: int, timeout: float):
        queries.append(query)
        return []

    monkeypatch.setattr("metafinder.finder.search_web", fake_search_web)

    MetadataFinder(per_query_results=1, max_web_queries=8)._collect_urls("新時代，新魔法 衝鴨小程程")

    assert "新時代，新魔法 衝鴨小程程 晉江文學城" in queries
    assert "新時代，新魔法 衝鴨小程程 jjwxc" in queries


def test_limited_web_search_prioritizes_store_sources_before_web_novel_hints():
    queries = _web_queries(["遠野物語 柳田國男"], max_queries=2)

    assert queries == ["遠野物語 柳田國男", "遠野物語 柳田國男 site:books.com.tw"]


def test_kadokawa_imprint_query_reserves_official_search_slot():
    query = "水魔法ぐらいしか取り柄がないけど現代知識があれば充分だよね？ ２ (カドカワBOOKS) mono-zo"

    queries = _web_queries([query], max_queries=2)

    assert queries == [query, query + " site:kadokawa.co.jp"]


def test_kadokawa_imprint_uses_source_search(monkeypatch):
    site_queries: list[str] = []
    web_queries: list[str] = []

    monkeypatch.setattr(
        "metafinder.finder.search_source_sites",
        lambda query, limit, timeout, stop_after_first_hit=False: site_queries.append(query) or [],
    )
    monkeypatch.setattr(
        "metafinder.finder.search_web",
        lambda query, limit, timeout: web_queries.append(query) or [],
    )
    query = "水魔法ぐらいしか取り柄がないけど現代知識があれば充分だよね？ ２ (カドカワBOOKS) mono-zo"

    MetadataFinder(per_query_results=1, max_web_queries=2)._collect_urls(query)

    assert query in site_queries
    assert query + " site:kadokawa.co.jp" in web_queries


def test_kadokawa_imprint_skips_generic_store_cards(monkeypatch):
    monkeypatch.setattr(
        "metafinder.finder.search_source_candidates",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不應查泛用書店卡")),
    )
    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda *args, **kwargs: [])
    monkeypatch.setattr("metafinder.finder.search_web", lambda *args, **kwargs: [])

    assert MetadataFinder(max_web_queries=0).search("水魔法 ２ (カドカワBOOKS) mono-zo") == []


def test_collect_urls_searches_with_fanqie_query_hints(monkeypatch):
    queries: list[str] = []

    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda query, limit, timeout, stop_after_first_hit=False: [])

    def fake_search_web(query: str, limit: int, timeout: float):
        queries.append(query)
        return []

    monkeypatch.setattr("metafinder.finder.search_web", fake_search_web)

    MetadataFinder(per_query_results=1, max_web_queries=14)._collect_urls("被勾錯魂，我帶侯爺搬空京城流放 巒鏡")

    assert "被勾錯魂，我帶侯爺搬空京城流放 巒鏡 番茄小說" in queries
    assert "被勾错魂，我带侯爷搬空京城流放 峦镜 番茄小说" in queries
    assert "被勾错魂，我带侯爷搬空京城流放 峦镜 fanqienovel" in queries


def test_collect_urls_searches_simplified_query_variant(monkeypatch):
    queries: list[str] = []
    site_queries: list[str] = []

    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda query, limit, timeout, stop_after_first_hit=False: site_queries.append(query) or [])

    def fake_search_web(query: str, limit: int, timeout: float):
        queries.append(query)
        return []

    monkeypatch.setattr("metafinder.finder.search_web", fake_search_web)

    MetadataFinder(per_query_results=1, max_web_queries=14)._collect_urls("社畜也能成為魔法少女嗎 盧貝多")

    assert "社畜也能成為魔法少女嗎 盧貝多" in site_queries
    assert "社畜也能成为魔法少女吗 卢贝多" in site_queries
    assert "社畜也能成为魔法少女吗 卢贝多 晋江文学城" in queries
    assert "社畜也能成为魔法少女吗 卢贝多 jjwxc" in queries


def test_query_variants_strip_leading_series_volume_prefix():
    variants = _query_variants("01 86-不存在的戰區 安里アサト")

    assert "01 86-不存在的戰區 安里アサト" in variants
    assert "86-不存在的戰區 安里アサト" in variants
    assert "86-不存在的戰區 1 安里アサト" in variants
    assert "86-不存在的戰區 第1集 安里アサト" in variants
    assert "86-不存在的戰區 第一集 安里アサト" in variants
    assert "86-不存在的戰區 vol.1 安里アサト" in variants
    assert "86-不存在的戰區（1） 安里アサト" in variants


def test_query_variants_include_taiwan_traditional_terms():
    variants = _query_variants("01 在地下城尋求邂逅是否搞錯了什麽 大森藤ノ")

    assert any("什麼" in variant for variant in variants)


def test_query_variants_include_common_title_glyph_variants():
    variants = _query_variants("01 帶著外掛轉生為公會櫃檯小姐 夏にコタツ")

    assert "帶著外掛轉生為公會櫃臺小姐 夏にコタツ" in variants
    assert "帶著外掛轉生為公會櫃台小姐 夏にコタツ" in variants


def test_candidate_matching_accepts_common_title_glyph_variants():
    query = "01 帶著外掛轉生為公會櫃檯小姐 夏にコタツ"
    official = candidate("帶著外掛轉生為公會櫃臺小姐(1) - 夏にコタツ", ["夏にコタツ"], 69)

    assert _candidate_matches_query(official, query)
    assert _candidate_query_rank(official, query) > 0


def test_query_variants_try_chinese_first_bilingual_titles():
    variants = _query_variants("01 OUTBREAK COMPANY 萌萌侵略者 榊一郎")

    assert "萌萌侵略者 OUTBREAK COMPANY 榊一郎" in variants
    assert "萌萌侵略者OUTBREAK COMPANY(01) 榊一郎" in variants


def test_site_query_variants_prioritize_bilingual_volume_variants():
    query = "01 OUTBREAK COMPANY 萌萌侵略者 榊一郎"
    variants = _site_query_variants(query, _query_variants(query), 8)

    assert variants[0] == query
    assert "萌萌侵略者 OUTBREAK COMPANY 榊一郎" in variants
    assert "萌萌侵略者OUTBREAK COMPANY(01) 榊一郎" in variants


def test_query_variants_strip_bracketed_and_ordinal_volume_prefixes():
    assert "86-不存在的戰區 安里アサト" in _query_variants("（03）86-不存在的戰區 安里アサト")
    assert "86-不存在的戰區 安里アサト" in _query_variants("第4集 86-不存在的戰區 安里アサト")
    assert "86-不存在的戰區 第3集 安里アサト" in _query_variants("（03）86-不存在的戰區 安里アサト")
    assert "86-不存在的戰區 第四集 安里アサト" in _query_variants("第4集 86-不存在的戰區 安里アサト")


def test_query_variants_do_not_strip_decimal_title_prefix():
    variants = _query_variants("5.18光州！光州！ 黃晳暎")

    assert "18光州！光州！ 黃晳暎" not in variants


def test_leading_volume_query_rejects_different_candidate_volume():
    query = "02 29張當票 當舖裡特有的人生風景 秦嗣林"
    volume_2 = candidate("29張當票②：當舖裡特有的人生風景 - 秦嗣林", ["秦嗣林"], 72)
    volume_3 = candidate("29張當票③：門簾外的人生鑑定 - 秦嗣林", ["秦嗣林"], 69)

    assert _candidate_matches_query(volume_2, query)
    assert not _candidate_matches_query(volume_3, query)
    assert _candidate_query_rank(volume_2, query) > _candidate_query_rank(volume_3, query)


def test_leading_volume_query_rejects_missing_or_attached_wrong_volume():
    query = "09 福爾摩斯．新探案(自炊) 柯南．道爾"

    assert not _candidate_matches_query(candidate("新探案", ["柯南．道爾"], 74), query)
    assert not _candidate_matches_query(candidate("福爾摩斯探案全集8：新探案", ["柯南．道爾"], 77), query)


def test_single_title_query_rejects_ampersand_compilation():
    query = "01 福爾摩斯．血字的研究(自炊) 柯南．道爾"
    compilation = candidate("福爾摩斯探案全集1：血字的研究＆四簽名", ["柯南．道爾"], 77)

    assert not _candidate_matches_query(compilation, query)


def test_leading_volume_query_rejects_parenthesized_wrong_volume():
    query = "01 86-不存在的戰區 安里アサト"
    volume_1 = candidate("86－不存在的戰區（1）", ["安里アサト"], 70)
    volume_9 = candidate("86－不存在的戰區（9）", ["安里アサト"], 70)

    assert _candidate_matches_query(volume_1, query)
    assert not _candidate_matches_query(volume_9, query)


def test_query_with_volume_before_author_rejects_wrong_volume():
    query = "Fairy Tale 幻想編年史 11 埴輪星人"
    volume_8 = candidate("Fairy Tale 幻想編年史～不懂察言觀色的異世界生活～ 8", ["埴輪星人"], 80)
    volume_11 = candidate("Fairy Tale 幻想編年史～不懂察言觀色的異世界生活～ 11", ["埴輪星人"], 80)

    assert not _candidate_matches_query(volume_8, query)
    assert _candidate_matches_query(volume_11, query)


def test_isbn_web_queries_are_bounded_and_skip_title_author_hints():
    queries = _web_queries(["9789863842590"], expected_isbn="9789863842590", max_queries=7)

    assert queries == [
        "9789863842590",
        "9789863842590 site:books.com.tw",
        "9789863842590 site:books.com.tw/products/E",
        "9789863842590 site:readmoo.com",
        "9789863842590 site:crown.com.tw",
        "9789863842590 site:cite.com.tw",
        "9789863842590 site:eslite.com",
    ]
    assert not any("jjwxc" in query or "晉江" in query for query in queries)


def test_general_web_queries_include_tongli_as_official_publisher_source():
    queries = _web_queries(["異世界料理道 EDA"], max_queries=30)

    assert "異世界料理道 EDA site:tongli.com.tw" in queries


def test_isbn_search_returns_empty_when_no_candidate_matches_expected_isbn(monkeypatch):
    wrong = BookCandidate(
        source_name="Pubu",
        source_url="https://www.pubu.com.tw/ebook/682575",
        source_kind="store",
        metadata=BookMetadata(title="怪獸與牠們的產地", authors=["J.K. 羅琳"], isbn="9789573340294"),
        score=67,
    )

    monkeypatch.setattr(MetadataFinder, "_collect_urls", lambda self, query, expected_isbn=None, deadline=None: ["https://www.pubu.com.tw/ebook/682575"])
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda query, limit, timeout, expected_isbn=None: [])
    monkeypatch.setattr("metafinder.finder.GenericPageParser.parse_url", lambda self, url, query=None, expected_isbn=None: wrong)
    monkeypatch.setattr("metafinder.finder.lookup_openlibrary_isbn", lambda isbn, timeout: None)

    assert MetadataFinder().search("9789861690773") == []


def test_collect_urls_stops_when_deadline_is_expired(monkeypatch):
    calls: list[str] = []

    def fake_source_search(query: str, limit: int, timeout: float, stop_after_first_hit: bool = False):
        calls.append(query)
        return ["https://readmoo.com/book/123"]

    def fake_web_search(query: str, limit: int, timeout: float):
        calls.append(query)
        return []

    monkeypatch.setattr("metafinder.finder.search_source_sites", fake_source_search)
    monkeypatch.setattr("metafinder.finder.search_web", fake_web_search)

    urls = MetadataFinder(per_query_results=1)._collect_urls("9789863842590", expected_isbn="9789863842590", deadline=0)

    assert urls == []
    assert calls == []


def test_isbn_store_candidate_returns_before_slow_optional_discovery(monkeypatch):
    exact = candidate("迷宮飯(01)", ["九井諒子"], 50)
    exact.metadata.isbn = "9789865127558"
    finder = MetadataFinder(max_search_seconds=1)

    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [exact])
    monkeypatch.setattr(finder, "_hydrate_source_candidate", lambda candidates, *args: candidates)
    monkeypatch.setattr(finder, "_collect_urls", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不應繼續慢查")))
    monkeypatch.setattr("metafinder.finder.lookup_openlibrary_isbn", lambda *args, **kwargs: None)

    assert finder.search("9789865127558") == [exact]


def test_collect_urls_caps_source_site_results_before_web_search(monkeypatch):
    site_calls: list[str] = []

    def fake_source_search(query: str, limit: int, timeout: float, stop_after_first_hit: bool = False):
        site_calls.append(query)
        return [f"https://readmoo.com/book/{len(site_calls)}{i}" for i in range(10)]

    monkeypatch.setattr("metafinder.finder.search_source_sites", fake_source_search)
    monkeypatch.setattr("metafinder.finder.search_web", lambda query, limit, timeout: [])

    urls = MetadataFinder(per_query_results=1)._collect_urls("01 86-不存在的戰區 安里アサト")

    assert len(urls) == 12
    assert len(site_calls) < len(_query_variants("01 86-不存在的戰區 安里アサト"))


def test_collect_urls_keeps_web_fallback_after_source_urls(monkeypatch):
    monkeypatch.setattr(
        "metafinder.finder.search_source_sites",
        lambda *args, **kwargs: ["https://www.sanmin.com.tw/product/index/noise"],
    )
    calls = []

    def web_search(query, limit, timeout):
        calls.append(query)
        return [SearchResult("高年級實習生", "https://www.books.com.tw/products/0010946554")]

    monkeypatch.setattr("metafinder.finder.search_web", web_search)
    urls = MetadataFinder(per_query_results=1, max_web_queries=1)._collect_urls("高年級實習生")

    assert calls == ["高年級實習生"]
    assert "https://www.books.com.tw/products/0010946554" in urls


def test_search_keeps_matching_store_link_when_product_page_is_blocked(monkeypatch):
    finder = MetadataFinder()
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(finder, "_collect_urls", lambda *args, **kwargs: ["https://www.books.com.tw/products/0010946554"])
    monkeypatch.setattr(finder.parser, "parse_url", lambda *args, **kwargs: BookCandidate(
        "博客來", "https://www.books.com.tw/products/0010946554", "store", BookMetadata(), 0,
    ))
    monkeypatch.setattr(
        "metafinder.finder.search_web",
        lambda *args, **kwargs: [SearchResult("高年級實習生：馬里亞納海溝跳島記 - 博客來", "https://www.books.com.tw/products/0010946554")],
    )

    result = finder.search("高年級實習生")

    assert result[0].metadata.title == "高年級實習生：馬裡亞納海溝跳島記"
    assert result[0].evidence == ["web-search-result"]


def test_title_prefix_matches_a_store_subtitle():
    candidate = BookCandidate(
        "博客來", "https://www.books.com.tw/products/0010946554", "store",
        BookMetadata(title="高年級實習生：馬里亞納海溝跳島記"), 18,
    )

    assert _candidate_matches_query(candidate, "高年級實習生")


def test_collect_urls_limits_source_site_volume_variants_when_no_urls(monkeypatch):
    site_calls: list[str] = []

    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda query, limit, timeout, stop_after_first_hit=False: site_calls.append(query) or [])
    monkeypatch.setattr("metafinder.finder.search_web", lambda query, limit, timeout: [])

    MetadataFinder(per_query_results=1)._collect_urls("01 86-不存在的戰區 安里アサト")

    assert len(site_calls) == 6


def test_collect_urls_does_not_starve_explicit_volume_variant(monkeypatch):
    def fake_source_search(query: str, limit: int, timeout: float, stop_after_first_hit: bool = False):
        if " 1 安里" in query:
            return ["https://readmoo.com/book/210092370000101"]
        return [f"https://readmoo.com/book/wrong{i}" for i in range(limit)]

    monkeypatch.setattr("metafinder.finder.search_source_sites", fake_source_search)
    monkeypatch.setattr("metafinder.finder.search_web", lambda query, limit, timeout: [])

    urls = MetadataFinder(per_query_results=4)._collect_urls("01 86-不存在的戰區 安里アサト")

    assert "https://readmoo.com/book/210092370000101" in urls


def test_jjwxc_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://www.jjwxc.net/onebook.php?novelid=9253635")
    assert _matches_book_url("https://m.jjwxc.net/book2/9253635")
    assert _matches_book_url("https://wap.jjwxc.net/book2/9253635?more=0&whole=1")


def test_crown_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://www.crown.com.tw/view.aspx?bc=375180")


def test_books_search_redirect_is_normalized_to_product_url():
    url = "https://search.books.com.tw/redirect/move/key/9789573325758/area/mid_name/item/0010448124/page/1/idx/1/cat/001/pdf/0/spell/3"

    assert _strip_tracking(url) == "https://www.books.com.tw/products/0010448124"
    assert _matches_book_url(_strip_tracking(url))


def test_books_unique_search_result_builds_candidate(monkeypatch):
    html = """
    <div class="search_results"><p>搜尋結果共 <span>1</span> 筆</p></div>
    <div id="prod-itemlist-CN11861294">
      <a href="//search.books.com.tw/redirect/move/key/x/area/mid_image/item/CN11861294/page/1/idx/1/cat/CN1/pdf/0/spell/3">
        <img data-src="https://www.books.com.tw/img/CN1/186/12/CN11861294.jpg" />
      </a>
      <h4><a href="//search.books.com.tw/redirect/move/key/x/area/mid_name/item/CN11861294/page/1/idx/1/cat/CN1/pdf/0/spell/3" title="21世紀的21位思想家">21世紀的21位思想家</a></h4>
      <p class="author"><a title="（澳）麥肯齊·沃克">（澳）麥肯齊·沃克</a></p>
    </div>
    """

    class Response:
        text = html
        url = "https://search.books.com.tw/search/query/key/x/cat/all"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("metafinder.sources.site_search.polite_get", lambda url, headers, timeout: Response())

    candidates = search_source_candidates("21世紀的21位思想家", expected_isbn="9787532182978")

    assert len(candidates) == 1
    assert candidates[0].metadata.title == "21世紀的21位思想家"
    assert candidates[0].metadata.authors == ["（澳）麥肯齊．沃克"]
    assert candidates[0].metadata.isbn == "9787532182978"
    assert candidates[0].source_url == "https://www.books.com.tw/products/CN11861294"


def test_books_multiple_search_results_do_not_build_guess_candidate(monkeypatch):
    html = '<div class="search_results"><p>搜尋結果共 <span>67</span> 筆</p></div>'

    class Response:
        text = html
        url = "https://search.books.com.tw/search/query/key/x/cat/all"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("metafinder.sources.site_search.polite_get", lambda url, headers, timeout: Response())

    assert search_source_candidates("01 86-不存在的戰區") == []


def test_books_isbn_search_result_keeps_multiple_product_candidates(monkeypatch):
    html = """
    <div class="search_results"><p>搜尋結果共 <span>2</span> 筆</p></div>
    <div id="prod-itemlist-E050030670">
      <a href="//search.books.com.tw/redirect/move/key/x/area/mid_image/item/E050030670/page/1/idx/1/cat/E05/pdf/1/spell/3">
        <img data-src="https://www.books.com.tw/img/E05/003/06/E050030670.jpg" />
      </a>
      <h4><a href="//search.books.com.tw/redirect/move/key/x/area/mid_name/item/E050030670/page/1/idx/1/cat/E05/pdf/1/spell/3" title="LV999的村民 (1) (電子書)">LV999的村民 (1) (電子書)</a></h4>
      <p class="author"><a title="星月子貓">星月子貓</a></p>
    </div>
    <div id="prod-itemlist-0010783807">
      <h4><a href="//search.books.com.tw/redirect/move/key/x/area/mid_name/item/0010783807/page/1/idx/2/cat/001/pdf/1/spell/3" title="LV999的村民 (1)">LV999的村民 (1)</a></h4>
    </div>
    """

    class Response:
        text = html
        url = "https://search.books.com.tw/search/query/key/x/cat/all"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("metafinder.sources.site_search.polite_get", lambda url, headers, timeout: Response())

    candidates = search_source_candidates("9789575641801", expected_isbn="9789575641801", limit=5)

    assert [candidate.source_url for candidate in candidates] == [
        "https://www.books.com.tw/products/E050030670",
        "https://www.books.com.tw/products/0010783807",
    ]
    assert all(candidate.metadata.isbn == "9789575641801" for candidate in candidates)


def test_tdtb_site_search_strips_leading_volume_prefix(monkeypatch):
    calls: list[str] = []

    class Response:
        url = "https://tdtb.org/library"

        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            pass

    def fake_get(url: str, headers, timeout: float):
        calls.append(url)
        if "Title=%E6%BD%9B%E8%89%87%E8%BF%B7%E5%AE%AE" in url:
            return Response('<a href="/library/3248">潛艇迷宮</a>')
        return Response("")

    monkeypatch.setattr("metafinder.sources.site_search.polite_get", fake_get)

    assert search_source_candidates("29潛艇迷宮 倪匡") == []
    urls = __import__("metafinder.sources.site_search", fromlist=["search_source_sites"]).search_source_sites("29潛艇迷宮 倪匡")

    assert "https://tdtb.org/library/3248" in urls
    assert any("Author=%E5%80%AA%E5%8C%A1" in call for call in calls)


def test_cite_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://www.cite.com.tw/book?id=SPB7Z000301")


def test_sanmin_product_page_patch_extracts_visible_book_fields():
    html = """
    <html><body>
      <h1>如何有效閱讀一本書：超實用筆記讀書法（簡體書）</h1>
      <section>
        ISBN13：9787210082972
        出版社：江西人民出版社
        作者：(日)奧野宣之
        譯者：張晶晶
        出版日：2024-01-10
      </section>
      <h3>內容簡介</h3>
      <p>本書介紹以筆記整理閱讀過程，讓讀者把讀過的內容轉化為可重新使用的知識。</p>
    </body></html>
    """

    candidate = GenericPageParser().parse_html("https://www.sanmin.com.tw/product/index/005749190", html)

    assert candidate.source_name == "三民網路書店"
    assert candidate.metadata.isbn == "9787210082972"
    assert candidate.metadata.publisher == "江西人民出版社"
    assert candidate.metadata.authors == ["(日)奧野宣之"]
    assert candidate.metadata.translators == ["張晶晶"]
    assert candidate.metadata.published_date == "2024-01-10"
    assert "sanmin-page" in candidate.evidence


def test_catalog_fact_sheet_is_not_used_as_description():
    html = """
    <html><head>
      <meta property="og:title" content="即使，這份戀情今晚就會從世界上消失" />
      <meta property="og:description" content="書名：即使，這份戀情今晚就會從世界上消失，原文名稱：今夜、世界からこの戀が消えても，語言：繁體中文，ISBN：9786269533831，頁數：304，出版社：平裝本，作者：一條岬，譯者：林于楟，出版日期：2022/01/10，類別：文學小說" />
    </head><body></body></html>
    """

    candidate = GenericPageParser().parse_html("https://www.books.com.tw/products/0010912143", html)

    assert candidate.metadata.description is None


def test_pubu_product_page_strips_description_prefix_and_reads_fields():
    html = """
    <html><head>
      <meta property="og:title" content=" | 真假夫君 | Pubu - " />
      <meta property="og:description" content="出版：宋雨桐工作室，作者：宋雨桐，☆浪漫女王宋雨桐，狗屋經典，浪漫回歸☆ 一覺醒來，他從權傾天下的王爺，變成了病弱書生。" />
      <meta property="og:image" content="https://res2.pubu.tw/docs/587797/56671/6FhVHo_l.jpg" />
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "真假夫君",
        "author": "宋雨桐",
        "publisher": "宋雨桐工作室",
        "inLanguage": "zh-TW",
        "image": "https://res2.pubu.tw/docs/587797/56671/6FhVHo_l.jpg",
        "url": "https://www.pubu.com.tw/ebook/688165",
        "description": "",
        "isbn": ""
      }
      </script>
    </head><body>
      <main>
        發行
        2026/08/18
        語言
        繁體中文
      </main>
    </body></html>
    """

    candidate = GenericPageParser().parse_html("https://www.pubu.com.tw/ebook/688165", html)

    assert candidate.source_name == "Pubu"
    assert candidate.metadata.title == "真假夫君"
    assert candidate.metadata.authors == ["宋雨桐"]
    assert candidate.metadata.publisher == "宋雨桐工作室"
    assert candidate.metadata.published_date == "2026/08/18"
    assert candidate.metadata.language == "zh-TW"
    assert candidate.metadata.description.startswith("☆浪漫女王宋雨桐")
    assert "出版：" not in candidate.metadata.description
    assert "pubu-page" in candidate.evidence


def test_readmoo_product_page_prefers_full_description_panel():
    html = """
    <html><head>
      <meta name="description" content="這是遭截斷的商品摘要..." />
    </head><body>
      <div class="book-description-container"><div class="book-description">
        <p>這是商品頁實際完整的內容簡介。</p><p>應優先取代遭截斷的頁面摘要。</p>
      </div></div>
    </body></html>
    """

    candidate = GenericPageParser().parse_html("https://readmoo.com/book/210297089000101", html)

    assert candidate.metadata.description == "這是商品頁實際完整的內容簡介。\n應優先取代遭截斷的頁面摘要。"
    assert "readmoo-description-panel" in candidate.evidence


def test_json_ld_cjk_authors_split_ascii_comma():
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "轉轉轉遊樂園",
        "author": "青山美智子,田中達也",
        "publisher": "皇冠文化",
        "inLanguage": "zh-TW"
      }
      </script>
    </head><body></body></html>
    """

    candidate = GenericPageParser().parse_html("https://www.pubu.com.tw/ebook/689156", html)

    assert candidate.metadata.authors == ["青山美智子", "田中達也"]


def test_pubu_product_page_accepts_english_description_prefix():
    html = """
    <html><head>
      <meta property="og:title" content=" | Book Title | Pubu - " />
      <meta name="description" content="Publisher: Example Press, Author: Example Author, Real description text." />
    </head><body></body></html>
    """

    candidate = GenericPageParser().parse_html("https://www.pubu.com.tw/ebook/123456", html)

    assert candidate.metadata.publisher == "Example Press"
    assert candidate.metadata.authors == ["Example Author"]
    assert candidate.metadata.description == "Real description text."


def test_generic_description_strips_publisher_author_prefix():
    html = """
    <html><head>
      <meta property="og:title" content="可能內容不實" />
      <meta name="description" content="Publisher: 平安, Author: 艾力克斯．艾德曼斯, 要在充斥錯誤的世界保持清醒，只要有這本書就可以。" />
    </head><body></body></html>
    """

    candidate = GenericPageParser().parse_html("https://example.com/book/1", html)

    assert candidate.metadata.description == "要在充斥錯誤的世界保持清醒，只要有這本書就可以。"
    assert "Publisher:" not in candidate.metadata.description


def test_isbn_source_search_stops_after_first_store_hit(monkeypatch):
    calls = []

    def fake_search_source_sites(query, limit, timeout, stop_after_first_hit):
        calls.append(stop_after_first_hit)
        return []

    monkeypatch.setattr("metafinder.finder.search_source_sites", fake_search_source_sites)
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr("metafinder.finder.lookup_openlibrary_isbn", lambda *args, **kwargs: None)

    finder = MetadataFinder(max_search_seconds=3, max_web_queries=0)
    finder.search("9786269533831")

    assert calls == [True]


def test_isbn_search_still_uses_web_queries_after_source_hits(monkeypatch):
    web_queries = []

    class Result:
        url = "https://www.pubu.com.tw/ebook/279471"

    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda *args, **kwargs: ["https://www.books.com.tw/products/0010912143"])
    monkeypatch.setattr("metafinder.finder.search_web", lambda query, **kwargs: web_queries.append(query) or [Result()])

    finder = MetadataFinder(max_search_seconds=3, max_web_queries=1)
    urls = finder._collect_urls("9786269533831", expected_isbn="9786269533831", deadline=None)

    assert "https://www.books.com.tw/products/0010912143" in urls
    assert "https://www.pubu.com.tw/ebook/279471" in urls
    assert web_queries


def test_direct_product_url_does_not_treat_url_number_as_expected_isbn(monkeypatch):
    detail = BookCandidate(
        source_name="三民網路書店",
        source_url="https://www.sanmin.com.tw/product/index/005749190",
        source_kind="store",
        metadata=BookMetadata(title="如何有效閱讀一本書：超實用筆記讀書法", isbn="9787210082972"),
        score=67,
        evidence=["sanmin-page"],
    )
    finder = MetadataFinder(max_search_seconds=3)
    monkeypatch.setattr(finder.parser, "parse_url", lambda *args, **kwargs: detail)

    result = finder.search("https://www.sanmin.com.tw/product/index/005749190")

    assert result == [detail]


def test_tdtb_library_page_patch_extracts_publisher_year_and_description():
    html = """
    <html><body>
      <h1>潛艇迷宮</h1>
      <main>
        作者 倪匡
        出版單位 金蘭文化出版社
        出版年份 1986
        格式類型 文字
        書籍類型 語文類
        雲四風和幾個著名的遊艇製造廠工程師共同設計及製造了一艘遊艇，命名為兄弟姐妹號。
      </main>
    </body></html>
    """

    candidate = GenericPageParser().parse_html("https://tdtb.org/library/3248", html)

    assert candidate.source_name == "本館館藏"
    assert candidate.metadata.publisher == "金蘭文化出版社"
    assert candidate.metadata.published_date == "1986"
    assert candidate.metadata.title == "潛艇迷宮"
    assert candidate.metadata.description.startswith("雲四風")
    assert "tdtb-library-page" in candidate.evidence


def test_tdtb_library_page_does_not_use_next_label_as_blank_publisher():
    html = """
    <html><body>
      <main>
        <h2>北極氫彈戰</h2>
        作者
        倪匡
        出版單位
        出版年份
        格式類型
        文字
        《北極氫彈戰》為完結版，作者倪匡。
      </main>
    </body></html>
    """

    candidate = GenericPageParser().parse_html("https://tdtb.org/library/3102", html)

    assert candidate.metadata.publisher is None
    assert candidate.metadata.published_date is None
    assert candidate.metadata.title == "北極氫彈戰"


def test_qq_reader_and_qidian_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://ubook.reader.qq.com/book-detail/45849533")
    assert _matches_book_url("https://www.qidian.com/book/1035849533/")


def test_video_anime_pages_are_not_probably_book_pages():
    assert not _is_probably_book_page("https://ani.gamer.com.tw/animeVideo.php?sn=22245")


def test_wikipedia_pages_are_not_automatic_book_candidates():
    assert not _is_probably_book_page("https://zh.wikipedia.org/zh-tw/86%EF%BC%8D%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E6%88%B0%E5%8D%80%EF%BC%8D")
def test_search_reserves_time_to_parse_collected_urls(monkeypatch):
    clock = [0.0]
    finder = MetadataFinder(max_search_seconds=12, request_timeout=3)
    book = candidate("目標書名", ["作者"], 80)
    book.source_kind = "store"
    monkeypatch.setattr("metafinder.finder.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("metafinder.finder.search_source_candidates", lambda *args, **kwargs: [])

    def collect(*args, **kwargs):
        clock[0] = kwargs["deadline"]
        return [book.source_url]

    monkeypatch.setattr(finder, "_collect_urls", collect)
    monkeypatch.setattr(finder.parser, "parse_url", lambda *args, **kwargs: book)
    assert finder.search("目標書名 作者") == [book]
