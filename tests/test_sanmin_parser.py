from metafinder.sources.generic import GenericPageParser


def test_preface_heading_is_not_translator_name():
    page = "<h1>Effective Objective-C 2.0</h1><h2>目錄</h2><p>譯者序</p><p>作者簡介</p>"
    result = GenericPageParser().parse_html("https://www.sanmin.com.tw/product/index/004385868", page)
    assert result.metadata.translators == []
    assert result.metadata.authors == []


def test_description_uses_product_intro_not_catalog_meta():
    page = '''<h1>測試書</h1><meta name="description" content="ISBN：9789861343228 作者：某人 出版社：先覺">
    <h2 id="Intro1">商品簡介</h2><div class="SectionBody">探索思考的限制，<br>以及群體如何共享知識。</div>
    <h2 id="Intro2">作者簡介</h2><div class="SectionBody">不應混入的作者資料。</div>'''
    result = GenericPageParser().parse_html("https://www.sanmin.com.tw/product/index/006788237", page)
    assert result.metadata.description == "探索思考的限制，\n以及群體如何共享知識。"


def test_store_product_code_is_not_isbn():
    page = '<h1>測試書</h1><script type="application/ld+json">{"@type":"Book","isbn":"2222221329588"}</script>'
    result = GenericPageParser().parse_html("https://www.sanmin.com.tw/product/index/015280475", page)
    assert result.metadata.isbn is None


def test_visible_label_does_not_restore_rejected_product_barcode():
    page = '<h1>種子的勝利</h1><script type="application/ld+json">{"@type":"Book","isbn":"4717702110444"}</script><p>ISBN13：4717702110444</p><p>電子ISBN：4717702110444</p>'
    result = GenericPageParser().parse_html("https://www.sanmin.com.tw/product/index/008386959", page)
    assert result.metadata.isbn is None
    assert result.metadata.eisbn is None


def test_translator_links_win_over_biography_heading():
    page = '''<h1>測試書</h1><li><h3><span>譯者</span><span>：</span><span>
    <a>李佳純</a>;<a>薄文承</a></span></h3></li><div>譯者簡介</div>'''
    result = GenericPageParser().parse_html("https://www.sanmin.com.tw/product/index/013039317", page)
    assert result.metadata.translators == ["李佳純", "薄文承"]
