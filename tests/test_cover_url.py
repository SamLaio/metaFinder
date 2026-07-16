from metafinder.models import BookCandidate, BookMetadata
from metafinder.sources.generic import GenericPageParser


def test_candidate_dict_exposes_cover_url_at_top_level():
    candidate = BookCandidate(
        source_name="test",
        source_url="https://example.invalid/book",
        source_kind="store",
        metadata=BookMetadata(title="書名", cover_url="https://example.invalid/cover.jpg"),
    )

    data = candidate.as_dict()

    assert data["cover_url"] == "https://example.invalid/cover.jpg"
    assert data["metadata"]["cover_url"] == "https://example.invalid/cover.jpg"


def test_parser_extracts_cover_from_meta_secure_image():
    html = """
    <html>
      <head>
        <meta property="og:title" content="書名" />
        <meta property="og:image:secure_url" content="/images/cover.jpg" />
      </head>
    </html>
    """

    candidate = GenericPageParser().parse_html("https://example.invalid/books/1", html)

    assert candidate.metadata.cover_url == "https://example.invalid/images/cover.jpg"


def test_parser_extracts_cover_from_lazy_loaded_image():
    html = """
    <html>
      <body>
        <img alt="封面" data-lazy-src="../covers/book.webp" />
      </body>
    </html>
    """

    candidate = GenericPageParser().parse_html("https://example.invalid/books/1/index.html", html)

    assert candidate.metadata.cover_url == "https://example.invalid/books/covers/book.webp"


def test_parser_extracts_cover_from_jsonld_image_object():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "Book",
          "name": "書名",
          "image": {"@type": "ImageObject", "contentUrl": "/cover.png"}
        }
        </script>
      </head>
    </html>
    """

    candidate = GenericPageParser().parse_html("https://example.invalid/book", html)

    assert candidate.metadata.cover_url == "https://example.invalid/cover.png"
