from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from deep_research.config import Settings
from deep_research.models import Limits
from deep_research.runner import resume_run, reverify_run, start_run
from deep_research.store import PageStore

OK_STATUSES = {"done", "budget_exhausted"}

# (flag, Limits field, type)
LIMIT_FLAGS = [
    ("--max-searches", "max_searches", int),
    ("--max-fetches", "max_fetches", int),
    ("--max-tokens", "max_tokens", int),
    ("--max-wall", "max_wall_s", float),
    ("--researchers", "researchers", int),
    ("--rounds", "rounds", int),
    ("--topics", "max_topics", int),
]


def add_limit_flags(p: argparse.ArgumentParser) -> None:
    for flag, dest, typ in LIMIT_FLAGS:
        p.add_argument(flag, dest=dest, type=typ, default=None)


def limits_from_args(args: argparse.Namespace) -> Limits:
    given = {
        dest: getattr(args, dest) for _, dest, _ in LIMIT_FLAGS if getattr(args, dest) is not None
    }
    return Limits(**given)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dr", description="Local-first research agent with verified citations."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def runs_dir(p: argparse.ArgumentParser) -> None:
        p.add_argument("--runs-dir", default=None, help="default: $DR_RUNS_DIR or ./runs")

    p = sub.add_parser("run", help="research a question")
    p.add_argument("question")
    p.add_argument("--run-id", default=None)
    add_limit_flags(p)
    runs_dir(p)

    p = sub.add_parser("resume", help="continue a crashed run from its checkpoint")
    p.add_argument("run_id")
    runs_dir(p)

    p = sub.add_parser("show", help="print the claims of a run")
    p.add_argument("run_id")
    p.add_argument("--rejected", action="store_true")
    runs_dir(p)

    p = sub.add_parser("verify", help="re-verify a run's claims and report markers")
    p.add_argument("run_id")
    runs_dir(p)

    p = sub.add_parser("eval", help="run the live eval suite")
    p.add_argument("--suite", default="evals/questions.yaml")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--only", default=None, help="comma-separated question ids")
    p.add_argument("--out", default="evals/results")
    add_limit_flags(p)
    runs_dir(p)

    p = sub.add_parser("bench", help="offline verifier benchmark")
    p.add_argument("--pages", default="tests/fixtures/pages")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--per-page", type=int, default=40)
    p.add_argument("--out", default=None)
    p.add_argument("--check", default=None)

    p = sub.add_parser("serve", help="read-only web view of runs")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5301)
    runs_dir(p)
    return parser


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()
    if getattr(args, "runs_dir", None):
        settings = Settings(
            ollama_base_url=settings.ollama_base_url,
            searxng_url=settings.searxng_url,
            model=settings.model,
            runs_dir=Path(args.runs_dir),
        )
    return settings


def _load_run(settings: Settings, run_id: str) -> dict:
    path = settings.runs_dir / run_id / "run.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _cmd_run(args, settings, deps_factory) -> int:
    kwargs = deps_factory() if deps_factory else {}
    summary = start_run(
        args.question, limits_from_args(args), settings, run_id=args.run_id, **kwargs
    )
    _print_summary(summary)
    return 0 if summary.status in OK_STATUSES else 1


def _print_summary(summary) -> None:
    print(f"run_id: {summary.run_id}")
    print(f"status: {summary.status}")
    print(f"verified {summary.verified}/{summary.proposed}")
    print(f"report: {summary.report_path}")


def _cmd_resume(args, settings, deps_factory) -> int:
    kwargs = deps_factory() if deps_factory else {}
    summary = resume_run(args.run_id, settings, **kwargs)
    _print_summary(summary)
    return 0 if summary.status in OK_STATUSES else 1


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def _cmd_show(args, settings) -> int:
    run = _load_run(settings, args.run_id)
    verdicts = {v["claim_id"]: v for v in run["verdicts"]}
    rows = []
    for claim in run["claims"]:
        verdict = verdicts.get(claim["claim_id"], {"status": "unverified", "reason": None})
        if args.rejected and verdict["status"] != "rejected":
            continue
        rows.append((claim, verdict))
    width = max([len(c["claim_id"]) for c, _ in rows] + [8])
    print(f"{'claim_id':<{width}} | {'status':<8} | {'reason':<16} | claim")
    for claim, verdict in rows:
        print(
            f"{claim['claim_id']:<{width}} | {verdict['status']:<8} | "
            f"{verdict['reason'] or '-':<16} | {_clip(claim['text'], 60)}"
        )
        if args.rejected and claim["citations"]:
            print(f"{'':<{width}}   quote: {_clip(claim['citations'][0]['quote'], 80)}")
    return 0


def _cmd_verify(args, settings) -> int:
    run = _load_run(settings, args.run_id)
    store = PageStore(settings.runs_dir / "store.sqlite")
    try:
        result = reverify_run(run, store)
    finally:
        store.close()
    print(
        f"claims: {result['claims']}  re-verified same: {result['same']}  "
        f"report markers: {result['report_markers']}  unverifiable: {result['unverifiable']}"
    )
    return 0 if result["same"] == result["claims"] and result["unverifiable"] == 0 else 1


def main(argv: list[str] | None = None, *, deps_factory: Callable[[], dict] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command in ("run", "eval"):
            limits_from_args(args)  # validate flags early
    except SystemExit as exc:
        return int(exc.code or 0)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    settings = _settings(args)
    try:
        if args.command == "run":
            return _cmd_run(args, settings, deps_factory)
        if args.command == "resume":
            return _cmd_resume(args, settings, deps_factory)
        if args.command == "show":
            return _cmd_show(args, settings)
        if args.command == "verify":
            return _cmd_verify(args, settings)
        if args.command == "bench":
            from deep_research.bench import bench_main

            return bench_main(args.pages, args.seed, args.per_page, args.out, args.check)
        print(f"dr {args.command}: not implemented", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
