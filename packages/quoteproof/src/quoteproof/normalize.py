import re
import unicodedata

NORM_VERSION = "NORM_V1"

_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "″": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
    }
)
_WS = re.compile(r"\s+")


def _pass(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_MAP)
    return _WS.sub(" ", text).strip().casefold()


def normalize(text: str) -> str:
    """NORM_V1: NFKC, ASCII quotes and dashes, collapsed whitespace, casefold.

    Applied twice: casefold can emit sequences that NFKC recomposes,
    so two passes make it idempotent.
    """
    return _pass(_pass(text))
