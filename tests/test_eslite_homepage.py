import pytest
from metafinder.sources.generic import GenericPageParser


def test_product_url_returning_homepage_is_not_a_book():
    page = '<title>誠品線上 - 把生活變成喜歡的樣子</title><meta name="description" content="發現生活好物">'
    with pytest.raises(ValueError, match="商店首頁"):
        GenericPageParser().parse_html('https://www.eslite.com/product/1001125621769694', page)


def test_real_book_title_and_metadata_are_retained():
    page = '<h1>紳士遊戲</h1><p>作者：赤城毅</p><p>ISBN：9789571038230</p>'
    result = GenericPageParser().parse_html('https://www.eslite.com/product/1001125621769694', page)
    assert result.metadata.title == '紳士遊戲'
    assert result.metadata.isbn == '9789571038230'


def test_homepage_phrase_does_not_discard_explicit_book_identity():
    page = '<title>誠品線上 - 把生活變成喜歡的樣子</title><p>ISBN：9789571038230</p>'
    result = GenericPageParser().parse_html('https://www.eslite.com/product/test', page)
    assert result.metadata.isbn == '9789571038230'
