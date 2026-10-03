import json

import pytest
from fakes import FakeFetch, FakeSearch, scripted_llm

from deep_research.config import Settings
from deep_research.models import Limits
from deep_research.runner import resume_run, start_run
from deep_research.store import PageStore

TOPICS = ["topic one", "topic two", "topic three"]


def load(cfg, run_id):
    return json.loads((cfg.runs_dir / run_id / "run.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("researchers", [1, 3])
def test_resume_after_crash(tmp_path, researchers):
    limits = Limits(max_topics=3, rounds=1, researchers=researchers)

    ref_cfg = Settings(runs_dir=tmp_path / "ref")
    ref_fetch = FakeFetch()
    start_run(
        "Q?",
        limits,
        ref_cfg,
        llm=scripted_llm(TOPICS),
        search=FakeSearch(),
        fetch=ref_fetch,
        run_id="run1",
    )
    ref = load(ref_cfg, "run1")
    ref_total = PageStore(ref_cfg.runs_dir / "store.sqlite").budget_totals("run1")["fetches"]
    assert ref_total == len(ref_fetch.ok_calls) == 9

    cfg = Settings(runs_dir=tmp_path / "crash")
    llm = scripted_llm(TOPICS)
    crash_fetch = FakeFetch(fail_on_call=3)
    with pytest.raises(RuntimeError, match="simulated crash"):
        start_run("Q?", limits, cfg, llm=llm, search=FakeSearch(), fetch=crash_fetch, run_id="run1")
    assert load(cfg, "run1")["status"] == "failed"

    resume_fetch = FakeFetch()
    summary = resume_run("run1", cfg, llm=llm, search=FakeSearch(), fetch=resume_fetch)
    assert summary.status == "done"
    run = load(cfg, "run1")

    assert sorted(c["claim_id"] for c in run["claims"]) == sorted(
        c["claim_id"] for c in ref["claims"]
    )
    assert {v["claim_id"]: v["status"] for v in run["verdicts"]} == {
        v["claim_id"]: v["status"] for v in ref["verdicts"]
    }

    # no URL was fetched successfully twice, and together they cover the reference set
    all_ok = crash_fetch.ok_calls + resume_fetch.ok_calls
    assert len(all_ok) == len(set(all_ok))
    assert set(all_ok) == set(ref_fetch.ok_calls)

    # ADR-0005 charges before the call, so the one call that crashed stays counted
    totals = PageStore(cfg.runs_dir / "store.sqlite").budget_totals("run1")
    assert totals["fetches"] == ref_total + 1

    # the planner ran once across crash and resume
    assert [c.purpose for c in llm.calls].count("plan") == 1
    assert run["budget"]["fetches"] == totals["fetches"]
    assert len(run["budget"]["segments"]) == 2


def test_resume_of_finished_run_is_a_noop(tmp_path):
    cfg = Settings(runs_dir=tmp_path / "runs")
    limits = Limits(max_topics=2, rounds=1)
    llm = scripted_llm(TOPICS[:2])
    start_run("Q?", limits, cfg, llm=llm, search=FakeSearch(), fetch=FakeFetch(), run_id="r1")
    calls = len(llm.calls)
    fetch = FakeFetch()
    summary = resume_run("r1", cfg, llm=llm, search=FakeSearch(), fetch=fetch)
    assert summary.status == "done"
    assert len(llm.calls) == calls
    assert fetch.calls == []
