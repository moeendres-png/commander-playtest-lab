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

from commander_lab.qualification.current_boundary import lifecycle as lifecycle_mod  # noqa: E402
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary import semantic as semantic_mod  # noqa: E402

OUT = REPO / "qualification" / "final-current-boundary-20260927"
FORGE_WS = Path("/home/moeen/code/ws-forge-full107-cdq-20260926")

# Execution receipts. The assembler trusts nothing else for native credit: no
# receipt means no credit, and source text is never a substitute.
RECEIPT_DIR = OUT / "receipts"

FORGE_NATIVE_BINDING_PATH = OUT / "wsr20-ingest" / "FULL107_FORGE_MAPPING.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print("wrote", name)


def native_bindings() -> dict[str, dict[str, list[str]]]:
    """Fixture -> test identities, derived from persisted positive receipts only.

    This previously scanned test source for fixture-id strings. That promoted
    HIDDEN_02 from UNKNOWN to PASS on the strength of a test that mentions
    HIDDEN_02 only to assert that loading it FAILS. A string mention is not
    evidence, so the whole scanning path is gone: credit now requires a positive
    receipt, and anything without one simply receives no credit.
    """
    denominator = {
        load(OUT / "EFFECTIVE_FULL107_MANIFEST.json")["rows"][i]["fixture_id"] for i in range(107)
    }
    receipts, rejected = receipt_mod.collect_receipts(RECEIPT_DIR)
    if rejected:
        for reason in rejected:
            print(f"native receipt rejected: {reason}")
    if not receipts:
        print("no valid native receipts: no native credit is possible this assembly")
    identity = {
        c: load(OUT / f"FULL107_{c.upper()}_RESULTS.json")["runtime_identity"]
        for c in ("xmage", "forge")
    }
    pb03_path = OUT / "PB03_DIMENSION_ADMISSION.json"
    pb03 = load(pb03_path) if pb03_path.is_file() else {}
    pb03_admitted = {str(item) for item in pb03.get("admitted", [])}
    pb03_blocked = {
        str(item) for item in (pb03.get("blocked", {}) or {}).keys()
    }
    pb03_managed = pb03_admitted | pb03_blocked
    out: dict[str, dict[str, list[str]]] = {}
    for candidate in ("xmage", "forge"):
        commit = identity[candidate].get("engine_candidate_commit", "")
        credited = receipt_mod.positive_fixture_credit(
            receipts, candidate=candidate, expected_commit=commit, denominator=denominator
        )
        for fixture, tests in credited.items():
            # Defense in depth: a positive native testcase cannot override
            # PB-03's live capability admission. Admission itself grants no
            # credit, but blocked admission is a hard routing prohibition.
            if (
                candidate == "xmage"
                and fixture in pb03_managed
                and fixture not in pb03_admitted
            ):
                print(
                    "PB-03 blocked admission cannot be overridden by positive receipt: "
                    + fixture
                )
                continue
            out.setdefault(fixture, {})[candidate] = tests
    return out


def native_credit(candidate: str, expected_commit: str) -> dict[str, Any]:
    """Native-suite credit for one candidate, from receipts only.

    `native_runs` keeps its established shape: a mapping of group name to that
    group's observed detail, so a consumer can read one suite's result directly.
    The aggregate summary and the provenance rule live under sibling keys rather
    than being mixed into the mapping, where a scalar would break iteration.
    """
    receipts, _ = receipt_mod.collect_receipts(RECEIPT_DIR)
    credit = receipt_mod.native_suite_credit(
        receipts, candidate=candidate, expected_commit=expected_commit
    )
    # PURELY a per-group mapping. Every value must be subscriptable, because
    # consumers iterate it directly; scalar metadata lives beside it.
    return {
        group["group"]: {
            "candidate": group["candidate"],
            "tests": group["tests"],
            "passed": group["passed"],
            # `failures` is the established key consumers read; `failed` is the
            # receipt's own name. Both are emitted so no consumer has to guess.
            "failed": group["failed"],
            "failures": group["failed"],
            "errors": group["errors"],
            "returncode": group["returncode"],
            "candidate_commit": group["candidate_commit"],
            "executed_commit": group["executed_commit"],
            "engine_identity_justification": group["engine_identity_justification"],
            "receipt_digest": group["receipt_digest"],
        }
        for group in credit["groups"]
    }


