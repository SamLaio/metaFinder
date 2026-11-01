from metafinder.sources.generic import GenericPageParser


def test_xxsy_book_profile_uses_main_author_not_recommendations():
    html = '<title>《灯花笑》小说在线阅读_全文免费完结无删减 – 潇湘书院</title><h1>灯花笑</h1><div class="author-profile"><p class="p-name">千山茶客</p></div><div id="book_intro">归乡后的复仇与成长。<br/>第二段简介。</div><span class="author">其他作者</span>'
    parser = GenericPageParser()
    candidate = parser.parse_html('https://www.xxsy.net/book/27760376302677004', html)
    assert candidate.metadata.title == '燈花笑'
    assert candidate.metadata.authors == ['千山茶客']
    assert candidate.metadata.publisher == '網版'
    assert 'xxsy-book-profile' in candidate.evidence
    for url in ['https://example.com/book/123', 'https://www.xxsy.net/search']:
        assert 'xxsy-book-profile' not in parser.parse_html(url, html).evidence
    assert 'xxsy-book-profile' not in parser.parse_html('https://www.xxsy.net/book/123', html.replace('author-profile', 'recommendation')).evidence


def test_locus_main_blurb_does_not_include_author_or_trial():
    html = '<meta name="description" content="出版社品牌介紹"><h1>前線的女人們</h1><div class="book_com"><div class="editor_box">第一段故事簡介。<br/>第二段故事簡介。</div></div><div class="editor_box">作者傳記或試閱。</div>'
    p = GenericPageParser()
    c = p.parse_html('https://www.locuspublishing.com/book/detail/11529', html)
    assert '第一段故事簡介' in c.metadata.description and '第二段故事簡介' in c.metadata.description
    assert '作者傳記' not in c.metadata.description and '品牌介紹' not in c.metadata.description
    assert 'locus-description-panel' in c.evidence
    assert 'locus-description-panel' not in p.parse_html('https://example.com/book/detail/11529', html).evidence


def test_readmoo_stops_at_standalone_author_intro_but_keeps_story_mention():
    html = '<h1>書名</h1><div id="book-detail-description"><p>故事中的作者介紹了秘密，這是正文簡介。<br/>第二段完整的內容簡介。<br/>作者介紹<br/>甲作者的傳記不應混入。</p></div>'
    c = GenericPageParser().parse_html('https://readmoo.com/book/123', html)
    assert '故事中的作者介紹了秘密' in c.metadata.description
    assert '甲作者' not in c.metadata.description
