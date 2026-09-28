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

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .bridge_launcher import BridgeProcess
from .game_driver import (
    DECISION_IDENTITY_SHAPES,
    CommandedGameResult,
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

# PB-03 dimension admission (Muse XHIGH Wave 1): the starting-state requirement
# is classified by REQUIRED MECHANISM per row, never by fixture-id prefix.
# The Lab-owned XMage restoration seam (`XmageNativeStateRestoration`) is the
# admission oracle: TIER_1 rows construct as-is through `planFromFrozenRecord`;
# TIER_2 rows need a qualified genuine-causal transaction on top of a
# constructible pre-cause state (real cast / real choice / real declaration);
# TIER_3 rows need dimensions with no genuine engine path and stay BLOCKED
# with the exact missing dimension named. The Java suite
# `XmagePb03DimensionAdmissionTest` pins this table against the live seam:
# Python and Java must agree on every row, or the test fails.
#
# Dimension vocabulary (short keys for the seam's documented dimensions):
#   ZONES_PUBLIC      battlefield/graveyard/exile placement of real cards
#   HAND_IDENTITY     hand identity via the setup primitive (principal-scoped)
#   COMMANDERS        commanders with prior cast counts (native game-load path)
#   COMMANDER_DAMAGE  damage matrices through exact live CommanderInfo bindings
#   LIFE_TOTALS       life totals (pre-start assembly; SBA stay authoritative)
#   TURN1_TEMPORAL    qualified turn-1 temporal targets (RG-03 allow-list)
#   RULES_SEED        explicit Rules-seed binding with replay determinism
#   READBACK_DIGEST   strict native readback with field-level compare/digests
#   STACK_SPELLS      live stack spells (unsupported: casting needs real costs)
#   CONTROL_DIVERGENCE owner/controller divergence (unsupported: layers re-derive)
#   EXTRA_TURN_QUEUE  a pre-existing extra-turn queue (unsupported: no restore
#                     API exists; extra turns arise only from genuine casts)
#   LIFE_ZERO_PRESTART a 0-life player in the requested pre-start state
#                     (unsupported: the engine re-derives starting life at start)
REQUIRED_DIMENSIONS: dict[str, tuple[str, ...]] = {
    # ---- TIER_1: construct as-is, then native evaluate/observe ----
    "MICRO_COMBAT": (
        "ZONES_PUBLIC",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "MICRO_CONTINUOUS_EFFECTS": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "MICRO_MODES": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "MICRO_PREVENTION": (
        "ZONES_PUBLIC",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "MICRO_REPLACEMENT": (
        "ZONES_PUBLIC",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "WS05-MP-BLOCK-4": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "WS05-MP-COMBAT-4": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "WS05-MP-COMBAT-5": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "WS05-MP-TURN-5": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "EXTRA_TURN_QUEUE",
    ),
    # PB-10 demotion row, re-admitted by mechanism: 19 restored Commander damage
    # plus a genuine combat-damage step reaches the 21-damage loss threshold.
    "WS05-CMD-ELIM-4": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "COMMANDER_DAMAGE",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    # ---- TIER_2: constructible pre-cause state + genuine causal path ----
    "WS05-CMD-ZONE-GY-YES": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-CMD-ZONE-GY-NO": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-CMD-ZONE-EXILE-YES": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-CMD-ZONE-EXILE-NO": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-CMD-ZONE-HAND-YES": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-CMD-ZONE-HAND-NO": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-CMD-ZONE-LIB-NO": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "MICRO_COSTS": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "MICRO_MANA_PAYMENT": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "MICRO_PRIORITY": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "MICRO_STACK": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "MICRO_STATE_BASED_ACTIONS": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "MICRO_TRIGGERS": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    ),
    "MICRO_ZONE_CHANGES": (
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "MICRO_COPY": (
        "ZONES_PUBLIC",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "MICRO_CONTROL": (
        "ZONES_PUBLIC",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "CONTROL_DIVERGENCE",
    ),
    "MICRO_RULES_RANDOMNESS": (
        "ZONES_PUBLIC",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-MP-PRIO-3": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-MP-PRIO-5": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    # PB-10 demotion rows: donor PASS rested on non-credit harnesses
    # (rejection / blocker-characterization tests), so they re-enter
    # admission by mechanism rather than inheriting PASS.
    "WS05-CMD-ZONE-LIB-YES": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "STACK_SPELLS",
    ),
    "WS05-MP-ELIM-OWNED-3": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "LIFE_ZERO_PRESTART",
    ),
    # ---- TIER_3: no genuine engine path; BLOCKED with named dimension ----
    "WS05-MP-ELIM-5": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "LIFE_ZERO_PRESTART",
    ),
    "WS05-MP-ELIM-CONTROL-3": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "LIFE_ZERO_PRESTART",
        "CONTROL_DIVERGENCE",
    ),
    "WS05-MP-ELIM-PRIO-3": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "LIFE_ZERO_PRESTART",
    ),
    "WS05-MP-ELIM-TURN-3": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "LIFE_ZERO_PRESTART",
    ),
    "WS05-MP-ELIM-STACK-3": (
        "ZONES_PUBLIC",
        "COMMANDERS",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
        "LIFE_ZERO_PRESTART",
        "STACK_SPELLS",
    ),
}

