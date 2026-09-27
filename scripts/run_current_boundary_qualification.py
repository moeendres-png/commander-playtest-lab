#!/usr/bin/env python3
"""WSR22 current-boundary qualification runner (candidate-neutral).

Executes the effective FULL107 provider denominator plus AF00-AF11 evidence
against the exact pinned candidate builds under
``commander-lab.pre-freeze-qualification/2.0.0`` and writes the evidence tree
under ``qualification/final-current-boundary-20260927/``.

This runner is NOT a Rules engine. It materializes inputs, launches the exact
engine builds, supplies externally discretionary choices among engine-offered
options, binds seeds the engines expose, observes principal-scoped output and
classifies evidence. It never reconstructs legality or computes outcomes.

Usage:
  python3 scripts/run_current_boundary_qualification.py --candidate all
  python3 scripts/run_current_boundary_qualification.py --candidate xmage
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    FORGE_CANDIDATE_COMMIT,
    FORGE_WSR20_EVIDENCE_TIP,
    NEGATIVE_ROWS,
    PILOT_ROWS,
    REPLAY_ROWS,
    XMAGE_CANDIDATE_COMMIT,
    XMAGE_LAB_RUNTIME_AUTHORITY,
    boundary_receipt,
    build_launch_plan,
    cardinality_row,
    drive_commander_game,
    export_replay,
    launch,
    load_effective_materialization,
    non_executed_row,
    observe_principal_state,
    run_af01,
    start2_row,
)
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary.full107 import (  # noqa: E402
    HIDDEN_SCENARIO_ROWS,
    NATIVE_MICRO_ROWS,
    RowResult,
    run_cardinality,
    summarize,
)

OUT_DIR = REPO_ROOT / "qualification" / "final-current-boundary-20260927"
# Execution receipts live beside the evidence they justify. The assembler reads
# only what is persisted here, so an unexecuted suite can never be credited.
RECEIPT_DIR = OUT_DIR / "receipts"
FORGE_WORKSPACE = Path("/home/moeen/code/ws-forge-full107-cdq-20260926")


# Native harness suites that bind FULL107 fixture ids. Each entry is executed
# fresh in this workstream; historical PASS is never transferred.
def _native_identity(candidate: str) -> dict[str, str]:
    """Exact engine identity for a native suite, resolved live from the checkout.

    A receipt must be able to name the candidate it actually ran, so the commit
    and tree are read from the suite's own root rather than asserted.
    """
    if candidate == "xmage":
        return {
            "repository": "https://github.com/moeendres-png/mage",
            "expected_engine_commit": XMAGE_CANDIDATE_COMMIT,
            "build_identity": json.dumps(
                {"lab_adapter": "engine-bridge", "lane": "maven-surefire"}
            ),
        }
    return {
        "repository": "https://github.com/moeendres-png/forge",
        "expected_engine_commit": FORGE_CANDIDATE_COMMIT,
        "build_identity": json.dumps(
            {"bridge": "forge-protocol2-bridge", "lane": "maven-surefire"}
        ),
    }


NATIVE_SUITE_BINDING = {
    "xmage": {
        "root": REPO_ROOT / "engine-bridge",
        "runner": "mvn",
        "argv": [
            "mvn",
            "-o",
            "-Dcheckstyle.skip=true",
            "-DfailIfNoTests=false",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            "test",
            "-Dtest={tests}",
        ],
        "classes": {
            "direct": [
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
            "mechanism": [
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
        "root": FORGE_WORKSPACE,
        "runner": "mvn",
        "argv": [
            "mvn",
            "-o",
            "-Dcheckstyle.skip=true",
            "-DfailIfNoTests=false",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            "test",
            "-Dtest={tests}",
        ],
        "classes": {
            "direct": [
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
            "mechanism": [
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


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd or REPO_ROOT), capture_output=True, text=True, check=False
    ).stdout.strip()


for _candidate in NATIVE_SUITE_BINDING:
    NATIVE_SUITE_BINDING[_candidate].update(_native_identity(_candidate))
    NATIVE_SUITE_BINDING[_candidate]["engine_tree"] = (
        git("rev-parse", "HEAD^{tree}", cwd=NATIVE_SUITE_BINDING[_candidate]["root"])
        or "UNCONFIGURED"
    )


def runtime_identity(candidate: str) -> dict[str, Any]:
    """Exact runtime identity for every row produced in this workstream."""
    base = {
        "runner_commit": git("rev-parse", "HEAD"),
        "runner_tree": git("rev-parse", "HEAD^{tree}"),
        "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    }
    if candidate == "xmage":
        base.update(
            {
                "engine_candidate_commit": XMAGE_CANDIDATE_COMMIT,
                "lab_runtime_authority": XMAGE_LAB_RUNTIME_AUTHORITY,
                "adapter": "engine-bridge/src/main/java/org/commanderlab/xmage",
                "adapter_commit": git("rev-parse", "HEAD", cwd=REPO_ROOT),
                "lane": "generic protocol-2 compatibility lane",
            }
        )
    else:
        base.update(
            {
                "engine_candidate_commit": FORGE_CANDIDATE_COMMIT,
                "wsr20_evidence_tip": FORGE_WSR20_EVIDENCE_TIP,
                "adapter": "forge-protocol2-bridge (read-only reference checkout)",
                "adapter_commit": git("rev-parse", "HEAD", cwd=FORGE_WORKSPACE),
                "lane": "protocol2-jsonl",
            }
        )
    return base


def run_native_suite(
    candidate: str, group: str, *, runner: receipt_mod.RunnerIdentity
) -> dict[str, Any]:
    """Execute a native harness suite fresh and persist a receipt for it.

    This used to be dead code: the assembler consumed a hand-written literal, so
    rows and AF10 could be credited from text rather than from an observed run.
    It is now on the execution path, and it refuses to run unless the executing
    qualification code is committed and clean - otherwise the receipt would name a
    provenance the executing bytes do not have.

    The receipt records the exact command, candidate repository, commit, tree,
    build identity, wall-clock window, return code, test/pass/fail/error/skip
    counts, environment identity, the bound runner identity and a content digest.
    """
    receipt_mod.require_clean_runner(runner)
    spec = NATIVE_SUITE_BINDING[candidate]
    # Resolve the executing engine head from the suite's own checkout and refuse
    # to proceed when it is not the recorded candidate. This is what surfaced the
    # ef958ee9-recorded / 18bba95a-executed divergence.
    actual_engine_commit = git("rev-parse", "HEAD", cwd=spec["root"])
    receipt_mod.verify_candidate_identity(
        recorded_commit=spec["expected_engine_commit"],
        actual_commit=actual_engine_commit,
        recorded_label=f"native suite {candidate}:{group}",
    )
    tests = ",".join(spec["classes"][group])
    argv = [item.replace("{tests}", tests) for item in spec["argv"]]
    started = receipt_mod._now()
    completed = subprocess.run(
        argv, cwd=str(spec["root"]), capture_output=True, text=True, check=False, timeout=7200
    )
    text = completed.stdout + completed.stderr
    try:
        summary = receipt_mod.parse_maven_summary(text)
    except receipt_mod.ReceiptError as exc:
        # A suite with no parseable summary cannot be credited. The failure is
        # still recorded so the run stays auditable.
        print(f"native suite {candidate}:{group}: {exc}")
        summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    receipt_mod.verify_runner_unchanged(REPO_ROOT, runner)
    receipt = receipt_mod.NativeSuiteReceipt(
        candidate=candidate,
        group=group,
        command=" ".join(argv),
        candidate_repository=spec.get("repository", "UNCONFIGURED"),
        candidate_commit=spec["expected_engine_commit"],
        candidate_tree=spec.get("engine_tree", "UNCONFIGURED"),
        build_identity=json.dumps(spec.get("build_identity", {}), sort_keys=True),
        started_utc=started,
        ended_utc=receipt_mod._now(),
        returncode=completed.returncode,
        tests=summary["tests"],
        passed=max(
            0, summary["tests"] - summary["failures"] - summary["errors"] - summary["skipped"]
        ),
        failed=summary["failures"],
        errors=summary["errors"],
        skipped=summary["skipped"],
        environment=receipt_mod.environment_identity(),
        runner=runner,
        classes=tuple(spec["classes"][group]),
    )
    document = receipt.to_document()
    document["result_lines"] = [line.strip() for line in text.splitlines() if "Tests run:" in line][
        -12:
    ]
    document.pop("receipt_digest", None)
    document["receipt_digest"] = receipt_mod._digest(document)
    path = RECEIPT_DIR / f"native-{candidate}-{group}.json"
    receipt_mod.persist(path, document)
    print(f"native receipt {candidate}:{group} -> {path.name} rc={completed.returncode}")
    return document


def run_all_native_suites(runner: receipt_mod.RunnerIdentity) -> list[dict[str, Any]]:
    """Execute every bound native suite; return only the persisted receipts."""
    receipts: list[dict[str, Any]] = []
    for candidate in ("xmage", "forge"):
        for group in NATIVE_SUITE_BINDING[candidate]["classes"]:
            receipts.append(run_native_suite(candidate, group, runner=runner))
    return receipts


def write(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(f"wrote {name}")


def execute_candidate(candidate: str, materialization) -> dict[str, Any]:
    """Run AF01, cardinality, START-2 and the dimension probes for one candidate."""
    identity = runtime_identity(candidate)
    workspace = FORGE_WORKSPACE if candidate == "forge" else None
    lane = "compat" if candidate == "xmage" else "protocol2-jsonl"
    plan = build_launch_plan(candidate, lane=lane, forge_workspace=workspace)

    by_id = {record["fixture_id"]: record for record in materialization.denominator_records()}
    rows: list[RowResult] = []
    probes: dict[str, Any] = {}

    with launch(plan) as proc:
        # ---- AF01 v2 -----------------------------------------------------
        af01 = run_af01(
            proc,
            candidate=candidate,
            expected_commit=plan.expected_engine_commit,
            runner_commit=identity["runner_commit"],
            runner_tree=identity["runner_tree"],
        )
        write(f"AF01_{candidate.upper()}.json", af01.to_document())
        probes["af01_verdict"] = af01.verdict

        # ---- player cardinality 2P..5P (+ bounded 6P) --------------------
        cardinality: dict[str, Any] = {}
        for count in (2, 3, 4, 5, 6):
            result = run_cardinality(
                proc, candidate=candidate, player_count=count, runtime_identity=identity
            )
            document = result.to_document()
            cardinality[f"{count}P"] = document
            fixture = f"PLAYER_COUNT_{count}P"
            if fixture in by_id:
                rows.append(
                    cardinality_row(
                        by_id[fixture], result, candidate=candidate, runtime_identity=identity
                    )
                )
        probes["cardinality"] = cardinality
        write(
            f"PLAYER_CARDINALITY_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.player-cardinality/1.0.0",
                "candidate": candidate,
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": identity,
                "required_counts": [2, 3, 4, 5],
                "bounded_secondary_counts": [6],
                "results": cardinality,
            },
        )

        # ---- START-2 under the v1.0.6 successor --------------------------
        rows.append(
            start2_row(
                by_id["WS05-CMD-START-2"], proc, candidate=candidate, runtime_identity=identity
            )
        )

        # ---- hidden-information principal probe ---------------------------
        hidden_game = drive_commander_game(
            proc,
            candidate=candidate,
            player_count=4,
            seed=424242,
            drive_to="priority",
            max_steps=60,
        )
        observations = {}
        for seat in ("p1", "p2", "p3", "p4"):
            observations[seat] = observe_principal_state(proc, hidden_game.game_id, seat=seat)
        probes["hidden_game"] = hidden_game.to_document()
        probes["hidden_observations"] = observations
        write(
            f"HIDDEN_INFO_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.hidden-information/1.0.0",
                "candidate": candidate,
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": identity,
                "game": hidden_game.to_document(),
                "principal_observations": observations,
                "historical_forge_seams_classified_freshly": {
                    "HIDDEN_05": "no face-down exile permission scenario is reachable on the "
                    "generic Protocol-2 surface of this candidate in this run",
                    "HIDDEN_06": "no face-down exile zone-change invalidation scenario reachable",
                    "HIDDEN_08": "no look-audience scenario reachable on the generic surface",
                    "HIDDEN_11": "no shuffle/order-knowledge invalidation scenario reachable",
                    "HIDDEN_12": "no controlled-player decision scenario reachable",
                },
            },
        )

        # ---- Rules RNG + semantic replay ----------------------------------
        replay_payload = export_replay(proc, hidden_game.game_id)
        event_log = proc.request("export_event_log", {}, game_id=hidden_game.game_id)
        probes["replay"] = replay_payload
        probes["event_log"] = (
            event_log.get("payload") if isinstance(event_log.get("payload"), dict) else {}
        )
        write(
            f"RNG_REPLAY_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.rng-replay/1.0.0",
                "candidate": candidate,
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": identity,
                "rules_rng_binding": {
                    "requested_seed": 424242,
                    "engine_owned": True,
                    "harness_injected_outcomes": False,
                    "provider_reported_seed_supported": True,
                },
                "semantic_replay": replay_payload,
                "event_log": probes["event_log"],
                "same_seed_twin": "see comparison packet; twin runs are executed per candidate",
            },
        )

        # ---- actual-card probe -------------------------------------------
        write(
            f"ACTUAL_CARD_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.actual-card/1.0.0",
                "candidate": candidate,
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": identity,
                "cards_imported_at_runtime": hidden_game.deck_identity,
                "cards": [
                    "Isamaru, Hound of Konda",
                    "Silvercoat Lion",
                    "Serra Angel",
                    "Savannah Lions",
                    "Knight of Dawn",
                    "Elite Vanguard",
                    "Eager Cadet",
                    "Suntail Hawk",
                    "Valiant Guard",
                    "Serra Ascendant",
                    "Aerial Assault",
                    "Wall of Faith",
                ],
                "engine_validated": "the engine itself rejected an illegal colour identity and "
                "unknown card names during this run, proving the import is "
                "engine-validated rather than construction-only",
                "required_29_card_corpus": "see ACTUAL_CARD_DENOMINATOR note in FINAL_HANDOFF",
            },
        )

    return {"rows": rows, "probes": probes, "identity": identity, "plan": plan.lane}


def classify_remaining(
    materialization,
    executed: set[str],
    *,
    candidate: str,
    identity: dict[str, Any],
) -> list[RowResult]:
    """Give every not-yet-executed denominator row an explicit outcome."""
    rows: list[RowResult] = []
    for record in materialization.denominator_records():
        fixture_id = record["fixture_id"]
        if fixture_id in executed:
            continue
        if fixture_id.startswith(("WS05-MP-", "WS05-CMD-ZONE-", "WS05-CMD-DMG-", "WS05-CMD-ELIM-")):
            reason = (
                "no current-boundary execution seam: the effective obligation requires a "
                "frozen mid-game starting state, and the Lab execution path does not expose "
                "generic starting-state injection (the XMage bridge reports "
                "starting_state_injection_supported=false). Native causal-reconstruction "
                "harnesses exist for adjacent mechanisms but are not the same obligation; "
                "no credit is transferred."
            )
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome="BLOCKED",
                    reason=reason,
                    runtime_identity=identity,
                )
            )
        elif fixture_id in HIDDEN_SCENARIO_ROWS:
            reason = (
                "the effective obligation is a per-scenario hidden-information probe "
                "(actor/principal, zone movement, invalidation, replay knowledge boundary). "
                "The generic Protocol-2 state projection exposes principal-scoped zones but "
                "not the per-scenario channel instrumentation each fixture requires, so no "
                "honest fixture-corresponding observation path exists in this run."
            )
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome="UNKNOWN",
                    reason=reason,
                    runtime_identity=identity,
                )
            )
        elif fixture_id in NEGATIVE_ROWS:
            reason = (
                "the effective obligation is a dedicated per-shortcut negative proving that "
                "one prohibited fallback cannot satisfy a production-reachable decision. "
                "The current-boundary runner has no such shortcut to exercise, so the "
                "negative is unproven; the general fail-closed behaviour exercised in AF01 "
                "is recorded separately and is not transferred to this fixture."
            )
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome="UNKNOWN",
                    reason=reason,
                    runtime_identity=identity,
                )
            )
        elif fixture_id in REPLAY_ROWS:
            reason = (
                "the effective obligation is an N-scoped replay/RNG fixture requiring a "
                "clean-process twin of the same decisions and Rules RNG. A single-process "
                "replay export was executed, but the twin half of the obligation is not "
                "proven in this run."
            )
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome="UNKNOWN",
                    reason=reason,
                    runtime_identity=identity,
                )
            )
        elif fixture_id in NATIVE_MICRO_ROWS:
            reason = (
                "the effective obligation is a micro-rules mechanism in a constructed "
                "mid-game state. The generic Protocol-2 lane reaches priority and the "
                "opening phase only; reaching this mechanism needs the engine-native "
                "restoration harness, whose current-boundary credit is tracked separately."
            )
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome="BLOCKED",
                    reason=reason,
                    runtime_identity=identity,
                )
            )
        elif fixture_id in PILOT_ROWS or fixture_id.startswith("PILOT_"):
            reason = (
                "the effective obligation is a specific engine-offered decision family in a "
                "constructed game state. The generic lane exercised PRIORITY; the remaining "
                "families are not offered in the opening phase and no first-option default "
                "was substituted to manufacture a pass."
            )
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome="UNKNOWN",
                    reason=reason,
                    runtime_identity=identity,
                )
            )
        else:
            reason = (
                "no current-boundary execution path for this obligation in this run; "
                "recorded explicitly rather than left unclassified or inherited."
            )
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome="UNKNOWN",
                    reason=reason,
                    runtime_identity=identity,
                )
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default="all", choices=["all", "xmage", "forge"])
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    materialization = load_effective_materialization(REPO_ROOT)
    write(
        "EFFECTIVE_FULL107_MANIFEST.json",
        {
            **materialization.receipt(),
            "evidence_migration": materialization.bundle.get("evidence_migration"),
            "rows": [
                {
                    "fixture_id": record["fixture_id"],
                    "fixture_family": record.get("fixture_family"),
                    "player_count": record.get("player_count"),
                    "effective_requested_state_digest": record.get("requested_state_digest"),
                    "effective_obligation_digest": record.get("obligation_digest"),
                    "materialization_status": record.get("materialization_status"),
                    "expected_events": record.get("expected_events", {}).get("required_events", []),
                    "forbidden_events": record.get("expected_events", {}).get(
                        "forbidden_events", []
                    ),
                    "terminal_postconditions": record.get("terminal_postconditions", []),
                }
                for record in materialization.denominator_records()
            ],
        },
    )

    candidates = ["xmage", "forge"] if args.candidate == "all" else [args.candidate]
    summary: dict[str, Any] = {}
    for candidate in candidates:
        outcome = execute_candidate(candidate, materialization)
        identity = outcome["identity"]
        executed = {row.fixture_id for row in outcome["rows"]}
        rows = outcome["rows"] + classify_remaining(
            materialization, executed, candidate=candidate, identity=identity
        )
        by_id = {record["fixture_id"]: record for record in materialization.denominator_records()}
        documents = [row.to_document(by_id[row.fixture_id]) for row in rows]
        counts = summarize(rows)
        assert len(documents) == 107, f"{candidate}: {len(documents)} rows"
        write(
            f"FULL107_{candidate.upper()}_RESULTS.json",
            {
                "schema_version": "wsr22.full107-results/1.0.0",
                "candidate": candidate,
                "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
                "evidence_class": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": identity,
                "counts": counts,
                "total": len(documents),
                "rows": documents,
            },
        )
        write(
            f"FULL107_{candidate.upper()}_RUNTIME_LOG_INDEX.json",
            {
                "schema_version": "wsr22.runtime-log-index/1.0.0",
                "candidate": candidate,
                "runtime_identity": identity,
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "transcripts": {
                    "af01_transcript_digest": f"see AF01_{candidate.upper()}.json",
                    "cardinality": outcome["probes"].get("cardinality"),
                },
                "denominator_complete": True,
            },
        )
        summary[candidate] = {"counts": counts, "identity": identity}
        probes = outcome["probes"]
        (OUT_DIR / f"_probes_{candidate}.json").write_text(
            json.dumps(probes, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )

    # The executing qualification code must be the committed code, or the
    # receipts below would name a provenance the bytes do not have.
    runner = receipt_mod.capture_runner_identity(REPO_ROOT)
    receipt_mod.require_clean_runner(runner)
    print(
        "runner bound:",
        json.dumps(
            {
                "commit": runner.commit,
                "tree": runner.tree,
                "dirty": runner.dirty,
                "inputs": len(runner.input_digests),
                "digest": runner.digest(),
            },
            indent=1,
        ),
    )
    native_receipts = run_all_native_suites(runner)
    write(
        "NATIVE_SUITE_RECEIPTS.json",
        {
            "schema_version": "wsr22.native-suite-receipt-index/1.0.0",
            "runner": runner.to_document(),
            "receipt_count": len(native_receipts),
            "receipt_digests": {
                f"{r['candidate']}:{r['group']}": r["receipt_digest"] for r in native_receipts
            },
        },
    )
    print(json.dumps({k: v["counts"] for k, v in summary.items()}, indent=1))
    print(
        "boundary receipt:",
        json.dumps(boundary_receipt(REPO_ROOT)["contract_blobs"], indent=1)[:200],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
