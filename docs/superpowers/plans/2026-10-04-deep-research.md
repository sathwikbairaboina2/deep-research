# deep-research v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans (one builder, one context) or superpowers:subagent-driven-development to implement this plan task by task. Use superpowers:test-driven-development for every task (write the test, run it, see it fail, implement, see it pass) and superpowers:verification-before-completion before claiming done. Steps use checkboxes (`- [ ]`).

**Goal:** Ship a local-first LangGraph research agent (planner, supervisor with `Send` fan-out, researcher subgraphs, deterministic citation verifier, coverage gate, writer with linter, budget caps, checkpoint resume), the zero-dependency `quoteproof` verifier package, a CLI `dr`, an offline benchmark, a live eval, a read-only web view, Docker compose and CI.

**Architecture:** A uv workspace. `packages/quoteproof` is pure stdlib (normalize, verify, lint). `src/deep_research` holds the I/O edges (`search`, `fetch`, `store`, `llm`), the budget, the LangGraph graph (`nodes`, `researcher`, `graph`, `writer`), the run orchestration (`runner`) and the entry points (`cli`, `bench`, `evals`, `serve`). Every I/O edge is injected through a `Deps` dataclass so tests run with sockets disabled, a scripted LLM and fake search/fetch.

**Tech stack (all versions checked on PyPI / registries on 2026-10-04):** CPython 3.12, uv 0.12.21 (build backend `uv_build>=0.12.21,<0.13`), langgraph 1.2.12, langgraph-checkpoint-sqlite 3.1.1, httpx 0.28.1, pydantic 2.13.5, trafilatura 2.3.0, pypdf 6.19.0, pyyaml 6.0.3. Dev: pytest 9.1.1, pytest-socket 0.8.1, hypothesis 6.168.3, ruff 0.16.10. Docker: `python:3.12-slim-bookworm`, `ghcr.io/astral-sh/uv:0.12.21`, `searxng/searxng:2026.10.2-19ffbcd30`. CI: `actions/checkout@v4`, `astral-sh/setup-uv@v10.2.0`.

**Spec:** `docs/superpowers/specs/2026-10-04-deep-research.md`. **Decisions:** `docs/adr/0001`-`0010`. Read both before Task 1.

**Ledger:** `.superpowers/sdd/2026-10-04-deep-research/progress.md`. Append one line per task: `Task N: complete (tests: <command> -> <real result>; red seen: <what failed first>)`. Record every deviation as `Ruling: <what> - <why> - <cost>`. A fresh builder resumes from the first task without a `complete` line.

## Status at hand-off from planner

- DONE (planner, Task 0): `git init -b main`; spec, ADRs, this plan, ledger; fixtures copied to `tests/fixtures/pages/*.html` (5 SQLite doc pages, public domain) and `tests/fixtures/searxng/sqlite_wal.json` (a real SearXNG JSON response, thumbnails blanked). Committed.
- Prototypes run by the planner (scratchpad, not in repo): Send fan-out with `max_concurrency` (peak 3 of 8, 16 claims merged over 2 rounds); `SqliteSaver` crash and resume under `pytest --disable-socket` on Windows (only the failed branch re-ran); trafilatura on the 5 pages (`"WAL provides more concurrency as readers do not block writers"` present verbatim); Ollama `/api/chat` with `format` schema and `think:false` (4 of 4 quotes found, 138.8 s); bench idea (198 of 200 genuine quotes found). SearXNG JSON on port 5300 returned 20 results (brave and duckduckgo were rate-limited; google cse answered).
- NOT STARTED: Tasks 1-24.

## Global constraints

