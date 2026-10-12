from metafinder.sources.generic import GenericPageParser


def test_pubu_full_description_and_placeholder_author():
    html = '''<html><head>
    <meta name="description" content="出版：出版者，作者：{0}，截斷內容..." />
    <script type="application/ld+json">{"@type":"Book","name":"書名","author":"{0}"}</script>
    </head><body>
    <div class="info-name-metaAuthor"><a href="/search?condition=fl_ahr%3D作者">作者</a></div>
    <div id="info-content"><div class="list-group-collapse"><div class="collapse">
    <div class="font-base"><div>完整簡介第一段。<br/><br/>完整簡介第二段，保留結尾。</div></div>
    </div></div></div>
    <div id="related-content"><div class="font-base">不屬於本書的推薦內容</div></div>
    </body></html>'''
    candidate = GenericPageParser().parse_html('https://www.pubu.com.tw/ebook/123456', html)
    assert candidate.metadata.authors == ['作者']
    assert candidate.metadata.description == '完整簡介第一段。\n完整簡介第二段，保留結尾。'
    assert 'pubu-description-panel' in candidate.evidence


def test_pubu_preserves_valid_author_when_panel_is_missing():
    html = '''<html><head><meta name="description" content="出版：出版者，作者：原作者，完整摘要。" /></head>
    <body><div class="info-name-metaAuthor"><a href="/search?condition=fl_ahr%3D別人">別人</a></div></body></html>'''
    candidate = GenericPageParser().parse_html('https://www.pubu.com.tw/ebook/123456', html)
    assert candidate.metadata.authors == ['原作者']
    assert candidate.metadata.description == '完整摘要。'


def test_pubu_missing_visible_author_drops_placeholder_and_reads_isbn():
    html = '''<meta name="description" content="出版：出版者，作者：{0}，完整摘要。" />
    <div><span>ISBN</span><span>9786269309931</span></div>'''
    candidate = GenericPageParser().parse_html('https://www.pubu.com.tw/ebook/123456', html)
    assert candidate.metadata.authors == []
    assert candidate.metadata.isbn == '9786269309931'
