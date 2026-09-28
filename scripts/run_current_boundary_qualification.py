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

from commander_lab.qualification.current_boundary import (  # noqa: E402
    FORGE_CANDIDATE_COMMIT,
    FORGE_WSR20_EVIDENCE_TIP,
    NEGATIVE_ROWS,
    PILOT_ROWS,
    REPLAY_ROWS,
    XMAGE_CANDIDATE_COMMIT,
    XMAGE_LAB_RUNTIME_AUTHORITY,
    boundary_receipt,
    build_deck,
    build_launch_plan,
    cardinality_row,
    drive_commander_game,
    export_replay,
    launch,
    load_effective_materialization,
    mid_game_mechanisms,
    non_executed_row,
    observe_principal_state,
    run_af01,
    run_af03,
    start2_row,
    validate_principal_scoping,
)
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary.full107 import (  # noqa: E402
    HIDDEN_SCENARIO_ROWS,
    NATIVE_MICRO_ROWS,
    RowResult,
    run_cardinality,
    summarize,
)

OUT_DIR = Path(
    os.environ.get(
        "COMMANDER_LAB_OUT_DIR",
        str(REPO_ROOT / "qualification" / "final-current-boundary-20260927"),
    )
)

# Native harness suites that bind FULL107 fixture ids. Each entry is executed
# fresh in this workstream; historical PASS is never transferred.
# Execution receipts live beside the evidence they justify. The assembler reads
# only what is persisted here, so an unexecuted suite can never be credited.
RECEIPT_DIR = OUT_DIR / "receipts"
# The Forge checkout the native suites execute in. Configurable so the bound
# bridge/evidence head can be a detached worktree at the exact Forge PR head
# without moving any other lane's checkout. The default remains the historical
# WSR20 evidence checkout.
#
# The Rules Core this must be equivalent to is ef958ee9/fc3387b; the bridge and
# evidence head is Forge PR #4 d5bd22d1, which changes forge-protocol2-bridge
# only. engine_tree_equivalence re-proves that separation on every run.
#
# PB-09 pristine-upstream runs point this at the isolated pristine worktree via
# COMMANDER_LAB_FORGE_WORKSPACE (preferred) or FORGE_WORKSPACE, with the engine
# commit overridden below; that lane is recorded separately and never conflated
# with the fork/PR-#4 identities above.
FORGE_WORKSPACE = Path(
    os.environ.get("COMMANDER_LAB_FORGE_WORKSPACE")
    or os.environ.get("FORGE_WORKSPACE", "/home/moeen/code/ws-forge-full107-cdq-20260926")
)
# PB-09 pristine-upstream runs override the executed engine commit (and only
# that): the workspace HEAD must equal this commit or the run fails closed.
FORGE_ENGINE_COMMIT_OVERRIDE = os.environ.get("COMMANDER_LAB_FORGE_ENGINE_COMMIT") or None


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


# The actual-card names this artifact declares. Named once so the corpus
# completeness statement is derived from the list rather than restated in prose.
ACTUAL_CARD_NAMES: tuple[str, ...] = (
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
)

# The actual-card corpus the effective contract requires. The IDENTITIES are
# loaded from the frozen domain manifest rather than restated here: a local list
# can drift from the contract, and measuring completion against a drifted list
# would advertise a corpus nobody required. The declared ACTUAL_CARD_NAMES above
# shares ZERO members with the frozen 29, so a count derived from it measured
# nothing.
ACTUAL_CARD_DOMAIN_MANIFEST = REPO_ROOT / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json"
COMMON_FIXTURE_MANIFEST = REPO_ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"


