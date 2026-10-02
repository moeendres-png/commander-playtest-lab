#!/usr/bin/env python3
"""Forge current-boundary scenario lane runner (issue #455).

Default is a *structural* census: it binds the pinned Forge source, derives the
ScenarioBootstrap capability matrix, and classifies every effective FULL107 row
without launching an engine. ``--row`` / ``--wave`` / ``--eligible`` additionally
execute the real pinned Forge bridge in an isolated process and persist
source-bound receipts.

Heavy Forge runtime: one bridge process at a time, launched from the bound
checkout, all engine state under the caller's ``.runtime/engine`` directory.
The lane never edits the Forge repository.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary.forge_scenario_lane import (  # noqa: E402
    FORGE_SCENARIO_BLOCKER_WAVE as WAVE,
)
from commander_lab.qualification.current_boundary.forge_scenario_lane import (  # noqa: E402
    LANE_SCHEMA_VERSION,
    RESULT_NOT_ATTEMPTED,
    RowEvidence,
    bind_forge_scenario_source,
    derive_capability_matrix,
    launch_forge_scenario,
    model_requested_state,
    probe_row,
    run_capability_probe,
    temporal_reachable,
)
from commander_lab.qualification.current_boundary.materialization import (  # noqa: E402
    load_effective_materialization,
)


def _write(directory: Path, name: str, payload: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return path


def structural_census(materialization) -> dict[str, object]:
    rows = []
    for record in materialization.denominator_records():
        model = model_requested_state(record)
        rows.append(
            {
                "fixture_id": model.fixture_id,
                "fixture_family": record.get("fixture_family"),
                "player_count": model.player_count,
                "execution_entry_mode": record.get("execution_entry_mode"),
                "materialization_status": record.get("materialization_status"),
                "construction_eligible": model.construction_eligible,
                "credit_eligible": model.credit_eligible,
                "temporal_reachable": temporal_reachable(model),
                "unsupported_dimensions": [item.to_document() for item in model.hard_unsupported],
                "unobservable_dimensions": [item.to_document() for item in model.unobservable],
                "requested_temporal_state": model.temporal_state,
                "neutral_initial_state": model.neutral_initial_state,
            }
        )
    counts: dict[str, int] = {}
    for row in rows:
        key = (
            "CREDIT_ELIGIBLE"
            if row["credit_eligible"]
            else "CONSTRUCTIBLE_NOT_OBSERVABLE"
            if row["construction_eligible"]
            else "UNSUPPORTED_DIMENSION"
        )
        counts[key] = counts.get(key, 0) + 1
    return {
        "schema_version": f"{LANE_SCHEMA_VERSION}.structural-census",
        "qualification_boundary": materialization.receipt().get("qualification_boundary"),
        "contract_id": materialization.bundle.get("contract_id"),
        "canonical_bundle_digest": materialization.canonical_bundle_digest,
        "denominator": len(rows),
        "counts": counts,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forge-workspace",
        default=os.environ.get("FORGE_WORKSPACE"),
        help="explicit clean Forge checkout at the bound bridge source (no default)",
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "docs" / "forge_scenario_lane_20261001" / "receipts"),
    )
    parser.add_argument("--row", action="append", default=[], help="effective fixture id")
    parser.add_argument(
        "--wave", action="store_true", help="execute the seven structurally relevant rows"
    )
    parser.add_argument(
        "--eligible",
        action="store_true",
        help="execute every row the structural classifier marks credit-eligible",
    )
    parser.add_argument(
        "--capability-probe",
        action="store_true",
        help="run the live engine rejection probes for stack/decision_script",
    )
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--max-steps", type=int, default=200)
    args = parser.parse_args()

    out_dir = Path(args.out)
    materialization = load_effective_materialization(REPO_ROOT)
    census = structural_census(materialization)
    _write(out_dir, "STRUCTURAL_CENSUS.json", census)
    print(
        "structural census:",
        census["counts"],
        "denominator",
        census["denominator"],
        "contract",
        census["contract_id"],
    )

    selected: list[str] = []
    if args.wave:
        selected.extend(WAVE)
    selected.extend(args.row)
    if args.eligible:
        selected.extend(
            row["fixture_id"]
            for row in census["rows"]
            if row["credit_eligible"] and row["fixture_id"] not in selected
        )
    needs_engine = bool(selected) or args.capability_probe
    if not args.forge_workspace:
        if not needs_engine:
            print("structural census written to", out_dir)
            return 0
        print(
            "FORGE_WORKSPACE (or --forge-workspace) is required: a Forge run needs an "
            "explicit, source-locked checkout and there is no ambient default",
            file=sys.stderr,
        )
        return 2

    source = bind_forge_scenario_source(args.forge_workspace)
    matrix = derive_capability_matrix(source, Path(source.workspace))
    matrix["source_identity"] = source.to_document()
    _write(out_dir, "SCENARIO_CAPABILITY_MATRIX.json", matrix)
    print(
        "capability matrix bound:",
        source.bridge_commit[:12],
        "source blob",
        source.scenario_source_sha256[:12],
    )

    records = {record["fixture_id"]: record for record in materialization.denominator_records()}
    missing = [fixture for fixture in selected if fixture not in records]
    if missing:
        print(f"unknown fixture ids: {missing}", file=sys.stderr)
        return 2

    evidence: list[RowEvidence] = []
    proc, runtime_identity = launch_forge_scenario(source)
    try:
        if args.capability_probe:
            probe_model = model_requested_state(
                records[selected[0]] if selected else next(iter(records.values()))
            )
            live_probe = run_capability_probe(proc, probe_model)
            _write(out_dir, "LIVE_REJECTION_PROBE.json", live_probe)
            print("live rejection probe:", live_probe)
        for index, fixture_id in enumerate(selected, start=1):
            model = model_requested_state(records[fixture_id])
            print(f"[{index}/{len(selected)}] {fixture_id}: probing")
            item = probe_row(
                proc,
                model=model,
                source=source,
                root=REPO_ROOT,
                seed=args.seed,
                max_steps=args.max_steps,
            )
            classification = (item.fields.get("classification") or {}).get("result")
            print(f"    -> {classification}")
            evidence.append(item)
            _write(
                out_dir,
                "EXECUTION_RECEIPT.json",
                {
                    "schema_version": f"{LANE_SCHEMA_VERSION}.execution-receipt",
                    "source_identity": source.to_document(),
                    "runtime_identity": runtime_identity,
                    "attempted": [entry.fixture_id for entry in evidence],
                    "rows": [entry.to_document() for entry in evidence],
                },
            )
    finally:
        proc.close()

    counts: dict[str, int] = {}
    for item in evidence:
        result = (item.fields.get("classification") or {}).get("result", RESULT_NOT_ATTEMPTED)
        counts[result] = counts.get(result, 0) + 1
    print("execution classifications:", counts)
    print("receipts written to", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
