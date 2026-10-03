from hypothesis import given
from hypothesis import strategies as st
from quoteproof.normalize import NORM_VERSION, normalize


def test_whitespace_and_case():
    assert normalize("  WAL provides\n\tmore ") == "wal provides more"


def test_quotes_and_dashes():
    assert normalize("“Readers” don’t block – writers") == ('"readers" don\'t block - writers')


def test_ligature():
    assert normalize("ﬁle") == "file"


def test_casefold():
    assert normalize("STRASSE") == normalize("straße")


def test_version():
    assert NORM_VERSION == "NORM_V1"


@given(st.text())
def test_idempotent_and_clean(s):
    n = normalize(s)
    assert normalize(n) == n
    assert n == n.strip()
    assert "  " not in n
    assert "\n" not in n


_WORDS = st.text(alphabet=st.characters(categories=["L", "N", "Zs", "P"]))


@given(_WORDS, _WORDS, _WORDS)
def test_substring_preserved(x, a, y):
    b = x + " " + a + " " + y
    assert normalize(a) in normalize(b)
