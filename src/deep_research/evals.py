"""Live eval harness: run questions, then score each run by re-verifying it from the store."""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from deep_research.config import Settings
from deep_research.models import Limits
from deep_research.runner import RunSummary, reverify_run, start_run
from deep_research.store import PageStore


def load_suite(path: str | Path) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    questions = data["questions"]
    ids = [q["id"] for q in questions]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate question ids: {', '.join(dupes)}")
    for q in questions:
        q.setdefault("expected_domains", [])
    return questions


def _host_matches(url: str, domains: list[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def score_run(run: dict, store: PageStore, expected_domains: list[str] | None = None) -> dict:
    verdicts = run["verdicts"]
    proposed = len(run["claims"])
    verified_ids = {v["claim_id"] for v in verdicts if v["status"] == "verified"}
    rejected_by_reason: dict[str, int] = {}
    for v in verdicts:
        if v["status"] == "rejected":
            rejected_by_reason[v["reason"]] = rejected_by_reason.get(v["reason"], 0) + 1
    min_verified = run["limits"]["min_verified_claims"]
    per_topic: dict[str, int] = {}
    for v in verdicts:
        if v["status"] == "verified":
            per_topic[v["topic_id"]] = per_topic.get(v["topic_id"], 0) + 1
    topics = len(run["topics"])
    covered = sum(1 for t in run["topics"] if per_topic.get(t["topic_id"], 0) >= min_verified)
    again = reverify_run(run, store)
    url_of = {s["source_id"]: s["url"] for s in run["sources"]}
    share = None
    if expected_domains and verified_ids:
        hits = sum(
            1
            for c in run["claims"]
            if c["claim_id"] in verified_ids
            and any(
                _host_matches(url_of.get(x["source_id"], ""), expected_domains)
                for x in c["citations"]
            )
        )
        share = round(hits / len(verified_ids), 4)
    segments = run["budget"].get("segments", [])
    return {
        "proposed": proposed,
        "verified": len(verified_ids),
        "rejected": proposed - len(verified_ids),
        "rejected_by_reason": dict(sorted(rejected_by_reason.items())),
        "rejection_rate": round((proposed - len(verified_ids)) / proposed, 4) if proposed else None,
        "topics": topics,
        "topics_covered": covered,
        "coverage_rate": round(covered / topics, 4) if topics else None,
        "report_markers": again["report_markers"],
        "claims_reverified_same": again["same"],
        "unverifiable_shipped": again["unverifiable"],
        "writer": run["writer"],
        "status": run["status"],
        "wall_s": round(sum(s.get("wall_s", 0) for s in segments), 3),
        "tokens": run["budget"].get("tokens", 0),
        "expected_domain_share": share,
    }


def aggregate(scores: list[dict]) -> dict:
    ok = [s for s in scores if s.get("status") != "error"]
    proposed = sum(s["proposed"] for s in ok)
    rejected = sum(s["rejected"] for s in ok)
    by_reason: dict[str, int] = {}
    for s in ok:
        for reason, n in s["rejected_by_reason"].items():
            by_reason[reason] = by_reason.get(reason, 0) + n
    walls = [s["wall_s"] for s in ok]
    tokens = [s["tokens"] for s in ok]
    return {
        "questions": len(scores),
        "errors": len(scores) - len(ok),
        "proposed": proposed,
        "verified": sum(s["verified"] for s in ok),
        "rejected": rejected,
        "rejected_by_reason": dict(sorted(by_reason.items())),
        "rejection_rate": round(rejected / proposed, 4) if proposed else None,
        "topics": sum(s["topics"] for s in ok),
        "topics_covered": sum(s["topics_covered"] for s in ok),
        "unverifiable_shipped": sum(s["unverifiable_shipped"] for s in ok),
        "fallback_count": sum(1 for s in ok if s["writer"] == "fallback"),
        "median_wall_s": round(statistics.median(walls), 3) if walls else None,
        "max_wall_s": max(walls) if walls else None,
        "median_tokens": statistics.median(tokens) if tokens else None,
        "max_tokens": max(tokens) if tokens else None,
    }


def _markdown(result: dict) -> str:
    lines = [
        f"# Live eval {result['date']}",
        "",
        f"Model: `{result['model'].get('model')}`. Questions run: {len(result['questions'])}.",
        "",
        "| id | status | proposed | verified | rejected | rate | covered | writer | wall s |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for q in result["questions"]:
        if q["status"] == "error":
            lines.append(f"| {q['id']} | error | | | | | | | |")
            continue
        lines.append(
            f"| {q['id']} | {q['status']} | {q['proposed']} | {q['verified']} | {q['rejected']} "
            f"| {q['rejection_rate']} | {q['topics_covered']}/{q['topics']} | {q['writer']} "
            f"| {q['wall_s']} |"
        )
    agg = result["aggregate"]
    lines += [
        "",
        f"Aggregate: {agg['rejected']} of {agg['proposed']} proposed claims rejected "
        f"(rate {agg['rejection_rate']}); unverifiable citations shipped: "
        f"{agg['unverifiable_shipped']}; errors: {agg['errors']}.",
        "",
    ]
    return "\n".join(lines)


def run_eval(
    suite: list[dict],
    *,
    limit: int | None,
    limits: Limits,
    settings: Settings,
    runner: Callable[..., RunSummary] = start_run,
    out_dir: str | Path,
    suite_name: str = "evals/questions.yaml",
) -> Path:
    chosen = suite[:limit] if limit else suite
    store = PageStore(Path(settings.runs_dir) / "store.sqlite")
    results: list[dict] = []
    model: dict = {"model": settings.model, "digest": None}
    try:
        for q in chosen:
            try:
                summary = runner(q["question"], limits, settings)
                run = json.loads(summary.run_json_path.read_text(encoding="utf-8"))
                model = run.get("model") or model
                score = score_run(run, store, q.get("expected_domains"))
                results.append(
                    {"id": q["id"], "question": q["question"], "run_id": run["run_id"]} | score
                )
            except Exception as exc:
                results.append(
                    {
                        "id": q["id"],
                        "question": q["question"],
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    finally:
        store.close()
    date = datetime.now(UTC).date().isoformat()
    result = {
        "date": date,
        "suite": suite_name,
        "limit": limit,
        "limits": limits.model_dump(),
        "model": model,
        "questions": results,
        "aggregate": aggregate(results),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{date}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (out / f"{date}.md").write_text(_markdown(result), encoding="utf-8", newline="\n")
    return path
