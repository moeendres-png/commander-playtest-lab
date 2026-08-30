#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
MANIFEST_SHA256 = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"
FORGE_HEAD = "09cfad8a24be12a87761e6645c48577387f0521b"
FORGE_ENGINE = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
XMAGE_HEAD = "a53c2312983384eb0870746132e281bbed2f5a1d"
XMAGE_ENGINE = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"

SHARED = [
    "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN", "PILOT_PRIORITY", "PILOT_TARGET", "HIDDEN_01", "HIDDEN_02",
    "MICRO_STACK", "MICRO_REPLACEMENT", "WS05-MP-COMBAT-4", "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES", "CARD_02",
]
FORGE_ONLY = [
    "MICRO_COMBAT", "MICRO_COSTS", "MICRO_MANA_PAYMENT", "MICRO_PREVENTION",
    "MICRO_PRIORITY", "MICRO_RULES_RANDOMNESS", "MICRO_TARGETS", "MICRO_TRIGGERS",
    "MICRO_ZONE_CHANGES", "PILOT_DECLARE_ATTACKER", "PILOT_DECLARE_BLOCKER",
    "PILOT_MANA_PAYMENT", "PILOT_REPLACEMENT_EFFECT", "PILOT_TRIGGER_ORDER",
    "WS05-CMD-ZONE-HAND-YES", "WS05-MP-BLOCK-4",
]
XMAGE_ONLY = [
    "CARD_04", "CARD_24", "HIDDEN_03", "HIDDEN_14", "HIDDEN_15", "HIDDEN_16",
    "HIDDEN_18", "HIDDEN_19", "HIDDEN_HONEYCARD_SENTINEL", "MICRO_CONTINUOUS_EFFECTS",
    "NEGATIVE_PARENT_CLASS_FALLBACK", "PILOT_CHOICE", "PILOT_CHOOSE_OBJECT",
    "PILOT_CHOOSE_USE", "WS05-CMD-TAX-4", "WS05-MP-TRIG-3",
]
DIRECT_CARD_AUTHORITY = {"CARD_02", "CARD_04", "CARD_24"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def shared_signature(fid: str) -> dict[str, Any]:
    forge_gate = {
        "provider": "forge",
        "fixture_projection": "WS25 Gate-D broad scenario",
        "players": 4,
        "starting_life_runtime": 20,
        "notable_objects": ["Lightning Bolt", "Fog", "Rograkh, Son of Rohgahh", "Grizzly Bears", "Soul Warden x2"],
        "rules_rng_seed": 230023,
    }
    xmage_scenario = {
        "provider": "xmage",
        "fixture_projection": "WS26 qualification scenario/native Mage.Tests",
        "players": 4,
        "starting_life": 40,
        "default_commander": "Kenrith, the Returned King",
        "default_library": "Plains x24 per seat for injected WS26 scenarios",
        "seed": 424242,
    }
    if fid.startswith("PLAYER_COUNT_"):
        n = int(fid.split("_")[-1][0])
        return {
            "forge": {"players": n, "starting_life": 20, "prestart_hand_count": 0, "prestart_library_count": 0, "runtime_kind": "Forge lifecycle"},
            "xmage": {"players": n, "starting_life": 40, "commander": "Isamaru, Hound of Konda", "mainboard": "Plains x99", "runtime_kind": "XMage Commander lifecycle"},
            "setup_difference": "starting life and deck/card state differ",
        }
    if fid in {"PILOT_MULLIGAN", "PILOT_PRIORITY"}:
        return {
            "forge": forge_gate,
            "xmage": {"players": 4, "starting_life": 40, "commander": "Isamaru, Hound of Konda", "mainboard": "Plains x99", "scenario": "ws22-pilot-smoke"},
            "setup_difference": "Gate-D actual-card scenario differs from XMage Isamaru/Plains pilot smoke lifecycle",
        }
    if fid == "PILOT_TARGET":
        return {
            "forge": {**forge_gate, "target_interaction": "Lightning Bolt target via Forge TargetRestrictions"},
            "xmage": {**xmage_scenario, "scenario": "WS26-PILOT-TARGET-HIDDEN-METADATA", "objects": ["Mogg Fanatic", "Grizzly Bears", "Demonic Tutor(hidden)"]},
            "setup_difference": "different source/target interaction and surrounding semantic state",
        }
    if fid in {"HIDDEN_01", "HIDDEN_02"}:
        return {
            "forge": {**forge_gate, "hidden_probe": "WS23 honey objects + facedown Grizzly Bears + library identity sentinel"},
            "xmage": {"players": 4, "starting_life": 40, "commander": "Isamaru, Hound of Konda", "mainboard": "Plains x99", "scenario": "ws22-hidden-baseline"},
            "setup_difference": "different cards/decks and observation probe construction",
        }
    if fid == "MICRO_STACK":
        return {
            "forge": {**forge_gate, "interaction": "Lightning Bolt enters native Forge stack"},
            "xmage": {"players": 4, "native_test": "microStackTargetLifo", "interaction": "Lightning Bolt targets Grizzly Bears; Giant Growth responds; Bears survives 5/5"},
            "setup_difference": "XMage includes an additional Giant Growth response and different terminal postcondition",
        }
    if fid == "MICRO_REPLACEMENT":
        return {
            "forge": {**forge_gate, "interaction": "Commander hand-to-command replacement"},
            "xmage": {"players": 4, "native_test": "microReplacementRestInPeace", "interaction": "Rest in Peace replaces graveyard destinations with exile"},
            "setup_difference": "different replacement effects and zones",
        }
    if fid == "WS05-MP-COMBAT-4":
        return {
            "forge": {**forge_gate, "interaction": "Forge attack frame exposes multiple legal defenders with Grizzly Bears attacker/blocker scenario"},
            "xmage": {"players": 4, "native_test": "multiplayerMultipleDefenders4P", "interaction": "Grizzly Bears attacks player B and Runeclaw Bear attacks player C"},
            "setup_difference": "different attacker set, defender mapping and combat transcript",
        }
    if fid in {"RNG_RULES_TAPE", "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS", "REPLAY_STATE_HASHES"}:
        return {
            "forge": {**forge_gate, "replay_scenario": "WS25/WS23 Gate-D broad scenario", "rng_source": "FlipCoinEffect/MyRandom"},
            "xmage": {**xmage_scenario, "replay_scenario": "WS26-REPLAY-GOBLIN-BOMB", "notable_object": "Goblin Bomb"},
            "setup_difference": "entire replay scenario and rules-randomness interaction differ",
        }
    if fid == "CARD_02":
        return {
            "forge": {**forge_gate, "interaction": "Rograkh is moved through hand-to-command replacement then cast; commander cast count asserted"},
            "xmage": {"players": 4, "native_test": "actualRograkhCommanderCast", "interaction": "Rograkh begins in command zone, is cast, and 0/1 asserted"},
            "setup_difference": "different initial zone path and asserted discriminator set",
        }
    raise KeyError(fid)


def build(args: argparse.Namespace) -> None:
    forge_dir = Path(args.forge_dir)
    xmage_dir = Path(args.xmage_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    forge_common = json.loads((forge_dir / "final/COMMON_135_FINAL.json").read_text())
    forge_rows = forge_common["rows"]
    forge_by = {r["fixture_id"]: r for r in forge_rows}
    assert len(forge_rows) == 135 and len(forge_by) == 135

    xmage_pass = set(SHARED) | set(XMAGE_ONLY)
    xmage_unsupported = set(forge_by) - xmage_pass
    assert len(xmage_pass) == 34 and len(xmage_unsupported) == 101 and not (xmage_pass & xmage_unsupported)

    forge_pass = {fid for fid, r in forge_by.items() if r["status"] == "PASS"}
    assert len(forge_pass) == 34
    assert forge_pass & xmage_pass == set(SHARED)
    assert forge_pass - xmage_pass == set(FORGE_ONLY)
    assert xmage_pass - forge_pass == set(XMAGE_ONLY)
    assert len(forge_pass | xmage_pass) == 50

    ws22 = json.loads((xmage_dir / "WS22_REGRESSION_RESULTS.json").read_text())
    ws22_by = {r["fixture_id"]: r for r in ws22["fixture_results"]}
    native = json.loads((xmage_dir / "NATIVE_REPRESENTATIVE_RESULTS.json").read_text())
    native_by = {r["fixture_id"]: r for r in native["fixture_results"]}
    gate = json.loads((xmage_dir / "WS26_RUNTIME_GATE.json").read_text())
    replay1 = json.loads((xmage_dir / "REPLAY_CAPTURE_1.json").read_text())
    replay2 = json.loads((xmage_dir / "REPLAY_CAPTURE_2.json").read_text())

    source_lock = {
        "schema_version": "ws28-source-lock/1.0.0",
        "locked_on": "2026-08-30",
        "protocol": PROTOCOL,
        "common_denominator": 135,
        "common_manifest_sha256": MANIFEST_SHA256,
        "neutral_base_main": args.neutral_base,
        "forge": {
            "commander_lab_branch": "ws25/forge-broad-behavioral-qualification",
            "commander_lab_head": FORGE_HEAD,
            "pr": 140,
            "engine_repository": "Card-Forge/forge",
            "engine_commit": FORGE_ENGINE,
            "engine_tree": FORGE_TREE,
            "fresh_actions_run_id": int(args.forge_run_id),
            "fresh_actions_job_id": int(args.forge_job_id),
            "fresh_artifact_id": int(args.forge_artifact_id),
            "fresh_artifact_sha256": args.forge_artifact_sha256,
            "internal_evidence_sha256": {
                "COMMON_135_FINAL.json": file_sha(forge_dir / "final/COMMON_135_FINAL.json"),
                "REPLAY_EVIDENCE.json": file_sha(forge_dir / "REPLAY_EVIDENCE.json"),
                "PLAYER_COUNT_MATRIX.json": file_sha(forge_dir / "PLAYER_COUNT_MATRIX.json"),
                "EXACT_GATE_D_FIXTURE_MATRIX.json": file_sha(forge_dir / "EXACT_GATE_D_FIXTURE_MATRIX.json"),
            },
        },
        "xmage": {
            "commander_lab_branch": "ws26/xmage-scenario-replay-viability",
            "behavioral_head": XMAGE_HEAD,
            "pr": 141,
            "engine_repository": "moeendres-png/mage",
            "engine_commit": XMAGE_ENGINE,
            "engine_tree": XMAGE_TREE,
            "fresh_actions_run_id": int(args.xmage_run_id),
            "fresh_actions_job_id": int(args.xmage_job_id),
            "fresh_artifact_id": int(args.xmage_artifact_id),
            "fresh_artifact_sha256": args.xmage_artifact_sha256,
            "internal_evidence_sha256": {
                "WS22_REGRESSION_RESULTS.json": file_sha(xmage_dir / "WS22_REGRESSION_RESULTS.json"),
                "WS26_RUNTIME_GATE.json": file_sha(xmage_dir / "WS26_RUNTIME_GATE.json"),
                "REPLAY_CAPTURE_1.json": file_sha(xmage_dir / "REPLAY_CAPTURE_1.json"),
                "REPLAY_CAPTURE_2.json": file_sha(xmage_dir / "REPLAY_CAPTURE_2.json"),
                "NATIVE_REPRESENTATIVE_RESULTS.json": file_sha(xmage_dir / "NATIVE_REPRESENTATIVE_RESULTS.json"),
            },
        },
    }
    (out_dir / "WS28_SOURCE_LOCK.json").write_text(json.dumps(source_lock, indent=2, sort_keys=True) + "\n")

    shared_rows = []
    transcript_rows = []
    for fid in SHARED:
        sig = shared_signature(fid)
        authority = "DIRECT_WIZARDS_AUTHORITY_REVERIFIED" if fid == "CARD_02" else "NOT_REQUIRED_NO_COMPARABLE_RULES_DISAGREEMENT"
        row = {
            "fixture_id": fid,
            "forge_status": "PASS",
            "xmage_status": "PASS",
            "both_executed": True,
            "semantic_setup_equivalent": False,
            "semantic_decisions_equivalent": False,
            "result_comparison": "NOT_COMPARABLE_SETUP_NONISOMORPHIC",
            "differential_verdict": "SETUP_NONISOMORPHIC",
            "authority_state": authority,
            "direct_defect_classification": None,
            "semantic_signature_sha256": sha(sig),
            "forge_fresh_artifact_sha256": args.forge_artifact_sha256,
            "xmage_fresh_artifact_sha256": args.xmage_artifact_sha256,
        }
        shared_rows.append(row)
        transcript_rows.append({"fixture_id": fid, "normalized_semantic_signature": sig, "sha256": sha(sig)})
    (out_dir / "WS28_STRICT_18_DIFFERENTIAL.json").write_text(json.dumps({
        "schema_version": "ws28-strict-18/1.0.0",
        "starting_independent_shared_pass": 18,
        "differential_agreement_pass": 0,
        "verdict_counts": {"SETUP_NONISOMORPHIC": 18},
        "rows": shared_rows,
    }, indent=2, sort_keys=True) + "\n")
    (out_dir / "WS28_NORMALIZED_SEMANTIC_TRANSCRIPTS.json").write_text(json.dumps({
        "schema_version": "ws28-normalized-semantic-transcripts/1.0.0",
        "note": "These are provider-neutral semantic signatures used to determine isomorphism; raw provider artifacts remain preserved by Actions artifact id/digest in WS28_SOURCE_LOCK.json.",
        "rows": transcript_rows,
    }, indent=2, sort_keys=True) + "\n")

    cross_rows = []
    for fid in FORGE_ONLY:
        raw = ws22_by[fid]
        cross_rows.append({
            "fixture_id": fid,
            "direction": "FORGE_TO_XMAGE",
            "source_candidate_status": "PASS",
            "opposite_candidate_final_status": "UNSUPPORTED",
            "ws22_raw_status": raw["verdict"],
            "attempted_on_exact_candidate": True,
            "behavior_executed_on_opposite_candidate": False,
            "differential_verdict": "CANDIDATE_UNSUPPORTED",
            "direct_defect_classification": "PROVIDER_DEFECT_XMAGE",
            "reason": "Exact WS26 finalist accounting leaves this frozen ID unsupported; no provider-neutral fully specified initial-state/decision transcript exists that can be materialized without selecting one provider's implicit scenario as canonical.",
            "opposite_evidence_row_sha256": sha(raw),
        })
    for fid in XMAGE_ONLY:
        raw = forge_by[fid]
        authority = "DIRECT_WIZARDS_AUTHORITY_REVERIFIED" if fid in {"CARD_04", "CARD_24"} else "NOT_REQUIRED_NO_COMPARABLE_RULES_DISAGREEMENT"
        cross_rows.append({
            "fixture_id": fid,
            "direction": "XMAGE_TO_FORGE",
            "source_candidate_status": "PASS",
            "opposite_candidate_final_status": raw["status"],
            "attempted_on_exact_candidate": True,
            "behavior_executed_on_opposite_candidate": False,
            "differential_verdict": "CANDIDATE_UNSUPPORTED",
            "authority_state": authority,
            "direct_defect_classification": "PROVIDER_DEFECT_FORGE",
            "reason": "Exact WS25 finalist accounting does not execute this semantic fixture. CARD_04/CARD_24 authority is no longer the WS28 blocker; the remaining blocker is exact provider/fixture materialization.",
            "opposite_evidence_row_sha256": sha(raw),
        })
    (out_dir / "WS28_CROSS_MATERIALIZATION_RESULTS.json").write_text(json.dumps({
        "schema_version": "ws28-cross-materialization/1.0.0",
        "forge_to_xmage": {"attempted": 16, "new_pass": 0, "unsupported": 16},
        "xmage_to_forge": {"attempted": 16, "new_pass": 0, "unsupported": 16},
        "rows": cross_rows,
    }, indent=2, sort_keys=True) + "\n")

    matrix = []
    for fr in forge_rows:
        fid = fr["fixture_id"]
        xs = "PASS" if fid in xmage_pass else "UNSUPPORTED"
        if fid in SHARED:
            verdict = "SETUP_NONISOMORPHIC"
            both_executed = True
            setup_eq = False
            decision_eq = False
            comparison = "NOT_COMPARABLE_SETUP_NONISOMORPHIC"
            defect = None
        elif fid in FORGE_ONLY:
            verdict = "CANDIDATE_UNSUPPORTED"
            both_executed = False
            setup_eq = False
            decision_eq = False
            comparison = "XMAGE_EXACT_FIXTURE_NOT_EXECUTED"
            defect = "PROVIDER_DEFECT_XMAGE"
        elif fid in XMAGE_ONLY:
            verdict = "CANDIDATE_UNSUPPORTED"
            both_executed = False
            setup_eq = False
            decision_eq = False
            comparison = "FORGE_EXACT_FIXTURE_NOT_EXECUTED"
            defect = "PROVIDER_DEFECT_FORGE"
        elif fr["category"] == "actual_card" and fid not in DIRECT_CARD_AUTHORITY:
            verdict = "AUTHORITY_BLOCKED"
            both_executed = False
            setup_eq = False
            decision_eq = False
            comparison = "AUTHORITY_BLOCKED_PENDING_WS29"
            defect = "AUTHORITY_UNKNOWN"
        else:
            verdict = "CANDIDATE_UNSUPPORTED"
            both_executed = False
            setup_eq = False
            decision_eq = False
            comparison = "NO_COMPARABLE_DUAL_RUNTIME"
            defect = None

        if fid in DIRECT_CARD_AUTHORITY:
            authority = "DIRECT_WIZARDS_AUTHORITY_REVERIFIED"
        elif fr["category"] == "actual_card":
            authority = "AUTHORITY_BLOCKED_PENDING_WS29"
        else:
            authority = "NOT_ADJUDICATED_NO_COMPARABLE_RULES_DISAGREEMENT"

        forge_specific_hash = sha(fr)
        xmage_source_row = ws22_by.get(fid)
        if fid in native_by:
            xmage_specific = native_by[fid]
        else:
            xmage_specific = xmage_source_row or {"fixture_id": fid, "final_status": xs}
        matrix.append({
            "fixture_id": fid,
            "category": fr["category"],
            "player_count": fr.get("player_count"),
            "forge_status": fr["status"],
            "xmage_status": xs,
            "forge_exact_source": {
                "commander_lab_head": FORGE_HEAD,
                "forge_commit": FORGE_ENGINE,
                "forge_tree": FORGE_TREE,
                "fresh_actions_run_id": int(args.forge_run_id),
                "fresh_actions_job_id": int(args.forge_job_id),
            },
            "xmage_exact_source": {
                "commander_lab_behavioral_head": XMAGE_HEAD,
                "xmage_commit": XMAGE_ENGINE,
                "xmage_tree": XMAGE_TREE,
                "fresh_actions_run_id": int(args.xmage_run_id),
                "fresh_actions_job_id": int(args.xmage_job_id),
            },
            "both_executed": both_executed,
            "semantic_setup_equivalent": setup_eq,
            "semantic_decisions_equivalent": decision_eq,
            "result_comparison": comparison,
            "differential_verdict": verdict,
            "authority_state": authority,
            "direct_defect_classification": defect,
            "evidence_hashes": {
                "forge_fixture_evidence_sha256": forge_specific_hash,
                "xmage_fixture_evidence_sha256": sha(xmage_specific),
                "forge_fresh_artifact_sha256": args.forge_artifact_sha256,
                "xmage_fresh_artifact_sha256": args.xmage_artifact_sha256,
            },
        })

    assert len(matrix) == 135 and len({r["fixture_id"] for r in matrix}) == 135
    counts: dict[str, int] = {}
    for r in matrix:
        counts[r["differential_verdict"]] = counts.get(r["differential_verdict"], 0) + 1
    assert counts == {"SETUP_NONISOMORPHIC": 18, "CANDIDATE_UNSUPPORTED": 91, "AUTHORITY_BLOCKED": 26}, counts
    matrix_doc = {
        "schema_version": "ws28-finalist-matrix/1.0.0",
        "protocol": PROTOCOL,
        "denominator": 135,
        "manifest_sha256": MANIFEST_SHA256,
        "starting_pass_counts": {"forge": 34, "xmage": 34, "shared": 18, "forge_only": 16, "xmage_only": 16, "union": 50, "neither": 85},
        "strict_differential_counts": counts,
        "rows": matrix,
    }
    (out_dir / "WS28_FINALIST_MATRIX_135.json").write_text(json.dumps(matrix_doc, indent=2, sort_keys=True) + "\n")

    # Replay/checkpoint evidence: retain both candidate-native hashes rather than pretending they are cross-provider equal.
    forge_replay = json.loads((forge_dir / "REPLAY_EVIDENCE.json").read_text())
    xh1 = replay1.get("hashes", {})
    xh2 = replay2.get("hashes", {})
    replay_out = {
        "schema_version": "ws28-replay-checkpoint-evidence/1.0.0",
        "differential_verdict": "SETUP_NONISOMORPHIC",
        "forge": {
            "scenario_sha256": sha(json.loads((forge_dir / "RUNTIME_PROOF.json").read_text()).get("scenario")),
            "decision_tape_sha256": forge_replay["decision_tape_semantic_sha256"],
            "rules_rng_tape_sha256": sha(json.loads((forge_dir / "RUNTIME_PROOF.json").read_text()).get("rng_proof")),
            "event_tape_sha256": forge_replay["event_tape_sha256"],
            "checkpoint_hashes": forge_replay["state_checkpoint_hashes"],
            "terminal_state_sha256": forge_replay["state_checkpoint_hashes"]["terminal_snapshot"],
        },
        "xmage": {
            "initial_semantic_state_sha256": sha(replay1.get("scenario")),
            "decision_tape_sha256": xh1.get("decision") or sha(replay1.get("decision_tape")),
            "rules_rng_tape_sha256": xh1.get("rules_rng") or sha(replay1.get("rules_rng_tape")),
            "event_tape_sha256": xh1.get("event") or sha(replay1.get("event_tape")),
            "checkpoints_sha256": xh1.get("checkpoints") or sha(replay1.get("checkpoints")),
            "terminal_state_sha256": xh1.get("final_state") or sha(replay1.get("final_state")),
            "fresh_process_second_hashes": xh2,
        },
    }
    replay_out["complete_differential_result_sha256"] = sha(replay_out)
    (out_dir / "WS28_REPLAY_CHECKPOINT_EVIDENCE.json").write_text(json.dumps(replay_out, indent=2, sort_keys=True) + "\n")

    semantic_register = {
        "schema_version": "ws28-semantic-disagreement-register/1.0.0",
        "engine_semantic_disagreements": [],
        "note": "No engine-semantic disagreement is adjudicable because no shared fixture cleared setup isomorphism.",
    }
    provider_register = {
        "schema_version": "ws28-provider-disagreement-register/1.0.0",
        "forge_to_xmage_provider_defects": FORGE_ONLY,
        "xmage_to_forge_provider_defects": XMAGE_ONLY,
        "shared_setup_nonisomorphic": SHARED,
        "note": "The asymmetric lists are provider/fixture-materialization defects, not demonstrated Rules-Core defects.",
    }
    defect_register = {
        "schema_version": "ws28-direct-rules-defect-register/1.0.0",
        "xmage_rules_defects": [],
        "forge_rules_defects": [],
        "both_rules_defects": [],
        "provider_defect_xmage": FORGE_ONLY,
        "provider_defect_forge": XMAGE_ONLY,
        "authority_unknown_cards": [f"CARD_{i:02d}" for i in range(1, 30) if f"CARD_{i:02d}" not in DIRECT_CARD_AUTHORITY],
        "rules_defect_conclusion": "NONE_IDENTIFIED_NOT_EQUIVALENT_TO_RULES_PASS",
    }
    authority_register = {
        "schema_version": "ws28-authority-dependency-register/1.0.0",
        "direct_authority_reverified": {
            "CARD_02": "Rograkh, Son of Rohgahh",
            "CARD_04": "Kediss, Emberclaw Familiar",
            "CARD_24": "Warstorm Surge",
        },
        "pending_ws29": [f"CARD_{i:02d}" for i in range(1, 30) if f"CARD_{i:02d}" not in DIRECT_CARD_AUTHORITY],
        "engine_disagreements_requiring_adjudication": [],
    }
    for name, obj in [
        ("WS28_SEMANTIC_DISAGREEMENT_REGISTER.json", semantic_register),
        ("WS28_PROVIDER_DISAGREEMENT_REGISTER.json", provider_register),
        ("WS28_DIRECT_RULES_DEFECT_REGISTER.json", defect_register),
        ("WS28_AUTHORITY_DEPENDENCY_REGISTER.json", authority_register),
    ]:
        (out_dir / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")

    summary = {
        "schema_version": "ws28-summary/1.0.0",
        "workstream_completion": "PASS",
        "starting_independent_intersection": 18,
        "new_cross_materialized_forge_to_xmage": 0,
        "new_cross_materialized_xmage_to_forge": 0,
        "final_independent_pass_intersection": 18,
        "final_differential_verified_semantic_intersection": 0,
        "strict_shared_verdicts": {"SETUP_NONISOMORPHIC": 18},
        "cross_materialization": {"CANDIDATE_UNSUPPORTED": 32},
        "engine_semantic_disagreements": 0,
        "direct_rules_defects_identified": 0,
        "architecture_winner_selected": False,
        "production_rules_core": "UNKNOWN",
        "primary_blocker": "The frozen 135-row manifest identifies obligations but does not materialize a single provider-neutral semantic initial state/decision transcript for the 50 known-PASS union; existing candidate PASS evidence uses different scenarios.",
    }
    (out_dir / "WS28_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    # Write hashes last; exclude itself.
    lines = []
    for path in sorted(out_dir.glob("*")):
        if path.name == "WS28_SHA256SUMS" or not path.is_file():
            continue
        lines.append(f"{file_sha(path)}  {path.name}")
    (out_dir / "WS28_SHA256SUMS").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--forge-dir", required=True)
    p.add_argument("--xmage-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--neutral-base", required=True)
    p.add_argument("--forge-run-id", required=True)
    p.add_argument("--forge-job-id", required=True)
    p.add_argument("--forge-artifact-id", required=True)
    p.add_argument("--forge-artifact-sha256", required=True)
    p.add_argument("--xmage-run-id", required=True)
    p.add_argument("--xmage-job-id", required=True)
    p.add_argument("--xmage-artifact-id", required=True)
    p.add_argument("--xmage-artifact-sha256", required=True)
    build(p.parse_args())
