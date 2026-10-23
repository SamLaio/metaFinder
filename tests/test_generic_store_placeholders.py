import pytest
from metafinder.sources.generic import GenericPageParser


@pytest.mark.parametrize('url,title', [
    ('https://www.pubu.com.tw/ebook/278274', 'Pubu'),
    ('https://readmoo.com/search/keyword?q=眼裡怨妳夢裡念妳', '搜尋結果：眼裡怨妳夢裡念妳'),
])
def test_store_placeholder_is_not_a_book(url, title):
    html = f'<html><head><meta property="og:title" content="{title}"/></head><body>書店首頁與搜尋列表</body></html>'
    with pytest.raises(ValueError):
        GenericPageParser().parse_html(url, html)


def test_real_pubu_book_even_named_pubu_keeps_verified_identity():
    html = '''<html><head><script type="application/ld+json">{"@type":"Book","name":"Pubu","author":{"@type":"Person","name":"張三"},"isbn":"9789573344681"}</script></head><body>完整出版書目</body></html>'''
    candidate = GenericPageParser().parse_html('https://www.pubu.com.tw/ebook/695590', html)
    assert candidate.metadata.title == 'Pubu'
    assert candidate.metadata.authors == ['張三']


def test_pubu_placeholder_with_unrelated_author_still_is_not_book():
    html = '<html><head><meta property="og:title" content="Pubu"/><meta name="author" content="八月 八"/></head><body>網站與推薦商品</body></html>'
    with pytest.raises(ValueError):
        GenericPageParser().parse_html('https://www.pubu.com.tw/ebook/278274',html)
