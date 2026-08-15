from metafinder.sources.generic import GenericPageParser
from metafinder.sources.site_search import _matches_book_url


def test_anobii_book_urls_match_source_site_book_patterns():
    assert _matches_book_url("https://www.anobii.com/it/books/16sui-de-zui-hou-xin-yuan/9789573325758/016655c675f02816d6")


def test_anobii_patch_extracts_isbn_from_url_and_drops_generic_title():
    html = """
    <html>
      <head><title>Condividi la tua passione per la lettura - Anobii</title></head>
    </html>
    """

    candidate = GenericPageParser().parse_html(
        "https://www.anobii.com/it/books/16sui-de-zui-hou-xin-yuan/9789573325758/016655c675f02816d6",
        html,
    )

    assert candidate.source_name == "Anobii"
    assert candidate.metadata.title is None
    assert candidate.metadata.isbn == "9789573325758"
    assert "anobii-url" in candidate.evidence
