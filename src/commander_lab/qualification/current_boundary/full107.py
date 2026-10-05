"""Current-boundary FULL107 executor (candidate-neutral, fresh runtime).

Executes the effective 107-row provider denominator against a live external
candidate engine and records an explicit outcome for every row. No row is
silently skipped, and no outcome is inherited from historical evidence.

Outcome vocabulary (AF10 requires denominator-complete accounting):

PASS       the effective obligation was executed and the obligated facts were
           observed in this run
FAIL       the run executed and the obligated facts were not observed
UNKNOWN    no execution seam or no honest observation path exists; recorded
           with the exact reason
BLOCKED    the boundary contract locks the execution seam (e.g. a capability
           the provider truthfully reports as unavailable)
CRASH      the external process died or produced an unparsable stream
TIMEOUT    the external process exceeded its bound
PROTOCOL_FAILURE  the provider answered in a shape the current contract
           forbids
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import generic_construction, lifecycle
from .bridge_launcher import BridgeProcess
from .game_driver import (
    CommandedGameResult,
    DecisionUnsatisfied,
    drive_commander_game,
    poll_decision,
)
from .source_lock import (
    CURRENT_QUALIFICATION_BOUNDARY,
    CURRENT_RULES_AUTHORITY_EFFECTIVE_DATE,
    CURRENT_TRANSPORT_PROTOCOL,
    FULL107_SUCCESSOR_CONTRACT,
)

OUTCOMES = (
    "PASS",
    "FAIL",
    "UNKNOWN",
    "BLOCKED",
    "CRASH",
    "TIMEOUT",
    "PROTOCOL_FAILURE",
)

# Rows the effective contract itself blocks on the XMage Lab path: the bridge
# reports starting_state_injection_supported=false, so a frozen mid-game
# starting state cannot be constructed. This is a contract-locked seam, not a
# Rules incapability of XMage itself.
#
# PB-03: which rows those are is decided by MECHANISM, not by row name. The
# previous constant was a tuple of fixture-id prefixes, which could not classify
# a row it had never seen and hid the reason behind a string. See
# materialization.requires_starting_state and MID_GAME_MECHANISM_FAMILIES.
#
# starting_state_injection_supported is never flipped: the production XMage
# starting-state seam exists, but it is not this generic obligation, so the
# capability flag stays as the provider reports it.

# Rows whose obligation is a *per-scenario hidden-information probe* that needs
# engine-native principal-scoped channel instrumentation which the generic
# Protocol-2 state projection does not expose.
HIDDEN_SCENARIO_ROWS = (
    *(f"HIDDEN_{index:02d}" for index in range(1, 20)),
    "HIDDEN_HONEYCARD_SENTINEL",
)

# Rows whose obligation is a dedicated forbidden-shortcut negative campaign.
NEGATIVE_ROWS = (
    "NEGATIVE_FIRST_OPTION",
    "NEGATIVE_RANDOM_OPTION",
    "NEGATIVE_DEFAULT_YES_NO",
    "NEGATIVE_INTERNAL_AI",
    "NEGATIVE_GUI_DEFAULT",
    "NEGATIVE_SILENT_SKIP",
    "NEGATIVE_PARENT_CLASS_FALLBACK",
)

# Replay / RNG rows.
REPLAY_ROWS = (
    "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
)

# Micro-rules rows that need engine-native mid-game state construction.
NATIVE_MICRO_ROWS = (
    "MICRO_COSTS",
    "MICRO_MANA_PAYMENT",
    "MICRO_PRIORITY",
    "MICRO_STACK",
    "MICRO_MODES",
    "MICRO_TRIGGERS",
    "MICRO_REPLACEMENT",
    "MICRO_PREVENTION",
    "MICRO_CONTINUOUS_EFFECTS",
    "MICRO_STATE_BASED_ACTIONS",
    "MICRO_ZONE_CHANGES",
    "MICRO_COPY",
    "MICRO_CONTROL",
    "MICRO_COMBAT",
    "MICRO_RULES_RANDOMNESS",
)

# Pilot decision-family rows that need a specific engine-offered decision class
# in a constructed game state.
PILOT_ROWS = (
    "PILOT_PRIORITY",
    "PILOT_TARGET",
    "PILOT_CHOOSE_OBJECT",
    "PILOT_TARGET_AMOUNT",
    "PILOT_MULLIGAN",
    "PILOT_CHOOSE_USE",
    "PILOT_CHOICE",
    "PILOT_PILE",
    "PILOT_MANA_PAYMENT",
    "PILOT_ANNOUNCE_X",
    "PILOT_MULTI_AMOUNT",
    "PILOT_REPLACEMENT_EFFECT",
    "PILOT_TRIGGER_ORDER",
    "PILOT_CHOOSE_MODE",
    "PILOT_CHOOSE_ABILITY",
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
)


@dataclass
class RowResult:
    fixture_id: str
    candidate: str
    outcome: str
    execution_mode: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_document(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "candidate": self.candidate,
            "effective_obligation_digest": record.get("obligation_digest"),
            "effective_requested_state_digest": record.get("requested_state_digest"),
            "qualification_boundary": CURRENT_QUALIFICATION_BOUNDARY,
            "full107_successor_contract": FULL107_SUCCESSOR_CONTRACT,
            "rules_authority_effective_date": CURRENT_RULES_AUTHORITY_EFFECTIVE_DATE,
            "transport_protocol": CURRENT_TRANSPORT_PROTOCOL,
            "fixture_family": record.get("fixture_family"),
            "player_count": self.evidence.get("player_count"),
            "actual_cards": self.evidence.get("actual_cards"),
            "initial_materialization": {
                "materialization_version": record.get("materialization_version"),
                "materialization_digest": record.get("materialization_digest"),
                "execution_entry_mode": record.get("execution_entry_mode"),
            },
            "externally_supplied_decision_tape": self.evidence.get("decision_tape", []),
            "rules_rng_binding": self.evidence.get("rules_rng_binding"),
            "principal_observation_scope": self.evidence.get("principal_observation_scope"),
            "semantic_events": self.evidence.get("semantic_events", []),
            "terminal_facts": self.evidence.get("terminal_facts", {}),
            "exit_state": self.outcome,
            "evidence_class": self.evidence.get("evidence_class"),
            "execution_mode": self.execution_mode,
            "failure_reason": None if self.outcome == "PASS" else self.reason,
            "reason": self.reason,
            "runtime_identity": self.evidence.get("runtime_identity", {}),
            # What justified a construction-dependent outcome: the field-level
            # construction proof and the record's scripted pregame against the
            # engine's own decisions. Persisted with the row, so a receipt's
            # row digest binds them.
            "construction_proof": self.evidence.get("construction_proof"),
            "scripted_pregame_plan": self.evidence.get("scripted_pregame_plan"),
            "observed_pregame_decisions": self.evidence.get("observed_pregame_decisions"),
        }


def _actual_cards() -> list[str]:
    return [
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
    ]


def run_cardinality(
    proc: BridgeProcess,
    *,
    candidate: str,
    player_count: int,
    runtime_identity: dict[str, Any],
    record: dict[str, Any] | None = None,
) -> CommandedGameResult:
    """Run one real Commander lifecycle at one player count.

    With the fixture's ``record`` the run imports the record's own decks and seed,
    so the provider constructs the requested state and its construction proof can
    be compared (#441 decision (c)). A record whose decks are not a 100-card
    Commander deck per seat imports nothing of its own; the run then uses the
    driver's decks and the record's construction stays unestablished.
    """
    decks = None
    seed = 424242
    plan = None
    if record is not None:
        try:
            decks = record_decks(record)
        except ValueError:
            decks = None
        record_seed = (record.get("rules_randomness") or {}).get("rules_seed")
        if isinstance(record_seed, int) and not isinstance(record_seed, bool):
            seed = record_seed
        if record.get("pregame_decision_plan") is not None:
            # The record's own keeps, seat by seat in the order it names: the
            # driver answers only those and fails closed on any other frame.
            # An inconsistent plan runs nothing of its own and is never credited
            # (cardinality_row re-derives it).
            try:
                plan = scripted_pregame_plan(record)
            except ValueError:
                plan = None
    return drive_commander_game(
        proc,
        candidate=candidate,
        player_count=player_count,
        seed=seed,
        drive_to="priority",
        max_steps=80,
        mulligan_plan=plan,
        decks=decks,
    )


def construction_credit_gap(
    record: dict[str, Any], proof: generic_construction.ConstructionProof | None = None
) -> str | None:
    """Why the record's construction condition is unmet on the generic lane.

    A record whose ``construction_validation`` is required credits a row only when
    the provider's normalized constructed state equals the requested state. Without
    a construction proof the generic lane can observe the obligation but never
    establish the credit condition (Owner decision (a), Commander-Lab #441); with
    one, only an established equality lifts the gap (decision (c)). ``None`` means
    the record imposes no construction condition or the proof establishes it.
    """
    construction = record.get("construction_validation") or {}
    if not construction.get("required"):
        return None
    if proof is None:
        return (
            f"the record requires {construction.get('credit_condition')} and this lane "
            "emits no normalized constructed state, so construction equality is unestablished"
        )
    if proof.established:
        return None
    return (
        f"the record requires {construction.get('credit_condition')} and the provider's "
        f"constructed state does not establish it, so construction equality is "
        f"unestablished: {proof.reason()}"
    )


def generic_construction_proof(
    record: dict[str, Any], result: CommandedGameResult
) -> generic_construction.ConstructionProof | None:
    """The generic-lane construction proof of one run, or None without a provider state.

    A provider that does not declare ``constructed_state_supported``, or a launch
    without an orchestration key, emits nothing, and there is then no proof at all
    (not a failed one).
    """
    if not result.terminal_facts.get("provider_constructed_state_supported"):
        return None
    if result.terminal_facts.get("constructed_state_channel") != "orchestration_keyed_launch":
        return None
    binding = result.seed_binding
    seed = binding.acknowledged_seed if binding is not None and binding.controlled else None
    return generic_construction.compare(
        record,
        result.constructed_state,
        acknowledged_seed=seed,
        first_priority_seat=result.terminal_facts.get("first_priority_seat"),
        capture=result.terminal_facts.get("constructed_state_capture"),
        orchestration_key=result.orchestration_key,
    )


def cardinality_row(
    record: dict[str, Any],
    result: CommandedGameResult,
    *,
    candidate: str,
    runtime_identity: dict[str, Any],
) -> RowResult:
    """Classify one PLAYER_COUNT_* row from a real lifecycle run."""
    fixture_id = record["fixture_id"]
    # The effective record carries the seat roster, not a scalar player_count.
    # Derive the required cardinality from the frozen seat list.
    seats = record.get("players")
    wanted = len(seats) if isinstance(seats, list) and seats else None
    if wanted is None:
        digits = "".join(ch for ch in fixture_id.split("_")[-1] if ch.isdigit())
        wanted = int(digits) if digits else None
    created = result.terminal_facts.get("created_player_count")
    evidence = {
        "player_count": wanted,
        "actual_cards": _actual_cards(),
        "decision_tape": [entry.__dict__ for entry in result.decision_tape],
        "semantic_events": result.semantic_events,
        "terminal_facts": result.terminal_facts,
        "runtime_identity": runtime_identity,
        "evidence_class": "FRESH_CURRENT_BOUNDARY_RUNTIME",
        # Same defect as START-2: engine_owned was asserted from caller intent.
        # Control comes from the engine's acknowledgement via the driver.
        "rules_rng_binding": (
            result.seed_binding.to_document()
            if result.seed_binding is not None
            else {
                "control": "UNCONTROLLED_ENGINE_RNG",
                "detail": "the engine acknowledged no seed for this run",
            }
        ),
        "principal_observation_scope": "engine-offered decision frames for the acting seat",
    }
    planned = record.get("pregame_decision_plan") is not None
    if planned:
        evidence["observed_pregame_decisions"] = [
            [entry.seat, entry.keep] for entry in result.decision_tape if entry.step == "mulligan"
        ]
    if result.failure:
        if planned and result.failure.startswith(f"{DecisionUnsatisfied.__name__}:"):
            # The engine asked a pregame the record's plan does not name: the
            # record's decisions were not executed, which proves nothing either way.
            return RowResult(
                fixture_id,
                candidate,
                "UNKNOWN",
                "PROTOCOL2_LIFECYCLE",
                f"the record's scripted pregame did not complete: {result.failure}",
                evidence,
            )
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_LIFECYCLE",
            f"lifecycle runtime failure: {result.failure}",
            evidence,
        )
    if wanted is None:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_LIFECYCLE",
            "the effective record does not state the required player count",
            evidence,
        )
    if created != wanted:
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_LIFECYCLE",
            f"engine created {created} players for a {wanted}P fixture",
            evidence,
        )
    # All-or-nothing. A run that stopped part-way through the lifecycle has not
    # established the fixture, whatever prefix it did complete, so an incomplete
    # lifecycle is UNKNOWN rather than FAIL and never a partial PASS.
    assessment = lifecycle.lifecycle_completeness(
        {
            "steps_completed": list(result.steps_completed),
            "failure": result.failure,
            "terminal_facts": result.terminal_facts,
            "decision_tape": [entry.__dict__ for entry in result.decision_tape],
        }
    )
    evidence["lifecycle_completeness"] = assessment
    if not assessment["complete"]:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_LIFECYCLE",
            "the Commander lifecycle was not completed, so this fixture is "
            "unestablished: " + "; ".join(assessment["reasons"]),
            evidence,
        )
    if planned:
        try:
            plan = [list(entry) for entry in scripted_pregame_plan(record)]
        except ValueError as exc:
            return RowResult(
                fixture_id,
                candidate,
                "UNKNOWN",
                "PROTOCOL2_LIFECYCLE",
                f"a real {wanted}P Commander lifecycle was observed, but the record's "
                f"pregame is not executable: {exc}",
                evidence,
            )
        evidence["scripted_pregame_plan"] = plan
        if any(len(entry) > 1 and entry[1] is False for entry in plan):
            # Only the scripted pregame lane checks the engine's own CR 103.5
            # shuffles; a mulligan-bearing plan is never credited here (#553 Audit 1 B5).
            return RowResult(
                fixture_id,
                candidate,
                "UNKNOWN",
                "PROTOCOL2_LIFECYCLE",
                "a mulligan-bearing pregame plan needs the scripted pregame lane's CR 103.5 "
                "shuffle evidence, which this lane does not read",
                evidence,
            )
        if evidence["observed_pregame_decisions"] != plan:
            return RowResult(
                fixture_id,
                candidate,
                "UNKNOWN",
                "PROTOCOL2_LIFECYCLE",
                f"a real {wanted}P Commander lifecycle was observed, but the engine's "
                f"pregame decisions {evidence['observed_pregame_decisions']} are not the "
                f"record's plan {plan}",
                evidence,
            )
    proof = generic_construction_proof(record, result)
    if proof is not None:
        evidence["construction_proof"] = proof.to_document()
    gap = construction_credit_gap(record, proof)
    if gap is not None:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_LIFECYCLE",
            f"a real {wanted}P Commander lifecycle was observed, but {gap}",
            evidence,
        )
    return RowResult(
        fixture_id,
        candidate,
        "PASS",
        "PROTOCOL2_LIFECYCLE",
        f"real {wanted}P Commander lifecycle executed under Protocol "
        f"{CURRENT_TRANSPORT_PROTOCOL} with engine-owned legality and external "
        f"discretionary choices bound to engine-offered options",
        evidence,
    )


def start2_row(
    record: dict[str, Any],
    proc: BridgeProcess,
    *,
    candidate: str,
    runtime_identity: dict[str, Any],
) -> RowResult:
    """Execute WS05-CMD-START-2 under the v1.0.6 successor semantics.

    Obligation (CR 103.8a, current official 2026-09-25): in a two-player game
    the starting player skips the ENTIRE first-turn draw step, so no draw-step
    checkpoint, no draw event and no priority inside that step may be observed,
    and hand/library counts must be unchanged by a first-turn draw.
    """
    fixture_id = record["fixture_id"]
    required = list(record["expected_events"]["required_events"])
    forbidden = list(record["expected_events"]["forbidden_events"])
    game = drive_commander_game(
        proc,
        candidate=candidate,
        player_count=2,
        seed=424242,
        drive_to="first_turn_draw_skip",
        max_steps=60,
    )
    kinds = [entry.kind for entry in game.decision_tape]
    draw_frames = game.terminal_facts.get("draw_step_decision_frames", [])
    # Observations, not the fixture's expectations. The verdict below is derived
    # from these, and from the fixture only as a statement of the obligation.
    # They are also written into the persisted terminal facts: a verdict whose
    # guard inputs are not in the artifact cannot be audited, and the document
    # schema persists terminal_facts, not the row-local evidence dict.
    zone_counts = game.terminal_facts.get("observed_actor_zone_counts")
    baseline_counts = game.terminal_facts.get("start2_baseline_zone_counts")
    post_counts = game.terminal_facts.get("start2_post_zone_counts")
    baseline_checkpoint = game.terminal_facts.get("start2_baseline_checkpoint")
    post_checkpoint = game.terminal_facts.get("start2_post_checkpoint")
    observed_draw_events = [event for event in game.semantic_events if "draw" in str(event).lower()]
    observed_starting_actor = next(
        (
            entry.actor
            for entry in game.decision_tape
            if entry.kind.upper() != "DRAW" and entry.actor
        ),
        None,
    )
    game.terminal_facts["observed_decision_kinds"] = kinds
    game.terminal_facts["observed_draw_semantic_events"] = observed_draw_events
    game.terminal_facts["observed_starting_actor"] = observed_starting_actor
    evidence = {
        "player_count": 2,
        "actual_cards": _actual_cards(),
        "decision_tape": [entry.__dict__ for entry in game.decision_tape],
        "semantic_events": game.semantic_events,
        "terminal_facts": game.terminal_facts,
        "runtime_identity": runtime_identity,
        "evidence_class": "FRESH_CURRENT_BOUNDARY_RUNTIME",
        # Real binding from the engine's acknowledgement, not a hard-coded
        # engine_owned flag. An engine that confirms nothing leaves this
        # UNCONTROLLED and the row cannot be credited for RNG or replay.
        "rules_rng_binding": (
            game.seed_binding.to_document()
            if game.seed_binding is not None
            else {
                "control": "UNCONTROLLED_ENGINE_RNG",
                "detail": "the engine acknowledged no seed for this run",
            }
        ),
        "principal_observation_scope": "engine-offered decision frames for the acting seat",
        "v1_0_6_required_events": required,
        "v1_0_6_forbidden_events": forbidden,
        "observed_decision_kinds": kinds,
        "observed_draw_step_frames": draw_frames,
        "observed_draw_semantic_events": observed_draw_events,
        "observed_actor_zone_counts": zone_counts,
        "observed_starting_actor": observed_starting_actor,
        "fixture_required_events_are_obligation_statements_not_evidence": True,
    }
    if game.failure:
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_START2_V1_0_6",
            f"START-2 lifecycle failure: {game.failure}",
            evidence,
        )
    if draw_frames:
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_START2_V1_0_6",
            "the engine exposed a decision checkpoint inside the first-turn draw "
            "step, which CR 103.8a skips entirely; this is a current-boundary "
            "Rules-visible FAIL candidate requiring Coordinator adjudication",
            evidence,
        )
    # A draw semantic event inside the skipped step is a Rules-visible failure,
    # distinct from a draw checkpoint: either would mean the step was not
    # skipped entirely.
    if observed_draw_events:
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_START2_V1_0_6",
            "the engine emitted a draw event during the step CR 103.8a skips "
            f"entirely: {observed_draw_events}",
            evidence,
        )
    if not baseline_counts:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "no principal-scoped post-mulligan/upkeep baseline was observed before "
            "the first-turn draw step, so unchanged hand/library state is unproven",
            evidence,
        )
    if not post_counts:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "no principal-scoped precombat-main checkpoint was observed after the "
            "first-turn draw step boundary, so the START-2 postcondition is unproven",
            evidence,
        )
    if not isinstance(baseline_checkpoint, dict) or (
        baseline_checkpoint.get("turn_number"),
        baseline_checkpoint.get("phase"),
        baseline_checkpoint.get("step"),
    ) != (1, "beginning", "upkeep"):
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            f"the baseline checkpoint is not turn-1 upkeep: {baseline_checkpoint!r}",
            evidence,
        )
    if not isinstance(post_checkpoint, dict) or (
        post_checkpoint.get("turn_number") != 1 or post_checkpoint.get("phase") != "precombat_main"
    ):
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            f"the postcondition checkpoint is not turn-1 precombat main: {post_checkpoint!r}",
            evidence,
        )

    baseline = baseline_counts[0] if isinstance(baseline_counts, list) and baseline_counts else None
    post = post_counts[0] if isinstance(post_counts, list) and post_counts else None
    if not isinstance(baseline, dict) or not isinstance(post, dict):
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "START-2 zone-count records are malformed, so no state-transition credit is possible",
            evidence,
        )
    compared_fields = ("hand_count", "library_count")
    if any(
        isinstance(baseline.get(field), bool)
        or not isinstance(baseline.get(field), int)
        or isinstance(post.get(field), bool)
        or not isinstance(post.get(field), int)
        for field in compared_fields
    ):
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "START-2 hand/library counts are incomplete or non-integer",
            evidence,
        )
    if any(baseline[field] != post[field] for field in compared_fields):
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_START2_V1_0_6",
            "the starting principal's hand/library counts changed between turn-1 "
            f"upkeep and precombat main: baseline={baseline!r}, post={post!r}",
            evidence,
        )

    if not zone_counts:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "the engine reported no principal-scoped zone counts, so the "
            "hand/library postcondition of the skipped draw step could not be "
            "observed and the row is not credited",
            evidence,
        )
    if observed_starting_actor is None:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "no acting principal was observed, so which seat was the starting "
            "player could not be established from the run",
            evidence,
        )
    if not game.terminal_facts.get("priority_reached"):
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "the run did not reach an observable checkpoint after the skipped draw "
            "step, so the successor terminal postcondition could not be evaluated",
            evidence,
        )
    # The construction proof of this run: only a keyed launch carries the
    # provider's constructed state, and only an established equality lifts the
    # gap (#441 decision (c)). Without a proof the gap stays.
    proof = generic_construction_proof(record, game)
    if proof is not None:
        evidence["construction_proof"] = proof.to_document()
    gap = construction_credit_gap(record, proof)
    if gap is not None:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "the CR 103.8a obligation was observed (identical turn-1 upkeep and "
            "precombat-main hand/library counts, no draw-step checkpoint or draw "
            f"event), but {gap}",
            evidence,
        )
    return RowResult(
        fixture_id,
        candidate,
        "PASS",
        "PROTOCOL2_START2_V1_0_6",
        "CR 103.8a satisfied on the current boundary: engine-observed turn-1 "
        "upkeep and precombat-main principal views have identical hand/library "
        "counts, and no draw-step checkpoint, draw event or in-step priority was "
        "exposed between them",
        evidence,
    )


# Records whose whole obligation is a scripted pregame: every mulligan decision
# of every seat is named, in the order the rules ask them (CR 103.5).
SCRIPTED_PREGAME_ROWS = ("PILOT_MULLIGAN", "WS05-CMD-MULL-2", "WS05-CMD-MULL-4")
SCRIPTED_PREGAME_MODE = "PROTOCOL2_SCRIPTED_PREGAME"
_PLAN_ANSWERS = {"MULLIGAN": ("mulligan", False), "KEEP": ("keep_opening_hand", True)}


def scripted_pregame_plan(record: dict[str, Any]) -> tuple[tuple[str, bool], ...]:
    """The record's pregame plan as ``(seat, keep)`` entries, or ``ValueError``.

    The plan and the decision script state the same decisions twice; they must
    agree entry for entry (actor, family and answer), or the record does not
    say what to do and nothing is executed.
    """
    plan = record.get("pregame_decision_plan")
    script = record.get("decision_script")
    if isinstance(script, list):
        # A London bottom selection follows the keep it belongs to; it is no
        # keep-or-mulligan answer, so the plan names it nowhere (see
        # scripted_london_bottoms).
        script = [step for step in script if step.get("decision_family") != "london_bottom"]
    if not isinstance(plan, list) or not isinstance(script, list) or len(plan) != len(script):
        raise ValueError("the pregame plan and the decision script do not have one entry each")
    entries: list[tuple[str, bool]] = []
    for index, (planned, step) in enumerate(zip(plan, script, strict=True)):
        answer = _PLAN_ANSWERS.get(str(planned.get("decision")))
        player = str(planned.get("player_id") or "")
        selection = step.get("selection") or {}
        if (
            answer is None
            or not re.fullmatch(r"P[1-6]", player)
            or step.get("actor") != player
            or step.get("decision_family") != "mulligan"
            or selection.get("selector_kind") != "semantic_action"
            or selection.get("semantic_value") != answer[0]
        ):
            raise ValueError(f"pregame plan entry {index + 1} disagrees with the decision script")
        entries.append((player.lower(), answer[1]))
    return tuple(entries)


def record_decks(record: dict[str, Any]) -> list[dict[str, Any]]:
    """The record's requested Commander decks, one import payload per seat.

    Each seat's deck is its commander(s) from ``commander_state`` plus its
    ``library_template``; a deck that is not exactly 100 cards, or a seat the
    deck state does not cover, is a record defect and nothing is imported.
    """
    commanders = {
        str(entry.get("commander_id")): str(entry.get("card_identity"))
        for entry in (record.get("commander_state") or {}).get("commanders") or ()
    }
    by_player = {
        str(deck.get("player_id")): deck
        for deck in record.get("deck_state") or ()
        if isinstance(deck, dict)
    }
    payloads: list[dict[str, Any]] = []
    for seat in record.get("players") or ():
        player = str(seat.get("player_id"))
        deck = by_player.get(player)
        if deck is None:
            raise ValueError(f"the record's deck state does not cover {player}")
        names = [commanders.get(str(cid), "") for cid in deck.get("commander_ids") or ()]
        template = deck.get("library_template") or {}
        count = template.get("count")
        if (
            not names
            or not all(names)
            or not isinstance(count, int)
            or not template.get("card_identity")
            or len(names) + count != 100
        ):
            raise ValueError(f"the record's deck for {player} is not a 100-card Commander deck")
        mainboard = [str(template["card_identity"])] * count
        payloads.append(
            {
                "deck_id": f"{record['fixture_id']}-{player}",
                "deck_hash": hashlib.sha256(
                    "|".join([*names, *mainboard]).encode("utf-8")
                ).hexdigest(),
                "name": f"{record['fixture_id']} {player}",
                "commander_names": names,
                "mainboard": mainboard,
            }
        )
    return payloads


def scripted_london_bottoms(record: dict[str, Any]) -> list[tuple[str, Any]]:
    """The record's scripted London bottom selections as ``(seat, multiset)``."""
    return [
        (str(step.get("actor") or "").lower(), (step.get("selection") or {}).get("semantic_value"))
        for step in record.get("decision_script") or ()
        if isinstance(step, dict) and step.get("decision_family") == "london_bottom"
    ]


def _bottom_count(hands: dict[str, Any], hand_sizes: dict[str, Any], seat: str) -> int | None:
    """Cards a seat put on the bottom, from its engine-reported hand at turn 1's start."""
    seen = hands.get(seat) or {}
    checkpoint = seen.get("checkpoint") or {}
    size = hand_sizes.get(seat)
    if (
        not isinstance(size, int)
        or not isinstance(seen.get("hand_count"), int)
        or checkpoint.get("turn_number") != 1
        or checkpoint.get("phase") != "beginning"
        or checkpoint.get("step") not in ("untap", "upkeep")
    ):
        return None
    return int(size - seen["hand_count"])


def _pregame_rounds(tape: list[tuple[str, bool]]) -> dict[str, list[bool]]:
    """Each seat's answers in the order the engine asked them (its rounds)."""
    rounds: dict[str, list[bool]] = {}
    for seat, keep in tape:
        rounds.setdefault(seat, []).append(keep)
    return rounds


def _performed_mulligans(game: Any) -> dict[str, int] | None:
    """Mulligans the engine performed per seat, from its own library shuffles.

    The count at the first mulligan decision (the constructed state) against
    the count at the first priority after the pregame; None when either read
    is missing, so nothing the engine did not show is assumed.
    """
    before = getattr(game, "constructed_state", None)
    after = (getattr(game, "terminal_facts", None) or {}).get("post_pregame_library_shuffles")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None
    start: dict[str, int] = {}
    for player in before.get("players") or ():
        shuffles = player.get("library_shuffles") if isinstance(player, dict) else None
        seat = str(player.get("player_id") or "").lower() if isinstance(player, dict) else ""
        if not seat or seat in start or not isinstance(shuffles, int) or isinstance(shuffles, bool):
            # A missing, malformed or duplicated seat row makes the delta unknowable.
            return None
        start[seat] = shuffles
    if set(start) != set(after):
        return None
    if any(not isinstance(value, int) or isinstance(value, bool) for value in after.values()):
        return None
    return {seat: after[seat] - start[seat] for seat in sorted(start)}


def scripted_pregame_row(
    record: dict[str, Any],
    proc: BridgeProcess,
    *,
    candidate: str,
    runtime_identity: dict[str, Any],
) -> RowResult:
    """Execute a scripted-pregame record on the candidate-neutral lifecycle lane.

    Every mulligan frame the engine asks is answered from the record's plan, for
    the seat the engine names as its actor, in the plan's order; an unscripted,
    extra or missing frame fails closed. The obligation is then read from the
    engine: the decisions it asked (``mulligan:Pn:roundK``/``keep:Pn:roundK``)
    and each seat's hand at the first priority after the pregame
    (``bottom_count:Pn:K`` is the opening hand size minus that hand).
    """
    fixture_id = record["fixture_id"]
    required = list((record.get("expected_events") or {}).get("required_events") or ())
    players = record.get("players")
    player_count = len(players) if isinstance(players, list) else 0
    hand_sizes = {
        str(deck.get("player_id")).lower(): deck.get("opening_hand_size")
        for deck in record.get("deck_state") or ()
        if isinstance(deck, dict)
    }
    seed = int((record.get("rules_randomness") or {}).get("rules_seed") or 424242)
    evidence: dict[str, Any] = {
        "player_count": player_count,
        "actual_cards": _actual_cards(),
        "runtime_identity": runtime_identity,
        "evidence_class": "FRESH_CURRENT_BOUNDARY_RUNTIME",
        "principal_observation_scope": "engine-offered decision frames for the acting seat",
        "fixture_required_events_are_obligation_statements_not_evidence": True,
    }
    try:
        plan = scripted_pregame_plan(record)
        decks = record_decks(record)
    except ValueError as exc:
        return RowResult(
            fixture_id, candidate, "UNKNOWN", SCRIPTED_PREGAME_MODE, str(exc), evidence
        )
    bottoms = scripted_london_bottoms(record)
    if bottoms:
        # The bottom card is the player's own choice (CR 103.5), so the Lab
        # never selects it and no default may answer it. This lane has no
        # external London bottom surface: the XMage generic lane refuses the
        # selection as UNSUPPORTED_COMPATIBILITY_DECISION and the pinned Forge
        # bridge never answers an owed tuck. Nothing is executed.
        evidence["scripted_london_bottoms"] = [[seat, value] for seat, value in bottoms]
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            SCRIPTED_PREGAME_MODE,
            "the record scripts a London bottom selection "
            f"({', '.join(seat.upper() for seat, _ in bottoms)}), and this lane offers no "
            "external bottom-card decision; the Lab never chooses the card for the player",
            evidence,
        )
    evidence["requested_decks"] = [
        {"deck_id": deck["deck_id"], "deck_hash": deck["deck_hash"]} for deck in decks
    ]
    game = drive_commander_game(
        proc,
        candidate=candidate,
        player_count=player_count,
        seed=seed,
        drive_to="priority",
        max_steps=80,
        mulligan_plan=plan,
        decks=decks,
    )
    asked = [
        (str(entry.seat), bool(entry.keep))
        for entry in game.decision_tape
        if entry.step == "mulligan"
    ]
    hands = game.terminal_facts.get("post_pregame_zone_counts") or {}
    evidence.update(
        {
            "decision_tape": [entry.__dict__ for entry in game.decision_tape],
            "semantic_events": game.semantic_events,
            "terminal_facts": game.terminal_facts,
            "rules_rng_binding": (
                game.seed_binding.to_document()
                if game.seed_binding is not None
                else {
                    "control": "UNCONTROLLED_ENGINE_RNG",
                    "detail": "the engine acknowledged no seed for this run",
                }
            ),
            "scripted_pregame_plan": [list(entry) for entry in plan],
            "observed_pregame_decisions": [list(entry) for entry in asked],
        }
    )
    if game.failure:
        # A lane or provider failure proves nothing about the obligation either
        # way; it is recorded, not credited and not called a Rules failure.
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            SCRIPTED_PREGAME_MODE,
            f"the scripted pregame did not complete: {game.failure}",
            evidence,
        )
    if game.terminal_facts.get("created_player_count") != player_count:
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            SCRIPTED_PREGAME_MODE,
            f"engine created {game.terminal_facts.get('created_player_count')} players for a "
            f"{player_count}P fixture",
            evidence,
        )
    if asked != list(plan):
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            SCRIPTED_PREGAME_MODE,
            f"the engine's pregame decisions {asked} are not the record's plan {list(plan)}",
            evidence,
        )
    rounds = _pregame_rounds(asked)
    unmet: list[str] = []
    # The engine's own evidence that each answered mulligan was performed: a
    # London mulligan shuffles the hand back into the library (CR 103.5), so a
    # seat's library-shuffle count rises by exactly its mulligans between the
    # first mulligan decision and the first priority. Accepted answers alone
    # (the decision tape) are not evidence that the engine redrew anything.
    performed = _performed_mulligans(game)
    evidence["engine_performed_mulligans"] = performed
    mulligan_backed = performed is not None and all(
        performed.get(seat) == answers.count(False) for seat, answers in rounds.items()
    )
    # The gate follows the plan, not the wording of the record's tokens: any
    # mulligan the run answered must be backed by the engine's own shuffles,
    # whatever the required events name (#553 Audit 1 B4).
    plan_mulligans = any(not keep for answers in rounds.values() for keep in answers)
    # The seats that took exactly one mulligan and then kept: the subject of
    # mulligan_once and free_mulligan (CR 103.5c makes that one free in a game
    # of more than two players).
    once = sorted(
        seat
        for seat, answers in rounds.items()
        if answers.count(False) == 1 and answers and answers[-1] is True
    )
    for token in required:
        decided = re.fullmatch(r"(mulligan|keep):(P[1-6]):round([1-9])", token)
        bottomed = re.fullmatch(r"bottom_count:(P[1-6]):([0-9]+)", token)
        mulligan_once = re.fullmatch(r"mulligan_once:(P[1-6])", token)
        free = re.fullmatch(r"free_mulligan:(true|false)", token)
        if (mulligan_once or free or (decided and decided.group(1) == "mulligan")) and not (
            mulligan_backed
        ):
            unmet.append(token)
        elif mulligan_once:
            if mulligan_once.group(1).lower() not in once:
                unmet.append(token)
        elif free:
            # The one seat that mulliganed once, and the cards it bottomed: none
            # for a free mulligan, one otherwise.
            count = _bottom_count(hands, hand_sizes, once[0]) if len(once) == 1 else None
            if count is None or count != (0 if free.group(1) == "true" else 1):
                unmet.append(token)
        elif decided:
            seat, round_number = decided.group(2).lower(), int(decided.group(3))
            answers = rounds.get(seat) or []
            wanted_keep = decided.group(1) == "keep"
            if round_number > len(answers) or answers[round_number - 1] != wanted_keep:
                unmet.append(token)
        elif bottomed:
            count = _bottom_count(hands, hand_sizes, bottomed.group(1).lower())
            if count is None or count != int(bottomed.group(2)):
                unmet.append(token)
        else:
            unmet.append(token)
    if plan_mulligans and not mulligan_backed:
        unmet.append("cr103.5:engine_performed_mulligans")
    evidence["unmet_required_events"] = unmet
    if unmet:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            SCRIPTED_PREGAME_MODE,
            f"the engine-observed pregame does not establish {unmet}",
            evidence,
        )
    # The record's own credit conditions, beyond the observed obligation: its
    # seeded shuffles must run under the engine-acknowledged Rules seed, and its
    # construction_validation requires the provider's normalized constructed
    # state to equal the requested state. The generic lane emits no constructed
    # state, so there the obligation is observed but the row is not credited.
    if game.seed_binding is None or not game.seed_binding.controlled:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            SCRIPTED_PREGAME_MODE,
            "the obligation was observed, but the engine did not acknowledge the record's "
            f"Rules seed {seed}, so the record's seeded shuffles are not established",
            evidence,
        )
    proof = generic_construction_proof(record, game)
    if proof is not None:
        evidence["construction_proof"] = proof.to_document()
    gap = construction_credit_gap(record, proof)
    if gap is not None:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            SCRIPTED_PREGAME_MODE,
            "the obligation was observed on the record's decks under the acknowledged "
            f"Rules seed, but {gap}",
            evidence,
        )
    return RowResult(
        fixture_id,
        candidate,
        "PASS",
        SCRIPTED_PREGAME_MODE,
        f"real {player_count}P Commander pregame executed under Protocol "
        f"{CURRENT_TRANSPORT_PROTOCOL}: the engine asked exactly the record's mulligan "
        "decisions in order, each answered from the record's plan, and every seat's "
        "engine-reported hand at the first priority states the bottom counts",
        evidence,
    )


