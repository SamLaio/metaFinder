from metafinder.sources.generic import GenericPageParser


def test_kadokawa_page_extracts_official_metadata():
    html = """
    <html><head><title>「水魔法ぐらいしか取り柄がないけど現代知識があれば充分だよね？ ２」mono-zo [カドカワBOOKS] - KADOKAWA</title></head>
    <body>
      <p>著者</p><p>mono-zo</p><p>発売日：</p><p>2024年11月09日</p><p>ISBN：</p><p>9784040756806</p>
      <p>ISBN：</p><p>9784040756806</p><p>転生幼女が披露する未知の魔法と知識に、先生たちも騒然！？</p>
      <p>スラムの孤児から一気に伯爵になった転生者のフリム。</p><p>※画像は表紙及び帯等、実際とは異なる場合があります。</p>
    </body></html>
    """

    candidate = GenericPageParser().parse_html("https://www.kadokawa.co.jp/product/322408000119/", html)

    assert candidate.source_name == "KADOKAWA"
    assert candidate.source_kind == "publisher"
    assert candidate.metadata.authors == ["mono-zo"]
    assert candidate.metadata.publisher == "KADOKAWA"
    assert candidate.metadata.published_date == "2024年11月09日"
    assert candidate.metadata.isbn == "9784040756806"
    assert "原文" in candidate.metadata.tags
    assert "転生幼女" in candidate.metadata.description
