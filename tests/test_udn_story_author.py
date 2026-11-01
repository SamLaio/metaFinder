from metafinder.sources.generic import GenericPageParser


def test_udn_story_empty_schema_author_uses_verified_product_byline():
    html='<script type="application/ld+json">{"@type":"Book","name":"侯府嫡長女","author":[{"@type":"Person","name":""}]}</script><h1>侯府嫡長女</h1><h3><a title="葉子瀟瀟" href="/story/search/author/?type=piece">葉子瀟瀟</a></h3>'
    parser=GenericPageParser()
    assert parser.parse_html('https://reading.udn.com/story/products/237322/',html).metadata.authors==['葉子瀟瀟']
    for url,body in [('https://example.com/story/products/237322/',html),('https://reading.udn.com/story/search/author/',html),('https://reading.udn.com/story/products/237322/',html.replace('title="葉子瀟瀟"','title="其他人"'))]:
        assert not parser.parse_html(url,body).metadata.authors
