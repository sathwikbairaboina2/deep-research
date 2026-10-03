import builtins
import json
import random
from pathlib import Path

from hypothesis import assume, given
from hypothesis import strategies as st
from quoteproof import (
    Citation,
    Claim,
    Corpus,
    normalize,
    verify_claim,
    verify_claims,
)

T = (Path(__file__).parent / "fixtures" / "wal.txt").read_text(encoding="utf-8")
S = "sha256:wal"
NT = normalize(T)
NWORDS = NT.split()
GOOD = "WAL provides more concurrency as readers do not block writers"


def claim(cid, *quotes, source=S):
    return Claim(cid, "text", tuple(Citation(source, q) for q in quotes))


def test_verified():
    v = verify_claim(claim("c1", GOOD), {S: T})
    assert v.status == "verified"
    assert v.reason is None
    assert v.norm == "NORM_V1"
    assert v.citations[0].offset == NT.find(normalize(GOOD))
    assert v.citations[0].match == "exact_normalized"


def test_case_and_whitespace_drift():
    words = GOOD.upper().split()
    drifted = " ".join(words[:3]) + "\n  " + " ".join(words[3:])
    assert verify_claim(claim("c1", drifted), {S: T}).status == "verified"


def test_rejection_codes():
    texts = {S: T}
    assert verify_claim(Claim("c", "t", ()), texts).reason == "NO_CITATIONS"
    assert verify_claim(claim("c", GOOD, source="sha256:zzz"), texts).reason == "UNKNOWN_SOURCE"
    assert verify_claim(claim("c", "one two three four five"), texts).reason == "QUOTE_TOO_SHORT"
    short_chars = "a b c d e f"
    assert verify_claim(claim("c", short_chars), texts).reason == "QUOTE_TOO_SHORT"
    long_quote = " ".join(NWORDS[:20] * 5)  # 100 words
    assert len(long_quote.split()) > 80
    assert verify_claim(claim("c", long_quote), texts).reason == "QUOTE_TOO_LONG"
    para = "WAL lets many readers proceed while a single writer appends to the log"
    assert verify_claim(claim("c", para), texts).reason == "QUOTE_NOT_FOUND"


def test_one_bad_citation_rejects_claim():
    v = verify_claim(claim("c", GOOD, "readers never block anything at all in WAL mode"), {S: T})
    assert v.status == "rejected"
    assert v.reason == "QUOTE_NOT_FOUND"
    assert v.citations[0].status == "found"


def test_to_dict_json():
    v = verify_claim(claim("c", GOOD), {S: T})
    assert json.loads(json.dumps(v.to_dict()))["citations"][0]["status"] == "found"


def _windows(rng, n):
    out = []
    for _ in range(n):
        size = rng.randint(10, 30)
        start = rng.randint(0, len(NWORDS) - size)
        out.append(NWORDS[start : start + size])
    return out


def _mutations(words, rng):
    w = list(words)
    i = rng.randrange(len(w))
    swap = w[:i] + ["zebra"] + w[i + 1 :]
    delete = w[: len(w) // 2] + w[len(w) // 2 + 1 :]
    insert = w[:3] + ["not"] + w[3:]
    j = next((k for k in range(len(w) - 1) if w[k] != w[k + 1]), None)
    trans = None
    if j is not None:
        trans = w[:j] + [w[j + 1], w[j]] + w[j + 2 :]
    return [swap, delete, insert, trans]


def test_mutated_quotes_rejected():
    rng = random.Random(7)
    checked = 0
    for words in _windows(rng, 30):
        genuine = " ".join(words)
        assert verify_claim(claim("g", genuine), {S: T}).status == "verified"
        for mutated in _mutations(words, rng):
            if mutated is None:
                continue
            text = " ".join(mutated)
            if text in NT:
                continue
            checked += 1
            v = verify_claim(claim("m", text), {S: T})
            assert v.reason == "QUOTE_NOT_FOUND", text
    assert checked >= 110


def test_verifier_is_pure(monkeypatch):
    rng = random.Random(1)
    claims = []
    for i, words in enumerate(_windows(rng, 40)):
        q = " ".join(words)
        if i % 3 == 1:
            q = q + " zebra"
        src = "sha256:other" if i % 3 == 2 else S
        claims.append(claim(f"c{i}", q, source=src))
    corpus = Corpus({S: T})
    baseline = {v.claim_id: v for v in verify_claims(claims, corpus)}
    assert {v.status for v in baseline.values()} == {"verified", "rejected"}

    def no_open(*a, **k):
        raise AssertionError("file I/O in verifier")

    monkeypatch.setattr(builtins, "open", no_open)
    for i in range(100):
        shuffled = random.Random(i).sample(claims, len(claims))
        for v in verify_claims(shuffled, {S: T}):
            assert v == baseline[v.claim_id]


@given(st.data())
def test_windows_always_verify(data):
    size = data.draw(st.integers(6, 80))
    start = data.draw(st.integers(0, len(NWORDS) - size))
    quote = " ".join(NWORDS[start : start + size])
    assume(len(quote) >= 30)  # MIN_CHARS rule
    assert verify_claim(claim("c", quote), {S: T}).status == "verified"
