import contextlib
import threading

import pytest

from deep_research.budget import Budget, BudgetExceeded
from deep_research.models import Limits


def _hammer(budget, kind, threads=16, per=10):
    barrier = threading.Barrier(threads)

    def work():
        barrier.wait()
        for _ in range(per):
            with contextlib.suppress(BudgetExceeded):
                budget.charge(kind)

    ts = [threading.Thread(target=work) for _ in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()


def test_budget_hard_caps():
    events = []
    lock = threading.Lock()

    def sink(kind, n):
        with lock:
            events.append((kind, n))

    b = Budget(Limits(max_searches=5, max_fetches=7), sink=sink)
    _hammer(b, "search")
    snap = b.snapshot()
    assert snap["searches"] == 5
    assert [e for e in events if e[0] == "search"] == [("search", 1)] * 5
    assert b.exhausted
    assert b.caps_hit() == ["search"]

    _hammer(b, "fetch")
    assert b.snapshot()["fetches"] == 7
    assert sum(1 for e in events if e[0] == "fetch") == 7
    assert b.caps_hit() == ["fetch", "search"]


def test_tokens_reserved_then_recorded():
    b = Budget(Limits(max_tokens=1000))
    b.reserve_tokens(600)
    b.record_tokens(400, 200)
    with pytest.raises(BudgetExceeded):
        b.reserve_tokens(401)
    b.reserve_tokens(400)
    assert b.snapshot()["tokens"] == 600
    assert b.caps_hit() == ["tokens"]


def test_wall_clock():
    times = iter([0, 0, 901])
    b = Budget(Limits(max_wall_s=900), clock=lambda: next(times))
    b.charge("search")
    with pytest.raises(BudgetExceeded) as err:
        b.charge("search")
    assert err.value.kind == "wall"


def test_resume_seed():
    b = Budget(Limits(max_searches=5), start={"searches": 5})
    with pytest.raises(BudgetExceeded):
        b.charge("search")


def test_estimate():
    assert Budget.estimate_tokens("ab", "cde", 10) == 12
