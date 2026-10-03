from fakes import make_deps

from deep_research.models import Limits
from deep_research.researcher import build_researcher


def payload(topic_id="t1", title="alpha"):
    return {
        "run_id": "r1",
        "question": "q",
        "topic": {"topic_id": topic_id, "title": title},
        "round": 1,
    }


def test_researcher_alone(tmp_path):
    deps = make_deps(tmp_path)
    out = build_researcher(deps).invoke(payload())
    assert [c["claim_id"] for c in out["claims"]] == ["t1-r1-c1", "t1-r1-c2"]
    assert len(out["sources"]) == 3
    assert out["budget_hit"] == []
    assert out["errors"] == []


def test_researcher_budget_hit_still_extracts(tmp_path):
    deps = make_deps(tmp_path, limits=Limits(max_fetches=1))
    out = build_researcher(deps).invoke(payload())
    assert out["budget_hit"] == ["fetch"]
    assert len(out["sources"]) == 1
    assert len(out["claims"]) == 2
