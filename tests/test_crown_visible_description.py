from metafinder.sources.generic import GenericPageParser


def test_crown_full_blurb_excludes_author_and_sidebar():
    html = '''<html><head><meta name="description" content="只有書名" /></head><body>
    <div><span>內容簡介</span><hr/></div>
    <div class="mb-10"><p><span>完整第一段。</span><br/><br/><span>完整第二段。</span></p></div>
    <div><span>關於作者</span><hr/></div><div class="mb-10">不混入作者簡介。</div>
    </body></html>'''
    candidate = GenericPageParser().parse_html('https://www.crown.com.tw/view.aspx?bc=123', html)
    assert candidate.metadata.description == '完整第一段。\n\n完整第二段。'
    assert 'crown-description-panel' in candidate.evidence


def test_crown_selector_does_not_apply_to_other_hosts():
    html = '''<meta name="description" content="原摘要" /><div><span>內容簡介</span></div>
    <div class="mb-10">不應覆蓋其他網站的摘要。</div>'''
    candidate = GenericPageParser().parse_html('https://example.com/book/1', html)
    assert candidate.metadata.description == '原摘要'
