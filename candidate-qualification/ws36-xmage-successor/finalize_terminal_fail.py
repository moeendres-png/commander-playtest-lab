#!/usr/bin/env python3
"""Generate the complete WS-36 terminal evidence suite after a proven stop condition.

This finalizer never promotes historical or source-derived evidence to runtime
PASS.  A mandatory provider capability blocker makes 107/107 impossible under
the immutable contract, so every record receives one explicit terminal result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

WS34_COMMIT = "b370c044e6410504eb92547a35ea55cdfa2b291b"
WS34_TREE = "c4f65c1b3fcf843cbf34242da36131475d6bbce4"
WS34_RUN = 33580331547
WS34_ARTIFACT = 9828355438
WS34_ARTIFACT_SHA256 = "eb983fc2a70fd42102817ac79ea8ebe241fffede19035f2d54e461b1ba2aeaa5"
WS34_RESULTS_SHA256 = "83970cfaf28f98dd1682340f5acbecb474c76853e98c8615fd26158de054c0c6"
WS32_COMMIT = "038d0f38635eecee4e331c99af41f148de267a26"
WS32_TREE = "0d160128119f2bad30b220a17c43419b50b7edbe"
WS32_BUNDLE = "61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b"
WS32_MATERIALIZATION = "ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23"
WS32_FILE_SHA256 = "0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"
UPSTREAM_COMMIT = "8f8b9828a8e236ab1435b2ffe4c3023125763c4a"
UPSTREAM_TREE = "732847b8b7c1df138378e421817289e32a2cad99"
COMMANDER_WATCHER_BLOB = "0f87de7885cb33faf493613882c3ab7ed053a335"
TERMINAL_IDS = {"WS05-CMD-TAX-2", "WS05-CMD-TAX-4", "WS05-CMD-PARTNER-TAX"}
AF_FAMILY = {
    "AF04": {"pilot_boundary", "pilot_boundary_negative"},
    "AF05": {"hidden_information"},
    "AF06": {"micro_rules"},
    "AF08": {"multiplayer_commander"},
    "AF09": {"replay_rng"},
}
AF_DENOM = {"AF04": 24, "AF05": 20, "AF06": 17, "AF08": 36, "AF09": 5}


def canonical_bytes(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(v: Any) -> str:
    return hashlib.sha256(canonical_bytes(v)).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--capability", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    census = json.loads(args.census.read_text())
    capability = json.loads(args.capability.read_text())
    if census["denominator"] != 107 or census["unique_fixture_ids"] != 107:
        raise SystemExit("WS36_FINAL_DENOMINATOR_FAILURE")
    if not capability.get("terminal_provider_blocker_established"):
        raise SystemExit("WS36_FINALIZER_REQUIRES_PROVEN_STOP_CONDITION")

    provider_commit = os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD")
    provider_tree = git("rev-parse", f"{provider_commit}^{{tree}}")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0")) or None

    source_lock = {
        "schema_version": "commander-lab.ws36-source-lock/1.0.0",
        "workstream": "WS-36",
        "provider_branch": "ws36/xmage-successor-provider-remediation",
        "provider_runtime_commit": provider_commit,
        "provider_runtime_tree": provider_tree,
        "ws34_terminal": {
            "commit": WS34_COMMIT, "tree": WS34_TREE, "run_id": WS34_RUN,
            "artifact_id": WS34_ARTIFACT, "artifact_sha256": WS34_ARTIFACT_SHA256,
            "results_sha256": WS34_RESULTS_SHA256,
        },
        "ws32": {
            "contract": "commander-lab.semantic-fixture-materialization/1.0.2",
            "freeze_commit": WS32_COMMIT, "freeze_tree": WS32_TREE,
            "freeze_bundle_sha256": WS32_BUNDLE,
            "canonical_materialization_digest": WS32_MATERIALIZATION,
            "materialization_file_sha256": WS32_FILE_SHA256,
        },
        "xmage": {"repository": "moeendres-png/mage", "commit": XMAGE_COMMIT, "tree": XMAGE_TREE},
        "fresh_upstream_observation": {"repository": "magefree/mage", "commit": UPSTREAM_COMMIT, "tree": UPSTREAM_TREE},
        "workflow_run_id": run_id,
        "historical_pass_imported": False,
    }
    write_json(out / "WS36_SOURCE_LOCK.json", source_lock)

    upstream = {
        "schema_version": "commander-lab.ws36-xmage-upstream-delta-audit/1.0.0",
        "retained": {"commit": XMAGE_COMMIT, "tree": XMAGE_TREE},
        "observed_upstream": {"commit": UPSTREAM_COMMIT, "tree": UPSTREAM_TREE},
        "successor_relevant_domains": [
            "state_construction", "player_decision_apis", "commander_support", "stack_combat_construction",
            "uuid_identity", "hidden_information", "rng_replay", "multiplayer", "cleanup_playerlist",
        ],
        "commander_plays_count_watcher_blob_retained": COMMANDER_WATCHER_BLOB,
        "commander_plays_count_watcher_blob_upstream": COMMANDER_WATCHER_BLOB,
        "terminal_blocker_fixed_upstream": False,
        "pin_decision": "RETAIN_77d7646",
        "reason": "No successor-relevant evidence justifies Rules-sensitive drift; the terminal commander-history restore gap is unchanged in observed upstream.",
    }
    write_json(out / "WS36_XMAGE_UPSTREAM_DELTA_AUDIT.json", upstream)

    defects = {
        "schema_version": "commander-lab.ws36-defect-remediation-ledger/1.0.0",
        "inherited": {
            "WS34-XMAGE-SETUP": {"status": "OPEN_TERMINAL", "remediation": "tapped snapshot construction code added; complete state loader remains blocked by commander history restore capability"},
            "WS34-XMAGE-CORE-UUID": {"status": "REMEDIATED_CI_VERIFIED", "remediation": "DecisionFrame maps actor-safe option ids bijectively to native XMage option ids before native submission"},
            "WS34-XMAGE-CARD02-IDENTITY": {"status": "CODE_REMEDIATED_NOT_FULL_RECORD_RERUN", "remediation": "native alias map scoped to current projection frame to permit zone-incarnation changes without semantic alias collision"},
            "WS34-ADAPTER-TRANSACTION-COVERAGE": {"status": "OPEN_AFTER_STOP_CONDITION"},
            "WS34-ADAPTER-RNG-SEED": {"status": "REMEDIATED_SCHEMA_VERIFIED_NOT_AF09_RERUN", "remediation": "v1.0.2 SCENARIO_SEED binding used; no frozen rules_seed assumption"},
            "WS34-XMAGE-PILOT-CHOOSE-USE-STATE": {"status": "CODE_REMEDIATED_NOT_FULL_RECORD_RERUN", "remediation": "NATIVE_STATE_LOAD normalizes requested tapped snapshot using XMage Permanent.setTapped and validates it"},
            "WS34-PRIVACY-KNOWN-DECK-INVERSION": {"status": "CLOSED_REGRESSION_PRESERVED_CI"},
        },
        "new": {
            "WS36-XMAGE-COMMANDER-HISTORY-RESTORE": {
                "status": "TERMINAL_BLOCKER",
                "classification": "XMAGE_PROVIDER_DEFECT",
                "affected_fixture_ids": sorted(TERMINAL_IDS),
                "evidence": capability,
            }
        },
    }
    write_json(out / "WS36_WS34_DEFECT_REMEDIATION_LEDGER.json", defects)

    construction_rows = []
    digest_rows = []
    transaction_rows = []
    result_rows = []
    for row in census["records"]:
        fid = row["fixture_id"]
        terminal = fid in TERMINAL_IDS
        final = "BLOCKED_XMAGE_PROVIDER_DEFECT_COMMANDER_CAST_HISTORY" if terminal else "NOT_RUN_AFTER_MANDATORY_PROVIDER_STOP_CONDITION"
        construction_rows.append({
            "fixture_id": fid,
            "materialization_digest": row["materialization_digest"],
            "requested_state_digest": row["requested_state_digest"],
            "entry_mode": row["entry_mode"],
            "ws34_construction_blockers": row["construction_blockers_ws34"],
            "ws36_terminal_construction_blocker": "COMMANDER_CAST_HISTORY_RESTORE_UNAVAILABLE" if terminal else None,
            "native_construction_result": "FAIL_PROVIDER_CAPABILITY" if terminal else "NOT_RUN_AFTER_STOP_CONDITION",
            "runtime_credit": "NO",
        })
        digest_rows.append({
            "fixture_id": fid,
            "requested_state_digest": row["requested_state_digest"],
            "normalized_constructed_state_digest": None,
            "equal": False,
            "result": "CANNOT_CONSTRUCT_REQUIRED_NATIVE_HISTORY" if terminal else "NOT_RUN_AFTER_STOP_CONDITION",
            "runtime_credit": "NO",
        })
        transaction_rows.append({
            "fixture_id": fid,
            "native_operations": row["native_operations"],
            "decision_families": row["decision_families"],
            "executor_completion": "BLOCKED_BEFORE_RUNTIME" if terminal else "NOT_COMPLETED_AFTER_STOP_CONDITION",
            "runtime_result": final,
        })
        result_rows.append({
            "fixture_id": fid,
            "fixture_family": row["fixture_family"],
            "materialization_digest": row["materialization_digest"],
            "requested_state_digest": row["requested_state_digest"],
            "constructed_state_digest": None,
            "native_execution_entered": False,
            "decision_tape": [], "event_tape": [], "checkpoints": [],
            "terminal_semantic_state": None,
            "postcondition_result": "NOT_EVALUATED",
            "successor_runtime_credit": "NO",
            "final_result": final,
            "failure_taxonomy": "XMAGE_PROVIDER_DEFECT" if terminal else "DEPENDENCY_STOP_CONDITION",
            "historical_pass_imported": False,
        })

    native_matrix = {
        "schema_version": "commander-lab.ws36-native-construction-matrix/1.0.0",
        "denominator": 107, "unique_fixture_ids": 107,
        "terminal_blocker_fixture_ids": sorted(TERMINAL_IDS), "records": construction_rows,
    }
    write_json(out / "WS36_NATIVE_CONSTRUCTION_MATRIX_107.json", native_matrix)
    write_json(out / "WS36_REQUESTED_CONSTRUCTED_DIGEST_RESULTS_107.json", {
        "schema_version": "commander-lab.ws36-requested-constructed-digests/1.0.0",
        "denominator": 107, "equal_pass_count": 0, "records": digest_rows,
    })

    identity = {
        "schema_version": "commander-lab.ws36-decision-identity-mapping-audit/1.0.0",
        "semantic_and_native_domains_separate": True,
        "decision_frame_bijective_binding_implemented": True,
        "stale_mapping_fail_closed": True,
        "wrong_actor_fail_closed": True,
        "native_uuid_actor_exposure_prohibited": True,
        "known_deck_inversion_regression_preserved": True,
        "ci_regression_status": "PASS_AT_SCOPED_IDENTITY_WORKFLOW",
        "full_107_runtime_status": "NOT_RUN_AFTER_STOP_CONDITION",
        "qualification_credit": "NO",
    }
    write_json(out / "WS36_DECISION_IDENTITY_MAPPING_AUDIT.json", identity)
    write_json(out / "WS36_TRANSACTION_COVERAGE_107.json", {
        "schema_version": "commander-lab.ws36-transaction-coverage/1.0.0", "denominator": 107,
        "unhandled_complete_denominator": True, "records": transaction_rows,
    })

    hidden = {
        "schema_version": "commander-lab.ws36-hidden-information-results/1.0.0",
        "af_gate": "AF05", "denominator": 20, "runtime_pass": 0,
        "narrow_known_deck_inversion_regression": "PASS_CI",
        "complete_successor_denominator_executed": False,
        "final_verdict": "FAIL_NOT_QUALIFIED_AFTER_TERMINAL_PROVIDER_STOP_CONDITION",
        "historical_pass_imported": False,
    }
    rng = {
        "schema_version": "commander-lab.ws36-rng-replay-results/1.0.0",
        "af_gate": "AF09", "denominator": 5, "runtime_pass": 0,
        "rules_randomness_schema_binding": "SCENARIO_SEED",
        "old_rules_seed_keyerror_classification": "QUALIFICATION_INFRA_DEFECT_REMEDIATED",
        "complete_successor_denominator_executed": False,
        "final_verdict": "FAIL_NOT_QUALIFIED_AFTER_TERMINAL_PROVIDER_STOP_CONDITION",
        "historical_pass_imported": False,
    }
    card02 = {
        "schema_version": "commander-lab.ws36-card02-result/1.0.0",
        "fixture_id": "CARD_02", "runtime_pass": False,
        "identity_alias_code_remediation": "IMPLEMENTED",
        "complete_v1_0_2_record_rerun": False,
        "final_result": "NOT_RUN_AFTER_MANDATORY_PROVIDER_STOP_CONDITION",
        "successor_runtime_credit": "NO",
    }
    write_json(out / "WS36_HIDDEN_INFORMATION_RESULTS.json", hidden)
    write_json(out / "WS36_RNG_REPLAY_RESULTS.json", rng)
    write_json(out / "WS36_CARD02_RESULT.json", card02)

    successor = {
        "schema_version": "commander-lab.ws36-successor-results/1.0.0",
        "workstream_status": "COMPLETE",
        "candidate_qualification": "FAIL_NOT_QUALIFIED",
        "terminal_stop_condition": "A_NATIVE_PROVIDER_IMPOSSIBILITY_WITH_CURRENT_XMAGE_API",
        "denominator": 107, "unique_fixture_ids": 107,
        "successor_runtime_credit": {"PASS": 0, "NO_CREDIT": 107, "historical_pass_imported": False},
        "terminal_provider_blocker_fixture_ids": sorted(TERMINAL_IDS),
        "records": result_rows,
    }
    write_json(out / "WS36_SUCCESSOR_RESULTS_107.json", successor)

    af_rows = []
    for gate, families in AF_FAMILY.items():
        ids = [r["fixture_id"] for r in census["records"] if r["fixture_family"] in families]
        if len(ids) != AF_DENOM[gate]:
            raise SystemExit(f"WS36_AF_DENOMINATOR_MISMATCH:{gate}:{len(ids)}")
        af_rows.append({
            "gate_id": gate, "denominator": len(ids), "runtime_pass": 0,
            "fixture_ids": sorted(ids), "final_verdict": "FAIL_NOT_QUALIFIED",
            "freeze_satisfying": False, "historical_pass_imported": False,
        })
    af = {"schema_version": "commander-lab.ws36-af-results/1.0.0", "architecture_freeze": af_rows}
    write_json(out / "WS36_AF_RESULTS.json", af)

    evidence_index = {
        "schema_version": "commander-lab.ws36-evidence-index/1.0.0",
        "workflow_run_id": run_id,
        "provider_runtime_commit": provider_commit,
        "provider_runtime_tree": provider_tree,
        "evidence_stage": "TERMINAL_FAIL_CLOSED",
        "required_engine_change": capability["required_engine_side_remediation"],
        "artifact_identity": "TO_BE_FILLED_FROM_GITHUB_ACTIONS_METADATA_AFTER_UPLOAD",
        "files": [],
    }
    validation = {
        "schema_version": "commander-lab.ws36-validation/1.0.0",
        "workstream_complete": True,
        "candidate_qualification": "FAIL_NOT_QUALIFIED",
        "gates": {
            "G36-01": "PASS", "G36-02": "PASS", "G36-03": "FAIL_PROVIDER_CAPABILITY",
            "G36-04": "PASS_STATIC_AND_REGRESSION", "G36-05": "NOT_FULL_DENOMINATOR",
            "G36-06": "NOT_FULL_DENOMINATOR", "G36-07": "NOT_FULL_DENOMINATOR",
            "G36-08": "PARTIAL_REMEDIATION_NOT_FULL_DENOMINATOR", "G36-09": "NOT_FULL_DENOMINATOR",
            "G36-10": "PASS", "G36-11": "PASS", "G36-12": "PASS_TERMINAL_ACCOUNTING",
        },
        "exact_terminal_accounting": {"records": 107, "unique": 107, "pass": 0, "no_credit": 107},
        "unknown_is_pass": False, "not_run_is_pass": False, "historical_pass_imported": False,
        "architecture_freeze_granted": False, "af07_granted": False,
        "actual_card_runtime_unblocked": False,
    }
    write_json(out / "WS36_VALIDATION.json", validation)

    # Index all machine-readable evidence except the index itself and checksum file.
    evidence_index["files"] = sorted(p.name for p in out.iterdir() if p.is_file() and p.suffix == ".json")
    write_json(out / "WS36_EVIDENCE_INDEX.json", evidence_index)

    handoff = f"""# WS36 FINAL HANDOFF\n\n## Source Lock\n\nCommander Lab qualification runtime commit: `{provider_commit}`  \nTree: `{provider_tree}`  \nXMage: `{XMAGE_COMMIT}` / `{XMAGE_TREE}`  \nWS-32: `{WS32_COMMIT}` / `{WS32_TREE}`  \nContract: `commander-lab.semantic-fixture-materialization/1.0.2`  \nCanonical materialization: `{WS32_MATERIALIZATION}`  \nWorkflow run: `{run_id}`\n\n## Work Completed\n\nWS-34 UUID-domain, CARD_02 identity-domain, v1.0.2 RNG-schema and PILOT_CHOOSE_USE tapped-snapshot provider defects were root-caused and code-remediated where legal. The exact 107-record frozen denominator was re-censused. A pin-bound terminal capability audit established that the three mandatory commander-tax records require prior command-zone cast history as starting state but the retained XMage API exposes no non-event state-restore path for `CommanderPlaysCountWatcher`.\n\n## New Findings\n\n`CommanderPlaysCountWatcher` stores command-zone cast counts in private maps, mutates them only from native `SPELL_CAST` / `LAND_PLAYED` events from the command zone, and exposes read-only count access. The same watcher blob is present at the freshly observed upstream commit `{UPSTREAM_COMMIT}`. Replaying fabricated historical casts/events is prohibited by WS-32/WS-36, and Commander Lab may not implement commander-tax semantics itself.\n\n## WS-34 Defect Closure\n\nSee `WS36_WS34_DEFECT_REMEDIATION_LEDGER.json`. `WS34-XMAGE-CORE-UUID` is remediated and scoped-CI verified. The known-deck inversion privacy regression remains closed. CARD_02 identity, RNG schema and PILOT_CHOOSE_USE construction received code remediation but no full-record v1.0.2 runtime credit after the mandatory terminal stop condition. Setup/transaction coverage remains terminally blocked.\n\n## Native Construction Results\n\nExact denominator: 107. Three mandatory records (`WS05-CMD-TAX-2`, `WS05-CMD-TAX-4`, `WS05-CMD-PARTNER-TAX`) cannot construct the frozen prior-command-zone-cast-count state with the retained native XMage API without either fabricated historical Rules events, private-state reflection, or an external commander-tax implementation. All are prohibited. No requested/constructed equality credit is granted.\n\n## Runtime Results\n\n107 records have one terminal accounting result: 3 `BLOCKED_XMAGE_PROVIDER_DEFECT_COMMANDER_CAST_HISTORY`; 104 `NOT_RUN_AFTER_MANDATORY_PROVIDER_STOP_CONDITION`. Runtime PASS: 0/107. Historical PASS imported: false.\n\n## AF04\n\n0/24 PASS. Final: FAIL_NOT_QUALIFIED.\n\n## AF05\n\n0/20 PASS. Narrow known-deck inversion regression remains PASS, but full AF05 was not promoted. Final: FAIL_NOT_QUALIFIED.\n\n## AF06\n\n0/17 PASS. Final: FAIL_NOT_QUALIFIED.\n\n## AF08\n\n0/36 PASS. Mandatory commander-tax records are within this denominator and establish the terminal provider blocker. Final: FAIL_NOT_QUALIFIED.\n\n## AF09\n\n0/5 successor PASS. `SCENARIO_SEED` infrastructure defect is code-remediated, but no historical or partial replay result is promoted. Final: FAIL_NOT_QUALIFIED.\n\n## CARD_02\n\nCode remediation for projection aliasing is present; complete v1.0.2 runtime record was not promoted after the terminal stop condition. Final: NO CREDIT.\n\n## Changes\n\nCommander Lab only. XMage source changed: **NO**. WS-32 changed: **NO**. WS-34/WS-35 changed: **NO**.\n\n## Tests / Evidence\n\nAll machine-readable evidence is SHA-256 sealed in `WS36_SHA256SUMS`. The GitHub Actions artifact metadata must be appended to this handoff after upload.\n\n## PASS / FAIL / UNKNOWN\n\n**COMPLETE / FAIL_NOT_QUALIFIED**. `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = false`. This is terminal for WS-36 under the current no-XMage-modification scope.\n\n## Defect Register\n\n- CONTRACT_DEFECT: none established.\n- QUALIFICATION_INFRA_DEFECT: old `rules_seed` assumption remediated; prior WS-34 constructed-state echo cannot be used as v1.0.2 credit.\n- XMAGE_PROVIDER_DEFECT: terminal `CommanderPlaysCountWatcher` state-restoration capability gap plus remaining unexecuted construction/transaction surfaces.\n- XMAGE_RULES_DEFECT: none established.\n- AUTHORITY_DEFECT: none established.\n\n## Remaining Blockers\n\nMinimum blocking change: XMage must expose a native state-restoration-safe API (or general serialized GameState restoration path) that restores per-commander/per-player command-zone cast counters without generating historical Rules events. WS-36 is not authorized to modify `moeendres-png/mage`.\n\n## Outputs\n\nSee `WS36_EVIDENCE_INDEX.json` and `WS36_SHA256SUMS`.\n\n## Dependencies Unblocked\n\nA new Actual-Card runtime workstream **may not** consume XMage as a qualified successor provider. WS-35 remains unchanged and must not be reopened.\n\n## Exact Next Action\n\nPreserve the exact terminal blocker(s), do not weaken WS-32, and identify the minimum next provider- or engine-side remediation required. The minimum next engine-side remediation is the native commander-cast-history restoration capability described above; after such an authorized XMage change, start a new successor-provider remediation/requalification workstream rather than rewriting WS-36 evidence.\n"""
    (out / "WS36_FINAL_HANDOFF.md").write_text(handoff, encoding="utf-8")

    # Seal everything except checksum file itself.
    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "WS36_SHA256SUMS")
    sums = []
    for p in files:
        sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (out / "WS36_SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({
        "workstream_status": "COMPLETE",
        "candidate_qualification": "FAIL_NOT_QUALIFIED",
        "denominator": 107,
        "terminal_blockers": sorted(TERMINAL_IDS),
        "provider_runtime_commit": provider_commit,
        "provider_runtime_tree": provider_tree,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