- Work only in `C:\Users\sathwik\projects\taskarinchu\deep-research`. Never edit sibling directories. Wave-1 repos may be read for style.
- Commands are for **Git Bash** from the repo root (`cd /c/Users/sathwik/projects/taskarinchu/deep-research`). Use forward slashes. Pipe noisy output through `tail -n 20` or `grep`.
- **Windows Application Control blocks new venv launchers on this host.** Prototype: `uv run dr` failed with `An Application Control policy has blocked this file. (os error 4551)`, while `uv run pytest`, `uv run ruff` and `uv run python -m deep_research` worked. So on the host always invoke the CLI as `uv run python -m deep_research <args>` (needs `src/deep_research/__main__.py`). The `dr` script still ships for Linux, Docker and CI, and docs show `dr` for users.
- Host ports 5300-5309 only (SearXNG 5300, `dr serve` 5301). Docker compose project `deep-research`; every container name starts with `deep-research-`. Stop containers you start (`docker compose down`) at the end of the task that started them, except where a task says to leave SearXNG up for the next task.
- Pin exactly the versions above with `==` in `pyproject.toml`. Do not add dependencies beyond them. If one is truly needed, write a `Ruling:` line.
- Graph state holds only JSON-able plain data (dicts, lists, str, int). Pydantic models are used at boundaries and dumped with `model_dump()` before entering state. (LangGraph's checkpoint serializer restricts which classes it revives; plain data avoids that.)
- Tests never touch the network or Ollama. The suite runs with `--disable-socket`. Fetch and serve tests opt in with `@pytest.mark.allow_hosts(["127.0.0.1"])`. Live tests are marked `live` and skip unless `DR_LIVE=1`.
- Never invent numbers. Every number in README, DEVDOCS or the ledger comes from a command you ran, copied from its output or from a committed JSON file.
- No secrets, no `.env` files committed. Never push, never add a remote.
- **Commits (authorized, local only):** one conventional commit per task with the subject given in the task, ending with the trailer line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Check `git status --short` and stage only the task's files (never blind `git add -A`). If a hook or permission check blocks a commit, do not work around it; write a `Ruling:` line and continue.
- `uv.lock` is created in Task 1 and must not change afterwards unless a `Ruling:` adds a dependency.
- Line endings: `.gitattributes` (committed in Task 0) has `* text=auto eol=lf` and `tests/fixtures/** -text`, so fixtures stay byte-identical and bench numbers reproduce on Linux CI.

## Review focus (the reviewer will check these first)

1. A claim reaches the writer or the report only if every citation is `found` (invariants 1 and 4). The fallback writer path too.
2. Search and fetch counts never exceed caps, also with 4 parallel researchers (invariant 5, test with real threads).
3. Fetch byte cap, slow-drip timeout and content-type rejection use a real local HTTP server (invariant 6), not mocks.
4. Resume does not refetch or double count (invariant 8).
5. README numbers match `bench/results/latest.json` and `evals/results/*.json` exactly.
6. No fake tests: every invariant test fails if the guarded code is removed (the builder records the red step).

## File map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Workspace root, package `deep-research`, script `dr`, ruff and pytest config |
| `packages/quoteproof/pyproject.toml` | Package `quoteproof`, no dependencies |
| `packages/quoteproof/src/quoteproof/normalize.py` | `NORM_VERSION`, `normalize` |
| `packages/quoteproof/src/quoteproof/verify.py` | `Citation`, `Claim`, `CitationResult`, `Verdict`, `Corpus`, `check_quote`, `verify_claim`, `verify_claims`, codes |
| `packages/quoteproof/src/quoteproof/lint.py` | `MARKER_RE`, `LintError`, `LintResult`, `lint_report`, `render_footnotes` |
| `src/deep_research/config.py` | `Settings.from_env()` |
| `src/deep_research/models.py` | `Limits`, LLM output models, `SearchHit`, `FetchResult` |
| `src/deep_research/budget.py` | `Budget`, `BudgetExceeded` |
| `src/deep_research/store.py` | `PageStore` (SQLite) |
| `src/deep_research/urls.py` | `canonical_url`, `is_denied` |
| `src/deep_research/search.py` | `SearxngSearch` |
| `src/deep_research/fetch.py` | `Fetcher`, `extract_text`, `RobotsCache` |
| `src/deep_research/llm.py` | `LLMRequest`, `LLMResult`, `LLM`, `OllamaLLM`, `ScriptedLLM`, `call_structured`, `LLMOutputError` |
| `src/deep_research/prompts.py` | Prompt builders (pure string functions) |
| `src/deep_research/deps.py` | `Deps` dataclass |
| `src/deep_research/nodes.py` | `plan_topics`, `write_queries`, `gather_sources`, `extract_claims`, `verify_new_claims`, `coverage_decision` |
| `src/deep_research/researcher.py` | Researcher subgraph builder |
| `src/deep_research/graph.py` | `ResearchState`, `build_graph` |
| `src/deep_research/writer.py` | `select_writer_input`, `fallback_report`, `write_report` |
| `src/deep_research/runner.py` | `start_run`, `resume_run`, `RunSummary`, run.json and report.md |
| `src/deep_research/cli.py` | `main(argv) -> int` |
| `src/deep_research/bench.py` | `html_sentences`, `mutate`, `run_bench` |
| `src/deep_research/evals.py` | `load_suite`, `score_run`, `aggregate`, `run_eval` |
| `src/deep_research/serve.py` | `make_server` (stdlib, read-only) |
| `tests/fakes.py` | `FakeSearch`, `FakeFetch`, `scripted_llm()` helpers shared by graph tests |
| `evals/questions.yaml` | 12-question suite |
| `Dockerfile`, `docker-compose.yml`, `searxng/settings.yml`, `.dockerignore` | Containers |
| `.github/workflows/ci.yml` | CI |

---

### Task 0: Planning docs (DONE by planner)

Commit `docs: v0.1 spec, ADRs, plan and fixtures`.

---

### Task 1: Workspace scaffold

**Files:** create `pyproject.toml`, `packages/quoteproof/pyproject.toml`, `packages/quoteproof/README.md`, `packages/quoteproof/src/quoteproof/__init__.py`, `src/deep_research/__init__.py`, `src/deep_research/__main__.py` (`import sys; from deep_research.cli import main; sys.exit(main())`), `src/deep_research/cli.py` (stub `main(argv=None) -> int` printing usage, replaced in Task 16), `.python-version` (`3.12`), `.gitignore`, `tests/test_smoke.py`, `packages/quoteproof/tests/test_smoke_qp.py`, `tests/fixtures/README.md`.

- [ ] Root `pyproject.toml`:

```toml
[project]
name = "deep-research"
version = "0.1.0"
description = "Local-first LangGraph research agent whose citations are checked by a deterministic verifier."
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
dependencies = [
  "quoteproof==0.1.0",
  "langgraph==1.2.12",
  "langgraph-checkpoint-sqlite==3.1.1",
  "httpx==0.28.1",
  "pydantic==2.13.5",
  "trafilatura==2.3.0",
  "pypdf==6.19.0",
  "pyyaml==6.0.3",
]

[project.scripts]
dr = "deep_research.cli:main"

[build-system]
requires = ["uv_build>=0.12.21,<0.13"]
build-backend = "uv_build"

[dependency-groups]
dev = ["pytest==9.1.1", "pytest-socket==0.8.1", "hypothesis==6.168.3", "ruff==0.16.10"]

[tool.uv.workspace]
members = ["packages/quoteproof"]

[tool.uv.sources]
quoteproof = { workspace = true }

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests", "packages/quoteproof/tests"]
addopts = "-q --disable-socket --import-mode=importlib"
markers = ["live: needs Ollama and SearXNG; runs only with DR_LIVE=1"]
```

- [ ] `packages/quoteproof/pyproject.toml`: name `quoteproof`, version `0.1.0`, description "Deterministic check that a cited quote is really on the cited page.", `requires-python = ">=3.10"`, `dependencies = []`, same `[build-system]`, `readme = "README.md"`, license MIT. `README.md`: 15 lines: what it does, `pip install quoteproof` (local wheel for now), a 6-line usage example (filled in Task 3).
- [ ] `__init__.py` files: `__version__ = "0.1.0"` (quoteproof also re-exports later).
- [ ] `README.md` at root: one line placeholder `# deep-research` (rewritten in Task 23; uv_build needs it).
- [ ] `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.hypothesis/`, `dist/`, `runs/`, `*.sqlite`, `.env`, `.env.*`, `!.env.example`.
- [ ] `.gitattributes` already exists from Task 0 (`* text=auto eol=lf`, `tests/fixtures/** -text`); do not change it. The host has `core.autocrlf=true`, and the attribute keeps fixture bytes identical on Linux CI.
- [ ] `tests/fixtures/README.md`: pages are from https://www.sqlite.org (public domain, see sqlite.org/copyright.html), fetched 2026-10-04; the SearXNG response is a real query "sqlite wal mode concurrency" from 2026-10-04 with thumbnails blanked.
- [ ] Smoke tests: `assert deep_research.__version__ == "0.1.0"` and `assert quoteproof.__version__ == "0.1.0"`. A third test `test_sockets_disabled` asserts `socket.socket()` raises `pytest_socket.SocketBlockedError`.
- [ ] Run:

```bash
uv sync 2>&1 | tail -n 3
uv run pytest 2>&1 | tail -n 3
uv run ruff check . && uv run ruff format --check .
```
Expected: `3 passed`; ruff `All checks passed!` and `N files already formatted`.

- [ ] Commit `chore: uv workspace scaffold with quoteproof member` (include `uv.lock`).

---

### Task 2: `quoteproof.normalize`

**Files:** `packages/quoteproof/src/quoteproof/normalize.py`, `packages/quoteproof/tests/test_normalize.py`.

- [ ] Tests first:
  - `normalize("  WAL\u00a0provides\n\tmore ") == "wal provides more"`
  - `normalize("\u201cReaders\u201d don\u2019t block \u2013 writers") == '"readers" don\'t block - writers'`
  - `normalize("\ufb01le") == "file"` (NFKC ligature)
  - `normalize("STRASSE") == normalize("straße")` (casefold)
  - Hypothesis `@given(st.text())`: idempotent `normalize(normalize(s)) == normalize(s)`; no leading/trailing space; no `"  "`; no `\n`.
  - Hypothesis: if `a` is a substring of `b` and `a` starts and ends at word boundaries surrounded by spaces in `b`, then `normalize(a) in normalize(b)` (build `b = x + " " + a + " " + y` from `st.text(alphabet=st.characters(categories=["L","N","Zs","P"]))`).
  - `NORM_VERSION == "NORM_V1"`.
- [ ] Implementation:

```python
import re
import unicodedata

NORM_VERSION = "NORM_V1"

_MAP = str.maketrans(
    {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
        "\u2015": "-", "\u2212": "-",
    }
)
_WS = re.compile(r"\s+")


def _pass(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_MAP)
    return _WS.sub(" ", text).strip().casefold()


def normalize(text: str) -> str:
    """NORM_V1: NFKC, ASCII quotes and dashes, collapsed whitespace, casefold.

    Applied twice because casefold can emit sequences NFKC recomposes; two passes make it idempotent.
    """
    return _pass(_pass(text))
```
  If Hypothesis still finds a non-idempotent input, loop `_pass` until a fixed point (max 4) and add the example with `@example`. Record a `Ruling:`.
- [ ] `uv run pytest packages/quoteproof -q 2>&1 | tail -n 3` -> all pass. Commit `feat(quoteproof): NORM_V1 normalization`.

---

### Task 3: `quoteproof.verify`

**Files:** `packages/quoteproof/src/quoteproof/verify.py`, `packages/quoteproof/src/quoteproof/__init__.py` (re-exports), `packages/quoteproof/tests/test_verify.py`, `packages/quoteproof/tests/fixtures/wal.txt`.

- [ ] Create the text fixture once (trafilatura is available in the workspace venv; quoteproof itself does not depend on it):

```bash
uv run python -c "import pathlib,trafilatura;t=trafilatura.extract(pathlib.Path('tests/fixtures/pages/wal.html').read_text(encoding='utf-8'),include_tables=True,favor_recall=True,deduplicate=False);pathlib.Path('packages/quoteproof/tests/fixtures').mkdir(parents=True,exist_ok=True);pathlib.Path('packages/quoteproof/tests/fixtures/wal.txt').write_text(t,encoding='utf-8',newline='\n');print(len(t))"
```
Expected: a number near 30000 (planner saw 30188).
- [ ] API:

```python
NO_CITATIONS = "NO_CITATIONS"; UNKNOWN_SOURCE = "UNKNOWN_SOURCE"; QUOTE_TOO_SHORT = "QUOTE_TOO_SHORT"
QUOTE_TOO_LONG = "QUOTE_TOO_LONG"; QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"; FOUND = "found"
MIN_WORDS, MIN_CHARS, MAX_WORDS = 6, 30, 80

@dataclass(frozen=True)
class Citation:
    source_id: str
    quote: str

@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    citations: tuple[Citation, ...]

@dataclass(frozen=True)
class CitationResult:
    source_id: str
    status: str            # "found" or a rejection code
    offset: int | None     # index into normalize(page text)
    match: str | None      # "exact_normalized" when found

@dataclass(frozen=True)
class Verdict:
    claim_id: str
    status: str            # "verified" | "rejected"
    citations: tuple[CitationResult, ...]
    reason: str | None
    norm: str = NORM_VERSION
    def to_dict(self) -> dict: ...   # plain JSON-able dict, citations as list of dicts

class Corpus:
    """Read-only map source_id -> raw text with a memo of normalized text."""
    def __init__(self, texts: Mapping[str, str]) -> None: ...
    def __contains__(self, source_id: object) -> bool: ...
    def normalized(self, source_id: str) -> str: ...

def check_quote(source_id: str, quote: str, corpus: Corpus) -> CitationResult: ...
def verify_claim(claim: Claim, texts: Corpus | Mapping[str, str]) -> Verdict: ...
def verify_claims(claims: Iterable[Claim], texts: Corpus | Mapping[str, str]) -> list[Verdict]: ...
```
  Order of checks per citation: unknown source, too short (`len(nq.split()) < 6 or len(nq) < 30` on the normalized quote), too long (`> 80` words), not found (`corpus.normalized(id).find(nq) == -1`). Claim reason = first non-found citation's status. The module imports only stdlib and `.normalize`.
- [ ] Tests (`T = wal.txt`, `S = "sha256:wal"`):
  - verified: quote `"WAL provides more concurrency as readers do not block writers"` -> `verified`, offset equals `normalize(T).find(normalize(quote))`, match `exact_normalized`, norm `NORM_V1`.
  - case and whitespace drift accepted: same quote upper-cased with `"\n  "` between two words -> `verified`.
  - each code: no citations; unknown source; 5-word quote; 25-char 6-word quote (`"a b c d e fghijklmnopqrstuvwx"` style); 81-word quote built by repeating text that does occur (still TOO_LONG, checked before NOT_FOUND); paraphrase -> NOT_FOUND.
  - two citations, one found and one not -> `rejected`, reason `QUOTE_NOT_FOUND`, first citation result still `found`.
  - `Verdict.to_dict()` round-trips through `json.dumps`.
  - **`test_mutated_quotes_rejected` (invariant 3):** take 30 genuine windows from `T` (seeded `random.Random(7)`, 10-30 consecutive words of `normalize(T).split()`, assert each verifies), then for each apply: replace one word with `"zebra"`; delete the middle word; insert `"not"` after the 3rd word; swap two adjacent different words. Assert every mutation that does not occur in `normalize(T)` (check with `in`) is `QUOTE_NOT_FOUND`, and that at least 110 of the 120 mutations were checked (the `in` guard only skips coincidental real substrings).
  - **`test_verifier_is_pure` (invariant 2):** build 40 claims (mix of found, not found, unknown source); run `verify_claims` 100 times on `random.Random(i).sample(claims, len(claims))` with sockets disabled (the suite default) and assert the verdict for each `claim_id` is identical across all runs; also `monkeypatch` `builtins.open` to raise and assert verification still works (no file I/O).
  - Hypothesis `@given` random window offsets/lengths over `T`: windows with 6..80 words always verify.
- [ ] Re-export from `quoteproof/__init__.py`: `normalize, NORM_VERSION, Citation, Claim, CitationResult, Verdict, Corpus, check_quote, verify_claim, verify_claims` and the codes. Fill the usage example in `packages/quoteproof/README.md`.
- [ ] `uv run pytest packages/quoteproof -q 2>&1 | tail -n 3` -> all pass. Commit `feat(quoteproof): deterministic citation verifier`.

---

### Task 4: `quoteproof.lint`

**Files:** `packages/quoteproof/src/quoteproof/lint.py`, `packages/quoteproof/tests/test_lint.py`, `__init__` re-exports.

- [ ] API:

```python
MARKER_RE = re.compile(r"\[c:([A-Za-z0-9][A-Za-z0-9_.-]*)\]")
OPEN_RE = re.compile(r"\[c:", re.IGNORECASE)
MALFORMED_MARKER = "MALFORMED_MARKER"; UNKNOWN_MARKER = "UNKNOWN_MARKER"
REJECTED_MARKER = "REJECTED_MARKER"; NO_MARKERS = "NO_MARKERS"

@dataclass(frozen=True)
class LintError:
    code: str
    marker: str      # the raw text (up to 40 chars from the "[c:" position)
    position: int

@dataclass(frozen=True)
class LintResult:
    ok: bool
    errors: tuple[LintError, ...]
    markers: tuple[str, ...]   # valid marker ids in order of first appearance, no duplicates

def lint_report(draft: str, verified_ids: Collection[str], known_ids: Collection[str]) -> LintResult: ...
def render_footnotes(draft: str, notes: Mapping[str, str]) -> str: ...
```
  Malformed = any `OPEN_RE` match whose position is not the start of a `MARKER_RE` match (covers `[C:x]`, `[c: x]`, `[c:a,b]`, `[c:a` unclosed, `[c:]`). `render_footnotes` replaces each marker with `[^n]` (n by first appearance, repeats reuse n) and appends `"\n\n" + "\n".join(f"[^{n}]: {notes[id]}")`. It raises `ValueError` if a marker id has no note.
- [ ] **`test_linter_rejects_orphan_markers` (invariant 4)**, parametrized: unknown id -> `UNKNOWN_MARKER`; known-but-rejected id -> `REJECTED_MARKER`; each malformed form above -> `MALFORMED_MARKER`; no markers -> `NO_MARKERS`; clean draft with two verified ids, one repeated -> `ok`, `markers == ("a1", "b2")`.
- [ ] `render_footnotes` test: exact expected string for `"X [c:a1]. Y [c:b2]. Z [c:a1]."` -> `"X [^1]. Y [^2]. Z [^1].\n\n[^1]: note a\n[^2]: note b"`.
- [ ] Run quoteproof tests; build the wheel and import it in isolation:

```bash
uv build --package quoteproof 2>&1 | tail -n 2
uv run --isolated --no-project --with dist/quoteproof-0.1.0-py3-none-any.whl python -c "import quoteproof,sys;print(quoteproof.__version__, quoteproof.NORM_VERSION)"
```
Expected: `Successfully built dist/quoteproof-0.1.0-py3-none-any.whl` (and sdist); then `0.1.0 NORM_V1`.
- [ ] Commit `feat(quoteproof): report marker linter and footnote renderer`.

---

### Task 5: Config and models

**Files:** `src/deep_research/config.py`, `src/deep_research/models.py`, `tests/test_models.py`.

- [ ] `Settings` (frozen dataclass) with `ollama_base_url`, `searxng_url`, `model`, `runs_dir: Path`; `Settings.from_env(env: Mapping[str,str] | None = None)` with the defaults from the spec (`http://localhost:11434`, `http://localhost:5300`, `qwen3.8:27b`, `./runs`).
- [ ] `models.py` (Pydantic v2):
  - `Limits` (frozen, `extra="forbid"`): fields and defaults exactly as the spec table; all ints `> 0` (`Field(gt=0)`), `max_wall_s: float`.
  - LLM outputs: `PlanTopic(title: str min 3, rationale: str = "")`, `PlanOut(topics: list[PlanTopic], min_length=1)`, `QueriesOut(queries: list[str], min_length=1)`, `LLMCitation(source: str, quote: str)`, `LLMClaim(text: str min 3, citations: list[LLMCitation])`, `ExtractOut(claims: list[LLMClaim])`, `WriteOut(report_markdown: str min 1)`.
  - `SearchHit(url, canonical_url, title="", snippet="", engine="")`.
  - `FetchResult(url, final_url, canonical_url, status: int, content_type: str, bytes: int, truncated: bool, text: str | None, extractor: str | None, error: str | None)`.
- [ ] Tests: defaults match the spec table (assert each field); `Limits(max_searches=0)` raises; `Limits(foo=1)` raises; `PlanOut.model_json_schema()` contains `"topics"`; `Settings.from_env({"SEARXNG_URL": "http://x:1"}).searxng_url == "http://x:1"`.
- [ ] Commit `feat: settings and pydantic models`.

---

### Task 6: Budget ledger

**Files:** `src/deep_research/budget.py`, `tests/test_budget.py`.

- [ ] API:

```python
class BudgetExceeded(Exception):
    def __init__(self, kind: str, used: int | float, cap: int | float) -> None: ...

class Budget:
    def __init__(self, limits: Limits, *, clock: Callable[[], float] = time.monotonic,
                 sink: Callable[[str, int], None] | None = None,
                 start: dict[str, int] | None = None) -> None: ...
    def charge(self, kind: Literal["search", "fetch"], n: int = 1) -> None   # raises before recording
    def reserve_tokens(self, estimate: int) -> None                          # raises if used+estimate > max_tokens
    def record_tokens(self, prompt: int, completion: int) -> None
    def check_wall(self) -> None
    @property
    def exhausted(self) -> bool          # any BudgetExceeded was raised
    def caps_hit(self) -> list[str]      # sorted kinds that raised
    def snapshot(self) -> dict           # searches, fetches, prompt_tokens, completion_tokens, tokens, wall_s, caps_hit
    @staticmethod
    def estimate_tokens(system: str, user: str, num_predict: int) -> int   # ceil(len(system+user)/3)+num_predict
```
  `charge` and `reserve_tokens` call `check_wall()` first. All mutation under one `threading.Lock`. `sink(kind, amount)` is called for every recorded charge (kinds `search`, `fetch`, `prompt_tokens`, `completion_tokens`). `start` seeds counters on resume.
- [ ] **`test_budget_hard_caps` (invariant 5):** `Limits(max_searches=5, max_fetches=7)`; 16 threads each calling `charge("search")` 10 times inside `try/except BudgetExceeded` with a `Barrier`; afterwards `snapshot()["searches"] == 5`, exactly 5 sink events of kind `search`, `exhausted` is True, `caps_hit() == ["search"]`. Same for fetch with 7.
  - tokens: `max_tokens=1000`; `reserve_tokens(600)` ok, `record_tokens(400, 200)`; `reserve_tokens(401)` raises (`600 + 401 > 1000`); `reserve_tokens(400)` ok.
  - wall: fake clock list `[0, 0, 901]` with `max_wall_s=900` -> second charge raises `BudgetExceeded("wall", ...)`.
  - resume seed: `Budget(limits, start={"searches": 5})` then `charge("search")` with cap 5 raises immediately.
- [ ] Commit `feat: thread-safe budget ledger with hard caps`.

---

### Task 7: Page store

**Files:** `src/deep_research/store.py`, `tests/test_store.py`.

- [ ] `PageStore(path: Path)`: opens SQLite with `check_same_thread=False`, `PRAGMA journal_mode=WAL`, one `threading.Lock` around every statement, creates the three tables from the spec (`texts`, `sources`, `budget_events`). Methods:
  - `put_source(run_id, fetch: FetchResult) -> str` returns `source_id = "sha256:" + sha256(text.encode()).hexdigest()`; inserts `texts` with `INSERT OR IGNORE` and `sources` with `INSERT OR REPLACE`.
  - `get_by_url(run_id, canonical_url) -> dict | None` (source row).
  - `texts_for_run(run_id) -> dict[str, str]`.
  - `source_ids_for_run(run_id) -> set[str]`; `sources_for_run(run_id) -> list[dict]`.
  - `get_text(source_id) -> str | None`.
  - `add_budget_event(run_id, kind, amount)` (seq = next per run, inside the lock); `budget_totals(run_id) -> dict[str, int]` mapping `search->searches`, `fetch->fetches`, `prompt_tokens`, `completion_tokens`.
  - `close()`.
- [ ] Tests: same text from two URLs in one run -> one `texts` row, two `sources` rows; same URL in two runs -> both runs see it; `texts_for_run` isolates runs; budget events from 8 threads x 25 -> 200 rows, seq unique 1..200, totals correct; reopening the file keeps data.
- [ ] Commit `feat: sqlite page store with content-addressed texts`.

---

### Task 8: URL canonicalization and SearXNG search

**Files:** `src/deep_research/urls.py`, `src/deep_research/search.py`, `tests/test_urls.py`, `tests/test_search.py`.

- [ ] `canonical_url(url)`: lower-case scheme and host (keep `www.`), drop default ports (`:80` http, `:443` https), drop fragment, drop query keys starting `utm_` and `fbclid`, `gclid`, `ref`, sort remaining query pairs, strip trailing `/` unless the path is `/`, empty path becomes `/`. `is_denied(url, denylist)` matches host equal to or ending in `"." + entry`. Default denylist: `youtube.com, youtu.be, facebook.com, instagram.com, tiktok.com, x.com, twitter.com, pinterest.com, linkedin.com`.
- [ ] `SearxngSearch(base_url, client: httpx.Client, denylist=DEFAULT_DENYLIST)`, `__call__(query: str, max_results: int) -> list[SearchHit]`: `GET {base}/search` with `params={"q": query, "format": "json", "safesearch": 0}`, timeout 30 s; raises `SearchError` on non-200 or invalid JSON; keeps only `http(s)` URLs, drops denied hosts, dedupes by canonical URL keeping first, returns at most `max_results`.
- [ ] Tests: table of 10 canonicalization cases; `is_denied("https://m.youtube.com/x")` True, `("https://notyoutube.com")` False. Search with `httpx.MockTransport` returning `tests/fixtures/searxng/sqlite_wal.json`: request has `format=json`; `max_results=5` returns 5 hits, first `https://www.sqlite.org/wal.html`; no `linkedin.com` hit appears (the fixture has one); 500 response raises `SearchError`.
- [ ] Commit `feat: searxng search tool with canonical-url dedupe`.

---

### Task 9: Fetch with limits

**Files:** `src/deep_research/fetch.py`, `tests/test_fetch.py`.

- [ ] `extract_text(body: bytes, content_type: str) -> tuple[str | None, str]`: HTML/XHTML -> `trafilatura.extract(html, include_tables=True, favor_recall=True, deduplicate=False)` (decode with the charset from the header, else utf-8 with `errors="replace"`), extractor `"trafilatura"`; PDF -> `pypdf.PdfReader(BytesIO(body))`, pages joined with `"\n\n"`, extractor `"pypdf"`; `text/plain` -> decoded text, extractor `"plain"`. Empty or whitespace-only text returns `None`.
- [ ] `Fetcher(client: httpx.Client, *, max_bytes, timeout_s, user_agent="deep-research/0.1 (+local research agent)", robots: RobotsCache | None, clock=time.monotonic)`, `__call__(url) -> FetchResult`. Rules:
  - robots check first (`RobotsCache.allowed(url)` with `urllib.robotparser`; fetch `/robots.txt` with the same client and a 10 s timeout; 4xx or network error -> allow all; 5xx -> disallow all; cache per scheme+host). Disallowed -> `error="ROBOTS_DISALLOWED"`, no GET of the page.
  - `client.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(timeout_s))`. Content type (before `;`, lower-cased) must be in `{"text/html","application/xhtml+xml","application/pdf","text/plain"}` else `error="CONTENT_TYPE"` without reading the body.
  - Read with `iter_bytes()`; stop and set `truncated=True` once `max_bytes` is reached (keep exactly `max_bytes`); check `clock() - start > timeout_s` after every chunk and stop with `error="TIMEOUT"` (this catches slow-drip bodies that never trip the per-read timeout). `httpx.TimeoutException` -> `error="TIMEOUT"`. Non-2xx -> `error="HTTP_<status>"`.
  - Truncated PDFs are not parsed (`error="PDF_TRUNCATED"`); truncated HTML is extracted.
  - Never raises for network problems; returns a `FetchResult` with `error` set and `text=None`.
- [ ] **`test_fetch_limits` (invariant 6)** with a real `ThreadingHTTPServer` on `127.0.0.1:0` in a daemon thread, marked `@pytest.mark.allow_hosts(["127.0.0.1"])`. Routes: `/robots.txt` (`User-agent: *\nDisallow: /private`), `/page` (fixture `wal.html`), `/endless` (HTML header then writes 64 KiB chunks forever until the client disconnects), `/slow` (HTML, writes 10 bytes every 0.3 s forever), `/bin` (`application/octet-stream`), `/private`, `/pdf` (a 1-page PDF generated in the test with `pypdf.PdfWriter` + `add_blank_page` is textless, so instead serve a tiny hand-written PDF with text, see note), `/404`.
  - `/page` -> text contains `"readers do not block writers"`, extractor trafilatura, not truncated.
  - `/endless` with `max_bytes=200_000` -> `truncated is True`, `bytes == 200_000`, returns within 5 s.
  - `/slow` with `timeout_s=1.0` -> `error == "TIMEOUT"`, returns within 3 s.
  - `/bin` -> `error == "CONTENT_TYPE"`, `text is None`.
  - `/private` -> `error == "ROBOTS_DISALLOWED"` and the server log shows no GET `/private`.
  - `/404` -> `error == "HTTP_404"`.
  - `/pdf` serves `make_pdf("Hello quoteproof world")` with `application/pdf`; assert extractor `pypdf` and text contains `"Hello quoteproof world"`. Put this helper in `tests/fakes.py` (planner prototype: pypdf 6.19.0 extracts exactly `'Hello quoteproof world'` from it):

```python
def make_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)
```
  - pytest-socket note (prototyped): with the global `--disable-socket`, the marker `@pytest.mark.allow_hosts(["127.0.0.1"])` alone is enough for a local `ThreadingHTTPServer` plus `httpx`; a slow-drip body with the deadline check stopped after 1.2 s for `timeout_s=1.0`.
- [ ] Commit `feat: fetch tool with byte cap, deadline, content-type allowlist and robots.txt`.

---

### Task 10: LLM client

**Files:** `src/deep_research/llm.py`, `tests/test_llm.py`.

- [ ] API:

```python
@dataclass(frozen=True)
class LLMRequest:
    purpose: str          # "plan" | "queries" | "extract" | "write"
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
    def __init__(self, base_url: str, model: str, *, client: httpx.Client | None = None,
                 num_ctx: int = 16384, timeout_s: float = 900.0) -> None: ...
    def complete(self, req: LLMRequest) -> LLMResult: ...   # POST /api/chat
    def describe(self) -> dict: ...                        # {"model", "digest"} from GET /api/tags; digest None on error

class ScriptedLLM:
    def __init__(self, handlers: Mapping[str, Callable[[LLMRequest], str | dict]], model: str = "scripted") -> None: ...
    calls: list[LLMRequest]                                # appended under a lock
    def complete(self, req: LLMRequest) -> LLMResult: ...   # dict -> json.dumps; tokens = len(system+user)//4, len(content)//4
    def describe(self) -> dict: ...                        # {"model": "scripted", "digest": None}

class LLMOutputError(Exception): ...

NUM_PREDICT = {"plan": 600, "queries": 200, "extract": 1200, "write": 2000}

def call_structured(llm: LLM, budget: Budget, *, purpose: str, system: str, user: str,
                    model_cls: type[T]) -> T: ...
```
  Ollama payload: `{"model", "stream": False, "think": False, "format": schema, "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": n}, "messages": [{"role": "system", ...}, {"role": "user", ...}]}`; read `message.content`, `prompt_eval_count`, `eval_count` (default 0). Non-200 raises `LLMError`.
  `call_structured`: `budget.reserve_tokens(Budget.estimate_tokens(system, user, n))`, call, `budget.record_tokens(...)`, strip a leading `<think>...</think>` block and Markdown code fences, `model_cls.model_validate_json`. On `ValidationError` or JSON error: one retry with `user + "\n\nYour previous answer was invalid: <first 500 chars of error>. Reply with JSON matching the schema only."` (reserve and record again). Second failure raises `LLMOutputError`.
- [ ] Tests (MockTransport for Ollama): payload has `think: False`, `format` equal to the schema, `temperature` 0; usage parsed; `<think>x</think>{"queries":["a"]}` parses; a first invalid then valid answer succeeds with exactly 2 calls and 2 token records; two invalid answers raise `LLMOutputError`; `BudgetExceeded` from `reserve_tokens` propagates and no HTTP request is made (transport call count 0).
- [ ] Commit `feat: ollama structured-output client and scripted fake`.

---

### Task 11: Prompts and node functions

**Files:** `src/deep_research/prompts.py`, `src/deep_research/deps.py`, `src/deep_research/nodes.py`, `tests/fakes.py`, `tests/test_nodes.py`.

- [ ] `deps.py`:

```python
@dataclass
class Deps:
    llm: LLM
    search: Callable[[str, int], list[SearchHit]]
    fetch: Callable[[str], FetchResult]
    store: PageStore
    budget: Budget
    limits: Limits
    run_id: str
```
- [ ] `prompts.py` (pure functions returning `(system, user)`):
  - `plan_prompt(question, max_topics)`: "Split the research question into 2 to {max_topics} distinct sub-topics that together answer it. Each has a short title and a one-sentence rationale."
  - `queries_prompt(question, topic_title, n)`: "Write {n} web search queries (plain keywords, no operators) for this sub-topic."
  - `extract_prompt(question, topic_title, sources: list[tuple[label, url, text]], max_claims=6)`: system text from the planner prototype: "You extract factual claims from sources. Each claim must cite one or more sources by their label (e.g. S1) with a quote copied EXACTLY, character for character, from that source (6 to 80 words). Never paraphrase quotes. Return at most {max_claims} claims." User: question, topic, then each source as `[S1] <url>\n<<<\n<text>\n>>>`.
  - `write_prompt(question, claims: list[dict], errors: list[str] | None)`: "Write a concise Markdown report (no title, no footnote section) answering the question using ONLY the claims listed. After each sentence that uses a claim, add its marker exactly as shown, e.g. [c:t1-r1-c2]. One id per marker. Never invent ids." Claims listed as `[c:<id>] <text>`. If `errors`, append "Your previous draft failed these checks: ..." .
- [ ] `nodes.py` (plain functions over `Deps` and dicts; the graph wraps them in Task 13):
  - `plan_topics(deps, question) -> list[dict]`: `call_structured(... PlanOut)`; keep first `limits.max_topics`; ids `t1..tn`; returns `[{"topic_id","title","rationale"}]`.
  - `write_queries(deps, question, topic) -> list[str]`: `QueriesOut`, dedupe case-insensitively, keep `limits.queries_per_topic`.
  - `gather_sources(deps, topic, round, queries) -> tuple[list[dict], list[str]]`: returns `(sources, budget_hits)`. For each query: `budget.charge("search")` then `deps.search(q, results_per_query * 2)`; take up to `results_per_query` hits not seen in this call. For each candidate URL until `sources_per_extract` texts are collected: if `store.get_by_url(run_id, canonical)` exists reuse it (no charge); else `budget.charge("fetch")`, `deps.fetch(url)`, and if `text` store it. `BudgetExceeded` stops gathering and appends its kind to `budget_hits`; `SearchError` skips that query. Each source dict: `{"source_id","url","canonical_url","topic_id","round"}`.
  - `extract_claims(deps, question, topic, round, sources) -> list[dict]`: labels `S1..Sn` in order; texts from `store.get_text`, truncated to `limits.source_chars`; `ExtractOut`; claim ids `f"{topic_id}-r{round}-c{i}"` from 1; each citation `{"source_id": label_map.get(c.source.strip(), f"label:{c.source.strip()}"), "quote": c.quote, "label": c.source}`; claim dict `{"claim_id","topic_id","round","text","citations"}`. No sources -> `[]` without an LLM call.
  - `verify_new_claims(store, run_id, claims, verdicts) -> list[dict]`: claims whose id has no verdict yet; `Corpus(store.texts_for_run(run_id))`; convert to `quoteproof.Claim`; return `Verdict.to_dict()` list (adds `"topic_id"`).
  - `coverage_decision(topics, verdicts, round, limits, exhausted) -> tuple[str, list[str]]`: verified count per topic; `open = [ids with count < min_verified_claims]`; returns `("writer", [])` if not open, or `round >= limits.rounds`, or `exhausted`; else `("supervisor", open)`.
- [ ] `tests/fakes.py`: `FakeSearch(results: dict[str, list[str]] | Callable)` returning `SearchHit`s for URLs like `https://example.test/<topic>/<n>`, counting calls under a lock; `FakeFetch(pages: dict[str, str] | Callable[[str], str])` returning `FetchResult` with `text`, counting calls, optional `fail_on_call: int` raising `RuntimeError("simulated crash")`; `scripted_llm(...)` building a `ScriptedLLM` whose `extract` handler copies a real sentence from the given source text for "good" claims and writes a paraphrase for "bad" claims (decided by topic title, e.g. titles containing "bad").
- [ ] Tests: plan ids and cap; queries dedupe and cap; `gather_sources` reuses a stored URL without a fetch charge; budget hit is reported and stops; extract maps labels and maps an unknown `S9` to `label:S9`; verify only new claims; `coverage_decision` table (covered, open with rounds left, open at last round, exhausted).
- [ ] Commit `feat: prompts and research node functions`.

---

### Task 12: Researcher subgraph

**Files:** `src/deep_research/researcher.py`, `tests/test_researcher.py`.

- [ ] `build_researcher(deps) -> CompiledStateGraph` with `input_schema=ResearcherInput` (`run_id`, `question`, `topic: dict`, `round: int`) and `output_schema=ResearcherOutput` (`claims`, `sources`, `budget_hit`, `errors`, all `Annotated[list, operator.add]`). Nodes: `queries` -> `gather` -> `extract` -> END. Internal state `ResearcherState(TypedDict, total=False)` adds `queries: list[str]`. `BudgetExceeded` in `queries` or `extract` is caught and recorded in `budget_hit`; `LLMOutputError` is recorded in `errors` as `"<topic_id>:<purpose>:LLMOutputError"` and yields no claims.
- [ ] Tests: invoking the subgraph alone with fakes returns claims with the expected ids and sources; with `max_fetches=1` it returns `budget_hit == ["fetch"]` and still extracts from the one fetched page.
- [ ] Commit `feat: researcher subgraph`.

---

### Task 13: Supervisor, coverage gate and graph assembly

**Files:** `src/deep_research/graph.py`, `tests/test_graph.py`.

- [ ] `ResearchState(TypedDict, total=False)`: `run_id`, `question`, `topics: list[dict]`, `round: int`, `open_topics: list[str]`, `claims`, `verdicts`, `sources`, `budget_hit`, `errors` (all `Annotated[list, operator.add]`), `report_md: str`, `report_draft: str`, `writer: str`, `status: str`.
- [ ] `build_graph(deps, *, checkpointer=None) -> CompiledStateGraph`. Nodes and edges:
  - `planner`: `plan_topics`; sets `topics`, `round=0`, `open_topics=[all ids]`; `LLMOutputError` -> `status="failed"` and route to END (conditional edge).
  - `supervisor`: returns `{"round": state["round"] + 1}`. Conditional edges via `dispatch(state) -> [Send("researcher", {"run_id","question","topic","round": state["round"]}) for each open topic]`. (Note: `round` in the Send is the already-incremented value since the supervisor update has been applied when the edge function runs; the test asserts claim ids `-r1-` in round 1.)
  - `researcher`: the compiled subgraph from Task 12.
  - `verify`: `verify_new_claims`.
  - `gate`: node that computes `coverage_decision` with `exhausted = deps.budget.exhausted or bool(state["budget_hit"])` and writes `open_topics`; conditional edge to `supervisor` or `writer`.
  - `writer`: Task 14 (until then a stub that sets `status` and `report_md=""`); then END.
  - Concurrency cap: the graph is invoked with `config["max_concurrency"] = limits.researchers` (runner sets it; tests pass it explicitly).
- [ ] Tests (all with fakes, `max_concurrency` set):
  - **`test_fanout_merge` (invariant 7):** 8 topics, `rounds=1`, each fake researcher sleeps a seeded random 0-50 ms; all 8 topics' claims present; claim ids unique; repeat 5 times with different seeds.
  - **`test_round_and_fanout_caps` (invariant 9):** fake extract always returns only rejected (paraphrased) claims so the gate always sees gaps; `rounds=3`, `researchers=2`, 5 topics; assert `final["round"] == 3`, ids contain `-r1-`, `-r2-`, `-r3-` and no `-r4-`; a concurrency counter inside `FakeFetch` (increment on enter, sleep 20 ms, decrement) never exceeds 2.
  - **`test_graph_respects_search_cap`:** `max_searches=3`, 4 topics x 2 queries; `FakeSearch.calls == 3`; final `status` reflects exhaustion once the writer exists (Task 14); `budget_hit` contains `"search"`.
  - Covered topics are not re-dispatched in round 2.
- [ ] Commit `feat: supervisor fan-out with coverage gate and round caps`.

---

### Task 14: Writer, fallback and linter integration

**Files:** `src/deep_research/writer.py`, `tests/test_writer.py`, wire into `graph.py`.

- [ ] API:

```python
def select_writer_input(claims: list[dict], verdicts: list[dict]) -> list[dict]
    # claims whose verdict status == "verified", in original order
def fallback_report(question: str, topics: list[dict], claims: list[dict]) -> str
    # "## <topic title>\n\n- <claim text> [c:<id>]" per topic with verified claims
def footnote_notes(claims: list[dict], sources: list[dict]) -> dict[str, str]
    # id -> '"<quote>" - <url>' for each citation, joined by "; "
def write_report(deps, question, topics, claims, verdicts, sources) -> dict
    # returns {"report_md", "report_draft", "writer", "report_markers"}
```
  `write_report`: verified = `select_writer_input`; none -> `report_draft = ""`, `report_md = "No verified claims."`, `writer = "none"`, no LLM call. Else LLM draft (`WriteOut`) -> `lint_report(draft, verified_ids, all_claim_ids)`; failure -> retry once with error codes and markers -> failure -> `fallback_report` (lint it; assert ok). Render with `render_footnotes`. Prepend the header: `# <question>\n\n_Status: <status>. <v> of <p> proposed claims verified; <r> rejected by the citation verifier._\n\n` and, when caps were hit, `_Budget caps hit: search, fetch._\n\n`; append `## Under-covered topics` listing topics below `min_verified_claims`. `LLMOutputError` or `BudgetExceeded` from the writer goes straight to the fallback.
  - Graph `writer` node sets `status = "budget_exhausted"` if exhausted, else `"done"`, then calls `write_report`.
- [ ] **`test_writer_input_only_verified` (invariant 1):** Hypothesis generates lists of claim dicts with random ids and a random subset marked verified (others with random rejection codes; some claims with no verdict at all); assert `select_writer_input` returns exactly the verified ones in order. Plus: the `write` request seen by `ScriptedLLM` contains every verified id and no rejected id (check `req.user`).
  - Fallback path: the scripted writer returns a draft with `[c:nope]` twice -> `writer == "fallback"`, report lints clean, 2 write calls.
  - Retry path: first draft bad, second good -> `writer == "llm_retry"`.
  - **`test_report_markers_all_verified` (in `tests/test_graph.py`, invariant 4 end to end):** full graph with mixed good/bad topics; every id in `report_markers` has a `verified` verdict; `report_md` contains no `[c:`.
- [ ] Commit `feat: verified-only writer with lint retry and deterministic fallback`.

---

### Task 15: Runner, run.json and resume

**Files:** `src/deep_research/runner.py`, `tests/test_runner.py`, `tests/test_resume.py`.

- [ ] API:

```python
@dataclass
class RunSummary:
    run_id: str; status: str; report_path: Path; run_json_path: Path
    proposed: int; verified: int; rejected: int; writer: str; budget: dict

def new_run_id(now: datetime | None = None) -> str   # "YYYYMMDD-HHMMSS-<6 hex>"
def start_run(question: str, limits: Limits, settings: Settings, *, llm: LLM | None = None,
              search=None, fetch=None, run_id: str | None = None) -> RunSummary
def resume_run(run_id: str, settings: Settings, *, llm=None, search=None, fetch=None) -> RunSummary
```
  - Paths: `runs_dir/store.sqlite`, `runs_dir/checkpoints.sqlite`, `runs_dir/<run_id>/{limits.json,run.json,report.md}`. `limits.json` and `{"question": ...}` (in `meta.json`) are written before the graph runs.
  - Defaults when not injected: `OllamaLLM(settings.ollama_base_url, settings.model)`, `SearxngSearch(settings.searxng_url, httpx.Client())`, `Fetcher(httpx.Client(), max_bytes, timeout, robots=RobotsCache(...))`.
  - Budget: `sink = lambda kind, n: store.add_budget_event(run_id, kind, n)`; on resume `start = store.budget_totals(run_id)`.
  - Checkpointer: `SqliteSaver(sqlite3.connect(path, check_same_thread=False))`; `config = {"configurable": {"thread_id": run_id}, "max_concurrency": limits.researchers, "recursion_limit": 100}`. Start: `graph.invoke({"run_id", "question"}, config)`. Resume: `graph.invoke(None, config)`; if the checkpoint has no pending next nodes, just rebuild `run.json` from the saved state.
  - An exception escaping `invoke` (crash) leaves the checkpoint and `meta.json`, writes `run.json` with `status = "failed"` and `error`, then re-raises.
  - `run.json` keys: `run_id, question, status, limits, model {model, digest}, norm, topics, claims, verdicts, sources, report_markers, report_draft, writer, budget (snapshot + segments list of {started_at, wall_s}), caps_hit, errors, started_at, finished_at, versions {deep_research, quoteproof, langgraph}`. JSON is written with `indent=2, sort_keys=True`.
- [ ] Tests: a fake end-to-end run writes `run.json` with those keys and `report.md` beginning with `# <question>`; `proposed == verified + rejected`.
  - **`test_resume_after_crash` (invariant 8):** reference run with `FakeFetch` -> record `fetch_calls_ref` and the store's fetch total. Crash run in a fresh `tmp_path`: `FakeFetch(fail_on_call=k)` where `k` is in the middle of round 1 (e.g. 3 of 6), `start_run` raises `RuntimeError`; then `resume_run` with a non-failing `FakeFetch` sharing the same page map. Assert: the resumed run's final claims set equals the reference run's set; store `budget_totals(run_id)["fetches"]` equals the reference total; total successful fetch calls across both processes equals `fetch_calls_ref` (no URL fetched twice: assert each canonical URL was fetched successfully exactly once, using the fakes' call logs). Planner calls: exactly 1 across crash + resume.
