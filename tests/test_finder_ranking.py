from metafinder.finder import MetadataFinder, _candidate_matches_query, _candidate_query_rank, _is_probably_book_page, _query_variants, _site_query_variants, _web_queries
from metafinder.models import BookCandidate, BookMetadata
from metafinder.sources.site_search import _matches_book_url, _strip_tracking, search_source_candidates


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


def test_query_variants_try_chinese_first_bilingual_titles():
    variants = _query_variants("01 OUTBREAK COMPANY 萌萌侵略者 榊一郎")

    assert "萌萌侵略者 OUTBREAK COMPANY 榊一郎" in variants
    assert "萌萌侵略者OUTBREAK COMPANY(01) 榊一郎" in variants


def test_site_query_variants_prioritize_bilingual_volume_variants():
    query = "01 OUTBREAK COMPANY 萌萌侵略者 榊一郎"
    variants = _site_query_variants(query, _query_variants(query), 8)

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

    monkeypatch.setattr("metafinder.sources.site_search.requests.get", lambda url, headers, timeout: Response())

    candidates = search_source_candidates("21世紀的21位思想家", expected_isbn="9787532182978")

    assert len(candidates) == 1
    assert candidates[0].metadata.title == "21世紀的21位思想家"
    assert candidates[0].metadata.authors == ["（澳）麥肯齊·沃克"]
    assert candidates[0].metadata.isbn == "9787532182978"
    assert candidates[0].source_url == "https://www.books.com.tw/products/CN11861294"


def test_books_multiple_search_results_do_not_build_guess_candidate(monkeypatch):
    html = '<div class="search_results"><p>搜尋結果共 <span>67</span> 筆</p></div>'

    class Response:
        text = html
        url = "https://search.books.com.tw/search/query/key/x/cat/all"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("metafinder.sources.site_search.requests.get", lambda url, headers, timeout: Response())

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

    monkeypatch.setattr("metafinder.sources.site_search.requests.get", lambda url, headers, timeout: Response())

    candidates = search_source_candidates("9789575641801", expected_isbn="9789575641801", limit=5)

    assert [candidate.source_url for candidate in candidates] == [
        "https://www.books.com.tw/products/E050030670",
        "https://www.books.com.tw/products/0010783807",
    ]
    assert all(candidate.metadata.isbn == "9789575641801" for candidate in candidates)


def test_cite_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://www.cite.com.tw/book?id=SPB7Z000301")


def test_qq_reader_and_qidian_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://ubook.reader.qq.com/book-detail/45849533")
    assert _matches_book_url("https://www.qidian.com/book/1035849533/")


def test_video_anime_pages_are_not_probably_book_pages():
    assert not _is_probably_book_page("https://ani.gamer.com.tw/animeVideo.php?sn=22245")


def test_wikipedia_pages_are_not_automatic_book_candidates():
    assert not _is_probably_book_page("https://zh.wikipedia.org/zh-tw/86%EF%BC%8D%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E6%88%B0%E5%8D%80%EF%BC%8D")
