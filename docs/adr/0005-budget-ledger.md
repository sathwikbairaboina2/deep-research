# ADR-0005: One thread-safe budget per run, persisted as events; searches and fetches are exact, tokens are reserved

- Status: accepted (2026-10-04)

## Decision
- `Budget` lives outside graph state, because state copies would split it across parallel `Send` branches. Nodes get it from the `Deps` object that `build_graph` closes over.
- `charge(kind, n)` checks and records under a lock before the network call, so `searches` and `fetches` can never exceed their caps.
- Tokens: before each LLM call, `reserve_tokens(estimate)` with `estimate = ceil(len(system + user) / 3) + num_predict`. It raises `BudgetExceeded` if `used + estimate > max_tokens`. After the call, the actual usage is recorded. A cap overshoot is possible only if the model used more tokens than the reservation.
- Wall clock: checked before every search, fetch and LLM call against `max_wall_s`, measured from the start of this process. A resumed run gets a fresh wall budget, and `run.json` records both segments.
- Every charge is appended to `budget_events`, so `dr resume` rebuilds the totals and nothing is double counted.

## What I gave up
- An exact token cap. Exact would need a tokenizer for every model. The reservation is conservative and any overshoot is visible in `run.json`.