- [ ] Commit `feat: run orchestration with sqlite checkpoints and resume`.

---

### Task 16: CLI

**Files:** `src/deep_research/cli.py`, `tests/test_cli.py`.

- [ ] `main(argv: list[str] | None = None, *, deps_factory=None) -> int` with argparse subcommands from the spec (`run`, `resume`, `verify`, `show`, `eval`, `bench`, `serve`; `eval`/`bench`/`serve` are wired in Tasks 17-19 and print "not implemented" with exit 2 until then). `deps_factory` lets tests inject the scripted LLM and fakes. Every subcommand accepts `--runs-dir` (default `Settings.from_env().runs_dir`). Exit codes: 0 ok, 1 run failed or verify mismatch, 2 usage error.
  - `dr run "<q>" [--max-searches N --max-fetches N --max-tokens N --max-wall S --researchers N --rounds N --topics N --runs-dir P --run-id ID]` prints `run_id`, status, `verified v/p`, report path.
  - `dr resume <run_id>`.
  - `dr show <run_id> [--rejected]`: fixed-width table `claim_id | status | reason | claim text (60 chars)`; `--rejected` shows only rejected, plus the first rejected quote (80 chars).
  - `dr verify <run_id>`: re-verify every claim against `store.texts_for_run`; compare to `run.json` verdict statuses; count `report_markers` whose re-verification is not `verified` (`unverifiable`). Prints `claims: <n>  re-verified same: <n>  report markers: <k>  unverifiable: <u>`; exit 0 iff all same and `u == 0`.
