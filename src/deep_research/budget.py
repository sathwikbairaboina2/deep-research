from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import Literal

from deep_research.models import Limits


class BudgetExceeded(Exception):
    def __init__(self, kind: str, used: int | float, cap: int | float) -> None:
        super().__init__(f"{kind} cap reached: {used} of {cap}")
        self.kind = kind
        self.used = used
        self.cap = cap


class Budget:
    """Thread-safe per-run ledger. Searches and fetches are exact; tokens are reserved."""

    def __init__(
        self,
        limits: Limits,
        *,
        clock: Callable[[], float] = time.monotonic,
        sink: Callable[[str, int], None] | None = None,
        start: dict[str, int] | None = None,
    ) -> None:
        start = start or {}
        self.limits = limits
        self._clock = clock
        self._sink = sink
        self._lock = threading.Lock()
        self._t0 = clock()
        self._searches = start.get("searches", 0)
        self._fetches = start.get("fetches", 0)
        self._prompt = start.get("prompt_tokens", 0)
        self._completion = start.get("completion_tokens", 0)
        self._hit: set[str] = set()

    def _raise(self, kind: str, used: int | float, cap: int | float) -> None:
        self._hit.add(kind)
        raise BudgetExceeded(kind, used, cap)

    def _check_wall_locked(self) -> None:
        elapsed = self._clock() - self._t0
        if elapsed > self.limits.max_wall_s:
            self._raise("wall", round(elapsed, 3), self.limits.max_wall_s)

    def check_wall(self) -> None:
        with self._lock:
            self._check_wall_locked()

    def charge(self, kind: Literal["search", "fetch"], n: int = 1) -> None:
        with self._lock:
            self._check_wall_locked()
            if kind == "search":
                if self._searches + n > self.limits.max_searches:
                    self._raise("search", self._searches, self.limits.max_searches)
                self._searches += n
            else:
                if self._fetches + n > self.limits.max_fetches:
                    self._raise("fetch", self._fetches, self.limits.max_fetches)
                self._fetches += n
            if self._sink:
                self._sink(kind, n)

    def reserve_tokens(self, estimate: int) -> None:
        with self._lock:
            self._check_wall_locked()
            used = self._prompt + self._completion
            if used + estimate > self.limits.max_tokens:
                self._raise("tokens", used + estimate, self.limits.max_tokens)

    def record_tokens(self, prompt: int, completion: int) -> None:
        with self._lock:
            self._prompt += prompt
            self._completion += completion
            if self._sink:
                self._sink("prompt_tokens", prompt)
                self._sink("completion_tokens", completion)

    @property
    def exhausted(self) -> bool:
        with self._lock:
            return bool(self._hit)

    def caps_hit(self) -> list[str]:
        with self._lock:
            return sorted(self._hit)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "searches": self._searches,
                "fetches": self._fetches,
                "prompt_tokens": self._prompt,
                "completion_tokens": self._completion,
                "tokens": self._prompt + self._completion,
                "wall_s": round(self._clock() - self._t0, 3),
                "caps_hit": sorted(self._hit),
            }

    @staticmethod
    def estimate_tokens(system: str, user: str, num_predict: int) -> int:
        return math.ceil(len(system + user) / 3) + num_predict
