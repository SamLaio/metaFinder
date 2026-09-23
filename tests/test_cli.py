import argparse
import time

from metafinder import cli


def test_cli_search_enforces_hard_total_timeout(monkeypatch, capsys):
    class SlowFinder:
        def __init__(self, **_kwargs):
            pass

        def search(self, *_args, **_kwargs):
            time.sleep(0.05)
            return []

    monkeypatch.setattr(cli, "MetadataFinder", SlowFinder)
    args = argparse.Namespace(
        query="測試",
        limit=8,
        json=False,
        download_cover=None,
        request_timeout=1.0,
        max_search_seconds=0.01,
        max_web_queries=1,
    )

    assert cli._search(args) == 1
    assert "查找逾時" in capsys.readouterr().err