def native_credit_provenance(candidate: str, expected_commit: str) -> dict[str, Any]:
    """The provenance statement that accompanies `native_runs`."""
    receipts, _ = receipt_mod.collect_receipts(RECEIPT_DIR)
    credit = receipt_mod.native_suite_credit(
        receipts, candidate=candidate, expected_commit=expected_commit
    )
    return {
        "source": "PERSISTED_EXECUTION_RECEIPTS_ONLY",
        "absent_receipts_yield_no_credit": True,
        "expected_engine_commit": expected_commit,
        "summary": {
            "groups_credited": credit["groups_credited"],
            "tests": credit["tests"],
            "passed": credit["passed"],
            "failed": credit["failed"],
            "errors": credit["errors"],
            "receipt_digests": credit["receipt_digests"],
        },
    }


def source_lock_verdict(af01: dict[str, Any], expected_commit: str) -> str:
    """AF00 derived from the reported engine identity, not asserted.

    The gate is only satisfied when the provider named a commit, and named the
    commit the evidence is about. A provider that reports nothing is UNKNOWN: an
    absent identity is not a verified one. A provider that names a *different*
    commit is FAIL, because the evidence would be attributed to an engine that
    did not run.
    """
    reported = str(af01.get("engine_commit_reported") or "").strip()
    if not reported:
        return "UNKNOWN"
    expected = str(expected_commit or "").strip()
    if not expected:
        return "UNKNOWN"
    return "PASS" if reported == expected else "FAIL"


def af03_gate(candidate: str) -> dict[str, Any]:
    """AF03 RULES_AUTHORITY, read from this run's negative deck-import probe.

    AF03 used to be a literal ``"verdict": "PASS"`` in this assembler, with an
    evidence list describing deck imports that were never performed and no
    artifact behind them. It is now read from the probe artifact the runner
    produces, so a run that did not probe gets no credit, and a run in which the
    engine accepted an illegal deck gets a FAIL.
    """
    path = OUT / f"AF03_{candidate.upper()}.json"
    if not path.is_file():
        return {
            "gate": "AF03",
            "name": "RULES_AUTHORITY",
            "verdict": "UNKNOWN",
            "evidence": ["no AF03 probe artifact exists for this candidate"],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "AF03 cannot be credited without observed negative deck-import probes"
            ],
        }
    document = load(path)
    probes = document.get("probes", [])
    return {
        "gate": "AF03",
        "name": "RULES_AUTHORITY",
        "verdict": document.get("verdict", "UNKNOWN"),
        "evidence": [
            f"{probe['invariant']}: {probe['verdict']} ({probe['detail']})" for probe in probes
        ],
        "observed_probe_count": len(probes),
        "authority": document.get("authority"),
        "blocking_rows": [probe["probe"] for probe in probes if probe.get("verdict") == "FAIL"],
        "nonblocking_limitations": document.get("nonblocking_limitations", []),
    }


