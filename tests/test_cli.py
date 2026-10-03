import sqlite3

from fakes import FakeFetch, FakeSearch, scripted_llm

from deep_research.cli import main


def factory():
    return {
        "llm": scripted_llm(["good one", "good two", "bad three"]),
        "search": FakeSearch(),
        "fetch": FakeFetch(),
    }


def run_cli(tmp_path, capsys, *args):
    code = main([*args, "--runs-dir", str(tmp_path / "runs")], deps_factory=factory)
    return code, capsys.readouterr()


def test_run_show_verify(tmp_path, capsys):
    code, out = run_cli(
        tmp_path, capsys, "run", "What is a widget?", "--topics", "3", "--rounds", "1",
        "--run-id", "r1",
    )  # fmt: skip
    assert code == 0
    assert "run_id: r1" in out.out
    assert "verified 4/6" in out.out

    code, out = run_cli(tmp_path, capsys, "show", "r1")
    assert code == 0
    assert "t1-r1-c1" in out.out
    assert "t3-r1-c1" in out.out

    code, out = run_cli(tmp_path, capsys, "show", "r1", "--rejected")
    assert code == 0
    assert "t3-r1-c1" in out.out
    assert "QUOTE_NOT_FOUND" in out.out
    assert "quote:" in out.out
    assert "t1-r1-c1" not in out.out

    code, out = run_cli(tmp_path, capsys, "verify", "r1")
    assert code == 0
    assert "unverifiable: 0" in out.out
    assert "claims: 6  re-verified same: 6" in out.out


def test_verify_detects_tampering(tmp_path, capsys):
    run_cli(tmp_path, capsys, "run", "Q?", "--topics", "3", "--rounds", "1", "--run-id", "r1")
    db = sqlite3.connect(tmp_path / "runs" / "store.sqlite")
    db.execute("UPDATE texts SET text = 'x'")
    db.commit()
    db.close()
    code, out = run_cli(tmp_path, capsys, "verify", "r1")
    assert code == 1
    assert "unverifiable:" in out.out
    assert "unverifiable: 0" not in out.out


def test_usage_errors(tmp_path, capsys):
    assert main(["bogus"]) == 2
    assert main([]) == 2
    assert main(["run", "q", "--max-searches", "0"]) == 2
    assert main(["show", "nope", "--runs-dir", str(tmp_path)]) == 2
    capsys.readouterr()