def non_executed_row(
    record: dict[str, Any],
    *,
    candidate: str,
    outcome: str,
    reason: str,
    runtime_identity: dict[str, Any],
    evidence_class: str = "NOT_EXECUTED_CURRENT_BOUNDARY",
) -> RowResult:
    """Record an explicit non-PASS outcome with its exact reason."""
    return RowResult(
        record["fixture_id"],
        candidate,
        outcome,
        "NO_CURRENT_BOUNDARY_EXECUTION_SEAM",
        reason,
        {
            "player_count": record.get("player_count"),
            "actual_cards": None,
            "decision_tape": [],
            "semantic_events": [],
            "terminal_facts": {},
            "runtime_identity": runtime_identity,
            "evidence_class": evidence_class,
            "rules_rng_binding": None,
            "principal_observation_scope": None,
        },
    )


def observe_principal_state(
    proc: BridgeProcess,
    game_id: str,
    *,
    seat: str,
) -> dict[str, Any]:
    """Read one principal-scoped state observation."""
    response = proc.request(
        "get_game_state", {"observer_player_id": seat}, game_id=game_id, timeout_s=60.0
    )
    if not response.get("success"):
        return {"error": response.get("errors")}
    payload = response.get("payload")
    return payload if isinstance(payload, dict) else {}


