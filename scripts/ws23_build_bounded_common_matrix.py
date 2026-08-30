#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FIXTURE_IDS = (
    "PLAYER_COUNT_4P",
    "PILOT_PRIORITY",
    "PILOT_TARGET",
    "PILOT_MANA_PAYMENT",
    "WS05-MP-COMBAT-4",
    "WS05-MP-BLOCK-4",
    "PILOT_TRIGGER_ORDER",
    "PILOT_REPLACEMENT_EFFECT",
    "MICRO_PREVENTION",
    "WS05-CMD-ZONE-HAND-YES",
    "HIDDEN_01",
    "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE",
    "CARD_02",
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def decision_frames(proof: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [
        item
        for item in proof.get("transcript", [])
        if item.get("message_type") == "DECISION_FRAME"
        and item.get("payload", {}).get("decision_kind") == kind
    ]


def tapes_equal(first: dict[str, Any], replay: dict[str, Any]) -> bool:
    keys = (
        "actor_id",
        "decision_kind",
        "options_digest",
        "offered_option_ids",
        "selected_option_id",
    )
    a = first.get("decision_tape", [])
    b = replay.get("decision_tape", [])
    return len(a) > 0 and len(a) == len(b) and all(
        all(left.get(key) == right.get(key) for key in keys)
        for left, right in zip(a, b, strict=True)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--runtime-proof", type=Path, required=True)
    ap.add_argument("--replay-proof", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    manifest = load(args.manifest)
    runtime = load(args.runtime_proof)
    replay = load(args.replay_proof)
    fixtures = {item["fixture_id"]: item for item in manifest["fixtures"]}
    missing = [fixture_id for fixture_id in FIXTURE_IDS if fixture_id not in fixtures]
    if missing:
        raise AssertionError(f"canonical common fixture IDs missing: {missing}")
    wrong_scope = [
        fixture_id
        for fixture_id in FIXTURE_IDS
        if fixtures[fixture_id].get("player_count") != 4
        or fixtures[fixture_id].get("expected_evidence_class") != "RUNTIME_VERIFIED"
    ]
    if wrong_scope:
        raise AssertionError(f"bounded matrix fixture contract drift: {wrong_scope}")

    state = runtime.get("decision_coverage", {})
    observation = runtime.get("observation") or {}
    commander = runtime.get("commander_proof") or {}
    trigger = runtime.get("trigger_proof") or {}
    prevention = runtime.get("prevention_proof") or {}
    rng = runtime.get("rng_proof") or {}
    result_payload = (runtime.get("result") or {}).get("payload", {})
    snapshot = result_payload.get("snapshot") or {}

    attack_frames = decision_frames(runtime, "declareAttackers")
    multi_defender = any(
        len(
            [
                option
                for option in frame.get("payload", {}).get("options", [])
                if option.get("kind") == "ATTACK"
            ]
        )
        >= 3
        for frame in attack_frames
    )

    replay_ok = (
        replay.get("replay_mode") is True
        and replay.get("result") is not None
        and replay.get("rng_replay_match") is True
        and replay.get("snapshot_replay_match") is True
        and tapes_equal(runtime, replay)
    )
    rng_ok = (
        rng.get("common_fixture_id") == "RNG_RULES_TAPE"
        and rng.get("engine_path") == "FlipCoinEffect/MyRandom"
        and rng.get("seed") == 230023
        and rng.get("flip_count") == 16
        and len(rng.get("sequence", "")) == 16
        and replay.get("rng_replay_match") is True
    )

    checks: dict[str, tuple[bool, str]] = {
        "PLAYER_COUNT_4P": (
            snapshot.get("player_count") == 4,
            "real SESSION_RESULT snapshot contains exactly four Forge players",
        ),
        "PILOT_PRIORITY": (
            state.get("bolt_cast") is True,
            "actual Lightning Bolt selected from Forge-owned priority options",
        ),
        "PILOT_TARGET": (
            state.get("target") is True,
            "target selected from Forge TargetRestrictions/getAllCandidates + canTarget",
        ),
        "PILOT_MANA_PAYMENT": (
            state.get("mana_payments", 0) >= 2,
            "Bolt and Fog mana selected from Forge-filtered ManaPool choices and accepted by Forge",
        ),
        "WS05-MP-COMBAT-4": (
            state.get("attack") is True and multi_defender,
            "four-player attack frame offered multiple Forge-valid defending players",
        ),
        "WS05-MP-BLOCK-4": (
            state.get("block") is True,
            "Forge-valid blocker assignment selected and validateBlocks accepted it",
        ),
        "PILOT_TRIGGER_ORDER": (
            state.get("trigger_order") is True
            and trigger.get("ordered_trigger_count") == 2
            and trigger.get("life_gain_after_resolution") == 2
            and trigger.get("native_trigger_resolution_verified") is True,
            "two actual Soul Warden ETB triggers ordered externally and resolved by Forge",
        ),
        "PILOT_REPLACEMENT_EFFECT": (
            state.get("replacement") is True,
            "optional Forge replacement APPLY/DECLINE decision externalized",
        ),
        "MICRO_PREVENTION": (
            prevention.get("common_fixture_id") == "MICRO_PREVENTION"
            and prevention.get("card_identity") == "Fog"
            and prevention.get("native_prevention_verified") is True
            and prevention.get("attacker_damage") == 0
            and prevention.get("blocker_damage") == 0,
            "actual Fog resolved through Forge and prevented both creatures' combat damage",
        ),
        "WS05-CMD-ZONE-HAND-YES": (
            commander.get("common_fixture_id") == "WS05-CMD-ZONE-HAND-YES"
            and commander.get("native_commander_replacement_applied") is True,
            "Forge Commander 903.9b hand replacement moved Rograkh to the command zone",
        ),
        "HIDDEN_01": (
            observation.get("opponent_hand_identity_hidden") is True,
            "opponent hand identities absent while owner/count visibility remains actor-scoped",
        ),
        "RNG_RULES_TAPE": (
            rng_ok,
            "16 real FlipCoinEffect/MyRandom outcomes reproduce under seed 230023 in a fresh JVM",
        ),
        "REPLAY_DECISION_TAPE": (
            replay_ok,
            "fresh JVM consumed exact actor/kind/digest/offered-ID/selection DecisionTape and matched snapshot",
        ),
        "CARD_02": (
            commander.get("actual_card_fixture_id") == "CARD_02"
            and commander.get("card_identity") == "Rograkh, Son of Rohgahh"
            and commander.get("cast_from_command_runtime_verified") is True
            and commander.get("commander_cast_count") == 1
            and commander.get("actual_card_behavior_verified") is True,
            "Rograkh was Forge-legally cast from command, counted as commander cast, and resolved to battlefield",
        ),
    }

    rows = []
    for fixture_id in FIXTURE_IDS:
        passed, evidence = checks[fixture_id]
        fixture = fixtures[fixture_id]
        rows.append(
            {
                "fixture_id": fixture_id,
                "category": fixture["category"],
                "description": fixture["description"],
                "player_count": fixture["player_count"],
                "expected_evidence_class": fixture["expected_evidence_class"],
                "status": "PASS" if passed else "FAIL",
                "runtime_evidence": evidence,
            }
        )

    output = {
        "schema_version": "ws23-bounded-common-matrix/1.1.0",
        "manifest_schema_version": manifest.get("schema_version"),
        "fixture_ids": list(FIXTURE_IDS),
        "pass_count": sum(row["status"] == "PASS" for row in rows),
        "denominator": len(rows),
        "all_pass": all(row["status"] == "PASS" for row in rows),
        "continue_gate": "CONTINUE" if all(row["status"] == "PASS" for row in rows) else "UNKNOWN",
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass_count": output["pass_count"],
                "denominator": len(rows),
                "continue_gate": output["continue_gate"],
            },
            sort_keys=True,
        )
    )
    return 0 if output["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
