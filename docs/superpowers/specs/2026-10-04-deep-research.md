# deep-research v0.1 spec (2026-10-04)

Source design: `taskarinchu/docs/devdocs/deep-research.md`. This spec is the binding v0.1 cut of that design. Where they differ, this spec wins and the difference is an ADR in `docs/adr/`.

## One line

A local-first LangGraph research agent. The model proposes claims with quotes; a deterministic verifier (`quoteproof`, a zero-dependency package) throws out every claim whose quote is not on the page it cites. Only verified claims reach the report.

## Portfolio bar (what "done" means)

| Bar | v0.1 answer |
|---|---|
| 30-second wow | README opens with a real run: the report excerpt plus the "rejected claims" table from `dr show --rejected` (real model output, real reason codes). `dr serve` renders the same run with the quote highlighted in the stored page text. |
| Measured headline number | Two measured sources, both committed as JSON: (1) `dr bench` offline verifier benchmark over committed fixture pages (reproducible in CI); (2) `dr eval` live runs: claim rejection rate and "unverifiable citations shipped" (must be 0). README quotes only numbers present in those files. |
| Something installable | `quoteproof` wheel (zero runtime deps) built with `uv build --package quoteproof`, plus the `deep-research` wheel (CLI `dr`) and the Docker image `deep-research-app`. Nothing is published (no push). |
| Honest ADRs | `docs/adr/0001`..`0010`, each with "What I gave up". |
| CI with tests | `.github/workflows/ci.yml`: ruff, pytest (unit + fake-LLM graph tiers, network disabled), `dr bench`, wheel build. |

## Scope

