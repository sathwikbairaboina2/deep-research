"""Offline verifier benchmark (ADR-0010): genuine sentences versus mutated copies of them."""

from __future__ import annotations

import hashlib
import json
import random
import re
from html.parser import HTMLParser
from importlib.metadata import version
from pathlib import Path

from quoteproof import NORM_VERSION, Citation, Claim, Corpus, normalize, verify_claim

from deep_research.fetch import extract_text

BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th", "pre"}
BLOCK_TAGS |= {"dd", "dt"}
SKIP_TAGS = {"script", "style"}
SWAP_WORDS = ["zebra", "never", "seven", "purple", "always"]
KINDS = ["swap_word", "delete_word", "change_number", "insert_not", "transpose"]
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DIGITS = re.compile(r"\d+")


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_sentences(html: str) -> list[str]:
    """Sentences of 8 to 40 words from a stdlib text pass, independent of trafilatura."""
    parser = _TextParser()
    parser.feed(html)
    out: list[str] = []
    seen: set[str] = set()
    for line in "".join(parser.parts).split("\n"):
        for sent in _SENT_SPLIT.split(" ".join(line.split())):
            n = len(sent.split())
            if 8 <= n <= 40 and sent not in seen:
                seen.add(sent)
                out.append(sent)
    return out


def swap_word(quote: str, rng: random.Random) -> str | None:
    words = quote.split()
    idx = [i for i, w in enumerate(words) if len(w) >= 4]
    if not idx:
        return None
    i = rng.choice(idx)
    new = next(w for w in SWAP_WORDS if w != words[i].lower())
    return " ".join([*words[:i], new, *words[i + 1 :]])


def delete_word(quote: str, rng: random.Random) -> str | None:
    words = quote.split()
    if len(words) < 3:
        return None
    i = rng.randrange(1, len(words) - 1)
    return " ".join([*words[:i], *words[i + 1 :]])


def change_number(quote: str, rng: random.Random) -> str | None:
    m = _DIGITS.search(quote)
    if not m:
        return None
    return quote[: m.start()] + str(int(m.group()) + 1) + quote[m.end() :]


def insert_not(quote: str, rng: random.Random) -> str | None:
    words = quote.split()
    if not words:
        return None
    i = rng.randrange(len(words))
    return " ".join([*words[: i + 1], "not", *words[i + 1 :]])


def transpose(quote: str, rng: random.Random) -> str | None:
    words = quote.split()
    idx = [i for i in range(len(words) - 1) if words[i].lower() != words[i + 1].lower()]
    if not idx:
        return None
    i = rng.choice(idx)
    words[i], words[i + 1] = words[i + 1], words[i]
    return " ".join(words)


MUTATORS = {
    "swap_word": swap_word,
    "delete_word": delete_word,
    "change_number": change_number,
    "insert_not": insert_not,
    "transpose": transpose,
}


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def run_bench(pages_dir: Path, *, seed: int = 42, per_page: int = 40) -> dict:
    pages = sorted(Path(pages_dir).glob("*.html"))
    corpus_info = []
    genuine_total = genuine_ok = 0
    rejected_by_reason: dict[str, int] = {}
    by_kind = {k: {"total": 0, "rejected": 0, "skipped": 0} for k in KINDS}
    mutated_reasons: dict[str, int] = {}
    quote_index = 0

    for page in pages:
        raw = page.read_bytes()
        text, _ = extract_text(raw, "text/html")
        text = text or ""
        source_id = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        corpus = Corpus({source_id: text})
        normalized_page = corpus.normalized(source_id)
        sentences = html_sentences(raw.decode("utf-8", errors="replace"))
        sample = random.Random(seed).sample(sentences, min(per_page, len(sentences)))
        corpus_info.append(
            {
                "file": page.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "sentences": len(sentences),
                "sampled": len(sample),
            }
        )
        for sentence in sample:
            genuine_total += 1
            verdict = verify_claim(Claim("g", "g", (Citation(source_id, sentence),)), corpus)
            if verdict.status != "verified":
                rejected_by_reason[verdict.reason] = rejected_by_reason.get(verdict.reason, 0) + 1
                continue
            genuine_ok += 1
            for kind in KINDS:
                stats = by_kind[kind]
                mutated = MUTATORS[kind](sentence, random.Random(seed + quote_index))
                if mutated is None or normalize(mutated) in normalized_page:
                    stats["skipped"] += 1
                    continue
                stats["total"] += 1
                result = verify_claim(Claim("m", "m", (Citation(source_id, mutated),)), corpus)
                if result.status == "rejected":
                    stats["rejected"] += 1
                    mutated_reasons[result.reason] = mutated_reasons.get(result.reason, 0) + 1
            quote_index += 1

    m_total = sum(s["total"] for s in by_kind.values())
    m_rej = sum(s["rejected"] for s in by_kind.values())
    for stats in by_kind.values():
        stats["rate"] = _rate(stats["rejected"], stats["total"])
    return {
        "bench": "quoteproof-v1",
        "seed": seed,
        "per_page": per_page,
        "norm": NORM_VERSION,
        "corpus": corpus_info,
        "genuine": {
            "total": genuine_total,
            "accepted": genuine_ok,
            "rate": _rate(genuine_ok, genuine_total),
            "rejected_by_reason": dict(sorted(rejected_by_reason.items())),
        },
        "mutated": {
            "by_kind": by_kind,
            "total": m_total,
            "rejected": m_rej,
            "rate": _rate(m_rej, m_total),
            "rejected_by_reason": dict(sorted(mutated_reasons.items())),
        },
        "versions": {
            "quoteproof": version("quoteproof"),
            "trafilatura": version("trafilatura"),
        },
    }


def summary_line(result: dict) -> str:
    g, m = result["genuine"], result["mutated"]
    return (
        f"genuine accepted {g['accepted']}/{g['total']} ({g['rate']}) | "
        f"mutated rejected {m['rejected']}/{m['total']} ({m['rate']})"
    )


def dumps(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def first_difference(a, b, path: str = "") -> str | None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                return f"{path}/{key}"
            found = first_difference(a[key], b[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path} (length)"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            found = first_difference(x, y, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if a == b else path or "/"


def bench_main(pages: str, seed: int, per_page: int, out: str | None, check: str | None) -> int:
    result = run_bench(Path(pages), seed=seed, per_page=per_page)
    print(summary_line(result))
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(result), encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    if check:
        expected = json.loads(Path(check).read_text(encoding="utf-8"))
        diff = first_difference(expected, json.loads(dumps(result)))
        if diff:
            print(f"bench check FAILED: first difference at {diff}")
            return 1
        print("bench check ok")
    return 0