def export_replay(proc: BridgeProcess, game_id: str) -> dict[str, Any]:
    response = proc.request("export_replay", {}, game_id=game_id, timeout_s=90.0)
    if not response.get("success"):
        return {"error": response.get("errors")}
    payload = response.get("payload")
    return payload if isinstance(payload, dict) else {}


def new_game_id(candidate: str, label: str) -> str:
    return f"wsr22-{candidate}-{label}-{uuid.uuid4().hex[:8]}"


def wait_for_frame(
    proc: BridgeProcess, game_id: str, *, seat_count: int, candidate: str
) -> dict[str, Any] | None:  # pragma: no cover - helper
    try:
        return poll_decision(proc, game_id, seat_count=seat_count, candidate=candidate)
    except Exception:
        return None


def summarize(rows: list[RowResult]) -> dict[str, int]:
    counts = {outcome: 0 for outcome in OUTCOMES}
    for row in rows:
        counts[row.outcome] = counts.get(row.outcome, 0) + 1
    return counts


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def sleep(seconds: float) -> None:
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Principal scoping must be validated before an observation is persisted as
# principal-scoped evidence.
# ---------------------------------------------------------------------------
#
# The hidden-information loop used to read one state observation per seat and
# write all of them straight into HIDDEN_INFO_<CANDIDATE>.json. Nothing checked
# that the response was actually scoped to the seat that asked for it. The
# committed XMage run demonstrates the failure this permits: all four entries
# held identical state payloads, including stable object ids and ordering for
# every opponent's seven-card hand and ninety-two-card library. Persisting that
# under four principal labels presents one unscoped view as four scoped ones.
#
# Masking identifiers at the provider is necessary but not sufficient, because a
# provider can still return the same unscoped payload to every caller. The
# observation has to be checked where it is trusted, which is here.

