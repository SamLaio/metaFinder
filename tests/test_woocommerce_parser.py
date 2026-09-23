from metafinder.sources.generic import GenericPageParser


def test_description_tab_excludes_author_and_catalog_fields():
    page = '''<h1>田野研究</h1><meta name="description" content="ISBN：9789570840582 作者：甲 出版社：聯經">
    <div class="woocommerce-Tabs-panel woocommerce-Tabs-panel--description" id="tab-description"><p>從村落出發，探索信仰與社會的關係。</p></div>
    <div class="woocommerce-Tabs-panel" id="tab-author">作者生平不能併入</div>
    <div class="product_meta">貨號：9789570840582</div>'''
    result = GenericPageParser().parse_html("https://store.linkingbooks.com.tw/product/test", page)
    assert result.metadata.description == "從村落出發，探索信仰與社會的關係。"
    assert "woocommerce-description-panel" in result.evidence


def test_empty_tab_does_not_erase_existing_description():
    page = '''<h1>田野研究</h1><meta name="description" content="既有有效簡介。">
    <div class="woocommerce-Tabs-panel--description" id="tab-description"></div>'''
    result = GenericPageParser().parse_html("https://example.com/book", page)
    assert result.metadata.description == "既有有效簡介。"
