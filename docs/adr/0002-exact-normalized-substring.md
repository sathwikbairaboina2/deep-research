# ADR-0002: A citation passes only on an exact substring match after NORM_V1

- Status: accepted (2026-10-04)

## Decision
- NORM_V1 = NFKC, curly quotes and dashes to ASCII, collapse whitespace, strip, casefold. It is applied to the quote and the page text alike. Nothing else: no stemming, no edit distance, no embeddings.
- Every citation of a claim must be found. One missing quote rejects the whole claim (the design's open question, decided as "all must pass").
- Quotes must be 6 to 80 words and at least 30 characters, so a model cannot pass by quoting "the" or by pasting a whole section.
- Offsets are indexes into the normalized text. The serve view re-normalizes to highlight.
- `NORM_V1` is written into every verdict. Changing normalization means a new version string.

## What I gave up
- Recall. A genuine quote that crosses a boundary the extractor rewrote (table cells, footnotes, hyphenation) is rejected. `dr bench` measures this false-rejection rate instead of hiding it.
- Any notion of "supports the claim". A real quote attached to a wrong claim still passes. The README says so.
