from metafinder.sources.site_search import search_source_sites


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "result": {
                "book": [
                    {"itemCode": "322509001118", "title": "水魔法 2", "subgenre_name": "コミックス"},
                    {"itemCode": "322408000119", "title": "水魔法 2", "subgenre_name": "新文芸"},
                ]
            }
        }


def test_kadokawa_imprint_uses_its_json_search(monkeypatch):
    posted = {}

    def fake_post(url, data, headers, timeout):
        posted.update(url=url, data=data, headers=headers, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("metafinder.sources.site_search.requests.post", fake_post)

    urls = search_source_sites("水魔法 ２ (カドカワBOOKS) mono-zo", limit=3, timeout=2)

    assert urls[0] == "https://www.kadokawa.co.jp/product/322408000119/"
    assert posted["data"]["kw"] == "水魔法 ２"
    assert posted["data"]["size"] == "20"
