import pytest
from pydantic import ValidationError

from deep_research.config import Settings
from deep_research.models import Limits, PlanOut


def test_limit_defaults_match_spec():
    lim = Limits()
    assert (lim.max_searches, lim.max_fetches, lim.max_tokens) == (40, 60, 400_000)
    assert lim.max_wall_s == 900
    assert (lim.researchers, lim.rounds, lim.max_topics) == (4, 2, 5)
    assert (lim.queries_per_topic, lim.results_per_query, lim.sources_per_extract) == (2, 3, 3)
    assert (lim.source_chars, lim.min_verified_claims) == (6000, 2)
    assert (lim.max_bytes, lim.fetch_timeout_s) == (2_000_000, 20)


def test_limits_validation():
    with pytest.raises(ValidationError):
        Limits(max_searches=0)
    with pytest.raises(ValidationError):
        Limits(foo=1)


def test_schema_has_topics():
    assert "topics" in PlanOut.model_json_schema()["properties"]


def test_settings_env():
    assert Settings.from_env({"SEARXNG_URL": "http://x:1"}).searxng_url == "http://x:1"
    s = Settings.from_env({})
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.model == "qwen3.8:27b"
