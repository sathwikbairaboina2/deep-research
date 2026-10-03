# ADR-0001: The verifier ships as `quoteproof`, a zero-dependency workspace package

- Status: accepted (2026-10-04)

## Context
The portfolio bar asks for something other people can install. The most reusable part of this project is not the agent. It is the check that a quote really is on the cited page. Other agents (LangChain, LlamaIndex, plain scripts) could use that check without LangGraph.

## Decision
- `packages/quoteproof` is a uv workspace member with no runtime dependencies (stdlib only). It holds `normalize`, `verify_claim`, `Corpus`, `lint_report` and `render_footnotes`.
- The app package `deep-research` depends on it through `[tool.uv.sources] quoteproof = { workspace = true }`.
- `uv build --package quoteproof` must produce a wheel that imports in a clean environment.
- The name was checked free on PyPI on 2026-10-04 (`citecheck` and `quotecheck` were taken).

## What I gave up
- A separate repository and a real PyPI release. Nothing is pushed or published in v0.1. The wheel is built locally and in CI.
- Pydantic models inside the verifier. It uses frozen dataclasses so it stays dependency-free. The app converts at the boundary.
