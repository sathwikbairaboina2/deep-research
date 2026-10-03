from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from deep_research.budget import Budget
from deep_research.llm import LLM
from deep_research.models import FetchResult, Limits, SearchHit
from deep_research.store import PageStore


@dataclass
class Deps:
    """Every I/O edge of a run, injected so tests can run with sockets disabled."""

    llm: LLM
    search: Callable[[str, int], list[SearchHit]]
    fetch: Callable[[str], FetchResult]
    store: PageStore
    budget: Budget
    limits: Limits
    run_id: str
