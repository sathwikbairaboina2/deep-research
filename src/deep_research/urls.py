from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_DENYLIST: tuple[str, ...] = (
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
    "linkedin.com",
)

_DROP_KEYS = {"fbclid", "gclid", "ref"}
_DEFAULT_PORTS = {"http": 80, "https": 443}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host
    if port and _DEFAULT_PORTS.get(scheme) != port:
        netloc = f"{host}:{port}"
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.startswith("utm_") and k not in _DROP_KEYS
    ]
    query = urlencode(sorted(pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def is_denied(url: str, denylist: Iterable[str] = DEFAULT_DENYLIST) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in denylist)