- [ ] Tests: `run` then `show --rejected` then `verify` through `main()` with fakes (capsys); `verify` exits 1 after the test tampers with a stored text (`UPDATE texts SET text = 'x'`); bad args exit 2.
- [ ] Commit `feat: dr cli (run, resume, show, verify)`.

---

### Task 17: Offline verifier benchmark (`dr bench`)

**Files:** `src/deep_research/bench.py`, `tests/test_bench.py`, `bench/results/latest.json`, `bench/README.md`.

- [ ] Implement as ADR-0010 says: `html_sentences(html) -> list[str]` (stdlib `HTMLParser`, skip `script`/`style`, newline on block tags `p div br li h1-h6 tr td th pre dd dt`, sentence split `(?<=[.!?])\s+`, keep 8-40 words); genuine quotes = `random.Random(seed).sample` of up to `per_page` sentences per page (pages in sorted order); page text via `fetch.extract_text(bytes, "text/html")`; verify with `quoteproof`. Mutations on accepted quotes: `swap_word` (replace a random word of length >= 4 with the first word from `["zebra","never","seven","purple","always"]` that differs), `delete_word` (remove a random non-first, non-last word), `change_number` (first digit run `n` -> `n+1`; skipped if no digit), `insert_not` (insert `not` after a random word), `transpose` (swap two adjacent different words; skipped if none). Each mutation uses its own `Random(seed + i)`.
  - Output dict: `{"bench": "quoteproof-v1", "seed", "per_page", "norm": "NORM_V1", "corpus": [{"file", "sha256", "sentences", "sampled"}], "genuine": {"total","accepted","rate","rejected_by_reason"}, "mutated": {"by_kind": {kind: {"total","rejected","skipped","rate"}}, "total","rejected","rate"}, "versions": {...}}`. Rates rounded to 4 decimals. No timestamps (so `--check` can compare).
  - CLI: `dr bench [--pages tests/fixtures/pages] [--seed 42] [--per-page 40] [--out bench/results/latest.json] [--check FILE]`. `--check` recomputes and exits 1 if the result differs from FILE (prints the first differing key).