# Keys whose values describe a principal's own hidden content. Counts are not
# hidden; card identities and ordering are.
_HIDDEN_CONTENT_KEYS: frozenset[str] = frozenset({"hand", "library", "revealed", "face_down_cards"})


# A provider that correctly hides a zone usually says so with a placeholder
# rather than omitting the zone. A placeholder is the ABSENCE of content, so
# counting it as content accuses a candidate of a leak it did not commit. The
# Forge bridge returns "<hidden>" per opponent card; treating that array as
# exposed hand content produced a false ENGINE_CANDIDATE_DEFECT against a
# provider that was redacting correctly.
_REDACTION_PLACEHOLDERS: frozenset[str] = frozenset(
    {"<hidden>", "hidden", "***", "<redacted>", "redacted", "?", "null", "none", ""}
)


def _zone_exposes_content(zone: Any) -> bool:
    """Whether a zone carries real content rather than a redaction placeholder.

    An empty list, a null, or a list made entirely of placeholders means nothing
    was disclosed. A list containing at least one real entry means it was.
    """
    if zone is None:
        return False
    if isinstance(zone, (str, int, float, bool)):
        return str(zone).strip().lower() not in _REDACTION_PLACEHOLDERS
    if isinstance(zone, dict):
        # An object is real content unless every value is a placeholder.
        return any(_zone_exposes_content(value) for value in zone.values())
    if isinstance(zone, (list, tuple, set)):
        return any(_zone_exposes_content(item) for item in zone)
    return bool(zone)


