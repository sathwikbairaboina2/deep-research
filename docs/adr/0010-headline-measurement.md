# ADR-0010: The headline comes from two measured files, never from prose

- Status: accepted (2026-10-04)

## Decision
- `dr bench` (offline, seed 42, committed fixture pages): genuine quotes are sentences of 8 to 40 words taken from an independent stdlib `HTMLParser` text pass, not from trafilatura, so the number measures real extraction drift. Mutations (word swap, word deletion, number change, negation insert, adjacent-word transposition) are applied to quotes that were found. Output: `bench/results/latest.json`. A planning prototype on the same pages accepted 198 of 200 genuine quotes. The README must use the repo's own run, not this prototype figure.
- `dr eval` (live, Ollama + SearXNG): rejection rate and shipped-unverifiable citations per question. Output: `evals/results/<date>.json`. One LLM call took 138.8 s under shared-GPU load, so the committed live run uses `--limit 3` with small caps, and the README states N.
- If the live eval cannot finish, the README headline uses the bench numbers and says the live numbers are pending.

## What I gave up
- A large live sample. Three questions are a demo, not a statistic, and the README says that.
