# Handoff

## 2026-10-04, Claude (sonnet-builder), branch main

**What changed.** Built v0.1 from the plan: the `quoteproof` package (normalize, verify, lint), the agent (search, fetch, store, llm, budget, nodes, researcher, graph, writer, runner), the CLI (`run`, `resume`, `show`, `verify`, `eval`, `bench`, `serve`), the offline benchmark with its committed result, the eval harness and 12-question suite, Docker image and compose, CI workflow, a live example run and a 3-question live eval, README, DEVDOCS draft. Local commits only; nothing pushed.

**What is left.** The Opus lead reviews against the spec, reruns the gates, rewrites `docs/DEVDOCS.md` and updates the board. Known gaps: see README "Limits". The live eval is small (3 questions) and ran on a CPU-bound shared machine.

**How to verify** (Git Bash, repo root):

```bash
uv sync --frozen
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run python -m deep_research bench --check bench/results/latest.json
uv build --package quoteproof && uv build --package deep-research
uv run --isolated --no-project --with dist/quoteproof-0.1.0-py3-none-any.whl python -c "import quoteproof"
docker compose build app && docker compose run --rm --entrypoint "" app pytest
docker compose down
git ls-files | grep -iE '(^|/)\.env($|\.)|secret|\.pem$|\.key$' || echo NO_SECRETS
```

Ledger: `.superpowers/sdd/2026-10-04-deep-research/progress.md` (includes the Ruling lines).
