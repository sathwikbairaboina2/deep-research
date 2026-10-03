import re

from fakes import make_deps, scripted_llm
from hypothesis import given
from hypothesis import strategies as st

from deep_research.llm import ScriptedLLM
from deep_research.models import Limits
from deep_research.writer import fallback_report, footnote_notes, select_writer_input, write_report

CODES = ["QUOTE_NOT_FOUND", "UNKNOWN_SOURCE", "QUOTE_TOO_SHORT", "NO_CITATIONS"]


@given(
    st.lists(
        st.tuples(st.sampled_from(["verified", "rejected", None]), st.sampled_from(CODES)),
        max_size=30,
    )
)
def test_writer_input_only_verified(spec):
    claims, verdicts = [], []
    for i, (status, code) in enumerate(spec):
        cid = f"t1-r1-c{i}"
        claims.append({"claim_id": cid, "topic_id": "t1", "text": f"claim {i}", "citations": []})
        if status == "verified":
            verdicts.append({"claim_id": cid, "status": "verified", "reason": None})
        elif status == "rejected":
            verdicts.append({"claim_id": cid, "status": "rejected", "reason": code})
    chosen = select_writer_input(claims, verdicts)
    expected = [c for c, (s, _) in zip(claims, spec, strict=True) if s == "verified"]
    assert chosen == expected


TOPICS = [
    {"topic_id": "t1", "title": "good topic", "rationale": ""},
    {"topic_id": "t2", "title": "bad topic", "rationale": ""},
]


def _claims():
    claims = [
        {
            "claim_id": f"{t}-r1-c{i}",
            "topic_id": t,
            "text": f"{t} claim {i}",
            "citations": [{"source_id": "sha256:a", "quote": "some quote words here now ok"}],
        }
        for t in ("t1", "t2")
        for i in (1, 2)
    ]
    verdicts = [
        {"claim_id": c["claim_id"], "topic_id": c["topic_id"], "status": s, "reason": r}
        for c, (s, r) in zip(
            claims,
            [("verified", None)] * 2 + [("rejected", "QUOTE_NOT_FOUND")] * 2,
            strict=True,
        )
    ]
    sources = [{"source_id": "sha256:a", "url": "https://example.test/a"}]
    return claims, verdicts, sources


def _deps(tmp_path, write):
    return make_deps(tmp_path, scripted_llm(["x"], write=write), Limits())


def test_write_request_has_only_verified_ids(tmp_path):
    claims, verdicts, sources = _claims()
    deps = _deps(tmp_path, None)
    out = write_report(deps, "Q?", TOPICS, claims, verdicts, sources)
    req = deps.llm.calls[0]
    assert "t1-r1-c1" in req.user
    assert "t1-r1-c2" in req.user
    assert "t2-r1-c1" not in req.user
    assert "t2-r1-c2" not in req.user
    assert out["writer"] == "llm"
    assert out["report_markers"] == ["t1-r1-c1", "t1-r1-c2"]
    assert "[c:" not in out["report_md"]
    assert "[^1]: " in out["report_md"]
    assert "https://example.test/a" in out["report_md"]


def test_retry_path(tmp_path):
    claims, verdicts, sources = _claims()
    drafts = iter(["bad [c:nope]", "fine [c:t1-r1-c1]. also [c:t1-r1-c2]."])
    deps = _deps(tmp_path, lambda req: {"report_markdown": next(drafts)})
    out = write_report(deps, "Q?", TOPICS, claims, verdicts, sources)
    assert out["writer"] == "llm_retry"
    assert len(deps.llm.calls) == 2
    assert "UNKNOWN_MARKER" in deps.llm.calls[1].user


def test_fallback_path(tmp_path):
    claims, verdicts, sources = _claims()
    deps = _deps(tmp_path, lambda req: {"report_markdown": "bad [c:nope] and [c:nope]"})
    out = write_report(deps, "Q?", TOPICS, claims, verdicts, sources)
    assert out["writer"] == "fallback"
    assert len(deps.llm.calls) == 2
    assert out["report_markers"] == ["t1-r1-c1", "t1-r1-c2"]
    assert "[c:" not in out["report_md"]
    assert "## good topic" in out["report_md"]


def test_rejected_marker_in_draft_is_not_shipped(tmp_path):
    claims, verdicts, sources = _claims()
    deps = _deps(tmp_path, lambda req: {"report_markdown": "oops [c:t2-r1-c1]"})
    out = write_report(deps, "Q?", TOPICS, claims, verdicts, sources)
    assert out["writer"] == "fallback"
    assert "t2 claim" not in out["report_md"]


def test_writer_error_goes_to_fallback(tmp_path):
    claims, verdicts, sources = _claims()
    deps = _deps(tmp_path, lambda req: "not json at all")
    out = write_report(deps, "Q?", TOPICS, claims, verdicts, sources)
    assert out["writer"] == "fallback"


def test_no_verified_claims_no_llm_call(tmp_path):
    claims, verdicts, sources = _claims()
    verdicts = [{**v, "status": "rejected"} for v in verdicts]
    llm = ScriptedLLM({})
    deps = make_deps(tmp_path, llm)
    out = write_report(deps, "Q?", TOPICS, claims, verdicts, sources, caps_hit=["fetch"])
    assert out["writer"] == "none"
    assert llm.calls == []
    assert "No verified claims." in out["report_md"]
    assert "_Budget caps hit: fetch._" in out["report_md"]
    assert out["report_markers"] == []


def test_header_counts(tmp_path):
    claims, verdicts, sources = _claims()
    out = write_report(_deps(tmp_path, None), "Q?", TOPICS, claims, verdicts, sources)
    assert re.search(r"2 of 4 proposed claims verified; 2 rejected", out["report_md"])
    assert "## Under-covered topics" in out["report_md"]
    assert "- bad topic (0 verified)" in out["report_md"]


def test_helpers():
    claims, verdicts, sources = _claims()
    ver = select_writer_input(claims, verdicts)
    assert fallback_report("Q?", TOPICS, ver).count("[c:") == 2
    notes = footnote_notes(ver, sources)
    assert notes["t1-r1-c1"] == '"some quote words here now ok" - https://example.test/a'


def test_writer_transport_error_goes_to_fallback(tmp_path):
    from deep_research.llm import LLMError

    def boom(req):
        raise LLMError("timed out")

    claims, verdicts, sources = _claims()
    deps = _deps(tmp_path, boom)
    out = write_report(deps, "Q?", TOPICS, claims, verdicts, sources)
    assert out["writer"] == "fallback"
    assert "[c:" not in out["report_md"]
