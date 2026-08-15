from metafinder.sources.openlibrary import lookup_openlibrary_isbn


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self._data


def test_lookup_openlibrary_isbn_builds_candidate(monkeypatch):
    def fake_get(url, headers, timeout):
        if url == "https://openlibrary.org/isbn/9780452284234.json":
            return FakeResponse(
                {
                    "title": "Nineteen eighty-four",
                    "subtitle": "a novel",
                    "publish_date": "2003",
                    "publishers": ["Plume"],
                    "covers": [7898938],
                    "authors": [{"key": "/authors/OL118077A"}],
                }
            )
        if url == "https://openlibrary.org/authors/OL118077A.json":
            return FakeResponse({"name": "George Orwell"})
        raise AssertionError(url)

    monkeypatch.setattr("metafinder.sources.openlibrary.requests.get", fake_get)

    candidate = lookup_openlibrary_isbn("9780452284234")

    assert candidate is not None
    assert candidate.source_name == "Open Library"
    assert candidate.metadata.title == "Nineteen eighty-four"
    assert candidate.metadata.authors == ["George Orwell"]
    assert candidate.metadata.isbn == "9780452284234"
    assert candidate.metadata.cover_url == "https://covers.openlibrary.org/b/id/7898938-L.jpg"


def test_lookup_openlibrary_isbn_returns_none_on_404(monkeypatch):
    monkeypatch.setattr("metafinder.sources.openlibrary.requests.get", lambda url, headers, timeout: FakeResponse({}, 404))

    assert lookup_openlibrary_isbn("9787115287960") is None
