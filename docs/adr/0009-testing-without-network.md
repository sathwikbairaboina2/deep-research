# ADR-0009: Tests run with sockets disabled, a scripted LLM and local servers; resume is tested with an injected crash

- Status: accepted (2026-10-04)

## Decision
- `pytest-socket` with `--disable-socket --allow-unix-socket` for the whole suite. Fetch and serve tests opt in with `@pytest.mark.allow_hosts(["127.0.0.1"])` and use a local `ThreadingHTTPServer`.
- Search tests use `httpx.MockTransport` and the recorded SearXNG response `tests/fixtures/searxng/sqlite_wal.json`.
- Verifier and bench tests use the 5 committed SQLite documentation pages (public domain).
- Graph tests use `ScriptedLLM` plus fake search and fetch functions.
- Resume (invariant 8) is tested with a fake fetch that raises on its Nth call, then a second `build_graph` over the same SQLite files with `invoke(None, config)`. This replaces the design's `kill -9` subprocess test, which is slow and flaky on Windows. The checkpoint semantics are the same (prototype: only the failed branch re-ran).
- Live tests are marked `live` and skip unless `DR_LIVE=1`.

## What I gave up
- Proof against a hard kill between a checkpoint write and its commit. SQLite transactions cover that case; the test does not.
