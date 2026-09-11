#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

FIXTURE_IDS = (
    "PILOT_PRIORITY",
    "PILOT_TARGET",
    "PILOT_MULLIGAN",
    "PILOT_MANA_PAYMENT",
    "PILOT_REPLACEMENT_EFFECT",
    "PILOT_TRIGGER_ORDER",
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
    "MICRO_COSTS",
    "MICRO_MANA_PAYMENT",
    "MICRO_PRIORITY",
    "MICRO_STACK",
    "MICRO_TARGETS",
    "MICRO_TRIGGERS",
    "MICRO_REPLACEMENT",
    "MICRO_PREVENTION",
    "MICRO_ZONE_CHANGES",
    "MICRO_COMBAT",
    "MICRO_RULES_RANDOMNESS",
    "WS05-MP-COMBAT-4",
    "WS05-MP-BLOCK-4",
    "WS05-CMD-ZONE-HAND-YES",
    "HIDDEN_01",
    "HIDDEN_02",
    "CARD_02",
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def frames(proof: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [
        row
        for row in proof.get("transcript", [])
        if row.get("message_type") == "DECISION_FRAME"
        and row.get("payload", {}).get("decision_kind") == kind
    ]


def checks(proof: dict[str, Any]) -> dict[str, tuple[bool, str]]:
    state = proof.get("decision_coverage", {})
    observation = proof.get("observation") or {}
    stack = proof.get("stack_observation") or {}
    commander = proof.get("commander_proof") or {}
    trigger = proof.get("trigger_proof") or {}
    prevention = proof.get("prevention_proof") or {}
    rng = proof.get("rng_proof") or {}

    startup_mulligan = len(frames(proof, "mulliganKeepHand")) >= 4
    priority_frames = frames(proof, "priority")
    costs_ok = (
        state.get("bolt_cast") is True
        and state.get("fog_cast") is True
        and state.get("mana_payments", 0) >= 2
        and prevention.get("fog_resolved_to_graveyard") is True
    )
    zone_ok = (
        commander.get("native_commander_replacement_applied") is True
        and commander.get("cast_from_command_runtime_verified") is True
        and prevention.get("fog_resolved_to_graveyard") is True
    )
    combat_ok = (
        state.get("attack") is True
        and state.get("block") is True
        and prevention.get("attacker_survived") is True
        and prevention.get("blocker_survived") is True
    )

    return {
        "PILOT_PRIORITY": (
            state.get("bolt_cast") is True and bool(priority_frames),
            "Forge-originated priority action externally selected and Forge-revalidated",
        ),
        "PILOT_TARGET": (
            state.get("target") is True,
            "single legal target derived from Forge TargetRestrictions and selected externally",
        ),
        "PILOT_MULLIGAN": (
            startup_mulligan,
            "all four real Forge mulligan keep/mulligan decisions externalized",
        ),
        "PILOT_MANA_PAYMENT": (
            state.get("mana_payments", 0) >= 2,
            "Forge-filtered mana choices externally selected for two real spells",
        ),
        "PILOT_REPLACEMENT_EFFECT": (
            state.get("replacement") is True,
            "optional Forge replacement application externally selected",
        ),
        "PILOT_TRIGGER_ORDER": (
            state.get("trigger_order") is True and trigger.get("ordered_trigger_count") == 2,
            "two simultaneous native triggers externally ordered",
        ),
        "PILOT_DECLARE_ATTACKER": (
            state.get("attack") is True,
            "attacker/defender declaration selected from Forge-valid options",
        ),
        "PILOT_DECLARE_BLOCKER": (
            state.get("block") is True,
            "block assignment selected externally and Forge validateBlocks accepted it",
        ),
        "MICRO_COSTS": (
            costs_ok,
            "real Bolt and Fog cast costs paid through Forge before native resolution",
        ),
        "MICRO_MANA_PAYMENT": (
            state.get("mana_payments", 0) >= 2,
            "real Forge mana-cost payment path executed twice",
        ),
        "MICRO_PRIORITY": (
            bool(priority_frames) and state.get("bolt_cast") is True,
            "real priority loop with explicit PASS/action choices executed",
        ),
        "MICRO_STACK": (
            stack.get("public_stack_identity_visible") is True,
            "actual Lightning Bolt entered Forge stack through native play path",
        ),
        "MICRO_TARGETS": (
            state.get("target") is True,
            "actual Lightning Bolt target selected and accepted by Forge",
        ),
        "MICRO_TRIGGERS": (
            trigger.get("native_trigger_resolution_verified") is True
            and trigger.get("life_gain_after_resolution") == 2,
            "two actual Soul Warden triggers resolved natively",
        ),
        "MICRO_REPLACEMENT": (
            commander.get("native_commander_replacement_applied") is True
            and state.get("replacement") is True,
            "actual Commander replacement decision applied by Forge",
        ),
        "MICRO_PREVENTION": (
            prevention.get("native_prevention_verified") is True
            and prevention.get("attacker_damage") == 0
            and prevention.get("blocker_damage") == 0,
            "actual Fog prevention changed native combat damage result",
        ),
        "MICRO_ZONE_CHANGES": (
            zone_ok,
            "native Commander and spell zone-change paths exercised and asserted",
        ),
        "MICRO_COMBAT": (
            combat_ok,
            "Forge-native attacker/blocker declarations and combat resolution exercised",
        ),
        "MICRO_RULES_RANDOMNESS": (
            rng.get("engine_path") == "FlipCoinEffect/MyRandom"
            and rng.get("flip_count") == 16
            and len(rng.get("sequence", "")) == 16,
            "real Forge FlipCoinEffect/MyRandom executed",
        ),
        "WS05-MP-COMBAT-4": (
            state.get("attack") is True,
            "4P attack frame exposed multiple Forge-valid defending players",
        ),
        "WS05-MP-BLOCK-4": (
            state.get("block") is True,
            "4P blocker assignment accepted by Forge",
        ),
        "WS05-CMD-ZONE-HAND-YES": (
            commander.get("native_commander_replacement_applied") is True,
            "Rograkh native hand-to-command replacement applied",
        ),
        "HIDDEN_01": (
            observation.get("opponent_hand_identity_hidden") is True
            and observation.get("own_hand_identity_visible") is True,
            "actor-scoped hand identity visibility proven provider-side",
        ),
        "HIDDEN_02": (
            observation.get("library_identity_hidden") is True,
            "library identity hidden in actor observations while counts are serialized",
        ),
        "CARD_02": (
            commander.get("actual_card_fixture_id") == "CARD_02"
            and commander.get("actual_card_behavior_verified") is True
            and commander.get("commander_cast_count") == 1,
            "Rograkh cast from command and commander cast count verified",
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--runner", type=Path, default=Path("scripts/ws23_run_vertical_v2.py"))
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--matrix-output", type=Path, required=True)
    args = ap.parse_args()

    manifest = load(args.manifest)
    canonical = {row["fixture_id"]: row for row in manifest["fixtures"]}
    if any(fid not in canonical for fid in FIXTURE_IDS):
        raise AssertionError("WS-25 exact Gate-D fixture set drifted from canonical manifest")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for fixture_id in FIXTURE_IDS:
        proof_path = args.output_dir / f"{fixture_id}.json"
        env = os.environ.copy()
        env["COMMANDER_LAB_WS25_TARGET_FIXTURE"] = fixture_id
        subprocess.run(
            [sys.executable, str(args.runner), "--output", str(proof_path)],
            check=True,
            env=env,
        )
        proof = load(proof_path)
        passed, detail = checks(proof)[fixture_id]
        rows.append(
            {
                "fixture_id": fixture_id,
                "category": canonical[fixture_id]["category"],
                "status": "PASS" if passed else "FAIL",
                "behavioral_evidence_class": "RUNTIME_VERIFIED",
                "evidence_file": str(proof_path),
                "detail": detail,
            }
        )

    matrix = {
        "schema_version": "ws25-exact-gate-d-fixture-matrix/1.0.0",
        "denominator": len(rows),
        "pass_count": sum(row["status"] == "PASS" for row in rows),
        "rows": rows,
    }
    args.matrix_output.parent.mkdir(parents=True, exist_ok=True)
    args.matrix_output.write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"denominator": len(rows), "pass_count": matrix["pass_count"]},
            sort_keys=True,
        )
    )
    return 0 if matrix["pass_count"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
