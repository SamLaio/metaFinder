import pytest
from metafinder.sources.generic import GenericPageParser


def test_brand_homepage_is_not_a_book_even_if_query_matches_brand():
    html='<title>Nothing | TW</title><meta name="description" content="讓科技重拾樂趣"><img src="https://www.facebook.com/tr?id=123">'
    with pytest.raises(ValueError,match='首頁沒有可核實書籍'):
        GenericPageParser().parse_html('https://tw.nothing.tech/',html,query='Nothing Lasts Forever 世事無常')


def test_homepage_with_explicit_book_identity_is_retained():
    html='<h1>獨立出版書</h1><p>作者：王小明</p><p>ISBN：9789861733692</p>'
    result=GenericPageParser().parse_html('https://example.com/',html)
    assert result.metadata.title=='獨立出版書'
    assert result.metadata.isbn=='9789861733692'


def test_non_homepage_without_isbn_can_still_be_examined():
    result=GenericPageParser().parse_html('https://example.com/article/1','<h1>待核實書籍</h1>')
    assert result.metadata.title=='待核實書籍'