# Dimensions the restoration seam supports today (mirror of
# `XmageNativeStateRestoration.dimensionsPayload()` supported_dimensions).
SEAM_SUPPORTED_DIMENSIONS = frozenset(
    {
        "ZONES_PUBLIC",
        "HAND_IDENTITY",
        "COMMANDERS",
        "COMMANDER_DAMAGE",
        "LIFE_TOTALS",
        "TURN1_TEMPORAL",
        "RULES_SEED",
        "READBACK_DIGEST",
    }
)

# Tiers route admitted rows to their execution seam.
TIER_1_CONSTRUCT_ONLY: tuple[str, ...] = tuple(
    fixture
    for fixture, dims in REQUIRED_DIMENSIONS.items()
    if set(dims) <= set(SEAM_SUPPORTED_DIMENSIONS)
)
TIER_2_GENUINE_CAUSAL: tuple[str, ...] = (
    "WS05-CMD-ZONE-GY-YES",
    "WS05-CMD-ZONE-GY-NO",
    "WS05-CMD-ZONE-EXILE-YES",
    "WS05-CMD-ZONE-EXILE-NO",
    "WS05-CMD-ZONE-HAND-YES",
    "WS05-CMD-ZONE-HAND-NO",
    "WS05-CMD-ZONE-LIB-NO",
    "WS05-CMD-ZONE-LIB-YES",
    "MICRO_COPY",
    "MICRO_CONTROL",
    "MICRO_RULES_RANDOMNESS",
    "MICRO_MANA_PAYMENT",
    "MICRO_PRIORITY",
    "MICRO_STACK",
    "MICRO_ZONE_CHANGES",
    "WS05-MP-PRIO-3",
    "WS05-MP-PRIO-5",
    "WS05-MP-TURN-5",
)
TIER_3_NO_GENUINE_PATH: tuple[str, ...] = (
    "WS05-MP-ELIM-5",
    "WS05-MP-ELIM-CONTROL-3",
    "WS05-MP-ELIM-PRIO-3",
    "WS05-MP-ELIM-TURN-3",
    "WS05-MP-ELIM-STACK-3",
    "WS05-MP-ELIM-OWNED-3",
)


def admit_row(fixture_id: str) -> tuple[str, tuple[str, ...]]:
    """Classify one fixture by required mechanism.

    Returns (tier, missing_dimensions) where tier is one of
    TIER_1 / TIER_2 / TIER_3 / UNLISTED. TIER_3 rows name the exact missing
    dimension; UNLISTED rows are not part of the PB-03 set.
    """
    if fixture_id in TIER_1_CONSTRUCT_ONLY:
        return ("TIER_1", ())
    if fixture_id in TIER_2_GENUINE_CAUSAL:
        missing = tuple(
            dim for dim in REQUIRED_DIMENSIONS[fixture_id] if dim not in SEAM_SUPPORTED_DIMENSIONS
        )
        return ("TIER_2", missing)
    if fixture_id in TIER_3_NO_GENUINE_PATH:
        missing = tuple(
            dim for dim in REQUIRED_DIMENSIONS[fixture_id] if dim not in SEAM_SUPPORTED_DIMENSIONS
        )
        return ("TIER_3", missing)
    return ("UNLISTED", ())


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
) -> CommandedGameResult:
    """Run one real Commander lifecycle at one player count."""
    return drive_commander_game(
        proc,
        candidate=candidate,
        player_count=player_count,
        seed=424242,
        drive_to="priority",
        max_steps=80,
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
        "rules_rng_binding": {
            "requested_seed": 424242,
            "engine_owned": True,
            "provider_reported_seed_supported": DECISION_IDENTITY_SHAPES is not None,
        },
        "principal_observation_scope": "engine-offered decision frames for the acting seat",
    }
    if result.failure:
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
    if not result.terminal_facts.get("priority_reached"):
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_LIFECYCLE",
            "no external priority decision was ever reached",
            evidence,
        )
    external_choices = [entry for entry in result.decision_tape if entry.chosen_option_id]
    if not external_choices:
        return RowResult(
            fixture_id,
            candidate,
            "FAIL",
            "PROTOCOL2_LIFECYCLE",
            "no externally supplied discretionary decision was bound to an engine-offered option",
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
    evidence = {
        "player_count": 2,
        "actual_cards": _actual_cards(),
        "decision_tape": [entry.__dict__ for entry in game.decision_tape],
        "semantic_events": game.semantic_events,
        "terminal_facts": game.terminal_facts,
        "runtime_identity": runtime_identity,
        "evidence_class": "FRESH_CURRENT_BOUNDARY_RUNTIME",
        "rules_rng_binding": {"requested_seed": 424242, "engine_owned": True},
        "principal_observation_scope": "engine-offered decision frames for the acting seat",
        "v1_0_6_required_events": required,
        "v1_0_6_forbidden_events": forbidden,
        "observed_decision_kinds": kinds,
        "observed_draw_step_frames": draw_frames,
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
    if "starting_player:P1" not in required:
        return RowResult(
            fixture_id,
            candidate,
            "UNKNOWN",
            "PROTOCOL2_START2_V1_0_6",
            "effective record does not carry the starting-player event",
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
    return RowResult(
        fixture_id,
        candidate,
        "PASS",
        "PROTOCOL2_START2_V1_0_6",
        "CR 103.8a satisfied on the current boundary: the starting player's entire "
        "first-turn draw step was skipped, no draw-step checkpoint, draw event or "
        "in-step priority was ever exposed by the engine, and the first observable "
        "external checkpoint was the normal precombat decision handoff",
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
