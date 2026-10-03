import pytest
from quoteproof.lint import (
    MALFORMED_MARKER,
    NO_MARKERS,
    REJECTED_MARKER,
    UNKNOWN_MARKER,
    lint_report,
    render_footnotes,
)

VERIFIED = {"a1", "b2"}
KNOWN = {"a1", "b2", "r9"}


@pytest.mark.parametrize(
    ("draft", "code"),
    [
        ("Claim [c:zz].", UNKNOWN_MARKER),
        ("Claim [c:r9].", REJECTED_MARKER),
        ("Claim [C:a1].", MALFORMED_MARKER),
        ("Claim [c: a1].", MALFORMED_MARKER),
        ("Claim [c:a1,b2].", MALFORMED_MARKER),
        ("Claim [c:a1 and more", MALFORMED_MARKER),
        ("Claim [c:].", MALFORMED_MARKER),
        ("No markers here.", NO_MARKERS),
    ],
)
def test_linter_rejects_orphan_markers(draft, code):
    result = lint_report(draft, VERIFIED, KNOWN)
    assert not result.ok
    assert code in {e.code for e in result.errors}


def test_clean_draft():
    result = lint_report("X [c:a1]. Y [c:b2]. Z [c:a1].", VERIFIED, KNOWN)
    assert result.ok
    assert result.markers == ("a1", "b2")


def test_render_footnotes():
    out = render_footnotes("X [c:a1]. Y [c:b2]. Z [c:a1].", {"a1": "note a", "b2": "note b"})
    assert out == "X [^1]. Y [^2]. Z [^1].\n\n[^1]: note a\n[^2]: note b"


def test_render_missing_note():
    with pytest.raises(ValueError):
        render_footnotes("X [c:a1].", {})
