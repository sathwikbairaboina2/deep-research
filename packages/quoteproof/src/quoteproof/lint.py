from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass

MARKER_RE = re.compile(r"\[c:([A-Za-z0-9][A-Za-z0-9_.-]*)\]")
OPEN_RE = re.compile(r"\[c:", re.IGNORECASE)
MALFORMED_MARKER = "MALFORMED_MARKER"
UNKNOWN_MARKER = "UNKNOWN_MARKER"
REJECTED_MARKER = "REJECTED_MARKER"
NO_MARKERS = "NO_MARKERS"


@dataclass(frozen=True)
class LintError:
    code: str
    marker: str  # the raw text (up to 40 chars from the "[c:" position)
    position: int


@dataclass(frozen=True)
class LintResult:
    ok: bool
    errors: tuple[LintError, ...]
    markers: tuple[str, ...]  # valid marker ids in order of first appearance, no duplicates


def lint_report(
    draft: str, verified_ids: Collection[str], known_ids: Collection[str]
) -> LintResult:
    errors: list[LintError] = []
    valid_starts = {m.start() for m in MARKER_RE.finditer(draft)}
    for m in OPEN_RE.finditer(draft):
        if m.start() not in valid_starts:
            errors.append(LintError(MALFORMED_MARKER, draft[m.start() : m.start() + 40], m.start()))
    markers: list[str] = []
    for m in MARKER_RE.finditer(draft):
        marker_id = m.group(1)
        if marker_id not in known_ids:
            errors.append(LintError(UNKNOWN_MARKER, m.group(0), m.start()))
        elif marker_id not in verified_ids:
            errors.append(LintError(REJECTED_MARKER, m.group(0), m.start()))
        elif marker_id not in markers:
            markers.append(marker_id)
    if not valid_starts:
        errors.append(LintError(NO_MARKERS, "", 0))
    errors.sort(key=lambda e: e.position)
    return LintResult(not errors, tuple(errors), tuple(markers))


def render_footnotes(draft: str, notes: Mapping[str, str]) -> str:
    numbers: dict[str, int] = {}

    def sub(m: re.Match[str]) -> str:
        marker_id = m.group(1)
        if marker_id not in notes:
            raise ValueError(f"no footnote text for marker {marker_id!r}")
        n = numbers.setdefault(marker_id, len(numbers) + 1)
        return f"[^{n}]"

    body = MARKER_RE.sub(sub, draft)
    if not numbers:
        return body
    lines = "\n".join(f"[^{n}]: {notes[i]}" for i, n in numbers.items())
    return body + "\n\n" + lines
