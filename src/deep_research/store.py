from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from deep_research.models import FetchResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS texts (
    source_id TEXT PRIMARY KEY,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    run_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    http_status INTEGER,
    content_type TEXT,
    bytes INTEGER,
    extractor TEXT,
    PRIMARY KEY (run_id, canonical_url)
);
CREATE TABLE IF NOT EXISTS budget_events (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    kind TEXT NOT NULL,
    amount INTEGER NOT NULL,
    at TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
"""

_TOTAL_KEYS = {
    "search": "searches",
    "fetch": "fetches",
    "prompt_tokens": "prompt_tokens",
    "completion_tokens": "completion_tokens",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PageStore:
    """Content-addressed page texts plus per-run source and budget rows (SQLite, WAL)."""

    def __init__(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(_SCHEMA)
            self._db.commit()

    def put_source(self, run_id: str, fetch: FetchResult) -> str:
        if fetch.text is None:
            raise ValueError("cannot store a fetch without text")
        source_id = "sha256:" + hashlib.sha256(fetch.text.encode()).hexdigest()
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO texts (source_id, text) VALUES (?, ?)",
                (source_id, fetch.text),
            )
            self._db.execute(
                "INSERT OR REPLACE INTO sources (run_id, canonical_url, source_id, url, fetched_at,"
                " http_status, content_type, bytes, extractor) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    fetch.canonical_url,
                    source_id,
                    fetch.final_url or fetch.url,
                    _now(),
                    fetch.status,
                    fetch.content_type,
                    fetch.bytes,
                    fetch.extractor,
                ),
            )
            self._db.commit()
        return source_id

    def get_by_url(self, run_id: str, canonical_url: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM sources WHERE run_id = ? AND canonical_url = ?",
                (run_id, canonical_url),
            ).fetchone()
        return dict(row) if row else None

    def texts_for_run(self, run_id: str) -> dict[str, str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT DISTINCT t.source_id, t.text FROM texts t"
                " JOIN sources s ON s.source_id = t.source_id WHERE s.run_id = ?",
                (run_id,),
            ).fetchall()
        return {r["source_id"]: r["text"] for r in rows}

    def source_ids_for_run(self, run_id: str) -> set[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT source_id FROM sources WHERE run_id = ?", (run_id,)
            ).fetchall()
        return {r["source_id"] for r in rows}

    def sources_for_run(self, run_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM sources WHERE run_id = ? ORDER BY fetched_at, canonical_url",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_text(self, source_id: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT text FROM texts WHERE source_id = ?", (source_id,)
            ).fetchone()
        return row["text"] if row else None

    def add_budget_event(self, run_id: str, kind: str, amount: int) -> None:
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM budget_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            self._db.execute(
                "INSERT INTO budget_events (run_id, seq, kind, amount, at) VALUES (?,?,?,?,?)",
                (run_id, row["n"], kind, amount, _now()),
            )
            self._db.commit()

    def budget_totals(self, run_id: str) -> dict[str, int]:
        totals = dict.fromkeys(_TOTAL_KEYS.values(), 0)
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, SUM(amount) AS total FROM budget_events WHERE run_id = ?"
                " GROUP BY kind",
                (run_id,),
            ).fetchall()
        for r in rows:
            key = _TOTAL_KEYS.get(r["kind"])
            if key:
                totals[key] = int(r["total"])
        return totals

    def close(self) -> None:
        with self._lock:
            self._db.close()
