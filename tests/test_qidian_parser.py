from metafinder.sources.generic import GenericPageParser
from metafinder.sources.site_search import search_source_sites


def test_qidian_www_book_url_uses_mobile_equivalent(monkeypatch):
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "兽血沸腾",
        "author": {"@type": "Person", "name": "静官"},
        "publisher": {"@type": "Organization", "name": "起点中文网"},
        "inLanguage": "zh-CN",
        "datePublished": "2005-11-19T10:12:07+08:00",
        "image": "https://bookcover.yuewen.com/qdbimg/349573/45050/600",
        "description": "一名牺牲在南疆战场上的侦察兵，神奇地在异时空中重生。"
      }
      </script>
    </head></html>
    """
    fetched_urls = []

    def fake_fetch(url):
        fetched_urls.append(url)
        return html

    parser = GenericPageParser()
    monkeypatch.setattr(parser, "fetch", fake_fetch)

    candidate = parser.parse_url("https://www.qidian.com/book/45050/")

    assert fetched_urls == ["https://m.qidian.com/book/45050/"]
    assert candidate.source_name == "起點中文網"
    assert candidate.source_url == "https://m.qidian.com/book/45050/"
    assert candidate.metadata.title == "獸血沸騰"
    assert candidate.metadata.authors == ["靜官"]
    assert candidate.metadata.publisher == "起點中文網"
    assert candidate.metadata.published_date == "2005-11-19T10:12:07+08:00"
    assert "異時空中重生" in candidate.metadata.description
    assert candidate.metadata.cover_url == "https://bookcover.yuewen.com/qdbimg/349573/45050/600"


def test_qidian_mobile_search_extracts_book_urls(monkeypatch):
    html = """
    <a href="//m.qidian.com/chapter/45050/0/" title="兽血沸腾在线阅读" data-bid="45050">
      <h2>兽血沸腾</h2>
    </a>
    """

    class Response:
        url = "https://m.qidian.com/soushu/%E7%8D%B8%E8%A1%80%E6%B2%B8%E9%A8%B0.html"
        text = html

        def raise_for_status(self):
            return None

    requested: list[str] = []

    def fake_get(url, headers=None, timeout=15.0):
        requested.append(url)
        if url.startswith("https://m.qidian.com/search?kw="):
            return Response()
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("metafinder.sources.site_search.polite_get", fake_get)

    urls = search_source_sites("獸血沸騰 靜官", limit=3, timeout=1)

    assert any(url.startswith("https://m.qidian.com/search?kw=") for url in requested)
    assert "https://m.qidian.com/book/45050/" in urls
def test_qidian_search_does_not_collect_recommended_unrelated_books(monkeypatch):
    from metafinder.sources.site_search import _search_qidian_mobile

    class Response:
        text = '<a data-bid="123"><h2>另外一本熱門推薦</h2></a><a href="//m.qidian.com/chapter/456/0/" title="別的小說在线阅读"></a>'

        def raise_for_status(self):
            pass

    monkeypatch.setattr("metafinder.sources.site_search.polite_get", lambda *args, **kwargs: Response())
    assert _search_qidian_mobile("百鍊霸王與聖約女武神 鷹山誠一", 1, 5) == []
