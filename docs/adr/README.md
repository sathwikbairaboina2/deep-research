# Architecture decision records

| ADR | Decision |
|---|---|
| [0001](0001-quoteproof-zero-dependency-package.md) | The verifier ships as `quoteproof`, a zero-dependency package |
| [0002](0002-exact-normalized-substring.md) | Exact substring match after NORM_V1; all citations must pass |
| [0003](0003-ollama-native-structured-output.md) | Ollama `/api/chat` with a JSON-schema `format`, behind an `LLM` protocol |
| [0004](0004-v0-1-scope.md) | v0.1 includes fan-out and resume; excludes JS, PDF pages, LLM judge |
| [0005](0005-budget-ledger.md) | Thread-safe persisted budget; exact search and fetch caps, reserved tokens |
| [0006](0006-source-labels.md) | The model cites `S1..Sn` labels, mapped back in code |
| [0007](0007-writer-fallback.md) | One lint retry, then a deterministic fallback report |
| [0008](0008-toolchain-and-isolation.md) | Host uv dev loop, Docker for SearXNG and parity, ports 5300-5309 |
| [0009](0009-testing-without-network.md) | No-network tests, scripted LLM, crash-injection resume test |
| [0010](0010-headline-measurement.md) | Headline from `dr bench` and `dr eval` JSON only |
