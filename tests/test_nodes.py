import pytest
from fakes import make_deps, scripted_llm

from deep_research.llm import ScriptedLLM
from deep_research.models import Limits
from deep_research.nodes import (
    coverage_decision,
    extract_claims,
    gather_sources,
    plan_topics,
    verify_new_claims,
    write_queries,
)


def test_plan_ids_and_cap(tmp_path):
    deps = make_deps(
        tmp_path, scripted_llm(["topic a", "topic b", "topic c", "topic d"]), Limits(max_topics=3)
    )
    topics = plan_topics(deps, "q")
    assert [t["topic_id"] for t in topics] == ["t1", "t2", "t3"]
    assert topics[0]["title"] == "topic a"


def test_queries_dedupe_and_cap(tmp_path):
    llm = ScriptedLLM({"queries": lambda r: {"queries": ["A b", "a B", "c", "d"]}})
    deps = make_deps(tmp_path, llm, Limits(queries_per_topic=2))
    assert write_queries(deps, "q", {"topic_id": "t1", "title": "alpha"}) == ["A b", "c"]


def test_gather_reuses_stored_url_without_fetch_charge(tmp_path):
    deps = make_deps(tmp_path)
    topic = {"topic_id": "t1", "title": "alpha"}
    first, hits = gather_sources(deps, topic, 1, ["alpha overview"])
    assert hits == []
    assert len(first) == 3
    assert deps.budget.snapshot()["fetches"] == 3
    second, _ = gather_sources(deps, topic, 2, ["alpha overview"])
    assert [s["source_id"] for s in second] == [s["source_id"] for s in first]
    assert deps.budget.snapshot()["fetches"] == 3
    assert deps.fetch.calls.__len__() == 3
    assert deps.budget.snapshot()["searches"] == 2


def test_gather_reports_budget_hit_and_stops(tmp_path):
    deps = make_deps(tmp_path, limits=Limits(max_fetches=1))
    topic = {"topic_id": "t1", "title": "alpha"}
    sources, hits = gather_sources(deps, topic, 1, ["alpha overview"])
    assert hits == ["fetch"]
    assert len(sources) == 1
    deps2 = make_deps(tmp_path / "x", limits=Limits(max_searches=1), run_id="r2")
    sources, hits = gather_sources(deps2, topic, 1, ["one", "two"])
    assert hits == ["search"]
    assert deps2.search.calls == 1


def test_extract_maps_labels(tmp_path):
    def extract(req):
        return {
            "claims": [
                {
                    "text": "first claim",
                    "citations": [{"source": "S1", "quote": "x y z a b c"}],
                },
                {"text": "ghost claim", "citations": [{"source": "S9", "quote": "x y z a b c"}]},
            ]
        }

    llm = ScriptedLLM({"extract": extract})
    deps = make_deps(tmp_path, llm)
    topic = {"topic_id": "t2", "title": "alpha"}
    sources, _ = gather_sources(deps, topic, 1, ["alpha overview"])
    claims = extract_claims(deps, "q", topic, 1, sources)
    assert [c["claim_id"] for c in claims] == ["t2-r1-c1", "t2-r1-c2"]
    assert claims[0]["citations"][0]["source_id"] == sources[0]["source_id"]
    assert claims[1]["citations"][0]["source_id"] == "label:S9"


def test_extract_without_sources_makes_no_llm_call(tmp_path):
    llm = ScriptedLLM({})
    deps = make_deps(tmp_path, llm)
    assert extract_claims(deps, "q", {"topic_id": "t1", "title": "a"}, 1, []) == []
    assert llm.calls == []


def test_verify_only_new_claims(tmp_path):
    deps = make_deps(tmp_path)
    topics = [{"topic_id": "t1", "title": "good"}, {"topic_id": "t2", "title": "bad one"}]
    claims = []
    for topic in topics:
        deps_llm = scripted_llm([t["title"] for t in topics])
        deps.llm = deps_llm
        sources, _ = gather_sources(deps, topic, 1, [topic["title"] + " overview"])
        claims += extract_claims(deps, "q", topic, 1, sources)
    verdicts = verify_new_claims(deps.store, "r1", claims, [])
    by_id = {v["claim_id"]: v for v in verdicts}
    assert by_id["t1-r1-c1"]["status"] == "verified"
    assert by_id["t2-r1-c1"]["status"] == "rejected"
    assert by_id["t2-r1-c1"]["reason"] == "QUOTE_NOT_FOUND"
    assert by_id["t1-r1-c1"]["topic_id"] == "t1"
    assert verify_new_claims(deps.store, "r1", claims, verdicts) == []


def _v(topic, status, n):
    return [{"claim_id": f"{topic}-{i}", "topic_id": topic, "status": status} for i in range(n)]


@pytest.mark.parametrize(
    ("verdicts", "round_", "exhausted", "want"),
    [
        (_v("t1", "verified", 2) + _v("t2", "verified", 2), 1, False, ("writer", [])),
        (_v("t1", "verified", 2), 1, False, ("supervisor", ["t2"])),
        (_v("t1", "verified", 2), 2, False, ("writer", [])),
        (_v("t1", "verified", 1) + _v("t2", "rejected", 5), 1, True, ("writer", [])),
        ([], 1, False, ("supervisor", ["t1", "t2"])),
    ],
)
def test_coverage_decision(verdicts, round_, exhausted, want):
    topics = [{"topic_id": "t1"}, {"topic_id": "t2"}]
    assert coverage_decision(topics, verdicts, round_, Limits(rounds=2), exhausted) == want
