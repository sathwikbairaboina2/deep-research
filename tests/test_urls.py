import pytest

from deep_research.urls import canonical_url, is_denied


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("HTTP://Example.COM/A", "http://example.com/A"),
        ("https://example.com:443/x", "https://example.com/x"),
        ("http://example.com:80/x", "http://example.com/x"),
        ("https://example.com:8443/x", "https://example.com:8443/x"),
        ("https://example.com/x#frag", "https://example.com/x"),
        ("https://example.com/x?utm_source=a&b=2&a=1", "https://example.com/x?a=1&b=2"),
        ("https://example.com/x?fbclid=1&gclid=2&ref=3", "https://example.com/x"),
        ("https://example.com/x/", "https://example.com/x"),
        ("https://example.com", "https://example.com/"),
        ("https://www.example.com/", "https://www.example.com/"),
    ],
)
def test_canonical_url(raw, want):
    assert canonical_url(raw) == want


def test_is_denied():
    assert is_denied("https://m.youtube.com/x")
    assert is_denied("https://youtube.com/x")
    assert not is_denied("https://notyoutube.com")
