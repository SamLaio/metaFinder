import pytest

from metafinder.sources.generic import GenericPageParser


@pytest.mark.parametrize(('url', 'panels', 'evidence'), [
    ('https://mail.acornbooks.com.tw/book.php?book_sn=5013',
     '<div class="mainbookscontact"><p>王國舉辦博覽會。</p><p>主角潛入敵境，追查實驗室。</p></div>'
     '<div class="mainbookscontact">作者簡介不能併入</div>'
     '<div class="mainbookscontact">目錄不能併入</div>'
     '<div class="mainbookscontact">試閱不能併入</div>', 'acornbooks-description-panel'),
    ('https://www.bookrep.com.tw/index.php?at=bookcontent&id=21635',
     '<div class="nrjj_c_box"><div class="nrjj_c"><p>王國舉辦博覽會。</p><p>主角潛入敵境，追查實驗室。</p></div></div>'
     '<div class="nrjj_c_box"><div class="nrjj_c">作者簡介不能併入</div></div>'
     '<div class="article_box"><div class="nrjj_c">試閱不能併入</div></div>', 'bookrep-description-panel'),
])
def test_publisher_visible_intro_replaces_short_meta_without_adjacent_sections(url, panels, evidence):
    page='<title>故事</title><meta name="description" content="被截斷的短介">'+panels
    result=GenericPageParser().parse_html(url,page)
    assert result.metadata.description=='王國舉辦博覽會。\n主角潛入敵境，追查實驗室。'
    assert evidence in result.evidence


@pytest.mark.parametrize('url', ['https://example.com/book/1', 'https://mail.acornbooks.com.tw/book.php?book_sn=1'])
def test_unrelated_or_empty_panel_keeps_existing_intro(url):
    panel=''if 'acornbooks'in url else'不相關的網站區塊'
    page='<title>故事</title><meta name="description" content="既有完整簡介。"><div class="mainbookscontact">'+panel+'</div>'
    result=GenericPageParser().parse_html(url,page)
    assert result.metadata.description=='既有完整簡介。'
