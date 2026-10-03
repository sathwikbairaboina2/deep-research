import json
from pathlib import Path

import pytest
import yaml
from fakes import FakeFetch, FakeSearch, scripted_llm

from deep_research.cli import main
from deep_research.config import Settings
from deep_research.evals import aggregate, load_suite, run_eval
from deep_research.models import Limits
from deep_research.runner import start_run

SUITE = [
    {"id": "q1", "question": "What is a widget?", "expected_domains": ["example.test"]},
    {"id": "q2", "question": "What is a gadget?", "expected_domains": ["other.test"]},
]


def fake_runner(topics):
    def runner(question, limits, settings):
        return start_run(
            question,
            limits,
            settings,
            llm=scripted_llm(topics),
            search=FakeSearch(),
            fetch=FakeFetch(),
        )

    return runner


def test_shipped_suite_loads():
    suite = load_suite(Path(__file__).parents[1] / "evals" / "questions.yaml")
    assert len(suite) == 12
    assert len({q["id"] for q in suite}) == 12


def test_duplicate_ids_rejected(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text(
        yaml.safe_dump({"version": 1, "questions": [SUITE[0], SUITE[0]]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_suite(path)


def test_run_eval_aggregates_sum_of_parts(tmp_path):
    settings = Settings(runs_dir=tmp_path / "runs")
    limits = Limits(max_topics=3, rounds=1)
    path = run_eval(
        SUITE,
        limit=None,
        limits=limits,
        settings=settings,
        runner=fake_runner(["good one", "good two", "bad three"]),
        out_dir=tmp_path / "out",
    )
    result = json.loads(path.read_text(encoding="utf-8"))
    qs = result["questions"]
    agg = result["aggregate"]
    assert len(qs) == 2
    assert agg["proposed"] == sum(q["proposed"] for q in qs) == 12
    assert agg["verified"] == sum(q["verified"] for q in qs) == 8
    assert agg["rejected"] == 4
    assert agg["rejection_rate"] == round(4 / 12, 4)
    assert agg["unverifiable_shipped"] == 0
    assert agg["topics_covered"] == 4
    assert agg["errors"] == 0
    assert agg["rejected_by_reason"] == {"QUOTE_NOT_FOUND": 4}
    assert qs[0]["expected_domain_share"] == 1.0
    assert qs[1]["expected_domain_share"] == 0.0
    assert path.with_suffix(".md").exists()
    assert "| q1 |" in path.with_suffix(".md").read_text(encoding="utf-8")


def test_raising_runner_is_recorded_as_error(tmp_path):
    def runner(question, limits, settings):
        if "gadget" in question:
            raise RuntimeError("boom")
        return fake_runner(["good one", "good two"])(question, limits, settings)

    path = run_eval(
        SUITE,
        limit=None,
        limits=Limits(max_topics=2, rounds=1),
        settings=Settings(runs_dir=tmp_path / "runs"),
        runner=runner,
        out_dir=tmp_path / "out",
    )
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["questions"][1]["status"] == "error"
    assert "boom" in result["questions"][1]["error"]
    assert result["aggregate"]["errors"] == 1
    assert result["aggregate"]["proposed"] == result["questions"][0]["proposed"]


def test_limit_applies(tmp_path):
    path = run_eval(
        SUITE,
        limit=1,
        limits=Limits(max_topics=2, rounds=1),
        settings=Settings(runs_dir=tmp_path / "runs"),
        runner=fake_runner(["good one", "good two"]),
        out_dir=tmp_path / "out",
    )
    assert len(json.loads(path.read_text(encoding="utf-8"))["questions"]) == 1


def test_aggregate_handles_empty():
    assert aggregate([])["proposed"] == 0


def test_cli_eval_rejects_unknown_only(tmp_path, capsys):
    suite = tmp_path / "s.yaml"
    suite.write_text(yaml.safe_dump({"version": 1, "questions": SUITE}), encoding="utf-8")
    code = main(["eval", "--suite", str(suite), "--only", "nope", "--runs-dir", str(tmp_path)])
    assert code == 2
    capsys.readouterr()
