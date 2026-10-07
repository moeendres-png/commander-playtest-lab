"""Forge current-boundary scenario lane (issue #455).

Consumes the **Forge-authored native ScenarioBootstrap seam** without building a
second Rules engine and without inventing a generic state injector.

Boundary contract
-----------------
Forge remains the sole Rules authority. This module only:

* binds the exact pinned Forge Rules-Core and bridge/materialization identities;
* derives the ScenarioBootstrap capability matrix from the exact pinned bridge
  source (blob digest bound), failing closed on source drift;
* translates an effective FULL107 record into the ``neutral_initial_state``
  subset the current bootstrap actually supports;
* classifies every requested-state field that has no bootstrap representation as
  an exact unsupported dimension (never silently dropped);
* runs the engine, compares authoritative readback to the requested state field
  by field, and evaluates a bounded set of terminal obligations from
  engine-reported facts;
* records engine-authored decisions only (no first/random/default option).

It never computes legality, never fabricates an option, never injects outcomes,
and never repairs Forge. Unsupported rows fail closed with exact per-field
reasons.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from commander_lab.qualification.current_boundary import forge_causal_route as fcr
from commander_lab.qualification.current_boundary import receipts as receipt_mod
from commander_lab.qualification.current_boundary import scripted_selection as ss

from .bridge_launcher import (
    BridgeLaunchError,
    BridgeProcess,
    build_launch_plan,
    canonical_forge_authority,
    launch,
)
from .game_driver import (
    DecisionTapeEntry,
    DecisionUnsatisfied,
    GameDriveError,
    decision_identity_params,
    poll_decision,
    select_cost_order_action,
)
from .starting_player import (
    STARTER_DECLARATION_SCRIPT,
    scenario_setup_starting_seat,
)

LANE_SCHEMA_VERSION = "commander-lab.forge-scenario-lane/1.0.0"
BRIDGE_MODULE = "forge-protocol2-bridge"
SCENARIO_SOURCE_RELATIVE = f"{BRIDGE_MODULE}/src/main/java/forge/bridge/ScenarioBootstrap.java"
SESSION_SOURCE_RELATIVE = f"{BRIDGE_MODULE}/src/main/java/forge/bridge/BridgeSession.java"
PROJECTION_SOURCE_RELATIVE = f"{BRIDGE_MODULE}/src/main/java/forge/bridge/StateProjection.java"

SEATS = ("p1", "p2", "p3", "p4", "p5", "p6")

DEFAULT_MAINBOARD_BASIC = "Mountain"

# ---------------------------------------------------------------------------
# Result vocabulary. Deliberately not collapsed into PASS/FAIL: transport,
# construction, checkpoint equivalence, decision execution, semantic obligation
# and receipt eligibility stay separate.
# ---------------------------------------------------------------------------
RESULT_OBLIGATION_OBSERVED = "EXECUTED_OBLIGATION_OBSERVED"
RESULT_CHECKPOINT_MISMATCH = "EXECUTED_CHECKPOINT_MISMATCH"
RESULT_OBLIGATION_NOT_OBSERVABLE = "OBLIGATION_NOT_OBSERVABLE"
RESULT_ENGINE_REJECTED = "ENGINE_REJECTED_SCENARIO"
RESULT_UNSUPPORTED_DIMENSION = "UNSUPPORTED_DIMENSION"
RESULT_TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
RESULT_NOT_ATTEMPTED = "NOT_ATTEMPTED"

CHECKPOINT_EXACT = "EXACT"
CHECKPOINT_ALLOWED_VARIANCE = "ALLOWED_VARIANCE"
CHECKPOINT_MISMATCH = "MISMATCH"
CHECKPOINT_UNSUPPORTED_DIMENSION = "UNSUPPORTED_DIMENSION"
CHECKPOINT_TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
# A field whose readback cannot be attributed to one requested object (same
# name, same controller, differing values): never EXACT, never credited.
CHECKPOINT_UNKNOWN = "UNKNOWN"

DIMENSION_SUPPORTED = "SUPPORTED"
DIMENSION_UNSUPPORTED = "UNSUPPORTED"
DIMENSION_UNOBSERVABLE = "UNOBSERVABLE"
# Requested state that the bootstrap cannot place but the lane reaches causally
# through the engine's own frames (``forge_causal_route``). It earns nothing by
# itself: the route must run and its terminal obligation must be observed.
DIMENSION_CAUSED = "CAUSED"


class ScenarioLaneError(RuntimeError):
    """The lane cannot proceed without crossing its boundary."""


class ScenarioCapabilityDrift(ScenarioLaneError):
    """The pinned ScenarioBootstrap source no longer matches the derived matrix."""


# ---------------------------------------------------------------------------
# Source binding
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ForgeScenarioSource:
    """Exact pinned identities plus the ScenarioBootstrap source blob digest."""

    workspace: str
    actual_commit: str
    actual_tree: str
    rules_core_commit: str
    rules_core_tree: str
    bridge_commit: str
    bridge_tree: str
    scenario_source_path: str
    scenario_source_sha256: str
    session_source_sha256: str
    projection_source_sha256: str
    rules_core_identity: dict[str, Any]
    bridge_identity: dict[str, Any]

    def to_document(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "actual_commit": self.actual_commit,
            "actual_tree": self.actual_tree,
            "rules_core_commit": self.rules_core_commit,
            "rules_core_tree": self.rules_core_tree,
            "bridge_commit": self.bridge_commit,
            "bridge_tree": self.bridge_tree,
            "scenario_source_path": self.scenario_source_path,
            "scenario_source_sha256": self.scenario_source_sha256,
            "session_source_sha256": self.session_source_sha256,
            "projection_source_path": PROJECTION_SOURCE_RELATIVE,
            "projection_source_sha256": self.projection_source_sha256,
            "rules_core_identity": self.rules_core_identity,
            "bridge_identity": self.bridge_identity,
        }


def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise ScenarioLaneError(f"git {' '.join(args)} failed in {cwd}: {completed.stderr.strip()}")
    return completed.stdout


def _porcelain(root: Path) -> tuple[str, ...]:
    output = _git(["status", "--porcelain"], root)
    return tuple(line for line in output.splitlines() if line.strip())


def _blob_sha256(root: Path, commit: str, relative: str) -> str:
    text = _git(["show", f"{commit}:{relative}"], root)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_scenario_source(workspace: Path | str, commit: str | None = None) -> str:
    root = Path(workspace).expanduser().resolve()
    source = commit or canonical_forge_authority()["bridge_commit"]
    return _git(["show", f"{source}:{SCENARIO_SOURCE_RELATIVE}"], root)


def bind_forge_scenario_source(workspace: Path | str) -> ForgeScenarioSource:
    """Bind an explicitly named Forge checkout to the current R-1 identities.

    Mirrors the shared runner's fail-closed contract: explicit workspace only,
    clean checkout, Rules-Core equivalence against the admitted candidate, and
    separate bridge/materialization module-tree equality. The ScenarioBootstrap
    source is read from the *bridge commit*, not the working tree, so the
    capability matrix is bound to the instrumented source even if the checkout
    carries untracked build output.
    """
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise ScenarioLaneError(f"FORGE_WORKSPACE {root} is not a directory")
    toplevel = _git(["rev-parse", "--show-toplevel"], root).strip()
    if Path(toplevel) != root:
        raise ScenarioLaneError(
            f"FORGE_WORKSPACE {root} is not the top level of its Git checkout ({toplevel})"
        )
    dirty = _porcelain(root)
    if dirty:
        raise ScenarioLaneError(
            f"FORGE_WORKSPACE {root} has {len(dirty)} uncommitted paths; a credited "
            "scenario lane requires a clean checkout"
        )
    authority = canonical_forge_authority()
    actual_commit = _git(["rev-parse", "HEAD"], root).strip()
    actual_tree = _git(["rev-parse", "HEAD^{tree}"], root).strip()
    try:
        rules_core_identity = receipt_mod.verify_engine_identity(
            root,
            recorded_commit=authority["rules_core_commit"],
            actual_commit=actual_commit,
            recorded_label="Forge workspace Rules Core",
        )
    except receipt_mod.ReceiptError as exc:
        raise ScenarioLaneError(f"RULES_CORE_IDENTITY_DIVERGENCE: {exc}") from exc
    # The manifest's bridge tree is the *commit* tree of the bound bridge source.
    # The executable bridge identity is the module subtree, compared separately
    # (mirrors the shared runner's two-stage bridge identity proof).
    expected_bridge_tree = authority["bridge_tree"]
    recorded_commit_tree = _git(
        ["rev-parse", f"{authority['bridge_commit']}^{{tree}}"], root
    ).strip()
    if recorded_commit_tree != expected_bridge_tree:
        raise ScenarioLaneError(
            "BRIDGE_IDENTITY_DIVERGENCE: the bound bridge commit "
            f"{authority['bridge_commit'][:12]} names tree {recorded_commit_tree[:12]}, not "
            f"the recorded {expected_bridge_tree[:12]}"
        )
    expected_module_tree = _git(
        ["rev-parse", f"{authority['bridge_commit']}:{BRIDGE_MODULE}"], root
    ).strip()
    actual_module_tree = _git(["rev-parse", f"{actual_commit}:{BRIDGE_MODULE}"], root).strip()
    if actual_module_tree != expected_module_tree:
        raise ScenarioLaneError(
            "BRIDGE_IDENTITY_DIVERGENCE: the executing checkout's "
            f"{BRIDGE_MODULE} tree {actual_module_tree[:12]} is not the bound bridge module "
            f"tree {expected_module_tree[:12]}"
        )
    return ForgeScenarioSource(
        workspace=str(root),
        actual_commit=actual_commit,
        actual_tree=actual_tree,
        rules_core_commit=authority["rules_core_commit"],
        rules_core_tree=authority["rules_core_tree"],
        bridge_commit=authority["bridge_commit"],
        bridge_tree=authority["bridge_tree"],
        scenario_source_path=SCENARIO_SOURCE_RELATIVE,
        scenario_source_sha256=_blob_sha256(
            root, authority["bridge_commit"], SCENARIO_SOURCE_RELATIVE
        ),
        session_source_sha256=_blob_sha256(
            root, authority["bridge_commit"], SESSION_SOURCE_RELATIVE
        ),
        projection_source_sha256=_blob_sha256(
            root, authority["bridge_commit"], PROJECTION_SOURCE_RELATIVE
        ),
        rules_core_identity=rules_core_identity,
        bridge_identity={
            "bridge_module": BRIDGE_MODULE,
            "bridge_commit": authority["bridge_commit"],
            "bridge_commit_tree": recorded_commit_tree,
            "expected_module_tree": expected_module_tree,
            "actual_module_tree": actual_module_tree,
            "identical": True,
        },
    )


# ---------------------------------------------------------------------------
# Capability matrix derived from the exact source
# ---------------------------------------------------------------------------
# Each assertion is an exact code fragment whose presence/absence is what makes
# the documented capability true. If the pinned source changes, derivation
# raises ScenarioCapabilityDrift instead of silently claiming an old matrix.
_SUPPORTED_FIELD_ASSERTIONS: dict[str, tuple[str, ...]] = {
    "battlefield": (
        'neutral.has("battlefield")',
        'optString(entry, "card", "")',
        "battlefield entry missing controller",
        "takeCommander(owner, placement.cardName)",
        "takeFromLibrary(owner, placement.cardName)",
        "Card.fromPaperCard(paper, owner)",
    ),
    "battlefield.tapped": ('entry.has("tapped")', "tapped must be a boolean"),
    "battlefield.counters": (
        'entry.has("counters")',
        "counters must be an object",
        "counter amounts must be integers",
        "CounterEnumType.valueOf(counter.getKey())",
    ),
    "battlefield.attached_to": (
        'entry.has("attached_to")',
        "attach host not on battlefield: ",
        "aura.attachToEntity(host, null)",
    ),
    "hands": ('neutral.has("hands")', "scenario_placed_hand"),
    "life": ('neutral.has("life")', "scenario_set_life"),
    "commander_damage": ('"commander_damage_taken"', "scenario_commander_damage"),
    "continuous_effects_present_informational_only": ("continuous_effects_present",),
}

_REJECTION_ASSERTIONS: dict[str, str] = {
    "stack": "scenario must not inject stack",
    "decision_script": "scenario must not inject decisions",
}

# Readback dimensions the bridge projects from an engine-native fact rather than
# accepting a construction request. forge#33 G1 R1 (C3): the first-turn control
# flag is a per-battlefield-entry projection of Card.isFirstTurnControlled()
# (raw summoning sickness, CR 302.6; never hasSickness(), which folds in haste).
# The lane forwards a requested controlled_since_turn_began only for checkpoint
# verification and compares it against this readback; the bootstrap neither sets
# nor validates it, so a missing or non-boolean readback is a MISMATCH.
_READBACK_ASSERTIONS: dict[str, tuple[str, ...]] = {
    "battlefield_details.controlled_since_turn_began": (
        "firstTurnControlled = card.isFirstTurnControlled();",
        'entry.addProperty("controlled_since_turn_began", !firstTurnControlled);',
    ),
}

# Re-derived for forge#33 (G1 R1 port, Coordinator decision G1 on #561):
# permanents are placed by a GameEventTurnBegan(turn 1) subscriber registered on
# the game's own event bus (it runs before the engine's readiness loop). The
# session owns the one-shot latch and the recorded failure; the retained
# startGameHook keeps the givePriorityToPlayer frame of
# PhaseHandler.setupFirstTurn and fails closed unless that placement ran exactly
# once without error, then applies the post-untap plan.
_HOOK_ASSERTIONS: dict[str, tuple[str, ...]] = {
    "hook_apply": (
        "final ScenarioBootstrap.Plan capturedPlan = scenarioPlan;",
        "installScenarioBootstrap(capturedGame, capturedPlan);",
        "final Runnable scenarioHook = scenarioStartGameHook(capturedGame, capturedPlan);",
        "launchStarter(() -> capturedMatch.startGame(capturedGame, scenarioHook));",
    ),
    "hook_placement": (
        "game.subscribeToEvents(new ScenarioTurnBeganSubscriber());",
        "void handleScenarioTurnBegan(final GameEventTurnBegan event)",
        "ScenarioBootstrap.placeBattlefield(this, intended, plan);",
    ),
    "hook_plan_set_once_at_creation": (
        "public synchronized void setScenarioPlan(ScenarioBootstrap.Plan plan)",
    ),
    "hook_bootstrap_error_recorded_on_session": (
        "private void recordScenarioBootstrapFailure(final String reason)",
        "if (scenarioBootstrapInvocations.incrementAndGet() > 1)",
        'recordScenarioBootstrapFailure("scenario bootstrap failed: " + t);',
        "if (status == Status.RUNNING) {",
        "void requireScenarioBootstrapCompleted()",
        "scenario bootstrap did not run exactly once before the start-game hook",
    ),
    "hook_post_untap_complete_placement": (
        "ScenarioBootstrap.applyPostUntap(self, game, plan, scenarioPlacedCards);",
        "scenario bootstrap placed ",
    ),
}

# The ScenarioBootstrap side of the same contract (C1/C2): placement happens
# untapped at TurnBegan (the untap step runs after it), counters are added once
# there with fireEvents=false, tapped state is applied silently after the untap
# step, and a truncated placement fails closed instead of skipping plan entries.
_SCENARIO_HOOK_ASSERTIONS: dict[str, tuple[str, ...]] = {
    "place_at_turn_began_untapped": (
        "public static List<Card> placeBattlefield(BridgeSession session, Game game, Plan plan)",
        "static void addRequestedCounters(BridgeSession session, Plan plan, List<Card> placed)",
        "card.addCounterInternal(counterType, counter.getValue(), null, false, null,",
    ),
    "complete_placement_fails_closed": (
        "private static void requireCompletePlacement(Plan plan, List<Card> placed)",
        "scenario placement incomplete: placed ",
    ),
    "tapped_after_untap_silently": (
        "static void applyRequestedTapped(BridgeSession session, Plan plan, List<Card> placed)",
        "requested tapped permanent left the battlefield before the post-untap ",
        "card.setTapped(true);",
        "public static void applyPostUntap(BridgeSession session, Game game, Plan plan,",
    ),
}

# Fields the bootstrap has no representation for. Derived from the effective
# fixture record schema; every one fails closed rather than being dropped.
_UNSUPPORTED_RECORD_DIMENSIONS: dict[str, str] = {
    "stack_state": "non-empty stack_state requires stack injection, which the bootstrap rejects",
    "combat_state": "combat declaration state has no bootstrap field",
    "action_cost_state": "mid-cast cost/payment state has no bootstrap field",
    "knowledge_state": "knowledge permissions have no bootstrap field",
    "rules_randomness.predetermined_semantic_draws": "predetermined draws have no bootstrap field",
}

# Declared decision families this lane can execute itself. Everything else is an
# execution-contract blocker owned by an engine-authored selector surface this
# lane does not reimplement (the shared mid-game selector workstream). A declared
# family is never silently ignored and no option is ever fabricated.
_LANE_EXECUTABLE_DECISION_SELECTORS: frozenset[str] = frozenset()

# The causal stack route (#520) answers a record's scripted steps through the
# shared fail-closed selector (``scripted_selection``) only for the selectors
# its declared terminal admits, and only for a terminal whose obligation this
# lane judges from engine readback and the route's decision tape (one observer
# contract per terminal, ``_CAUSAL_TERMINAL_CONTRACTS``). Commander zone choices
# (CR 903.9): graveyard and exile are the state-based choice (a COMMANDER_MOVE
# frame after the move), hand is the replacement (a REPLACEMENT_CONFIRM frame
# before it). Library contents are never exposed by the readback, so a library
# row stays unsupported. A scripted decision (``scripted_decision_offered``) is
# a cast on the caused stack: the scripted priority cast, its targets (a stack
# target named by the record's own stack) and its payment from the record's own
# ``action_cost_state`` sources. A terminal without an observer contract here
# (a priority ring, a copy, an elimination) stays unrouted.
_CAUSAL_TERMINAL_SELECTORS: dict[str, frozenset[str]] = {
    "commander_zone_choice": frozenset({"choice.boolean", "replacement_effect.boolean"}),
    "scripted_decision_offered": frozenset(
        {
            "priority.semantic_action",
            "target.semantic_object",
            "target.semantic_player",
            "target.semantic_stack_object",
            "mana_payment.mana_payment",
        }
    ),
}
_CAUSAL_ROUTE_SELECTORS: frozenset[str] = frozenset().union(*_CAUSAL_TERMINAL_SELECTORS.values())
_CAUSAL_ROUTE_TERMINALS: frozenset[str] = frozenset(_CAUSAL_TERMINAL_SELECTORS)
_COMMANDER_EVENT_FRAMES: dict[str, str] = {
    "graveyard": "COMMANDER_MOVE",
    "exile": "COMMANDER_MOVE",
    "hand": "REPLACEMENT_CONFIRM",
}

# Refusal dimension for a starting-player obligation the record does not script.
STARTING_PLAYER_UNSCRIPTED = "decision_execution.starting_player.unscripted"
# The only basis on which a starting-player selection may earn credit.
STARTING_PLAYER_AUTHORIZED_BASIS = "FIXTURE_DECISION_SCRIPT"

# Dimensions whose *observability* (not construction) is missing from the
# generic Protocol-2 readback. These do not make construction impossible, but a
# checkpoint field that cannot be observed cannot prove equivalence.
_UNOBSERVABLE_RECORD_DIMENSIONS: dict[str, str] = {
    "owner": "the generic readback exposes controller rows, not card owner",
    "attachments": "the generic readback exposes no attachment relation",
    "library": "library contents/order are never exposed; only library_size",
    "exile": "exile is exposed as names only, with no semantic identity mapping",
    "graveyard": "graveyard is exposed as names only, with no semantic identity mapping",
    "revealed": "revealed zones have no generic projection",
    "face_down": "face-down state has no bootstrap field and no generic projection",
    "prior_command_zone_cast_count": "no bootstrap field for command-zone cast counts",
    "temporal_state": "the bootstrap places permanents when the first turn begins and completes at the first-turn untap; other checkpoints are reachable only by native progression",
}


def derive_capability_matrix(source: ForgeScenarioSource, root: Path) -> dict[str, Any]:
    """Derive the exact supported/rejected scenario contract from pinned source."""
    scenario_text = _git(["show", f"{source.bridge_commit}:{SCENARIO_SOURCE_RELATIVE}"], root)
    session_text = _git(["show", f"{source.bridge_commit}:{SESSION_SOURCE_RELATIVE}"], root)
    projection_text = _git(["show", f"{source.bridge_commit}:{PROJECTION_SOURCE_RELATIVE}"], root)
    supported: dict[str, dict[str, Any]] = {}
    for capability, fragments in _SUPPORTED_FIELD_ASSERTIONS.items():
        missing = [fragment for fragment in fragments if fragment not in scenario_text]
        if missing:
            raise ScenarioCapabilityDrift(
                f"pinned ScenarioBootstrap no longer supports {capability!r}: missing {missing}"
            )
        supported[capability] = {
            "status": DIMENSION_SUPPORTED,
            "assertions": list(fragments),
            "evidence": "exact code fragment present in the pinned bridge source blob",
        }
    readback: dict[str, dict[str, Any]] = {}
    for capability, fragments in _READBACK_ASSERTIONS.items():
        missing = [fragment for fragment in fragments if fragment not in projection_text]
        if missing:
            raise ScenarioCapabilityDrift(
                f"pinned StateProjection no longer provides {capability!r}: missing {missing}"
            )
        readback[capability] = {
            "status": DIMENSION_SUPPORTED,
            "assertions": list(fragments),
            "evidence": "exact code fragment present in the pinned bridge source blob",
        }
    rejections: dict[str, dict[str, Any]] = {}
    for capability, fragment in _REJECTION_ASSERTIONS.items():
        if fragment not in scenario_text:
            raise ScenarioCapabilityDrift(
                f"pinned ScenarioBootstrap no longer rejects {capability!r}: missing {fragment!r}"
            )
        rejections[capability] = {
            "status": DIMENSION_UNSUPPORTED,
            "assertion": fragment,
            "enforced_at": "ScenarioBootstrap.parse -> BridgeEngine create_commander_game",
            "engine_error_code": "game_creation_failed",
        }
    hooks: dict[str, dict[str, Any]] = {}
    for hook, fragments in _HOOK_ASSERTIONS.items():
        for fragment in fragments:
            if fragment not in session_text:
                raise ScenarioCapabilityDrift(
                    f"pinned bridge session no longer provides {hook!r}: missing {fragment!r}"
                )
        hooks[hook] = {"status": "PRESENT", "assertions": list(fragments)}
    for hook, fragments in _SCENARIO_HOOK_ASSERTIONS.items():
        for fragment in fragments:
            if fragment not in scenario_text:
                raise ScenarioCapabilityDrift(
                    f"pinned ScenarioBootstrap no longer provides {hook!r}: missing {fragment!r}"
                )
        hooks[hook] = {"status": "PRESENT", "assertions": list(fragments)}
    return {
        "schema_version": f"{LANE_SCHEMA_VERSION}.capability-matrix",
        "source": {
            "bridge_commit": source.bridge_commit,
            "bridge_tree": source.bridge_tree,
            "scenario_source_path": SCENARIO_SOURCE_RELATIVE,
            "scenario_source_sha256": source.scenario_source_sha256,
            "session_source_path": SESSION_SOURCE_RELATIVE,
            "session_source_sha256": source.session_source_sha256,
            "projection_source_path": PROJECTION_SOURCE_RELATIVE,
            "projection_source_sha256": source.projection_source_sha256,
        },
        "supported": supported,
        "readback": readback,
        "rejected": rejections,
        "hook": hooks,
        "unsupported_record_dimensions": _UNSUPPORTED_RECORD_DIMENSIONS,
        "unobservable_record_dimensions": _UNOBSERVABLE_RECORD_DIMENSIONS,
        "note": (
            "capability matrix derived from the exact pinned bridge source blob; a source "
            "change that removes any asserted fragment raises ScenarioCapabilityDrift and no "
            "row credit can be produced until the matrix is re-derived and reviewed"
        ),
    }


# ---------------------------------------------------------------------------
# Effective-record translation and per-dimension classification
# ---------------------------------------------------------------------------
@dataclass
class DimensionFinding:
    dimension: str
    status: str
    detail: str
    requested: Any = None
    runtime_probe: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "status": self.status,
            "detail": self.detail,
            "requested": self.requested,
            "runtime_probe": self.runtime_probe,
        }


@dataclass
class RequestedStateModel:
    fixture_id: str
    record: dict[str, Any]
    neutral_initial_state: dict[str, Any]
    hands_by_player: dict[str, list[str]]
    life_by_player: dict[str, int]
    commander_damage_by_player: dict[str, dict[str, int]]
    battlefield: list[dict[str, Any]]
    command_zone: list[dict[str, Any]]
    temporal_state: dict[str, Any]
    dimensions: list[DimensionFinding] = field(default_factory=list)
    player_count: int = 0
    unscoped_requested_fields: dict[str, Any] = field(default_factory=dict)
    causal_plan: fcr.CausalPlan | None = None

    @property
    def hard_unsupported(self) -> list[DimensionFinding]:
        return [item for item in self.dimensions if item.status == DIMENSION_UNSUPPORTED]

    @property
    def unobservable(self) -> list[DimensionFinding]:
        return [item for item in self.dimensions if item.status == DIMENSION_UNOBSERVABLE]

    @property
    def construction_eligible(self) -> bool:
        """Every requested field can be represented in the bootstrap plan."""
        return not self.hard_unsupported

    @property
    def credit_eligible(self) -> bool:
        """Construction AND observation AND checkpoint reachability all hold."""
        return not self.hard_unsupported and not self.unobservable

    def to_document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "player_count": self.player_count,
            "neutral_initial_state": self.neutral_initial_state,
            "hands_by_player": self.hands_by_player,
            "life_by_player": self.life_by_player,
            "commander_damage_by_player": self.commander_damage_by_player,
            "battlefield": self.battlefield,
            "command_zone": self.command_zone,
            "temporal_state": self.temporal_state,
            "construction_eligible": self.construction_eligible,
            "credit_eligible": self.credit_eligible,
            "dimensions": [item.to_document() for item in self.dimensions],
            "unscoped_requested_fields": self.unscoped_requested_fields,
            "causal_plan": None if self.causal_plan is None else self.causal_plan.to_document(),
        }


def _requested_hands(record: dict[str, Any]) -> dict[str, list[str]]:
    hands: dict[str, list[str]] = {}
    for obj in record.get("semantic_objects") or []:
        if not isinstance(obj, dict) or obj.get("zone") != "hand":
            continue
        controller = str(obj.get("controller") or "")
        card = str(obj.get("card_identity") or "")
        if controller and card:
            hands.setdefault(controller.lower(), []).append(card)
    return hands


def _requested_battlefield(record: dict[str, Any]) -> list[dict[str, Any]]:
    placements: list[dict[str, Any]] = []
    for obj in record.get("semantic_objects") or []:
        if not isinstance(obj, dict) or obj.get("zone") != "battlefield":
            continue
        entry: dict[str, Any] = {
            "card": obj.get("card_identity"),
            "controller": str(obj.get("controller") or "").lower(),
            "owner": str(obj.get("owner") or obj.get("controller") or "").lower(),
            "semantic_id": obj.get("semantic_id"),
        }
        if obj.get("tapped"):
            entry["tapped"] = True
        counters = obj.get("counters") or {}
        if counters:
            entry["counters"] = dict(counters)
        if obj.get("attached_to"):
            entry["attached_to"] = obj.get("attached_to")
        # Requested control history (CR 302.6) is forwarded for verification
        # only. At forge#33 the bootstrap neither reads nor validates it: the
        # lane's checkpoint comparison against the battlefield_details readback
        # (the engine's !isFirstTurnControlled()) is the entire check, and a
        # missing or non-boolean readback is a MISMATCH.
        if obj.get("controlled_since_turn_began") is not None:
            entry["controlled_since_turn_began"] = obj.get("controlled_since_turn_began")
        placements.append(entry)
    return placements


def _requested_command_zone(record: dict[str, Any]) -> list[dict[str, Any]]:
    commanders: list[dict[str, Any]] = []
    commander_state = record.get("commander_state") or {}
    identity_by_id = {
        str(item.get("commander_id")): item
        for item in commander_state.get("commanders") or []
        if isinstance(item, dict)
    }
    for obj in record.get("semantic_objects") or []:
        if not isinstance(obj, dict) or obj.get("zone") != "command":
            continue
        commander_id = obj.get("commander_id")
        if not commander_id:
            continue
        declared = identity_by_id.get(str(commander_id), {})
        commanders.append(
            {
                "semantic_id": obj.get("semantic_id"),
                "commander_id": commander_id,
                "card_identity": obj.get("card_identity"),
                "owner": str(obj.get("owner") or "").lower(),
                "zone": declared.get("zone", "command"),
                "prior_command_zone_cast_count": declared.get("prior_command_zone_cast_count", 0),
            }
        )
    return commanders


def _requested_commander_damage(
    record: dict[str, Any],
) -> dict[str, dict[str, int]]:
    commander_state = record.get("commander_state") or {}
    identity = {
        str(item.get("commander_id")): str(item.get("card_identity") or "")
        for item in commander_state.get("commanders") or []
        if isinstance(item, dict)
    }
    damage: dict[str, dict[str, int]] = {}
    for entry in commander_state.get("commander_damage_matrix") or []:
        if not isinstance(entry, dict):
            continue
        player = str(entry.get("damaged_player") or "").lower()
        commander_id = str(entry.get("source_commander_id") or "")
        card = identity.get(commander_id, "")
        amount = entry.get("combat_damage")
        if not player or not card or not isinstance(amount, int):
            continue
        damage.setdefault(player, {})
        damage[player][card] = damage[player].get(card, 0) + amount
    return damage


def _requested_life(record: dict[str, Any]) -> dict[str, int]:
    life: dict[str, int] = {}
    for player in record.get("players") or []:
        if not isinstance(player, dict):
            continue
        player_id = str(player.get("player_id") or "").lower()
        if player_id and isinstance(player.get("life"), int):
            life[player_id] = player["life"]
    return life


def _requested_temporal(record: dict[str, Any]) -> dict[str, Any]:
    temporal = record.get("temporal_state") or {}
    return {
        "turn_number": temporal.get("turn_number"),
        "phase": str(temporal.get("phase") or "").lower() or None,
        "step": str(temporal.get("step") or "").lower() or None,
        "active_player": str(temporal.get("active_player") or "").lower() or None,
        "priority_player": str(temporal.get("priority_player") or "").lower() or None,
    }


def _commander_zone_route(record: dict[str, Any], plan: fcr.CausalPlan) -> bool:
    """One spell aimed at exactly one commander, for a zone the readback exposes."""
    required = list((record.get("expected_events") or {}).get("required_events") or [])
    zone = _required_token(required, "commander_zone_event:")
    if zone not in _COMMANDER_EVENT_FRAMES or not _required_token(required, "commander_choice:"):
        return False
    if len(plan.spells) != 1:
        return False
    (spell,) = plan.spells
    commanders = [
        obj
        for obj in record.get("semantic_objects") or ()
        if isinstance(obj, dict)
        and obj.get("commander_id")
        and obj.get("semantic_id") in spell.targets
    ]
    return len(spell.targets) == 1 and len(commanders) == 1


def _scripted_decision_route(record: dict[str, Any], plan: fcr.CausalPlan) -> bool:
    """The script opens with a priority cast and declares obligation tokens."""
    script = [step for step in record.get("decision_script") or () if isinstance(step, dict)]
    required = (record.get("expected_events") or {}).get("required_events") or []
    return bool(plan.spells) and script[0].get("decision_family") == "priority" and bool(required)


_CAUSAL_TERMINAL_ROUTES = {
    "commander_zone_choice": _commander_zone_route,
    "scripted_decision_offered": _scripted_decision_route,
}


def lane_causal_plan(record: dict[str, Any]) -> fcr.CausalPlan | None:
    """The causal stack route this lane can run and judge for a record, or None.

    The route needs the shared declared entry (with its fuel), a complete,
    modeless stack, a terminal with an observer contract in this lane, scripted
    steps the shared selector answers for that terminal, and the terminal's own
    shape (``_CAUSAL_TERMINAL_ROUTES``).
    """
    fixture_id = str(record.get("fixture_id"))
    entry = fcr.declared_causal_entry(fixture_id)
    terminal = None if entry is None else str(entry.get("terminal"))
    if entry is None or terminal not in _CAUSAL_ROUTE_TERMINALS:
        return None
    script = [step for step in record.get("decision_script") or () if isinstance(step, dict)]
    if not script or any(
        f"{step.get('decision_family')}.{(step.get('selection') or {}).get('selector_kind')}"
        not in _CAUSAL_TERMINAL_SELECTORS[terminal]
        for step in script
    ):
        return None
    plan = fcr.causal_plan(record, entry)
    if plan is None or not _CAUSAL_TERMINAL_ROUTES[terminal](record, plan):
        return None
    return plan


def causal_terminal(model: RequestedStateModel) -> str | None:
    """The declared terminal of a routed record (None when the lane has no route)."""
    if model.causal_plan is None:
        return None
    entry = fcr.declared_causal_entry(model.fixture_id) or {}
    terminal = str(entry.get("terminal"))
    return terminal if terminal in _CAUSAL_ROUTE_TERMINALS else None


def model_requested_state(record: dict[str, Any]) -> RequestedStateModel:
    """Translate an effective FULL107 record into the bootstrap contract.

    Every requested dimension the bootstrap cannot represent becomes an exact
    finding. Nothing is silently dropped and no fixture is weakened.
    """
    fixture_id = str(record.get("fixture_id"))
    hands = _requested_hands(record)
    battlefield = _requested_battlefield(record)
    command_zone = _requested_command_zone(record)
    commander_damage = _requested_commander_damage(record)
    life = _requested_life(record)
    temporal = _requested_temporal(record)
    players = record.get("players") or []
    player_count = len(players) if isinstance(players, list) else 0

    neutral: dict[str, Any] = {}
    if battlefield:
        neutral["battlefield"] = [
            {key: value for key, value in placement.items() if key != "semantic_id"}
            for placement in battlefield
        ]
    if hands:
        neutral["hands"] = dict(hands)
    if life:
        neutral["life"] = dict(life)
    if commander_damage:
        neutral["players"] = [
            {"id": player_id, "commander_damage_taken": dict(damage)}
            for player_id, damage in commander_damage.items()
        ]

    plan = lane_causal_plan(record)
    if plan is not None:
        neutral = fcr.pre_causal_state(neutral, plan)

    dimensions: list[DimensionFinding] = []
    dimensions.extend(_classify_record_dimensions(record, plan))

    # Requested zones the bootstrap cannot place.
    zone_objects = Counter(
        str(obj.get("zone"))
        for obj in (record.get("semantic_objects") or [])
        if isinstance(obj, dict)
    )
    for zone, reason in (
        ("stack", "the bootstrap rejects stack injection and has no stack field"),
        ("library", _UNOBSERVABLE_RECORD_DIMENSIONS["library"]),
        ("exile", _UNOBSERVABLE_RECORD_DIMENSIONS["exile"]),
        ("graveyard", _UNOBSERVABLE_RECORD_DIMENSIONS["graveyard"]),
        ("revealed", _UNOBSERVABLE_RECORD_DIMENSIONS["revealed"]),
    ):
        if zone_objects.get(zone):
            status = DIMENSION_UNSUPPORTED if zone == "stack" else DIMENSION_UNOBSERVABLE
            if zone == "stack" and plan is not None:
                status, reason = DIMENSION_CAUSED, _CAUSED_STACK_DETAIL
            dimensions.append(
                DimensionFinding(
                    dimension=f"semantic_objects.zone:{zone}",
                    status=status,
                    detail=reason,
                    requested=zone_objects[zone],
                    runtime_probe="stack"
                    if status == DIMENSION_UNSUPPORTED and zone == "stack"
                    else None,
                )
            )
    for obj in record.get("semantic_objects") or []:
        if not isinstance(obj, dict):
            continue
        if obj.get("face_down"):
            dimensions.append(
                DimensionFinding(
                    dimension="semantic_objects.face_down",
                    status=DIMENSION_UNSUPPORTED,
                    detail=_UNOBSERVABLE_RECORD_DIMENSIONS["face_down"],
                    requested=obj.get("semantic_id"),
                )
            )
        if obj.get("controlled_since_turn_began") is not None and not isinstance(
            obj.get("controlled_since_turn_began"), bool
        ):
            # G1 R1 (C3): the dimension is checkpoint-verified, which needs a
            # boolean request; anything else fails closed here.
            dimensions.append(
                DimensionFinding(
                    dimension="semantic_objects.controlled_since_turn_began",
                    status=DIMENSION_UNSUPPORTED,
                    detail="controlled_since_turn_began must be a boolean to be verified",
                    requested=obj.get("semantic_id"),
                )
            )
        elif (
            obj.get("controlled_since_turn_began") is not None and obj.get("zone") != "battlefield"
        ):
            # Control history exists only for permanents; the readback has no
            # other zone to verify it against.
            dimensions.append(
                DimensionFinding(
                    dimension="semantic_objects.controlled_since_turn_began",
                    status=DIMENSION_UNSUPPORTED,
                    detail="controlled_since_turn_began is verifiable only for battlefield objects",
                    requested=obj.get("semantic_id"),
                )
            )
        if (
            obj.get("owner") is not None
            and obj.get("controller") is not None
            and str(obj.get("owner")).lower() != str(obj.get("controller")).lower()
        ):
            # Constructible (placement has an owner field) but not observable
            # in the generic projection.
            dimensions.append(
                DimensionFinding(
                    dimension="owner_controller_divergence",
                    status=DIMENSION_UNOBSERVABLE,
                    detail=_UNOBSERVABLE_RECORD_DIMENSIONS["owner"],
                    requested={
                        "semantic_id": obj.get("semantic_id"),
                        "owner": obj.get("owner"),
                        "controller": obj.get("controller"),
                    },
                )
            )

    # Attachment construction is supported; observation is not.
    if any(
        isinstance(obj, dict) and obj.get("attached_to")
        for obj in record.get("semantic_objects") or []
    ):
        dimensions.append(
            DimensionFinding(
                dimension="semantic_objects.attached_to",
                status=DIMENSION_UNOBSERVABLE,
                detail=_UNOBSERVABLE_RECORD_DIMENSIONS["attachments"],
                requested="present",
            )
        )

    # Command-zone cast counts are not constructible.
    for commander in command_zone:
        count = commander.get("prior_command_zone_cast_count")
        if isinstance(count, int) and count > 0:
            dimensions.append(
                DimensionFinding(
                    dimension="commander_state.prior_command_zone_cast_count",
                    status=DIMENSION_UNSUPPORTED,
                    detail=_UNOBSERVABLE_RECORD_DIMENSIONS["prior_command_zone_cast_count"],
                    requested={commander["commander_id"]: count},
                )
            )

    # Temporal checkpoint reachability: the bootstrap places at the first turn's
    # TurnBegan event and the retained hook completes the apply at the first-turn
    # untap step. Other requested checkpoints are reachable only by native
    # progression, and a requested explicit hand cannot equal the post-draw hand
    # unless the draw step is skipped.
    turn = temporal.get("turn_number")
    active = temporal.get("active_player")
    if turn is not None and turn != 1:
        dimensions.append(
            DimensionFinding(
                dimension="temporal_state.turn_number",
                status=DIMENSION_UNSUPPORTED,
                detail="the bootstrap hook runs during the first turn only",
                requested=turn,
            )
        )
    if (
        active
        and active != "p1"
        and not (
            player_count == 2
            and active == "p1"  # 2P starting player is externally chosen; recorded separately
        )
    ):
        dimensions.append(
            DimensionFinding(
                dimension="temporal_state.active_player",
                status=DIMENSION_UNSUPPORTED,
                detail=(
                    "the bootstrap hook establishes the starting player's first turn; a "
                    "different active player cannot be constructed"
                ),
                requested=active,
            )
        )
    if hands and player_count > 2 and active == "p1":
        # 3P+ starting player draws in the first turn draw step; an exact
        # requested hand observed at precombat main cannot be held by a
        # bootstrap hand alone (library ordering is not supported).
        dimensions.append(
            DimensionFinding(
                dimension="temporal_checkpoint.exact_hand_after_draw",
                status=DIMENSION_UNSUPPORTED,
                detail=(
                    "the requested explicit hand must survive the natural first-turn draw "
                    "step to the requested checkpoint; the bootstrap cannot hold library "
                    "order or suppress the draw, so exact hand equality is unconstructible"
                ),
                requested={player: len(cards) for player, cards in hands.items()},
            )
        )

    # A requested combat step stays fail-closed here. Since G1 R1 (#561) the
    # active seat's placed creatures are no longer summoning sick on turn 1 (they
    # enter when the first turn begins, before the engine's readiness loop), so
    # summoning sickness is no longer the reason. The reasons that remain: the
    # bootstrap has no combat-state field, this lane executes no
    # declare-attacker/blocker selection, and the six combat-step rows await
    # their own Coordinator ruling (G1: "the six combat-step rows get a
    # separate ruling"). Nothing here is credited until that ruling exists.
    requested_step = temporal.get("step")
    requested_phase = temporal.get("phase")
    if requested_phase == "combat" or (
        requested_step and str(requested_step).startswith(("declare_", "combat", "first_strike"))
    ):
        dimensions.append(
            DimensionFinding(
                dimension="temporal_state.combat_step",
                status=DIMENSION_UNSUPPORTED,
                detail=(
                    "the requested combat step is not established by the bootstrap: there "
                    "is no combat-state field and the lane executes no combat declaration; "
                    "the combat-step rows await a separate Coordinator ruling (G1)"
                ),
                requested={"phase": requested_phase, "step": requested_step},
            )
        )

    return RequestedStateModel(
        fixture_id=fixture_id,
        record=record,
        neutral_initial_state=neutral,
        hands_by_player=hands,
        life_by_player=life,
        commander_damage_by_player=commander_damage,
        battlefield=battlefield,
        command_zone=command_zone,
        temporal_state=temporal,
        dimensions=_dedupe(dimensions),
        player_count=player_count,
        causal_plan=plan,
    )


_CAUSED_STACK_DETAIL = (
    "reached causally: the declared spell is cast by its controller from a pre-causal "
    "position with declared fuel, on the engine's own frames (forge_causal_route)"
)


def _classify_record_dimensions(
    record: dict[str, Any], plan: fcr.CausalPlan | None = None
) -> list[DimensionFinding]:
    findings: list[DimensionFinding] = []
    stack_state = record.get("stack_state") or []
    if stack_state:
        findings.append(
            DimensionFinding(
                dimension="stack_state",
                status=DIMENSION_UNSUPPORTED if plan is None else DIMENSION_CAUSED,
                detail=(
                    _UNSUPPORTED_RECORD_DIMENSIONS["stack_state"]
                    if plan is None
                    else _CAUSED_STACK_DETAIL
                ),
                requested=[
                    {
                        "source_semantic_id": entry.get("source_semantic_id"),
                        "controller": entry.get("controller"),
                        "targets": entry.get("targets"),
                    }
                    for entry in stack_state
                    if isinstance(entry, dict)
                ],
                runtime_probe="stack" if plan is None else None,
            )
        )
    # A fixture decision_script is an EXECUTION requirement (the engine must
    # offer a decision and the harness must select within the offered domain),
    # never a request to inject decisions into the neutral state. Families this
    # lane cannot execute are recorded as exact execution blockers rather than
    # being misattributed to a bootstrap limitation.
    for index, entry in enumerate(record.get("decision_script") or []):
        if not isinstance(entry, dict):
            continue
        family = str(entry.get("decision_family") or "unknown")
        selector = entry.get("selection") or {}
        selector_kind = str(selector.get("selector_kind") or "unknown")
        token = f"{family}.{selector_kind}"
        if token in _LANE_EXECUTABLE_DECISION_SELECTORS:
            continue
        if plan is not None and token in _CAUSAL_ROUTE_SELECTORS:
            findings.append(
                DimensionFinding(
                    dimension=f"decision_execution.{token}",
                    status=DIMENSION_CAUSED,
                    detail=(
                        "answered on the engine's own frame by the shared fail-closed "
                        "selector during the causal route"
                    ),
                    requested={
                        "decision_index": index,
                        "actor": entry.get("actor"),
                        "causal_step_id": entry.get("causal_step_id"),
                        "selector_kind": selector_kind,
                        "semantic_value": selector.get("semantic_value"),
                    },
                )
            )
            continue
        findings.append(
            DimensionFinding(
                dimension=f"decision_execution.{token}",
                status=DIMENSION_UNSUPPORTED,
                detail=(
                    "this lane implements only engine-authored pass/mulligan/"
                    "starting-player/cost-order selection; executing this declared "
                    "decision family and selector requires a selector surface owned by "
                    "the shared mid-game selector workstream, and this lane must not "
                    "build a second generic selector or fabricate an option"
                ),
                requested={
                    "decision_index": index,
                    "actor": entry.get("actor"),
                    "causal_step_id": entry.get("causal_step_id"),
                    "selector_kind": selector_kind,
                    "semantic_value": selector.get("semantic_value"),
                },
            )
        )
    # A starting-player obligation is decided by a player's choice (CR 103.1).
    # The lane may select the starter only on an authorized scripted response:
    # choosing it from the requested end state would satisfy the obligation by
    # construction (requested-option selection), so without a scripted response
    # the row is refused rather than executed. No frozen record scripts that
    # decision family today; closing this needs a contract erratum.
    required_tokens = (record.get("expected_events") or {}).get("required_events") or []
    if any(str(token).startswith("starting_player:") for token in required_tokens) and not any(
        isinstance(entry, dict) and entry.get("decision_family") == "starting_player"
        for entry in record.get("decision_script") or []
    ):
        findings.append(
            DimensionFinding(
                dimension=STARTING_PLAYER_UNSCRIPTED,
                status=DIMENSION_UNSUPPORTED,
                detail=(
                    "the obligation names a starting player, but the effective record "
                    "scripts no starting-player response; the Lab may not choose the "
                    "starter from the requested state"
                ),
                requested={"required_events": [str(t) for t in required_tokens]},
            )
        )
    if record.get("combat_state"):
        combat = record["combat_state"]
        findings.append(
            DimensionFinding(
                dimension="combat_state",
                status=DIMENSION_UNSUPPORTED,
                detail=_UNSUPPORTED_RECORD_DIMENSIONS["combat_state"],
                requested={
                    "attackers": combat.get("attackers"),
                    "eligible_blockers": combat.get("eligible_blockers"),
                    "eligible_attackers": combat.get("eligible_attackers"),
                },
            )
        )
    cost_state = record.get("action_cost_state") or []
    if cost_state:
        findings.append(
            DimensionFinding(
                dimension="action_cost_state",
                status=DIMENSION_UNSUPPORTED,
                detail=_UNSUPPORTED_RECORD_DIMENSIONS["action_cost_state"],
                requested=[
                    {
                        "actor": entry.get("actor"),
                        "source_semantic_id": entry.get("source_semantic_id"),
                        "payable": entry.get("payable"),
                    }
                    for entry in cost_state
                    if isinstance(entry, dict)
                ],
            )
        )
    randomness = record.get("rules_randomness") or {}
    if randomness.get("predetermined_semantic_draws"):
        findings.append(
            DimensionFinding(
                dimension="rules_randomness.predetermined_semantic_draws",
                status=DIMENSION_UNSUPPORTED,
                detail=_UNSUPPORTED_RECORD_DIMENSIONS[
                    "rules_randomness.predetermined_semantic_draws"
                ],
                requested=randomness.get("predetermined_semantic_draws"),
            )
        )
    knowledge = record.get("knowledge_state") or {}
    viewer_states = knowledge.get("viewer_states") or []
    material_permissions = [
        state
        for state in viewer_states
        if isinstance(state, dict)
        and any(
            state.get(key)
            for key in (
                "known_library_ranges",
                "known_object_identities",
                "temporary_permissions",
                "face_down_look_permissions",
                "invalidation_conditions",
            )
        )
    ]
    if material_permissions:
        findings.append(
            DimensionFinding(
                dimension="knowledge_state",
                status=DIMENSION_UNSUPPORTED,
                detail=_UNSUPPORTED_RECORD_DIMENSIONS["knowledge_state"],
                requested=len(material_permissions),
            )
        )
    return findings


def _dedupe(findings: list[DimensionFinding]) -> list[DimensionFinding]:
    seen: set[tuple[str, str]] = set()
    unique: list[DimensionFinding] = []
    for finding in findings:
        key = (finding.dimension, finding.status)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


# ---------------------------------------------------------------------------
# Deck construction
# ---------------------------------------------------------------------------
def build_commander_deck(
    deck_id: str,
    commander_names: list[str],
    *,
    basic: str = DEFAULT_MAINBOARD_BASIC,
) -> dict[str, Any]:
    """A real 100-card Commander deck matching the requested commanders."""
    if not 1 <= len(commander_names) <= 2:
        raise ScenarioLaneError("a Commander deck needs one or two partner commanders")
    mainboard_size = 100 - len(commander_names)
    mainboard = [basic] * mainboard_size
    digest = hashlib.sha256(("|".join([*commander_names, *mainboard])).encode("utf-8")).hexdigest()
    return {
        "deck_id": deck_id,
        "deck_hash": digest,
        "name": f"FSL {deck_id}",
        "commander_names": list(commander_names),
        "mainboard": mainboard,
    }


def _deck_plan(model: RequestedStateModel) -> dict[str, list[str]]:
    """Per-seat commander lists from the requested commander identities.

    ``commander_state.commanders`` is the authoritative roster: it names every
    commander identity, including a partner that a fixture references only from
    its damage matrix. Deriving decks from battlefield/command-zone semantic
    objects alone dropped partner identities and made the engine's commander
    damage seeding unresolvable.
    """
    plan: dict[str, list[str]] = {}
    commander_state = model.record.get("commander_state") or {}
    for entry in commander_state.get("commanders") or []:
        if not isinstance(entry, dict):
            continue
        owner = str(entry.get("owner") or "").lower()
        card = str(entry.get("card_identity") or "")
        if owner and card:
            plan.setdefault(owner, []).append(card)
    # Fall back to the requested command-zone objects when no roster is declared.
    for entry in model.command_zone:
        owner = str(entry.get("owner") or "").lower()
        card = str(entry.get("card_identity") or "")
        if owner and card and card not in plan.get(owner, []):
            plan.setdefault(owner, []).append(card)
    for index in range(1, model.player_count + 1):
        plan.setdefault(f"p{index}", [])
    return plan


# ---------------------------------------------------------------------------
# Engine observation helpers
# ---------------------------------------------------------------------------
def _payload(response: dict[str, Any]) -> dict[str, Any]:
    value = response.get("payload")
    return value if isinstance(value, dict) else {}


def observe_seat_state(proc: BridgeProcess, game_id: str, seat: str) -> dict[str, Any]:
    response = proc.request(
        "get_game_state", {"observer_player_id": seat}, game_id=game_id, timeout_s=120.0
    )
    return response


def observe_all_seats(
    proc: BridgeProcess, game_id: str, seat_count: int
) -> dict[str, dict[str, Any]]:
    seats = SEATS[:seat_count]
    return {seat: observe_seat_state(proc, game_id, seat) for seat in seats}


@dataclass
class FieldVerdict:
    field: str
    verdict: str
    requested: Any = None
    observed: Any = None
    detail: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "verdict": self.verdict,
            "requested": self.requested,
            "observed": self.observed,
            "detail": self.detail,
        }


@dataclass
class CheckpointEquivalence:
    verdict: str
    fields: list[FieldVerdict]
    unsupported_dimensions: list[str]
    unobservable_dimensions: list[str]
    variance_source: str | None = None

    @property
    def exact(self) -> bool:
        return self.verdict == CHECKPOINT_EXACT

    @property
    def credit_eligible(self) -> bool:
        return self.verdict in (CHECKPOINT_EXACT, CHECKPOINT_ALLOWED_VARIANCE)

    def to_document(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "variance_source": self.variance_source,
            "fields": [item.to_document() for item in self.fields],
            "unsupported_dimensions": list(self.unsupported_dimensions),
            "unobservable_dimensions": list(self.unobservable_dimensions),
        }


def _declared_player_loss_cause(model: RequestedStateModel) -> bool:
    """Whether the fixture itself declares a native player-loss cause."""
    for step in model.record.get("native_procedure") or []:
        if not isinstance(step, dict):
            continue
        if "PLAYER_LOSS" in str(step.get("operation", "")):
            return True
    return False


def _losing_players(model: RequestedStateModel) -> set[str]:
    if not _declared_player_loss_cause(model):
        return set()
    return {
        player_id
        for player_id, life in model.life_by_player.items()
        if isinstance(life, int) and life <= 0
    }


def effective_temporal_target(model: RequestedStateModel) -> dict[str, Any]:
    """The temporal target after the fixture's own declared native cause.

    A seat that is eliminated by the declared loss cannot hold priority or be
    the active player afterwards, so chasing those pre-cause coordinates would
    exhaust the drive bound. They are dropped from the *reachable* target and
    the difference is recorded as a fixture-declared cause advance, never as an
    invented variance.
    """
    target = dict(model.temporal_state)
    losing = _losing_players(model)
    if losing:
        if target.get("priority_player") in losing:
            target["priority_player"] = None
        if target.get("active_player") in losing:
            target["active_player"] = None
    return target


def temporal_reachable(model: RequestedStateModel) -> bool:
    """Whether the requested temporal checkpoint is reachable by native play.

    The bootstrap places permanents when the requested starting player's first
    turn begins and completes at that turn's untap step. Any other turn, a
    different active player, or a combat step (no combat state can be
    established and the combat-step rows await a separate G1 ruling) is not
    reachable and must fail closed statically.
    """
    temporal = model.temporal_state
    if not temporal:
        return True
    turn = temporal.get("turn_number")
    if turn is not None and turn != 1:
        return False
    active = temporal.get("active_player")
    if active and active != "p1":
        return False
    phase = temporal.get("phase")
    step = temporal.get("step")
    if phase == "combat":
        return False
    return not (step and str(step).startswith(("declare_", "combat", "first_strike")))


# Transport field mapping between the contract counter vocabulary and the
# bridge's CounterEnumType display names (ScenarioBootstrap accepts the enum
# constant name via CounterEnumType.valueOf; StateProjection emits
# CounterType.getName()). Mapping is name-space translation only: a counter not
# in this table is compared verbatim so an unknown counter fails closed.
_COUNTER_DISPLAY_NAMES = {
    "P1P1": "+1/+1",
    "M1M1": "-1/-1",
}


def _canonical_counters(counters: dict[str, Any]) -> dict[str, Any]:
    return {
        _COUNTER_DISPLAY_NAMES.get(str(key), str(key)): value for key, value in counters.items()
    }


def _group_field_verdict(requested: list[Any], observed: list[Any]) -> str:
    """Verdict for one field over same-name, same-controller objects (P3-1).

    The readback names objects only by card name, so ``n`` requested objects
    and the ``m`` matching details are compared as multisets. ``requested``
    holds one value per requested object (``None`` = unconstrained). EXACT
    only when every matching detail agrees with every constrained request;
    MISMATCH when the observed multiset cannot hold the requests; UNKNOWN
    when it can but the readback cannot say which object holds which value.
    """
    constrained = [value for value in requested if value is not None]
    if not constrained:
        return CHECKPOINT_EXACT
    if len(observed) < len(requested):
        return CHECKPOINT_MISMATCH
    keys_observed = Counter(json.dumps(value, sort_keys=True) for value in observed)
    keys_requested = Counter(json.dumps(value, sort_keys=True) for value in constrained)
    if any(keys_observed[key] < count for key, count in keys_requested.items()):
        return CHECKPOINT_MISMATCH
    if len(keys_observed) == 1:
        return CHECKPOINT_EXACT
    return CHECKPOINT_UNKNOWN


def _state_view(response: dict[str, Any]) -> dict[str, Any]:
    state = _payload(response).get("state")
    return state if isinstance(state, dict) else {}


def _players_by_id(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for player in state.get("players") or []:
        if isinstance(player, dict) and player.get("player_id"):
            rows[str(player["player_id"]).lower()] = player
    return rows


_PHASE_ALIASES = {
    "main1": "precombat_main",
    "main_1": "precombat_main",
    "precombatmain": "precombat_main",
}

# Structural transport mapping between the bridge's Forge phase-enum step names
# (StateProjection emits ``phase.name()``) and the contract's normalized step
# vocabulary. This is field mapping, not rules inference: no step is invented
# and no obligation semantics change.
_STEP_TO_CONTRACT = {
    "main1": "main",
    "combat_begin": "combat_begin",
    "combat_declare_attackers": "declare_attackers",
    "combat_declare_blockers": "declare_blockers",
    "combat_first_strike_damage": "first_strike_damage",
    "combat_damage": "combat_damage",
    "combat_end": "end_of_combat",
    "end_turn": "end_step",
    "cleanup": "cleanup",
    "untap": "untap",
    "upkeep": "upkeep",
    "draw": "draw",
}


def _normalize_step(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace(" ", "_")
    return _STEP_TO_CONTRACT.get(text, text)


def _normalize_phase(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace(" ", "_")
    return _PHASE_ALIASES.get(text, text)


def compare_checkpoint(
    model: RequestedStateModel, seat_observations: dict[str, dict[str, Any]]
) -> CheckpointEquivalence:
    """Field-level requested-vs-constructed comparison from engine readback.

    Every requested field is compared. Any unsupported dimension is a hard
    no-credit classification; any unobservable requested field is a hard
    no-credit classification. Only a comparison with no mismatch, no
    unsupported field and no unobservable field reaches EXACT.
    """
    verdicts: list[FieldVerdict] = []
    if not seat_observations:
        return CheckpointEquivalence(
            verdict=CHECKPOINT_TRANSPORT_FAILURE,
            fields=[],
            unsupported_dimensions=[item.dimension for item in model.hard_unsupported],
            unobservable_dimensions=[item.dimension for item in model.unobservable],
        )
    primary = _state_view(next(iter(seat_observations.values())))
    players = _players_by_id(primary)

    # temporal_state
    temporal = model.temporal_state
    losing = _losing_players(model)
    if temporal:
        observed = {
            "turn_number": primary.get("turn_number"),
            "phase": _normalize_phase(primary.get("phase")),
            "step": _normalize_step(primary.get("step")),
            "active_player": (
                str(primary.get("active_player_id")).lower()
                if primary.get("active_player_id")
                else None
            ),
            "priority_player": (
                str(primary.get("priority_player_id")).lower()
                if primary.get("priority_player_id")
                else None
            ),
        }
        requested = dict(temporal)
        mismatched: dict[str, Any] = {}
        cause_fields: dict[str, Any] = {}
        for key, expected in requested.items():
            if expected is None:
                continue
            actual = observed.get(key)
            if expected == actual:
                continue
            if key in ("priority_player", "active_player") and expected in losing:
                cause_fields[key] = {"requested": expected, "observed": actual}
                continue
            mismatched[key] = {"requested": expected, "observed": actual}
        if mismatched:
            temporal_verdict = CHECKPOINT_MISMATCH
            temporal_detail = f"mismatched fields: {sorted(mismatched)}"
        elif cause_fields:
            temporal_verdict = "CAUSE_ADVANCE"
            temporal_detail = (
                "fixture-declared native player loss removes the requested pre-cause "
                f"priority/active coordinates: {json.dumps(cause_fields, sort_keys=True)}"
            )
        else:
            temporal_verdict = CHECKPOINT_EXACT
            temporal_detail = "all matched"
        verdicts.append(
            FieldVerdict(
                field="temporal_state",
                verdict=temporal_verdict,
                requested=requested,
                observed=observed,
                detail=temporal_detail,
            )
        )

    # life
    for player_id, expected in model.life_by_player.items():
        life_row = players.get(player_id)
        observed_life = life_row.get("life") if isinstance(life_row, dict) else None
        verdicts.append(
            FieldVerdict(
                field=f"players.{player_id}.life",
                verdict=(CHECKPOINT_EXACT if observed_life == expected else CHECKPOINT_MISMATCH),
                requested=expected,
                observed=observed_life,
            )
        )

    # commander damage
    for player_id, _damage in model.commander_damage_by_player.items():
        damage_row = players.get(player_id)
        observed_damage = (
            damage_row.get("commander_damage_received") if isinstance(damage_row, dict) else None
        )
        by_identity: dict[str, int] = {}
        identity = {
            str(item.get("commander_id")): str(item.get("card_identity") or "")
            for item in (model.record.get("commander_state") or {}).get("commanders") or []
            if isinstance(item, dict)
        }
        source_cards: list[str] = []
        for entry in (model.record.get("commander_state") or {}).get(
            "commander_damage_matrix"
        ) or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("damaged_player") or "").lower() != player_id:
                continue
            card = identity.get(str(entry.get("source_commander_id") or ""), "")
            amount = entry.get("combat_damage")
            if card and isinstance(amount, int):
                source_cards.append(card)
                by_identity[card] = by_identity.get(card, 0) + amount
        expected_names = sorted(by_identity)
        observed_map = observed_damage if isinstance(observed_damage, dict) else {}
        observed_names = sorted(str(key) for key in observed_map)
        # The readback is commander-name-keyed. Ambiguity only exists when the
        # compared sources for THIS player share a name; the full roster may
        # legitimately contain same-named commanders on different players.
        names_unique = len(set(source_cards)) == len(source_cards)
        exact = (
            names_unique
            and observed_names == expected_names
            and all(int(observed_map[name]) == by_identity[name] for name in expected_names)
        )
        verdicts.append(
            FieldVerdict(
                field=f"players.{player_id}.commander_damage_received",
                verdict=CHECKPOINT_EXACT if exact else CHECKPOINT_MISMATCH,
                requested=by_identity,
                observed=observed_map,
                detail=(
                    "commander identity is name-keyed; same-name commanders make this "
                    "comparison ambiguous and it fails closed"
                    if not names_unique
                    else ""
                ),
            )
        )

    # command zone
    for entry in model.command_zone:
        owner = str(entry.get("owner") or "").lower()
        row = players.get(owner)
        zones = row.get("zones") if isinstance(row, dict) else {}
        command = zones.get("command") if isinstance(zones, dict) else None
        command = command if isinstance(command, list) else []
        present = entry.get("card_identity") in command
        if present:
            command_verdict = CHECKPOINT_EXACT
        elif owner in losing:
            command_verdict = "CAUSE_ADVANCE"
        else:
            command_verdict = CHECKPOINT_MISMATCH
        verdicts.append(
            FieldVerdict(
                field=f"command_zone.{entry.get('commander_id')}",
                verdict=command_verdict,
                requested=entry.get("card_identity"),
                observed=command,
                detail=(
                    "fixture declares NATIVE_CAUSE_DECLARED_PLAYER_LOSS; this seat left "
                    "the game by the declared native cause"
                    if command_verdict == "CAUSE_ADVANCE"
                    else ""
                ),
            )
        )
        count = entry.get("prior_command_zone_cast_count")
        if isinstance(count, int) and count:
            cast_map = row.get("commander_cast_count") if isinstance(row, dict) else {}
            observed_count = (
                cast_map.get(entry.get("card_identity")) if isinstance(cast_map, dict) else None
            )
            verdicts.append(
                FieldVerdict(
                    field=f"commander_cast_count.{entry.get('commander_id')}",
                    verdict=(CHECKPOINT_EXACT if observed_count == count else CHECKPOINT_MISMATCH),
                    requested=count,
                    observed=observed_count,
                )
            )

    # battlefield placement / tapped / counters
    # P3-1: requested objects that share a name and a controller are matched
    # against every detail of that name as a multiset, never against the first.
    group_members: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for placement in model.battlefield:
        group_members.setdefault((placement["controller"], str(placement["card"])), []).append(
            placement
        )
    for placement in model.battlefield:
        controller = placement["controller"]
        row = players.get(controller)
        zones = row.get("zones") if isinstance(row, dict) else {}
        battlefield = zones.get("battlefield") if isinstance(zones, dict) else []
        details = zones.get("battlefield_details") if isinstance(zones, dict) else []
        battlefield = battlefield if isinstance(battlefield, list) else []
        details = details if isinstance(details, list) else []
        matching = [
            item
            for item in details
            if isinstance(item, dict) and item.get("name") == placement["card"]
        ]
        group = group_members[(controller, str(placement["card"]))]
        position = next(index for index, member in enumerate(group) if member is placement)
        detail = matching[position] if position < len(matching) else None
        present = placement["card"] in battlefield and detail is not None
        cause_declared = _declared_player_loss_cause(model)
        losing_controller = (
            cause_declared
            and isinstance(model.life_by_player.get(controller), int)
            and model.life_by_player[controller] <= 0
        )
        if present:
            placement_verdict = CHECKPOINT_EXACT
        elif losing_controller:
            placement_verdict = "CAUSE_ADVANCE"
        else:
            placement_verdict = CHECKPOINT_MISMATCH
        verdicts.append(
            FieldVerdict(
                field=f"battlefield.{placement.get('semantic_id')}",
                verdict=placement_verdict,
                requested={
                    "card": placement["card"],
                    "controller": controller,
                    "tapped": bool(placement.get("tapped")),
                    "counters": placement.get("counters") or {},
                },
                observed=(
                    None
                    if detail is None
                    else {
                        "name": detail.get("name"),
                        "tapped": detail.get("tapped"),
                        "counters": detail.get("counters"),
                    }
                ),
                detail=(
                    "fixture declares NATIVE_CAUSE_DECLARED_PLAYER_LOSS; this seat's "
                    "permanents leave by the declared native cause, not by construction "
                    "variation"
                    if placement_verdict == "CAUSE_ADVANCE"
                    else ""
                ),
            )
        )
        if detail is not None:
            observed_tapped = [bool(item.get("tapped")) for item in matching]
            verdicts.append(
                FieldVerdict(
                    field=f"battlefield.{placement.get('semantic_id')}.tapped",
                    verdict=_group_field_verdict(
                        [bool(member.get("tapped")) for member in group], observed_tapped
                    ),
                    requested=bool(placement.get("tapped")),
                    observed=observed_tapped[0] if len(observed_tapped) == 1 else observed_tapped,
                )
            )
            # G1 R1 (C3): checkpoint-verified control history. The readback is
            # the engine's own !isFirstTurnControlled(). The request is compared
            # as the literal True/False it is (no coercion); an absent or
            # non-boolean readback cannot prove equivalence and is a mismatch.
            requested_since = placement.get("controlled_since_turn_began")
            if requested_since is not None:
                observed_since = [item.get("controlled_since_turn_began") for item in matching]
                strict_request = requested_since is True or requested_since is False
                strict_readback = all(value is True or value is False for value in observed_since)
                if not (strict_request and strict_readback):
                    since_verdict = CHECKPOINT_MISMATCH
                else:
                    since_verdict = _group_field_verdict(
                        [member.get("controlled_since_turn_began") for member in group],
                        observed_since,
                    )
                verdicts.append(
                    FieldVerdict(
                        field=(
                            f"battlefield.{placement.get('semantic_id')}"
                            ".controlled_since_turn_began"
                        ),
                        verdict=since_verdict,
                        requested=requested_since,
                        observed=observed_since[0] if len(observed_since) == 1 else observed_since,
                    )
                )
            counter_requested = Counter(_canonical_counters(placement.get("counters") or {}))
            counters_observed = [
                dict(Counter(_canonical_counters(item.get("counters") or {}))) for item in matching
            ]
            if counter_requested or any(counters_observed):
                verdicts.append(
                    FieldVerdict(
                        field=f"battlefield.{placement.get('semantic_id')}.counters",
                        verdict=_group_field_verdict(
                            [
                                dict(Counter(_canonical_counters(member.get("counters") or {})))
                                for member in group
                            ],
                            counters_observed,
                        ),
                        requested=dict(counter_requested),
                        observed=(
                            counters_observed[0]
                            if len(counters_observed) == 1
                            else counters_observed
                        ),
                    )
                )

    # hands, observed through each seat's own principal-scoped view
    for player_id, expected_cards in model.hands_by_player.items():
        observation = seat_observations.get(player_id)
        state = _state_view(observation) if observation else {}
        rows = _players_by_id(state)
        row = rows.get(player_id, {})
        zones = row.get("zones") if isinstance(row, dict) else {}
        hand = zones.get("hand") if isinstance(zones, dict) else None
        hand = hand if isinstance(hand, list) else []
        verdicts.append(
            FieldVerdict(
                field=f"hands.{player_id}",
                verdict=(
                    CHECKPOINT_EXACT
                    if Counter(expected_cards) == Counter(str(card) for card in hand)
                    else CHECKPOINT_MISMATCH
                ),
                requested=sorted(expected_cards),
                observed=sorted(str(card) for card in hand),
            )
        )

    unsupported = [item.dimension for item in model.hard_unsupported]
    unobservable = [item.dimension for item in model.unobservable]
    mismatches = [item for item in verdicts if item.verdict == CHECKPOINT_MISMATCH]
    unknown_fields = [item for item in verdicts if item.verdict == CHECKPOINT_UNKNOWN]
    cause_advances = [item for item in verdicts if item.verdict == "CAUSE_ADVANCE"]
    variance_source: str | None = None
    if unsupported:
        verdict = CHECKPOINT_UNSUPPORTED_DIMENSION
    elif mismatches:
        verdict = CHECKPOINT_MISMATCH
    elif unknown_fields:
        verdict = CHECKPOINT_UNKNOWN
    elif unobservable:
        verdict = CHECKPOINT_UNSUPPORTED_DIMENSION
    elif cause_advances:
        verdict = CHECKPOINT_ALLOWED_VARIANCE
        variance_source = (
            "fixture.native_procedure NATIVE_CAUSE_DECLARED_PLAYER_LOSS + declared "
            "terminal_postconditions; the cause transition is declared by the frozen "
            "fixture, not invented by this lane"
        )
    else:
        verdict = CHECKPOINT_EXACT
    return CheckpointEquivalence(
        verdict=verdict,
        fields=verdicts,
        unsupported_dimensions=unsupported,
        unobservable_dimensions=unobservable,
        variance_source=variance_source,
    )


# ---------------------------------------------------------------------------
# Engine-authored decision driving
# ---------------------------------------------------------------------------
@dataclass
class ScenarioDriveResult:
    game_id: str
    decision_tape: list[DecisionTapeEntry] = field(default_factory=list)
    semantic_events: list[str] = field(default_factory=list)
    terminal_facts: dict[str, Any] = field(default_factory=dict)
    steps_completed: list[str] = field(default_factory=list)
    failure: str | None = None
    failure_kind: str | None = None
    checkpoint: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "steps_completed": self.steps_completed,
            "failure": self.failure,
            "failure_kind": self.failure_kind,
            "checkpoint": self.checkpoint,
            "decision_tape": [
                {
                    "step": entry.step,
                    "kind": entry.kind,
                    "actor": entry.actor,
                    "revision": entry.revision,
                    "policy": entry.policy,
                    "chosen_option_id": entry.chosen_option_id,
                    "offered_option_ids": entry.offered_option_ids,
                    "note": entry.note,
                }
                for entry in self.decision_tape
            ],
            "semantic_events": self.semantic_events,
            "terminal_facts": self.terminal_facts,
        }


def _temporal_matches(state: dict[str, Any], requested: dict[str, Any]) -> bool:
    if not requested:
        return True
    for key, expected in requested.items():
        if expected is None:
            continue
        if key == "phase":
            observed = _normalize_phase(state.get("phase"))
        elif key == "step":
            observed = _normalize_step(state.get("step"))
        elif key == "active_player":
            observed = (
                str(state.get("active_player_id")).lower()
                if state.get("active_player_id")
                else None
            )
        elif key == "priority_player":
            observed = (
                str(state.get("priority_player_id")).lower()
                if state.get("priority_player_id")
                else None
            )
        else:
            observed = state.get(key)
        if observed != expected:
            return False
    return True


def progression_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """The engine's turn position and per-player hand and library counts.

    Counts only: the observer's own hand names and every other principal's
    hidden cards stay out of the snapshot.
    """
    players = {}
    for player_id, row in sorted(_players_by_id(state).items()):
        zones = row.get("zones") or {}
        hand = zones.get("hand")
        players[player_id] = {
            "hand": len(hand) if isinstance(hand, list) else None,
            "library_size": zones.get("library_size"),
        }
    return {
        "turn_number": state.get("turn_number"),
        "active_player": str(state.get("active_player_id") or "").lower() or None,
        "phase": _normalize_phase(state.get("phase")),
        "step": _normalize_step(state.get("step")),
        "priority_player": str(state.get("priority_player_id") or "").lower() or None,
        "players": players,
    }


def drive_scenario_game(
    proc: BridgeProcess,
    model: RequestedStateModel,
    *,
    seed: int,
    max_steps: int = 400,
    stop_at_requested_checkpoint: bool = True,
) -> ScenarioDriveResult:
    """Create/start the scenario game and drive it with engine-authored choices only.

    Decision policy (mirrors the current-boundary driver, never a default):

    * MULLIGAN -> keep (declared policy; engine-offered option)
    * STARTING_PLAYER -> the record's explicit declaration (scripted
      starting-player step, explicit field, or the requested state's own active
      player as setup) submitted through the engine-offered frame; a record
      without one fails closed, never p1 (#572)
    * PRIORITY -> pass (the requested checkpoint is reached by native progression)
    * ORDER_CHOICE -> the provider-published native CostPart order
    * any other decision class -> record the offered domain and stop fail closed
    """
    players = model.player_count or 2
    seats = SEATS[:players]
    if players < 2 or players > 6:
        raise ScenarioLaneError(f"unsupported player count {players}")
    # The record's explicit starting-seat declaration (scripted step, explicit
    # field, or the requested state's own active player as setup); no default.
    declared_starting_seat, declared_starting_source = scenario_setup_starting_seat(model)
    result = ScenarioDriveResult(game_id=f"fsl-{model.fixture_id.lower()}-{uuid.uuid4().hex[:8]}")
    game_id = result.game_id
    result.terminal_facts["starting_player_declaration"] = (
        {"seat": declared_starting_seat, "source": declared_starting_source}
        if declared_starting_seat is not None
        else None
    )
    created_request: dict[str, Any] = {
        "game_id": game_id,
        "deck_handles": [],
        "format": "commander",
        "external_control": True,
        "seed": seed,
        "rules_seed": seed,
        "scenario": {"neutral_initial_state": model.neutral_initial_state},
    }

    try:
        for message in ("start_engine", "get_provider_version", "get_capabilities"):
            response = proc.request(message, {}, timeout_s=300.0)
            if response.get("success") is not True:
                raise GameDriveError(f"{message} failed: {response.get('errors')}")
        result.steps_completed.append("handshake")

        handles: list[str] = []
        deck_plan = _deck_plan(model)
        for seat in seats:
            commanders = deck_plan.get(seat) or ["Rograkh, Son of Rohgahh"]
            deck = build_commander_deck(f"fsl-{game_id}-{seat}", commanders)
            payload = _payload(proc.request("import_deck", {"deck": deck}, timeout_s=300.0))
            handle = payload.get("deck_handle")
            handle_id = handle.get("handle_id") if isinstance(handle, dict) else None
            if not handle_id:
                raise GameDriveError(f"import_deck returned no handle for {seat}: {payload}")
            handles.append(str(handle_id))
        created_request["deck_handles"] = handles
        result.steps_completed.append("import_deck")

        created = proc.request(
            "create_commander_game",
            {"request": created_request},
            game_id=game_id,
            timeout_s=300.0,
        )
        result.terminal_facts["create_response"] = created
        if created.get("success") is not True:
            result.failure = f"create_commander_game rejected: {created.get('errors')}"
            result.failure_kind = "ENGINE_REJECTED_SCENARIO"
            return result
        result.steps_completed.append("create_commander_game")

        started = proc.request("start_game", {}, game_id=game_id, timeout_s=300.0)
        if started.get("success") is not True:
            raise GameDriveError(f"start_game failed: {started.get('errors')}")
        result.steps_completed.append("start_game")

        checkpoint_reached = False
        steps = 0
        while steps < max_steps:
            steps += 1
            frame = poll_decision(proc, game_id, seat_count=players, candidate="forge")
            decision = frame["decision"]
            kind = str(decision.get("kind", "")).upper()
            actor = str(decision.get("actor", frame["seat"]))
            revision = decision.get("revision")
            actions = frame["actions"]
            offered = [
                str(action.get("action_id")) for action in actions if action.get("action_id")
            ]

            if kind in {"MULLIGAN", "KEEP_OR_MULLIGAN"}:
                response = proc.request(
                    "resolve_mulligan",
                    {
                        "player_id": actor,
                        **decision_identity_params("forge", frame),
                        "keep": True,
                        "bottom_card_ids": [],
                    },
                    game_id=game_id,
                    timeout_s=120.0,
                )
                if response.get("success") is not True:
                    raise GameDriveError(f"resolve_mulligan failed: {response.get('errors')}")
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "mulligan",
                        kind,
                        actor,
                        revision,
                        "keep_all",
                        None,
                        offered,
                        "external keep; no bottoming",
                    )
                )
                continue

            if kind in {"STARTING_PLAYER", "CHOOSE_STARTING_PLAYER"}:
                # The scenario lane never picks the starter itself: the seat must
                # be declared by the record (scripted step or explicit field), or
                # by the requested state's own active player as a setup answer.
                # The p1 fallback that used to live here was the defect (#572).
                if declared_starting_seat is None:
                    raise DecisionUnsatisfied(
                        "the engine offered a STARTING_PLAYER decision and the scenario "
                        "record declares no starting seat; the Lab never chooses the "
                        "starting player"
                    )
                wanted = declared_starting_seat
                options = [
                    action
                    for action in actions
                    if action.get("action_type") == "structural_decision"
                    and str(action.get("source_object_id", "")).strip().lower() == wanted
                ]
                if len(options) != 1:
                    raise DecisionUnsatisfied(
                        f"engine offered {len(options)} starting-player options for "
                        f"{wanted!r}; require exactly one, offered "
                        f"{[a.get('source_object_id') for a in actions]}"
                    )
                [chosen_action] = options
                chosen = str(chosen_action["action_id"])
                # A scripted starting-player decision is the only basis that can
                # earn a starting-player obligation (STARTING_PLAYER_AUTHORIZED_
                # BASIS); a setup answer from the requested state is recorded with
                # its own basis and earns no such credit.
                scripted_starter = declared_starting_source == STARTER_DECLARATION_SCRIPT
                result.terminal_facts["starting_player_choice"] = {
                    "chooser": actor,
                    "revision": revision,
                    "chosen_seat": wanted,
                    "offered_seats": sorted(
                        str(action.get("source_object_id"))
                        for action in actions
                        if action.get("action_type") == "structural_decision"
                    ),
                    "policy": (
                        "fixture_decision_script" if scripted_starter else "record_declared_setup"
                    ),
                    "basis": (
                        STARTING_PLAYER_AUTHORIZED_BASIS
                        if scripted_starter
                        else "LAB_SELECTED_ENGINE_OFFERED"
                    ),
                    "declared_source": declared_starting_source,
                }
                response = proc.request(
                    "submit_action",
                    {
                        **decision_identity_params("forge", frame),
                        "proposal": {
                            "proposal_id": str(uuid.uuid4()),
                            "actor_id": actor,
                            "legal_action_id": chosen,
                            "action_type": "structural_decision",
                        },
                    },
                    game_id=game_id,
                    timeout_s=120.0,
                )
                if response.get("success") is not True:
                    raise GameDriveError(
                        f"submit_action(STARTING_PLAYER) failed: {response.get('errors')}"
                    )
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "starting_player",
                        kind,
                        actor,
                        revision,
                        "requested_starting_seat",
                        chosen,
                        offered,
                        f"engine-offered seat {wanted}",
                    )
                )
                continue

            if kind == "ORDER_CHOICE":
                chosen_action = select_cost_order_action(actions)
                chosen = str(chosen_action["action_id"])
                response = proc.request(
                    "submit_action",
                    {
                        **decision_identity_params("forge", frame),
                        "proposal": {
                            "proposal_id": str(uuid.uuid4()),
                            "actor_id": actor,
                            "legal_action_id": chosen,
                            "action_type": str(chosen_action.get("action_type")),
                        },
                    },
                    game_id=game_id,
                    timeout_s=120.0,
                )
                if response.get("success") is not True:
                    raise GameDriveError(
                        f"submit_action(ORDER_CHOICE) failed: {response.get('errors')}"
                    )
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "cost_order",
                        kind,
                        actor,
                        revision,
                        "native_declared_cost_part_order",
                        chosen,
                        offered,
                        "provider-published native CostPart order",
                    )
                )
                continue

            if kind == "PRIORITY":
                pass_actions = [
                    action for action in actions if action.get("action_type") == "pass_priority"
                ]
                if len(pass_actions) != 1:
                    raise DecisionUnsatisfied(
                        f"PRIORITY offered {len(pass_actions)} pass_priority options; "
                        "require exactly one"
                    )
                [pass_action] = pass_actions
                chosen = str(pass_action["action_id"])
                response = proc.request(
                    "pass_priority",
                    decision_identity_params("forge", frame),
                    game_id=game_id,
                    timeout_s=120.0,
                )
                if response.get("success") is not True:
                    raise GameDriveError(f"pass_priority failed: {response.get('errors')}")
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "priority",
                        kind,
                        actor,
                        revision,
                        "pass_when_offered",
                        chosen,
                        offered,
                        "external priority pass",
                    )
                )
                target = effective_temporal_target(model)
                if stop_at_requested_checkpoint and target:
                    checkpoint_response = observe_seat_state(proc, game_id, seats[0])
                    state = _state_view(checkpoint_response)
                    snapshot = progression_snapshot(state)
                    progression = result.terminal_facts.setdefault("progression", [])
                    if not progression or progression[-1] != snapshot:
                        progression.append(snapshot)
                    if _temporal_matches(state, target):
                        checkpoint_reached = True
                        result.checkpoint = "REQUESTED_TEMPORAL_STATE"
                        break
                continue

            result.decision_tape.append(
                DecisionTapeEntry(
                    "other_decision_class",
                    kind,
                    actor,
                    revision,
                    "NO_MATCHING_OFFERED_OPTION",
                    None,
                    offered,
                    "unsupported decision class for this lane; fail closed",
                )
            )
            result.terminal_facts["stopped_at_decision_kind"] = kind
            result.failure = f"stopped at unsupported engine decision class {kind}"
            result.failure_kind = "FAIL_CLOSED_UNSATISFIED"
            return result

        if checkpoint_reached:
            result.steps_completed.append("checkpoint_reached")
        else:
            # Even without a declared temporal checkpoint, the first priority
            # frame is a legitimate observable checkpoint.
            result.checkpoint = result.checkpoint or "FIRST_PRIORITY"
        result.terminal_facts["provider_seed_supported"] = True
    except (GameDriveError, DecisionUnsatisfied, BridgeLaunchError) as exc:
        result.failure = f"{type(exc).__name__}: {exc}"
        result.failure_kind = (
            "FAIL_CLOSED_UNSATISFIED"
            if isinstance(exc, DecisionUnsatisfied)
            else "ENGINE_RUNTIME_ERROR"
        )
    return result


# ---------------------------------------------------------------------------
# Obligation evaluation
# ---------------------------------------------------------------------------
@dataclass
class ObligationVerdict:
    kind: str
    observed: bool
    credit_eligible_observation: bool
    terminal_facts: dict[str, Any]
    semantic_events: list[str]
    reason: str

    def to_document(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "observed": self.observed,
            "credit_eligible_observation": self.credit_eligible_observation,
            "terminal_facts": self.terminal_facts,
            "semantic_events": self.semantic_events,
            "reason": self.reason,
        }


def _obligation_kind(model: RequestedStateModel) -> str | None:
    """Map a fixture's declared obligation to a lane observation contract.

    The mapping keys off the fixture's own required events first and its
    declared terminal postconditions second. It never derives an obligation
    from card text or from a provider observation.
    """
    if model.causal_plan is not None:
        # Only a routable record has a plan (``lane_causal_plan``); its terminal
        # is judged from the route's readback and decision tape by that
        # terminal's observer contract (``_CAUSAL_TERMINAL_CONTRACTS``).
        return causal_terminal(model)
    required = [
        str(event)
        for event in (model.record.get("expected_events") or {}).get("required_events") or []
    ]
    postconditions = " ".join(
        str(item) for item in (model.record.get("terminal_postconditions") or [])
    ).lower()
    if any(event.startswith("commander_damage_checked_per_commander") for event in required):
        return "commander_damage_checked_per_commander"
    if ("commander damage" in postconditions or "partner commanders" in postconditions) and (
        "21" in postconditions
    ):
        return "commander_damage_checked_per_commander"
    if any(event.startswith("game_start_command_zone:") for event in required):
        return "game_start_command_zone"
    if "command zone" in postconditions and "partner" in postconditions:
        return "game_start_command_zone"
    if any(event.startswith("player_leaves:") for event in required):
        return "player_leaves_multiplayer_cleanup"
    if any(event.startswith("first_turn_draw:") for event in required) and any(
        event.startswith("starting_player:") for event in required
    ):
        return "starting_player_first_turn_draw"
    if "leave the game" in postconditions or "leaves the game" in postconditions:
        return "player_leaves_multiplayer_cleanup"
    return None


def _required_token(required: list[Any], prefix: str) -> str | None:
    values = [str(event)[len(prefix) :] for event in required if str(event).startswith(prefix)]
    return values[0] if len(values) == 1 else None


def evaluate_first_turn_draw(
    required: list[Any],
    progression: list[dict[str, Any]],
    starting_choice: dict[str, Any] | None = None,
) -> ObligationVerdict:
    """CR 103.8: the starting player's first draw step, from the engine's own counts.

    The evidence is the engine-reported change across the starting player's
    turn-1 draw step: the last snapshot of that turn before the draw step and
    the first one in it. The starting player draws one card (hand +1, library
    -1) exactly when ``first_turn_draw`` is true (CR 103.8a skips it only in a
    two-player game); every other player's counts must not change. A missing
    snapshot on either side fails closed.

    The starter itself is not an engine observation: the Lab selects it among
    the seats the engine's starting-player frame offers. The verdict requires
    that recorded selection, names its basis, and checks only that the engine
    then started that seat's turn.
    """
    starter_token = _required_token(required, "starting_player:")
    draw_token = _required_token(required, "first_turn_draw:")
    facts: dict[str, Any] = {"starting_player": starter_token, "first_turn_draw": draw_token}

    def verdict(observed: bool, reason: str) -> ObligationVerdict:
        return ObligationVerdict(
            kind="starting_player_first_turn_draw",
            observed=observed,
            credit_eligible_observation=observed,
            terminal_facts=facts,
            semantic_events=(
                [f"starting_player:{starter_token}", f"first_turn_draw:{draw_token}"]
                if observed
                else []
            ),
            reason=reason,
        )

    if starter_token is None or draw_token not in {"true", "false"}:
        return verdict(False, "the record does not name exactly one starter and draw value")
    starter = starter_token.lower()
    facts["starting_player_choice"] = starting_choice
    if (
        not starting_choice
        or starting_choice.get("chosen_seat") != starter
        or starter not in (starting_choice.get("offered_seats") or [])
    ):
        return verdict(False, "no recorded engine-offered starting-player selection of the starter")
    facts["starting_player_basis"] = starting_choice.get("basis")
    if starting_choice.get("basis") != STARTING_PLAYER_AUTHORIZED_BASIS:
        return verdict(
            False,
            "the starter was selected without contract authority "
            f"({starting_choice.get('basis')}); only a scripted starting-player response "
            f"({STARTING_PLAYER_AUTHORIZED_BASIS}) may decide it",
        )
    turn_one = [snap for snap in progression if snap.get("turn_number") == 1]
    draw_index = next(
        (index for index, snap in enumerate(turn_one) if snap.get("step") == "draw"), None
    )
    if draw_index is None or draw_index == 0:
        facts["turn_one_snapshots"] = turn_one
        return verdict(False, "no engine snapshot on both sides of the turn-1 draw step")
    before, after = turn_one[draw_index - 1], turn_one[draw_index]
    facts["before_draw_step"] = before
    facts["in_draw_step"] = after
    if before.get("active_player") != starter or after.get("active_player") != starter:
        return verdict(False, "the engine's turn-1 active player is not the requested starter")
    if before.get("phase") != "beginning" or after.get("priority_player") != starter:
        return verdict(
            False, "the snapshots do not bracket the starter's draw step in the beginning phase"
        )
    if set(before.get("players") or {}) != set(after.get("players") or {}):
        return verdict(False, "the player set changed across the draw step")
    expected = 1 if draw_token == "true" else 0
    deltas = {}
    for player_id, counts in sorted((after.get("players") or {}).items()):
        prior = before["players"][player_id]
        if None in (
            counts.get("hand"),
            counts.get("library_size"),
            prior.get("hand"),
            prior.get("library_size"),
        ):
            return verdict(False, f"{player_id}'s hand or library count is not observable")
        deltas[player_id] = {
            "hand": counts["hand"] - prior["hand"],
            "library": counts["library_size"] - prior["library_size"],
        }
    facts["deltas"] = deltas
    wanted = {
        player_id: (
            {"hand": expected, "library": -expected}
            if player_id == starter
            else {"hand": 0, "library": 0}
        )
        for player_id in deltas
    }
    facts["expected_deltas"] = wanted
    if deltas != wanted:
        return verdict(False, "the engine's draw-step counts do not match the obligation")
    return verdict(
        True,
        "the engine's counts across the starting player's turn-1 draw step match "
        f"first_turn_draw:{draw_token} for starter {starter}, and no other player's counts "
        "changed; the starter was decided by the record's scripted response among the "
        "engine-offered seats, and the engine started that seat's turn",
    )


def evaluate_obligation(
    model: RequestedStateModel,
    seat_observations: dict[str, dict[str, Any]],
    progression: list[dict[str, Any]] | None = None,
    starting_choice: dict[str, Any] | None = None,
) -> ObligationVerdict:
    """Evaluate the fixture obligation from engine-reported facts only."""
    required = list((model.record.get("expected_events") or {}).get("required_events") or [])
    if not seat_observations:
        return ObligationVerdict("NONE", False, False, {}, [], "no engine observation available")
    primary = _state_view(next(iter(seat_observations.values())))
    players = _players_by_id(primary)
    terminal_outcomes = primary.get("terminal_outcomes") or []
    kind = _obligation_kind(model)

    if kind == "starting_player_first_turn_draw":
        return evaluate_first_turn_draw(required, progression or [], starting_choice)

    if kind == "commander_zone_choice":
        return ObligationVerdict(
            kind,
            False,
            False,
            {"required_events": required},
            [],
            "a commander zone choice is judged only from the causal route's engine facts",
        )

    if kind == "commander_damage_checked_per_commander":
        facts: dict[str, Any] = {}
        loss_free = True
        for player_id, _damage in model.commander_damage_by_player.items():
            row = players.get(player_id, {})
            observed_map = row.get("commander_damage_received") or {}
            facts[f"{player_id}.commander_damage_received"] = observed_map
            facts[f"{player_id}.life"] = row.get("life")
            per_commander_ge_21 = sorted(
                name for name, amount in observed_map.items() if int(amount) >= 21
            )
            facts[f"{player_id}.commanders_at_or_above_21"] = per_commander_ge_21
            aggregate = sum(int(amount) for amount in observed_map.values())
            facts[f"{player_id}.aggregate_commander_damage"] = aggregate
            if isinstance(row, dict) and row.get("has_lost"):
                loss_free = False
            outcome = next(
                (
                    entry
                    for entry in terminal_outcomes
                    if isinstance(entry, dict)
                    and str(entry.get("player_id", "")).lower() == player_id
                ),
                None,
            )
            if outcome is not None and outcome.get("lost"):
                loss_free = False
        aggregate_over_21 = any(
            facts.get(f"{player}.aggregate_commander_damage", 0) >= 21
            for player in model.commander_damage_by_player
        )
        observed_expected = any(
            facts.get(f"{player}.aggregate_commander_damage", 0) >= 21
            for player in model.commander_damage_by_player
        )
        semantic = [
            f"commander_damage_per_commander_evaluated:{player}"
            for player in sorted(model.commander_damage_by_player)
        ]
        return ObligationVerdict(
            kind="commander_damage_checked_per_commander",
            observed=bool(aggregate_over_21 and loss_free),
            credit_eligible_observation=bool(observed_expected and loss_free),
            terminal_facts={
                **facts,
                "declared_rule": "CR 903.10a: a player loses only if one commander dealt >= 21",
                "no_single_commander_at_or_above_21": loss_free,
            },
            semantic_events=semantic,
            reason=(
                "engine per-commander damage map observed with no per-commander value >= 21 "
                "while aggregate is >= 21; the engine did not apply a loss"
                if loss_free and aggregate_over_21
                else "the per-commander loss condition or damage readback did not match the obligation"
            ),
        )

    if kind == "game_start_command_zone":
        facts = {}
        all_present = True
        for entry in model.command_zone:
            owner = str(entry.get("owner") or "").lower()
            row = players.get(owner, {})
            command = (row.get("zones") or {}).get("command") or []
            present = entry.get("card_identity") in command
            facts[f"{entry.get('commander_id')}"] = {
                "owner": owner,
                "card": entry.get("card_identity"),
                "observed_command_zone": command,
                "present": present,
            }
            all_present = all_present and present
        semantic = [
            f"game_start_command_zone:{entry.get('commander_id')}"
            for entry in model.command_zone
            if str(
                (players.get(str(entry.get("owner") or "").lower(), {}).get("zones") or {}).get(
                    "command"
                )
                or []
            )
        ]
        return ObligationVerdict(
            kind="game_start_command_zone",
            observed=all_present,
            credit_eligible_observation=all_present,
            terminal_facts=facts,
            semantic_events=semantic,
            reason=(
                "both partner commander identities observed in the command zone at the "
                "first observable checkpoint"
                if all_present
                else "a requested commander identity was not observed in its command zone"
            ),
        )

    if kind == "player_leaves_multiplayer_cleanup":
        facts = {}
        all_cleanup = True
        expected_losers = [
            player_id for player_id, life in model.life_by_player.items() if life <= 0
        ]
        for player_id in expected_losers:
            row = players.get(player_id, {})
            outcome = next(
                (
                    entry
                    for entry in terminal_outcomes
                    if isinstance(entry, dict)
                    and str(entry.get("player_id", "")).lower() == player_id
                ),
                None,
            )
            lost = bool(row.get("has_lost")) or bool(outcome and outcome.get("lost"))
            facts[f"{player_id}.lost"] = lost
            facts[f"{player_id}.life"] = row.get("life")
            facts[f"{player_id}.terminal_outcome"] = outcome
            if not lost:
                all_cleanup = False
            controlled_present = (row.get("zones") or {}).get("battlefield") or []
            facts[f"{player_id}.battlefield_after_loss"] = controlled_present
            if controlled_present:
                all_cleanup = False
        live_players = sorted(
            str(entry.get("player_id")).lower()
            for entry in terminal_outcomes
            if isinstance(entry, dict) and not entry.get("lost") and not entry.get("left")
        )
        facts["live_players"] = live_players
        semantic = [f"player_leaves:{player}" for player in expected_losers]
        return ObligationVerdict(
            kind="player_leaves_multiplayer_cleanup",
            observed=all_cleanup,
            credit_eligible_observation=all_cleanup,
            terminal_facts=facts,
            semantic_events=semantic,
            reason=(
                "the declared zero-life seat is lost and its controlled permanents left the "
                "game, and the live-player ring excludes it"
                if all_cleanup
                else "the declared loss or the multiplayer cleanup was not fully observed"
            ),
        )

    return ObligationVerdict(
        kind="UNSUPPORTED_OBLIGATION_FAMILY",
        observed=False,
        credit_eligible_observation=False,
        terminal_facts={"required_events": required},
        semantic_events=[],
        reason=(
            "this lane has no observation contract for the obligation's required events; "
            "construction alone earns no credit"
        ),
    )


_READBACK_ZONES = ("battlefield", "graveyard", "exile", "command", "hand")


def _named_zones(state: dict[str, Any], owner: str, name: str) -> list[str]:
    """Every zone of the owner's own view holding a card of this name, once per card."""
    zones = (_players_by_id(state).get(owner) or {}).get("zones") or {}
    return [zone for zone in _READBACK_ZONES for card in zones.get(zone) or () if card == name]


def _route_commander(model: RequestedStateModel) -> dict[str, Any] | None:
    plan = model.causal_plan
    if plan is None:
        return None
    objects = {
        str(entry.get("semantic_id")): entry
        for entry in model.record.get("semantic_objects") or ()
        if isinstance(entry, dict)
    }
    commanders = [
        objects[target]
        for spell in plan.spells
        for target in spell.targets
        if target in objects and objects[target].get("commander_id")
    ]
    return commanders[0] if len(commanders) == 1 else None


def _route_answer_frames(model: RequestedStateModel) -> frozenset[str]:
    """The only engine frame kind the record's scripted answer may be given on."""
    required = list((model.record.get("expected_events") or {}).get("required_events") or [])
    zone = _required_token(required, "commander_zone_event:")
    frame = _COMMANDER_EVENT_FRAMES.get(zone or "")
    return frozenset({frame}) if frame else frozenset()


def _requested_checkpoint_facts(
    model: RequestedStateModel, run: fcr.CausalRun, spell_card: str, target_card_id: str | None
) -> dict[str, Any]:
    """The record's checkpoint compared with the engine snapshot the route captured."""
    snapshot = next(
        (snap["state"] for snap in run.snapshots if snap["at"] == "requested_checkpoint"), None
    )
    requested = model.temporal_state
    if snapshot is None:
        return {"verdict": CHECKPOINT_MISMATCH, "reason": "no requested-checkpoint snapshot"}
    stack = [str(entry) for entry in snapshot.get("stack") or ()]
    fields = {
        "stack_size": (len(stack), len(model.causal_plan.spells) if model.causal_plan else None),
        "stack_spell": (stack[0].split(" (")[0] if stack else None, spell_card),
        "stack_target_card_id": (
            bool(stack) and target_card_id is not None and f"({target_card_id})" in stack[0],
            True,
        ),
        "active_player": (
            str(snapshot.get("active_player_id") or "").lower(),
            str(requested.get("active_player") or "").lower(),
        ),
        "priority_player": (
            str(snapshot.get("priority_player_id") or "").lower(),
            str(requested.get("priority_player") or "").lower(),
        ),
        "phase": (_normalize_phase(snapshot.get("phase")), requested.get("phase")),
        "step": (_normalize_step(snapshot.get("step")), requested.get("step")),
        "turn_number": (snapshot.get("turn_number"), requested.get("turn_number")),
    }
    mismatched = sorted(name for name, (seen, wanted) in fields.items() if seen != wanted)
    return {
        "verdict": CHECKPOINT_EXACT if not mismatched else CHECKPOINT_MISMATCH,
        "fields": {
            name: {"observed": seen, "requested": wanted} for name, (seen, wanted) in fields.items()
        },
        "mismatched": mismatched,
    }


def evaluate_commander_zone_choice(
    model: RequestedStateModel, run: fcr.CausalRun
) -> ObligationVerdict:
    """CR 903.9 from the causal route's engine readback and decision tape only.

    The commander is identified by name inside its owner's own view; the check
    requires that name to be held by exactly one card across the owner's
    readable zones at every snapshot, so the name cannot stand for two objects.
    ``commander_zone_event:<zone>`` is the engine's move to the graveyard or
    exile observed before the owner's COMMANDER_MOVE answer (CR 903.9a), or,
    for the hand, the engine's REPLACEMENT_CONFIRM asked while the commander is
    still on the battlefield (CR 903.9b). ``commander_choice:<zone>`` is the
    scripted answer on that frame and the commander's settled zone.
    """
    kind = "commander_zone_choice"
    required = list((model.record.get("expected_events") or {}).get("required_events") or [])
    event_zone = _required_token(required, "commander_zone_event:")
    choice = _required_token(required, "commander_choice:")
    commander = _route_commander(model)
    plan = model.causal_plan
    facts: dict[str, Any] = {
        "causal_route": run.to_document(),
        "commander_zone_event": event_zone,
        "commander_choice": choice,
    }
    if run.failure:
        return ObligationVerdict(kind, False, False, facts, [], f"causal route: {run.failure}")
    if (
        plan is None
        or commander is None
        or event_zone not in _COMMANDER_EVENT_FRAMES
        or choice not in ("command", event_zone)
    ):
        return ObligationVerdict(
            kind, False, False, facts, [], "the record's commander zone obligation is not routable"
        )
    owner = str(commander.get("owner") or "").lower()
    name = str(commander.get("card_identity") or "")
    spell = plan.spells[0]
    snapshots = {snapshot["at"]: snapshot["state"] for snapshot in run.snapshots}
    zones_at = {at: _named_zones(state, owner, name) for at, state in snapshots.items()}
    facts["commander"] = {"semantic_id": commander.get("semantic_id"), "owner": owner, "name": name}
    facts["commander_zones"] = zones_at

    casts = [frame for frame in run.frames if frame.reason == f"causal cast {spell.semantic_id}"]
    target_refs = [
        (ref.get("kind"), ref.get("name"), str(ref.get("controller") or "").lower())
        for frame in run.frames
        if frame.reason == "causal target"
        for ref in frame.refs
    ]
    target_frames = sum(1 for frame in run.frames if frame.reason == "causal target")
    target_card_ids = [
        str(ref.get("card_id"))
        for frame in run.frames
        if frame.reason == "causal target"
        for ref in frame.refs
        if ref.get("card_id") is not None
    ]
    requested_checkpoint = _requested_checkpoint_facts(
        model, run, spell.card, target_card_ids[0] if len(target_card_ids) == 1 else None
    )
    facts["requested_checkpoint"] = requested_checkpoint
    answers = run.scripted_answers
    wanted_answer = choice == "command"
    settled_zone = "command" if wanted_answer else event_zone
    before = zones_at.get("before_scripted_0")
    checks = {
        "stack_caused": (
            run.stack_after_cast is not None
            and len(run.stack_after_cast) == 1
            and str(run.stack_after_cast[0]).startswith(f"{spell.card} (")
        ),
        "cast_by_declared_controller": len(casts) == 1
        and casts[0].actor.lower() == spell.controller,
        "target_is_the_commander": target_frames == 1 and target_refs == [("card", name, owner)],
        "one_scripted_answer_on_the_rule_frame": len(answers) == 1
        and answers[0].get("frame_kind") == _COMMANDER_EVENT_FRAMES[event_zone]
        and answers[0].get("boolean") is wanted_answer,
        "name_identifies_one_card": bool(zones_at)
        and all(len(zones) == 1 for zones in zones_at.values()),
        "commander_zone_event": before
        == (["battlefield"] if event_zone == "hand" else [event_zone]),
        "commander_choice": zones_at.get("settled") == [settled_zone],
        "requested_checkpoint": requested_checkpoint["verdict"] == CHECKPOINT_EXACT
        and zones_at.get("requested_checkpoint") == ["battlefield"],
    }
    facts["checks"] = checks
    observed = all(checks.values())
    events = (
        [f"commander_zone_event:{event_zone}", f"commander_choice:{choice}"] if observed else []
    )
    reason = (
        f"the engine moved the commander per CR 903.9 ({event_zone}) and the owner's scripted "
        f"{'yes' if wanted_answer else 'no'} left it in the {settled_zone} zone"
        if observed
        else "not observed: " + ", ".join(check for check, ok in checks.items() if not ok)
    )
    return ObligationVerdict(kind, observed, observed, facts, events, reason)


# ---------------------------------------------------------------------------
# Observer contract: a scripted decision on the caused stack
# ---------------------------------------------------------------------------
# Obligation-token families the scripted-decision contract cannot judge from the
# pinned Forge readback and the route's tape. Each stays unobserved with its
# reason; it is never inferred from card text or from rules knowledge.
SCRIPTED_TOKEN_UNOBSERVABLE: dict[str, str] = {
    "resolve": (
        "the readback shows a spell leaving the stack, not whether it resolved, was "
        "countered or was removed for illegal targets (CR 608.2b); the pinned bridge "
        "projects no marked damage and exports no event log"
    ),
}


def _scripted_token(token: str) -> tuple[str, str]:
    """A required token's family and argument (``Counterspell_cast`` is a cast)."""
    text = str(token)
    if ":" in text:
        family, argument = text.split(":", 1)
        return family, argument
    if text.endswith("_cast"):
        return "spell_cast", text[: -len("_cast")]
    return text, ""


def scripted_token_observable(token: str) -> bool:
    """Whether the scripted-decision contract has an observer for this token."""
    return _scripted_token(token)[0] in _SCRIPTED_TOKEN_OBSERVERS


def _card(argument: str) -> str:
    return argument.replace("_", " ")


@dataclass
class _ScriptedCast:
    """One scripted cast as the tape and the readback show it."""

    document: dict[str, Any]
    frame: fcr.RouteFrame
    payments: list[fcr.RouteFrame]
    before: dict[str, Any] | None
    complete: dict[str, Any] | None


def _scripted_casts(run: fcr.CausalRun) -> list[_ScriptedCast]:
    snapshots = {snapshot["at"]: snapshot["state"] for snapshot in run.snapshots}
    frames = [
        (index, frame)
        for index, frame in enumerate(run.frames)
        if frame.reason == "scripted step" and frame.kind == "PRIORITY"
    ]
    if len(frames) != len(run.scripted_casts):
        return []
    casts: list[_ScriptedCast] = []
    for number, ((index, frame), document) in enumerate(
        zip(frames, run.scripted_casts, strict=True)
    ):
        payments: list[fcr.RouteFrame] = []
        for later in run.frames[index + 1 :]:
            if later.kind == "PRIORITY":
                break
            if later.reason.startswith("declared payment "):
                payments.append(later)
        casts.append(
            _ScriptedCast(
                document=document,
                frame=frame,
                payments=payments,
                before=snapshots.get(f"before_scripted_{number}"),
                complete=snapshots.get(f"cast_complete:{document['source_semantic_id']}"),
            )
        )
    return casts


def _named_tapped(state: dict[str, Any] | None, player: str, name: str) -> int | None:
    if state is None:
        return None
    zones = (_players_by_id(state).get(player) or {}).get("zones") or {}
    return sum(
        1
        for card in zones.get("battlefield_details") or ()
        if isinstance(card, dict) and card.get("name") == name and card.get("tapped") is True
    )


def _payment_bound(model: RequestedStateModel, cast: _ScriptedCast) -> tuple[bool, str]:
    """Every payment is an engine-offered tap of one declared source of this cast.

    The tape's chosen option id must be one the engine offered on that frame,
    its offered label must be the recorded choice, and its source must be the
    declared source the route bound; each declared source pays once. The
    readback must show exactly that many more of those sources tapped.
    """
    objects = ss.semantic_objects(model.record)
    declared = list(cast.document.get("declared_payment_sources") or ())
    seen: list[str] = []
    for frame in cast.payments:
        if frame.chosen_option_id not in frame.offered_option_ids:
            return False, f"{frame.chosen_option_id} was not offered on its payment frame"
        offered_label = frame.offered[frame.offered_option_ids.index(frame.chosen_option_id)]
        source = objects.get(str(frame.payment_source))
        if (
            offered_label != frame.chosen
            or frame.chosen_kind != "tap_mana_source"
            or source is None
            or frame.payment_source not in declared
            or frame.chosen_source != source.name
        ):
            return False, f"{offered_label!r} is not a tap of a declared payment source"
        seen.append(source.semantic_id)
    if len(set(seen)) != len(seen) or sorted(seen) != sorted(declared):
        return False, f"paid from {seen}, declared {declared}"
    actor = str(cast.document.get("actor"))
    for name in sorted({objects[sid].name for sid in seen}):
        taps = sum(1 for sid in seen if objects[sid].name == name)
        before = _named_tapped(cast.before, actor, name)
        after = _named_tapped(cast.complete, actor, name)
        if before is None or after is None or after - before != taps:
            return False, f"the readback shows {before} -> {after} tapped {name}, taps {taps}"
    return True, f"{len(seen)} engine-offered taps of the declared sources {seen}"


def _one_cast(casts: list[_ScriptedCast], card: str | None = None) -> _ScriptedCast | None:
    matching = [cast for cast in casts if card is None or cast.document.get("card") == card]
    return matching[0] if len(matching) == 1 else None


def _observe_priority(
    model: RequestedStateModel, run: fcr.CausalRun, casts: list[_ScriptedCast], argument: str
) -> tuple[bool, str]:
    player = argument.lower()
    taken = [cast for cast in casts if cast.frame.actor == player]
    ok = bool(taken) and all(cast.before and cast.before.get("stack") for cast in taken)
    return ok, f"{player} took the scripted cast on its own PRIORITY frame over the caused stack"


def _observe_spell_cast(
    model: RequestedStateModel, run: fcr.CausalRun, casts: list[_ScriptedCast], argument: str
) -> tuple[bool, str]:
    cast = _one_cast(casts, _card(argument))
    ok = (
        cast is not None
        and cast.frame.chosen_kind == "cast"
        and cast.frame.chosen_source == _card(argument)
        and cast.frame.chosen_option_id in cast.frame.offered_option_ids
        and cast.complete is not None
    )
    return ok, f"the engine-offered cast of {_card(argument)} completed with priority returned"


def _observe_stack_push(
    model: RequestedStateModel, run: fcr.CausalRun, casts: list[_ScriptedCast], argument: str
) -> tuple[bool, str]:
    cast = _one_cast(casts, _card(argument))
    if cast is None or cast.before is None or cast.complete is None:
        return False, f"no completed scripted cast of {_card(argument)}"
    before = fcr._stack(cast.before)
    after = fcr._stack(cast.complete)
    ok = len(after) == len(before) + 1 and fcr.stack_card(after[0]) == _card(argument)
    return ok, f"the stack went from {before} to {after}"


def _observe_mana_abilities(
    model: RequestedStateModel, run: fcr.CausalRun, casts: list[_ScriptedCast], argument: str
) -> tuple[bool, str]:
    paying = [cast for cast in casts if cast.payments]
    cast = paying[0] if len(paying) == 1 else None
    if cast is None or not argument.isdigit():
        return False, f"{len(paying)} scripted casts paid"
    bound, detail = _payment_bound(model, cast)
    return bound and len(cast.payments) == int(argument), detail


def _observe_mana_paid(
    model: RequestedStateModel, run: fcr.CausalRun, casts: list[_ScriptedCast], argument: str
) -> tuple[bool, str]:
    paying = [cast for cast in casts if cast.payments]
    cast = paying[0] if len(paying) == 1 else None
    if cast is None or cast.complete is None:
        return False, f"{len(paying)} scripted casts paid"
    declared = cast.document.get("declared_mana") or []
    cost = "(" + "".join(f"{{{symbol}}}" for symbol in declared) + ")"
    bound, detail = _payment_bound(model, cast)
    actor = str(cast.document.get("actor"))
    pool = (_players_by_id(cast.complete).get(actor) or {}).get("mana_pool")
    checks = {
        "declared_mana_is_the_token": "".join(declared) == argument,
        "engine_cast_cost": str(cast.frame.chosen or "").endswith(cost),
        "one_tap_per_declared_symbol": len(cast.payments) == len(declared),
        "taps_matched_to_declared_source_names": bound,
        "no_floating_mana": isinstance(pool, dict)
        and bool(pool)
        and all(value == 0 for value in pool.values()),
    }
    failed = [name for name, ok in checks.items() if not ok]
    return not failed, detail if not failed else f"not observed: {failed}; {detail}"


def _observe_payment_frame(
    model: RequestedStateModel, run: fcr.CausalRun, casts: list[_ScriptedCast], argument: str
) -> tuple[bool, str]:
    player = argument.lower()
    paying = [cast for cast in casts if cast.payments and cast.frame.actor == player]
    ok = bool(paying) and all(
        frame.kind == "MANA_PAYMENT" and frame.actor == player
        for cast in paying
        for frame in cast.payments
    )
    return (
        ok,
        f"the engine asked {player} {sum(len(c.payments) for c in paying)} MANA_PAYMENT frames",
    )


_SCRIPTED_TOKEN_OBSERVERS = {
    "mana_payment_frame": _observe_payment_frame,
    "priority": _observe_priority,
    "spell_cast": _observe_spell_cast,
    "stack_push": _observe_stack_push,
    "mana_abilities_activated": _observe_mana_abilities,
    "mana_paid": _observe_mana_paid,
}


def _route_checkpoint(model: RequestedStateModel, run: fcr.CausalRun) -> dict[str, Any]:
    """The record's checkpoint against the snapshot taken with the caused stack."""
    plan = model.causal_plan
    snapshot = next(
        (snap["state"] for snap in run.snapshots if snap["at"] == "requested_checkpoint"), None
    )
    if plan is None or snapshot is None:
        return {"verdict": CHECKPOINT_MISMATCH, "reason": "no requested-checkpoint snapshot"}
    stack = fcr._stack(snapshot)
    requested = model.temporal_state
    targets = [
        (index, target) for index, spell in enumerate(plan.spells) for target in spell.targets
    ]
    target_frames = [frame for frame in run.frames if frame.reason == "causal target"]
    bound = len(target_frames) == len(targets) and len(stack) == len(plan.spells)
    for frame, (index, target) in zip(target_frames, targets, strict=False):
        refs = frame.refs
        entry = stack[len(stack) - 1 - index] if bound else ""
        if len(refs) != 1:
            bound = False
        elif refs[0].get("kind") == "player":
            bound = bound and str(refs[0].get("player_id")).lower() == target.lower()
        else:
            bound = bound and f"({refs[0].get('card_id')})" in entry
    fields = {
        "stack_cards": (
            [fcr.stack_card(entry) for entry in stack],
            [spell.card for spell in reversed(plan.spells)],
        ),
        "stack_targets_bound": (bound, True),
        "active_player": (
            str(snapshot.get("active_player_id") or "").lower(),
            str(requested.get("active_player") or "").lower(),
        ),
        "priority_player": (
            str(snapshot.get("priority_player_id") or "").lower(),
            str(requested.get("priority_player") or "").lower(),
        ),
        "phase": (_normalize_phase(snapshot.get("phase")), requested.get("phase")),
        "step": (_normalize_step(snapshot.get("step")), requested.get("step")),
        "turn_number": (snapshot.get("turn_number"), requested.get("turn_number")),
    }
    mismatched = sorted(name for name, (seen, wanted) in fields.items() if seen != wanted)
    return {
        "verdict": CHECKPOINT_EXACT if not mismatched else CHECKPOINT_MISMATCH,
        "fields": {
            name: {"observed": seen, "requested": wanted} for name, (seen, wanted) in fields.items()
        },
        "mismatched": mismatched,
    }


# The obligation fields the scripted-decision contract has no evaluator for. A
# record that states any of them non-empty stays unobserved (UNKNOWN), and its
# receipt never lists them as exercised.
SCRIPTED_UNEVALUATED_FIELDS = (
    "forbidden_events",
    "ordering_constraints",
    "partial_order_constraints",
    "terminal_postconditions",
)


def scripted_unevaluated_fields(record: dict[str, Any]) -> list[str]:
    """The record's non-empty obligation fields the scripted contract cannot judge."""
    expected = record.get("expected_events") or {}
    values = {
        "forbidden_events": expected.get("forbidden_events"),
        "ordering_constraints": expected.get("ordering_constraints"),
        "partial_order_constraints": expected.get("partial_order_constraints"),
        "terminal_postconditions": record.get("terminal_postconditions"),
    }
    return [name for name in SCRIPTED_UNEVALUATED_FIELDS if values[name]]


def evaluate_scripted_decision_offered(
    model: RequestedStateModel, run: fcr.CausalRun
) -> ObligationVerdict:
    """The record's scripted cast on the caused stack, from the tape and readback only.

    The caused stack must be the record's (cast by its declared controllers on
    engine-offered options, top first as requested), the record's checkpoint
    must equal the snapshot taken with that stack, every tape choice must be an
    option the engine offered on its frame, and every required token needs its
    own observer. A token without one (``SCRIPTED_TOKEN_UNOBSERVABLE``) leaves
    the obligation unobserved: UNKNOWN, never PASS. So does any non-empty
    obligation field the contract does not evaluate
    (``SCRIPTED_UNEVALUATED_FIELDS``).
    """
    kind = "scripted_decision_offered"
    plan = model.causal_plan
    required = [
        str(token)
        for token in (model.record.get("expected_events") or {}).get("required_events") or []
    ]
    facts: dict[str, Any] = {"causal_route": run.to_document(), "required_events": required}
    if run.failure:
        return ObligationVerdict(kind, False, False, facts, [], f"causal route: {run.failure}")
    if plan is None or not required:
        return ObligationVerdict(kind, False, False, facts, [], "the record is not routable")
    casts = _scripted_casts(run)
    checkpoint = _route_checkpoint(model, run)
    facts["requested_checkpoint"] = checkpoint
    causal_casts = [frame for frame in run.frames if frame.reason.startswith("causal cast ")]
    checks: dict[str, bool] = {
        "stack_caused": run.stack_after_cast is not None
        and [fcr.stack_card(entry) for entry in run.stack_after_cast]
        == [spell.card for spell in reversed(plan.spells)],
        "cast_by_declared_controllers": [frame.actor.lower() for frame in causal_casts]
        == [spell.controller for spell in plan.spells],
        "tape_choices_offered": all(
            frame.chosen_option_id is None
            or (
                frame.chosen_option_id in frame.offered_option_ids
                and frame.offered[frame.offered_option_ids.index(frame.chosen_option_id)]
                == frame.chosen
            )
            for frame in run.frames
        ),
        "scripted_casts_recorded": bool(casts) and len(casts) == len(run.scripted_casts),
        "requested_checkpoint": checkpoint["verdict"] == CHECKPOINT_EXACT,
    }
    unevaluated = scripted_unevaluated_fields(model.record)
    facts["unevaluated_obligation_fields"] = unevaluated
    checks["no_unevaluated_obligation_fields"] = not unevaluated
    tokens: dict[str, dict[str, Any]] = {}
    for token in required:
        family, argument = _scripted_token(token)
        observer = _SCRIPTED_TOKEN_OBSERVERS.get(family)
        if observer is None:
            reason = SCRIPTED_TOKEN_UNOBSERVABLE.get(
                family, f"the lane has no observer for {family!r} tokens"
            )
            tokens[token] = {"observed": False, "detail": reason}
            continue
        ok, detail = observer(model, run, casts, argument)
        tokens[token] = {"observed": bool(ok), "detail": detail}
    facts["checks"] = checks
    facts["tokens"] = tokens
    unobserved = [token for token, entry in tokens.items() if not entry["observed"]]
    failed = [name for name, ok in checks.items() if not ok]
    observed = not failed and not unobserved
    reason = (
        "the scripted cast on the caused stack was observed from engine facts: "
        + "; ".join(f"{token}: {entry['detail']}" for token, entry in tokens.items())
        if observed
        else "not observed: "
        + ", ".join([*failed, *(f"{token} ({tokens[token]['detail']})" for token in unobserved)])
    )
    return ObligationVerdict(
        kind, observed, observed, facts, list(required) if observed else [], reason
    )


_CAUSAL_TERMINAL_CONTRACTS = {
    "commander_zone_choice": evaluate_commander_zone_choice,
    "scripted_decision_offered": evaluate_scripted_decision_offered,
}


def _route_observer(model: RequestedStateModel) -> str:
    """The seat whose principal-scoped readback the route's terminal is judged from."""
    if causal_terminal(model) == "commander_zone_choice":
        return str((_route_commander(model) or {}).get("owner") or "").lower()
    script = [step for step in model.record.get("decision_script") or () if isinstance(step, dict)]
    return str(script[0].get("actor") or "").lower() if script else ""


# ---------------------------------------------------------------------------
# Per-row evidence pipeline
# ---------------------------------------------------------------------------
_RECEIPT_FIELDS = (
    "fixture_identity",
    "obligation_identity",
    "requested_state_identity",
    "lab_source_identity",
    "rules_core_identity",
    "bridge_identity",
    "runner_identity",
    "transport",
    "scenario_parse",
    "native_bootstrap",
    "readback",
    "checkpoint_equivalence",
    "pending_decision_frame",
    "external_decision_selection",
    "semantic_events",
    "terminal_facts",
    "receipt_eligibility",
    "classification",
)


@dataclass
class RowEvidence:
    fixture_id: str
    fields: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        if key not in _RECEIPT_FIELDS:
            raise ScenarioLaneError(f"unknown evidence field {key!r}")
        self.fields[key] = value

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "fixture_id": self.fixture_id,
            "schema_version": LANE_SCHEMA_VERSION,
        }
        for key in _RECEIPT_FIELDS:
            document[key] = self.fields.get(key)
        return document


