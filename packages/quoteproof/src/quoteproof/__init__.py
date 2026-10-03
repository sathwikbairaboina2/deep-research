from .normalize import NORM_VERSION, normalize
from .verify import (
    FOUND,
    NO_CITATIONS,
    QUOTE_NOT_FOUND,
    QUOTE_TOO_LONG,
    QUOTE_TOO_SHORT,
    UNKNOWN_SOURCE,
    Citation,
    CitationResult,
    Claim,
    Corpus,
    Verdict,
    check_quote,
    verify_claim,
    verify_claims,
)

__version__ = "0.1.0"

__all__ = [
    "FOUND",
    "NORM_VERSION",
    "NO_CITATIONS",
    "QUOTE_NOT_FOUND",
    "QUOTE_TOO_LONG",
    "QUOTE_TOO_SHORT",
    "UNKNOWN_SOURCE",
    "Citation",
    "CitationResult",
    "Claim",
    "Corpus",
    "Verdict",
    "check_quote",
    "normalize",
    "verify_claim",
    "verify_claims",
]
