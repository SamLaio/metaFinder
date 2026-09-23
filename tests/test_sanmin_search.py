from urllib.parse import unquote

from metafinder.sources.site_search import _search_sanmin


def test_sanmin_search_filters_recommendations_and_keeps_volume_links(monkeypatch):
    class Response:
        text = '<a href="/product/index/1">小學生辭典</a><a href="/product/index/2">1. 百鍊霸王與聖約女武神06</a>'

        def raise_for_status(self):
            pass

    requested = []
    monkeypatch.setattr("metafinder.sources.site_search.polite_get", lambda url, **kw: requested.append(url) or Response())
    assert _search_sanmin("06 百鍊霸王與聖約女武神 鷹山誠一", 2, 5) == ["https://www.sanmin.com.tw/product/index/2"]
    assert "06+" not in requested[0]


def test_sanmin_search_selects_old_exact_volume_before_applying_limit(monkeypatch):
    class Response:
        text = """
            <a href="/product/index/11">1. 轉生公主與天才千金的魔法革命11</a>
            <a href="/product/index/01m">2. 轉生公主與天才千金的魔法革命01（漫畫）</a>
            <a href="/product/index/01">3. 轉生公主與天才千金的魔法革命01</a>
        """

        def raise_for_status(self):
            pass

    monkeypatch.setattr("metafinder.sources.site_search.polite_get", lambda *args, **kwargs: Response())
    assert _search_sanmin("01 轉生公主與天才千金的魔法革命 鴉ぴえろ", 2, 1) == [
        "https://www.sanmin.com.tw/product/index/01"
    ]


def test_sanmin_search_supports_volume_before_a_trailing_author(monkeypatch):
    class Response:
        text = '<a href="/product/index/2">1. 迷宮飯02</a><a href="/product/index/13">2. 迷宮飯13</a>'

        def raise_for_status(self):
            pass

    requested = []
    monkeypatch.setattr("metafinder.sources.site_search.polite_get", lambda url, **kw: requested.append(url) or Response())

    assert _search_sanmin("迷宮飯 02 九井諒子", 2, 5) == ["https://www.sanmin.com.tw/product/index/2"]
    assert "迷宮飯02" in unquote(requested[0])
