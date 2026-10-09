#!/usr/bin/env python3
"""Compare a serial and a shadow PB-03 packet for the #479 E2 overlap experiment.

The shadow workflow (``.github/workflows/pb03-shadow-parallel.yml``) runs the
same pinned producers with ``PB03_SHADOW_PARALLEL_FORGE_NATIVE=1``. This script
compares the two packets' semantic output and ignores everything that
legitimately differs between two runs: timestamps, durations and run ids.

Compared, per candidate:
- the AF00-AF11 gate verdicts and blocking-row sets;
- the FULL107 outcome counts;
- the exit state of every FULL107 fixture row;
- every native receipt's return code, test/failure/error/skip counts and
  declared/executed/unexecuted class identities and per-class outcome counts.

Both inputs must contain all 12 AF gates, 107 distinct FULL107 rows and all
four native candidate/group receipts. Equal omissions, duplicate identities,
malformed fields and internally inconsistent row counts fail closed.

The five raw XMage-only phase documents (PB03_RUNTIME_EXECUTION.json,
MIDGAME_ROW_EXECUTIONS.json, KNOWLEDGE_PROJECTION_EXECUTIONS.json,
MIDGAME_REPLAY_TWIN_EXECUTIONS.json, ACTUAL_CARD_CAMPAIGN_XMAGE.json) are not
read directly: a divergence there is only a difference when it reaches the
derived AF00-AF11 verdicts or the FULL107 rows, which are compared above.

One line is printed per difference and the exit code is non-zero when any
difference exists. This comparison is a shadow-experiment control, never
qualification credit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

CANDIDATES: tuple[str, ...] = ("xmage", "forge")
# Mirrors NATIVE_SUITE_BINDING[candidate]["classes"] in the current-boundary
# runner. Keep in sync without importing its environment-dependent module setup.
NATIVE_GROUPS: tuple[str, ...] = ("direct", "mechanism")


def _strings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and item for item in value)
        and len(set(value)) == len(value)
    )


def _count(value: Any) -> bool:
    return type(value) is int and value >= 0


def _source(root: Path) -> dict[str, str] | None:
    doc = _read_json(root / "EPOCH_IDENTITY.json")
    source = doc.get("producing_source") if isinstance(doc, dict) else None
    if not isinstance(source, dict) or not isinstance(source.get("repository"), str):
        return None
    if not source["repository"] or not all(
        isinstance(source.get(field), str) and re.fullmatch(r"[0-9a-f]{40}", source[field])
        for field in ("commit", "tree")
    ):
        return None
    return {field: source[field] for field in ("repository", "commit", "tree")}


def _packet_errors(root: Path, side: str) -> list[str]:
    """Validate completeness before reducing lists to keyed comparison maps."""
    errors: list[str] = []

    def invalid(label: str, reason: str) -> None:
        errors.append(f"{side} {label}: invalid comparison input: {reason}")

    source = _source(root)
    if source is None:
        invalid("epoch identity", "missing or malformed producing source")
    for candidate in CANDIDATES:
        label = f"{candidate} AF00-AF11"
        doc = _read_json(root / f"AF00_AF11_{candidate.upper()}.json")
        if doc is None:
            errors.append(f"{label}: document missing from the {side} packet")
        elif not isinstance(doc, dict) or doc.get("candidate") != candidate:
            invalid(label, "expected a candidate-bound object")
        else:
            gates = doc.get("gates")
            if not isinstance(gates, list) or len(gates) != 12:
                invalid(label, "exactly 12 gates are required")
            elif not all(
                isinstance(gate, dict)
                and isinstance(gate.get("gate"), str)
                and isinstance(gate.get("verdict"), str)
                and bool(gate["verdict"])
                and _strings(gate.get("blocking_rows"))
                for gate in gates
            ):
                invalid(label, "malformed gate identity, verdict or blocking rows")
            elif {gate["gate"] for gate in gates} != {f"AF{i:02d}" for i in range(12)}:
                invalid(label, "missing or duplicate AF00-AF11 gate identities")

        label = f"{candidate} FULL107"
        doc = _read_json(root / f"FULL107_{candidate.upper()}_RESULTS.json")
        if doc is None:
            errors.append(f"{label}: document missing from the {side} packet")
            continue
        if not isinstance(doc, dict) or doc.get("candidate") != candidate:
            invalid(label, "expected a candidate-bound object")
            continue
        rows, counts = doc.get("rows"), doc.get("counts")
        if type(doc.get("total")) is not int or doc["total"] != 107:
            invalid(label, "total must be exactly 107")
        if not isinstance(rows, list) or len(rows) != 107:
            invalid(label, "exactly 107 rows are required")
            continue
        if not all(
            isinstance(row, dict)
            and isinstance(row.get("fixture_id"), str)
            and bool(row["fixture_id"])
            and isinstance(row.get("exit_state"), str)
            and bool(row["exit_state"])
            for row in rows
        ):
            invalid(label, "malformed fixture identity or exit state")
            continue
        if len({row["fixture_id"] for row in rows}) != 107:
            invalid(label, "duplicate fixture identities")
        if (
            not isinstance(counts, dict)
            or not counts
            or not all(
                isinstance(key, str) and key and _count(value) for key, value in counts.items()
            )
        ):
            invalid(label, "malformed outcome counts")
        elif dict(Counter(row["exit_state"] for row in rows)) != {
            key: value for key, value in counts.items() if value
        }:
            invalid(label, "outcome counts disagree with the 107 row states")

    seen: set[tuple[str, str]] = set()
    for path in sorted((root / "receipts").glob("native-*.json")):
        doc = _read_json(path)
        label = f"native receipt {path.name}"
        if not isinstance(doc, dict):
            invalid(label, "expected an object")
            continue
        candidate, group = doc.get("candidate"), doc.get("group")
        if candidate not in CANDIDATES or group not in NATIVE_GROUPS:
            invalid(label, "unknown candidate/group identity")
            continue
        key = (candidate, group)
        if key in seen:
            invalid(label, "duplicate candidate/group identity")
        seen.add(key)
        if type(doc.get("returncode")) is not int or not all(
            _count(doc.get(field)) for field in ("tests", "failed", "errors", "skipped")
        ):
            invalid(label, "malformed native return code or outcome counts")
        classes, executed, unexecuted = (
            doc.get("classes"),
            doc.get("executed_classes"),
            doc.get("unexecuted_classes"),
        )
        if not _strings(classes) or not classes or not _strings(unexecuted):
            invalid(label, "missing, malformed or duplicate declared/unexecuted classes")
            continue
        if (
            not isinstance(executed, dict)
            or set(executed) != set(classes)
            or not set(unexecuted) <= set(classes)
        ):
            invalid(
                label,
                "every declared class must have an observation; unexecuted classes must be declared",
            )
            continue
        for name, counts in executed.items():
            fields = ("tests", "failures", "errors", "skipped")
            if not isinstance(counts, dict):
                invalid(label, "malformed per-class execution counts")
            elif all(_count(counts.get(field)) for field in fields):
                # observed_class_executions also calls failed, all-skipped and
                # zero-case classes unexecuted, while retaining their counters.
                missing = (
                    counts["tests"] == 0
                    or counts["skipped"] >= counts["tests"]
                    or bool(counts["failures"] or counts["errors"])
                )
                if (name in unexecuted) != missing:
                    invalid(label, "unexecuted identity inconsistent with class outcomes")
            elif not (
                name in unexecuted
                and not any(field in counts for field in fields)
                and _count(counts.get("fresh_reports_scanned"))
                and isinstance(counts.get("unparseable_reports"), list)
                and all(isinstance(report, str) for report in counts["unparseable_reports"])
            ):
                # No fresh case/report is represented by scan diagnostics in
                # the real producer's observation map, not by a missing entry.
                invalid(label, "malformed per-class execution counts")
    required = {(candidate, group) for candidate in CANDIDATES for group in NATIVE_GROUPS}
    for candidate, group in sorted(required - seen):
        invalid(f"native receipt {candidate}:{group}", "required group is missing")
    return errors


def _read_json(path: Path) -> Any:
    """Read a packet document; a missing file is None, malformed JSON fails closed."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit(
            f"{path}: unreadable JSON ({exc}); the two packets cannot be compared"
        ) from exc