- [ ] Tests: deterministic (two runs equal); every mutation kind changes the string or returns `None`; a genuine quote from `wal.html` is accepted; the structure keys exist; sanity bounds `genuine.rate > 0.9` and `mutated.rate > 0.95` (sanity only, the README quotes the file).
- [ ] Generate and commit the result:

```bash
uv run python -m deep_research bench --out bench/results/latest.json
uv run python -m deep_research bench --check bench/results/latest.json && echo CHECK_OK
```
Expected: a summary line like `genuine accepted A/G (rate) | mutated rejected R/M (rate)` with the real numbers, then `CHECK_OK`. Copy the summary line into the ledger.
- [ ] `bench/README.md`: what is measured, how, how to re-run, and the caveat (genuine = sentences from an independent HTML-to-text pass, so rejections show extraction drift).
- [ ] Commit `feat: offline verifier benchmark with committed result`.

---

### Task 18: Eval harness (`dr eval`)

**Files:** `src/deep_research/evals.py`, `evals/questions.yaml`, `tests/test_evals.py`.

- [ ] `evals/questions.yaml`: `version: 1`, `questions:` list of `{id, question, expected_domains}`:
  1. `sqlite-wal` - How does SQLite WAL mode affect reader and writer concurrency? - `[sqlite.org]`
  2. `http-429` - What does HTTP status 429 mean and how does the Retry-After header work? - `[developer.mozilla.org, rfc-editor.org, httpwg.org]`
  3. `python-gil` - How does the Python GIL affect CPU-bound multithreaded programs? - `[docs.python.org, peps.python.org]`
  4. `pg-isolation` - Which transaction isolation levels does PostgreSQL support and which anomalies does each prevent? - `[postgresql.org]`
  5. `tcp-slow-start` - How does TCP slow start work? - `[rfc-editor.org, datatracker.ietf.org]`
  6. `utf8-vs-utf16` - How do UTF-8 and UTF-16 encode Unicode code points differently? - `[unicode.org, rfc-editor.org]`
  7. `git-objects` - How does Git store blobs, trees and commits? - `[git-scm.com]`
  8. `robots-rfc9309` - What does RFC 9309 require of crawlers that read robots.txt? - `[rfc-editor.org, datatracker.ietf.org, developers.google.com]`
  9. `dns-ttl` - How do DNS resolvers use TTL values for caching? - `[rfc-editor.org, datatracker.ietf.org, cloudflare.com]`
  10. `rust-ownership` - What are Rust's ownership and borrowing rules? - `[doc.rust-lang.org]`
  11. `http2-multiplexing` - How does HTTP/2 multiplexing differ from HTTP/1.1 pipelining? - `[rfc-editor.org, developer.mozilla.org, httpwg.org]`
  12. `linux-oom` - What does the Linux OOM killer do and how does oom_score_adj change its choice? - `[kernel.org, man7.org]`
