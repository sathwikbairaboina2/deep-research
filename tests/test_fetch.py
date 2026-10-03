import contextlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
from fakes import make_pdf

from deep_research.fetch import Fetcher, RobotsCache, extract_text

PAGES = Path(__file__).parent / "fixtures" / "pages"
WAL = (PAGES / "wal.html").read_bytes()
PDF = make_pdf("Hello quoteproof world")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    log: list[str] = []

    def log_message(self, *args):
        pass

    def _send(self, status, ctype, body):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Handler.log.append(self.path)
        with contextlib.suppress(BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.route()

    def route(self):
        path = self.path
        if path == "/robots.txt":
            self._send(200, "text/plain", b"User-agent: *\nDisallow: /private\n")
        elif path == "/page":
            self._send(200, "text/html; charset=utf-8", WAL)
        elif path == "/pdf":
            self._send(200, "application/pdf", PDF)
        elif path == "/bin":
            self._send(200, "application/octet-stream", b"\x00\x01\x02")
        elif path == "/private":
            self._send(200, "text/html", b"<p>secret</p>")
        elif path == "/endless":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            chunk = b"<p>" + b"lorem ipsum " * 5000 + b"</p>"
            while True:
                self.wfile.write(chunk)
        elif path == "/slow":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            while True:
                self.wfile.write(b"0123456789")
                self.wfile.flush()
                time.sleep(0.3)
        else:
            self._send(404, "text/html", b"<p>nope</p>")


@pytest.fixture
def server():
    Handler.log = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def make_fetcher(max_bytes=2_000_000, timeout_s=5.0):
    client = httpx.Client()
    return Fetcher(client, max_bytes=max_bytes, timeout_s=timeout_s, robots=RobotsCache(client))


@pytest.mark.allow_hosts(["127.0.0.1"])
def test_fetch_limits(server):
    fetch = make_fetcher()
    page = fetch(f"{server}/page")
    assert page.error is None
    assert "readers do not block writers" in page.text
    assert page.extractor == "trafilatura"
    assert not page.truncated

    t0 = time.monotonic()
    endless = make_fetcher(max_bytes=200_000)(f"{server}/endless")
    assert endless.truncated is True
    assert endless.bytes == 200_000
    assert time.monotonic() - t0 < 5

    t0 = time.monotonic()
    slow = make_fetcher(timeout_s=1.0)(f"{server}/slow")
    assert slow.error == "TIMEOUT"
    assert time.monotonic() - t0 < 3

    binary = fetch(f"{server}/bin")
    assert binary.error == "CONTENT_TYPE"
    assert binary.text is None

    private = fetch(f"{server}/private")
    assert private.error == "ROBOTS_DISALLOWED"
    assert "/private" not in Handler.log

    assert fetch(f"{server}/404").error == "HTTP_404"

    pdf = fetch(f"{server}/pdf")
    assert pdf.extractor == "pypdf"
    assert "Hello quoteproof world" in pdf.text


@pytest.mark.allow_hosts(["127.0.0.1"])
def test_unreachable_does_not_raise():
    result = make_fetcher(timeout_s=2.0)("http://127.0.0.1:1/x")
    assert result.text is None
    assert result.error


def test_extract_text_plain_and_empty():
    assert extract_text(b"hello world", "text/plain; charset=utf-8") == ("hello world", "plain")
    assert extract_text(b"   ", "text/plain")[0] is None