def _missing(label: str, serial: Any, shadow: Any) -> str:
    if serial is None and shadow is None:
        return f"{label}: document absent from both packets; nothing could be compared"
    side = "serial" if serial is None else "shadow"
    return f"{label}: document missing from the {side} packet"


def _af_state(root: Path, candidate: str) -> dict[str, dict[str, Any]] | None:
    document = _read_json(root / f"AF00_AF11_{candidate.upper()}.json")
    if document is None or not isinstance(document.get("gates"), list):
        return None
    state: dict[str, dict[str, Any]] = {}
    for gate in document["gates"]:
        if not isinstance(gate, dict):
            continue
        state[str(gate.get("gate"))] = {
            "verdict": gate.get("verdict"),
            "blocking_rows": sorted(str(row) for row in gate.get("blocking_rows") or ()),
        }
    return state


def _full107_state(root: Path, candidate: str) -> dict[str, Any] | None:
    document = _read_json(root / f"FULL107_{candidate.upper()}_RESULTS.json")
    if document is None:
        return None
    rows = {
        str(row.get("fixture_id")): row.get("exit_state")
        for row in document.get("rows") or ()
        if isinstance(row, dict)
    }
    return {"counts": dict(document.get("counts") or {}), "rows": rows}


def _native_state(root: Path) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    receipts = root / "receipts"
    if not receipts.is_dir():
        return state
    for path in sorted(receipts.glob("native-*.json")):
        document = _read_json(path)
        if not isinstance(document, dict):
            continue
        key = f"{document.get('candidate')}:{document.get('group')}"
        state[key] = {
            "returncode": document.get("returncode"),
            "tests": document.get("tests"),
            "failures": document.get("failed"),
            "errors": document.get("errors"),
            "skipped": document.get("skipped"),
            "unexecuted_classes": sorted(document.get("unexecuted_classes") or ()),
            "classes": sorted(document["classes"]),
            "executed_classes": {
                name: {
                    field: counts.get(field) for field in ("tests", "failures", "errors", "skipped")
                }
                for name, counts in document["executed_classes"].items()
            },
        }
    return state


