from __future__ import annotations

import json
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from quoteproof import NORM_VERSION, Citation, Claim, Corpus, verify_claims

from deep_research.budget import Budget
from deep_research.config import Settings
from deep_research.deps import Deps
from deep_research.fetch import Fetcher, RobotsCache
from deep_research.graph import build_graph
from deep_research.llm import LLM, OllamaLLM
from deep_research.models import Limits
from deep_research.search import SearxngSearch
from deep_research.store import PageStore


@dataclass
class RunSummary:
    run_id: str
    status: str
    report_path: Path
    run_json_path: Path
    proposed: int
    verified: int
    rejected: int
    writer: str
    budget: dict


def new_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _pkg_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def run_dir(settings: Settings, run_id: str) -> Path:
    return Path(settings.runs_dir) / run_id


def _default_edges(settings: Settings, limits: Limits, llm, search, fetch):
    if llm is None:
        llm = OllamaLLM(settings.ollama_base_url, settings.model)
    if search is None:
        search = SearxngSearch(settings.searxng_url, httpx.Client())
    if fetch is None:
        client = httpx.Client()
        fetch = Fetcher(
            client,
            max_bytes=limits.max_bytes,
            timeout_s=limits.fetch_timeout_s,
            robots=RobotsCache(client),
        )
    return llm, search, fetch


def _execute(
    run_id: str,
    question: str,
    limits: Limits,
    settings: Settings,
    *,
    resume: bool,
    llm: LLM | None,
    search,
    fetch,
) -> RunSummary:
    runs_dir = Path(settings.runs_dir)
    rdir = run_dir(settings, run_id)
    rdir.mkdir(parents=True, exist_ok=True)
    meta_path = rdir / "meta.json"
    run_json_path = rdir / "run.json"
    report_path = rdir / "report.md"

    previous: dict = {}
    if run_json_path.exists():
        previous = json.loads(run_json_path.read_text(encoding="utf-8"))
    if not resume:
        _write_json(rdir / "limits.json", limits.model_dump())
        _write_json(meta_path, {"question": question, "started_at": _now()})
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    llm, search, fetch = _default_edges(settings, limits, llm, search, fetch)
    store = PageStore(runs_dir / "store.sqlite")
    start = store.budget_totals(run_id) if resume else None
    budget = Budget(
        limits, sink=lambda kind, n: store.add_budget_event(run_id, kind, n), start=start
    )
    deps = Deps(
        llm=llm,
        search=search,
        fetch=fetch,
        store=store,
        budget=budget,
        limits=limits,
        run_id=run_id,
    )
    conn = sqlite3.connect(str(runs_dir / "checkpoints.sqlite"), check_same_thread=False)
    graph = build_graph(deps, checkpointer=SqliteSaver(conn))
    config = {
        "configurable": {"thread_id": run_id},
        "max_concurrency": limits.researchers,
        "recursion_limit": 100,
    }
    segment = {"started_at": _now()}
    t0 = time.monotonic()
    error: str | None = None
    try:
        if resume:
            snap = graph.get_state(config)
            final = graph.invoke(None, config) if snap.next else dict(snap.values)
        else:
            final = graph.invoke({"run_id": run_id, "question": question}, config)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        final = dict(graph.get_state(config).values or {})
        final["status"] = "failed"
        raise
    finally:
        segment["wall_s"] = round(time.monotonic() - t0, 3)
        describe = getattr(llm, "describe", None)
        model = describe() if describe else {"model": getattr(llm, "model", None), "digest": None}
        status = final.get("status", "failed") if error is None else "failed"
        claims = final.get("claims", [])
        verdicts = final.get("verdicts", [])
        verified = sum(1 for v in verdicts if v["status"] == "verified")
        snapshot = budget.snapshot()
        snapshot["segments"] = [*previous.get("budget", {}).get("segments", []), segment]
        run_json = {
            "run_id": run_id,
            "question": question,
            "status": status,
            "limits": limits.model_dump(),
            "model": model,
            "norm": NORM_VERSION,
            "topics": final.get("topics", []),
            "claims": claims,
            "verdicts": verdicts,
            "sources": final.get("sources", []),
            "report_markers": final.get("report_markers", []),
            "report_draft": final.get("report_draft", ""),
            "writer": final.get("writer", "none"),
            "budget": snapshot,
            "caps_hit": sorted(set(final.get("budget_hit", [])) | set(budget.caps_hit())),
            "errors": final.get("errors", []),
            "started_at": meta.get("started_at"),
            "finished_at": _now(),
            "versions": {
                "deep_research": _pkg_version("deep-research"),
                "quoteproof": _pkg_version("quoteproof"),
                "langgraph": _pkg_version("langgraph"),
            },
        }
        if error:
            run_json["error"] = error
        _write_json(run_json_path, run_json)
        if error is None:
            report = final.get("report_md") or f"# {question}\n\n_Status: {status}._\n"
            report_path.write_text(report, encoding="utf-8", newline="\n")
        store.close()
        conn.close()
    return RunSummary(
        run_id=run_id,
        status=status,
        report_path=report_path,
        run_json_path=run_json_path,
        proposed=len(claims),
        verified=verified,
        rejected=len(claims) - verified,
        writer=run_json["writer"],
        budget=snapshot,
    )


def start_run(
    question: str,
    limits: Limits,
    settings: Settings,
    *,
    llm: LLM | None = None,
    search=None,
    fetch=None,
    run_id: str | None = None,
) -> RunSummary:
    run_id = run_id or new_run_id()
    return _execute(
        run_id, question, limits, settings, resume=False, llm=llm, search=search, fetch=fetch
    )


def resume_run(
    run_id: str, settings: Settings, *, llm: LLM | None = None, search=None, fetch=None
) -> RunSummary:
    rdir = run_dir(settings, run_id)
    meta = json.loads((rdir / "meta.json").read_text(encoding="utf-8"))
    limits = Limits(**json.loads((rdir / "limits.json").read_text(encoding="utf-8")))
    return _execute(
        run_id, meta["question"], limits, settings, resume=True, llm=llm, search=search, fetch=fetch
    )


def reverify_run(run: dict, store: PageStore) -> dict:
    """Re-verify every claim of a run against the stored texts and compare with run.json.

    `unverifiable` counts report markers whose claim does not re-verify.
    """
    corpus = Corpus(store.texts_for_run(run["run_id"]))
    claims = [
        Claim(
            c["claim_id"],
            c["text"],
            tuple(Citation(x["source_id"], x["quote"]) for x in c["citations"]),
        )
        for c in run["claims"]
    ]
    now = {v.claim_id: v.status for v in verify_claims(claims, corpus)}
    recorded = {v["claim_id"]: v["status"] for v in run["verdicts"]}
    same = sum(1 for cid in now if recorded.get(cid) == now[cid])
    markers = run.get("report_markers", [])
    unverifiable = sum(1 for m in markers if now.get(m) != "verified")
    return {
        "claims": len(claims),
        "same": same,
        "report_markers": len(markers),
        "unverifiable": unverifiable,
    }
