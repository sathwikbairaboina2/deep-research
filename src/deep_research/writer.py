from __future__ import annotations

from collections.abc import Iterable

from quoteproof import lint_report, render_footnotes

from deep_research.budget import BudgetExceeded
from deep_research.deps import Deps
from deep_research.llm import LLMOutputError, call_structured
from deep_research.models import WriteOut
from deep_research.prompts import write_prompt


def select_writer_input(claims: list[dict], verdicts: list[dict]) -> list[dict]:
    """Exactly the claims whose verdict is verified, in original order (invariant 1)."""
    verified = {v["claim_id"] for v in verdicts if v["status"] == "verified"}
    return [c for c in claims if c["claim_id"] in verified]


def fallback_report(question: str, topics: list[dict], claims: list[dict]) -> str:
    """Deterministic report: one bullet per verified claim, grouped by topic."""
    parts = []
    for topic in topics:
        mine = [c for c in claims if c["topic_id"] == topic["topic_id"]]
        if not mine:
            continue
        bullets = "\n".join(f"- {c['text']} [c:{c['claim_id']}]" for c in mine)
        parts.append(f"## {topic['title']}\n\n{bullets}")
    return "\n\n".join(parts)


def footnote_notes(claims: list[dict], sources: list[dict]) -> dict[str, str]:
    urls: dict[str, str] = {}
    for s in sources:
        urls.setdefault(s["source_id"], s["url"])
    notes = {}
    for c in claims:
        cites = [
            f'"{x["quote"]}" - {urls.get(x["source_id"], x["source_id"])}' for x in c["citations"]
        ]
        notes[c["claim_id"]] = "; ".join(cites)
    return notes


def _draft_with_llm(
    deps: Deps, question: str, verified: list[dict], known_ids: Iterable[str]
) -> tuple[str, str, tuple[str, ...]] | None:
    """Return (draft, writer_mode, markers) for a lint-clean LLM draft, else None."""
    verified_ids = {c["claim_id"] for c in verified}
    known = set(known_ids)
    errors: list[str] | None = None
    for mode in ("llm", "llm_retry"):
        system, user = write_prompt(question, verified, errors)
        try:
            out = call_structured(
                deps.llm, deps.budget, purpose="write", system=system, user=user, model_cls=WriteOut
            )
        except (LLMOutputError, BudgetExceeded):
            return None
        result = lint_report(out.report_markdown, verified_ids, known)
        if result.ok:
            return out.report_markdown, mode, result.markers
        errors = [f"{e.code} {e.marker}".strip() for e in result.errors]
    return None


def write_report(
    deps: Deps,
    question: str,
    topics: list[dict],
    claims: list[dict],
    verdicts: list[dict],
    sources: list[dict],
    *,
    status: str = "done",
    caps_hit: Iterable[str] = (),
) -> dict:
    verified = select_writer_input(claims, verdicts)
    proposed, n_verified = len(claims), len(verified)
    header = (
        f"# {question}\n\n_Status: {status}. {n_verified} of {proposed} proposed claims "
        f"verified; {proposed - n_verified} rejected by the citation verifier._\n\n"
    )
    caps = sorted(set(caps_hit))
    if caps:
        header += f"_Budget caps hit: {', '.join(caps)}._\n\n"

    if not verified:
        draft, mode, markers, body = "", "none", (), "No verified claims."
    else:
        found = _draft_with_llm(deps, question, verified, (c["claim_id"] for c in claims))
        if found is None:
            draft = fallback_report(question, topics, verified)
            lint = lint_report(
                draft, {c["claim_id"] for c in verified}, {c["claim_id"] for c in claims}
            )
            if not lint.ok:  # cannot happen by construction; never ship a bad report
                raise RuntimeError(f"fallback report failed lint: {lint.errors}")
            mode, markers = "fallback", lint.markers
        else:
            draft, mode, markers = found
        body = render_footnotes(draft, footnote_notes(verified, sources))

    counts: dict[str, int] = {}
    for c in verified:
        counts[c["topic_id"]] = counts.get(c["topic_id"], 0) + 1
    thin = [t for t in topics if counts.get(t["topic_id"], 0) < deps.limits.min_verified_claims]
    tail = ""
    if thin:
        lines = "\n".join(f"- {t['title']} ({counts.get(t['topic_id'], 0)} verified)" for t in thin)
        tail = f"\n\n## Under-covered topics\n\n{lines}"
    return {
        "report_md": header + body + tail + "\n",
        "report_draft": draft,
        "writer": mode,
        "report_markers": list(markers),
    }
