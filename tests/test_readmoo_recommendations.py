from metafinder.sources.generic import GenericPageParser


def test_readmoo_recommendation_dates_are_not_book_publication():
    html = '<h1>男孩子氣的女友超級可愛</h1><div class="book-meta"><li>出版社：東立</li><li>eISBN: <span itemprop="eisbn">9786260271626</span></li></div><li class="listItem-box"><div class="publish-date">出版日期：2026-06-10</div><p>譯者：錯誤譯者</p></li>'
    parser = GenericPageParser()
    book = parser.parse_html('https://readmoo.com/book/123', html).metadata
    assert book.published_date is None
    assert not book.translators
    assert book.eisbn == '9786260271626'
    dated = html.replace('出版社：東立', '出版日期：2026-02-24</li><li>出版社：東立')
    assert parser.parse_html('https://readmoo.com/book/123', dated).metadata.published_date == '2026-02-24'
    assert parser.parse_html('https://example.com/book/123', html).metadata.published_date == '2026-06-10'