def _state_view(payload: dict[str, Any]) -> dict[str, Any]:
    """The state view inside a principal observation.

    The observation wraps the state under ``state``; the players array lives
    there, not at the top level. Reading the top level produced a false
    "no players array" finding against a correctly shaped response, which is
    exactly as bad as missing a real leak: a scoping verdict must be true, not
    merely conservative.
    """
    state = payload.get("state")
    return state if isinstance(state, dict) else payload


def _players_of(payload: dict[str, Any]) -> list[Any]:
    players = _state_view(payload).get("players")
    return players if isinstance(players, list) else []


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


# Provider requester-binding metadata is not observed content. The distinctness
# check compares what each principal actually observed; if the binding fields
# were included, a provider could return one identical unscoped payload to every
# requester while varying only the marker, and four identical views would look
# distinct. Excluding the binding metadata makes the comparison stricter, which
# is the safe direction for a leak check; the fields themselves are still
# consumed by the binding checks above and by no_opponent_hidden_content below.
# The monotonic `state_observation_offset` lives outside the state view and is
# excluded by construction, because only the state view is compared.
_BINDING_STATE_KEYS: frozenset[str] = frozenset(
    {
        "observer_player_id",
        "observer_engine_player_id",
        "observer_seat",
        "state_observation_offset",
    }
)
_BINDING_PLAYER_KEYS: frozenset[str] = frozenset({"is_actor"})


