"""Read-only stdlib web view of finished runs. GET only, every dynamic string escaped."""

from __future__ import annotations

import html
import json
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quoteproof import normalize

ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

CSS = """
:root{--bg:#fafaf8;--fg:#1c1c1a;--muted:#6b6b66;--line:#dddcd6;--accent:#1f5fbf;--mark:#ffe58a}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#e8e8e3;--muted:#9a9a93;
--line:#34342f;--accent:#7fb0ff;--mark:#6b5a10}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:16px}
a{color:var(--accent)} nav{margin:0 0 16px;display:flex;gap:16px;flex-wrap:wrap}
h1{font-size:1.5rem;line-height:1.25} h2{font-size:1.2rem;margin-top:1.6em}
table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.muted{color:var(--muted)} mark{background:var(--mark);color:inherit;padding:0 2px}
pre{white-space:pre-wrap;word-break:break-word;border:1px solid var(--line);padding:12px}
code{font-family:ui-monospace,monospace;font-size:.9em}
"""


def page(title: str, body: str) -> bytes:
    doc = (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )
    return doc.encode("utf-8")


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w])_(.+?)_(?![\w])", r"<em>\1</em>", text)
    return re.sub(r"\[\^(\d+)\]", r'<sup><a href="#fn-\1">\1</a></sup>', text)


