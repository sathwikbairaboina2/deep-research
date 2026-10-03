from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from deep_research.budget import BudgetExceeded
from deep_research.deps import Deps
from deep_research.llm import LLMOutputError
from deep_research.nodes import extract_claims, gather_sources, write_queries


class ResearcherInput(TypedDict):
    run_id: str
    question: str
    topic: dict
    round: int


class ResearcherOutput(TypedDict):
    claims: Annotated[list, operator.add]
    sources: Annotated[list, operator.add]
    budget_hit: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]


class ResearcherState(TypedDict, total=False):
    run_id: str
    question: str
    topic: dict
    round: int
    queries: list[str]
    claims: Annotated[list, operator.add]
    sources: Annotated[list, operator.add]
    budget_hit: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]
    gathered: list[dict]


def build_researcher(deps: Deps):
    """queries -> gather -> extract, one topic per invocation."""

    def queries(state: ResearcherState) -> dict:
        topic = state["topic"]
        try:
            return {"queries": write_queries(deps, state["question"], topic)}
        except BudgetExceeded as exc:
            return {"queries": [], "budget_hit": [exc.kind]}
        except LLMOutputError as exc:
            return {
                "queries": [],
                "errors": [f"{topic['topic_id']}:queries:{type(exc).__name__}"],
            }

    def gather(state: ResearcherState) -> dict:
        if not state.get("queries"):
            return {"gathered": []}
        sources, hits = gather_sources(deps, state["topic"], state["round"], state["queries"])
        return {"gathered": sources, "sources": sources, "budget_hit": hits}

    def extract(state: ResearcherState) -> dict:
        topic = state["topic"]
        try:
            claims = extract_claims(
                deps, state["question"], topic, state["round"], state.get("gathered", [])
            )
        except BudgetExceeded as exc:
            return {"budget_hit": [exc.kind]}
        except LLMOutputError as exc:
            return {"errors": [f"{topic['topic_id']}:extract:{type(exc).__name__}"]}
        return {"claims": claims}

    graph = StateGraph(
        ResearcherState, input_schema=ResearcherInput, output_schema=ResearcherOutput
    )
    graph.add_node("queries", queries)
    graph.add_node("gather", gather)
    graph.add_node("extract", extract)
    graph.add_edge(START, "queries")
    graph.add_edge("queries", "gather")
    graph.add_edge("gather", "extract")
    graph.add_edge("extract", END)
    return graph.compile()
