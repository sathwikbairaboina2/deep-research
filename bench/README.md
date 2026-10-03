# Verifier benchmark

`dr bench` measures the `quoteproof` verifier with no network and no model.

## What it measures

- **Genuine quotes.** For each of the 5 committed SQLite documentation pages
  (`tests/fixtures/pages`), a stdlib `HTMLParser` pass splits the page into sentences of
  8 to 40 words. Up to `--per-page` (default 40) are sampled with `random.Random(seed)`.
  The page text that the verifier checks against comes from a different extractor
  (trafilatura, the same one the agent uses). So a genuine quote that the verifier rejects
  shows extraction drift between the two passes.
- **Mutated quotes.** Every accepted genuine quote is mutated five ways: `swap_word`,
  `delete_word`, `change_number`, `insert_not`, `transpose`. A mutation is skipped when it
  does not apply (for example no digits) or when the mutated text still occurs in the
  normalized page. Every other mutation must be rejected.

`bench/results/latest.json` holds the result. It has no timestamps, so a re-run must be
identical.

## Run it

```bash
uv run python -m deep_research bench --out bench/results/latest.json   # write
uv run python -m deep_research bench --check bench/results/latest.json # exit 1 on any difference
```

On Linux, Docker and CI the same command works as `dr bench ...`.

## Caveats

- The verifier is an exact normalized substring check, so the mutated-quote score mostly shows
  that the plumbing, normalization and length rules do what ADR-0002 says. It does not show
  that a real quote supports the claim it is attached to.
- The corpus is five documentation pages from one site. Other layouts (tables, PDFs) may
  show more extraction drift.
- Mutations rejected for a reason other than `QUOTE_NOT_FOUND` are listed under
  `mutated.rejected_by_reason`.
