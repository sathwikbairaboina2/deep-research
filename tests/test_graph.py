import random
import time

import pytest
from fakes import FakeFetch, FakeSearch, default_page, make_deps, scripted_llm

from deep_research.graph import build_graph
from deep_research.models import Limits


def run_graph(deps, **config):
    graph = build_graph(deps)
    return graph.invoke(
        {"run_id": deps.run_id, "question": "What is a widget?"},
        {"max_concurrency": deps.limits.researchers, "recursion_limit": 100, **config},
    )


@pytest.mark.parametrize("seed", range(5))
def test_fanout_merge(tmp_path, seed):
    rng = random.Random(seed)

    def slow_page(url):
        time.sleep(rng.random() * 0.05)
        return default_page(url)

    topics = [f"topic number {i}" for i in range(8)]
    limits = Limits(max_topics=8, rounds=1, researchers=4)
    deps = make_deps(
        tmp_path,
        scripted_llm(topics),
        limits,
        fetch=FakeFetch(slow_page),
    )
    final = run_graph(deps)
    ids = [c["claim_id"] for c in final["claims"]]
    assert len(ids) == 16
    assert len(set(ids)) == 16
    assert {c["topic_id"] for c in final["claims"]} == {f"t{i}" for i in range(1, 9)}
    assert len(final["verdicts"]) == 16
    assert all(v["status"] == "verified" for v in final["verdicts"])


def test_round_and_fanout_caps(tmp_path):
    topics = [f"bad topic {i}" for i in range(5)]
    limits = Limits(max_topics=5, rounds=3, researchers=2, max_searches=100, max_fetches=100)
    fetch = FakeFetch(delay=0.02)
    deps = make_deps(tmp_path, scripted_llm(topics), limits, fetch=fetch)
    final = run_graph(deps)
    assert final["round"] == 3
    ids = [c["claim_id"] for c in final["claims"]]
    assert any("-r1-" in i for i in ids)
    assert any("-r2-" in i for i in ids)
    assert any("-r3-" in i for i in ids)
    assert not any("-r4-" in i for i in ids)
    assert all(v["status"] == "rejected" for v in final["verdicts"])
    assert fetch.max_active <= 2
    assert fetch.max_active >= 1


def test_graph_respects_search_cap(tmp_path):
    topics = [f"topic number {i}" for i in range(4)]
    limits = Limits(max_topics=4, rounds=1, researchers=2, max_searches=3)
    search = FakeSearch()
    deps = make_deps(tmp_path, scripted_llm(topics), limits, search=search)
    final = run_graph(deps)
    assert search.calls == 3
    assert "search" in final["budget_hit"]
    assert final["status"] == "budget_exhausted"
    assert deps.budget.snapshot()["searches"] == 3


def test_covered_topics_not_redispatched(tmp_path):
    topics = ["good one", "good two", "bad three"]
    limits = Limits(max_topics=3, rounds=2)
    deps = make_deps(tmp_path, scripted_llm(topics), limits)
    final = run_graph(deps)
    ids = {c["claim_id"] for c in final["claims"]}
    assert {"t1-r1-c1", "t2-r1-c1", "t3-r1-c1", "t3-r2-c1"} <= ids
    assert not any(i.startswith(("t1-r2", "t2-r2")) for i in ids)
    assert final["status"] == "done"


def test_report_markers_all_verified(tmp_path):
    topics = ["good one", "good two", "bad three"]
    limits = Limits(max_topics=3, rounds=1)
    deps = make_deps(tmp_path, scripted_llm(topics), limits)
    final = run_graph(deps)
    verdicts = {v["claim_id"]: v["status"] for v in final["verdicts"]}
    assert final["report_markers"]
    assert all(verdicts[m] == "verified" for m in final["report_markers"])
    assert "[c:" not in final["report_md"]
    assert not any(m.startswith("t3-") for m in final["report_markers"])
    assert final["report_md"].startswith("# What is a widget?")
    assert "Under-covered topics" in final["report_md"]


def test_planner_failure_ends_run(tmp_path):
    from deep_research.llm import ScriptedLLM

    llm = ScriptedLLM({"plan": lambda r: "not json"})
    deps = make_deps(tmp_path, llm)
    final = run_graph(deps)
    assert final["status"] == "failed"
    assert final["errors"] == ["planner:LLMOutputError"]


def test_planner_transport_error_fails_the_run_cleanly(tmp_path):
    from deep_research.llm import LLMError, ScriptedLLM

    def boom(req):
        raise LLMError("timed out")

    final = run_graph(make_deps(tmp_path, ScriptedLLM({"plan": boom})))
    assert final["status"] == "failed"
    assert final["errors"] == ["planner:LLMError"]
