import json

import httpx
import pytest

from deep_research.budget import Budget, BudgetExceeded
from deep_research.llm import (
    LLMError,
    LLMOutputError,
    LLMRequest,
    OllamaLLM,
    ScriptedLLM,
    call_structured,
)
from deep_research.models import Limits, QueriesOut

SCHEMA = {"type": "object"}


def ollama(responses, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        body = responses.pop(0)
        if isinstance(body, int):
            return httpx.Response(body)
        return httpx.Response(200, json=body)

    return OllamaLLM(
        "http://ollama.test", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def msg(content, p=7, c=3):
    return {"message": {"content": content}, "prompt_eval_count": p, "eval_count": c}


def test_payload_and_usage():
    seen = []
    llm = ollama([msg("{}")], seen)
    res = llm.complete(LLMRequest("plan", "sys", "usr", SCHEMA, 600))
    payload = seen[0]
    assert payload["think"] is False
    assert payload["format"] == SCHEMA
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["num_predict"] == 600
    assert payload["messages"][0] == {"role": "system", "content": "sys"}
    assert (res.prompt_tokens, res.completion_tokens) == (7, 3)


def test_non_200_raises():
    llm = ollama([500], [])
    with pytest.raises(LLMError):
        llm.complete(LLMRequest("plan", "s", "u", SCHEMA, 10))


def test_think_block_and_fences_stripped():
    budget = Budget(Limits())
    llm = ollama([msg('<think>x</think>{"queries":["a"]}')], [])
    out = call_structured(
        llm, budget, purpose="queries", system="s", user="u", model_cls=QueriesOut
    )
    assert out.queries == ["a"]
    llm = ollama([msg('```json\n{"queries":["b"]}\n```')], [])
    out = call_structured(
        llm, budget, purpose="queries", system="s", user="u", model_cls=QueriesOut
    )
    assert out.queries == ["b"]


def test_retry_then_success_counts_two_calls():
    seen = []
    budget = Budget(Limits())
    llm = ollama([msg("not json"), msg('{"queries":["a"]}')], seen)
    out = call_structured(
        llm, budget, purpose="queries", system="s", user="u", model_cls=QueriesOut
    )
    assert out.queries == ["a"]
    assert len(seen) == 2
    assert "previous answer was invalid" in seen[1]["messages"][1]["content"]
    assert budget.snapshot()["prompt_tokens"] == 14


def test_two_failures_raise():
    llm = ollama([msg("nope"), msg("still nope")], [])
    with pytest.raises(LLMOutputError):
        call_structured(
            llm, Budget(Limits()), purpose="queries", system="s", user="u", model_cls=QueriesOut
        )


def test_budget_exceeded_means_no_http():
    seen = []
    llm = ollama([msg("{}")], seen)
    budget = Budget(Limits(max_tokens=10))
    with pytest.raises(BudgetExceeded):
        call_structured(llm, budget, purpose="queries", system="s", user="u", model_cls=QueriesOut)
    assert seen == []


def test_scripted_llm():
    llm = ScriptedLLM({"queries": lambda req: {"queries": ["q"]}})
    out = call_structured(
        llm, Budget(Limits()), purpose="queries", system="s", user="u", model_cls=QueriesOut
    )
    assert out.queries == ["q"]
    assert len(llm.calls) == 1
    assert llm.describe() == {"model": "scripted", "digest": None}


def test_describe_digest():
    def handler(request):
        return httpx.Response(200, json={"models": [{"name": "m", "digest": "abc"}]})

    llm = OllamaLLM(
        "http://ollama.test", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert llm.describe() == {"model": "m", "digest": "abc"}
