#!/usr/bin/env python3
"""Generate a fail-closed phase.rs card-domain crosswalk for WS-20 v2.

Source/test references are provenance only, never behavioral PASS. The exact 29-card
and 87-card lists are read from the committed domain manifest. The 1,385 denominator
is reported only to the granularity materialized by that manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grep_paths(root: Path, literal: str) -> list[str]:
    cp = subprocess.run(
        ["git", "-C", str(root), "grep", "-F", "-l", "-e", literal, "--"],
        text=True,
        capture_output=True,
    )
    if cp.returncode not in (0, 1):
        raise RuntimeError(cp.stderr.strip())
    return sorted({line.strip() for line in cp.stdout.splitlines() if line.strip()})


def classify(name: str, root: Path) -> dict:
    paths = grep_paths(root, name)
    test_paths = [p for p in paths if "/test" in p or p.startswith("tests/") or "/tests/" in p]
    engine_paths = [p for p in paths if p.startswith("crates/engine/src/")]
    return {
        "card_identity": name,
        "literal_source_reference_present": bool(paths),
        "literal_source_reference_paths": paths,
        "engine_source_literal_reference_present": bool(engine_paths),
        "engine_source_literal_reference_paths": engine_paths,
        "test_literal_reference_present": bool(test_paths),
        "test_literal_reference_paths": test_paths,
        "behavioral_runtime_verdict": "NOT_RUN",
        "behavioral_runtime_reason": (
            "Source/test presence is SOURCE_DERIVED only. Behavioral PASS requires execution of "
            "the identical frozen common behavioral fixture against this exact candidate build."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase-root", type=Path, required=True)
    ap.add_argument("--domain-manifest", type=Path, required=True)
    ap.add_argument("--source-lock", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    domain = json.loads(args.domain_manifest.read_text(encoding="utf-8"))
    lock = json.loads(args.source_lock.read_text(encoding="utf-8"))
    corpus = domain["regression_corpus_29"]
    rogshai = domain["current_rogshai_unique_identity_list"]
    assert len(corpus) == 29
    assert len(rogshai) == 87
    assert domain["known_actual_card_universe"] == 1385

    out = {
        "schema_version": "ws20-phase-card-crosswalk/2.0.0",
        "candidate": "phase.rs-ws20-v2-patched",
        "source_lock": lock["selected_upstream"],
        "source_lock_file_sha256": sha256(args.source_lock),
        "domain_manifest_sha256": sha256(args.domain_manifest),
        "behavioral_corpus_29": {
            "count": 29,
            "rows": [classify(name, args.phase_root) for name in corpus],
            "runtime_pass_count": 0,
            "runtime_status": "NOT_RUN",
        },
        "current_rogshai_87": {
            "count": 87,
            "rows": [classify(name, args.phase_root) for name in rogshai],
            "runtime_status": "NOT_RUN",
        },
        "known_actual_card_universe_1385": {
            "count": 1385,
            "identity_list_materialized_in_committed_manifest": False,
            "crosswalk_status": "UNKNOWN",
            "reason": (
                "The committed ACTUAL_CARD_DOMAIN_v1.json freezes the 1,385 denominator but does "
                "not materialize the complete 1,385-name identity list. WS-20 does not invent it."
            ),
        },
        "evidence_rule": (
            "Import, parse, source reference, or test reference is not runtime card behavior. "
            "Only identical executed common fixtures may produce behavioral PASS."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