def _content_view(payload: dict[str, Any]) -> dict[str, Any]:
    """The state view without provider requester-binding metadata."""
    content = {
        key: value for key, value in _state_view(payload).items() if key not in _BINDING_STATE_KEYS
    }
    players = content.get("players")
    if isinstance(players, list):
        content["players"] = [
            (
                {key: value for key, value in entry.items() if key not in _BINDING_PLAYER_KEYS}
                if isinstance(entry, dict)
                else entry
            )
            for entry in players
        ]
    return content


def validate_principal_scoping(
    observations: dict[str, Any], *, requested_seats: tuple[str, ...]
) -> dict[str, Any]:
    """Check that each observation is genuinely scoped to the seat that asked.

    Returns a verdict mapping. A failing check is never repaired by rewriting the
    observation: the observation is what the engine said, and the correct
    response is to refuse to present it as principal-scoped evidence.
    """
    findings: list[dict[str, Any]] = []

    usable = {
        seat: payload
        for seat, payload in observations.items()
        if isinstance(payload, dict) and "error" not in payload
    }
    for seat in requested_seats:
        if seat not in usable:
            findings.append(
                {
                    "check": "observation_present",
                    "seat": seat,
                    "ok": False,
                    "detail": "no usable principal observation was returned for this seat",
                }
            )

    # Each observation must bind exactly one live principal to the requester.
    # A provider may do this either with an in-state is_actor marker or with a
    # response-envelope binding that carries the exact requested external id,
    # resolved live engine id and seat. The envelope is accepted only when the
    # resolved engine id equals the player id at that seat in the scoped state;
    # merely echoing caller input is not enough.
    established_requester: dict[str, bool] = {}
    actor_seat_by_observation: dict[str, int | None] = {}
    for seat, payload in usable.items():
        players = _players_of(payload)
        established_requester[seat] = False
        actor_seat_by_observation[seat] = None
        if not players:
            findings.append(
                {
                    "check": "actor_marked",
                    "seat": seat,
                    "ok": False,
                    "detail": "the observation carries no players array to scope against",
                }
            )
            continue

        expected_seat = _seat_index(requested_seats, seat)
        actors = [
            entry for entry in players if isinstance(entry, dict) and entry.get("is_actor") is True
        ]
        marker_bound = (
            len(actors) == 1
            and expected_seat is not None
            and actors[0].get("seat") == expected_seat
        )

        envelope_fields_present = any(
            key in payload
            for key in ("observer_player_id", "observer_engine_player_id", "observer_seat")
        )
        envelope_bound = False
        if expected_seat is not None and 0 <= expected_seat < len(players):
            expected_entry = players[expected_seat]
            envelope_engine_id = payload.get("observer_engine_player_id")
            envelope_bound = (
                isinstance(expected_entry, dict)
                and payload.get("observer_player_id") == seat
                and payload.get("observer_seat") == expected_seat
                and isinstance(envelope_engine_id, str)
                and bool(envelope_engine_id)
                and expected_entry.get("player_id") == envelope_engine_id
            )

        if envelope_fields_present and not envelope_bound:
            findings.append(
                {
                    "check": "observer_binding",
                    "seat": seat,
                    "ok": False,
                    "detail": "observer envelope does not bind the requested seat to the "
                    "live player id present at that seat",
                }
            )

        # If both mechanisms are present they may not disagree. A valid
        # envelope must not be allowed to hide a contradictory in-state actor
        # marker, nor vice versa.
        marker_conflicts = bool(actors) and not marker_bound
        if envelope_bound and marker_conflicts:
            findings.append(
                {
                    "check": "actor_binding_conflict",
                    "seat": seat,
                    "ok": False,
                    "detail": "the response envelope binds the requester but the in-state "
                    "actor marker identifies a different or ambiguous principal",
                }
            )

        if marker_bound or (envelope_bound and not marker_conflicts):
            established_requester[seat] = True
            actor_seat_by_observation[seat] = expected_seat
            continue

        if len(actors) != 1:
            findings.append(
                {
                    "check": "actor_marked",
                    "seat": seat,
                    "ok": False,
                    "detail": f"expected exactly one actor in the observation, saw {len(actors)}",
                }
            )
            continue

        observed_seat = actors[0].get("seat")
        if expected_seat is not None and observed_seat != expected_seat:
            findings.append(
                {
                    "check": "actor_is_the_requester",
                    "seat": seat,
                    "ok": False,
                    "detail": f"the observation marks seat {observed_seat} as actor, but seat "
                    f"{seat} requested it",
                }
            )

    # Two principals cannot receive the same view. The comparison is over the
    # STATE VIEW, not the whole observation envelope. The envelope carries a
    # monotonically increasing `state_observation_offset`, so comparing it would
    # make four byte-identical states look like four distinct observations and
    # mask exactly the leak this check exists to catch. Provider requester-
    # binding metadata is excluded for the same reason: marking the observer is
    # not observation content.
    distinct = {_canonical(_content_view(usable[seat])) for seat in usable}
    if len(usable) > 1 and len(distinct) == 1:
        findings.append(
            {
                "check": "observations_differ_per_principal",
                "ok": False,
                "detail": f"all {len(usable)} principals received a byte-identical state "
                "payload, so the projection is not principal-scoped",
            }
        )

    # No observation may carry another principal's hidden card content.
    for seat, payload in usable.items():
        for entry in _players_of(payload):
            if not isinstance(entry, dict):
                continue
            raw_zones = entry.get("zones")
            zones: dict[str, Any] = raw_zones if isinstance(raw_zones, dict) else entry
            exposed = sorted(
                key for key in _HIDDEN_CONTENT_KEYS if _zone_exposes_content(zones.get(key))
            )
            entry_is_actor = entry.get("is_actor") is True
            if (
                not entry_is_actor
                and established_requester.get(seat, False)
                and actor_seat_by_observation.get(seat) == entry.get("seat")
            ):
                entry_is_actor = True
            if exposed and not entry_is_actor:
                findings.append(
                    {
                        "check": "no_opponent_hidden_content",
                        "seat": seat,
                        "ok": False,
                        "detail": f"the observation exposes opponent zone content {exposed} "
                        "for a non-actor seat",
                    }
                )

    # Classify the defect, because the two have different owners and the
    # difference matters. An ENGINE leak is a candidate defect: the provider
    # returned unauthorised identity or content and the Lab must not mask it.
    # A SERIALIZER leak is a Lab defect: the response was correctly scoped and
    # the Lab persisted extra identity. Masking an engine leak in the serializer
    # and then awarding engine correctness credit is forbidden, so the
    # classification is derived from what the observation actually contains.
    # The zone keys observed on a non-actor seat. This is the RAW observation, and
    # it is deliberately kept separate from engine_leak_indicators below: a key
    # appearing here says content sat on a seat that was not marked as the
    # requester's, which is not the same as a demonstrated leak.
    exposed_keys = sorted(
        {
            key
            for finding in findings
            if finding.get("check") == "no_opponent_hidden_content"
            for key in _exposed_keys_of(finding.get("detail", ""))
        }
    )
    # A content leak is only DEMONSTRATED when the evidence forces it. Two
    # different things must not be conflated:
    #
    #   * Two requesters receiving a byte-identical state proves an unscoped
    #     projection outright. The requester differs and the payload does not, so
    #     each caller necessarily sees every other seat's cards. That is a
    #     conclusive candidate defect.
    #   * Real content present while the provider does not mark the observing
    #     principal proves nothing on its own: the content may belong to the
    #     requester. Without actor marking the validator cannot tell who was
    #     asked, so attributing a leak to the candidate would be an accusation
    #     the evidence does not support.
    #
    # A provider that redacts opponents with placeholders and simply omits the
    # actor marker is unestablished, not defective.
    identical_views = any(
        finding.get("check") == "observations_differ_per_principal" for finding in findings
    )
    # A leaked-content finding is attributed to the observation that produced it.
    # A batch-wide flag is wrong in both directions: one response missing its
    # actor marker must not downgrade a demonstrated leak in every OTHER
    # response, and one response carrying a leak must not upgrade the rest.
    leaked_from_established = any(
        finding.get("check") == "no_opponent_hidden_content"
        and established_requester.get(str(finding.get("seat", "")), False)
        for finding in findings
    )
    if not findings:
        attribution = "NONE"
    elif identical_views or leaked_from_established:
        attribution = "ENGINE_CANDIDATE_DEFECT"
    elif exposed_keys:
        attribution = "SCOPING_NOT_ESTABLISHED_ACTOR_MARKING_ABSENT"
    else:
        attribution = "LAB_SERIALIZER_DEFECT"
    engine_leak = attribution == "ENGINE_CANDIDATE_DEFECT"

    return {
        "verdict": "PRINCIPAL_SCOPED" if not findings else "SCOPING_NOT_ESTABLISHED",
        "attribution": attribution,
        # Populated ONLY for a demonstrated leak. Listing zones here for an
        # unestablished case would restate the accusation the attribution just
        # declined to make.
        "engine_leak_indicators": exposed_keys if engine_leak else [],
        "zones_observed_on_unmarked_seats": exposed_keys,
        "observations_with_established_requester": sorted(
            seat for seat, ok in established_requester.items() if ok
        ),
        "observations_without_established_requester": sorted(
            seat for seat, ok in established_requester.items() if not ok
        ),
        "attribution_rule": "one shared state view across different requesters is a "
        "conclusive candidate defect, and real content for a KNOWN non-actor is too. A "
        "requester may be established by an exact in-state actor marker or by an observer "
        "envelope whose requested id, live engine id and seat agree with the scoped state. "
        "Real content without either binding is unestablished, not a demonstrated leak. "
        "A masked engine leak must never earn engine correctness credit, and an "
        "undemonstrated one must never be asserted.",
        "credible_as_principal_scoped_evidence": not findings,
        "principals_checked": sorted(usable),
        "distinct_state_views": len(distinct),
        "compared": "the state view, excluding the observation envelope whose "
        "monotonic offset would otherwise make identical states look distinct",
        "findings": findings,
        "note": "an observation that is not principal-scoped is recorded as observed and is "
        "not presented as hidden-information evidence",
    }


def _exposed_keys_of(detail: str) -> list[str]:
    """Recover the exposed zone names from a finding's detail text."""
    marker = "zone content ["
    if marker not in detail:
        return []
    tail = detail.split(marker, 1)[1]
    # The detail ends with prose after the bracketed list, so cut at "]".
    inside = tail.split("]", 1)[0]
    return [item.strip().strip("'\"") for item in inside.split(",") if item.strip()]


def _seat_index(seats: tuple[str, ...], seat: str) -> int | None:
    lowered = seat.lower()
    for index, candidate in enumerate(seats):
        if candidate.lower() == lowered:
            return index
    return None