In v0.1 (pulled forward from the design's v0.2 because the board pitch is "supervisor plus parallel researcher subgraphs"):

- Planner, supervisor with `Send` fan-out, researcher subgraph, verifier, coverage gate with round caps, writer, report linter.
- SearXNG search, fetch with limits and robots.txt, trafilatura/pypdf extraction, SQLite page store.
- Budget ledger with hard caps, persisted in SQLite.
- `SqliteSaver` checkpoints and `dr resume`.
- CLI: `dr run | resume | verify | show | eval | bench | serve`.
- Eval suite (12 questions) and live eval results JSON.
- `dr serve`: read-only stdlib HTTP view (runs list, report, rejected tab, source view with highlighted quote).
- Docker compose (SearXNG + app), CI workflow.

Out of v0.1: JavaScript rendering, PDF page-number citations, LLM judge for quote-supports-claim, hosted providers, demo GIF (README uses real text output instead), PyPI publish.

## Package layout

```
deep-research/                      uv workspace root, package "deep-research" (module deep_research)
  packages/quoteproof/              package "quoteproof" (module quoteproof), zero runtime deps
    src/quoteproof/{__init__,normalize,verify,lint}.py
    tests/
  src/deep_research/
    __init__.py  config.py  models.py  budget.py  store.py  urls.py  search.py  fetch.py
    llm.py  prompts.py  nodes.py  researcher.py  graph.py  writer.py  runner.py
    cli.py  evals.py  bench.py  serve.py
  tests/  tests/fixtures/{pages,searxng}/
  evals/questions.yaml  evals/results/
  bench/results/
  searxng/settings.yml  Dockerfile  docker-compose.yml  .github/workflows/ci.yml
```

## Behaviour contract

### quoteproof (pure, no I/O, no third-party imports)

- `NORM_VERSION = "NORM_V1"`. `normalize(s)`: NFKC; map `‘ ’ ‚ ‛ ′` to `'`, `“ ” „ ‟ ″` to `"`, `‐ ‑ ‒ – — ― −` to `-`; collapse every whitespace run to one space; strip; casefold. Idempotent.
- `verify_claim(claim, texts)`: `texts` maps `source_id -> raw text` for this run only.
  - No citations: `rejected`, reason `NO_CITATIONS`.
  - Per citation, first failing check wins: `UNKNOWN_SOURCE` (id not in `texts`), `QUOTE_TOO_SHORT` (normalized quote has fewer than 6 words or fewer than 30 characters), `QUOTE_TOO_LONG` (more than 80 words), `QUOTE_NOT_FOUND` (normalized quote not a substring of normalized text). Otherwise `found` with `offset` = index into the normalized text and `match = "exact_normalized"`.
  - The claim is `verified` only if every citation is `found`. Otherwise `rejected`, `reason` = code of the first non-found citation.
  - Every verdict carries `norm = "NORM_V1"`.
- `Corpus(texts)`: caches normalized texts; `verify_claim` accepts a `Corpus` or a plain mapping. Output is identical for identical inputs (no randomness, no clock).
- `lint_report(draft, verified_ids, known_ids)`: markers are `[c:<id>]` with `<id>` matching `[A-Za-z0-9][A-Za-z0-9_.-]*`. Errors: `MALFORMED_MARKER` (any `[c:` not forming a valid marker), `UNKNOWN_MARKER` (id not in `known_ids`), `REJECTED_MARKER` (known but not verified), `NO_MARKERS` (draft has zero valid markers). `ok` iff no errors.
- `render_footnotes(draft, notes)`: replaces markers with `[^n]` numbered by first appearance, appends `[^n]: <notes[id]>` lines. Only called on a lint-clean draft.

### Agent

- Claim ids: `t<topic>-r<round>-c<n>` (e.g. `t2-r1-c3`), unique per run.
- The LLM sees sources as labels `S1..Sn`; the extractor maps labels back to `sha256:` source ids. An unknown label becomes `source_id = "label:<label>"`, which the verifier rejects as `UNKNOWN_SOURCE` (ADR-0006).
- Writer input is exactly the verified subset of proposed claims (invariant 1).
- Writer gets one retry with the lint errors; if the second draft still fails lint, the deterministic fallback report (verified claims as bullets with markers, grouped by topic) is used and `run.json` records `"writer": "fallback"` (ADR-0007). A report with orphan or rejected markers is never written.
- Zero verified claims: no writer call; report says "No verified claims" and status is `budget_exhausted` or `done` as the gate decided; `run.json` is still written.

### Limits (defaults; all CLI flags)

| Field | Default | Flag |
|---|---|---|
| `max_searches` | 40 | `--max-searches` |
| `max_fetches` | 60 | `--max-fetches` |
| `max_tokens` | 400000 | `--max-tokens` |
| `max_wall_s` | 900 | `--max-wall` (seconds) |
| `researchers` (max concurrent `Send`s via `max_concurrency`) | 4 | `--researchers` |
| `rounds` | 2 | `--rounds` |
| `max_topics` | 5 | `--topics` |
| `queries_per_topic` | 2 | |
| `results_per_query` | 3 | |
| `sources_per_extract` | 3 | |
| `source_chars` (per source in extract prompt) | 6000 | |
| `min_verified_claims` | 2 | |
| `max_bytes` | 2000000 | |
| `fetch_timeout_s` | 20 | |

### Storage

- `<runs_dir>/store.sqlite`: `texts(source_id PK, text)`, `sources(run_id, canonical_url, source_id, url, fetched_at, http_status, content_type, bytes, extractor, PK(run_id, canonical_url))`, `budget_events(run_id, seq, kind, amount, at, PK(run_id, seq))`. (Design said `sources` PK `source_id`; changed because the same page can be fetched by several runs.)
- `<runs_dir>/checkpoints.sqlite`: LangGraph `SqliteSaver`, `thread_id = run_id`.
- `<runs_dir>/<run_id>/run.json` and `report.md`.
- `runs_dir` default `./runs`, env `DR_RUNS_DIR`.

### Environment

`OLLAMA_BASE_URL` (default `http://localhost:11434`), `SEARXNG_URL` (default `http://localhost:5300`), `DR_MODEL` (default `qwen3.8:27b`), `DR_RUNS_DIR`. No secrets.

### Ports and names

SearXNG host port `127.0.0.1:5300`, `dr serve` default `127.0.0.1:5301`. Compose project `deep-research`, containers `deep-research-searxng`, image `deep-research-app`.

## Invariants (each has a named test)

| # | Invariant | Test |
|---|---|---|
| 1 | Writer input is exactly the verified subset | `tests/test_writer.py::test_writer_input_only_verified` (Hypothesis) |
| 2 | Verifier is pure | `packages/quoteproof/tests/test_verify.py::test_verifier_is_pure` (socket disabled, 100 shuffled repeats) |
| 3 | Mutated quotes are rejected | `packages/quoteproof/tests/test_verify.py::test_mutated_quotes_rejected` |
| 4 | Every report marker resolves to a verified claim | `packages/quoteproof/tests/test_lint.py::test_linter_rejects_orphan_markers` and `tests/test_graph.py::test_report_markers_all_verified` |
| 5 | Search/fetch caps exact; tokens reservation-capped; wall clock checked | `tests/test_budget.py::test_budget_hard_caps`, `tests/test_graph.py::test_graph_respects_search_cap` |
| 6 | Fetch byte cap, timeout, content-type allowlist | `tests/test_fetch.py::test_fetch_limits` |
| 7 | Parallel researchers never lose claims | `tests/test_graph.py::test_fanout_merge` |
| 8 | Resume does not refetch or double count | `tests/test_resume.py::test_resume_after_crash` |
| 9 | Round and fan-out caps | `tests/test_graph.py::test_round_and_fanout_caps` |

## Metrics

- `bench/results/latest.json` (from `dr bench`): genuine quotes accepted / total, mutated quotes rejected / total, by mutation kind; corpus = 5 committed SQLite doc pages (public domain); seed 42.
- `evals/results/<date>.json` (from `dr eval`): per question and aggregate: proposed, verified, rejected by code, rejection rate, topics covered, unverifiable citations shipped (re-verified from the store; must be 0), writer mode, wall seconds, tokens, model name.