def _compare_af(
    differences: list[str], serial_root: Path, shadow_root: Path, candidate: str
) -> None:
    label = f"{candidate} AF00-AF11"
    serial = _af_state(serial_root, candidate)
    shadow = _af_state(shadow_root, candidate)
    if serial is None or shadow is None:
        differences.append(_missing(label, serial, shadow))
        return
    for gate in sorted(set(serial) | set(shadow)):
        left = serial.get(gate)
        right = shadow.get(gate)
        if left is None or right is None:
            differences.append(f"{label} {gate}: present in only one packet")
            continue
        if left["verdict"] != right["verdict"]:
            differences.append(
                f"{label} {gate} verdict: serial={left['verdict']!r} shadow={right['verdict']!r}"
            )
        if left["blocking_rows"] != right["blocking_rows"]:
            differences.append(
                f"{label} {gate} blocking_rows: serial={left['blocking_rows']} "
                f"shadow={right['blocking_rows']}"
            )


def _compare_full107(
    differences: list[str], serial_root: Path, shadow_root: Path, candidate: str
) -> None:
    label = f"{candidate} FULL107"
    serial = _full107_state(serial_root, candidate)
    shadow = _full107_state(shadow_root, candidate)
    if serial is None or shadow is None:
        differences.append(_missing(label, serial, shadow))
        return
    for key in sorted(set(serial["counts"]) | set(shadow["counts"])):
        left = serial["counts"].get(key)
        right = shadow["counts"].get(key)
        if left != right:
            differences.append(f"{label} counts.{key}: serial={left!r} shadow={right!r}")
    for fixture_id in sorted(set(serial["rows"]) | set(shadow["rows"])):
        left = serial["rows"].get(fixture_id)
        right = shadow["rows"].get(fixture_id)
        if left != right:
            differences.append(f"{label} row {fixture_id}: serial={left!r} shadow={right!r}")


def _compare_native_receipts(differences: list[str], serial_root: Path, shadow_root: Path) -> None:
    serial = _native_state(serial_root)
    shadow = _native_state(shadow_root)
    if not serial and not shadow:
        differences.append(
            "native receipts: none found in either packet; nothing could be compared"
        )
        return
    for key in sorted(set(serial) | set(shadow)):
        left = serial.get(key)
        right = shadow.get(key)
        if left is None or right is None:
            side = "serial" if left is None else "shadow"
            differences.append(f"native receipt {key}: missing from the {side} packet")
            continue
        for field in (
            "returncode",
            "tests",
            "failures",
            "errors",
            "skipped",
            "unexecuted_classes",
            "classes",
            "executed_classes",
        ):
            if left[field] != right[field]:
                differences.append(
                    f"native receipt {key} {field}: serial={left[field]!r} shadow={right[field]!r}"
                )


def compare_packets(serial_root: Path, shadow_root: Path) -> list[str]:
    """Every semantic difference between the two packets, one line each.

    Timestamps, durations and run ids are not read at all: only the compared
    fields above are, so run noise cannot produce a difference. Invalid input
    returns validation errors only, suppressing subsequent semantic differences.
    Repository URLs are byte-exact: checkout/clone .git spelling differences
    require identity adjudication rather than automatic equivalence.
    """
    differences = _packet_errors(serial_root, "serial") + _packet_errors(shadow_root, "shadow")
    if differences:
        return differences
    if _source(serial_root) != _source(shadow_root):
        differences.append("epoch identity: producing repository/commit/tree differ")
    for candidate in CANDIDATES:
        _compare_af(differences, serial_root, shadow_root, candidate)
        _compare_full107(differences, serial_root, shadow_root, candidate)
    _compare_native_receipts(differences, serial_root, shadow_root)
    return differences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare serial and shadow PB-03 packets (#479 E2 shadow experiment)."
    )
    parser.add_argument("serial", type=Path, help="packet directory produced without the overlap")
    parser.add_argument("shadow", type=Path, help="packet directory produced with the overlap")
    args = parser.parse_args(argv)
    for label, root in (("serial", args.serial), ("shadow", args.shadow)):
        if not root.is_dir():
            print(f"{label} packet directory does not exist: {root}", file=sys.stderr)
            return 2
    differences = compare_packets(args.serial, args.shadow)
    for line in differences:
        print(line)
    print(f"pb03 shadow comparison: {len(differences)} difference(s)")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
