import threading

from deep_research.models import FetchResult
from deep_research.store import PageStore


def fr(url, text):
    return FetchResult(
        url=url,
        final_url=url,
        canonical_url=url,
        status=200,
        content_type="text/html",
        bytes=len(text),
        truncated=False,
        text=text,
        extractor="trafilatura",
        error=None,
    )


def test_same_text_two_urls(tmp_path):
    store = PageStore(tmp_path / "s.sqlite")
    a = store.put_source("r1", fr("https://a.test/", "same text"))
    b = store.put_source("r1", fr("https://b.test/", "same text"))
    assert a == b
    assert a.startswith("sha256:")
    assert store._db.execute("SELECT COUNT(*) FROM texts").fetchone()[0] == 1
    assert len(store.sources_for_run("r1")) == 2
    assert store.texts_for_run("r1") == {a: "same text"}
    assert store.get_text(a) == "same text"


def test_runs_isolated(tmp_path):
    store = PageStore(tmp_path / "s.sqlite")
    a = store.put_source("r1", fr("https://a.test/", "one"))
    store.put_source("r2", fr("https://a.test/", "one"))
    store.put_source("r2", fr("https://b.test/", "two"))
    assert store.get_by_url("r1", "https://a.test/")["source_id"] == a
    assert store.get_by_url("r1", "https://b.test/") is None
    assert set(store.texts_for_run("r1")) == {a}
    assert len(store.texts_for_run("r2")) == 2
    assert store.source_ids_for_run("r1") == {a}


def test_budget_events_threads(tmp_path):
    store = PageStore(tmp_path / "s.sqlite")

    def work():
        for _ in range(25):
            store.add_budget_event("r1", "search", 1)

    ts = [threading.Thread(target=work) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    rows = store._db.execute("SELECT seq FROM budget_events WHERE run_id = 'r1'").fetchall()
    assert sorted(r[0] for r in rows) == list(range(1, 201))
    store.add_budget_event("r1", "prompt_tokens", 10)
    totals = store.budget_totals("r1")
    assert totals["searches"] == 200
    assert totals["prompt_tokens"] == 10
    assert totals["fetches"] == 0


def test_reopen(tmp_path):
    path = tmp_path / "s.sqlite"
    store = PageStore(path)
    sid = store.put_source("r1", fr("https://a.test/", "kept"))
    store.add_budget_event("r1", "fetch", 1)
    store.close()
    again = PageStore(path)
    assert again.get_text(sid) == "kept"
    assert again.budget_totals("r1")["fetches"] == 1