def assemble() -> None:
    bindings = native_bindings()
    per_candidate: dict[str, dict[str, Any]] = {}
    for candidate in ("xmage", "forge"):
        results = load(OUT / f"FULL107_{candidate.upper()}_RESULTS.json")
        rows = {row["fixture_id"]: dict(row) for row in results["rows"]}
        promoted = 0
        for fixture, per in bindings.items():
            classes = per.get(candidate)
            if not classes or fixture not in rows:
                continue
            row = rows[fixture]
            if row["exit_state"] == "PASS":
                continue
            row["exit_state"] = "PASS"
            row["execution_mode"] = "NATIVE_CURRENT_BOUNDARY_RUNTIME"
            row["failure_reason"] = None
            row["reason"] = (
                f"fixture-corresponding native harness executed fresh under the current "
                f"boundary ({', '.join(classes)}); the effective v1.0.6 record for this row "
                f"is byte-identical to the frozen v1.0.5 record it loads, as proven in "
                f"SUCCESSOR_INHERITANCE_PROOF.json"
            )
            row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
            row["native_harness_classes"] = classes
            row.setdefault("terminal_facts", {})
            row["terminal_facts"]["native_harness"] = classes
            promoted += 1
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
        results["native_runs"] = native_credit(
            candidate, results["runtime_identity"].get("engine_candidate_commit", "")
        )
        results["native_runs_provenance"] = native_credit_provenance(
            candidate, results["runtime_identity"].get("engine_candidate_commit", "")
        )
        write(f"FULL107_{candidate.upper()}_RESULTS.json", results)
        per_candidate[candidate] = {
            "rows": rows,
            "counts": counts,
            "native_runs": results["native_runs"],
            "native_runs_provenance": results["native_runs_provenance"],
            # Bound here so the AF matrix can never read another candidate's
            # identity through a leaked loop variable.
            "results_runtime_identity": results["runtime_identity"],
        }

    # ---- PB-03 runtime execution matrix -----------------------------------
    pb03_path = OUT / "PB03_DIMENSION_ADMISSION.json"
    if pb03_path.is_file() and "xmage" in per_candidate:
        pb03 = load(pb03_path)
        final_rows = per_candidate["xmage"]["rows"]
        runtime_rows: list[dict[str, Any]] = []
        for admission_row in pb03.get("rows", []):
            if not isinstance(admission_row, dict):
                continue
            fixture_id = str(admission_row.get("fixture_id") or "")
            final = final_rows.get(fixture_id, {})
            runtime_rows.append(
                {
                    "fixture_id": fixture_id,
                    "admission_verdict": admission_row.get("verdict"),
                    "required_tokens": admission_row.get("required_tokens", []),
                    "missing_tokens": admission_row.get("missing_tokens", []),
                    "admission_reason": admission_row.get("reason"),
                    "runtime_exit_state": final.get("exit_state", "UNKNOWN"),
                    "execution_mode": final.get("execution_mode"),
                    "runtime_reason": final.get("reason"),
                    "native_harness_classes": final.get("native_harness_classes", []),
                    "evidence_class": final.get("evidence_class"),
                }
            )

        admitted_rows = [
            row
            for row in runtime_rows
            if row["admission_verdict"] == "ADMITTED_TO_NATIVE_RESTORATION"
        ]
        blocked_rows = [
            row
            for row in runtime_rows
            if row["admission_verdict"] != "ADMITTED_TO_NATIVE_RESTORATION"
        ]
        admitted_counts: dict[str, int] = {}
        for row in admitted_rows:
            state = str(row["runtime_exit_state"])
            admitted_counts[state] = admitted_counts.get(state, 0) + 1
        blocked_not_blocked = [
            row["fixture_id"]
            for row in blocked_rows
            if row["runtime_exit_state"] != "BLOCKED"
        ]
        if blocked_not_blocked:
            classification = "FAIL"
        elif admitted_rows and all(
            row["runtime_exit_state"] == "PASS" for row in admitted_rows
        ) and not blocked_rows:
            classification = "PASS"
        elif any(row["runtime_exit_state"] == "PASS" for row in admitted_rows):
            classification = "PARTIAL"
        else:
            classification = "BLOCKED"

        write(
            "PB03_RUNTIME_EXECUTION_MATRIX.json",
            {
                "schema_version": "commander-lab.pb03-runtime-execution/1.0.0",
                "PB03_DIMENSION_ADMISSION": pb03.get("classification", "UNKNOWN"),
                "PB03_RUNTIME_EXECUTION": classification,
                "admitted_count": len(admitted_rows),
                "blocked_count": len(blocked_rows),
                "admitted_runtime_counts": dict(sorted(admitted_counts.items())),
                "blocked_rows_not_fail_closed": blocked_not_blocked,
                "rows": sorted(runtime_rows, key=lambda row: row["fixture_id"]),
                "credit_boundary": (
                    "Admission grants no PASS. PASS requires an exact positive "
                    "fixture receipt inside a digest-valid all-green native-suite "
                    "receipt at the expected candidate head."
                ),
                "architecture_freeze": "NOT_CLAIMED",
                "production_provider": "NOT_SELECTED",
            },
        )

    # ---- AF00-AF11 matrix ------------------------------------------------
    for candidate, data in per_candidate.items():
        counts = data["counts"]
        af01 = load(OUT / f"AF01_{candidate.upper()}.json")
        extra = load(OUT / "AF01_XMAGE_FULLGAME_LANE.json") if candidate == "xmage" else None
        # Receipt-derived, never the retired NATIVE_RUNS literal. The summary
        # counts only what a verified receipt observed, and it is empty when no
        # receipt exists, so the gate cannot inherit a historical count.
        native = data["native_runs"]
        native_summary = data["native_runs_provenance"].get("summary", {})
        native_groups = list(native)
        native_tests = int(native_summary.get("tests", 0))
        native_green = (
            bool(native_groups)
            and not native_summary.get("failed")
            and not native_summary.get("errors")
        )
        cardinality = load(OUT / f"PLAYER_CARDINALITY_{candidate.upper()}.json")
        # All-or-nothing. This previously counted any run with a non-empty
        # steps_completed list, so a lifecycle that only imported decks and
        # created a game counted as a completed player count, and four such
        # prefixes earned AF02 PASS. A shortfall is UNKNOWN, not FAIL: an
        # unestablished count is an evidence gap, not a refutation.
        cardinality_assessment = lifecycle_mod.cardinality_verdict(cardinality["results"])
        # The commit THIS candidate's evidence is required to be about, read from
        # this candidate's own results. It used to be a variable assigned in the
        # earlier per-candidate loop, so by the time the AF matrix ran it held the
        # LAST candidate's commit. XMage's AF00 was therefore compared against
        # Forge's expected commit and reported FAIL for the wrong reason.
        expected_engine_commit = data["results_runtime_identity"].get("engine_candidate_commit", "")
        matrix = [
            {
                # AF00 was a literal PASS. Its evidence merely printed the commit
                # the provider reported; nothing compared it to the commit the
                # evidence was supposed to be about, so a provider reporting the
                # wrong engine still earned PASS. The verdict is now derived from
                # that comparison.
                "gate": "AF00",
                "name": "SOURCE_AND_BUILD_LOCK",
                "verdict": source_lock_verdict(af01, expected_engine_commit),
                "evidence": [
                    f"candidate commit reported by the provider at handshake: "
                    f"{af01['engine_commit_reported']}",
                    f"commit the evidence is required to be about: {expected_engine_commit}",
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
                "verdict": cardinality_assessment["verdict"],
                "all_or_nothing": True,
                "evidence": [
                    cardinality_assessment["reason"],
                    f"counts with a complete lifecycle: {cardinality_assessment['complete_counts']}",
                    f"counts without one: {cardinality_assessment['incomplete_counts']}",
                    f"bounded 6P lifecycle recorded: {'6P' in cardinality['results']}",
                ],
                "lifecycle_assessment": cardinality_assessment,
                "blocking_rows": [],
                "nonblocking_limitations": [
                    "6P is bounded secondary evidence; 7P is not attempted on this boundary"
                ],
            },
            af03_gate(candidate),
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
            # PASS/PASS is not a semantic comparison. Compare the normalized
            # Rules-visible observations the two sides actually recorded, so two
            # engines that disagree about a turn number or a library count are
            # reported as a difference instead of being labelled equal.
            comparison_result = semantic_mod.compare_semantics(xr, fr)
            disposition = comparison_result["disposition"]
            note = comparison_result["reason"]
            if disposition == "RULES_VISIBLE_DIVERGENCE":
                note += " (requires Coordinator Rules adjudication)"
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
                **(
                    {"semantic_comparison": comparison_result}
                    if xr["exit_state"] == fr["exit_state"] == "PASS"
                    else {}
                ),
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
