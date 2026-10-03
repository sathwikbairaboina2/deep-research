import json
from datetime import UTC, datetime

import pytest
from fakes import FakeFetch, FakeSearch, scripted_llm

from deep_research.config import Settings
from deep_research.models import Limits
from deep_research.runner import new_run_id, start_run

KEYS = {
    "run_id",
    "question",
    "status",
    "limits",
    "model",
    "norm",
    "topics",
    "claims",
    "verdicts",
    "sources",
    "report_markers",
    "report_draft",
    "writer",
    "budget",
    "caps_hit",
    "errors",
    "started_at",
    "finished_at",
    "versions",
}


def settings(tmp_path):
    return Settings(runs_dir=tmp_path / "runs")


def test_new_run_id_format():
    rid = new_run_id(datetime(2026, 10, 4, 12, 30, 5, tzinfo=UTC))
    assert rid.startswith("20261004-123005-")
    assert len(rid.rsplit("-", 1)[1]) == 6


def test_end_to_end_with_fakes(tmp_path):
    cfg = settings(tmp_path)
    limits = Limits(max_topics=3, rounds=1)
    llm = scripted_llm(["good one", "good two", "bad three"])
    summary = start_run(
        "What is a widget?", limits, cfg, llm=llm, search=FakeSearch(), fetch=FakeFetch()
    )
    run = json.loads(summary.run_json_path.read_text(encoding="utf-8"))
    assert set(run) >= KEYS
    assert run["status"] == "budget_exhausted" or run["status"] == "done"
    assert summary.report_path.read_text(encoding="utf-8").startswith("# What is a widget?")
    assert summary.proposed == summary.verified + summary.rejected
    assert summary.proposed == 6
    assert summary.verified == 4
    assert run["norm"] == "NORM_V1"
    assert run["writer"] == "llm"
    assert run["budget"]["segments"][0]["wall_s"] >= 0
    assert (cfg.runs_dir / summary.run_id / "limits.json").exists()
    assert (cfg.runs_dir / summary.run_id / "meta.json").exists()
    assert run["model"] == {"model": "scripted", "digest": None}


def test_crash_writes_failed_run_json(tmp_path):
    cfg = settings(tmp_path)
    llm = scripted_llm(["good one"])
    with pytest.raises(RuntimeError):
        start_run(
            "Q?",
            Limits(max_topics=1, rounds=1),
            cfg,
            llm=llm,
            search=FakeSearch(),
            fetch=FakeFetch(fail_on_call=1),
            run_id="crash1",
        )
    run = json.loads((cfg.runs_dir / "crash1" / "run.json").read_text(encoding="utf-8"))
    assert run["status"] == "failed"
    assert "simulated crash" in run["error"]