def _lab_source_identity(root: Path) -> dict[str, Any]:
    def git(args: list[str]) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
        )
        return completed.stdout.strip()

    return {
        "repository": "moeendres-png/commander-playtest-lab",
        "commit": git(["rev-parse", "HEAD"]),
        "tree": git(["rev-parse", "HEAD^{tree}"]),
        "branch": git(["rev-parse", "--abbrev-ref", "HEAD"]),
    }


def probe_row(
    proc: BridgeProcess,
    *,
    model: RequestedStateModel,
    source: ForgeScenarioSource,
    root: Path,
    seed: int = 424242,
    max_steps: int = 400,
    inject_unsupported_probe: bool = True,
) -> RowEvidence:
    """Run the full per-row pipeline for one effective record.

    Hard-unsupported dimensions with an explicit engine rejection are proven by
    sending exactly that requested field and requiring the engine to reject it.
    Hard-unsupported dimensions the engine silently ignores are proven by
    constructing the supported subset and showing the authoritative readback
    cannot equal the requested state. Rows without hard-unsupported dimensions
    are executed and their obligation evaluated from engine facts.
    """
    evidence = RowEvidence(fixture_id=model.fixture_id)
    evidence.set("fixture_identity", model.fixture_id)
    evidence.set(
        "obligation_identity",
        {
            "obligation_digest": model.record.get("obligation_digest"),
            "materialization_digest": model.record.get("materialization_digest"),
            "materialization_status": model.record.get("materialization_status"),
            "required_events": (model.record.get("expected_events") or {}).get("required_events"),
            "terminal_postconditions": model.record.get("terminal_postconditions"),
            "execution_entry_mode": model.record.get("execution_entry_mode"),
        },
    )
    evidence.set(
        "requested_state_identity",
        {
            "requested_state_digest": model.record.get("requested_state_digest"),
            "neutral_initial_state": model.neutral_initial_state,
            "temporal_state": model.temporal_state,
            "dimensions": [item.to_document() for item in model.dimensions],
        },
    )
    evidence.set("lab_source_identity", _lab_source_identity(root))
    evidence.set("rules_core_identity", source.rules_core_identity)
    evidence.set("bridge_identity", source.bridge_identity)
    evidence.set(
        "runner_identity",
        {
            "lane": LANE_SCHEMA_VERSION,
            "module": "commander_lab.qualification.current_boundary.forge_scenario_lane",
            "python": True,
        },
    )

    # 1) explicit engine rejection probes for the fields with enforced rejection
    rejection_probes: list[dict[str, Any]] = []
    seen_probes: set[str] = set()
    if inject_unsupported_probe:
        for finding in model.hard_unsupported:
            if not finding.runtime_probe or finding.runtime_probe in seen_probes:
                continue
            seen_probes.add(finding.runtime_probe)
            game_id = f"fsl-probe-{model.fixture_id.lower()}-{finding.runtime_probe}-{uuid.uuid4().hex[:6]}"
            probe_state = dict(model.neutral_initial_state)
            if finding.runtime_probe == "stack":
                probe_state["stack"] = [
                    {
                        "card": (model.record.get("stack_state") or [{}])[0].get(
                            "source_semantic_id", "Unknown"
                        ),
                        "controller": "p1",
                    }
                ]
            elif finding.runtime_probe == "decision_script":
                probe_state["decision_script"] = [{"kind": "test_probe"}]
            else:
                continue
            response = proc.request(
                "create_commander_game",
                {
                    "request": {
                        "game_id": game_id,
                        "deck_handles": _import_probe_decks(proc, model, game_id),
                        "format": "commander",
                        "external_control": True,
                        "scenario": {"neutral_initial_state": probe_state},
                    }
                },
                game_id=game_id,
                timeout_s=300.0,
            )
            expected_rejection = bool(response.get("success") is not True)
            codes = [
                entry.get("code")
                for entry in (response.get("errors") or [])
                if isinstance(entry, dict)
            ]
            messages = [
                entry.get("message")
                for entry in (response.get("errors") or [])
                if isinstance(entry, dict)
            ]
            rejection_probes.append(
                {
                    "dimension": finding.dimension,
                    "probe_field": finding.runtime_probe,
                    "engine_rejected": expected_rejection,
                    "error_codes": codes,
                    "error_messages": messages,
                }
            )
    evidence.set(
        "scenario_parse",
        {
            "rejection_probes": rejection_probes,
            "hard_unsupported_dimensions": [item.to_document() for item in model.hard_unsupported],
        },
    )

    # 2) hard unsupported and the requested temporal checkpoint is unreachable:
    # a bounded runtime probe proves the engine silently ignores the fields it
    # has no contract for, then the row fails closed with exact blockers.
    if model.hard_unsupported and not temporal_reachable(model):
        silent = run_silent_ignore_probe(proc, model=model)
        evidence.set(
            "transport",
            {
                "attempted": True,
                "constructor": "silent-ignore probe (supported subset + unknown fields)",
                "probe": silent,
            },
        )
        evidence.set(
            "native_bootstrap",
            {
                "applied": bool(silent.get("create_success")),
                "silent_ignore_acceptance": bool(silent.get("create_success")),
                "note": "engine acceptance of an unknown field is not construction",
            },
        )
        evidence.set("readback", silent.get("first_observable_checkpoint"))
        evidence.set(
            "checkpoint_equivalence",
            CheckpointEquivalence(
                verdict=CHECKPOINT_UNSUPPORTED_DIMENSION,
                fields=[],
                unsupported_dimensions=[item.dimension for item in model.hard_unsupported],
                unobservable_dimensions=[item.dimension for item in model.unobservable],
            ).to_document(),
        )
        evidence.set("pending_decision_frame", None)
        evidence.set("external_decision_selection", None)
        evidence.set("semantic_events", [])
        evidence.set("terminal_facts", {})
        evidence.set(
            "receipt_eligibility",
            {
                "eligible": False,
                "reason": "unsupported dimensions are not representable in the bootstrap contract",
            },
        )
        evidence.set(
            "classification",
            {
                "result": RESULT_UNSUPPORTED_DIMENSION,
                "reasons": [f"{item.dimension}: {item.detail}" for item in model.hard_unsupported],
                "silent_ignore_probe": silent,
            },
        )
        return evidence

    # 3) real execution: create/start/drive the supported subset
    drive = drive_scenario_game(proc, model, seed=seed, max_steps=max_steps)
    evidence.set("transport", {"attempted": True, "game_id": drive.game_id})
    creation = drive.terminal_facts.get("create_response")
    evidence.set(
        "native_bootstrap",
        {
            "applied": bool(creation and creation.get("success") is True),
            "create_response": creation,
            "steps_completed": drive.steps_completed,
            "failure": drive.failure,
        },
    )
    if drive.failure and drive.failure_kind == "ENGINE_REJECTED_SCENARIO":
        evidence.set("readback", {"error": "scenario rejected by engine"})
        evidence.set(
            "checkpoint_equivalence",
            CheckpointEquivalence(
                verdict=CHECKPOINT_UNSUPPORTED_DIMENSION,
                fields=[],
                unsupported_dimensions=[item.dimension for item in model.hard_unsupported],
                unobservable_dimensions=[item.dimension for item in model.unobservable],
            ).to_document(),
        )
        evidence.set("pending_decision_frame", None)
        evidence.set("external_decision_selection", None)
        evidence.set("semantic_events", [])
        evidence.set("terminal_facts", {})
        evidence.set(
            "receipt_eligibility",
            {"eligible": False, "reason": "engine rejected the scenario at creation"},
        )
        evidence.set(
            "classification",
            {
                "result": RESULT_ENGINE_REJECTED,
                "reasons": [f"engine rejected scenario: {drive.failure}"],
            },
        )
        return evidence

    observations = observe_all_seats(proc, drive.game_id, model.player_count or 2)
    evidence.set(
        "readback",
        {
            "seats": sorted(observations),
            "primary": _state_view(next(iter(observations.values())) if observations else {}),
        },
    )
    equivalence = compare_checkpoint(model, observations)
    evidence.set("checkpoint_equivalence", equivalence.to_document())
    last_decision = drive.decision_tape[-1] if drive.decision_tape else None
    evidence.set(
        "pending_decision_frame",
        None
        if last_decision is None
        else {
            "kind": last_decision.kind,
            "actor": last_decision.actor,
            "revision": last_decision.revision,
            "offered_option_ids": last_decision.offered_option_ids,
        },
    )
    evidence.set(
        "external_decision_selection",
        [
            {
                "step": entry.step,
                "kind": entry.kind,
                "actor": entry.actor,
                "policy": entry.policy,
                "chosen_option_id": entry.chosen_option_id,
                "offered_option_ids": entry.offered_option_ids,
            }
            for entry in drive.decision_tape
        ],
    )

    if model.causal_plan is None:
        obligation = evaluate_obligation(
            model,
            observations,
            drive.terminal_facts.get("progression") or [],
            drive.terminal_facts.get("starting_player_choice"),
        )
    else:
        obligation = ObligationVerdict(
            str(causal_terminal(model)),
            False,
            False,
            {"causal_route": None},
            [],
            "the causal route runs only from a credit-eligible checkpoint after a clean drive",
        )
    evidence.set("semantic_events", obligation.semantic_events)
    evidence.set(
        "terminal_facts",
        {
            "drive": drive.terminal_facts,
            "obligation": obligation.terminal_facts,
            "drive_failure": drive.failure,
        },
    )

    if model.hard_unsupported or not equivalence.credit_eligible:
        if model.hard_unsupported:
            result = RESULT_UNSUPPORTED_DIMENSION
            reasons = [f"{item.dimension}: {item.detail}" for item in model.hard_unsupported]
        elif equivalence.unobservable_dimensions:
            result = RESULT_UNSUPPORTED_DIMENSION
            reasons = [f"{item.dimension}: {item.detail}" for item in model.unobservable]
        else:
            result = RESULT_CHECKPOINT_MISMATCH
            reasons = [
                f"{item.field}: requested={item.requested!r} observed={item.observed!r}"
                for item in equivalence.fields
                if item.verdict == CHECKPOINT_MISMATCH
            ]
        evidence.set(
            "receipt_eligibility",
            {
                "eligible": False,
                "reason": (
                    "checkpoint equivalence is not credit-eligible (EXACT or a "
                    "fixture-declared cause variance); construction alone earns no credit"
                ),
            },
        )
        evidence.set("classification", {"result": result, "reasons": reasons})
        return evidence

    if drive.failure:
        evidence.set(
            "receipt_eligibility",
            {"eligible": False, "reason": f"drive failure: {drive.failure}"},
        )
        evidence.set(
            "classification",
            {"result": RESULT_TRANSPORT_FAILURE, "reasons": [drive.failure]},
        )
        return evidence

    if model.causal_plan is not None:
        # The checkpoint is the pre-causal position; the requested stack is now
        # cast on the engine's own frames and the script answered from there.
        observer = _route_observer(model)
        contract = _CAUSAL_TERMINAL_CONTRACTS[str(causal_terminal(model))]

        def observe_owner(game_id: str) -> dict[str, Any]:
            return _state_view(observe_seat_state(proc, game_id, observer))

        run = fcr.run_causal_route(
            proc,
            drive.game_id,
            model.record,
            model.causal_plan,
            seat_count=model.player_count or 2,
            observe=observe_owner,
            answer_frame_kinds=_route_answer_frames(model),
            checkpoint_priority=model.temporal_state.get("priority_player"),
        )
        obligation = contract(model, run)
        # The bootstrap checkpoint compared above is the pre-causal position;
        # the record's own checkpoint (the cast stack, the requested player on
        # priority) is judged from the engine snapshot the route captured.
        evidence.set(
            "checkpoint_equivalence",
            {
                **equivalence.to_document(),
                "checkpoint_basis": "PRE_CAUSAL_POSITION_THEN_CAUSED_STACK",
                "requested_checkpoint": obligation.terminal_facts.get("requested_checkpoint"),
            },
        )
        evidence.set("semantic_events", obligation.semantic_events)
        evidence.set(
            "terminal_facts",
            {
                "drive": drive.terminal_facts,
                "obligation": obligation.terminal_facts,
                "drive_failure": drive.failure,
            },
        )
        evidence.set(
            "external_decision_selection",
            [
                *(evidence.fields.get("external_decision_selection") or []),
                *(
                    {
                        "step": f"causal-{index}",
                        "kind": frame.kind,
                        "actor": frame.actor,
                        "policy": frame.reason,
                        "chosen_option_id": frame.chosen_option_id,
                        "offered_labels": frame.offered,
                    }
                    for index, frame in enumerate(run.frames)
                ),
            ],
        )

    if not obligation.credit_eligible_observation:
        evidence.set(
            "receipt_eligibility",
            {
                "eligible": False,
                "reason": f"obligation not observed from engine facts: {obligation.reason}",
            },
        )
        evidence.set(
            "classification",
            {
                "result": RESULT_OBLIGATION_NOT_OBSERVABLE,
                "reasons": [obligation.reason],
                "obligation_kind": obligation.kind,
            },
        )
        return evidence

    evidence.set(
        "receipt_eligibility",
        {
            "eligible": True,
            "reason": (
                "exact identity binding, engine-accepted scenario, "
                f"{equivalence.verdict} checkpoint equivalence"
                + (
                    f" ({equivalence.variance_source})"
                    if equivalence.verdict == CHECKPOINT_ALLOWED_VARIANCE
                    else ""
                )
                + ", engine-authored decisions only, and an obligation observed from "
                "engine-reported terminal facts"
            ),
        },
    )
    evidence.set(
        "classification",
        {
            "result": RESULT_OBLIGATION_OBSERVED,
            "reasons": [obligation.reason],
            "obligation_kind": obligation.kind,
            "checkpoint_verdict": equivalence.verdict,
        },
    )
    return evidence


