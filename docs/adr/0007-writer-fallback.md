# ADR-0007: The writer gets one lint retry, then a deterministic fallback report

- Status: accepted (2026-10-04)

## Context
The design says a draft with orphan markers fails the run. One LLM call takes minutes on the local box, so failing a 20-minute run on a formatting slip wastes all the verified work.

## Decision
- Draft, then lint. On failure, retry once with the lint errors in the prompt. On a second failure, write the fallback report: verified claims as bullets under topic headings, each ending in its own marker. It always passes the linter by construction, and the code still lints it.
- `run.json` records `writer: "llm" | "llm_retry" | "fallback"`, and `dr eval` reports the fallback rate.

## What I gave up
- A guaranteed prose report. The trust guarantee (no orphan or rejected markers ever ship) is kept.