- [ ] API: `load_suite(path) -> list[dict]` (validates unique ids); `score_run(run_json: dict, store: PageStore) -> dict` with `proposed, verified, rejected, rejected_by_reason, rejection_rate, topics, topics_covered, coverage_rate, report_markers, unverifiable_shipped` (re-verified from the store, same logic as `dr verify`), `writer, status, wall_s, tokens, expected_domain_share` (share of verified claims whose source URL host ends with an expected domain); `aggregate(scores) -> dict` (sums, overall rejection rate, median and max wall and tokens, fallback count, total `unverifiable_shipped`); `run_eval(suite, *, limit, limits, settings, runner=start_run, out_dir) -> Path` writes `evals/results/<YYYY-MM-DD>.json` `{"suite", "limit", "limits", "model", "questions": [...], "aggregate": {...}}` and a sibling `.md` table. A question whose run raises is recorded with `status: "error"` and the error text and counted in the aggregate as `errors`.
  - CLI: `dr eval [--suite evals/questions.yaml] [--limit N] [--only id,id] [--out evals/results] [cap flags]`.
- [ ] Tests: `run_eval` with a fake runner (scripted LLM + fakes through `start_run` with injected deps) over a 2-question temp suite writes JSON whose aggregate equals the sum of parts and `unverifiable_shipped == 0`; a raising runner is recorded as `error`; duplicate ids rejected.
- [ ] Commit `feat: eval harness and 12-question suite`.

