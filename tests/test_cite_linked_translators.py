import pytest
from bs4 import BeautifulSoup
from metafinder.models import BookMetadata
from metafinder.sources.generic import GenericPageParser


@pytest.mark.parametrize('existing', ['', '周翰廷'])
def test_cite_translators_keep_all_links_in_explicit_fact_line(existing):
    schema = '<script type="application/ld+json">{"@type":"Book","name":"伊嵐翠","translator":{"@type":"Person","name":"'+existing+'"}}</script>'
    panel = '<div class="font08 pre-wrap">作者：<a>作者甲</a>\n譯者：<a href="/publisher/translators/1">周翰廷</a>、<a href="/publisher/translators/2">劉鈞豪</a>、<a href="/publisher/translators/3">段宗忱</a>\n出版社：<a>奇幻基地</a></div>'
    parser = GenericPageParser()
    result = parser.parse_html('https://www.cite.com.tw/book?id=69896',schema+panel)
    assert result.metadata.translators == ['周翰廷','劉鈞豪','段宗忱']
    assert 'cite-linked-translators' in result.evidence
    for url in ['https://example.com/book?id=69896','https://www.cite.com.tw/publisher/translators/1']:
        assert 'cite-linked-translators' not in parser.parse_html(url,schema+panel).evidence
    metadata = BookMetadata(translators=[existing] if existing else [])
    parser._extract_fallback_metadata(BeautifulSoup(panel,'html.parser'),'https://www.cite.com.tw/book?id=69896',metadata,[])
    assert metadata.translators == ['周翰廷','劉鈞豪','段宗忱']
    metadata = BookMetadata(translators=['其他譯者']);evidence=[]
    parser._extract_fallback_metadata(BeautifulSoup(panel,'html.parser'),'https://www.cite.com.tw/book?id=69896',metadata,evidence)
    assert metadata.translators == ['其他譯者'] and 'cite-linked-translators' not in evidence
