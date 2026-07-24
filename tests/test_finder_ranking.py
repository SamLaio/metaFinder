from metafinder.finder import MetadataFinder, _candidate_matches_query, _candidate_query_rank
from metafinder.models import BookCandidate, BookMetadata
from metafinder.sources.site_search import _matches_book_url


def candidate(title: str, authors: list[str], score: float) -> BookCandidate:
    return BookCandidate(
        source_name="test",
        source_url="https://example.invalid/book",
        source_kind="other",
        metadata=BookMetadata(title=title, authors=authors),
        score=score,
    )


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


def test_title_author_suffix_does_not_make_wrong_same_author_book_relevant():
    query = "盲眼刺客（下） 瑪格麗特．愛特伍"
    same_author_other_book = candidate("使女的故事 - 瑪格麗特．愛特伍", ["瑪格麗特．愛特伍"], 73)

    assert not _candidate_matches_query(same_author_other_book, query)


def test_short_title_wrong_same_author_book_is_not_relevant():
    query = "紅王子 提摩希．史奈德"
    same_author_other_book = candidate("血色大地：夾在希特勒與史達林之間的東歐 - 提摩希．史奈德", ["提摩希．史奈德"], 81)

    assert not _candidate_matches_query(same_author_other_book, query)


def test_author_match_with_title_token_is_relevant_for_title_author_query():
    query = "魔影魅靈5荼蘼香 黑潔明"
    same_author_matching_book = candidate("荼蘼香（上）～魔影魅靈之五", ["黑潔明"], 66)

    assert _candidate_matches_query(same_author_matching_book, query)


def test_jjwxc_wrapped_title_matches_core_title_and_author():
    query = "新時代，新魔法 衝鴨小程程"
    wrapped = candidate("《新時代，新魔法》衝鴨小程程_晉江文學城_【原創小說|言情小說】", ["衝鴨小程程"], 37)
    loose = candidate("小資女向前衝：新時代女性，好命靠自己", ["蘇妃"], 70)

    ranked = sorted([loose, wrapped], key=lambda c: (_candidate_query_rank(c, query), c.score), reverse=True)

    assert ranked[0] is wrapped


def test_collect_urls_searches_with_jjwxc_query_hints(monkeypatch):
    queries: list[str] = []

    monkeypatch.setattr("metafinder.finder.search_source_sites", lambda query, limit: [])

    def fake_search_web(query: str, limit: int):
        queries.append(query)
        return []

    monkeypatch.setattr("metafinder.finder.search_web", fake_search_web)

    MetadataFinder(per_query_results=1)._collect_urls("新時代，新魔法 衝鴨小程程")

    assert "新時代，新魔法 衝鴨小程程 晉江文學城" in queries
    assert "新時代，新魔法 衝鴨小程程 jjwxc" in queries


def test_jjwxc_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://www.jjwxc.net/onebook.php?novelid=9253635")
    assert _matches_book_url("https://m.jjwxc.net/book2/9253635")
    assert _matches_book_url("https://wap.jjwxc.net/book2/9253635?more=0&whole=1")
