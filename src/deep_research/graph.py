from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from deep_research.budget import BudgetExceeded
from deep_research.deps import Deps
from deep_research.llm import LLMOutputError
from deep_research.nodes import coverage_decision, plan_topics, verify_new_claims
from deep_research.researcher import build_researcher
from deep_research.writer import write_report


class ResearchState(TypedDict, total=False):
    run_id: str
    question: str
    topics: list[dict]
    round: int
    open_topics: list[str]
    claims: Annotated[list, operator.add]
    verdicts: Annotated[list, operator.add]
    sources: Annotated[list, operator.add]
    budget_hit: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]
    report_md: str
    report_draft: str
    report_markers: list[str]
    writer: str
    status: str


def build_graph(deps: Deps, *, checkpointer=None):
    """planner -> supervisor -(Send)-> researcher* -> verify -> gate -> supervisor | writer."""

    def planner(state: ResearchState) -> dict:
        try:
            topics = plan_topics(deps, state["question"])
        except (LLMOutputError, BudgetExceeded) as exc:
            return {"status": "failed", "errors": [f"planner:{type(exc).__name__}"], "topics": []}
        return {"topics": topics, "round": 0, "open_topics": [t["topic_id"] for t in topics]}

    def after_planner(state: ResearchState) -> str:
        return END if state.get("status") == "failed" else "supervisor"

    def supervisor(state: ResearchState) -> dict:
        return {"round": state["round"] + 1}

    def dispatch(state: ResearchState) -> list[Send]:
        # The supervisor update is already applied here, so round is the new round number.
        open_ids = set(state["open_topics"])
        return [
            Send(
                "researcher",
                {
                    "run_id": state["run_id"],
                    "question": state["question"],
                    "topic": t,
                    "round": state["round"],
                },
            )
            for t in state["topics"]
            if t["topic_id"] in open_ids
        ]

    def verify(state: ResearchState) -> dict:
        new = verify_new_claims(
            deps.store, state["run_id"], state.get("claims", []), state.get("verdicts", [])
        )
        return {"verdicts": new}

    def gate(state: ResearchState) -> dict:
        exhausted = deps.budget.exhausted or bool(state.get("budget_hit"))
        _, open_ids = coverage_decision(
            state["topics"], state.get("verdicts", []), state["round"], deps.limits, exhausted
        )
        return {"open_topics": open_ids}

    def after_gate(state: ResearchState) -> str:
        return "supervisor" if state["open_topics"] else "writer"

    def writer(state: ResearchState) -> dict:
        exhausted = deps.budget.exhausted or bool(state.get("budget_hit"))
        status = "budget_exhausted" if exhausted else "done"
        out = write_report(
            deps,
            state["question"],
            state["topics"],
            state.get("claims", []),
            state.get("verdicts", []),
            state.get("sources", []),
            status=status,
            caps_hit=sorted(set(state.get("budget_hit", [])) | set(deps.budget.caps_hit())),
        )
        return {**out, "status": status}

    g = StateGraph(ResearchState)
    g.add_node("planner", planner)
    g.add_node("supervisor", supervisor)
    g.add_node("researcher", build_researcher(deps))
    g.add_node("verify", verify)
    g.add_node("gate", gate)
    g.add_node("writer", writer)
    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", after_planner, ["supervisor", END])
    g.add_conditional_edges("supervisor", dispatch, ["researcher"])
    g.add_edge("researcher", "verify")
    g.add_edge("verify", "gate")
    g.add_conditional_edges("gate", after_gate, ["supervisor", "writer"])
    g.add_edge("writer", END)
    return g.compile(checkpointer=checkpointer)