def card_fixture_identities() -> dict[str, str]:
    """Map each CARD_nn fixture to the card identity it is required to exercise.

    The frozen corpus is not one obligation. It is twenty-nine separate mandatory
    fixtures, each with its own identity, and coverage must come from each of
    those rows passing. Reading a single CARD_02 result and trusting an
    `executed_cards` list attached to it would let one row claim the corpus while
    the other twenty-eight remained unexecuted.
    """
    document = json.loads(COMMON_FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for fixture in document["fixtures"]:
        fixture_id = str(fixture.get("fixture_id") or "")
        identity = fixture.get("card_identity")
        if fixture_id.startswith("CARD_") and identity:
            mapping[fixture_id] = str(identity)
    if not mapping:
        raise SystemExit(
            f"{COMMON_FIXTURE_MANIFEST} assigns no card identity to any CARD_ fixture; "
            "corpus coverage cannot be derived"
        )
    return mapping


def frozen_actual_card_corpus() -> tuple[str, ...]:
    """The frozen regression corpus identities, in manifest order."""
    document = json.loads(ACTUAL_CARD_DOMAIN_MANIFEST.read_text(encoding="utf-8"))
    corpus = document["regression_corpus_29"]
    if not isinstance(corpus, list) or not corpus:
        raise SystemExit(
            f"{ACTUAL_CARD_DOMAIN_MANIFEST} carries no regression_corpus_29; the "
            "actual-card obligation cannot be measured"
        )
    return tuple(str(name) for name in corpus)


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
                "engine_candidate_commit": FORGE_ENGINE_COMMIT_OVERRIDE or FORGE_CANDIDATE_COMMIT,
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
    # The engine-drift comparison only applies where the engine is its own Git
    # repository. The Forge suites execute in a Forge checkout, so a Rules-Core
    # drift check is meaningful there. The XMage bridge is a module of the Lab
    # repository, so `HEAD` there is the Lab's own commit, not the XMage engine's,
    # and comparing it against the XMage engine commit compares two unrelated
    # things. XMage's engine identity is the provider's own reported commit, which
    # AF00 verifies fail-closed at handshake, so nothing is lost by not
    # pretending a checkout exists where it does not.
    actual_head = git("rev-parse", "HEAD", cwd=spec["root"])
    engine_toplevel = git("rev-parse", "--show-toplevel", cwd=spec["root"])
    root_is_own_repo = (
        bool(engine_toplevel) and Path(engine_toplevel).resolve() == spec["root"].resolve()
    )
    if root_is_own_repo:
        engine_equivalence = receipt_mod.verify_engine_identity(
            spec["root"],
            recorded_commit=spec["expected_engine_commit"],
            actual_commit=actual_head,
            recorded_label=f"native suite {candidate}:{group}",
        )
        print(
            f"engine identity {candidate}:{group}: "
            f"{engine_equivalence['justification']} "
            f"(recorded {spec['expected_engine_commit'][:12]}, "
            f"executing {actual_head[:12]})"
        )
    else:
        engine_equivalence = {
            "engine_equivalent": None,
            "justification": "ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT",
            "recorded_commit": spec["expected_engine_commit"],
            "actual_commit": actual_head,
            "suite_root": str(spec["root"]),
            "containing_repository": engine_toplevel or "UNKNOWN",
            "detail": "the executing suite root is a module of the containing repository, "
            "so its HEAD identifies that repository, not the engine. The engine identity "
            "is the provider's own reported commit, verified fail-closed at handshake by "
            "AF00. No checkout identity is asserted for this candidate.",
        }
        print(
            f"engine identity {candidate}:{group}: not a separate checkout; engine identity "
            f"comes from the provider handshake (expected {spec['expected_engine_commit'][:12]})"
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
        executed_commit=actual_head,
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
    plan = build_launch_plan(
        candidate,
        lane=lane,
        forge_workspace=workspace,
        forge_engine_commit=FORGE_ENGINE_COMMIT_OVERRIDE,
    )

    by_id = {record["fixture_id"]: record for record in materialization.denominator_records()}
    rows: list[RowResult] = []
    probes: dict[str, Any] = {}

    with launch(plan) as proc:
        # ---- a real live game for the decision-time invariants -----------
        # AF01's fail-closed decision probes were previously issued with no
        # game at all. A provider asked to fail closed on a submission for a
        # game that does not exist refuses for reasons unrelated to
        # decision-time legality, so those results were passes for the wrong
        # reason. Drive a real Commander game to its first priority decision
        # and probe against that game instead.
        af01_live = drive_commander_game(
            proc,
            candidate=candidate,
            player_count=2,
            seed=int(identity.get("af01_probe_seed", 20260927)),
            drive_to="priority",
        )
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
        # Carry the provider's DECLARED capabilities into the run identity. Block
        # attribution must consult what this candidate says it supports, not a
        # hard-coded statement about one candidate applied to all of them.
        declared = af01_doc.get("capabilities_provider_reported") or {}
        identity["starting_state_injection_supported"] = declared.get(
            "starting_state_injection_supported"
        )
        identity["scenario_injection_supported"] = declared.get("scenario_injection_supported")
        identity["seed_supported"] = declared.get("seed_supported")
        identity["capabilities_provider_reported"] = declared

        # ---- AF03 RULES_AUTHORITY: negative deck-import probes ----------
        af03 = run_af03(
            proc,
            candidate=candidate,
            legal_deck=build_deck("af03-control"),
        )
        af03_document = af03.to_document()
        write(f"AF03_{candidate.upper()}.json", af03_document)
        probes["af03_verdict"] = af03.verdict
        # What the engine actually did on negative import, stated from the probe.
        af03_evidence = {
            "verdict": af03_document["verdict"],
            "probes_passed": [
                probe["invariant"]
                for probe in af03_document["probes"]
                if probe["verdict"] == "PASS"
            ],
            "probes_failed": [
                probe["invariant"]
                for probe in af03_document["probes"]
                if probe["verdict"] == "FAIL"
            ],
            "probes_unknown": [
                probe["invariant"]
                for probe in af03_document["probes"]
                if probe["verdict"] == "UNKNOWN"
            ],
            "statement": (
                "the engine refused every negative deck-import probe in this run, so the "
                "import is engine-validated rather than construction-only"
                if af03.verdict == "PASS"
                else "the engine did NOT refuse every negative deck-import probe, so this run "
                "does not establish engine-validated import; see the failed probes"
            ),
        }

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
        probes["hidden_game_seed_binding"] = hidden_game.seed_binding
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
                # Derived from what the engine acknowledged, never asserted from
                # caller intent. This previously carried a literal
                # engine_owned: true with a hard-coded requested seed, which is
                # the original defect: it credited Rules RNG and replay control
                # that no observation established. The probe game is the same
                # driven game whose binding is recorded, so the value is real.
                "rules_rng_binding": (
                    probes["hidden_game_seed_binding"].to_document()
                    if probes.get("hidden_game_seed_binding") is not None
                    else {
                        "control": "UNCONTROLLED_ENGINE_RNG",
                        "detail": "no engine acknowledgement was observed for this run",
                        "rng_credit": False,
                    }
                ),
                "harness_injected_outcomes": False,
                "semantic_replay": replay_payload,
                "event_log": probes["event_log"],
                "same_seed_twin": "see comparison packet; twin runs are executed per candidate",
            },
        )

        # ---- actual-card probe -------------------------------------------
        # Cards whose behaviour was EXERCISED this run, derived from the
        # actual-card row outcomes. Naming or importing a card is not execution.
        # Read the ACTUAL row result, not the materialization record: only a row
        # that executed and passed can contribute executed cards.
        frozen_corpus = frozen_actual_card_corpus()
        # An identity is covered only when ITS OWN mandatory fixture row passed.
        # No list attached to any other row can claim it.
        card_identities = card_fixture_identities()
        passed_rows = {row.fixture_id for row in rows if row.outcome == "PASS"}
        covered_corpus = {
            identity
            for fixture_id, identity in card_identities.items()
            if fixture_id in passed_rows
        }
        unexecuted_card_rows = sorted(
            fixture_id for fixture_id in card_identities if fixture_id not in passed_rows
        )

        write(
            f"ACTUAL_CARD_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.actual-card/1.0.0",
                "candidate": candidate,
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": identity,
                "cards_imported_at_runtime": hidden_game.deck_identity,
                "cards": list(ACTUAL_CARD_NAMES),
                # Derived from the AF03 probe this run actually executed. It
                # previously asserted in prose that "the engine itself rejected an
                # illegal colour identity and unknown card names", which is the
                # OPPOSITE of what the observed probe shows for Forge: the
                # executed Forge bridge ACCEPTED a colour-identity violation and a
                # non-Commander commander. A prose claim that contradicts the run's
                # own evidence is a false credit, so the value is now the probe
                # verdicts.
                "engine_validated": af03_evidence,
                "required_29_card_corpus": {
                    "required_count": len(frozen_corpus),
                    "required_identities_source": ACTUAL_CARD_DOMAIN_MANIFEST.name,
                    "declared_in_this_artifact": len(ACTUAL_CARD_NAMES),
                    "declared_identities_in_frozen_corpus": len(
                        set(ACTUAL_CARD_NAMES) & set(frozen_corpus)
                    ),
                    # Decks are per seat, not per card. Counting them said nothing
                    # about the corpus.
                    "decks_imported_at_runtime": len(hidden_game.deck_identity),
                    # Counted against the FROZEN identities, not the local list.
                    # ACTUAL_CARD_NAMES shares zero members with the required
                    # corpus, and a row passing 29 arbitrary cards must not be able
                    # to claim the corpus it never touched.
                    "behaviorally_executed_cards": sorted(covered_corpus),
                    "behaviorally_executed_count": len(covered_corpus),
                    "missing_identities": sorted(set(frozen_corpus) - covered_corpus),
                    "card_fixtures": len(card_identities),
                    "card_fixtures_passed": len(card_identities) - len(unexecuted_card_rows),
                    "unexecuted_card_fixtures": unexecuted_card_rows,
                    "complete": not (set(frozen_corpus) - covered_corpus),
                    "statement": (
                        f"{len(covered_corpus)} of the {len(frozen_corpus)} frozen corpus "
                        "identities have their own mandatory fixture row passing; the corpus "
                        "is "
                        + (
                            "complete"
                            if not (set(frozen_corpus) - covered_corpus)
                            else "NOT executed, so the actual-card obligation is "
                            "unestablished and the row cannot be credited"
                        )
                    ),
                },
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
        if candidate == "forge":
            # No XMage-seam admission table applies to Forge, and no audited
            # Forge per-row execution binding exists in this run: every
            # non-lifecycle row is honestly UNKNOWN pending the Wave-F native
            # audit, never BLOCKED by a foreign seam's vocabulary.
            reason = (
                "pristine-upstream Forge run: no audited per-row execution "
                "binding exists for this obligation in this run (Wave-F native "
                "audit pending). No seam absence is proven, so no BLOCKED is "
                "claimed; no credit is transferred from the fork column."
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
            continue
        # PB-03: decide from the obligation's mechanisms, not from the row name.
        mechanisms = mid_game_mechanisms(record)
        if mechanisms:
            # The mechanism requirement is candidate-neutral, but the CAPABILITY is
            # not. This reason used to cite the XMage bridge's
            # starting_state_injection_supported=false for every candidate, so
            # Forge rows were attributed to a capability Forge actually declares
            # it has: AF01_FORGE.json reports starting_state_injection_supported
            # true and scenario_injection_supported true. Where the candidate
            # declares the capability and this run did not exercise the seam, the
            # block is a Lab EXECUTION-PATH gap, not a candidate capability gap,
            # and saying otherwise would misdirect remediation away from the work
            # that would actually unblock the rows.
            declares_injection = identity.get("starting_state_injection_supported")
            if declares_injection is True:
                reason = (
                    "no current-boundary execution seam, and this is a LAB EXECUTION-PATH "
                    f"gap rather than a candidate capability gap: the obligation requires a "
                    f"frozen mid-game starting state ({sorted(mechanisms)}), and this "
                    f"candidate DECLARES starting_state_injection_supported=true, but this "
                    "run did not exercise the injection seam. The rows stay unestablished "
                    "and uncredited; closing them requires Lab execution work, not "
                    "candidate remediation."
                )
                outcome = "BLOCKED"
            else:
                reason = (
                    "no current-boundary execution seam: the effective obligation requires a "
                    "frozen mid-game starting state because it requires the mid-game "
                    f"mechanisms {sorted(mechanisms)}, and this candidate reports "
                    "starting_state_injection_supported="
                    f"{declares_injection!r}. Native causal-reconstruction harnesses exist "
                    "for adjacent mechanisms but are not the same obligation; no credit is "
                    "transferred."
                )
                outcome = "BLOCKED"
            rows.append(
                non_executed_row(
                    record,
                    candidate=candidate,
                    outcome=outcome,
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
