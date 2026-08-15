from metafinder.sources import web_search
from metafinder.sources.web_search import SearchResult, _unwrap_bing_url, search_web


def test_search_web_falls_back_to_bing_when_duckduckgo_fails(monkeypatch):
    monkeypatch.setattr(web_search, "_search_duckduckgo", lambda query, limit, timeout: (_ for _ in ()).throw(RuntimeError("timeout")))
    monkeypatch.setattr(web_search, "_search_bing", lambda query, limit, timeout: [SearchResult("title", "https://example.invalid/book")])

    results = search_web("9789573325758 site:crown.com.tw", limit=3, timeout=1)

    assert [result.url for result in results] == ["https://example.invalid/book"]


def test_unwrap_bing_redirect_url():
    url = (
        "https://www.bing.com/ck/a?!&&p=x&u="
        "a1aHR0cHM6Ly93d3cuY3Jvd24uY29tLnR3L3ZpZXcuYXNweD9iYz0zNzUxODA"
        "&ntb=1"
    )

    assert _unwrap_bing_url(url) == "https://www.crown.com.tw/view.aspx?bc=375180"