def markdown_to_html(md: str) -> str:
    """Tiny converter: headings, paragraphs, bullet lists, footnotes."""
    out: list[str] = []
    notes: list[str] = []
    bullets: list[str] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()
        if bullets:
            out.append("<ul>" + "".join(f"<li>{_inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for line in md.splitlines():
        stripped = line.strip()
        note = re.match(r"^\[\^(\d+)\]:\s*(.*)$", stripped)
        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if note:
            flush()
            notes.append(f'<li id="fn-{note.group(1)}">{_inline(note.group(2))}</li>')
        elif heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif stripped.startswith("- "):
            if para:
                flush()
            bullets.append(stripped[2:])
        elif not stripped:
            flush()
        else:
            if bullets:
                flush()
            para.append(stripped)
    flush()
    if notes:
        out.append("<h2>Sources</h2><ol>" + "".join(notes) + "</ol>")
    return "\n".join(out)


def highlight(text: str, quote: str, verdict_citation: dict | None) -> tuple[str, str]:
    """Return (html, note). Tries the raw text first, then the normalized text by offset."""
    words = quote.split()
    if words:
        pattern = r"\s+".join(re.escape(w) for w in words)
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (
                html.escape(text[: m.start()])
                + "<mark>"
                + html.escape(m.group())
                + "</mark>"
                + html.escape(text[m.end() :]),
                "",
            )
    norm = normalize(text)
    offset = (verdict_citation or {}).get("offset")
    nq = normalize(quote)
    if offset is not None and norm[offset : offset + len(nq)] == nq:
        return (
            html.escape(norm[:offset])
            + "<mark>"
            + html.escape(norm[offset : offset + len(nq)])
            + "</mark>"
            + html.escape(norm[offset + len(nq) :]),
            "Shown normalized (NORM_V1): the raw text differs from the quote in punctuation.",
        )
    return html.escape(text), "The quote was not found in this source."


def make_server(
    runs_dir: str | Path, host: str = "127.0.0.1", port: int = 5301
) -> ThreadingHTTPServer:
    root = Path(runs_dir)

    def load_run(run_id: str) -> dict | None:
        if not ID_RE.match(run_id):
            return None
        path = root / run_id / "run.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def source_text(source_id: str) -> str | None:
        db_path = root / "store.sqlite"
        if not db_path.is_file():
            return None
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT text FROM texts WHERE source_id = ?", (source_id,)
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def row_html(r: dict) -> str:
        rid = html.escape(r["run_id"])
        done = sum(1 for v in r["verdicts"] if v["status"] == "verified")
        return (
            f'<tr><td><a href="/runs/{rid}">{rid}</a></td>'
            f"<td>{html.escape(r['question'])}</td><td>{html.escape(r['status'])}</td>"
            f"<td>{done}/{len(r['claims'])}</td></tr>"
        )

    def runs_list() -> bytes:
        runs = []
        for path in root.glob("*/run.json"):
            try:
                runs.append(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                continue
        runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
        rows = "".join(row_html(r) for r in runs)
        table = (
            "<table><tr><th>run</th><th>question</th><th>status</th><th>verified</th></tr>"
            f"{rows}</table>"
            if runs
            else '<p class="muted">No runs yet.</p>'
        )
        return page("Runs", f"<h1>Runs</h1>{table}")

    def nav(run_id: str) -> str:
        rid = html.escape(run_id)
        return (
            f'<nav><a href="/">All runs</a><a href="/runs/{rid}">Report</a>'
            f'<a href="/runs/{rid}/rejected">Rejected claims</a></nav>'
        )

    def report(run_id: str, run: dict) -> bytes:
        md = (root / run_id / "report.md").read_text(encoding="utf-8")
        return page(run["question"], nav(run_id) + markdown_to_html(md))

    def rejected(run_id: str, run: dict) -> bytes:
        claims = {c["claim_id"]: c for c in run["claims"]}
        src = {s["source_id"]: s["url"] for s in run["sources"]}
        rows = []
        for v in run["verdicts"]:
            if v["status"] != "rejected":
                continue
            claim = claims.get(v["claim_id"], {"text": "", "citations": []})
            cites = claim["citations"][:1] or [{"quote": "", "source_id": ""}]
            quote = html.escape(cites[0]["quote"])
            url = html.escape(src.get(cites[0]["source_id"], cites[0]["source_id"]))
            reason = html.escape(v["reason"] or "")
            rows.append(
                f"<tr><td>{html.escape(v['claim_id'])}</td><td><code>{reason}</code></td>"
                f"<td>{html.escape(claim['text'])}</td><td>{quote}</td><td>{url}</td></tr>"
            )
        body = (
            "<table><tr><th>claim</th><th>reason</th><th>text</th><th>quote</th><th>source</th></tr>"
            + "".join(rows)
            + "</table>"
            if rows
            else '<p class="muted">No rejected claims.</p>'
        )
        return page("Rejected claims", nav(run_id) + "<h1>Rejected claims</h1>" + body)

    def source(run_id: str, run: dict, query: dict) -> bytes | None:
        claim_id = (query.get("claim") or [""])[0]
        try:
            index = int((query.get("i") or ["0"])[0])
        except ValueError:
            return None
        claim = next((c for c in run["claims"] if c["claim_id"] == claim_id), None)
        if claim is None or not 0 <= index < len(claim["citations"]):
            return None
        cite = claim["citations"][index]
        text = source_text(cite["source_id"])
        if text is None:
            return None
        verdict = next((v for v in run["verdicts"] if v["claim_id"] == claim_id), None)
        vc = verdict["citations"][index] if verdict and index < len(verdict["citations"]) else None
        body_html, note = highlight(text, cite["quote"], vc)
        src_url = next(
            (s["url"] for s in run["sources"] if s["source_id"] == cite["source_id"]), ""
        )
        return page(
            f"Source for {claim_id}",
            nav(run_id)
            + f"<h1>Source for {html.escape(claim_id)}</h1>"
            + f'<p class="muted">{html.escape(src_url)}</p>'
            + (f'<p class="muted">{html.escape(note)}</p>' if note else "")
            + f"<pre>{body_html}</pre>",
        )

    class Handler(BaseHTTPRequestHandler):
        server_version = "deep-research"

        def log_message(self, *args) -> None:
            pass

        def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _not_found(self) -> None:
            self._send(404, page("Not found", "<h1>Not found</h1><p><a href='/'>All runs</a></p>"))

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            segs = [s for s in parts.path.split("/") if s]
            if not segs:
                return self._send(200, runs_list())
            if segs[0] != "runs" or len(segs) not in (2, 3):
                return self._not_found()
            run = load_run(segs[1])
            if run is None:
                return self._not_found()
            run_id = segs[1]
            if len(segs) == 2:
                return self._send(200, report(run_id, run))
            if segs[2] == "rejected":
                return self._send(200, rejected(run_id, run))
            if segs[2] == "source":
                body = source(run_id, run, parse_qs(parts.query))
                return self._send(200, body) if body else self._not_found()
            return self._not_found()

        def _method_not_allowed(self) -> None:
            self._send(405, page("Method not allowed", "<h1>Read-only</h1>"))

        do_POST = do_PUT = do_DELETE = do_PATCH = _method_not_allowed

    return ThreadingHTTPServer((host, port), Handler)


def serve_main(host: str, port: int, runs_dir: str | Path) -> int:
    server = make_server(runs_dir, host, port)
    print(f"serving http://{host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
