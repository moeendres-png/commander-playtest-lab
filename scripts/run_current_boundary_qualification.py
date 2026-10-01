#!/usr/bin/env python3
"""WSR22 current-boundary qualification runner (candidate-neutral).

Executes the effective FULL107 provider denominator plus AF00-AF11 evidence
against the exact pinned candidate builds under
``commander-lab.pre-freeze-qualification/2.0.0`` and writes the evidence tree
under the source-bound runtime epoch resolved by
``commander_lab.qualification.current_boundary.evidence_epoch`` (the historical
WSR22 epoch is a read-only predecessor, never a write target).

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
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    NEGATIVE_ROWS,
    PILOT_ROWS,
    REPLAY_ROWS,
    XMAGE_LAB_RUNTIME_AUTHORITY,
    boundary_receipt,
    build_deck,
    build_launch_plan,
    canonical_forge_authority,
    canonical_forge_rules_core_pin,
    canonical_xmage_engine_pin,
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
from commander_lab.qualification.current_boundary import (  # noqa: E402
    dimension_admission as pb03_admission_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    evidence_epoch as epoch_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    midgame_rows as midgame_rows_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    pb03_runtime as pb03_runtime_mod,
)
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary.full107 import (  # noqa: E402
    HIDDEN_SCENARIO_ROWS,
    NATIVE_MICRO_ROWS,
    RowResult,
    run_cardinality,
    summarize,
)

# The evidence epoch this run writes into: an explicitly identified runtime
# epoch whose identity is the producing source (commit+tree), never the
# historical WSR22 tree. Both scripts resolve it through the one shared function
# so runner and assembler cannot disagree, and nothing here may name the
# historical epoch directly. See commander_lab.qualification.current_boundary.
# evidence_epoch for the invariants.
OUT_DIR = epoch_mod.epoch_root(REPO_ROOT)
EVIDENCE_EPOCH_RELATIVE = epoch_mod.relative_epoch_root(REPO_ROOT)
# Execution receipts live beside the evidence they justify. The assembler reads
# only what is persisted here, so an unexecuted suite can never be credited.
RECEIPT_DIR = OUT_DIR / "receipts"


class RunnerGitError(SystemExit):
    """A Git fact required for evidence could not be established (fail closed)."""


class ForgeWorkspaceError(SystemExit):
    """The Forge workspace is absent, ambiguous, or not the bound identity."""


def git(*args: str, cwd: Path | None = None) -> str:
    """A Git fact for an identity; fails closed instead of recording an empty string.

    Reads go through receipts.git_fact, which requires an existing directory, a
    finished command, return code 0, non-empty output and -- for HEAD/tree facts
    -- a full 40-hex SHA, over an environment with every Git redirection removed.
    The error type is a SystemExit subclass so a caller can distinguish it while
    the process still stops before any evidence names the failed fact.
    """
    sha = len(args) >= 2 and args[0] == "rev-parse" and args[-1] in {"HEAD", "HEAD^{tree}"}
    try:
        return receipt_mod.git_fact(cwd or REPO_ROOT, *args, sha=sha)
    except receipt_mod.ReceiptError as exc:
        raise RunnerGitError(f"no identity, no credit: {exc}") from exc


_SHA = re.compile(r"[0-9a-f]{40}")


def git_sha(*args: str, cwd: Path | None = None) -> str:
    """A Git object id required for evidence. Not a full SHA is not an identity."""
    value = git(*args, cwd=cwd)
    if not _SHA.fullmatch(value):
        raise RunnerGitError(
            f"git {' '.join(args)} in {cwd or REPO_ROOT} returned {value!r}, not a full SHA"
        )
    return value


def git_toplevel(root: Path) -> Path:
    """The work-tree root that owns ``root``; a non-repository fails closed."""
    return Path(git("rev-parse", "--show-toplevel", cwd=root)).resolve()


def _bridge_identity_proof(
    workspace: Path,
    *,
    expected_bridge_commit: str,
    expected_bridge_tree: str,
    actual_commit: str,
) -> dict[str, Any]:
    """Prove the executing bridge module is the bound bridge/evidence identity.

    The bridge is a separate identity from the Rules Core: transport and
    provenance, not Magic legality. It is bound separately, and the executable
    form of "the same bridge ran" is equality of the ``forge-protocol2-bridge``
    module trees at the recorded bridge/evidence commit and at the executing
    checkout. A checkout whose bridge differs executes a different provider
    surface, and a missing object means the claim cannot be verified at all.
    Either way: no Forge credit.
    """
    try:
        recorded_commit_tree = git_sha(
            "rev-parse", "--verify", "--quiet", f"{expected_bridge_commit}^{{tree}}", cwd=workspace
        )
    except RunnerGitError as exc:
        raise ForgeWorkspaceError(
            "BRIDGE_IDENTITY_UNVERIFIABLE: the bound bridge/evidence commit "
            f"{expected_bridge_commit[:12]} is not present in {workspace}: {exc}"
        ) from exc
    if recorded_commit_tree != expected_bridge_tree:
        raise ForgeWorkspaceError(
            "BRIDGE_IDENTITY_DIVERGENCE: the bound bridge/evidence commit "
            f"{expected_bridge_commit[:12]} names tree {recorded_commit_tree[:12]}, not the "
            f"recorded {expected_bridge_tree[:12]}"
        )
    try:
        expected_module_tree = git_sha(
            "rev-parse",
            "--verify",
            "--quiet",
            f"{expected_bridge_commit}:forge-protocol2-bridge",
            cwd=workspace,
        )
        actual_module_tree = git_sha(
            "rev-parse",
            "--verify",
            "--quiet",
            f"{actual_commit}:forge-protocol2-bridge",
            cwd=workspace,
        )
    except RunnerGitError as exc:
        raise ForgeWorkspaceError(f"BRIDGE_IDENTITY_UNVERIFIABLE: {exc}") from exc
    if expected_module_tree != actual_module_tree:
        raise ForgeWorkspaceError(
            "BRIDGE_IDENTITY_DIVERGENCE: the executing checkout's forge-protocol2-bridge tree "
            f"{actual_module_tree[:12]} is not the bound bridge/evidence tree "
            f"{expected_module_tree[:12]} (bridge commit {expected_bridge_commit[:12]}, "
            f"executing {actual_commit[:12]}). No Forge credit is produced."
        )
    return {
        "bridge_module": "forge-protocol2-bridge",
        "expected_bridge_commit": expected_bridge_commit,
        "expected_bridge_tree": expected_bridge_tree,
        "recorded_commit_tree": recorded_commit_tree,
        "expected_bridge_module_tree": expected_module_tree,
        "actual_bridge_module_tree": actual_module_tree,
        "actual_commit": actual_commit,
        "identical": True,
        "justification": (
            "EXACT_BRIDGE_COMMIT"
            if expected_bridge_commit == actual_commit
            else "BRIDGE_MODULE_TREE_IDENTICAL"
        ),
        "detail": (
            "the executing checkout's forge-protocol2-bridge module tree is identical to the "
            "bound bridge/evidence commit's, so the bridge that executes is the bridge the "
            "evidence is about; the Rules Core is bound separately by tree equivalence"
        ),
    }


def resolve_forge_workspace(workspace: Path | str | None = None) -> dict[str, Any]:
    """Resolve and fully bind the Forge checkout a credited run executes in.

    The identities are always the current authority in config/rules_engines.json
    (R-1 Rules-Core candidate, exact built bridge/materialization source and its
    tree); a caller cannot substitute others. See :func:`bind_forge_workspace`
    for the checkout validation itself.
    """
    authority = canonical_forge_authority()
    return bind_forge_workspace(
        workspace,
        expected_rules_core_commit=authority["rules_core_commit"],
        expected_bridge_commit=authority["bridge_commit"],
        expected_bridge_tree=authority["bridge_tree"],
    )


def bind_forge_workspace(
    workspace: Path | str | None,
    *,
    expected_rules_core_commit: str,
    expected_bridge_commit: str,
    expected_bridge_tree: str,
) -> dict[str, Any]:
    """Validate a Forge checkout against explicitly named identities.

    There is deliberately no default workspace. A machine-local path is not a
    source identity, and "the checkout that happens to exist on this machine" is
    not the checkout the evidence is about. Without an explicit workspace
    argument the module-level explicit input (``FORGE_WORKSPACE``) is required
    through :func:`require_forge_workspace`; the checkout must then prove, from
    its own Git state, that it is a clean work-tree root, that its Rules Core is
    equivalent to the named candidate, and that its bridge module is the named
    bridge/evidence identity. Anything unprovable fails closed.
    """
    for label, value in (
        ("Rules-Core commit", expected_rules_core_commit),
        ("bridge commit", expected_bridge_commit),
        ("bridge tree", expected_bridge_tree),
    ):
        if not value:
            raise ForgeWorkspaceError(f"no expected Forge {label} was named")
    if workspace is None:
        root = require_forge_workspace().resolve()
    else:
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            raise ForgeWorkspaceError(f"FORGE_WORKSPACE {root} is not a directory")
        try:
            toplevel = git_toplevel(root)
        except RunnerGitError as exc:
            raise ForgeWorkspaceError(
                f"FORGE_WORKSPACE {root} is not a Git work-tree root: {exc}"
            ) from exc
        if toplevel != root:
            raise ForgeWorkspaceError(
                f"FORGE_WORKSPACE {root} is not the top level of its Git checkout "
                f"({toplevel}); the engine identity would name another tree"
            )
    dirty_paths = tuple(receipt_mod._git_porcelain(root))
    if dirty_paths:
        raise ForgeWorkspaceError(
            f"FORGE_WORKSPACE {root} has uncommitted changes "
            f"({len(dirty_paths)} paths, e.g. {list(dirty_paths[:5])}); the committed checkout "
            "identity would not describe the bytes that execute. A credited Forge run requires a "
            "clean checkout."
        )
    actual_commit = git_sha("rev-parse", "HEAD", cwd=root)
    actual_tree = git_sha("rev-parse", "HEAD^{tree}", cwd=root)
    try:
        rules_core_proof = receipt_mod.verify_engine_identity(
            root,
            recorded_commit=expected_rules_core_commit,
            actual_commit=actual_commit,
            recorded_label="Forge workspace Rules Core",
        )
    except receipt_mod.ReceiptError as exc:
        raise ForgeWorkspaceError(f"RULES_CORE_IDENTITY_DIVERGENCE: {exc}") from exc
    bridge_proof = _bridge_identity_proof(
        root,
        expected_bridge_commit=expected_bridge_commit,
        expected_bridge_tree=expected_bridge_tree,
        actual_commit=actual_commit,
    )
    return {
        "workspace": str(root),
        "actual_commit": actual_commit,
        "actual_tree": actual_tree,
        "dirty": False,
        "expected_rules_core_commit": expected_rules_core_commit,
        "rules_core_identity_proof": rules_core_proof,
        "bridge_identity_proof": bridge_proof,
    }


def resolve_suite_root(candidate: str) -> dict[str, Any]:
    """The execution checkout for one native suite, with its identity proof.

    Suite roots are resolved and validated at execution time, never at import
    time: an import-time resolution recorded an empty tree for a path that
    existed but was not a repository, which is an unmeasured identity.
    """
    if candidate == "xmage":
        root = REPO_ROOT / "engine-bridge"
        if not root.is_dir():
            raise RunnerGitError(f"XMage bridge module is absent: {root}")
        try:
            toplevel = git_toplevel(root)
        except RunnerGitError as exc:
            raise RunnerGitError(
                f"{root} is not inside a Git work tree, so its executing identity cannot be "
                f"established: {exc}"
            ) from exc
        if toplevel != REPO_ROOT:
            raise RunnerGitError(
                f"{root} belongs to {toplevel}, not the Lab work tree {REPO_ROOT}; the XMage "
                "bridge suite must execute in this checkout"
            )
        return {
            "root": root,
            "expected_engine_commit": canonical_xmage_engine_pin(),
            "checkout_identity": {
                "kind": "LAB_MODULE",
                "suite_root": str(root),
                "containing_repository": str(toplevel),
                "actual_commit": git_sha("rev-parse", "HEAD", cwd=root),
                "actual_tree": git_sha("rev-parse", "HEAD^{tree}", cwd=root),
            },
        }
    if candidate != "forge":
        raise RunnerGitError(f"unknown native suite candidate: {candidate!r}")
    forge = resolve_forge_workspace()
    return {
        "root": Path(forge["workspace"]),
        "expected_engine_commit": forge["expected_rules_core_commit"],
        "checkout_identity": {
            "kind": "EXPLICIT_WORKSPACE",
            "actual_commit": forge["actual_commit"],
            "actual_tree": forge["actual_tree"],
            "rules_core_identity_proof": forge["rules_core_identity_proof"],
            "bridge_identity_proof": forge["bridge_identity_proof"],
        },
    }


# The Forge checkout the native suites execute in. It must be named explicitly
# (FORGE_WORKSPACE) so the bound bridge/evidence head can be a detached worktree
# at the exact Forge PR head without moving any other lane's checkout. There is
# no default: a machine-specific fallback silently bound whatever happened to sit
# at that path, so a Forge run without an explicit workspace fails closed
# (require_forge_workspace). Which Forge head is the candidate is PB-09's
# question, not this runner's.
#
# Live R-1/R-3 identities are resolved from config/rules_engines.json on every
# execution: #11/#12 is the admitted Rules-Core candidate and the bridge-only
# #13 descendant is the materialization source. The historical WSR22 source-lock
# constants remain untouched and are never used as live execution authority.
FORGE_WORKSPACE_ENV = "FORGE_WORKSPACE"
FORGE_WORKSPACE: Path | None = (
    Path(os.environ[FORGE_WORKSPACE_ENV]) if os.environ.get(FORGE_WORKSPACE_ENV) else None
)


def require_forge_workspace() -> Path:
    """The explicit Forge checkout, or SystemExit: no workspace means no Forge run."""
    if FORGE_WORKSPACE is None:
        raise ForgeWorkspaceError(
            "FORGE_WORKSPACE is not set; a Forge run needs an explicit, source-locked "
            "Forge checkout (no default path is assumed)"
        )
    if not FORGE_WORKSPACE.is_dir():
        raise ForgeWorkspaceError(f"FORGE_WORKSPACE {FORGE_WORKSPACE} is not a directory")
    try:
        toplevel = git_toplevel(FORGE_WORKSPACE)
    except RunnerGitError as exc:
        raise ForgeWorkspaceError(
            f"FORGE_WORKSPACE {FORGE_WORKSPACE} is not the top level of its Git checkout: {exc}"
        ) from exc
    if toplevel != FORGE_WORKSPACE.resolve():
        raise ForgeWorkspaceError(
            f"FORGE_WORKSPACE {FORGE_WORKSPACE} is not the top level of its Git "
            f"checkout ({toplevel}); the engine identity would name another tree"
        )
    return FORGE_WORKSPACE


# Native harness suites that bind FULL107 fixture ids. Each entry is executed
# fresh in this workstream; historical PASS is never transferred.
def _native_identity(candidate: str) -> dict[str, str]:
    """Exact engine identity for a native suite, resolved live from the checkout.

    A receipt must be able to name the candidate it actually ran, so the commit
    and tree are read from the suite's own root rather than asserted.
    """
    if candidate == "xmage":
        # The live canonical pin (config/rules_engines.json), not the frozen
        # WSR22 source_lock identity: a receipt must name the engine candidate
        # the canonical boundary currently pins, and the frozen WSR22 constant
        # remains the historical epoch of the sealed prior evidence only.
        return {
            "repository": "https://github.com/moeendres-png/mage",
            "expected_engine_commit": canonical_xmage_engine_pin(),
            "build_identity": json.dumps(
                {"lab_adapter": "engine-bridge", "lane": "maven-surefire"}
            ),
        }
    return {
        "repository": "https://github.com/moeendres-png/forge",
        "expected_engine_commit": canonical_forge_rules_core_pin(),
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
                # The declared engine commit is a constant; this runtime
                # fingerprint proves the loaded mage artifact actually carries
                # the candidate's APNAP primitives. Binding it here makes the
                # executing engine identity part of the observed suite evidence
                # instead of an assertion.
                "XmageCandidateEngineFingerprintTest",
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
                "XmagePb03CapabilityManifestTest",
                "XmagePb03DimensionAdmissionTest",
                "XmagePb03Tier1RowsTest",
                "XmagePb03Tier2StackTest",
                "XmagePb03Tier2CmdZoneTest",
                "XmagePb03Tier2ControlTurnTest",
                "XmageFullGameElimExecutionTest",
                "XmagePb03RuntimeGapClosureTest",
            ],
        },
    },
    "forge": {
        # Explicit input only: None when FORGE_WORKSPACE is not set. The binding
        # records the configured root for the tree marker; the run itself proves
        # identity through resolve_suite_root/resolve_forge_workspace.
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


def _bound_engine_tree(root: Path | None) -> str:
    """The suite root's tree for the binding table, or UNCONFIGURED.

    Importing the runner must not require every candidate's checkout; a run that
    uses one proves it strictly first (require_forge_workspace, git()).
    """
    if root is None:
        return "UNCONFIGURED"
    try:
        return receipt_mod.git_fact(root, "rev-parse", "HEAD^{tree}", sha=True)
    except receipt_mod.ReceiptError:
        return "UNCONFIGURED"


for _candidate in NATIVE_SUITE_BINDING:
    NATIVE_SUITE_BINDING[_candidate].update(_native_identity(_candidate))
    NATIVE_SUITE_BINDING[_candidate]["engine_tree"] = _bound_engine_tree(
        NATIVE_SUITE_BINDING[_candidate]["root"]
    )


def runtime_identity(candidate: str) -> dict[str, Any]:
    """Exact runtime identity for every row produced in this workstream.

    Every Git fact here is read through the fail-closed helpers: an identity
    that cannot be established raises before any evidence names it.
    """
    git_toplevel(REPO_ROOT)
    base = {
        "runner_commit": git_sha("rev-parse", "HEAD"),
        "runner_tree": git_sha("rev-parse", "HEAD^{tree}"),
        "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
        # Which epoch the bytes in this run belong to, and the explicit statement
        # that the historical WSR22 tree is not a write target. The path itself is
        # source-bound; this block makes the binding machine-readable inside every
        # artifact produced under it.
        "evidence_epoch": {
            "epoch_id": OUT_DIR.name,
            "epoch_root": EVIDENCE_EPOCH_RELATIVE,
            "predecessor_epoch": f"qualification/{epoch_mod.HISTORICAL_EPOCH_ID}",
            "predecessor_is_read_only": True,
            "writes_historical_epoch": False,
        },
    }
    if candidate == "xmage":
        base.update(
            {
                "engine_candidate_commit": canonical_xmage_engine_pin(),
                "lab_runtime_authority": XMAGE_LAB_RUNTIME_AUTHORITY,
                "adapter": "engine-bridge/src/main/java/org/commanderlab/xmage",
                "adapter_commit": git_sha("rev-parse", "HEAD", cwd=REPO_ROOT),
                "lane": "generic protocol-2 compatibility lane",
            }
        )
    else:
        forge = resolve_forge_workspace()
        authority = canonical_forge_authority()
        base.update(
            {
                "engine_candidate_commit": authority["rules_core_commit"],
                "engine_candidate_tree": authority["rules_core_tree"],
                "bridge_source_commit": authority["bridge_commit"],
                "bridge_source_tree": authority["bridge_tree"],
                "adapter": "forge-protocol2-bridge (read-only reference checkout)",
                "adapter_commit": forge["actual_commit"],
                "adapter_tree": forge["actual_tree"],
                "forge_workspace": forge["workspace"],
                "rules_core_identity": forge["rules_core_identity_proof"],
                "bridge_identity": forge["bridge_identity_proof"],
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
    if candidate == "forge":
        require_forge_workspace()
    spec = NATIVE_SUITE_BINDING[candidate]
    # Resolve the execution checkout and prove its identity before anything runs.
    # For Forge this is the explicit FORGE_WORKSPACE, validated as a work-tree
    # root, Rules-Core-equivalent to the recorded candidate and running the bound
    # bridge/evidence module tree. For XMage it is the Lab's own engine-bridge
    # module, which must belong to THIS Lab checkout. A suite that cannot prove
    # where it would execute does not execute.
    resolved = resolve_suite_root(candidate)
    suite_root = resolved["root"]
    checkout_identity = resolved["checkout_identity"]
    actual_head = str(checkout_identity["actual_commit"])
    # The binding declares build identity as a JSON document (a string), while the
    # receipt carries it as a JSON document as well; normalise here so the two
    # shapes can never be confused (the pb03-runtime CI job caught exactly that:
    # dict() over a JSON string raised before any receipt was persisted). A
    # missing or malformed declaration fails closed: a receipt that cannot name
    # the build that executed proves nothing.
    declared_build_identity = spec.get("build_identity")
    if declared_build_identity is None:
        raise SystemExit(
            f"native suite {candidate}:{group} binding declares no build_identity; a receipt "
            "cannot name the build that ran"
        )
    if isinstance(declared_build_identity, str):
        try:
            declared_build_identity = json.loads(declared_build_identity)
        except ValueError as exc:
            raise SystemExit(
                f"native suite {candidate}:{group} build_identity is not valid JSON: {exc}"
            ) from exc
    if not isinstance(declared_build_identity, dict):
        raise SystemExit(
            f"native suite {candidate}:{group} build_identity must be a JSON object, got "
            f"{type(declared_build_identity).__name__}"
        )
    build_identity: dict[str, Any] = dict(declared_build_identity)
    if checkout_identity["kind"] == "EXPLICIT_WORKSPACE":
        bridge_proof = checkout_identity["bridge_identity_proof"]
        engine_equivalence = {
            **checkout_identity["rules_core_identity_proof"],
            "bridge_identity_proof": bridge_proof,
            "workspace_identity": {
                "workspace": str(suite_root),
                "actual_commit": actual_head,
                "actual_tree": checkout_identity["actual_tree"],
                "selection": f"explicit {FORGE_WORKSPACE_ENV}; no ambient default",
            },
        }
        build_identity.update(
            {
                "bridge_source_commit": bridge_proof["expected_bridge_commit"],
                "rules_core_candidate_commit": resolved["expected_engine_commit"],
                "bridge_module_tree": bridge_proof["actual_bridge_module_tree"],
                "workspace_head": actual_head,
            }
        )
        print(
            f"engine identity {candidate}:{group}: "
            f"{engine_equivalence['justification']} + "
            f"{bridge_proof['justification']} "
            f"(recorded {resolved['expected_engine_commit'][:12]}, "
            f"executing {actual_head[:12]}, workspace {suite_root})"
        )
    else:
        # The XMage bridge is a module of the Lab repository, so `HEAD` there is
        # the Lab's own commit, not the XMage engine's, and comparing it against
        # the XMage engine commit compares two unrelated things. XMage's engine
        # identity is the provider's own reported commit, which AF00 verifies
        # fail-closed at handshake; the module checkout identity is recorded
        # instead of pretending a separate engine checkout exists.
        engine_equivalence = {
            "engine_equivalent": None,
            "justification": "ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT",
            "recorded_commit": resolved["expected_engine_commit"],
            "actual_commit": actual_head,
            "suite_root": str(suite_root),
            "containing_repository": str(checkout_identity["containing_repository"]),
            "detail": "the executing suite root is a module of the containing repository, "
            "so its HEAD identifies that repository, not the engine. The engine identity "
            "is the provider's own reported commit, verified fail-closed at handshake by "
            "AF00. No checkout identity is asserted for this candidate.",
        }
        build_identity.update(
            {
                "lab_adapter_head": actual_head,
                "lab_adapter_tree": checkout_identity["actual_tree"],
            }
        )
        print(
            f"engine identity {candidate}:{group}: not a separate checkout; engine identity "
            f"comes from the provider handshake (expected {resolved['expected_engine_commit'][:12]})"
        )
    tests = ",".join(spec["classes"][group])
    argv = [item.replace("{tests}", tests) for item in spec["argv"]]
    started = receipt_mod._now()
    started_epoch = time.time()
    completed = subprocess.run(
        argv, cwd=str(suite_root), capture_output=True, text=True, check=False, timeout=7200
    )
    text = completed.stdout + completed.stderr
    if completed.returncode != 0:
        # A failing suite must be attributable from the CI log alone. The
        # receipt records only counts and the command, so the output tail is
        # printed here (never stored) for the operator.
        tail = [line.rstrip() for line in text.splitlines() if line.strip()][-25:]
        print(f"native suite {candidate}:{group}: exit {completed.returncode}; output tail:")
        for line in tail:
            print(f"    {line}")
    try:
        summary = receipt_mod.parse_maven_summary(text)
    except receipt_mod.ReceiptError as exc:
        # A suite with no parseable summary cannot be credited. The failure is
        # still recorded so the run stays auditable.
        print(f"native suite {candidate}:{group}: {exc}")
        summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    receipt_mod.verify_runner_unchanged(REPO_ROOT, runner)
    # The execution identity of every requested class, from the surefire XML this
    # run wrote: an aggregate count cannot show that a requested class executed.
    # The report directories are read from the SAME identity-validated checkout
    # the suite just executed in (resolve_suite_root), not from an unvalidated
    # binding entry.
    report_dirs = [
        suite_root / "target" / "surefire-reports",
        *suite_root.glob("*/target/surefire-reports"),
    ]
    executed_classes, unexecuted_classes = receipt_mod.observed_class_executions(
        report_dirs, tuple(spec["classes"][group]), not_before=started_epoch - 1.0
    )
    if unexecuted_classes:
        print(
            f"native suite {candidate}:{group}: requested classes not executed: {unexecuted_classes}"
        )
    receipt = receipt_mod.NativeSuiteReceipt(
        candidate=candidate,
        group=group,
        command=" ".join(argv),
        candidate_repository=spec.get("repository", "UNCONFIGURED"),
        candidate_commit=resolved["expected_engine_commit"],
        candidate_tree=str(checkout_identity["actual_tree"]),
        executed_commit=actual_head,
        engine_identity_proof=engine_equivalence,
        build_identity=json.dumps(build_identity, sort_keys=True),
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
        executed_classes=executed_classes,
        unexecuted_classes=unexecuted_classes,
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


def run_all_native_suites(
    runner: receipt_mod.RunnerIdentity,
    candidates: tuple[str, ...] = ("xmage", "forge"),
) -> list[dict[str, Any]]:
    """Execute every bound native suite for the selected candidates.

    The native-suite stage is scoped to the candidates this run was asked for.
    A candidate that was not selected must not have its native receipts
    regenerated: that would re-execute a surface whose runtime claim is not
    under requalification.
    """
    receipts: list[dict[str, Any]] = []
    for candidate in candidates:
        for group in NATIVE_SUITE_BINDING[candidate]["classes"]:
            receipts.append(run_native_suite(candidate, group, runner=runner))
    return receipts


def bootstrap_evidence_epoch() -> dict[str, Any]:
    """Bind this run's evidence-epoch identity before any artifact is written.

    The identity is the producing source; an epoch that another source produced
    is never overwritten, and the historical WSR22 epoch cannot be selected at
    all (see evidence_epoch.epoch_root).
    """
    return epoch_mod.ensure_epoch_identity(OUT_DIR, repo_root=REPO_ROOT)


# The per-candidate artifacts the assembler requires for both columns of the
# comparison. A run that selects one candidate carries the other column forward
# from the historical epoch; the copied documents are explicitly marked, so the
# current epoch never claims a fresh execution that did not happen.
CARRIED_FORWARD_EVIDENCE_CLASS = "CARRIED_FORWARD_NOT_REEXECUTED"
_CARRIED_FORWARD_ARTIFACTS = (
    "FULL107_{candidate}_RESULTS.json",
    "AF01_{candidate}.json",
    "AF03_{candidate}.json",
    "PLAYER_CARDINALITY_{candidate}.json",
    "RNG_REPLAY_{candidate}.json",
)


def carry_forward_unselected_candidates(
    candidates: list[str] | tuple[str, ...],
    *,
    source_epoch: Path | None = None,
    target_epoch: Path | None = None,
    now: str | None = None,
) -> list[str]:
    """Copy a non-selected candidate's historical column into this epoch.

    The assembly compares two candidates, but a run may legitimately select one
    (the PB-03 CI run executes XMage only). The non-selected column is the
    historical record, not a fresh execution, so every copied document is marked
    ``CARRIED_FORWARD_NOT_REEXECUTED`` with its source epoch and the identity of
    the run that actually produced it. The historical epoch itself is only read.
    """
    source_root = source_epoch or epoch_mod.historical_epoch_root(REPO_ROOT)
    target_root = target_epoch or OUT_DIR
    carried: list[str] = []
    for candidate in ("xmage", "forge"):
        if candidate in candidates:
            continue
        copied = 0
        for template in _CARRIED_FORWARD_ARTIFACTS:
            name = template.format(candidate=candidate.upper())
            source = source_root / name
            target = target_root / name
            if not source.is_file() or target.exists():
                continue
            try:
                document = json.loads(source.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise SystemExit(
                    f"carried-forward artifact {source} is unreadable ({exc}); the non-selected "
                    "column cannot be assembled"
                ) from exc
            if not isinstance(document, dict):
                raise SystemExit(f"carried-forward artifact {source} is not an object")
            # Mark every freshness claim, including nested ones: a direct
            # consumer of the copied file must not read FRESH from a row or
            # boundary field after the top-level marker was rewritten.
            document["evidence_class"] = CARRIED_FORWARD_EVIDENCE_CLASS
            if "boundary" in document:
                document["boundary"] = CARRIED_FORWARD_EVIDENCE_CLASS
            rows = document.get("rows")
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and "evidence_class" in row:
                        row["evidence_class"] = CARRIED_FORWARD_EVIDENCE_CLASS
            document["carried_forward"] = {
                "source_epoch": str(source_root),
                "source_epoch_id": source_root.name,
                "reason": (
                    f"candidate {candidate} was not selected in this run, so this column is the "
                    "historical record that the current assembly compares against; it is not a "
                    "fresh execution"
                ),
                "copied_utc": now or receipt_mod._now(),
            }
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(document, indent=1, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
            copied += 1
        if copied:
            print(f"carried forward {copied} historical {candidate} artifact(s) from {source_root}")
            carried.append(candidate)
    return carried


def write(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(f"wrote {name}")


# R-4 direct FULL107 credit: only these runner routes validate an exact
# denominator obligation directly. Native-suite execution remains supporting
# evidence and is deliberately excluded from this list.
DIRECT_RECEIPT_MODES = frozenset(
    {
        "PROTOCOL2_LIFECYCLE",
        "PROTOCOL2_START2_V1_0_6",
    }
)
DIRECT_RECEIPT_IDENTITY_PREFIX = "current-boundary-direct:"


def _direct_positive_receipt(
    row: RowResult,
    record: dict[str, Any],
    *,
    candidate_commit: str,
    runner_digest: str,
) -> dict[str, Any]:
    """Bind one directly observed PASS to its exact FULL107 obligation.

    The receipt stores digests of the already-persisted observation rather than
    duplicating state/decision payloads. That preserves auditability without
    widening the hidden-information surface.
    """
    if row.outcome != "PASS" or row.execution_mode not in DIRECT_RECEIPT_MODES:
        raise ValueError(f"{row.fixture_id} is not an R-4 direct PASS")
    row_document = row.to_document(record)
    observation_digest = receipt_mod.document_digest(row_document)
    obligation = {
        "fixture_family": record.get("fixture_family"),
        "required_events": list((record.get("expected_events") or {}).get("required_events") or ()),
        "forbidden_events": list(
            (record.get("expected_events") or {}).get("forbidden_events") or ()
        ),
        "terminal_postconditions": list(record.get("terminal_postconditions") or ()),
        "requested_state_digest": record.get("requested_state_digest"),
        "obligation_digest": record.get("obligation_digest"),
    }
    document: dict[str, Any] = {
        "schema_version": receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": row.candidate,
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "fixture_id": row.fixture_id,
        "test_identity": (f"{DIRECT_RECEIPT_IDENTITY_PREFIX}{row.execution_mode}#{row.fixture_id}"),
        "execution_mode": row.execution_mode,
        "obligation_exercised": obligation,
        "observed_assertion": {
            "row_document_sha256": observation_digest,
            "semantic_events_sha256": receipt_mod.document_digest(
                {"semantic_events": row.evidence.get("semantic_events", [])}
            ),
            "terminal_facts_sha256": receipt_mod.document_digest(
                {"terminal_facts": row.evidence.get("terminal_facts", {})}
            ),
            "principal_observation_scope": row.evidence.get("principal_observation_scope"),
        },
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "outcome": "PASS",
        "runtime_receipt_digest": observation_digest,
    }
    document["receipt_digest"] = receipt_mod.document_digest(document)
    return document


def persist_direct_positive_receipts(
    rows_by_candidate: dict[str, list[RowResult]],
    records: dict[str, dict[str, Any]],
    *,
    runner_digest: str,
) -> dict[str, Any]:
    """Persist exact receipts for runner-native direct row families.

    Re-runs delete only this producer's own candidate-prefixed receipts. Midgame
    producer receipts are a separate family and remain untouched.
    """
    out_dir = RECEIPT_DIR / receipt_mod.POSITIVE_RECEIPT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}
    for candidate, rows in rows_by_candidate.items():
        for stale in out_dir.glob(f"direct-{candidate}--*.json"):
            stale.unlink()
        candidate_commit = ""
        for row in rows:
            candidate_commit = str(
                row.evidence.get("runtime_identity", {}).get("engine_candidate_commit", "")
            )
            if candidate_commit:
                break
        written: list[str] = []
        for row in rows:
            if row.outcome != "PASS" or row.execution_mode not in DIRECT_RECEIPT_MODES:
                continue
            record = records[row.fixture_id]
            receipt = _direct_positive_receipt(
                row,
                record,
                candidate_commit=candidate_commit,
                runner_digest=runner_digest,
            )
            receipt_mod.persist(
                out_dir / f"direct-{candidate}--{row.fixture_id}.json",
                receipt,
            )
            written.append(row.fixture_id)
        summary[candidate] = {
            "candidate_commit": candidate_commit,
            "runner_digest": runner_digest,
            "eligible_execution_modes": sorted(DIRECT_RECEIPT_MODES),
            "receipts_written": sorted(written),
            "receipt_count": len(written),
        }
    return {
        "schema_version": "commander-lab.direct-full107-receipts/1.0.0",
        "credit_rule": (
            "R-4: only exact per-fixture direct producer receipts earn FULL107 credit; "
            "native-suite and adjacent mechanism evidence remain supporting only"
        ),
        "candidates": summary,
    }


def _live_xmage_provider_identity() -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the itemised PB-03 manifest and the provider's own identity.

    The provider-reported identity includes the loaded engine artifact's
    SHA-256; the declared commit constant alone cannot prove which bytes ran, so
    the PB-03 evidence refuses to be produced without it.
    """
    plan = build_launch_plan("xmage", lane="full-game")
    with launch(plan) as proc:
        provider_payload: dict[str, Any] | None = None
        for message_type in ("start_engine", "get_provider_version"):
            response = proc.request(message_type, {})
            if response.get("success") is not True:
                raise SystemExit(
                    f"PB-03 live manifest handshake failed at {message_type}: "
                    f"{response.get('errors')!r}"
                )
            if message_type == "get_provider_version":
                payload = response.get("payload")
                if not isinstance(payload, dict):
                    raise SystemExit("PB-03 provider version payload is not an object")
                provider_payload = payload
        response = proc.request("get_capabilities", {})
        if response.get("success") is not True:
            raise SystemExit(
                "PB-03 live manifest unavailable: get_capabilities failed "
                f"{response.get('errors')!r}"
            )
        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise SystemExit("PB-03 capability payload is not an object")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, dict):
            raise SystemExit("PB-03 capability payload omitted capabilities")
        if capabilities.get("starting_state_injection_supported") is not False:
            raise SystemExit("PB-03 must not promote starting_state_injection_supported")
        lane = payload.get("full_game_lane")
        if not isinstance(lane, dict):
            raise SystemExit("PB-03 capability payload omitted full_game_lane")
        manifest = lane.get("state_restoration_dimensions")
        if not isinstance(manifest, dict):
            raise SystemExit("PB-03 live restoration dimension manifest missing")
        assert provider_payload is not None
        return manifest, provider_payload


