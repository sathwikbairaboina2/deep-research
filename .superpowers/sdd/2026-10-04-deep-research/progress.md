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
