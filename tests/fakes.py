"""Shared test helpers: tiny PDF builder plus fake search, fetch and scripted LLM."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from urllib.parse import urlsplit

from deep_research.budget import Budget
from deep_research.deps import Deps
from deep_research.llm import LLMRequest, ScriptedLLM
from deep_research.models import FetchResult, Limits, SearchHit
from deep_research.store import PageStore
from deep_research.urls import canonical_url


def make_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "x"


class FakeSearch:
    """Returns example.test URLs derived from the query; counts calls under a lock."""

    def __init__(self, results: dict[str, list[str]] | Callable | None = None) -> None:
        self.results = results
        self.calls = 0
        self.queries: list[str] = []
        self._lock = threading.Lock()

    def __call__(self, query: str, max_results: int) -> list[SearchHit]:
        with self._lock:
            self.calls += 1
            self.queries.append(query)
        if callable(self.results):
            urls = self.results(query, max_results)
        elif self.results is not None:
            urls = self.results.get(query, [])
        else:
            slug = _slug(query)
            urls = [f"https://example.test/{slug}/{n}" for n in range(1, max_results + 1)]
        return [
            SearchHit(url=u, canonical_url=canonical_url(u), title=u, snippet="", engine="fake")
            for u in urls[:max_results]
        ]


def default_page(url: str) -> str:
    path = urlsplit(url).path
    return "\n".join(
        f"Sentence {k} of the page at {path} states that widget subsystem number {k} "
        "keeps its own durable state."
        for k in range(1, 7)
    )


class FakeFetch:
    """Returns pages without a network. Records every call, concurrency and crash points."""

    def __init__(
        self,
        pages: dict[str, str] | Callable[[str], str] | None = None,
        *,
        fail_on_call: int | None = None,
        delay: float = 0.0,
    ) -> None:
        self.pages = pages
        self.fail_on_call = fail_on_call
        self.delay = delay
        self.calls: list[str] = []
        self.ok_calls: list[str] = []
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def __call__(self, url: str) -> FetchResult:
        with self._lock:
            self.calls.append(url)
            n = len(self.calls)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.fail_on_call is not None and n == self.fail_on_call:
                raise RuntimeError("simulated crash")
            if self.delay:
                time.sleep(self.delay)
            if callable(self.pages):
                text = self.pages(url)
            elif self.pages is not None:
                text = self.pages[url]
            else:
                text = default_page(url)
            with self._lock:
                self.ok_calls.append(canonical_url(url))
            return FetchResult(
                url=url,
                final_url=url,
                canonical_url=canonical_url(url),
                status=200,
                content_type="text/html",
                bytes=len(text),
                truncated=False,
                text=text,
                extractor="fake",
                error=None,
            )
        finally:
            with self._lock:
                self.active -= 1


_SOURCE_RE = re.compile(r"\[(S\d+)\] (\S+)\n<<<\n(.*?)\n>>>", re.DOTALL)
_CLAIM_LINE_RE = re.compile(r"^\[c:([^\]]+)\] (.*)$", re.MULTILINE)


def scripted_llm(
    topics: list[str],
    *,
    claims_per_topic: int = 2,
    write: Callable[[LLMRequest], str | dict] | None = None,
) -> ScriptedLLM:
    """A ScriptedLLM for the whole pipeline.

    Topics whose title contains "bad" get paraphrased (unfindable) quotes; others get a real
    sentence copied from the source text.
    """

    def plan(req):
        return {"topics": [{"title": t, "rationale": f"covers {t}"} for t in topics]}

    def queries(req):
        title = req.user.split("Sub-topic: ", 1)[1].strip()
        return {"queries": [f"{title} overview", f"{title} details"]}

    def extract(req):
        title = req.user.split("Sub-topic: ", 1)[1].split("\n", 1)[0].strip()
        sources = _SOURCE_RE.findall(req.user)
        bad = "bad" in title.lower()
        claims = []
        for i in range(claims_per_topic):
            label, _url, text = sources[i % len(sources)]
            lines = [x for x in text.splitlines() if len(x.split()) >= 8]
            line = lines[i % len(lines)]
            quote = line.replace("states that", "claims that") if bad else line
            claims.append(
                {"text": f"{title} fact {i + 1}", "citations": [{"source": label, "quote": quote}]}
            )
        return {"claims": claims}

    def default_write(req):
        found = _CLAIM_LINE_RE.findall(req.user)
        body = " ".join(f"{text}. [c:{cid}]" for cid, text in found)
        return {"report_markdown": body}

    return ScriptedLLM(
        {"plan": plan, "queries": queries, "extract": extract, "write": write or default_write}
    )


def make_deps(tmp_path, llm=None, limits=None, search=None, fetch=None, run_id="r1"):
    limits = limits or Limits()
    store = PageStore(tmp_path / "s.sqlite")
    return Deps(
        llm=llm or scripted_llm(["alpha", "beta"]),
        search=search or FakeSearch(),
        fetch=fetch or FakeFetch(),
        store=store,
        budget=Budget(limits, sink=lambda k, n: store.add_budget_event(run_id, k, n)),
        limits=limits,
        run_id=run_id,
    )
