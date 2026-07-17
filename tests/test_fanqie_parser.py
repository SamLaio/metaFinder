from metafinder.sources.generic import GenericPageParser, source_info
from metafinder.sources.site_search import _matches_book_url


def test_fanqie_page_extracts_book_metadata_from_visible_fields():
    html = """
    <html>
      <head>
        <title>冰封了千年的玄门大小姐她融化了完整版在线免费阅读_番茄小说官网</title>
      </head>
      <body>
        <h1>冰封了千年的玄门大小姐她融化了</h1>
        <div class="info-label">
          <span class="info-label-yellow">已完结</span>
          <span class="info-label-grey">现言脑洞</span>
          <span class="info-label-grey">现代言情</span>
          <span class="info-label-grey">幻想言情</span>
        </div>
        <span class="info-last-time">2024-05-28 19:51</span>
        <span class="author-name-text">悦悦爱瞅瞅</span>
        <div class="page-abstract-content">
          <p>最近小区里的人都在议论，故事就这样开始。</p>
        </div>
        <script>
          window.__INITIAL_STATE__ = {"page":{"thumbUrl":"https:\\u002F\\u002Fexample.invalid\\u002Fcover.jpg"}};
        </script>
      </body>
    </html>
    """

    candidate = GenericPageParser().parse_html("https://fanqienovel.com/page/7349417805017533464", html)

    assert candidate.source_name == "番茄小說"
    assert candidate.source_kind == "web-novel"
    assert candidate.metadata.title == "冰封了千年的玄門大小姐她融化了"
    assert candidate.metadata.authors == ["悅悅愛瞅瞅"]
    assert candidate.metadata.published_date == "2024-05-28 19:51"
    assert "現代言情" in candidate.metadata.tags
    assert "已完結" not in candidate.metadata.tags
    assert candidate.metadata.cover_url == "https://example.invalid/cover.jpg"
    assert "最近小區裡的人都在議論" in candidate.metadata.description
    assert "fanqie-page" in candidate.evidence


def test_fanqie_page_url_matches_book_pattern():
    assert _matches_book_url("https://fanqienovel.com/page/7349417805017533464")


def test_fanqie_source_info_is_web_novel():
    assert source_info("https://fanqienovel.com/page/7349417805017533464") == ("番茄小說", "web-novel")
