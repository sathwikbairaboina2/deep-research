# ADR-0006: The model cites `S1..Sn` labels, never hashes

- Status: accepted (2026-10-04)

## Decision
- Each extract prompt lists its sources as `[S1] <url>` blocks. The model returns `{"source": "S1", "quote": "..."}`.
- The extractor maps labels to `sha256:` ids with the same table it used to build the prompt. An unknown label maps to `label:<label>`, which the verifier rejects as `UNKNOWN_SOURCE`.

## What I gave up
- Nothing the verifier relies on. The mapping is deterministic code, and the model cannot corrupt a 71-character id it never types.