# ---------------------------------------------------------------------------
# Canonical R-4 positive receipts for the shared current-boundary chain
# ---------------------------------------------------------------------------
# This lane is the Forge-candidate producer on the canonical positive-receipt
# contract. The shared assembler credits a row only from a receipt that binds
# the fixture, the exact effective requested-state and obligation digests, the
# admitted Forge Rules-Core commit and the currently executing Lab runner. A
# receipt exists only for an obligation observed from engine-reported facts:
# construction alone, a checkpoint mismatch, a transport failure or a named
# blocker earns nothing.
FORGE_SCENARIO_EXECUTION_MODE = "FORGE_SCENARIO_BOOTSTRAP_OBLIGATION"
FORGE_SCENARIO_TEST_IDENTITY_PREFIX = "forge-scenario-lane:"
FORGE_SCENARIO_RECEIPT_PREFIX = "forge-scenario-lane--"

# The F6/F7 wave whose blockers are re-derived every epoch. These rows are
# always attempted so the current epoch carries its own blocker evidence
# instead of inheriting a previous epoch's classification.
FORGE_SCENARIO_BLOCKER_WAVE: tuple[str, ...] = (
    "MICRO_COPY",
    "MICRO_COSTS",
    "MICRO_MODES",
    "MICRO_REPLACEMENT",
    "MICRO_ZONE_CHANGES",
    "WS05-MP-BLOCK-4",
    "WS05-MP-COMBAT-4",
)


