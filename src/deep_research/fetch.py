from __future__ import annotations

import io
import threading
import time
import urllib.robotparser
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx
import pypdf
import trafilatura

from deep_research.models import FetchResult
from deep_research.urls import canonical_url

ALLOWED_TYPES = {"text/html", "application/xhtml+xml", "application/pdf", "text/plain"}
DEFAULT_UA = "deep-research/0.1 (+local research agent)"


def _charset(content_type: str) -> str:
    for part in content_type.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value.strip("\"'")
    return "utf-8"


def _decode(body: bytes, content_type: str) -> str:
    try:
        return body.decode(_charset(content_type), errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def extract_text(body: bytes, content_type: str) -> tuple[str | None, str]:
    """Return (text or None, extractor name) for an allowed content type."""
    base = content_type.split(";")[0].strip().lower()
    if base in ("text/html", "application/xhtml+xml"):
        text = trafilatura.extract(
            _decode(body, content_type),
            include_tables=True,
            favor_recall=True,
            deduplicate=False,
        )
        extractor = "trafilatura"
    elif base == "application/pdf":
        reader = pypdf.PdfReader(io.BytesIO(body))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        extractor = "pypdf"
    else:
        text = _decode(body, content_type)
        extractor = "plain"
    if text is None or not text.strip():
        return None, extractor
    return text, extractor


class RobotsCache:
    """robots.txt per scheme+host. 4xx or network error allows all, 5xx disallows all."""

    def __init__(self, client: httpx.Client, user_agent: str = DEFAULT_UA) -> None:
        self.client = client
        self.user_agent = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser | bool] = {}
        self._lock = threading.Lock()

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        key = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            if key not in self._cache:
                self._cache[key] = self._load(key)
            entry = self._cache[key]
        if isinstance(entry, bool):
            return entry
        return entry.can_fetch(self.user_agent, url)

    def _load(self, key: str) -> urllib.robotparser.RobotFileParser | bool:
        try:
            resp = self.client.get(
                f"{key}/robots.txt",
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            )
        except httpx.HTTPError:
            return True
        if resp.status_code >= 500:
            return False
        if resp.status_code >= 400:
            return True
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser


class Fetcher:
    def __init__(
        self,
        client: httpx.Client,
        *,
        max_bytes: int,
        timeout_s: float,
        user_agent: str = DEFAULT_UA,
        robots: RobotsCache | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.max_bytes = max_bytes
        self.timeout_s = timeout_s
        self.user_agent = user_agent
        self.robots = robots
        self.clock = clock

    def _result(self, url: str, **kw) -> FetchResult:
        base = {
            "url": url,
            "final_url": url,
            "canonical_url": canonical_url(url),
            "status": 0,
            "content_type": "",
            "bytes": 0,
            "truncated": False,
            "text": None,
            "extractor": None,
            "error": None,
        }
        base.update(kw)
        return FetchResult(**base)

    def __call__(self, url: str) -> FetchResult:
        if self.robots is not None and not self.robots.allowed(url):
            return self._result(url, error="ROBOTS_DISALLOWED")
        start = self.clock()
        status = 0
        final_url = url
        ctype = ""
        try:
            with self.client.stream(
                "GET",
                url,
                follow_redirects=True,
                timeout=httpx.Timeout(self.timeout_s),
                headers={"User-Agent": self.user_agent},
            ) as resp:
                status = resp.status_code
                final_url = str(resp.url)
                ctype = resp.headers.get("content-type", "")
                base = ctype.split(";")[0].strip().lower()
                if not 200 <= status < 300:
                    return self._result(
                        url, final_url=final_url, status=status, content_type=ctype,
                        error=f"HTTP_{status}",
                    )  # fmt: skip
                if base not in ALLOWED_TYPES:
                    return self._result(
                        url, final_url=final_url, status=status, content_type=ctype,
                        error="CONTENT_TYPE",
                    )  # fmt: skip
                body = bytearray()
                truncated = False
                timed_out = False
                for chunk in resp.iter_bytes():
                    room = self.max_bytes - len(body)
                    if len(chunk) > room:
                        body += chunk[:room]
                        truncated = True
                        break
                    body += chunk
                    if self.clock() - start > self.timeout_s:
                        timed_out = True
                        break
        except httpx.TimeoutException:
            return self._result(
                url, final_url=final_url, status=status, content_type=ctype, error="TIMEOUT"
            )
        except httpx.HTTPError as exc:
            return self._result(
                url, final_url=final_url, status=status, content_type=ctype,
                error=f"NETWORK_{type(exc).__name__}",
            )  # fmt: skip
        common = {
            "final_url": final_url,
            "status": status,
            "content_type": ctype,
            "bytes": len(body),
            "truncated": truncated,
        }
        if timed_out:
            return self._result(url, error="TIMEOUT", **common)
        if truncated and base == "application/pdf":
            return self._result(url, error="PDF_TRUNCATED", **common)
        try:
            text, extractor = extract_text(bytes(body), ctype)
        except Exception as exc:  # parser failures must not crash a research run
            return self._result(url, error=f"EXTRACT_{type(exc).__name__}", **common)
        if text is None:
            return self._result(url, error="NO_TEXT", extractor=extractor, **common)
        return self._result(url, text=text, extractor=extractor, **common)
