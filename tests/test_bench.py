import random
from pathlib import Path

import pytest

from deep_research.bench import MUTATORS, html_sentences, run_bench, summary_line
from deep_research.cli import main

PAGES = Path(__file__).parent / "fixtures" / "pages"


def test_deterministic():
    assert run_bench(PAGES, per_page=10) == run_bench(PAGES, per_page=10)


def test_structure_and_sanity():
    result = run_bench(PAGES, per_page=20)
    assert {"bench", "seed", "per_page", "norm", "corpus", "genuine", "mutated", "versions"} <= set(
        result
    )
    assert len(result["corpus"]) == 5
    assert set(result["mutated"]["by_kind"]) == set(MUTATORS)
    # sanity bounds only; the README quotes bench/results/latest.json
    assert result["genuine"]["rate"] > 0.9
    assert result["mutated"]["rate"] > 0.95
    assert "genuine accepted" in summary_line(result)


@pytest.mark.parametrize("kind", sorted(MUTATORS))
def test_mutations_change_the_string(kind):
    quote = "The 3 readers do not block writers because the log keeps every change"
    out = MUTATORS[kind](quote, random.Random(1))
    assert out is None or out != quote


def test_change_number_skips_without_digits():
    assert MUTATORS["change_number"]("no digits in this sentence at all", random.Random(1)) is None


def test_html_sentences_skip_scripts_and_filter_length():
    html = (
        "<script>var x = 'one two three four five six seven eight nine.';</script>"
        "<p>Short one.</p><p>This sentence has exactly nine words in it, honest. "
        "And another sentence that is long enough to keep around.</p>"
    )
    sents = html_sentences(html)
    assert all("var x" not in s for s in sents)
    assert "Short one." not in sents
    assert any(s.startswith("This sentence has exactly nine words") for s in sents)


def test_genuine_wal_quote_accepted():
    html = (PAGES / "wal.html").read_text(encoding="utf-8")
    sents = html_sentences(html)
    assert any("readers do not block writers" in s for s in sents)


def test_cli_bench_out_and_check(tmp_path, capsys):
    out = tmp_path / "latest.json"
    assert main(["bench", "--pages", str(PAGES), "--per-page", "5", "--out", str(out)]) == 0
    assert main(["bench", "--pages", str(PAGES), "--per-page", "5", "--check", str(out)]) == 0
    assert main(["bench", "--pages", str(PAGES), "--per-page", "6", "--check", str(out)]) == 1
    assert "FAILED" in capsys.readouterr().out
