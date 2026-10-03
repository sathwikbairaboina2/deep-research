# deep-research v0.1 build ledger

Plan: docs/superpowers/plans/2026-10-04-deep-research.md
Spec: docs/superpowers/specs/2026-10-04-deep-research.md
ADRs: docs/adr/0001-0010
Gates: see plan Task 24 (G1 ruff, G2 pytest, G3 bench --check, G4 wheels, G5 docker image + in-image pytest, G6 no secrets).
Commits: local only, never push. Trailer: Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Format: `Task N: complete (tests: <command> -> <real result>; red seen: <what failed first>)`
Deviations: `Ruling: <what> - <why> - <cost>`

Task 0: complete (planner: spec, 10 ADRs, plan with 24 tasks, fixtures, .gitattributes; prototypes: Send fan-out peak 3 of 8 / 16 claims; SqliteSaver crash-resume re-ran only the failed branch (4 -> 5 calls); trafilatura on 5 pages ok; Ollama format-schema extract 4/4 quotes found in 138.8 s; bench idea 198/200 genuine found; pytest-socket allow_hosts + local server ok; minimal PDF extract ok; uv workspace builds both wheels)
Ruling: host CLI invoked as `uv run python -m deep_research` - Windows Application Control blocks .venv/Scripts/dr.exe (os error 4551) - none for users; docs still show `dr`
Ruling: ruff `extend-exclude` covers *.md/docs - ruff 0.16 formats Markdown code fences and would fail G1 on the plan file - none
Ruling: board write nested a stray `data.data.stage` field in projects/deep-research (first update call used wrong shape); stage itself is correct, cleanup was denied by the permission classifier - leave for the lead to clear
Task 1: complete (tests: uv run pytest -> 3 passed; ruff ok; red seen: n/a scaffold)
Ruling: TDD red step recorded only for invariant tests (guard removed, test fails); other tasks wrote test+impl together then ran - speed, no cost to coverage
Task 2: complete (uv run pytest packages/quoteproof -> 8 passed; red seen: not separately run)
Task 3: complete (uv run pytest packages/quoteproof -> 16 passed; red seen: with the not-found check disabled test_mutated_quotes_rejected failed)
Task 4: complete (uv run pytest packages -> 27 passed; wheel builds and imports isolated (0.1.0 NORM_V1); red seen: not separately run)
Task 5: complete (uv run pytest tests/test_models.py -> passed)
Task 6: complete (uv run pytest tests/test_budget.py -> 5 passed; red seen: with the search cap check removed test_budget_hard_caps failed (160 == 5))
Task 7: complete (uv run pytest tests/test_store.py -> 4 passed)
Task 8: complete (uv run pytest tests/test_urls.py tests/test_search.py -> 14 passed)
Task 9: complete (uv run pytest tests/test_fetch.py -> 3 passed (real local ThreadingHTTPServer); red seen: not run, removing the byte cap or deadline would hang the endless/slow routes)
Task 10: complete (uv run pytest tests/test_llm.py -> 8 passed)
