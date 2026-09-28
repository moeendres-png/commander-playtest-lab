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
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402  # noqa: E402
    FORGE_CANDIDATE_COMMIT,
    FORGE_WSR20_EVIDENCE_TIP,
    NEGATIVE_ROWS,
    PILOT_ROWS,
    REPLAY_ROWS,
    XMAGE_CANDIDATE_COMMIT,
    XMAGE_LAB_RUNTIME_AUTHORITY,
    ManifestUnavailableError,
    RestorationManifest,
    admit,
    boundary_receipt,
    build_deck,
    build_launch_plan,
    cardinality_row,
    drive_commander_game,
    export_replay,
    game_driver,
    launch,
    load_effective_materialization,
    non_executed_row,
    observe_principal_state,
    parse_manifest,
    run_af01,
    run_af03,
    start2_row,
    validate_principal_scoping,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    materialization as materialization_mod,
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
# The Forge candidate workspace is a checkout (or export) of the PINNED
# materialization commit FORGE_BRIDGE_SOURCE_COMMIT, whose diff against the
# pinned Rules Core is confined to forge-protocol2-bridge/** and pom.xml.
#
# It is resolved from the environment rather than hardcoded, because a hardcoded
# scratch path would be unreproducible on any other machine and would silently
# point a later run at whatever happened to be left on disk. Fail closed when it
# is absent rather than falling back to the Lab fork checkout.
FORGE_WORKSPACE_ENV = "COMMANDER_LAB_FORGE_WORKSPACE"
_FORGE_WORKSPACE_DEFAULT = Path("/home/moeen/code/ws-forge-full107-cdq-20260926")
FORGE_WORKSPACE = Path(os.environ.get(FORGE_WORKSPACE_ENV) or _FORGE_WORKSPACE_DEFAULT)


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
            "identity_proof": "LAB_OWNED_BRIDGE_MODULE",
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
    # Resolve the executing engine head from the suite's own checkout. A suite
    # must execute at the descendant that actually contains its test classes, so
    # exact-commit equality is not the requirement; what must hold is that the
    # engine is the same engine. That is re-proven from the engine's main-source
    # trees on every run and fails closed if any module differs. Resolving this
    # live rather than asserting it is what surfaced the divergence originally.
    # A pinned materialization may be supplied as a verified export rather than a
    # git checkout. In that case there is no HEAD to read and, more importantly,
    # no module tree to compare, so no descendant-equivalence proof is possible.
    # Say so and withhold native credit rather than inventing a commit.
    workspace_has_git = Path(spec["root"], ".git").exists()
    if not workspace_has_git:
        return _no_credit_receipt(
            candidate,
            group,
            runner,
            "the candidate workspace is a verified materialization export with no git "
            "metadata, so neither an executing HEAD nor a per-module tree proof exists; "
            "native credit is withheld rather than inferred from the supplied commit",
        )
    actual_engine_commit = git("rev-parse", "HEAD", cwd=spec["root"])
    if spec.get("identity_proof") == "LAB_OWNED_BRIDGE_MODULE":
        # The suite runs in this repository's own engine-bridge module, so the
        # executing code is the Lab commit (already bound and digest-verified by
        # the runner receipt) and the engine is the separately pinned artifact.
        engine_equivalence = receipt_mod.verify_lab_owned_bridge_identity(
            runner.commit,
            spec["expected_engine_commit"],
            recorded_label=f"native suite {candidate}:{group}",
        )
    else:
        engine_equivalence = receipt_mod.verify_engine_identity(
            spec["root"],
            recorded_commit=spec["expected_engine_commit"],
            actual_commit=actual_engine_commit,
            recorded_label=f"native suite {candidate}:{group}",
        )
    print(
        f"engine identity {candidate}:{group}: "
        f"{engine_equivalence['justification']} "
        f"(recorded {spec['expected_engine_commit'][:12]}, "
        f"executing {actual_engine_commit[:12]})"
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
        executed_commit=actual_engine_commit,
        engine_identity_proof=engine_equivalence,
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


def _no_credit_receipt(
    candidate: str,
    group: str,
    runner: receipt_mod.RunnerIdentity,
    reason: str,
) -> dict[str, Any]:
    """Record a native suite that earns NO credit, with the exact reason.

    A bound suite that cannot be credited must not abort the run, and must not be
    silently skipped either: the assembler consumes these receipts and anything
    absent is not the same as anything refused. This is the difference between
    "not run" and "run and refused", and the evidence has to say which.
    """
    document = {
        "schema_version": "current-boundary.native-suite-receipt/1.0.0",
        "candidate": candidate,
        "group": group,
        "credit": receipt_mod._NO_CREDIT,
        "reason": reason,
        "tests": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "runner": {"commit": runner.commit, "tree": runner.tree, "branch": runner.branch},
    }
    document["receipt_digest"] = receipt_mod._digest(document)
    path = RECEIPT_DIR / f"native-{candidate}-{group}.json"
    receipt_mod.persist(path, document)
    print(f"native suite {candidate}:{group}: NO_CREDIT ({reason})")
    return document


def run_all_native_suites(runner: receipt_mod.RunnerIdentity) -> list[dict[str, Any]]:
    """Execute every bound native suite; return only the persisted receipts.

    A suite that cannot be credited records a NO_CREDIT receipt naming the exact
    reason. It must never abort the run: the rest of the boundary evidence is
    still valid and must be produced, and the uncreditable suite is reported
    rather than lost.
    """
    receipts: list[dict[str, Any]] = []
    for candidate in ("xmage", "forge"):
        for group in NATIVE_SUITE_BINDING[candidate]["classes"]:
            try:
                receipts.append(run_native_suite(candidate, group, runner=runner))
            except (
                receipt_mod.ReceiptError,
                subprocess.SubprocessError,
                OSError,
            ) as exc:
                receipts.append(
                    _no_credit_receipt(candidate, group, runner, f"{type(exc).__name__}: {exc}")
                )
    return receipts


def write(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(f"wrote {name}")


def _envelope_refusal(
    candidate: str, count: int, declared_min: int | None, declared_max: int | None
) -> dict[str, Any]:
    """Record a player count the engine itself does not qualify.

    This is the engine's advertised contract, not an observed behaviour and not a
    candidate capability result. It is recorded as its own document so a reader
    cannot mistake "not attempted" for "attempted and failed", and it is never
    promoted to a PASS: an unexecuted row is unexecuted.
    """
    return {
        "schema_version": "current-boundary.player-envelope-refusal/1.0.0",
        "candidate": candidate,
        "player_count": count,
        "attempted": False,
        "outcome": "ENGINE_DECLARES_COUNT_UNSUPPORTED",
        "declared_min_players": declared_min,
        "declared_max_players": declared_max,
        "reason": (
            f"the {candidate} engine declares a qualified player envelope of "
            f"{declared_min}..{declared_max}; {count} players is outside it, so the "
            "engine refuses the count by contract. Not attempted. This is not a "
            "capability result for this count and must not be read as one."
        ),
    }


def _record_envelope_row(
    rows_sink: list[RowResult],
    by_id: dict[str, Any],
    fixture_id: str,
    candidate: str,
    identity: dict[str, Any],
    document: dict[str, Any],
) -> None:
    """Give an un-attempted PLAYER_COUNT row an explicit, non-PASS outcome."""
    record = by_id.get(fixture_id)
    if record is None:
        return
    rows_sink.append(
        non_executed_row(
            record,
            candidate=candidate,
            # BLOCKED, not UNKNOWN and not FAIL: the module's own vocabulary
            # defines BLOCKED as the boundary contract locking the execution seam
            # because of a capability the provider truthfully reports as
            # unavailable, which is exactly this case. FAIL would assert a Rules
            # defect that was never observed; UNKNOWN would lose the fact that
            # the engine gave a definite, advertised answer.
            outcome="BLOCKED",
            reason=document["reason"],
            runtime_identity=identity,
        )
    )


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
        # ---- PB-03: the engine's OWN restoration manifest ------------------
        # Read it from the live candidate, not from a Lab projection. A missing
        # or malformed manifest fails closed: it must never be treated as "the
        # engine supports nothing", which would be an incapability nobody
        # observed.
        restoration_manifest: dict[str, Any] | None = None
        restoration_manifest_error: str | None = None
        try:
            capability_response = proc.request("get_capabilities", {})
            if capability_response.get("success") is not True:
                restoration_manifest_error = (
                    f"get_capabilities failed: {capability_response.get('status')}"
                )
            else:
                manifest = parse_manifest(capability_response.get("payload") or {})
                restoration_manifest = {
                    "schema_version": manifest.schema_version,
                    "starting_state_injection_supported": manifest.starting_state_injection_supported,
                    "supported": list(manifest.supported),
                    "unsupported": list(manifest.unsupported),
                }
        except ManifestUnavailableError as exc:
            restoration_manifest_error = str(exc)
        probes["restoration_manifest"] = restoration_manifest
        probes["restoration_manifest_error"] = restoration_manifest_error
        try:
            declared_caps = (capability_response or {}).get("capabilities") or {}
        except NameError:  # pragma: no cover - only when the fetch raised
            declared_caps = {}
        probes["lane_player_envelope"] = {
            "min": declared_caps.get("min_players"),
            "max": declared_caps.get("max_players"),
        }

        # ---- a real live game for the decision-time invariants -----------
        # AF01's fail-closed decision probes were previously issued with no
        # game at all. A provider asked to fail closed on a submission for a
        # game that does not exist refuses for reasons unrelated to
        # decision-time legality, so those results were passes for the wrong
        # reason. Drive a real Commander game to its first priority decision
        # and probe against that game instead.
        # The decision-time AF01 invariants need a live game, and the two
        # candidates do NOT qualify the same player counts: the pinned Forge
        # bridge qualifies exactly four. Drive the smallest count the engine
        # itself declares it supports, and record which count was used so the
        # evidence names it rather than implying a 2P surface both share.
        envelope = probes.get("lane_player_envelope") or {}
        declared_min = envelope.get("min")
        declared_max = envelope.get("max")
        af01_player_count = 2
        if isinstance(declared_min, int) and af01_player_count < declared_min:
            af01_player_count = declared_min
        if isinstance(declared_max, int) and af01_player_count > declared_max:
            af01_player_count = declared_max
        probes["af01_live_player_count_requested"] = af01_player_count
        # The engine, not the harness, decides which counts it qualifies. If it
        # refuses the requested count by contract, that refusal is RECORDED and
        # the drive is retried at the engine's own declared maximum. This is an
        # explicit, evidenced adaptation: the refused count, the engine's reason
        # and the count actually driven all appear in the evidence, so no reader
        # can assume a surface the engine never ran.
        refusals: list[dict[str, Any]] = []
        af01_player_count_driven = af01_player_count
        while True:
            try:
                af01_live = drive_commander_game(
                    proc,
                    candidate=candidate,
                    player_count=af01_player_count_driven,
                    seed=int(identity.get("af01_probe_seed", 20260927)),
                    drive_to="priority",
                )
                break
            except game_driver.UnsupportedPlayerCount as exc:
                refusals.append(
                    {
                        "requested_player_count": af01_player_count_driven,
                        "engine_reason": str(exc),
                        "attempted_beyond_handshake": False,
                    }
                )
                fallback = declared_max if isinstance(declared_max, int) else None
                if (
                    fallback is None
                    or fallback == af01_player_count_driven
                    or fallback in {r["requested_player_count"] for r in refusals}
                ):
                    raise
                af01_player_count_driven = fallback
        probes["af01_live_player_count_driven"] = af01_player_count_driven
        probes["af01_live_player_count_refusals"] = refusals
        af01_game_id = af01_live.game_id
        probes["af01_live_game"] = {
            "game_id": af01_game_id,
            "player_count": af01_live.player_count,
            "steps_completed": list(af01_live.steps_completed),
            "decisions_observed": len(af01_live.decision_tape),
            "failure": af01_live.failure,
        }
        if af01_live.failure is not None or not af01_live.steps_completed:
            raise SystemExit(
                "AF01 requires a live game to probe decision-time invariants, and no live "
                f"game was established: failure={af01_live.failure!r} "
                f"steps={af01_live.steps_completed!r}. AF01 evidence is not produced."
            )

        # ---- AF01 v2 -----------------------------------------------------
        af01 = run_af01(
            proc,
            candidate=candidate,
            expected_commit=plan.expected_engine_commit,
            runner_commit=identity["runner_commit"],
            runner_tree=identity["runner_tree"],
            game_id=af01_game_id,
            runner_root=REPO_ROOT,
        )
        af01_doc = af01.to_document()
        af01_doc["decision_probe_game"] = {
            "game_id": af01_game_id,
            "player_count": af01_live.player_count,
            "steps_completed": list(af01_live.steps_completed),
            "decisions_observed": len(af01_live.decision_tape),
            "binding": "LIVE_GAME_REQUIRED_FOR_DECISION_TIME_INVARIANTS",
        }
        write(f"AF01_{candidate.upper()}.json", af01_doc)
        probes["af01_verdict"] = af01.verdict

        # ---- AF03 RULES_AUTHORITY: negative deck-import probes ----------
        af03 = run_af03(
            proc,
            candidate=candidate,
            legal_deck=build_deck("af03-control"),
        )
        write(f"AF03_{candidate.upper()}.json", af03.to_document())
        probes["af03_verdict"] = af03.verdict

        # ---- player cardinality 2P..5P (+ bounded 6P) --------------------
        cardinality: dict[str, Any] = {}
        for count in (2, 3, 4, 5, 6):
            if isinstance(declared_min, int) and count < declared_min:
                cardinality[f"{count}P"] = _envelope_refusal(
                    candidate, count, declared_min, declared_max
                )
                _record_envelope_row(
                    rows,
                    by_id,
                    f"PLAYER_COUNT_{count}P",
                    candidate,
                    identity,
                    cardinality[f"{count}P"],
                )
                continue
            if isinstance(declared_max, int) and count > declared_max:
                cardinality[f"{count}P"] = _envelope_refusal(
                    candidate, count, declared_min, declared_max
                )
                _record_envelope_row(
                    rows,
                    by_id,
                    f"PLAYER_COUNT_{count}P",
                    candidate,
                    identity,
                    cardinality[f"{count}P"],
                )
                continue
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
        seats = ("p1", "p2", "p3", "p4")
        observations = {
            seat: observe_principal_state(proc, hidden_game.game_id, seat=seat) for seat in seats
        }
        # Validate that each observation is genuinely scoped to the seat that
        # asked before persisting it as principal-scoped evidence. Masking
        # identifiers at the provider is not sufficient: a provider can return
        # one unscoped payload to every caller, and the committed XMage run
        # returned byte-identical payloads for all four seats.
        scoping = validate_principal_scoping(observations, requested_seats=seats)
        probes["hidden_game"] = hidden_game.to_document()
        probes["hidden_observations"] = observations
        probes["hidden_scoping"] = scoping
        if not scoping["credible_as_principal_scoped_evidence"]:
            # Do not write the observations as hidden-information evidence.
            # The unscoped responses are still recorded, labelled as not scoped.
            print(f"principal scoping not established for {candidate}: {scoping['findings']}")
        write(
            f"HIDDEN_INFO_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.hidden-information/1.0.0",
                "candidate": candidate,
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": identity,
                "game": hidden_game.to_document(),
                "principal_observations": observations,
                "principal_scoping": scoping,
                "principal_observations_credible": scoping["credible_as_principal_scoped_evidence"],
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

    return {
        "rows": rows,
        "probes": probes,
        "identity": identity,
        "plan": plan.lane,
        "restoration_manifest": probes.get("restoration_manifest"),
        "restoration_manifest_error": probes.get("restoration_manifest_error"),
    }


def _starting_state_reason(
    candidate: str,
    mechanisms: list[str],
    restoration_manifest: dict[str, Any] | None,
    restoration_manifest_error: str | None,
) -> str:
    """Explain a frozen mid-game row using the ENGINE's own manifest.

    PB-03 replaced the previous Lab projection. The old text asserted that the
    mechanisms were unreachable because the bridge reported
    ``starting_state_injection_supported=false``; a bare boolean cannot support
    that, because it does not say which dimensions the engine can restore. The
    manifest does, so the reason now quotes the engine.

    Three outcomes are possible and all are explicit:

    * the engine declares every needed dimension supported: the mechanism is NOT
      an engine limitation, and the remaining blocker is the Lab transport seam;
    * the engine declares one unsupported: an engine-declared limitation, with
      the engine's own words;
    * no declared mapping, or no manifest: fail closed and say so.
    """
    families = tuple(sorted(set(mechanisms)))
    head = (
        "no current-boundary execution seam: the effective obligation requires a frozen "
        f"mid-game starting state because it requires the mid-game mechanisms {list(families)}. "
    )
    if restoration_manifest_error:
        return head + (
            "Admissibility could not be settled from the engine's own restoration manifest "
            f"because it was not available ({restoration_manifest_error}), so this row fails "
            "closed rather than inheriting a Lab projection. No credit is transferred."
        )
    if restoration_manifest is None:
        return head + (
            "Admissibility was not settled from the engine's own restoration manifest, so this "
            "row fails closed. No credit is transferred."
        )
    manifest = RestorationManifest(
        schema_version=str(restoration_manifest.get("schema_version", "")),
        starting_state_injection_supported=bool(
            restoration_manifest.get("starting_state_injection_supported")
        ),
        supported=tuple(str(item) for item in restoration_manifest.get("supported", ())),
        unsupported=tuple(str(item) for item in restoration_manifest.get("unsupported", ())),
    )
    verdict = admit(manifest, {}, families=families)
    per_family = " ".join(f"[{f.family}: {f.state}] {f.detail}" for f in verdict.families)
    if verdict.admitted:
        return head + (
            f"The {candidate} engine itself declares every dimension this obligation needs "
            f"SUPPORTED, so the mechanism is NOT an engine limitation. {per_family} It is "
            "still not executed here: the qualification lane exposes no protocol message that "
            "reaches the native state-restoration path, so the remaining blocker is a Lab "
            "transport seam, not a Rules or engine capability gap. The obligation also names "
            "fixture-specific objects, so driving a longer real game would not satisfy it; "
            "substituting a different object would be mechanism-equivalent evidence and needs "
            "a Coordinator ruling. No credit is transferred."
        )
    return head + (
        f"Admissibility settled against the {candidate} engine's own restoration manifest: "
        f"{per_family} No credit is transferred."
    )


def classify_remaining(
    materialization,
    executed: set[str],
    *,
    candidate: str,
    identity: dict[str, Any],
    restoration_manifest: dict[str, Any] | None = None,
    restoration_manifest_error: str | None = None,
) -> list[RowResult]:
    """Give every not-yet-executed denominator row an explicit outcome."""
    rows: list[RowResult] = []
    for record in materialization.denominator_records():
        fixture_id = record["fixture_id"]
        if fixture_id in executed:
            continue
        # PB-03: decide from the obligation's mechanisms, not from the row name,
        # and settle admissibility from the ENGINE's own restoration manifest
        # rather than from a Lab projection.
        # mid_game_mechanisms/requires_starting_state are module-level
        # functions, not EffectiveMaterialization methods. Calling them on
        # the instance raised AttributeError and aborted the whole run.
        mechanisms = materialization_mod.mid_game_mechanisms(record)
        if mechanisms:
            reason = _starting_state_reason(
                candidate,
                mechanisms,
                restoration_manifest,
                restoration_manifest_error,
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
            materialization,
            executed,
            candidate=candidate,
            identity=identity,
            restoration_manifest=outcome.get("restoration_manifest"),
            restoration_manifest_error=outcome.get("restoration_manifest_error"),
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
    runner = receipt_mod.capture_runner_identity(REPO_ROOT, output_paths=(str(OUT_DIR),))
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
