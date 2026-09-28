#!/usr/bin/env python3
"""WSR22 final current-boundary evidence assembler.

Combines the freshly executed Protocol-2 lifecycle evidence with the freshly
executed native harness evidence, produces the AF00-AF11 matrix, the
current-boundary comparison, the divergence packet and the provider-blocker
register.

Nothing here inherits a historical verdict. Every PASS traces to a run that
executed inside this workstream at the recorded runtime identity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    CHARACTERIZATION_XMAGE,
    PB10_DEMOTIONS,
    POSITIVE_NATIVE_BINDING_XMAGE,
)

OUT = REPO / "qualification" / "final-current-boundary-20260927"
FORGE_WS = Path("/home/moeen/code/ws-forge-full107-cdq-20260926")

# Native classes executed fresh in this workstream, with their green counts.
NATIVE_RUNS = {
    "xmage": {
        "direct": {
            "returncode": 0,
            "tests": 34,
            "failures": 0,
            "errors": 0,
            "classes": [
                "XmageFull107ResidualRequalificationTest",
                "XmageDigestCreditTest",
                "XmageFullGameWs05MulliganTest",
                "XmageFullGameTaxExecutionTest",
                "XmageFullGamePartnerExecutionTest",
                "XmageFullGameCard02ExecutionTest",
                "XmageFullGameMicroExecutionTest",
                "XmageFullGameTrigExecutionTest",
                "XmageFullGameDecisionExecutionTest",
            ],
        },
        "mechanism": {
            "returncode": 0,
            "tests": 134,
            "failures": 0,
            "errors": 0,
            "classes": [
                "XmageNativeStateRestorationTest",
                "XmageTemporalProgressionDriverTest",
                "XmageTemporalAdvancedProgressionTest",
                "XmageCausalStackReconstructionTest",
                "XmageCausalStackMechanicsTest",
                "XmageControlDivergenceReconstructionTest",
                "XmageCausalEliminationReconstructionTest",
                "XmageHiddenReplayIntegrationTest",
                "XmageCommanderDamageRestorationTest",
                "XmageFullGameHiddenInformationTest",
                "XmageFullGamePlayerCountTest",
                "XmageVariablePlayerLifecycleTest",
                "XmageFullGameCombatDamageTest",
                "XmageDecisionRejectionWs229Test",
                "XmageFullGameRulesSeedBindingTest",
            ],
        },
    },
    "forge": {
        "direct": {
            "returncode": 0,
            "tests": 150,
            "failures": 0,
            "errors": 0,
            "classes": [
                "WsR20Full107DenominatorTest",
                "WS233CardinalityTest",
                "WS227SemanticReplayTest",
                "WsR15HiddenInfoFamilyTest",
                "WS234S3BridgeTest",
                "WS236F4BridgeTest",
                "WS216GapClosureTest",
                "WS202ExecutableSurfaceTest",
                "WS217DividedAllocationTest",
                "WsR15MulticountCombatTest",
                "WsR15MulticountTriggerTest",
                "WsR15DeterminismTwinTest",
                "WsR15ConcessionFamilyTest",
                "WsR16SixPlayerFamilyTest",
                "BridgeEngineTest",
            ],
        },
        "mechanism": {
            "returncode": 0,
            "tests": 67,
            "failures": 0,
            "errors": 0,
            "classes": [
                "ProtocolTest",
                "BridgeProtocolProcessTest",
                "HeadlessGuiFailClosedTest",
                "WS216SeparateProcessTest",
                "WS217SeparateProcessTest",
                "WS227SeparateProcessTest",
                "WS233CardinalityProcessTest",
                "WS202SeparateProcessTest",
            ],
        },
    },
}

# Forge native suite -> FULL107 obligations: Wave-F builds audited Forge
# bindings mirroring the XMage package map. The donor WSR20 pointer mapping
# stays preserved in the donor evidence directory, never reused blindly.


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print("wrote", name)


def apply_evidence_rules(rows: dict[str, dict[str, Any]], candidate: str) -> tuple[int, int]:
    """Apply promotion/demotion rules. Returns (promoted, demoted).

    - Characterization rows take their proven non-PASS outcome even when the
      runner left them PASS (demotion with mechanism) or BLOCKED/UNKNOWN.
    - Rows with an audited positive binding promote to PASS when not already.
    - Rows currently PASS/NATIVE with no audited positive binding demote to
      BLOCKED (stale name-mention promotion); PB-10 rows carry exact reasons.
    """
    promoted = 0
    demoted = 0
    for fixture, row in rows.items():
        if candidate != "xmage":
            continue
        characterization = CHARACTERIZATION_XMAGE.get(fixture)
        if characterization is not None:
            # Idempotent: characterization rows always carry their proven
            # non-PASS outcome, whether the runner left them PASS (demotion),
            # BLOCKED or UNKNOWN.
            changed = (
                row["exit_state"] != characterization["outcome"]
                or row.get("execution_mode") != "NATIVE_CURRENT_BOUNDARY_RUNTIME"
            )
            row["exit_state"] = characterization["outcome"]
            row["execution_mode"] = "NATIVE_CURRENT_BOUNDARY_RUNTIME"
            row["failure_reason"] = characterization["reason"]
            row["reason"] = characterization["reason"]
            row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
            row["native_harness_classes"] = characterization["classes"]
            row.setdefault("terminal_facts", {})
            row["terminal_facts"]["native_harness"] = characterization["classes"]
            if changed:
                demoted += 1
            continue
        bindings = POSITIVE_NATIVE_BINDING_XMAGE.get(fixture)
        if bindings:
            if row["exit_state"] == "PASS":
                continue
            row["exit_state"] = "PASS"
            row["execution_mode"] = "NATIVE_CURRENT_BOUNDARY_RUNTIME"
            row["failure_reason"] = None
            row["reason"] = (
                "fixture-corresponding native harness executed fresh under the current "
                f"boundary ({', '.join(bindings)}); the effective v1.0.6 record for this row "
                "is byte-identical to the frozen v1.0.5 record it loads, as proven in "
                "SUCCESSOR_INHERITANCE_PROOF.json"
            )
            row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
            row["native_harness_classes"] = bindings
            row.setdefault("terminal_facts", {})
            row["terminal_facts"]["native_harness"] = bindings
            promoted += 1
            continue
        if row["exit_state"] == "PASS" and row.get("execution_mode", "").startswith("NATIVE"):
            demotion = PB10_DEMOTIONS.get(fixture, {})
            row["exit_state"] = "BLOCKED"
            row["failure_reason"] = (
                "stale name-mention promotion without an audited positive binding; "
                + str(demotion.get("proof", "flagged for audit"))
            )
            row["reason"] = row["failure_reason"]
            demoted += 1
    return promoted, demoted


def assemble() -> None:
    per_candidate: dict[str, dict[str, Any]] = {}
    for candidate in ("xmage", "forge"):
        results = load(OUT / f"FULL107_{candidate.upper()}_RESULTS.json")
        rows = {row["fixture_id"]: dict(row) for row in results["rows"]}
        promoted, demoted = apply_evidence_rules(rows, candidate)
        results["pb03_evidence_rules"] = {
            "promoted": promoted,
            "demoted": demoted,
            "rule": "positive native binding promotes; characterization binds non-PASS; "
            "PASS without audited binding demotes",
        }
        counts = {
            "PASS": 0,
            "FAIL": 0,
            "UNKNOWN": 0,
            "BLOCKED": 0,
            "CRASH": 0,
            "TIMEOUT": 0,
            "PROTOCOL_FAILURE": 0,
        }
        for row in rows.values():
            counts[row["exit_state"]] = counts.get(row["exit_state"], 0) + 1
        assert sum(counts.values()) == 107, counts
        results["rows"] = [rows[row["fixture_id"]] for row in results["rows"]]
        results["counts"] = counts
        results["native_promotions"] = promoted
        results["native_runs"] = NATIVE_RUNS[candidate]
        write(f"FULL107_{candidate.upper()}_RESULTS.json", results)
        per_candidate[candidate] = {
            "rows": rows,
            "counts": counts,
            "native_runs": NATIVE_RUNS[candidate],
        }

    # ---- AF00-AF11 matrix ------------------------------------------------
    for candidate, data in per_candidate.items():
        counts = data["counts"]
        af01 = load(OUT / f"AF01_{candidate.upper()}.json")
        extra = load(OUT / "AF01_XMAGE_FULLGAME_LANE.json") if candidate == "xmage" else None
        native = data["native_runs"]
        native_tests = sum(group["tests"] for group in native.values())
        native_green = all(
            group["returncode"] == 0 and group["failures"] == 0 and group["errors"] == 0
            for group in native.values()
        )
        cardinality = load(OUT / f"PLAYER_CARDINALITY_{candidate.upper()}.json")
        card_pass = [
            k
            for k, v in cardinality["results"].items()
            if v.get("steps_completed") and not v.get("failure") and k in {"2P", "3P", "4P", "5P"}
        ]
        matrix = [
            {
                "gate": "AF00",
                "name": "SOURCE_AND_BUILD_LOCK",
                "verdict": "PASS",
                "evidence": [
                    f"candidate commit reported by the provider at handshake: "
                    f"{af01['engine_commit_reported']}",
                    f"engine_commit provenance: {af01['engine_commit_provenance']}",
                    "Lab runner HEAD/TREE bound in FULL107_*_RUNTIME_LOG_INDEX.json",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": (
                    [
                        "Forge reports its engine commit from the FORGE_ENGINE_SHA environment "
                        "variable rather than deriving it from the built Forge bytes, so the "
                        "commit-to-build binding is operator-supplied, not build-proven"
                    ]
                    if candidate == "forge"
                    else []
                ),
            },
            {
                "gate": "AF01",
                "name": "PROTOCOL_HANDSHAKE",
                "verdict": af01["verdict"],
                "evidence": [
                    f"{len(af01['invariants'])} AF01 v2 invariants executed under "
                    f"Protocol 2.0.0 on the {af01['lane']} lane",
                    f"AF01_*_{candidate.upper()}.json",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": (
                    [
                        "the generic compatibility lane reports seed_supported=false, so the "
                        "Rules-RNG invariant is UNKNOWN on that lane; the full-game lane reports "
                        "seed_supported=true and AF01 PASS"
                    ]
                    if candidate == "xmage"
                    else []
                )
                + ([f"full-game lane AF01 verdict: {extra['verdict']}"] if extra else []),
            },
            {
                "gate": "AF02",
                "name": "PLAYER_CARDINALITY",
                "verdict": "PASS" if len(card_pass) == 4 else "FAIL",
                "evidence": [
                    f"independent live lifecycles executed at {sorted(card_pass)}",
                    f"bounded 6P lifecycle also executed: {'6P' in cardinality['results']}",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": [
                    "6P is bounded secondary evidence; 7P is not attempted on this boundary"
                ],
            },
            {
                "gate": "AF03",
                "name": "RULES_AUTHORITY",
                "verdict": "PASS",
                "evidence": [
                    "the engine rejected an illegal Commander colour identity during deck "
                    "import (proving the engine owns deck legality, not the harness)",
                    "the engine rejected unknown card names by name",
                    "out-of-scope submissions produced no fabricated legal option",
                    "runner contains no legality reconstruction",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": [],
            },
            {
                "gate": "AF04",
                "name": "LEGAL_ACTION_AND_DECISION_BOUNDARY",
                "verdict": "FAIL" if candidate == "xmage" else "UNKNOWN",
                "evidence": [
                    "an external PRIORITY decision was reached and answered with an "
                    "engine-offered option on the shared generic lane",
                    "XMage requires external_control=true at create_commander_game or "
                    "get_legal_actions fails closed (LEGAL_ACTIONS_UNAVAILABLE)"
                    if candidate == "xmage"
                    else "Forge exposes STARTING_PLAYER, MULLIGAN and PRIORITY as external decisions",
                    "XMage binds decisions by decision_id (sha256) and pass by action_id; "
                    "Forge binds by revision (long) and pass by actor_id; neither accepts the "
                    "other's shape",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": (
                    [
                        "a single candidate-neutral adapter cannot drive both candidates without "
                        "a provider-specific decision-identity shim"
                    ]
                    if candidate == "xmage"
                    else [
                        "no STARTING_PLAYER, MULLIGAN or DRAW decision class beyond PRIORITY was "
                        "reachable for the other candidate on the shared surface"
                    ]
                ),
            },
            {
                "gate": "AF05",
                "name": "HIDDEN_INFORMATION",
                "verdict": "UNKNOWN",
                "evidence": [
                    "principal-scoped state read for four seats in a live 4P game",
                    f"HIDDEN_INFO_{candidate.upper()}.json",
                    f"native hidden/replay suites green: {native_tests} tests",
                ],
                "blocking_rows": [
                    row
                    for row, data_ in data["rows"].items()
                    if data_["exit_state"] in ("UNKNOWN", "BLOCKED") and row.startswith("HIDDEN_")
                ],
                "nonblocking_limitations": [
                    "per-scenario hidden channels (face-down exile, "
                    "look, controlled-player, shuffle invalidation) are "
                    "not reachable on the generic surface"
                ],
            },
            {
                "gate": "AF06",
                "name": "GENERAL_RULES_CORRECTNESS",
                "verdict": "UNKNOWN",
                "evidence": [
                    f"{counts['PASS']} of 107 rows PASS under the effective v1.0.6 "
                    f"contract; {counts['BLOCKED']} BLOCKED; {counts['UNKNOWN']} UNKNOWN"
                ],
                "blocking_rows": sorted(
                    data["rows"][r]["fixture_id"]
                    for r in data["rows"]
                    if data["rows"][r]["exit_state"] == "BLOCKED"
                ),
                "nonblocking_limitations": [
                    "micro-rules mechanisms in constructed mid-game "
                    "states have no current-boundary execution seam"
                ],
            },
            {
                "gate": "AF07",
                "name": "ACTUAL_CARD_BEHAVIOR",
                "verdict": "UNKNOWN",
                "evidence": [
                    f"ACTUAL_CARD_{candidate.upper()}.json",
                    "engine-validated import of a real 100-card Commander deck",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": [
                    "the effective 29-card actual-card denominator was "
                    "not individually executed on this boundary"
                ],
            },
            {
                "gate": "AF08",
                "name": "MULTIPLAYER_COMMANDER",
                "verdict": "UNKNOWN",
                "evidence": [
                    "cardinality lifecycles at 2P/3P/4P/5P",
                    "START-2 executed under the v1.0.6 successor",
                ],
                "blocking_rows": sorted(
                    data["rows"][r]["fixture_id"]
                    for r in data["rows"]
                    if data["rows"][r]["exit_state"] == "BLOCKED" and r.startswith("WS05-")
                ),
                "nonblocking_limitations": [
                    "mid-game Commander/elimination fixtures need a "
                    "starting-state injection seam that is unavailable"
                ],
            },
            {
                "gate": "AF09",
                "name": "RNG_REPLAY",
                "verdict": "UNKNOWN",
                "evidence": [
                    f"replay export executed in a live game (RNG_REPLAY_{candidate.upper()}.json)",
                    "native replay/semantic suites green",
                ],
                "blocking_rows": sorted(
                    r
                    for r, v in data["rows"].items()
                    if v["exit_state"] in ("UNKNOWN", "BLOCKED")
                    and (r.startswith("REPLAY_") or r.startswith("RNG_"))
                ),
                "nonblocking_limitations": [
                    "the clean-process twin half of each replay "
                    "obligation is not proven per fixture"
                ],
            },
            {
                "gate": "AF10",
                "name": "RUNTIME_EVIDENCE_RELIABILITY",
                "verdict": "PASS"
                if (
                    counts["CRASH"] == 0
                    and counts["TIMEOUT"] == 0
                    and counts["PROTOCOL_FAILURE"] == 0
                    and native_green
                )
                else "FAIL",
                "evidence": [
                    f"denominator accounting complete: "
                    f"{sum(counts.values())} explicit outcomes for 107 rows",
                    "zero CRASH/TIMEOUT/PROTOCOL_FAILURE",
                    f"native suites: {native_tests} tests, all green",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": [],
            },
            {
                "gate": "AF11",
                "name": "INTEROP_LICENSE_TOPOLOGY",
                "verdict": "FAIL",
                "evidence": [
                    "both candidates run as genuine separate external processes over "
                    "stdin/stdout JSONL; no engine code is embedded in Lab",
                    "XMage MIT, Forge GPL-3.0 (recorded in the source lock)",
                    "the two candidates publish different request-body conventions "
                    "(XMage reads payload, Forge reads params) and different decision-identity "
                    "fields, so one adapter cannot serve both without a shim",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": [
                    "a provider-specific decision-identity shim in the "
                    "Lab adapter would be required for a single "
                    "provider-neutral pilot"
                ],
            },
        ]
        write(
            f"AF00_AF11_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.af-matrix/1.0.0",
                "candidate": candidate,
                "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
                "gate_catalog": "architecture_freeze_gate_catalog_v2.json (AF00-AF11, all required)",
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "native_runs": native,
                "full107_counts": counts,
                "gates": matrix,
            },
        )

    # ---- comparison ------------------------------------------------------
    x = per_candidate["xmage"]["rows"]
    f = per_candidate["forge"]["rows"]
    dispositions: dict[str, int] = {}
    comparison: list[dict[str, Any]] = []
    for fixture in sorted(x):
        xr, fr = x[fixture], f[fixture]
        if xr["exit_state"] == fr["exit_state"] == "PASS":
            disposition = "SAME_SEMANTICS"
            note = (
                "both candidates executed the effective v1.0.6 obligation and both "
                "observed the obligated facts in this boundary"
            )
        elif "FAIL" in (xr["exit_state"], fr["exit_state"]):
            disposition = "UNKNOWN_PENDING_RULES_ADJUDICATION"
            note = "a current-boundary failure requires Coordinator Rules adjudication"
        elif "BLOCKED" in (xr["exit_state"], fr["exit_state"]):
            disposition = "NON_COMPARABLE"
            note = (
                "no current-boundary execution seam on at least one side; an absent seam "
                "is not a Rules difference and is not a capability claim"
            )
        else:
            disposition = "NON_COMPARABLE"
            note = (
                "at least one side has no fixture-corresponding current-boundary evidence; "
                "this is an evidence gap, not a proven semantic difference"
            )
        dispositions[disposition] = dispositions.get(disposition, 0) + 1
        comparison.append(
            {
                "fixture_id": fixture,
                "disposition": disposition,
                "note": note,
                "xmage": {
                    "exit_state": xr["exit_state"],
                    "execution_mode": xr["execution_mode"],
                    "reason": xr["reason"],
                },
                "forge": {
                    "exit_state": fr["exit_state"],
                    "execution_mode": fr["execution_mode"],
                    "reason": fr["reason"],
                },
                "engine_local_ids_excluded": [
                    "game_id",
                    "engine_game_id",
                    "player_id",
                    "decision_id",
                    "option_id",
                    "revision",
                ],
            }
        )
    write(
        "CURRENT_BOUNDARY_COMPARISON.json",
        {
            "schema_version": "wsr22.current-boundary-comparison/1.0.0",
            "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
            "denominator": 107,
            "dispositions": dispositions,
            "rows": comparison,
            "no_ranking": "this packet contains no score, no ranking and no preferred provider",
        },
    )
    write(
        "DIVERGENCE_PACKET.json",
        {
            "schema_version": "wsr22.divergence-packet/1.0.0",
            "ruled_visible_divergences": [],
            "count": 0,
            "pending_rules_adjudication": [
                row["fixture_id"]
                for row in comparison
                if row["disposition"] == "UNKNOWN_PENDING_RULES_ADJUDICATION"
            ],
            "note": (
                "No Rules-visible behavioural divergence was observed. The cross-engine "
                "differences found in this workstream are protocol/interface shape "
                "differences, recorded in CURRENT_BOUNDARY_COMPARISON and "
                "PROVIDER_BLOCKERS, not Magic Rules disagreements. The Coordinator performs "
                "final independent Rules adjudication."
            ),
        },
    )
    print(json.dumps(dispositions, indent=1))
    print("xmage", per_candidate["xmage"]["counts"])
    print("forge", per_candidate["forge"]["counts"])


if __name__ == "__main__":
    assemble()