def select_execution_fixtures(records: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    """The rows this producer attempts in the canonical evidence run.

    Every structurally credit-eligible row is attempted for a current direct
    receipt, and the declared blocker wave is always attempted. Nothing else is
    attempted: a row this lane cannot represent stays a named terminal blocker
    rather than an inherited count.
    """
    selected: list[str] = []
    for fixture_id, record in records.items():
        model = model_requested_state(record)
        if model.credit_eligible and temporal_reachable(model):
            selected.append(fixture_id)
    for fixture_id in FORGE_SCENARIO_BLOCKER_WAVE:
        if fixture_id in records and fixture_id not in selected:
            selected.append(fixture_id)
    return tuple(selected)


def _receipt_observed_assertion(evidence: RowEvidence) -> dict[str, Any]:
    """The engine-observed assertion a positive receipt binds.

    It records the checkpoint verdict (including a fixture-declared cause
    variance, which is never relabelled EXACT), the semantic events, and digests
    that trace the claim back to the exact persisted row document.
    """
    fields = evidence.fields
    checkpoint = fields.get("checkpoint_equivalence") or {}
    classification = fields.get("classification") or {}
    decisions = fields.get("external_decision_selection") or []
    return {
        "checkpoint_verdict": checkpoint.get("verdict"),
        "checkpoint_variance_source": checkpoint.get("variance_source"),
        # A causal row's checkpoint verdict is the pre-causal position; its
        # requested checkpoint is judged separately from the caused stack.
        "checkpoint_basis": checkpoint.get("checkpoint_basis", "BOOTSTRAP_CHECKPOINT"),
        "requested_checkpoint_verdict": (checkpoint.get("requested_checkpoint") or {}).get(
            "verdict"
        ),
        "obligation_kind": classification.get("obligation_kind"),
        "semantic_events": list(fields.get("semantic_events") or []),
        "row_document_sha256": receipt_mod.document_digest(evidence.to_document()),
        "terminal_facts_sha256": receipt_mod.document_digest(
            {"terminal_facts": fields.get("terminal_facts") or {}}
        ),
        "external_decision_selection_sha256": receipt_mod.document_digest(
            {"external_decision_selection": decisions}
        ),
        "engine_authored_decision_count": len(decisions),
        "native_bootstrap_applied": bool((fields.get("native_bootstrap") or {}).get("applied")),
    }


def _obligation_exercised(
    record: dict[str, Any], obligation_kind: Any, state_digest: Any, obligation_digest: Any
) -> dict[str, Any]:
    """The obligation fields a receipt names as exercised: only those evaluated.

    The scripted-decision contract judges ``required_events`` only; the fields it
    does not evaluate are never listed (a record stating any of them is not
    observed, so it never reaches a receipt).
    """
    expected = record.get("expected_events") or {}
    exercised: dict[str, Any] = {
        "requested_state_digest": state_digest,
        "obligation_digest": obligation_digest,
        "required_events": list(expected.get("required_events") or ()),
    }
    if obligation_kind == "scripted_decision_offered":
        unevaluated = scripted_unevaluated_fields(record)
        if unevaluated:
            raise ScenarioLaneError(
                f"{record.get('fixture_id')}: {unevaluated} were not evaluated; no receipt"
            )
        return exercised
    exercised["forbidden_events"] = list(expected.get("forbidden_events") or ())
    exercised["terminal_postconditions"] = list(record.get("terminal_postconditions") or ())
    return exercised


def positive_receipt(
    evidence: RowEvidence,
    record: dict[str, Any],
    *,
    candidate_commit: str,
    runner_digest: str,
) -> dict[str, Any]:
    """The canonical runner-bound positive receipt for one observed obligation.

    This is the only route by which a scenario-lane execution may earn FULL107
    credit. It fails closed unless the obligation was observed from engine facts
    and the checkpoint was credit-eligible; constructed state alone can never be
    receipted. ``candidate_commit`` is the admitted Forge Rules-Core identity the
    assembler credits the Forge column against.
    """
    classification = evidence.fields.get("classification") or {}
    if classification.get("result") != RESULT_OBLIGATION_OBSERVED:
        raise ScenarioLaneError(
            f"{evidence.fixture_id} is not a directly observed obligation; no positive receipt"
        )
    eligibility = evidence.fields.get("receipt_eligibility") or {}
    if eligibility.get("eligible") is not True:
        raise ScenarioLaneError(
            f"{evidence.fixture_id} is not receipt-eligible: {eligibility.get('reason')}"
        )
    state_digest = record.get("requested_state_digest")
    obligation_digest = record.get("obligation_digest")
    if not state_digest or not obligation_digest:
        raise ScenarioLaneError(
            f"{evidence.fixture_id}: the effective record carries no exact "
            "requested-state/obligation digest"
        )
    checkpoint = (evidence.fields.get("checkpoint_equivalence") or {}).get("verdict")
    assertion = _receipt_observed_assertion(evidence)
    document: dict[str, Any] = {
        "schema_version": receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": "forge",
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "fixture_id": evidence.fixture_id,
        "test_identity": (
            f"{FORGE_SCENARIO_TEST_IDENTITY_PREFIX}{FORGE_SCENARIO_EXECUTION_MODE}"
            f"#{evidence.fixture_id}"
        ),
        "execution_mode": FORGE_SCENARIO_EXECUTION_MODE,
        "obligation_exercised": _obligation_exercised(
            record, classification.get("obligation_kind"), state_digest, obligation_digest
        ),
        "observed_assertion": assertion,
        # A fixture-declared native player-loss cause is recorded as such, never
        # relabelled EXACT: the checkpoint verdict travels with the receipt.
        "assertion_class": (
            "BEHAVIOUR_OBSERVED_FIXTURE_DECLARED_CAUSE_VARIANCE"
            if checkpoint == CHECKPOINT_ALLOWED_VARIANCE
            else "BEHAVIOUR_OBSERVED"
        ),
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "outcome": "PASS",
        "runtime_receipt_digest": assertion["row_document_sha256"],
    }
    document["receipt_digest"] = receipt_mod.document_digest(document)
    return document


def execute_and_persist(
    *,
    forge_workspace: Path | str,
    records: dict[str, dict[str, Any]],
    candidate_commit: str,
    runner_digest: str,
    out_dir: Path,
    lab_root: Path,
    seed: int = 424242,
    max_steps: int = 400,
) -> dict[str, Any]:
    """Execute the selected rows on the pinned scenario seam and persist receipts.

    Binds the exact pinned Forge source, derives the capability matrix (source
    drift fails closed), executes every selected row on one bridge process, and
    writes a canonical positive receipt for each observed obligation into
    ``out_dir``. This producer owns only its own prefixed receipt files; the
    other R-4 producers' receipts are never touched. An engine rejection, a
    checkpoint mismatch, a missing observation, or an unbound identity yields a
    row document with no receipt, never a PASS.
    """
    if not candidate_commit or not runner_digest:
        raise ScenarioLaneError(
            "execute_and_persist requires the exact candidate commit and a measured "
            "runner digest; an unbound receipt is never written"
        )
    source = bind_forge_scenario_source(forge_workspace)
    if source.rules_core_commit != candidate_commit:
        raise ScenarioLaneError(
            f"the bound Forge Rules Core {source.rules_core_commit[:12]} is not the "
            f"credited candidate {candidate_commit[:12]}"
        )
    matrix = derive_capability_matrix(source, Path(source.workspace))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixtures = select_execution_fixtures(records)
    # This producer owns only its own prefixed receipts: a row that no longer
    # observes an obligation must not keep credit from an earlier run, and the
    # other producers' receipts must survive this cleanup.
    for stale in out_dir.glob(f"{FORGE_SCENARIO_RECEIPT_PREFIX}*.json"):
        stale.unlink()
    evidence: list[RowEvidence] = []
    runtime_identities: dict[str, dict[str, Any]] = {}
    for fixture_id in fixtures:
        # Batch qualification is process-isolated: every fixture starts from a
        # fresh Forge bridge process so mutable engine/session state can never
        # carry into the next row. Source/build identity stays pinned by
        # launch_forge_scenario and is persisted per fixture below.
        proc, runtime_identity = launch_forge_scenario(source)
        runtime_identities[fixture_id] = runtime_identity
        try:
            model = model_requested_state(records[fixture_id])
            evidence.append(
                probe_row(
                    proc,
                    model=model,
                    source=source,
                    root=lab_root,
                    seed=seed,
                    max_steps=max_steps,
                )
            )
        finally:
            proc.close()
    receipts_written: list[str] = []
    rows: list[dict[str, Any]] = []
    for item in evidence:
        document = item.to_document()
        classification = item.fields.get("classification") or {}
        if classification.get("result") == RESULT_OBLIGATION_OBSERVED:
            receipt = positive_receipt(
                item,
                records[item.fixture_id],
                candidate_commit=candidate_commit,
                runner_digest=runner_digest,
            )
            receipt_path = out_dir / f"{FORGE_SCENARIO_RECEIPT_PREFIX}{item.fixture_id}.json"
            receipt_mod.persist(receipt_path, receipt)
            # Read the persisted bytes back under the canonical validator so a
            # malformed receipt can never be recorded as evidence.
            receipt_mod.load_positive_fixture_receipt(receipt_path)
            document["positive_receipt_digest"] = receipt["receipt_digest"]
            document["positive_receipt_test_identity"] = receipt["test_identity"]
            receipts_written.append(item.fixture_id)
        rows.append(document)
    counts: dict[str, int] = {}
    for item in evidence:
        result = str((item.fields.get("classification") or {}).get("result", "UNKNOWN"))
        counts[result] = counts.get(result, 0) + 1
    structural: list[dict[str, Any]] = []
    for fixture_id, record in records.items():
        model = model_requested_state(record)
        structural.append(
            {
                "fixture_id": fixture_id,
                "classification": (
                    "CREDIT_ELIGIBLE"
                    if model.credit_eligible
                    else "CONSTRUCTIBLE_NOT_OBSERVABLE"
                    if model.construction_eligible
                    else "UNSUPPORTED_DIMENSION"
                ),
                "unsupported_dimensions": [item.dimension for item in model.hard_unsupported],
                "unobservable_dimensions": [item.dimension for item in model.unobservable],
                "temporal_reachable": temporal_reachable(model),
            }
        )
    return {
        "schema_version": f"{LANE_SCHEMA_VERSION}.forge-scenario-executions",
        "execution_mode": FORGE_SCENARIO_EXECUTION_MODE,
        "candidate": "forge",
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "source_identity": source.to_document(),
        "capability_matrix": matrix,
        "capability_matrix_sha256": receipt_mod.document_digest(matrix),
        "structural_census": structural,
        "process_isolation": "FRESH_PROCESS_PER_FIXTURE",
        "runtime_identities": runtime_identities,
        "rows_attempted": len(rows),
        "rows_observed": len(receipts_written),
        "receipts_written": receipts_written,
        "counts": counts,
        "rows": rows,
    }


def run_silent_ignore_probe(proc: BridgeProcess, *, model: RequestedStateModel) -> dict[str, Any]:
    """Prove the engine ACCEPTS and silently ignores fields it has no contract for.

    This is the fail-closed control for unsupported dimensions without an
    explicit parse rejection (combat state, cost state, temporal state): the
    engine returns a created game, yet the constructed state cannot contain the
    requested dimension. The lane must therefore classify it itself; it must
    never treat engine acceptance as construction.
    """
    players = model.player_count or 2
    game_id = f"fsl-silent-{model.fixture_id.lower()}-{uuid.uuid4().hex[:6]}"
    unsupported_payload: dict[str, Any] = {}
    for key in ("combat_state", "action_cost_state", "temporal_state", "knowledge_state"):
        value = model.record.get(key)
        if value:
            unsupported_payload[key] = value
    if (model.record.get("stack_state") or []) or (model.record.get("decision_script") or []):
        # These have their own explicit-rejection probe; do not duplicate them here.
        pass
    neutral = dict(model.neutral_initial_state)
    neutral.update(unsupported_payload)
    handles = _import_probe_decks(proc, model, game_id)
    created = proc.request(
        "create_commander_game",
        {
            "request": {
                "game_id": game_id,
                "deck_handles": handles,
                "format": "commander",
                "external_control": True,
                "seed": 424242,
                "scenario": {"neutral_initial_state": neutral},
            }
        },
        game_id=game_id,
        timeout_s=300.0,
    )
    result: dict[str, Any] = {
        "game_id": game_id,
        "create_success": created.get("success") is True,
        "error_codes": [
            entry.get("code") for entry in (created.get("errors") or []) if isinstance(entry, dict)
        ],
        "error_messages": [
            entry.get("message")
            for entry in (created.get("errors") or [])
            if isinstance(entry, dict)
        ],
        "submitted_unsupported_fields": sorted(unsupported_payload),
        "requested_temporal_state": model.temporal_state,
    }
    if result["create_success"]:
        started = proc.request("start_game", {}, game_id=game_id, timeout_s=300.0)
        result["start_success"] = started.get("success") is True
        try:
            frame = poll_decision(proc, game_id, seat_count=players, candidate="forge")
            result["first_pending_kind"] = frame["decision"].get("kind")
        except GameDriveError as exc:
            result["first_pending_kind"] = None
            result["first_pending_error"] = str(exc)
        state = _state_view(observe_seat_state(proc, game_id, SEATS[0]))
        result["first_observable_checkpoint"] = {
            "turn_number": state.get("turn_number"),
            "phase": _normalize_phase(state.get("phase")),
            "step": _normalize_step(state.get("step")),
            "stack": state.get("stack"),
        }
        result["silently_ignored"] = bool(unsupported_payload)
        result["note"] = (
            "the engine accepted the create request with fields its parser has no "
            "contract for; acceptance is not construction and the first observable "
            "checkpoint cannot contain those dimensions"
        )
    return result


def _import_probe_decks(proc: BridgeProcess, model: RequestedStateModel, game_id: str) -> list[str]:
    handles: list[str] = []
    for seat in SEATS[: model.player_count or 2]:
        commanders = _deck_plan(model).get(seat) or ["Rograkh, Son of Rohgahh"]
        deck = build_commander_deck(f"{game_id}-{seat}", commanders)
        payload = _payload(proc.request("import_deck", {"deck": deck}, timeout_s=300.0))
        handle = payload.get("deck_handle")
        handle_id = handle.get("handle_id") if isinstance(handle, dict) else None
        if not handle_id:
            raise ScenarioLaneError(f"probe deck import failed for {seat}: {payload}")
        handles.append(str(handle_id))
    return handles


def launch_forge_scenario(
    source: ForgeScenarioSource,
) -> tuple[BridgeProcess, dict[str, Any]]:
    """Build and launch the exact pinned Forge bridge for this lane."""
    plan = build_launch_plan("forge", forge_workspace=Path(source.workspace))
    proc = launch(plan)
    capabilities = proc.request("start_engine", {}, timeout_s=300.0)
    provider = proc.request("get_provider_version", {}, timeout_s=120.0)
    declared = proc.request("get_capabilities", {}, timeout_s=120.0)
    identity = {
        "launch_plan": {
            "candidate": plan.candidate,
            "lane": plan.lane,
            "expected_engine_commit": plan.expected_engine_commit,
            "workspace": plan.workspace,
            "build_identity": plan.build_identity,
        },
        "start_engine": capabilities,
        "provider_version": provider,
        "capabilities": declared,
    }
    return proc, identity


def run_capability_probe(proc: BridgeProcess, model: RequestedStateModel) -> dict[str, Any]:
    """Prove the documented rejections on the live engine (read-only)."""
    probes: list[dict[str, Any]] = []
    handles = _import_probe_decks(proc, model, "fsl-reject-probe")
    for probe_field, payload in (
        ("stack", [{"card": "Lightning Bolt", "controller": "p1"}]),
        ("decision_script", [{"kind": "probe"}]),
    ):
        game_id = f"fsl-reject-{probe_field}-{uuid.uuid4().hex[:6]}"
        response = proc.request(
            "create_commander_game",
            {
                "request": {
                    "game_id": game_id,
                    "deck_handles": handles,
                    "format": "commander",
                    "external_control": True,
                    "scenario": {"neutral_initial_state": {probe_field: payload}},
                }
            },
            game_id=game_id,
            timeout_s=300.0,
        )
        probes.append(
            {
                "field": probe_field,
                "success": response.get("success"),
                "error_codes": [
                    entry.get("code")
                    for entry in (response.get("errors") or [])
                    if isinstance(entry, dict)
                ],
                "error_messages": [
                    entry.get("message")
                    for entry in (response.get("errors") or [])
                    if isinstance(entry, dict)
                ],
            }
        )
    return {"rejections": probes}


def summarize_classifications(evidence: list[RowEvidence]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in evidence:
        classification = item.fields.get("classification") or {}
        result = str(classification.get("result", "UNKNOWN"))
        counts[result] = counts.get(result, 0) + 1
    return {
        "total": len(evidence),
        "counts": counts,
        "evidence": [item.to_document() for item in evidence],
    }


def sleeps(seconds: float) -> None:  # pragma: no cover - small helper
    time.sleep(seconds)


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)