def _validated_provider_identity(provider: dict[str, Any]) -> dict[str, Any]:
    """Validate the live provider identity fail-closed and project it for evidence."""
    reported_commit = provider.get("engine_commit")
    expected_commit = canonical_xmage_engine_pin()
    if reported_commit != expected_commit:
        raise SystemExit(
            f"PB-03 provider reports engine commit {reported_commit!r}, "
            f"canonical pin is {expected_commit!r}"
        )
    artifact_kind = provider.get("engine_artifact_kind")
    artifact_digest = provider.get("engine_artifact_sha256")
    if (
        artifact_kind != "file"
        or not isinstance(artifact_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", artifact_digest)
    ):
        raise SystemExit(
            "PB-03 provider artifact identity unavailable: "
            f"kind={artifact_kind!r} sha256={artifact_digest!r}"
        )
    return {
        "engine": provider.get("engine"),
        "engine_version": provider.get("engine_version"),
        "engine_commit": reported_commit,
        "protocol_version": provider.get("protocol_version"),
        "xmage_code_source": provider.get("xmage_code_source"),
        "engine_artifact_kind": artifact_kind,
        "engine_artifact_path": provider.get("engine_artifact_path"),
        "engine_artifact_sha256": artifact_digest,
        "engine_artifact_size": provider.get("engine_artifact_size"),
    }


def build_xmage_pb03_admission(materialization) -> dict[str, Any]:
    """Build the 30-row frozen-state admission ledger from live capabilities."""
    manifest, provider = _live_xmage_provider_identity()
    provider_identity = _validated_provider_identity(provider)
    document = pb03_admission_mod.admit_manifest(materialization.denominator_records(), manifest)
    document.update(
        {
            "provider_identity": provider_identity,
            "manifest": manifest,
            "manifest_source": (
                "live full-game get_capabilities -> full_game_lane.state_restoration_dimensions"
            ),
            "global_capability_flag": (
                "starting_state_injection_supported remains false and is never "
                "used as the row admission verdict"
            ),
        }
    )
    if document["counts"] != {"admitted": 12, "blocked": 18}:
        raise SystemExit(
            "PB-03 admission projection drifted from the adjudicated current "
            f"30-row boundary: {document['counts']}"
        )
    write("PB03_DIMENSION_ADMISSION.json", document)
    write("PB03_ADMISSION_MATRIX.json", document)
    return document


def execute_candidate(candidate: str, materialization) -> dict[str, Any]:
    """Run AF01, cardinality, START-2 and the dimension probes for one candidate."""
    identity = runtime_identity(candidate)
    # The Forge candidate is launched from the same explicitly bound workspace the
    # native suites execute in; there is no other source for it.
    workspace = Path(resolve_forge_workspace()["workspace"]) if candidate == "forge" else None
    lane = "compat" if candidate == "xmage" else "protocol2-jsonl"
    plan = build_launch_plan(candidate, lane=lane, forge_workspace=workspace)

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
            seat_count=af01_live.player_count,
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
    if args.candidate in {"all", "forge"}:
        # Fail before anything is written: a Forge run has no default checkout.
        require_forge_workspace()
    # Bind the evidence epoch before the first artifact is written. The identity is
    # the producing source; an epoch that another source produced is never
    # overwritten, and the historical WSR22 epoch cannot be selected at all.
    epoch_identity = bootstrap_evidence_epoch()
    print(
        "evidence epoch:",
        epoch_identity["epoch_root"],
        "producing source",
        epoch_identity["producing_source"]["commit"][:12],
    )
    carried = carry_forward_unselected_candidates(
        ["xmage", "forge"] if args.candidate == "all" else [args.candidate]
    )
    if carried:
        print("non-selected candidate columns carried forward (historical):", carried)

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
    xmage_provider_identity: dict[str, Any] | None = None
    if "xmage" in candidates:
        admission_document = build_xmage_pb03_admission(materialization)
        xmage_provider_identity = admission_document["provider_identity"]
    summary: dict[str, Any] = {}
    direct_rows_by_candidate: dict[str, list[RowResult]] = {}
    denominator_by_id = {
        record["fixture_id"]: record for record in materialization.denominator_records()
    }
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
        direct_rows_by_candidate[candidate] = list(outcome["rows"])
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
    # R-4 receipt seam for candidate-neutral direct row families. This happens
    # only after the clean committed runner identity has been captured, so the
    # assembler can reject stale adapter/runner executions.
    write(
        "DIRECT_ROW_RECEIPTS.json",
        persist_direct_positive_receipts(
            direct_rows_by_candidate,
            denominator_by_id,
            runner_digest=runner.digest(),
        ),
    )

    # The PB-03 runtime ledger is derived from the surefire XML of the suites
    # that just ran. Clear the previous reports first so a class that failed to
    # compile or was not executed in this run cannot be credited from a stale
    # report left by an earlier run.
    if "xmage" in candidates:
        shutil.rmtree(
            REPO_ROOT / "engine-bridge" / "target" / "surefire-reports", ignore_errors=True
        )
    native_receipts = run_all_native_suites(runner, tuple(candidates))
    if "xmage" in candidates:
        pb03_runtime = pb03_runtime_mod.build_runtime_execution_matrix(
            REPO_ROOT / "engine-bridge" / "target" / "surefire-reports"
        )
        pb03_runtime["runner_commit"] = runner.commit
        pb03_runtime["runner_tree"] = runner.tree
        pb03_runtime["runner_digest"] = runner.digest()
        pb03_runtime["candidate_commit"] = canonical_xmage_engine_pin()
        if xmage_provider_identity is None:
            raise SystemExit(
                "PB-03 provider identity missing; refusing to seal a runtime ledger "
                "that cannot name the loaded engine artifact"
            )
        # The loaded engine artifact identity is the provider's own report from
        # the admission handshake of this same run. The declared commit constant
        # alone cannot prove which bytes executed.
        pb03_runtime["engine_artifact_kind"] = xmage_provider_identity["engine_artifact_kind"]
        pb03_runtime["engine_artifact_sha256"] = xmage_provider_identity["engine_artifact_sha256"]
        pb03_runtime["engine_artifact_path"] = xmage_provider_identity["engine_artifact_path"]
        pb03_runtime["engine_artifact_size"] = xmage_provider_identity["engine_artifact_size"]
        # Seal the identity block: the assembler rejects any ledger whose content
        # digest, runner digest, candidate commit or engine artifact digest does
        # not match the assembling head, so a stale ledger can never be credited.
        pb03_runtime["receipt_digest"] = receipt_mod.document_digest(pb03_runtime)
        write("PB03_RUNTIME_EXECUTION.json", pb03_runtime)
        # The PB-03 chain's last links: exact placement obligations executed on
        # the production midgame lane, each verified row persisted as a
        # runner-bound positive fixture receipt the assembler may credit.
        write(
            "MIDGAME_ROW_EXECUTIONS.json",
            midgame_rows_mod.execute_and_persist(
                workspace=REPO_ROOT / "engine-bridge",
                records={
                    record["fixture_id"]: record for record in materialization.denominator_records()
                },
                candidate_commit=canonical_xmage_engine_pin(),
                runner_digest=runner.digest(),
                out_dir=RECEIPT_DIR / receipt_mod.POSITIVE_RECEIPT_SUBDIR,
            ),
        )
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
