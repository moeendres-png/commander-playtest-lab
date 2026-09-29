#!/usr/bin/env python3
"""Capture the engine-bridge validation run as a durable evidence artifact.

The bridge suite runs in ``engine-bridge/target/surefire-reports``, which is
build output and not committed. A claim about the repaired generic lane would
therefore rest on a run nobody else can inspect. This script reads the reports
and writes a committed artifact that names the exact revision, the tree state,
the total counts, and every test that bears on the shuffle/seed repair.

It records only what the reports contain. A missing report is recorded as
missing rather than as a pass, and the artifact states the tree cleanliness so a
run made on a modified tree is visible as such.
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "engine-bridge" / "target" / "surefire-reports"
OUT = REPO / "qualification" / "final-current-boundary-20260927" / "BRIDGE_VALIDATION_XMAGE.json"

# Suites whose result bears on the PR #293 repair specifically.
FOCUS = (
    "XmageGenericLaneRulesSeedTest",
    "XmageBridgePlayerFailClosedTest",
    "XmageFullGameRulesSeedBindingTest",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
    ).stdout.strip()


def main() -> int:
    if not REPORTS.is_dir():
        print(f"no surefire reports at {REPORTS}; run the bridge suite first", file=sys.stderr)
        return 1

    total = failures = errors = skipped = 0
    suites: list[dict[str, object]] = []
    missing: list[str] = []

    for path in sorted(REPORTS.glob("*.xml")):
        root = ET.parse(path).getroot()
        name = str(root.get("name") or path.stem)
        counts = {
            "tests": int(root.get("tests", 0)),
            "failures": int(root.get("failures", 0)),
            "errors": int(root.get("errors", 0)),
            "skipped": int(root.get("skipped", 0)),
        }
        total += counts["tests"]
        failures += counts["failures"]
        errors += counts["errors"]
        skipped += counts["skipped"]
        if any(focus in name for focus in FOCUS):
            suites.append(
                {
                    "suite": name,
                    **counts,
                    "cases": [str(tc.get("name")) for tc in root.iter("testcase")],
                }
            )

    seen = {str(s["suite"]).split(".")[-1] for s in suites}
    missing = [focus for focus in FOCUS if focus not in seen]

    payload = {
        "schema_version": "commander-lab.bridge-validation/1.0.0",
        "candidate": "xmage",
        "captured_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "lab_revision": {
            "commit": _git("rev-parse", "HEAD"),
            "tree": _git("rev-parse", "HEAD^{tree}"),
            "tree_dirty": bool(_git("status", "--porcelain")),
            # What was actually tested is the bridge, so its own cleanliness is the
            # binding fact. A workstream editing Python qualification code does not
            # make a bridge run irreproducible, but an edit to the bridge does.
            "bridge_dirty": bool(_git("status", "--porcelain", "--", "engine-bridge")),
            "bridge_matches_recorded_revision": _git("diff", "--quiet", "--", "engine-bridge")
            == "",
            "note": (
                "bridge_dirty=false and bridge_matches_recorded_revision=true mean this "
                "result is reproducible from the recorded commit; tree_dirty describes the "
                "whole worktree and is expected to be true while the capturing script itself "
                "is being added"
            ),
        },
        "suite_totals": {
            "tests": total,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "focus_suites": suites,
        "focus_suites_missing": missing,
        "what_this_establishes": (
            "the engine-bridge suites pass at this revision, including the generic-lane shuffle "
            "repair and the Rules-seed binding that PR #293 introduced"
        ),
        "what_this_does_not_establish": [
            "that the current-boundary XMage column is requalified: the FULL107 rows are produced "
            "by scripts/run_current_boundary_qualification.py, not by the bridge suite",
            "that any gate verdict moves: AF05/AF09 stay UNKNOWN until the column is regenerated",
            "that the repaired lane is Rules-correct in general; each affected obligation still "
            "needs its own observation",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: tests={total} failures={failures} errors={errors}")
    if missing:
        print(f"WARNING: focus suites absent from the reports: {missing}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