---

### Task 19: Read-only web view (`dr serve`)

**Files:** `src/deep_research/serve.py`, `tests/test_serve.py`.

- [ ] `make_server(runs_dir, host="127.0.0.1", port=5301) -> ThreadingHTTPServer` (stdlib only; `BaseHTTPRequestHandler`, GET only, 405 otherwise). Routes:
  - `/` runs list (run_id, question, status, verified/proposed), newest first.
  - `/runs/<id>` report (Markdown shown as escaped `<pre>`-free HTML: headings, paragraphs, bullet lists and footnotes via a 40-line converter; no third-party Markdown lib), with a tab link to rejected.
  - `/runs/<id>/rejected` table: claim id, reason code, claim text, quote, source URL.
  - `/runs/<id>/source?claim=<claim_id>&i=<n>` stored page text with the cited quote wrapped in `<mark>` (find in raw text with a case-insensitive regex of the quote's words joined by `\s+`; if not found show the normalized text and highlight by offset).
  - Every dynamic string goes through `html.escape`. `<id>` must match `^[A-Za-z0-9_-]+$` and exist under `runs_dir`, else 404. Inline CSS only, light and dark via `prefers-color-scheme`, readable at 375 px wide.
  - CLI `dr serve [--host] [--port] [--runs-dir]` prints `serving http://127.0.0.1:5301` and blocks.
- [ ] Tests (`allow_hosts(["127.0.0.1"])`, port 0): build a run with fakes, start the server in a thread, GET each route with `httpx`: 200s; the rejected page contains a known rejected claim id and its reason code; the source page contains `<mark>`; `/runs/..%2F..%2Fetc` and `/runs/nope` -> 404; a claim text containing `<script>` is escaped.
- [ ] Commit `feat: read-only report viewer with quote highlighting`.

---

### Task 20: Docker image and compose

**Files:** `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `searxng/settings.yml`.

- [ ] `searxng/settings.yml`:

```yaml
use_default_settings: true
server:
  limiter: false
  image_proxy: false
search:
  safe_search: 0
  formats:
    - html
    - json
```
  Secret via env `SEARXNG_SECRET` (compose sets `${SEARXNG_SECRET:-deep-research-local-dev-only}`). If the container refuses to start without `server.secret_key` in the file, add `secret_key: "deep-research-local-dev-only"` with a comment that it is not a secret and write a `Ruling:`.
- [ ] `Dockerfile`: `FROM python:3.12-slim-bookworm`; `COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/`; `ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH DR_RUNS_DIR=/data/runs`; `WORKDIR /app`; copy `pyproject.toml uv.lock README.md packages/quoteproof/pyproject.toml packages/quoteproof/README.md` first and `uv sync --frozen --no-install-workspace`; then `COPY . .` and `uv sync --frozen`; non-root user `app`; `ENTRYPOINT ["dr"]`, `CMD ["--help"]`. `.dockerignore`: `.venv`, `runs`, `dist`, `.git`, caches.
- [ ] `docker-compose.yml`: `name: deep-research`; service `searxng` (`image: searxng/searxng:2026.10.2-19ffbcd30`, `container_name: deep-research-searxng`, `ports: ["127.0.0.1:5300:8080"]`, `volumes: ["./searxng:/etc/searxng"]`, env `SEARXNG_SECRET`, healthcheck optional); service `app` (`build: .`, `image: deep-research-app`, env `OLLAMA_BASE_URL=http://host.docker.internal:11434`, `SEARXNG_URL=http://searxng:8080`, `DR_MODEL=${DR_MODEL:-qwen3.8:27b}`, `extra_hosts: ["host.docker.internal:host-gateway"]`, `volumes: ["dr-runs:/data/runs"]`, `ports: ["127.0.0.1:5301:5301"]`, `depends_on: [searxng]`); `volumes: {dr-runs: {}}`.
- [ ] Before starting compose, make sure port 5300 is free: `docker ps --format '{{.Names}} {{.Ports}}' | grep 5300`. If the planner's prototype container `deep-research-proto-searxng` still holds it, `docker rm -f deep-research-proto-searxng` (it is a disposable prototype owned by this project).
- [ ] Verify:

```bash
docker compose build app 2>&1 | tail -n 3
docker compose run --rm --entrypoint "" app pytest -q 2>&1 | tail -n 3
docker compose up -d searxng && sleep 8
curl -s "http://127.0.0.1:5300/search?q=sqlite+wal&format=json" | python -c "import sys,json;print(len(json.load(sys.stdin)['results']))"
docker compose run --rm app --help | head -n 5
```
Expected: image built; the same pass count as the host suite (the fetch/serve tests bind 127.0.0.1 inside the container, which is fine); a result count > 0; the `dr` usage text. If the search count is 0, note which engines are unresponsive (`unresponsive_engines`) in the ledger; do not block. Leave SearXNG up for Task 22; otherwise `docker compose down`.
- [ ] Commit `build: docker image and compose with searxng on 5300`.

---

### Task 21: CI workflow and wheels

**Files:** `.github/workflows/ci.yml`.

- [ ] Jobs on `push` and `pull_request`:
  - `test` (ubuntu-latest): `actions/checkout@v4`; `astral-sh/setup-uv@v10.2.0` with `version: "0.12.21"` and `python-version: "3.12"`; `uv sync --frozen`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run pytest`; `uv run python -m deep_research bench --check bench/results/latest.json`; `uv build --package quoteproof`; `uv build --package deep-research`; `uv run --isolated --no-project --with dist/quoteproof-0.1.0-py3-none-any.whl python -c "import quoteproof"`; upload `dist/*` as an artifact (`actions/upload-artifact@v4`).
  - `docker` (ubuntu-latest): `docker build -t deep-research-app .` and `docker run --rm --entrypoint "" deep-research-app pytest -q`.
  - A comment says live and eval tiers stay local (no Ollama or GPU in CI).
- [ ] Local equivalent (CI cannot run here; nothing is pushed):

```bash
uv run python -c "import yaml;d=yaml.safe_load(open('.github/workflows/ci.yml'));print(sorted(d['jobs']))"
uv build --package quoteproof 2>&1 | tail -n 1 && uv build --package deep-research 2>&1 | tail -n 1
```
Expected: `['docker', 'test']` and two `Successfully built` lines. Write in the ledger that CI was validated locally only.
- [ ] Commit `ci: lint, tests, bench check, wheels and docker`.

---

### Task 22: Live tier, example run and live eval

**Files:** `tests/test_live.py`, `examples/sqlite-wal/{report.md,rejected.txt,run.json,verify.txt}`, `evals/results/<date>.json`, `evals/results/<date>.md`.

- [ ] `tests/test_live.py`: `pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("DR_LIVE") != "1", reason="set DR_LIVE=1")]`, enable sockets for this module (`pytest.mark.enable_socket`). One test: `start_run("How does SQLite WAL mode affect reader and writer concurrency?", Limits(max_topics=2, rounds=1, max_searches=4, max_fetches=6), Settings.from_env())`; asserts structure only: `run.json` exists, status in `{done, budget_exhausted}`, `dr verify` exits 0. Confirm `uv run pytest` still skips it (`N passed, 1 skipped`).
- [ ] Preconditions: `curl -s localhost:11434/api/tags | grep -c qwen3.8:27b` >= 1; SearXNG up from Task 20 (`docker compose up -d searxng` if not).
- [ ] Example run (slow: each LLM call took about 2 minutes under shared load; run in the background and poll the run directory instead of blocking):

```bash
uv run python -m deep_research run "How does SQLite WAL mode affect reader and writer concurrency?" --topics 3 --rounds 1 --max-searches 6 --max-fetches 9 --runs-dir runs 2>&1 | tail -n 5
uv run python -m deep_research show <run_id> --rejected --runs-dir runs > examples/sqlite-wal/rejected.txt
uv run python -m deep_research verify <run_id> --runs-dir runs | tee examples/sqlite-wal/verify.txt
cp runs/<run_id>/report.md runs/<run_id>/run.json examples/sqlite-wal/
```
  Expected: status `done` or `budget_exhausted`; `verify` prints `unverifiable: 0` and exits 0. If zero claims were rejected, keep it anyway (that is a real result) and say so in the README. If the run fails, record the error and retry once with `--topics 2`; if it fails again, write a `Ruling:` and continue with the README using bench numbers only.
- [ ] Live eval (background, budgeted): `uv run python -m deep_research eval --limit 3 --topics 3 --rounds 1 --max-searches 6 --max-fetches 9 --runs-dir runs`. Commit the JSON and MD it writes. Do not edit them by hand.
- [ ] Run `DR_LIVE=1 uv run pytest -m live 2>&1 | tail -n 3` once and record the result.
- [ ] `docker compose down` and confirm `docker ps --format '{{.Names}}' | grep deep-research-` prints nothing.
- [ ] Commit `docs: live example run and live eval results` (only files under `examples/` and `evals/results/` plus `tests/test_live.py`).

---

### Task 23: README, DEVDOCS draft and handoff

**Files:** `README.md`, `docs/DEVDOCS.md`, `docs/handoff.md`, `LICENSE` (MIT, 2026, sathwikbairaboina2).

- [ ] README order: (1) first line = headline built only from `bench/results/latest.json` and `evals/results/<date>.json` (for example "Rejected X% of N model-proposed claims; 0 unverifiable citations shipped in K live reports; verifier accepts A of G genuine quotes and rejects R of M mutated ones" with the real values, and N/K stated); (2) the real rejected-claims excerpt from `examples/sqlite-wal/rejected.txt` (5-8 lines) and 3-5 lines of the real report; (3) what it is and what it does not prove (a real quote can still be misused; ADR-0002); (4) quickstart (compose up searxng, `uv sync`, `uv run python -m deep_research run ...`, `uv run python -m deep_research serve`); (5) `quoteproof` usage snippet and how to build the wheel; (6) mermaid architecture diagram; (7) invariants table with test names; (8) limits; (9) ADR links; (10) hardware note for the live numbers (from the ledger/eval JSON model field; do not guess the GPU).
- [ ] Number check: for every number in README, `grep -F` it in `bench/results/latest.json`, `evals/results/*.json` or `examples/sqlite-wal/*`; paste the command and its output in the ledger.
- [ ] `docs/DEVDOCS.md`: draft in the 7-section order of the session brief (the Opus lead rewrites it at the end).
- [ ] `docs/handoff.md`: `2026-10-04, Claude (sonnet-builder), branch main`: what changed, what is left, how to verify (the gate commands below).
- [ ] Commit `docs: readme, devdocs draft, handoff`.

---

### Task 24: Final gates

Run all of these from the repo root and paste the tail of each output into the ledger as `FINAL:` lines.

```bash
uv sync --frozen 2>&1 | tail -n 1
uv run ruff check . && uv run ruff format --check .           # G1: All checks passed / already formatted
uv run pytest 2>&1 | tail -n 2                                  # G2: N passed, 1 skipped (live), 0 failed
uv run python -m deep_research bench --check bench/results/latest.json               # G3: exit 0
uv build --package quoteproof 2>&1 | tail -n 1                  # G4: Successfully built ...whl
uv build --package deep-research 2>&1 | tail -n 1
docker compose build app 2>&1 | tail -n 1                       # G5: image builds
docker compose run --rm --entrypoint "" app pytest -q 2>&1 | tail -n 2
docker compose down; docker ps --format '{{.Names}}' | grep deep-research- || echo NO_CONTAINERS
git ls-files | grep -iE '(^|/)\.env($|\.)|secret|\.pem$|\.key$' || echo NO_SECRETS   # G6
git status --short                                              # clean except runs/ (ignored)
```

- [ ] Every invariant test from the spec table exists under that exact name: `uv run pytest --collect-only -q | grep -E "test_writer_input_only_verified|test_verifier_is_pure|test_mutated_quotes_rejected|test_linter_rejects_orphan_markers|test_report_markers_all_verified|test_budget_hard_caps|test_graph_respects_search_cap|test_fetch_limits|test_fanout_merge|test_resume_after_crash|test_round_and_fanout_caps"` lists 11 lines.
- [ ] Ledger final line: `FINAL: <pass count>, bench check ok, wheels ok, docker ok, live <status>`.
- [ ] Commit `chore: final gates` only if files changed (ledger lives under `.superpowers/`, which is committed).
- [ ] Report DONE with: commits (`git log --oneline | head -n 30`), the measured headline numbers and the file each came from, anything skipped with its `Ruling:`.
