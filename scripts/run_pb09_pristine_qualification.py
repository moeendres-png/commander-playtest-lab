#!/usr/bin/env python3
"""PB-09 pristine-upstream Forge runtime qualification runner.

The current-boundary runner (``scripts/run_current_boundary_qualification.py``)
executes the effective FULL107 denominator against the Commander-Lab Forge
**fork** at ``ef958ee9``, because that is the engine the current-boundary
evidence is about. PB-09 is a different question: what does the *pinned,
pristine upstream* candidate (``config/rules_engines.json``
``secondary_engine.commit`` = ``a37a865a`` = upstream ``forge-2.0.14``) actually
do when it is observed through a lawful full-rules integration boundary?

This runner is a PB-09-owned lane. It changes nothing about the fork lane:

* every detector, classifier, fail-closed rule and row vocabulary is REUSED
  AS-IS from ``commander_lab.qualification.current_boundary`` and from the
  current-boundary runner (imported as a module, so the row-classification
  semantics cannot drift from the evidence they are compared against);
* the engine identity is the pristine pin, read from the pin manifest rather
  than from a constant in this workstream;
* the evidence is written to its own tree and never touches the current-boundary
  fork evidence;
* the denominator is the canonical 107 and is asserted, never reduced.

The pinned bridge source (``secondary_engine.bridge_source``) is used as the
provider surface because it is the manifest's own statement of how the pinned
candidate is materialised: the Rules Core plus additive bridge surfaces. Its
Rules-Core modules are proven byte-identical to the pristine pin at run time by
``verify_engine_identity``, so anything this runner observes is a property of the
pristine upstream engine, not of a Lab Rules modification.

This is NOT a Rules engine. It materialises inputs, launches the exact engine
build, supplies externally discretionary choices among engine-offered options,
binds seeds the engine exposes, observes principal-scoped output and classifies
evidence. It never reconstructs legality or computes outcomes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    FORGE_CANDIDATE_COMMIT,
    boundary_receipt,
    build_deck,
    build_launch_plan,
    drive_commander_game,
    launch,
    observe_principal_state,
    run_af01,
    run_af03,
    validate_principal_scoping,
)
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary.full107 import (  # noqa: E402
    RowResult,
    cardinality_row,
    export_replay,
    run_cardinality,
    start2_row,
    summarize,
)
from commander_lab.qualification.current_boundary.materialization import (  # noqa: E402
    load_effective_materialization,
)

OUT_DIR = REPO_ROOT / "qualification" / "pb09-pristine-upstream-20260929"
RECEIPT_DIR = OUT_DIR / "receipts"

# The pinned candidate is read from the pin manifest, which is the sole
# machine-readable authority for engine pins. Hardcoding it here would create a
# second place that could drift away from the pin of record.
PIN_MANIFEST = REPO_ROOT / "config" / "rules_engines.json"


def pinned_candidate() -> dict[str, str]:
    """The pinned pristine candidate identity, read from the manifest."""
    document = json.loads(PIN_MANIFEST.read_text(encoding="utf-8"))
    secondary = document["secondary_engine"]
    return {
        "repository": str(secondary["repository"]),
        "commit": str(secondary["commit"]),
        "release": str(secondary.get("release", "")),
        "license": str(secondary.get("license", "")),
        "bridge_repository": str(secondary["bridge_source"]["repository"]),
        "bridge_commit": str(secondary["bridge_source"]["commit"]),
        "bridge_rules_core_base": str(secondary["bridge_source"]["rules_core_base_commit"]),
    }


def load_current_boundary_runner() -> ModuleType:
    """Import the current-boundary runner so its shared logic is reused as-is.

    REUSE_AS_IS. ``classify_remaining``, the actual-card corpus helpers and the
    row accounting are candidate-neutral and must not be reimplemented here: a
    second copy could drift from the very semantics the fork evidence is
    compared against, and a drift would silently change a verdict.
    """
    path = REPO_ROOT / "scripts" / "run_current_boundary_qualification.py"
    spec = importlib.util.spec_from_file_location("run_current_boundary_qualification", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit(f"cannot load the current-boundary runner at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The native TestNG classes that exist in the pinned bridge source. These are
# discovered from the checkout itself, not asserted: a class named in a binding
# that does not exist simply runs nothing, and a receipt with no tests earns no
# credit.
def pin_native_classes(workspace: Path) -> list[str]:
    test_root = workspace / "forge-protocol2-bridge" / "src" / "test" / "java"
    if not test_root.is_dir():
        return []
    return sorted(
        path.stem
        for path in test_root.rglob("*Test.java")
    )


# --------------------------------------------------------------------------- #
# PB-09 runner identity
# --------------------------------------------------------------------------- #
#
# The current-boundary identity machinery binds its own scripts and excludes its
# own output tree. PB-09 runs different scripts and writes a different tree, so
# it binds its own identity over its own executed inputs. The shared fail-closed
# rules are reused: an uncommitted or mutated runner still earns no receipt.

_PB09_EXECUTED_INPUT_GLOBS = (
    "scripts/run_pb09_pristine_qualification.py",
    "scripts/assemble_pb09_pristine_evidence.py",
    "scripts/run_current_boundary_qualification.py",
    "src/commander_lab/qualification/current_boundary/*.py",
    "src/commander_lab/engine/rules/*.py",
    "schemas/engine_adapter_protocol.schema.json",
    "config/rules_engines.json",
)
_PB09_RUN_OUTPUT_PREFIXES = ("qualification/pb09-pristine-upstream-20260929/",)


def _pb09_is_run_output(relative: str) -> bool:
    normalised = relative.strip().strip('"')
    return normalised.startswith(_PB09_RUN_OUTPUT_PREFIXES)


def capture_pb09_runner_identity(root: Path) -> receipt_mod.RunnerIdentity:
    """Bind the executing PB-09 qualification code, exactly as WSR22 binds its own."""
    resolved = root.resolve()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(resolved),
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        raise receipt_mod.ReceiptError(
            f"git status --porcelain failed: {status.stderr.strip()[:200]}"
        )
    dirty_paths = tuple(
        line[3:] for line in status.stdout.splitlines() if line.strip() and not _pb09_is_run_output(line[3:])
    )
    import hashlib

    digests: dict[str, str] = {}
    for pattern in _PB09_EXECUTED_INPUT_GLOBS:
        for path in sorted(resolved.glob(pattern)):
            if path.is_file():
                digests[str(path.relative_to(resolved))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    if not digests:
        raise receipt_mod.ReceiptError("PB-09 runner identity captured zero executed inputs")
    return receipt_mod.RunnerIdentity(
        repository=_git(resolved, ["config", "--get", "remote.origin.url"]),
        commit=_git(resolved, ["rev-parse", "HEAD"]),
        tree=_git(resolved, ["rev-parse", "HEAD^{tree}"]),
        branch=_git(resolved, ["rev-parse", "--abbrev-ref", "HEAD"]),
        dirty=bool(dirty_paths),
        dirty_paths=dirty_paths,
        input_digests=digests,
        run_output_prefixes=_PB09_RUN_OUTPUT_PREFIXES,
    )


def _git(root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise receipt_mod.ReceiptError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.rstrip("\n")


def verify_pb09_runner_unchanged(root: Path, identity: receipt_mod.RunnerIdentity) -> None:
    """Re-verify at receipt time that the executed PB-09 inputs still hash as recorded."""
    current = capture_pb09_runner_identity(root)
    if current.input_digests != identity.input_digests:
        changed = sorted(
            name
            for name in set(current.input_digests) | set(identity.input_digests)
            if current.input_digests.get(name) != identity.input_digests.get(name)
        )
        raise receipt_mod.ReceiptError(
            f"RUNNER_MUTATED: executed PB-09 inputs changed during the run: {changed[:5]}"
        )
    if current.commit != identity.commit:
        raise receipt_mod.ReceiptError(
            f"RUNNER_MOVED: HEAD moved {identity.commit[:12]} -> {current.commit[:12]}"
        )


# --------------------------------------------------------------------------- #
# Runtime identity
# --------------------------------------------------------------------------- #


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd or REPO_ROOT), capture_output=True, text=True, check=False
    ).stdout.strip()


def pb09_runtime_identity(
    *, pinned: dict[str, str], workspace: Path, lane: str, bridge_note: str
) -> dict[str, Any]:
    """The exact identity every row produced in this run is stamped with.

    The engine commit is the pristine pin. The adapter commit is the bridge
    checkout that actually supplied the provider surface. They are separate
    fields because they are separate identities, and a row may not be attributed
    to the bridge commit.
    """
    return {
        "lane": lane,
        "boundary": "PB09_PRISTINE_UPSTREAM_EXECUTION",
        "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
        "runner_commit": git("rev-parse", "HEAD"),
        "runner_tree": git("rev-parse", "HEAD^{tree}"),
        "engine_candidate_commit": pinned["commit"],
        "engine_candidate_repository": pinned["repository"],
        "engine_candidate_release": pinned["release"],
        "engine_identity_class": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
        "adapter": f"forge-protocol2-bridge @ {workspace}",
        "adapter_commit": git("rev-parse", "HEAD", cwd=workspace),
        "adapter_repository": pinned["bridge_repository"],
        "adapter_manifest_pin": pinned["bridge_commit"],
        "bridge_note": bridge_note,
        "lab_fork_reference_not_executed": FORGE_CANDIDATE_COMMIT,
        "nonclaims": [
            "this run is about the pinned pristine candidate, not the Commander-Lab fork",
            "no result here is evidence for the fork column, and no fork result transfers here",
            "PB-09 itself remains OPEN and is a Coordinator decision",
        ],
    }


def write(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(f"wrote {name}")


# --------------------------------------------------------------------------- #
# The boundary execution
# --------------------------------------------------------------------------- #


def execute_lane(
    base: ModuleType,
    *,
    pinned: dict[str, str],
    workspace: Path,
    materialization: Any,
    lane: str,
    af01_player_count: int,
    hidden_player_count: int,
    bridge_note: str,
) -> dict[str, Any]:
    """Execute the boundary for one pristine candidate lane."""
    identity = pb09_runtime_identity(
        pinned=pinned, workspace=workspace, lane=lane, bridge_note=bridge_note
    )
    plan = build_launch_plan(
        "forge",
        lane="protocol2-jsonl",
        forge_workspace=workspace,
        forge_expected_commit=pinned["commit"],
    )
    by_id = {record["fixture_id"]: record for record in materialization.denominator_records()}
    rows: list[RowResult] = []
    probes: dict[str, Any] = {}

    with launch(plan) as proc:
        # ---- a real live game for the decision-time invariants -----------
        # The live-game player count is a property of what the provider actually
        # supports, not a constant of this script. The pristine candidate paired
        # with the pinned bridge source qualifies exactly four players, so a
        # two-player probe would fail for a reason unrelated to decision-time
        # legality and every decision-time invariant would be credited or
        # refused for the wrong reason. The count used is recorded below.
        af01_live = drive_commander_game(
            proc,
            candidate="forge",
            player_count=af01_player_count,
            seed=int(identity.get("af01_probe_seed", 20260927)),
            drive_to="priority",
        )
        af01_game_id = af01_live.game_id
        probes["af01_live_game"] = {
            "game_id": af01_game_id,
            "player_count_requested": af01_player_count,
            "player_count_created": af01_live.terminal_facts.get("created_player_count"),
            "steps_completed": list(af01_live.steps_completed),
            "decisions_observed": len(af01_live.decision_tape),
            "failure": af01_live.failure,
            "player_count_rule": (
                "the live-game count is the count this provider actually supports; probing a "
                "count the provider refuses would make every decision-time invariant a "
                "result about player-count gating rather than about decision-time legality"
            ),
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
            candidate="forge",
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
        write(f"AF01_{lane.upper()}.json", af01_doc)
        probes["af01_verdict"] = af01.verdict
        declared = af01_doc.get("capabilities_provider_reported") or {}
        identity["starting_state_injection_supported"] = declared.get(
            "starting_state_injection_supported"
        )
        identity["scenario_injection_supported"] = declared.get("scenario_injection_supported")
        identity["seed_supported"] = declared.get("seed_supported")
        identity["capabilities_provider_reported"] = declared

        # ---- AF03 RULES_AUTHORITY: negative deck-import probes ----------
        af03 = run_af03(proc, candidate="forge", legal_deck=build_deck("af03-control"))
        af03_document = af03.to_document()
        write(f"AF03_{lane.upper()}.json", af03_document)
        probes["af03_verdict"] = af03.verdict
        af03_evidence = {
            "verdict": af03_document["verdict"],
            "probes_passed": [
                p["invariant"] for p in af03_document["probes"] if p["verdict"] == "PASS"
            ],
            "probes_failed": [
                p["invariant"] for p in af03_document["probes"] if p["verdict"] == "FAIL"
            ],
            "probes_unknown": [
                p["invariant"] for p in af03_document["probes"] if p["verdict"] == "UNKNOWN"
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
        # Every count is ATTEMPTED. A provider that refuses a count is observed
        # refusing it, and the refusal is recorded as the run's result rather
        # than being replaced by a declared capability. Construction is not
        # multiplayer correctness, and a refused construction is neither.
        cardinality: dict[str, Any] = {}
        for count in (2, 3, 4, 5, 6):
            result = run_cardinality(
                proc, candidate="forge", player_count=count, runtime_identity=identity
            )
            document = result.to_document()
            cardinality[f"{count}P"] = document
            fixture = f"PLAYER_COUNT_{count}P"
            if fixture in by_id:
                rows.append(
                    cardinality_row(by_id[fixture], result, candidate="forge", runtime_identity=identity)
                )
        probes["cardinality"] = cardinality
        write(
            f"PLAYER_CARDINALITY_{lane.upper()}.json",
            {
                "schema_version": "pb09.player-cardinality/1.0.0",
                "lane": lane,
                "candidate": "forge",
                "candidate_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
                "boundary": "PB09_PRISTINE_UPSTREAM_EXECUTION",
                "runtime_identity": identity,
                "required_counts": [2, 3, 4, 5],
                "bounded_secondary_counts": [6],
                "all_counts_attempted": True,
                "results": cardinality,
            },
        )

        # ---- START-2 under the v1.0.6 successor --------------------------
        rows.append(
            start2_row(by_id["WS05-CMD-START-2"], proc, candidate="forge", runtime_identity=identity)
        )

        # ---- hidden-information principal probe ---------------------------
        hidden_game = drive_commander_game(
            proc,
            candidate="forge",
            player_count=hidden_player_count,
            seed=424242,
            drive_to="priority",
            max_steps=60,
        )
        seats = tuple(f"p{index}" for index in range(1, hidden_player_count + 1))
        observations = {
            seat: observe_principal_state(proc, hidden_game.game_id, seat=seat) for seat in seats
        }
        scoping = validate_principal_scoping(observations, requested_seats=seats)
        probes["hidden_game"] = hidden_game.to_document()
        probes["hidden_game_seed_binding"] = hidden_game.seed_binding
        probes["hidden_observations"] = observations
        probes["hidden_scoping"] = scoping
        if not scoping["credible_as_principal_scoped_evidence"]:
            print(f"principal scoping not established: {scoping['findings']}")
        write(
            f"HIDDEN_INFO_{lane.upper()}.json",
            {
                "schema_version": "pb09.hidden-information/1.0.0",
                "lane": lane,
                "candidate": "forge",
                "candidate_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
                "boundary": "PB09_PRISTINE_UPSTREAM_EXECUTION",
                "runtime_identity": identity,
                "game": hidden_game.to_document(),
                "principal_observations": observations,
                "principal_scoping": scoping,
                "principal_observations_credible": scoping[
                    "credible_as_principal_scoped_evidence"
                ],
                "hidden_scenario_rows_note": (
                    "the per-scenario hidden rows (face-down exile, look, controlled-player, "
                    "shuffle invalidation) need per-scenario channel instrumentation that this "
                    "provider surface does not expose; they are recorded as UNKNOWN by the "
                    "shared classifier and are not credited here"
                ),
            },
        )

        # ---- Rules RNG + semantic replay ----------------------------------
        replay_payload = export_replay(proc, hidden_game.game_id)
        try:
            event_log = proc.request("export_event_log", {}, game_id=hidden_game.game_id)
        except Exception as exc:  # a transport failure is a recorded result
            event_log = {"error": str(exc)}
        probes["replay"] = replay_payload
        probes["event_log"] = (
            event_log.get("payload") if isinstance(event_log.get("payload"), dict) else event_log
        )
        write(
            f"RNG_REPLAY_{lane.upper()}.json",
            {
                "schema_version": "pb09.rng-replay/1.0.0",
                "lane": lane,
                "candidate": "forge",
                "candidate_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
                "boundary": "PB09_PRISTINE_UPSTREAM_EXECUTION",
                "runtime_identity": identity,
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
                "replay_twin": (
                    "no clean-process twin is executed by this runner; the twin half of the "
                    "replay obligation is therefore unproven here and earns no credit"
                ),
            },
        )

        # ---- actual-card probe -------------------------------------------
        frozen_corpus = base.frozen_actual_card_corpus()
        card_identities = base.card_fixture_identities()
        passed_rows = {row.fixture_id for row in rows if row.outcome == "PASS"}
        covered_corpus = {
            identity_
            for fixture_id, identity_ in card_identities.items()
            if fixture_id in passed_rows
        }
        unexecuted_card_rows = sorted(
            fixture_id for fixture_id in card_identities if fixture_id not in passed_rows
        )
        write(
            f"ACTUAL_CARD_{lane.upper()}.json",
            {
                "schema_version": "pb09.actual-card/1.0.0",
                "lane": lane,
                "candidate": "forge",
                "candidate_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
                "boundary": "PB09_PRISTINE_UPSTREAM_EXECUTION",
                "runtime_identity": identity,
                "cards_imported_at_runtime": hidden_game.deck_identity,
                "engine_validated": af03_evidence,
                "required_29_card_corpus": {
                    "required_count": len(frozen_corpus),
                    "required_identities_source": base.ACTUAL_CARD_DOMAIN_MANIFEST.name,
                    "behaviorally_executed_cards": sorted(covered_corpus),
                    "behaviorally_executed_count": len(covered_corpus),
                    "missing_identities": sorted(set(frozen_corpus) - covered_corpus),
                    "card_fixtures": len(card_identities),
                    "card_fixtures_passed": len(card_identities) - len(unexecuted_card_rows),
                    "unexecuted_card_fixtures": unexecuted_card_rows,
                    "complete": not (set(frozen_corpus) - covered_corpus),
                    "statement": (
                        f"{len(covered_corpus)} of the {len(frozen_corpus)} frozen corpus "
                        "identities have their own mandatory fixture row passing; import, "
                        "parsing, construction and lookup are never counted as behaviour"
                    ),
                },
            },
        )

    return {"rows": rows, "probes": probes, "identity": identity, "plan": plan.lane}


# --------------------------------------------------------------------------- #
# Native suites (PB-09 binding)
# --------------------------------------------------------------------------- #


def run_native_suite(
    *,
    workspace: Path,
    lane: str,
    pinned: dict[str, str],
    classes: list[str],
    runner: receipt_mod.RunnerIdentity,
) -> dict[str, Any]:
    """Execute the pristine candidate's own native suite fresh, with a receipt.

    The receipt names the engine the suite is about (the pristine pin), the
    commit that actually executed (the bridge checkout), and the proof that the
    Rules Core of the executing commit is byte-identical to the pinned engine.
    Without that proof the receipt earns no credit, so a descendant that touched
    Rules-Core source could never be credited to the pin.
    """
    receipt_mod.require_clean_runner(runner)
    actual_head = git("rev-parse", "HEAD", cwd=workspace)
    equivalence = receipt_mod.verify_engine_identity(
        workspace,
        recorded_commit=pinned["commit"],
        actual_commit=actual_head,
        recorded_label=f"pb09 native suite {lane}",
    )
    print(f"engine identity {lane}: {equivalence['justification']}")
    argv = [
        "mvn",
        "-o",
        # Scope to the bridge module. The candidate's full reactor includes
        # forge-gui-mobile, whose libGDX dependencies were never fetched into this
        # environment, so an unscoped `mvn test` fails on a missing third-party
        # artifact before any provider test can run. That is an environment
        # defect in the test invocation, not a candidate or suite failure, and
        # scoping the invocation is the smallest repair that leaves the engine
        # and the assertions untouched.
        "-pl",
        "forge-protocol2-bridge",
        "-Dcheckstyle.skip=true",
        "-DfailIfNoTests=false",
        "-Dsurefire.failIfNoSpecifiedTests=false",
        "-Dtest=" + ",".join(classes),
        "test",
    ]
    started = receipt_mod._now()
    completed = subprocess.run(
        argv, cwd=str(workspace), capture_output=True, text=True, check=False, timeout=7200
    )
    text = completed.stdout + completed.stderr
    try:
        summary = receipt_mod.parse_maven_summary(text)
    except receipt_mod.ReceiptError as exc:
        print(f"native suite {lane}: {exc}")
        summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    verify_pb09_runner_unchanged(REPO_ROOT, runner)
    receipt = receipt_mod.NativeSuiteReceipt(
        candidate="forge",
        group=lane,
        command=" ".join(argv),
        candidate_repository=pinned["repository"],
        candidate_commit=pinned["commit"],
        candidate_tree=git("rev-parse", pinned["commit"] + "^{tree}", cwd=workspace)
        or "UNCONFIGURED",
        executed_commit=actual_head,
        engine_identity_proof=equivalence,
        build_identity=json.dumps(
            {"bridge": "forge-protocol2-bridge", "lane": "maven-surefire", "pb09_lane": lane},
            sort_keys=True,
        ),
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
        classes=tuple(classes),
    )
    document = receipt.to_document()
    document["result_lines"] = [
        line.strip() for line in text.splitlines() if "Tests run:" in line
    ][-12:]
    document.pop("receipt_digest", None)
    document["receipt_digest"] = receipt_mod._digest(document)
    path = RECEIPT_DIR / f"native-pristine-{lane}.json"
    receipt_mod.persist(path, document)
    print(f"native receipt {lane} -> {path.name} rc={completed.returncode}")
    return document


# --------------------------------------------------------------------------- #
# Lanes
# --------------------------------------------------------------------------- #


LANES: dict[str, dict[str, Any]] = {
    # The pin of record, materialised exactly as the manifest states: pristine
    # upstream Rules Core plus the pinned bridge source.
    "pin": {
        "workspace": Path(
            os.environ.get(
                "PB09_PIN_WORKSPACE", "/home/moeen/code/pb09-forge-bridge-pin-20260929"
            )
        ),
        "af01_player_count": 4,
        "hidden_player_count": 4,
        "bridge_note": (
            "the manifest's own bridge_source pin (secondary_engine.bridge_source.commit), "
            "whose six Rules-Core modules are byte-identical to the pristine candidate"
        ),
    },
    # The current provider architecture's bridge head, materialised onto the
    # pristine Rules Core. Its build outcome is measured, not assumed.
    "current_bridge": {
        "workspace": Path(
            os.environ.get(
                "PB09_CURRENT_BRIDGE_WORKSPACE",
                "/home/moeen/code/pb09-forge-bridge-current-20260929",
            )
        ),
        "af01_player_count": 4,
        "hidden_player_count": 4,
        "bridge_note": (
            "the Lab main bridge/evidence head of record (Forge PR #5 head) checked out onto "
            "the pristine Rules Core; build outcome measured separately"
        ),
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", default="pin", choices=sorted(LANES))
    parser.add_argument(
        "--phase", default="all", choices=["execute", "native", "all"]
    )
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pinned = pinned_candidate()
    if pinned["bridge_rules_core_base"] != pinned["commit"]:
        raise SystemExit(
            "the manifest's bridge_source must name the pristine candidate as its Rules-Core "
            f"base: {pinned['bridge_rules_core_base']} != {pinned['commit']}"
        )
    print(
        "pinned pristine candidate:",
        json.dumps(
            {"commit": pinned["commit"], "release": pinned["release"], "bridge": pinned["bridge_commit"]},
            indent=1,
        ),
    )

    base = load_current_boundary_runner()
    # The effective materialization is resolved by the canonical resolver, never
    # reimplemented: PB-09 must measure the same 107 rows the current boundary
    # measures, or the comparison between them would not be a comparison.
    materialization = load_effective_materialization(REPO_ROOT)
    lane = LANES[args.lane]
    workspace = lane["workspace"]
    if not workspace.is_dir():
        raise SystemExit(f"lane {args.lane}: engine workspace absent: {workspace}")

    # The pin must be what it claims: the Rules Core of the executing bridge
    # checkout has to be byte-identical to the pristine pin, or nothing this
    # runner observes is about the pristine candidate.
    executing_head = git("rev-parse", "HEAD", cwd=workspace)
    equivalence = receipt_mod.verify_engine_identity(
        workspace,
        recorded_commit=pinned["commit"],
        actual_commit=executing_head,
        recorded_label=f"pb09 lane {args.lane}",
    )
    print(f"lane {args.lane} engine identity: {equivalence['justification']}")
    write(
        f"PRISTINE_ENGINE_IDENTITY_{args.lane.upper()}.json",
        {
            "schema_version": "pb09.engine-identity/1.0.0",
            "lane": args.lane,
            "pinned_candidate": pinned,
            "executing_checkout_head": executing_head,
            "executing_checkout_head_tree": git("rev-parse", "HEAD^{tree}", cwd=workspace),
            "rules_core_equivalence": equivalence,
            "statement": (
                "every observation in this lane is a property of the pristine upstream "
                "candidate: the six Rules-Core modules of the executing checkout are "
                "byte-identical to the pinned commit, and the bridge module is bound "
                "separately as the provider surface"
            ),
        },
    )

    if args.phase in ("execute", "all"):
        write(
            "EFFECTIVE_FULL107_MANIFEST.json",
            {
                **materialization.receipt(),
                "lane": args.lane,
                "evidence_migration": materialization.bundle.get("evidence_migration"),
                "denominator_unchanged": True,
                "denominator_decreased_to_bypass_blocker": False,
                "rows": [
                    {
                        "fixture_id": record["fixture_id"],
                        "fixture_family": record.get("fixture_family"),
                        "player_count": record.get("player_count"),
                        "effective_obligation_digest": record.get("obligation_digest"),
                        "materialization_status": record.get("materialization_status"),
                        "required_events": record.get("expected_events", {}).get(
                            "required_events", []
                        ),
                        "forbidden_events": record.get("expected_events", {}).get(
                            "forbidden_events", []
                        ),
                    }
                    for record in materialization.denominator_records()
                ],
            },
        )
        outcome = execute_lane(
            base,
            pinned=pinned,
            workspace=workspace,
            materialization=materialization,
            lane=args.lane,
            af01_player_count=lane["af01_player_count"],
            hidden_player_count=lane["hidden_player_count"],
            bridge_note=lane["bridge_note"],
        )
        identity = outcome["identity"]
        executed = {row.fixture_id for row in outcome["rows"]}
        rows = outcome["rows"] + base.classify_remaining(
            materialization, executed, candidate="forge", identity=identity
        )
        by_id = {
            record["fixture_id"]: record for record in materialization.denominator_records()
        }
        documents = [row.to_document(by_id[row.fixture_id]) for row in rows]
        counts = summarize(rows)
        assert len(documents) == 107, f"PB-09 {args.lane}: {len(documents)} rows"
        write(
            f"FULL107_PRISTINE_{args.lane.upper()}_RESULTS.json",
            {
                "schema_version": "pb09.full107-results/1.0.0",
                "lane": args.lane,
                "candidate": "forge",
                "candidate_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
                "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
                "evidence_class": "PB09_PRISTINE_UPSTREAM_EXECUTION",
                "runtime_identity": identity,
                "counts": counts,
                "total": len(documents),
                "denominator_decreased_to_bypass_blocker": False,
                "rows": documents,
            },
        )
        write(
            f"FULL107_PRISTINE_{args.lane.upper()}_RUNTIME_LOG_INDEX.json",
            {
                "schema_version": "pb09.runtime-log-index/1.0.0",
                "lane": args.lane,
                "runtime_identity": identity,
                "boundary": "PB09_PRISTINE_UPSTREAM_EXECUTION",
                "cardinality": outcome["probes"].get("cardinality"),
                "denominator_complete": True,
            },
        )
        (OUT_DIR / f"_probes_{args.lane}.json").write_text(
            json.dumps(outcome["probes"], indent=1, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({args.lane: counts}, indent=1))

    if args.phase in ("native", "all"):
        runner = capture_pb09_runner_identity(REPO_ROOT)
        receipt_mod.require_clean_runner(runner)
        print(
            "PB-09 runner bound:",
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
        classes = pin_native_classes(workspace)
        if not classes:
            raise SystemExit(
                f"lane {args.lane}: no native test classes are present in {workspace}; "
                "no native credit is possible and the run must not claim one"
            )
        document = run_native_suite(
            workspace=workspace,
            lane=args.lane,
            pinned=pinned,
            classes=classes,
            runner=runner,
        )
        write(
            "NATIVE_SUITE_RECEIPTS.json",
            {
                "schema_version": "pb09.native-suite-receipt-index/1.0.0",
                "lane": args.lane,
                "runner": runner.to_document(),
                "receipt_count": 1,
                "receipt_digest": document["receipt_digest"],
                "classes": classes,
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
