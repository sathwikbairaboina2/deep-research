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

## 2026-10-04, Claude (Opus lead), branch main

**What changed.** I reviewed the build after the 06:08 machine crash and found no correctness bugs in the verifier, writer filter, re-verify or the LLM transport-error fix. I re-checked the README headline against `evals/results/2026-10-04.json` (5 of 42 rejected, 0 unverifiable shipped) and `bench/results/latest.json` (200/200, 812/812), and it matches. I reran every gate myself. Results: ruff ok (49 files formatted); pytest 136 passed, 1 skipped; bench check ok; both wheels built and quoteproof imports in isolation; docker image built with in-image pytest 136 passed, 1 skipped; no containers left; no secrets tracked; all 11 invariant tests present. I rewrote `docs/DEVDOCS.md` as the final developer guide and updated the board.

**What is left.** Run the full 12-question eval on a GPU. Add a check that the quote supports the claim. `DR_LIVE=1 pytest -m live` was not rerun after the crash, but the committed live eval and examples came from real runs. Commits 1ab1ca4..19c11d2 carry a Sonnet co-author trailer instead of the Opus one. I left history unrewritten.

**How to verify.** Run the commands in the section above, or follow `docs/DEVDOCS.md` section 5.
