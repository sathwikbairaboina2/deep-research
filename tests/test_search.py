from pathlib import Path

import httpx
import pytest

from deep_research.search import SearchError, SearxngSearch

FIXTURE = Path(__file__).parent / "fixtures" / "searxng" / "sqlite_wal.json"


def make(handler):
    return SearxngSearch("http://searx.test", httpx.Client(transport=httpx.MockTransport(handler)))


def test_search_fixture():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=FIXTURE.read_bytes())

    search = make(handler)
    hits = search("sqlite wal", 5)
    assert seen[0].url.params["format"] == "json"
    assert seen[0].url.params["q"] == "sqlite wal"
    assert len(hits) == 5
    assert hits[0].url == "https://www.sqlite.org/wal.html"
    everything = search("sqlite wal", 50)
    assert not any("linkedin.com" in h.url for h in everything)
    assert len({h.canonical_url for h in everything}) == len(everything)


def test_search_error():
    search = make(lambda request: httpx.Response(500))
    with pytest.raises(SearchError):
        search("x", 3)


def test_search_bad_json():
    search = make(lambda request: httpx.Response(200, content=b"not json"))
    with pytest.raises(SearchError):
        search("x", 3)
