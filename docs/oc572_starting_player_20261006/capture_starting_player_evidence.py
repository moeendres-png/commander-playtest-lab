#!/usr/bin/env python3
"""Capture LOCAL_OBSERVED #572 starting-player evidence from the real pinned XMage.

Run from the repository root after ``lab-ops/scripts/real_rows.py build``:

    python3 docs/oc572_starting_player_20261006/capture_starting_player_evidence.py

Writes ``LOCAL_OBSERVED_STARTING_PLAYER_EVIDENCE.json`` beside this file.
LOCAL_OBSERVED only: PB-03 on an exact head plus a sealed epoch is the credit
path. This script never selects a provider and never claims a freeze.
"""

# ruff: noqa: E402

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (
    bridge_launcher,
    full107,
)
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

OUT = Path(__file__).resolve().parent / "LOCAL_OBSERVED_STARTING_PLAYER_EVIDENCE.json"
identity = {"runner": "local-dev-oc572"}
materialization = load_effective_materialization(REPO_ROOT)
by_id = {record["fixture_id"]: record for record in materialization.denominator_records()}

plan = bridge_launcher.build_launch_plan(
    "xmage", lane="compat", xmage_workspace=(REPO_ROOT / "engine-bridge").resolve()
)
keyed = bridge_launcher.orchestration_plan(plan)

evidence: dict = {"evidence_class": "LOCAL_OBSERVED", "engine": "pinned-xmage", "runs": {}}


def run_cardinality(record: dict, player_count: int) -> dict:
    with bridge_launcher.launch(keyed) as proc:
        result = full107.run_cardinality(
            proc,
            candidate="xmage",
            player_count=player_count,
            runtime_identity=identity,
            record=record,
        )
    row = full107.cardinality_row(record, result, candidate="xmage", runtime_identity=identity)
    return {
        "outcome": row.outcome,
        "reason": row.reason,
        "failure": result.failure,
        "failure_kind": result.failure_kind,
        "starting_player_channel": result.terminal_facts.get("starting_player_channel"),
        "declared_starting_seat": result.terminal_facts.get("declared_starting_seat"),
        "starting_player_declaration": result.terminal_facts.get("starting_player_declaration"),
        "provider_acknowledged_seat": result.terminal_facts.get(
            "starting_player_provider_acknowledged_seat"
        ),
        "provider_confirmed_seat": result.terminal_facts.get(
            "starting_player_provider_confirmed_seat"
        ),
        # P3-3: true only when the bridge reported the CR 103.2 prompt
        # chooser/chosen identities, which the credit rule requires in
        # addition to the engine starting_player_id readback (#572).
        "provider_prompt_answer_recorded": result.terminal_facts.get(
            "starting_player_prompt_answer_recorded"
        ),
        "starting_player_frame_answered": result.terminal_facts.get(
            "starting_player_frame_answered"
        ),
        "starting_player_choice": result.terminal_facts.get("starting_player_choice"),
        "construction_proof_verdict": (row.evidence.get("construction_proof") or {}).get("verdict"),
        "temporal_checks": [
            {
                "field": check["field"],
                "verdict": check["verdict"],
                "requested": check["requested"],
                "observed": check["observed"],
            }
            for check in (row.evidence.get("construction_proof") or {}).get("checks", [])
            if check["field"].startswith("temporal_state.")
        ],
        "evidence_class": row.evidence.get("evidence_class"),
    }


# 1. Every required cardinality: the record's own pre-first-turn active player is
#    the explicit declaration the engine must acknowledge.
for count in (2, 3, 4, 5):
    record = by_id[f"PLAYER_COUNT_{count}P"]
    evidence["runs"][f"cardinality_{count}p_declared"] = run_cardinality(record, count)

# 2. Fail closed: the same 2P run with the declaration removed from the record.
undeclared = copy.deepcopy(by_id["PLAYER_COUNT_2P"])
undeclared["temporal_state"] = {"turn_number": 1, "active_player": None}
evidence["runs"]["cardinality_2p_undeclared"] = run_cardinality(undeclared, 2)

# 3. START-2: the 1.0.21 record is a turn-1 NATIVE_STATE_LOAD whose obligation
#    names starting_player:P1 but declares no starting seat; the run must refuse.
start2 = by_id["WS05-CMD-START-2"]
with bridge_launcher.launch(keyed) as proc:
    start2_result = full107.start2_row(start2, proc, candidate="xmage", runtime_identity=identity)
start2_facts = start2_result.evidence.get("terminal_facts") or {}
evidence["runs"]["start2_1_0_21"] = {
    "outcome": start2_result.outcome,
    "reason": start2_result.reason,
    "declared_starting_seat": start2_facts.get("declared_starting_seat"),
    "starting_player_channel": start2_facts.get("starting_player_channel"),
    "failure": start2_facts.get("failure"),
    "evidence_class": start2_result.evidence.get("evidence_class"),
}

# 4. PILOT_MULLIGAN: the record declares P1 at turn 0 and the real engine
#    acknowledges the declared create-time seat.
mulligan = by_id["PILOT_MULLIGAN"]
with bridge_launcher.launch(keyed) as proc:
    mulligan_result = full107.scripted_pregame_row(
        mulligan, proc, candidate="xmage", runtime_identity=identity
    )
mulligan_facts = mulligan_result.evidence.get("terminal_facts") or {}
evidence["runs"]["pilot_mulligan_declared"] = {
    "outcome": mulligan_result.outcome,
    "reason": mulligan_result.reason,
    "declared_starting_seat": mulligan_facts.get("declared_starting_seat"),
    "starting_player_channel": mulligan_facts.get("starting_player_channel"),
    "provider_acknowledged_seat": mulligan_facts.get("starting_player_provider_acknowledged_seat"),
    "provider_confirmed_seat": mulligan_facts.get("starting_player_provider_confirmed_seat"),
    "provider_prompt_answer_recorded": mulligan_facts.get("starting_player_prompt_answer_recorded"),
    "construction_proof_verdict": (mulligan_result.evidence.get("construction_proof") or {}).get(
        "verdict"
    ),
    "evidence_class": mulligan_result.evidence.get("evidence_class"),
}

OUT.write_text(json.dumps(evidence, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(evidence, indent=1, sort_keys=True))
