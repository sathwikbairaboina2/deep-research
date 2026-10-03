import json
import os

import pytest

from deep_research.cli import main
from deep_research.config import Settings
from deep_research.models import Limits
from deep_research.runner import start_run

pytestmark = [
    pytest.mark.live,
    pytest.mark.enable_socket,
    pytest.mark.skipif(os.environ.get("DR_LIVE") != "1", reason="set DR_LIVE=1"),
]


def test_live_run_and_verify(tmp_path, capsys):
    settings = Settings.from_env()
    settings = Settings(
        ollama_base_url=settings.ollama_base_url,
        searxng_url=settings.searxng_url,
        model=settings.model,
        runs_dir=tmp_path / "runs",
    )
    summary = start_run(
        "How does SQLite WAL mode affect reader and writer concurrency?",
        Limits(max_topics=2, rounds=1, max_searches=4, max_fetches=6),
        settings,
    )
    run = json.loads(summary.run_json_path.read_text(encoding="utf-8"))
    assert run["status"] in {"done", "budget_exhausted"}
    code = main(["verify", summary.run_id, "--runs-dir", str(settings.runs_dir)])
    assert code == 0
    assert "unverifiable: 0" in capsys.readouterr().out
