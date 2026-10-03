from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .normalize import NORM_VERSION, normalize

NO_CITATIONS = "NO_CITATIONS"
UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
QUOTE_TOO_SHORT = "QUOTE_TOO_SHORT"
QUOTE_TOO_LONG = "QUOTE_TOO_LONG"
QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"
FOUND = "found"
MIN_WORDS, MIN_CHARS, MAX_WORDS = 6, 30, 80


@dataclass(frozen=True)
class Citation:
    source_id: str
    quote: str


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class CitationResult:
    source_id: str
    status: str  # "found" or a rejection code
    offset: int | None  # index into normalize(page text)
    match: str | None  # "exact_normalized" when found


@dataclass(frozen=True)
class Verdict:
    claim_id: str
    status: str  # "verified" | "rejected"
    citations: tuple[CitationResult, ...]
    reason: str | None
    norm: str = NORM_VERSION

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "status": self.status,
            "reason": self.reason,
            "norm": self.norm,
            "citations": [
                {
                    "source_id": c.source_id,
                    "status": c.status,
                    "offset": c.offset,
                    "match": c.match,
                }
                for c in self.citations
            ],
        }


class Corpus:
    """Read-only map source_id -> raw text with a memo of normalized text."""

    def __init__(self, texts: Mapping[str, str]) -> None:
        self._texts = dict(texts)
        self._norm: dict[str, str] = {}

    def __contains__(self, source_id: object) -> bool:
        return source_id in self._texts

    def normalized(self, source_id: str) -> str:
        cached = self._norm.get(source_id)
        if cached is None:
            cached = normalize(self._texts[source_id])
            self._norm[source_id] = cached
        return cached


def check_quote(source_id: str, quote: str, corpus: Corpus) -> CitationResult:
    if source_id not in corpus:
        return CitationResult(source_id, UNKNOWN_SOURCE, None, None)
    nq = normalize(quote)
    words = len(nq.split())
    if words < MIN_WORDS or len(nq) < MIN_CHARS:
        return CitationResult(source_id, QUOTE_TOO_SHORT, None, None)
    if words > MAX_WORDS:
        return CitationResult(source_id, QUOTE_TOO_LONG, None, None)
    offset = corpus.normalized(source_id).find(nq)
    if offset == -1:
        return CitationResult(source_id, QUOTE_NOT_FOUND, None, None)
    return CitationResult(source_id, FOUND, offset, "exact_normalized")


def verify_claim(claim: Claim, texts: Corpus | Mapping[str, str]) -> Verdict:
    corpus = texts if isinstance(texts, Corpus) else Corpus(texts)
    if not claim.citations:
        return Verdict(claim.claim_id, "rejected", (), NO_CITATIONS)
    results = tuple(check_quote(c.source_id, c.quote, corpus) for c in claim.citations)
    bad = next((r for r in results if r.status != FOUND), None)
    if bad is None:
        return Verdict(claim.claim_id, "verified", results, None)
    return Verdict(claim.claim_id, "rejected", results, bad.status)


def verify_claims(claims: Iterable[Claim], texts: Corpus | Mapping[str, str]) -> list[Verdict]:
    corpus = texts if isinstance(texts, Corpus) else Corpus(texts)
    return [verify_claim(c, corpus) for c in claims]
