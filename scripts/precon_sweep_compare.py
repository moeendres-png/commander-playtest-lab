"""Compare two precon pod sweep reports pod by pod and say what changed.

A report from ``scripts/precon_pod_sweep.py`` has one row per pod. Comparing two reports
answers whether a pilot, bridge or pin change altered a game transcript, fixed a failure
or moved it into another family:

    python scripts/precon_sweep_compare.py before.json after.json

Pods are paired by name. A pod whose four decks changed is ``PLAN_MISMATCH`` rather than a
transcript change: the two rows did not play the same game, so their hashes are not
comparable. Exit code 0 means every paired pod is identical, 1 means something differs and
2 means an unusable report (one line on stderr, nothing on stdout).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from precon_pod_sweep import failure_family  # noqa: E402

CLASSES = (
    "IDENTICAL",
    "HASH_CHANGED",
    "FIXED",
    "BROKEN",
    "STILL_FAILED_SAME",
    "STILL_FAILED_OTHER",
    "PLAN_MISMATCH",
    "ONLY_BEFORE",
    "ONLY_AFTER",
)


@dataclass(frozen=True)
class PodDiff:
    """One pod's class and its rendered sides (``-`` when the pod is absent)."""

    pod: str
    kind: str
    before: str
    after: str


class ReportError(ValueError):
    """A report cannot be compared; guessing around a bad row would hide a broken sweep."""


def _index(report: object, label: str) -> dict[str, dict[str, Any]]:
    """Rows by pod name after checking every row is usable, else raise ``ReportError``."""
    if not isinstance(report, dict):
        raise ReportError(f"{label} report is not a JSON object")
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ReportError(f"{label} report has no rows list")
    index: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ReportError(f"{label} row {position} is not a JSON object")
        pod = row.get("pod")
        if not isinstance(pod, str) or not pod:
            raise ReportError(f"{label} row {position} has no pod")
        status = row.get("status")
        if status not in ("ok", "failed"):
            raise ReportError(f"{label} pod {pod} has status {status!r}, not ok or failed")
        if status == "ok" and not isinstance(row.get("semantic"), str):
            raise ReportError(f"{label} pod {pod} is ok without semantic")
        if pod in index:
            raise ReportError(f"{label} report repeats pod {pod}")
        index[pod] = row
    return index


def _side(row: dict[str, Any] | None) -> str:
    """How one report sees a pod: transcript prefix, failure family or absent."""
    if row is None:
        return "-"
    if row["status"] == "ok":
        return f"ok:{row['semantic'][:12]}"
    return failure_family(row.get("error"))


def _classify(before: dict[str, Any], after: dict[str, Any]) -> str:
    """The class of a pod present in both reports; never ``IDENTICAL`` for a failure."""
    if before.get("decks") != after.get("decks"):
        return "PLAN_MISMATCH"
    before_ok = before["status"] == "ok"
    after_ok = after["status"] == "ok"
    if before_ok and after_ok:
        return "IDENTICAL" if before["semantic"] == after["semantic"] else "HASH_CHANGED"
    if before_ok:
        return "BROKEN"
    if after_ok:
        return "FIXED"
    same_family = failure_family(before.get("error")) == failure_family(after.get("error"))
    return "STILL_FAILED_SAME" if same_family else "STILL_FAILED_OTHER"


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> list[PodDiff]:
    """Classify every pod of two reports, sorted by pod name; raises on unusable input."""
    old = _index(before, "before")
    new = _index(after, "after")
    diffs: list[PodDiff] = []
    for pod in sorted(set(old) | set(new)):
        old_row = old.get(pod)
        new_row = new.get(pod)
        if old_row is None:
            kind = "ONLY_AFTER"
        elif new_row is None:
            kind = "ONLY_BEFORE"
        else:
            kind = _classify(old_row, new_row)
        diffs.append(PodDiff(pod=pod, kind=kind, before=_side(old_row), after=_side(new_row)))
    return diffs


def _header(label: str, report: Mapping[str, Any]) -> str:
    jar = report.get("jar")
    name = Path(jar).name if isinstance(jar, str) and jar else "?"
    return (
        f"{label} jar={name} plan_seed={report.get('plan_seed')} "
        f"game_seed={report.get('game_seed')}"
    )


def _families(rows: Mapping[str, dict[str, Any]]) -> dict[str, int]:
    """Failed rows per family, keys sorted so the line is stable."""
    counts = Counter(
        failure_family(row.get("error")) for row in rows.values() if row["status"] == "failed"
    )
    return dict(sorted(counts.items()))


def render(before: dict[str, Any], after: dict[str, Any], diffs: Sequence[PodDiff]) -> str:
    """The plain-text comparison: headers, seed warning, counts, changed pods, families."""
    differing = [
        f"{key} {before.get(key)} -> {after.get(key)}"
        for key in ("plan_seed", "game_seed")
        if before.get(key) != after.get(key)
    ]
    counts = Counter(diff.kind for diff in diffs)
    lines = [
        _header("before", before),
        _header("after", after),
        "counts " + " ".join(f"{kind}={counts[kind]}" for kind in CLASSES),
    ]
    if differing:
        lines.insert(2, "WARNING seeds differ: " + "; ".join(differing))
    lines.extend(
        f"{diff.kind} {diff.pod} {diff.before} -> {diff.after}"
        for diff in diffs
        if diff.kind != "IDENTICAL"
    )
    lines.append(
        f"families before {_families(_index(before, 'before'))} "
        f"after {_families(_index(after, 'after'))}"
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: 0 all identical, 1 any difference, 2 unusable input (stderr only)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print(
            "usage: python scripts/precon_sweep_compare.py BEFORE.json AFTER.json", file=sys.stderr
        )
        return 2
    reports: list[Any] = []
    for raw in args:
        try:
            reports.append(json.loads(Path(raw).read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            message = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            print(f"unusable report {raw}: {message}", file=sys.stderr)
            return 2
    before, after = reports
    try:
        diffs = compare_reports(before, after)
    except ReportError as exc:
        print(f"unusable report: {exc}", file=sys.stderr)
        return 2
    print(render(before, after, diffs))
    return 0 if all(diff.kind == "IDENTICAL" for diff in diffs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
