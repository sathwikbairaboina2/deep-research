from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from deep_research.budget import Budget

NUM_PREDICT = {"plan": 600, "queries": 200, "extract": 1200, "write": 2000}


class LLMOutputError(Exception):
    """The model gave no usable answer (invalid output after retry, or the call itself failed)."""


class LLMError(LLMOutputError):
    """Transport-level failure (timeout, HTTP error). Handled like an unusable answer."""


@dataclass(frozen=True)
class LLMRequest:
    purpose: str  # "plan" | "queries" | "extract" | "write"
    system: str
    user: str
    schema: dict
    num_predict: int


@dataclass(frozen=True)
class LLMResult:
    content: str
    prompt_tokens: int
    completion_tokens: int


class LLM(Protocol):
    model: str

    def complete(self, req: LLMRequest) -> LLMResult: ...


class OllamaLLM:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        client: httpx.Client | None = None,
        num_ctx: int = 16384,
        timeout_s: float = 900.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client()
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s

    def complete(self, req: LLMRequest) -> LLMResult:
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": req.schema,
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx,
                "num_predict": req.num_predict,
            },
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
        }
        try:
            resp = self.client.post(
                f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_s
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"ollama request failed: {exc!r}") from exc
        if resp.status_code != 200:
            raise LLMError(f"ollama returned HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return LLMResult(
            content=data.get("message", {}).get("content", ""),
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
        )

    def describe(self) -> dict:
        try:
            resp = self.client.get(f"{self.base_url}/api/tags", timeout=10.0)
            for m in resp.json().get("models", []):
                if m.get("name") == self.model or m.get("model") == self.model:
                    return {"model": self.model, "digest": m.get("digest")}
        except (httpx.HTTPError, ValueError, AttributeError):
            pass
        return {"model": self.model, "digest": None}


class ScriptedLLM:
    """Deterministic fake: one handler per purpose returns a JSON string or a dict."""

    def __init__(
        self, handlers: Mapping[str, Callable[[LLMRequest], str | dict]], model: str = "scripted"
    ) -> None:
        self.handlers = handlers
        self.model = model
        self.calls: list[LLMRequest] = []
        self._lock = threading.Lock()

    def complete(self, req: LLMRequest) -> LLMResult:
        with self._lock:
            self.calls.append(req)
        out = self.handlers[req.purpose](req)
        content = out if isinstance(out, str) else json.dumps(out)
        return LLMResult(content, len(req.system + req.user) // 4, len(content) // 4)

    def describe(self) -> dict:
        return {"model": "scripted", "digest": None}


_THINK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _clean(content: str) -> str:
    content = _THINK_RE.sub("", content, count=1)
    m = _FENCE_RE.match(content)
    return (m.group(1) if m else content).strip()


def call_structured[T: BaseModel](
    llm: LLM,
    budget: Budget,
    *,
    purpose: str,
    system: str,
    user: str,
    model_cls: type[T],
) -> T:
    n = NUM_PREDICT[purpose]
    schema = model_cls.model_json_schema()
    current_user = user
    last_error = ""
    for _ in range(2):
        budget.reserve_tokens(Budget.estimate_tokens(system, current_user, n))
        result = llm.complete(LLMRequest(purpose, system, current_user, schema, n))
        budget.record_tokens(result.prompt_tokens, result.completion_tokens)
        try:
            return model_cls.model_validate_json(_clean(result.content))
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)[:500]
            current_user = (
                user
                + f"\n\nYour previous answer was invalid: {last_error}. "
                + "Reply with JSON matching the schema only."
            )
    raise LLMOutputError(f"{purpose}: invalid output after retry: {last_error}")
