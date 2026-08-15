from metafinder.sources.generic import GenericPageParser


def test_jjwxc_patch_cleans_wrapped_title_author_and_cover():
    html = """
    <html>
      <head><title>《卖脸花瓶是机甲大神》逢行_晋江文学城_【原创小说|言情小说】</title></head>
      <body>
        <img src="https://pic1.imgdb.cn/item/6808e4df58cb8da5c8c6a495.jpg" />
      </body>
    </html>
    """

    candidate = GenericPageParser().parse_html("https://www.jjwxc.net/onebook.php?novelid=7370132", html)

    assert candidate.source_name == "晉江文學城"
    assert candidate.metadata.title == "賣臉花瓶是機甲大神"
    assert candidate.metadata.authors == ["逢行"]
    assert candidate.metadata.publisher == "晉江文學城"
    assert candidate.metadata.cover_url == "https://pic1.imgdb.cn/item/6808e4df58cb8da5c8c6a495.jpg"
    assert "jjwxc-page" in candidate.evidence
