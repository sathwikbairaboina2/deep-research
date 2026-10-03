"""Plain node functions over Deps and JSON-able dicts. graph.py and researcher.py wrap them."""

from __future__ import annotations

from quoteproof import Citation, Claim, Corpus, verify_claims

from deep_research.budget import BudgetExceeded
from deep_research.deps import Deps
from deep_research.llm import call_structured
from deep_research.models import ExtractOut, Limits, PlanOut, QueriesOut
from deep_research.prompts import extract_prompt, plan_prompt, queries_prompt
from deep_research.search import SearchError
from deep_research.store import PageStore


def plan_topics(deps: Deps, question: str) -> list[dict]:
    system, user = plan_prompt(question, deps.limits.max_topics)
    out = call_structured(
        deps.llm, deps.budget, purpose="plan", system=system, user=user, model_cls=PlanOut
    )
    topics = out.topics[: deps.limits.max_topics]
    return [
        {"topic_id": f"t{i}", "title": t.title, "rationale": t.rationale}
        for i, t in enumerate(topics, 1)
    ]


def write_queries(deps: Deps, question: str, topic: dict) -> list[str]:
    n = deps.limits.queries_per_topic
    system, user = queries_prompt(question, topic["title"], n)
    out = call_structured(
        deps.llm, deps.budget, purpose="queries", system=system, user=user, model_cls=QueriesOut
    )
    seen: set[str] = set()
    queries: list[str] = []
    for q in out.queries:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
    return queries[:n]


def gather_sources(
    deps: Deps, topic: dict, round: int, queries: list[str]
) -> tuple[list[dict], list[str]]:
    lim = deps.limits
    budget_hits: list[str] = []

    def note(kind: str) -> None:
        if kind not in budget_hits:
            budget_hits.append(kind)

    candidates = []
    seen: set[str] = set()
    try:
        for q in queries:
            deps.budget.charge("search")
            try:
                found = deps.search(q, lim.results_per_query * 2)
            except SearchError:
                continue
            taken = 0
            for hit in found:
                if hit.canonical_url in seen:
                    continue
                seen.add(hit.canonical_url)
                candidates.append(hit)
                taken += 1
                if taken >= lim.results_per_query:
                    break
    except BudgetExceeded as exc:
        note(exc.kind)

    sources: list[dict] = []
    for hit in candidates:
        if len(sources) >= lim.sources_per_extract:
            break
        row = deps.store.get_by_url(deps.run_id, hit.canonical_url)
        if row is not None:
            source_id, url = row["source_id"], row["url"]
        else:
            try:
                deps.budget.charge("fetch")
            except BudgetExceeded as exc:
                note(exc.kind)
                break
            result = deps.fetch(hit.url)
            if not result.text:
                continue
            source_id = deps.store.put_source(deps.run_id, result)
            url = result.final_url or result.url
        sources.append(
            {
                "source_id": source_id,
                "url": url,
                "canonical_url": hit.canonical_url,
                "topic_id": topic["topic_id"],
                "round": round,
            }
        )
    return sources, budget_hits


def extract_claims(
    deps: Deps, question: str, topic: dict, round: int, sources: list[dict]
) -> list[dict]:
    if not sources:
        return []
    label_map: dict[str, str] = {}
    prompt_sources: list[tuple[str, str, str]] = []
    for i, src in enumerate(sources, 1):
        label = f"S{i}"
        label_map[label] = src["source_id"]
        text = deps.store.get_text(src["source_id"]) or ""
        prompt_sources.append((label, src["url"], text[: deps.limits.source_chars]))
    system, user = extract_prompt(question, topic["title"], prompt_sources)
    out = call_structured(
        deps.llm, deps.budget, purpose="extract", system=system, user=user, model_cls=ExtractOut
    )
    claims = []
    for i, claim in enumerate(out.claims, 1):
        citations = []
        for c in claim.citations:
            label = c.source.strip()
            citations.append(
                {
                    "source_id": label_map.get(label, f"label:{label}"),
                    "quote": c.quote,
                    "label": c.source,
                }
            )
        claims.append(
            {
                "claim_id": f"{topic['topic_id']}-r{round}-c{i}",
                "topic_id": topic["topic_id"],
                "round": round,
                "text": claim.text,
                "citations": citations,
            }
        )
    return claims


def verify_new_claims(
    store: PageStore, run_id: str, claims: list[dict], verdicts: list[dict]
) -> list[dict]:
    done = {v["claim_id"] for v in verdicts}
    new = [c for c in claims if c["claim_id"] not in done]
    if not new:
        return []
    corpus = Corpus(store.texts_for_run(run_id))
    qp_claims = [
        Claim(
            c["claim_id"],
            c["text"],
            tuple(Citation(x["source_id"], x["quote"]) for x in c["citations"]),
        )
        for c in new
    ]
    out = []
    for claim, verdict in zip(new, verify_claims(qp_claims, corpus), strict=True):
        d = verdict.to_dict()
        d["topic_id"] = claim["topic_id"]
        out.append(d)
    return out


def coverage_decision(
    topics: list[dict],
    verdicts: list[dict],
    round: int,
    limits: Limits,
    exhausted: bool,
) -> tuple[str, list[str]]:
    counts: dict[str, int] = {}
    for v in verdicts:
        if v["status"] == "verified":
            counts[v["topic_id"]] = counts.get(v["topic_id"], 0) + 1
    open_ids = [
        t["topic_id"] for t in topics if counts.get(t["topic_id"], 0) < limits.min_verified_claims
    ]
    if not open_ids or round >= limits.rounds or exhausted:
        return "writer", []
    return "supervisor", open_ids
