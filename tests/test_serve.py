import threading

import httpx
import pytest
from fakes import FakeFetch, FakeSearch, scripted_llm

from deep_research.config import Settings
from deep_research.models import Limits
from deep_research.runner import start_run
from deep_research.serve import highlight, make_server, markdown_to_html

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


@pytest.fixture
def base(tmp_path):
    runs = tmp_path / "runs"
    llm = scripted_llm(["good one", "bad two"])
    original = llm.handlers["extract"]

    def extract(req):
        out = original(req)
        out["claims"][0]["text"] = "<script>alert(1)</script> injected claim"
        return out

    llm.handlers = {**llm.handlers, "extract": extract}
    start_run(
        "What is a widget?",
        Limits(max_topics=2, rounds=1),
        Settings(runs_dir=runs),
        llm=llm,
        search=FakeSearch(),
        fetch=FakeFetch(),
        run_id="run1",
    )
    server = make_server(runs, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_routes(base):
    home = httpx.get(base + "/")
    assert home.status_code == 200
    assert "run1" in home.text
    assert "What is a widget?" in home.text

    report = httpx.get(base + "/runs/run1")
    assert report.status_code == 200
    assert "What is a widget?" in report.text
    assert "<script>alert(1)" not in report.text

    rejected = httpx.get(base + "/runs/run1/rejected")
    assert rejected.status_code == 200
    assert "t2-r1-c1" in rejected.text
    assert "QUOTE_NOT_FOUND" in rejected.text

    source = httpx.get(base + "/runs/run1/source", params={"claim": "t1-r1-c2", "i": 0})
    assert source.status_code == 200
    assert "<mark>" in source.text


def test_dynamic_text_is_escaped(base):
    rejected_page = httpx.get(base + "/runs/run1/source", params={"claim": "t1-r1-c1", "i": 0})
    assert rejected_page.status_code == 200
    assert "<script>" not in rejected_page.text
    report = httpx.get(base + "/runs/run1")
    assert "&lt;script&gt;alert(1)" in report.text


def test_bad_paths_404(base):
    assert httpx.get(base + "/runs/..%2F..%2Fetc").status_code == 404
    assert httpx.get(base + "/runs/nope").status_code == 404
    assert httpx.get(base + "/runs/run1/source", params={"claim": "zzz", "i": 0}).status_code == 404
    assert httpx.get(base + "/other").status_code == 404


def test_read_only(base):
    assert httpx.post(base + "/runs/run1").status_code == 405


def test_markdown_converter():
    out = markdown_to_html(
        "# T <b>\n\n_Status: done._\n\nBody [^1].\n\n- one\n- two\n\n[^1]: note <i>"
    )
    assert "<h1>T &lt;b&gt;</h1>" in out
    assert "<em>Status: done.</em>" in out
    assert '<sup><a href="#fn-1">1</a></sup>' in out
    assert "<li>one</li>" in out
    assert '<li id="fn-1">note &lt;i&gt;</li>' in out


def test_highlight_fallback_to_normalized_offset():
    text = "He said “hello there my dear friends of the lab” today"
    quote = 'said "hello there my dear friends of the lab" today'
    body, note = highlight(text, quote, {"offset": 3})
    assert "<mark>" in body
    assert note
