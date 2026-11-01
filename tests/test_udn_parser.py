from metafinder.sources.generic import GenericPageParser


def test_udn_intro_excludes_biographies_and_reads_electronic_fields():
    html = '''<title>視覺思考</title>
    <section class="detail-section"><h2>簡介</h2><div class="detail-paragraph">
    <p>利用圖像整理想法。<br>協助團隊溝通。</p>
    <p>作者簡介<br>作者甲<br>社會研究員<br>譯者簡介<br>鍾嘉惠<br>歷史系畢業。</p>
    </div></section>
    <section class="detail-section"><h2>目錄</h2><div class="detail-paragraph">不能混入。</div></section>
    <div class="public-info"><div class="public-info__heading">ISBN</div><div class="public-info__txt">9786263490734</div></div>
    <div class="public-info"><div class="public-info__heading">EISBN</div><div class="public-info__txt">9786263490727</div></div>
    <div class="public-info"><div class="public-info__heading">出版日期</div><div class="public-info__txt">2022-11-24</div></div>
    <div class="public-info"><div class="public-info__heading">線上出版日期</div><div class="public-info__txt">2022-12-09</div></div>'''
    candidate = GenericPageParser().parse_html('https://reading.udn.com/ebook/store/store_product.do?pid=1', html)
    meta = candidate.metadata
    assert meta.description == '利用圖像整理想法。\n協助團隊溝通。'
    assert meta.translators == ['鍾嘉惠']
    assert meta.isbn == '9786263490734' and meta.eisbn == '9786263490727'
    assert meta.published_date == '2022-12-09'
    assert not {'歷史', '社會'} & set(meta.tags)
    assert 'udn-description-panel' in candidate.evidence
    other = GenericPageParser().parse_html('https://example.com/store_product.do?pid=1', html)
    assert 'udn-description-panel' not in other.evidence


def test_udn_empty_panel_preserves_existing_description_and_no_guessed_translator():
    html = '<title>故事</title><meta name="description" content="原有摘要。"><section class="detail-section"><h2>簡介</h2><div class="detail-paragraph"></div></section>'
    meta = GenericPageParser().parse_html('https://reading.udn.com/ebook/store/store_product.do?pid=2', html).metadata
    assert meta.description == '原有摘要。'
    assert meta.translators == []
