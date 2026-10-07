"""Forge AF06/AF08 residuals: the first missing mechanism per row (#459).

Forge is measured on the same micro-rules (``MICRO_*``), pilot-decision
(``PILOT_*``) and multiplayer/Commander (``WS05-*``) rows as XMage. A row the
Forge scenario lane does not execute to a receipt stays UNKNOWN or BLOCKED;
this module names *why*, in pipeline order, so no row hides behind a generic
"no execution seam".

A row passes through three stages, and its class is the first stage that is
missing a mechanism:

1. **Construction** (``forge_scenario_lane.model_requested_state``, the lane's
   own model; there is no second translation):

   - a dimension the provider has no field or channel for, and that no engine
     action can cause either, is a ``PROVIDER_ADAPTER_GAP``;
   - a dimension the engine *can* cause on its own decision frames (a cast, a
     payment, an attack, a turn reached by native progression) is a
     ``LAB_EXECUTION_GAP``: the Forge lane implements no selector for that
     frame family, although the bridge offers the frames;
   - a requested field the generic readback cannot show (owner, attachment,
     object identity in a public zone) is a ``PROVIDER_ADAPTER_GAP`` of
     observation: checkpoint equivalence cannot be proven.

2. **Execution**: the record's scripted decision families, each a
   ``LAB_EXECUTION_GAP`` while the lane has no selector for it.

3. **Observation**: each required obligation token is observable through the
   state readback, through the engine's own decision frames (the decision
   tape), or only through an engine event stream. The pinned bridge exports no
   event log (``EVENT_LOG_UNSUPPORTED``), so an event-only token is a
   ``PROVIDER_ADAPTER_GAP``. A readback or frame token whose observation
   contract the lane does not implement is a ``LAB_EXECUTION_GAP``.

Nothing here executes a row, writes a receipt or promotes credit, and no row's
outcome changes: only its reason becomes exact. An unmapped dimension or token
raises instead of defaulting to a class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import forge_scenario_lane as lane

SCHEMA_VERSION = "commander-lab.forge-residuals/1.0.0"

SCOPE_PREFIXES = ("MICRO_", "PILOT_", "WS05-")

PROVIDER_ADAPTER_GAP = "PROVIDER_ADAPTER_GAP"
LAB_EXECUTION_GAP = "LAB_EXECUTION_GAP"
SCENARIO_LANE_EXECUTABLE = "SCENARIO_LANE_EXECUTABLE"
# The record itself lacks the authority execution needs (e.g. a scripted
# response for a discretionary decision). Neither Lab nor provider work closes
# it; only a Coordinator-adjudicated contract erratum can.
CONTRACT_AUTHORITY_GAP = "CONTRACT_AUTHORITY_GAP"

READBACK = "READBACK"
DECISION_FRAME = "DECISION_FRAME"
EVENT_LOG = "EVENT_LOG"

_CAUSAL_ROUTE_SCOPE = (
    "the lane casts only through its causal stack route (#520, #561): complete, modeless "
    "spells with declared fuel, either one aimed at a commander for a commander zone "
    "choice to the graveyard, exile or hand, or a stack the record's scripted priority "
    "cast, targets and declared payment answer (scripted_decision_offered)"
)

# Construction dimensions of the lane's model (``hard_unsupported``), by exact
# dimension or by prefix (``decision_execution.<family>.<selector>``).
_CONSTRUCTION: dict[str, tuple[str, str]] = {
    "stack_state": (
        LAB_EXECUTION_GAP,
        "a stack object is caused by a cast on the engine's own frames (the bootstrap "
        "rejects stack injection); " + _CAUSAL_ROUTE_SCOPE,
    ),
    "semantic_objects.zone:stack": (
        LAB_EXECUTION_GAP,
        "a requested stack object is caused by a cast on the engine's own frames; "
        + _CAUSAL_ROUTE_SCOPE,
    ),
    "action_cost_state": (
        LAB_EXECUTION_GAP,
        "mid-cast cost state is caused by casting and paying on the engine's own frames "
        "(the bootstrap has no cost field); " + _CAUSAL_ROUTE_SCOPE,
    ),
    "combat_state": (
        LAB_EXECUTION_GAP,
        "combat is declared on the engine's own attack and block frames (the bootstrap "
        "has no combat field); the lane has no attack or block selector",
    ),
    "temporal_state.combat_step": (
        LAB_EXECUTION_GAP,
        "the combat step is reached by declaring attackers on the engine's frames on a "
        "turn the attackers can attack; the lane has no attack selector",
    ),
    "temporal_state.turn_number": (
        LAB_EXECUTION_GAP,
        "the requested turn is reached only by native progression through turns the lane "
        "does not drive",
    ),
    "temporal_state.active_player": (
        LAB_EXECUTION_GAP,
        "the requested turn-1 active player is decided by the starting-player choice, which "
        "the lane may make only on a scripted response; no record scripts it",
    ),
    "temporal_checkpoint.exact_hand_after_draw": (
        LAB_EXECUTION_GAP,
        "the obligation requires the exact hand after the draw; the engine's natural draw "
        "adds a card the lane can neither control nor prove, so exact equality cannot be "
        "established; the open mechanism is controlling or proving the drawn card, and the "
        "exact-equality obligation stays unchanged",
    ),
    "commander_state.prior_command_zone_cast_count": (
        LAB_EXECUTION_GAP,
        "prior command-zone casts are caused by casting the commander on the engine's "
        "frames (the bootstrap has no cast-count field); " + _CAUSAL_ROUTE_SCOPE,
    ),
    "rules_randomness.predetermined_semantic_draws": (
        PROVIDER_ADAPTER_GAP,
        "predetermined draws have no bootstrap field and no engine action causes them",
    ),
    "semantic_objects.face_down": (
        PROVIDER_ADAPTER_GAP,
        "the bootstrap constructs only battlefield MANIFESTED face-down permanents "
        "(E-B2); this face-down object is another kind, zone or attached",
    ),
    "knowledge_state": (
        PROVIDER_ADAPTER_GAP,
        "the bootstrap has no knowledge or permission field",
    ),
}
_DECISION_PREFIX = "decision_execution."

# Scripted decision families (``decision_execution.<family>.<selector>``): the
# pinned bridge's frame kinds that carry each family, or the provider reason no
# frame can. An unmapped family raises.
_DECISION_FAMILIES: dict[str, tuple[str, str]] = {
    "announce_x": (LAB_EXECUTION_GAP, "ANNOUNCE"),
    "choice": (LAB_EXECUTION_GAP, "CARD_LIST, STRING, COLOR or BOOLEAN"),
    "choose_ability": (LAB_EXECUTION_GAP, "SPELL_ABILITY"),
    "choose_mode": (LAB_EXECUTION_GAP, "MODE_SUBSET"),
    "choose_object": (LAB_EXECUTION_GAP, "CARD, CARD_LIST or GAME_ENTITY"),
    "choose_use": (LAB_EXECUTION_GAP, "BOOLEAN"),
    "declare_attacker": (LAB_EXECUTION_GAP, "ATTACK_DECLARATION"),
    "declare_blocker": (LAB_EXECUTION_GAP, "BLOCK_DECLARATION"),
    "mana_payment": (LAB_EXECUTION_GAP, "MANA or MANA_COMBO"),
    "multi_amount": (LAB_EXECUTION_GAP, "AMOUNT_DISTRIBUTION_SELECTION"),
    "pile": (LAB_EXECUTION_GAP, "CARD_LIST"),
    "priority": (LAB_EXECUTION_GAP, "PRIORITY (cast and activate actions)"),
    "replacement_effect": (LAB_EXECUTION_GAP, "REPLACEMENT_EFFECT"),
    "target": (LAB_EXECUTION_GAP, "TARGETING"),
    "target_amount": (LAB_EXECUTION_GAP, "DIVIDED_TARGET"),
    "trigger_order": (LAB_EXECUTION_GAP, "ORDER"),
    "mulligan": (
        PROVIDER_ADAPTER_GAP,
        "the bridge frames keep or mulligan, but taking a mulligan calls "
        "tuckCardsViaMulligan, which the pinned bridge always rejects ('London-tuck card "
        "selection is not externally represented')",
    ),
    "london_bottom": (
        PROVIDER_ADAPTER_GAP,
        "the London mulligan's bottom selection is Forge's tuckCardsViaMulligan, which the "
        "pinned bridge never answers with a card ('London-tuck card selection is not "
        "externally represented')",
    ),
}

# Requested fields the generic readback cannot show (``unobservable``).
_UNOBSERVABLE: dict[str, tuple[str, str]] = {
    "owner_controller_divergence": (
        PROVIDER_ADAPTER_GAP,
        "the readback exposes controller rows, not card owner",
    ),
    "semantic_objects.attached_to": (
        PROVIDER_ADAPTER_GAP,
        "the readback exposes no attachment relation",
    ),
    "semantic_objects.zone:graveyard": (
        PROVIDER_ADAPTER_GAP,
        "graveyard objects are names only, with no identity",
    ),
    "semantic_objects.zone:exile": (
        PROVIDER_ADAPTER_GAP,
        "exile objects are names only, with no identity",
    ),
    "semantic_objects.zone:library": (PROVIDER_ADAPTER_GAP, "library contents are never exposed"),
    "semantic_objects.zone:revealed": (
        PROVIDER_ADAPTER_GAP,
        "revealed zones have no projection",
    ),
    "semantic_objects.controlled_since_turn_began": (
        LAB_EXECUTION_GAP,
        "bootstrap-placed creatures arrive after the turn began; continuous control is "
        "caused by native progression to a later turn and shown by the engine's own attack "
        "frame, neither of which the lane executes",
    ),
}

# Required obligation tokens (the part before the first ``:``), by observation
# basis. Every token family used by an in-scope row must be listed.
OBSERVATION: dict[str, str] = {
    # The engine's state readback (life, loss, zones, P/T, stack, command zone,
    # commander damage and cast counts, turn position).
    "both_creatures_die": READBACK,
    "commander_combat_damage": READBACK,
    "commander_damage_checked_per_commander": READBACK,
    "commander_damage_total": READBACK,
    "commander_zone_event": READBACK,
    "continuous_pt": READBACK,
    "continuous_pt_evaluated": READBACK,
    "control_effect_applied": READBACK,
    "copy_created_on_stack": READBACK,
    "copy_spell": READBACK,
    "create_Devil_token": READBACK,
    "creature_enters": READBACK,
    "damage": READBACK,
    "first_turn_draw": READBACK,
    "first_turn_draw_step_skipped": READBACK,
    "free_mulligan": READBACK,
    "game_start_command_zone": READBACK,
    "move_to_graveyard": READBACK,
    "multiplayer_cleanup": READBACK,
    "next_turn": READBACK,
    "object_leaves_game": READBACK,
    "player_leaves": READBACK,
    "player_loses": READBACK,
    "resolve": READBACK,
    "response_on_stack": READBACK,
    "stack_push": READBACK,
    "starting_player": READBACK,
    "trigger": READBACK,
    "zone_change": READBACK,
    "APNAP_stack_order": READBACK,
    "bottom_count": READBACK,
    # The layer tokens are characteristic readbacks (CR 613): the abilities and
    # the power and toughness the layer system yields, never an event (the
    # contract 1.0.21 MICRO_LAYERS erratum).
    "layer6_remove_abilities": READBACK,
    "layer7b_set_pt": READBACK,
    "layer7c_modify_pt": READBACK,
    # The engine's own decision frames, answered by the Lab (the decision tape).
    "ability_selected": DECISION_FRAME,
    "amount_assignment": DECISION_FRAME,
    "announce_x_frame": DECISION_FRAME,
    "attacker_declared": DECISION_FRAME,
    "blocker_declared": DECISION_FRAME,
    "choice": DECISION_FRAME,
    "choice_frame": DECISION_FRAME,
    "choose_ability_frame": DECISION_FRAME,
    "choose_mode_frame": DECISION_FRAME,
    "choose_object_frame": DECISION_FRAME,
    "choose_use_frame": DECISION_FRAME,
    "commander_cast_from_command": DECISION_FRAME,
    "commander_choice": DECISION_FRAME,
    "commander_replacement_chosen": DECISION_FRAME,
    "commander_tax": DECISION_FRAME,
    "cost_determined": DECISION_FRAME,
    "Counterspell_cast": DECISION_FRAME,
    "declare_attacker_frame": DECISION_FRAME,
    "declare_blocker_frame": DECISION_FRAME,
    "keep": DECISION_FRAME,
    "legal_blocker_partition": DECISION_FRAME,
    "legal_targets_exposed": DECISION_FRAME,
    "mana_abilities_activated": DECISION_FRAME,
    "mana_paid": DECISION_FRAME,
    "mana_payment_frame": DECISION_FRAME,
    "mode_selected": DECISION_FRAME,
    "mulligan": DECISION_FRAME,
    "mulligan_once": DECISION_FRAME,
    "multi_amount_frame": DECISION_FRAME,
    "object_selected": DECISION_FRAME,
    "partition_created": DECISION_FRAME,
    "pile_frame": DECISION_FRAME,
    "priority": DECISION_FRAME,
    "priority_action_resets_pass_count": DECISION_FRAME,
    "priority_decision_frame": DECISION_FRAME,
    "priority_ring_live_order": DECISION_FRAME,
    "replacement_effect_frame": DECISION_FRAME,
    "scry_choice": DECISION_FRAME,
    "simultaneous_triggers": DECISION_FRAME,
    "spell_cast": DECISION_FRAME,
    "target_amount_frame": DECISION_FRAME,
    "target_decision_frame": DECISION_FRAME,
    "target_selected": DECISION_FRAME,
    "tax": DECISION_FRAME,
    "trigger_order_frame": DECISION_FRAME,
    "x_announced": DECISION_FRAME,
    # Only an engine event stream shows these: a rules process with no lasting
    # state and no decision of its own (a would-be amount, an applied
    # replacement or prevention, a state-based-action pass, a
    # simultaneity, a new object incarnation, a Rules RNG outcome, a queued
    # extra turn).
    "combat_damage": EVENT_LOG,
    "combat_damage_prevented": EVENT_LOG,
    "combat_damage_would_be": EVENT_LOG,
    "damage_would_be": EVENT_LOG,
    "extra_turn_created": EVENT_LOG,
    "new_object_incarnation": EVENT_LOG,
    "prevention_applied": EVENT_LOG,
    "replacement_effect": EVENT_LOG,
    "rules_rng": EVENT_LOG,
    "simultaneous_trigger_event": EVENT_LOG,
    "state_based_actions": EVENT_LOG,
}

# Readback tokens whose characteristic the pinned bridge never projects: a
# provider gap however the lane observes them. Forge's battlefield projection
# carries each permanent's power and toughness but no abilities.
UNPROJECTED_READBACK: dict[str, str] = {
    "layer6_remove_abilities": (
        "the obligation reads a permanent's abilities and the pinned bridge's battlefield "
        "projection carries power and toughness but no abilities (no ability readback)"
    ),
}

# ``resolve:<card>`` tokens whose resolution leaves a characteristic the pinned
# bridge does project. Giant Growth's +3/+3 shows in the battlefield
# power/toughness readback, so its missing observer is the Lab's gap; a card
# whose effect is marked damage (Lightning Bolt) is not projected and stays a
# provider gap. Declared per card, never inferred from card text; the class
# names who owns the gap and never credits the row.
PROJECTED_RESOLUTION: dict[str, str] = {
    "Giant Growth": (
        "the resolution's +3/+3 is visible in the pinned bridge's battlefield "
        "power/toughness projection; the lane implements no resolve observer for it yet"
    ),
}

# Obligation kinds the lane already evaluates from engine facts.
_LANE_OBLIGATION_KINDS = frozenset(
    {
        "commander_damage_checked_per_commander",
        "commander_zone_choice",
        "game_start_command_zone",
        "scripted_decision_offered",
        "player_leaves_multiplayer_cleanup",
        "starting_player_first_turn_draw",
    }
)


def in_scope(fixture_id: str) -> bool:
    return fixture_id.startswith(SCOPE_PREFIXES)


def _token_family(token: Any) -> str:
    return str(token).split(":", 1)[0]


@dataclass
class ForgeResidual:
    fixture_id: str
    mechanisms: list[dict[str, str]] = field(default_factory=list)
    observation: dict[str, list[str]] = field(default_factory=dict)
    lane_obligation_kind: str | None = None

    @property
    def first_missing(self) -> dict[str, str] | None:
        """The first provider gap in pipeline order, else the first Lab gap.

        A provider gap anywhere means no Lab work alone closes the row, so it
        names the row's class even when a Lab gap comes earlier in the pipeline.
        """
        for mechanism in self.mechanisms:
            if mechanism["class"] == PROVIDER_ADAPTER_GAP:
                return mechanism
        return self.mechanisms[0] if self.mechanisms else None

    @property
    def classification(self) -> str:
        first = self.first_missing
        return SCENARIO_LANE_EXECUTABLE if first is None else first["class"]

    @property
    def needs_event_log(self) -> bool:
        return bool(self.observation.get(EVENT_LOG))

    def reason(self) -> str:
        first = self.first_missing
        if first is None:
            return (
                f"Forge {SCENARIO_LANE_EXECUTABLE}: the scenario lane constructs this row, "
                f"executes it and evaluates its obligation ({self.lane_obligation_kind}); it "
                "earns credit only through that lane's runner-bound receipt, and without one "
                "it stays unestablished."
            )
        parts = [
            f"Forge {self.classification}: first missing mechanism at "
            f"{first['stage']} ({first['dimension']}): {first['detail']}"
        ]
        later = [item for item in self.mechanisms if item is not first]
        if later:
            parts.append(
                "then: "
                + "; ".join(
                    f"{item['stage']} {item['dimension']} ({item['class']})" for item in later
                )
            )
        if self.needs_event_log:
            parts.append(
                "event-only obligation tokens with no Forge event log: "
                + ", ".join(self.observation[EVENT_LOG])
            )
        parts.append("no receipt; the row stays unestablished")
        return ". ".join(parts) + "."

    def to_document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "classification": self.classification,
            "first_missing": self.first_missing,
            "mechanisms": self.mechanisms,
            "observation": self.observation,
            "needs_event_log": self.needs_event_log,
            "lane_obligation_kind": self.lane_obligation_kind,
            "reason": self.reason(),
        }


def _family_binding(record: dict[str, Any] | None, family: str) -> str | None:
    """The provider surface a contract erratum binds ``family`` to, or None."""
    for step in (record or {}).get("native_procedure") or ():
        binding = ((step or {}).get("details") or {}).get("decision_family_binding")
        if isinstance(binding, dict) and binding.get("record_family") == family:
            surface = binding.get("provider_surface")
            return str(surface) if surface else None
    return None


def _construction(dimension: str, record: dict[str, Any] | None = None) -> tuple[str, str]:
    if dimension == lane.STARTING_PLAYER_UNSCRIPTED:
        return (
            CONTRACT_AUTHORITY_GAP,
            "the obligation names a starting player, but the effective record scripts no "
            "starting-player response; choosing the starter from the requested state would "
            "be requested-option selection, so the row needs a contract erratum that "
            "scripts the decision",
        )
    if dimension.startswith(_DECISION_PREFIX):
        family = dimension[len(_DECISION_PREFIX) :].split(".", 1)[0]
        mapped = _DECISION_FAMILIES.get(family)
        if mapped is None:
            raise ValueError(f"unmapped Forge decision family {family!r}")
        gap_class, frames = mapped
        # A contract erratum may bind the record's family to a different
        # provider surface (PILOT_CHOOSE_USE: scry 1 is a 0..1 card selection,
        # 1.0.21 E2a); the frame named is then that surface's, never the
        # family's default.
        binding = _family_binding(record, family)
        if binding is not None and gap_class == LAB_EXECUTION_GAP:
            frames = f"{_DECISION_FAMILIES['choose_object'][1]} ({binding})"
        if gap_class == PROVIDER_ADAPTER_GAP:
            return gap_class, f"the record scripts a {family} decision: {frames}"
        return (
            gap_class,
            f"the record scripts a {family} decision; the bridge carries it on its "
            f"{frames} frames, but the lane has no selector for them",
        )
    if dimension in _CONSTRUCTION:
        return _CONSTRUCTION[dimension]
    for prefix in ("semantic_objects.face_down", "knowledge_state"):
        if dimension.startswith(prefix):
            return _CONSTRUCTION[prefix]
    raise ValueError(f"unmapped Forge lane construction dimension {dimension!r}")


def classify_row(record: dict[str, Any]) -> ForgeResidual:
    """The first missing mechanism of one in-scope record, in pipeline order."""
    fixture_id = str(record.get("fixture_id"))
    if not in_scope(fixture_id):
        raise ValueError(f"{fixture_id} is not a Forge AF06/AF08 residual row")
    model = lane.model_requested_state(record)
    row = ForgeResidual(fixture_id=fixture_id, lane_obligation_kind=lane._obligation_kind(model))

    construction: list[dict[str, str]] = []
    execution: list[dict[str, str]] = []
    for finding in model.hard_unsupported:
        gap_class, detail = _construction(finding.dimension, record)
        entry = {"dimension": finding.dimension, "class": gap_class, "detail": detail}
        if finding.dimension.startswith(_DECISION_PREFIX):
            execution.append({**entry, "stage": "execution"})
        else:
            construction.append({**entry, "stage": "construction"})
    readback = []
    for finding in model.unobservable:
        mapped = _UNOBSERVABLE.get(finding.dimension)
        if mapped is None:
            raise ValueError(f"unmapped Forge readback dimension {finding.dimension!r}")
        gap_class, detail = mapped
        readback.append(
            {
                "stage": "checkpoint_readback",
                "dimension": finding.dimension,
                "class": gap_class,
                "detail": detail,
            }
        )

    required = (record.get("expected_events") or {}).get("required_events") or []
    observation: dict[str, list[str]] = {READBACK: [], DECISION_FRAME: [], EVENT_LOG: []}
    for token in required:
        family = _token_family(token)
        basis = OBSERVATION.get(family)
        if basis is None:
            raise ValueError(f"{fixture_id}: unmapped obligation token family {family!r}")
        observation[basis].append(str(token))
    row.observation = {basis: tokens for basis, tokens in observation.items() if tokens}

    observing: list[dict[str, str]] = []
    for token in observation[READBACK]:
        unprojected = UNPROJECTED_READBACK.get(_token_family(token))
        if unprojected is not None:
            observing.append(
                {
                    "stage": "observation",
                    "dimension": f"unprojected_readback:{_token_family(token)}",
                    "class": PROVIDER_ADAPTER_GAP,
                    "detail": unprojected,
                }
            )
    if observation[EVENT_LOG]:
        observing.append(
            {
                "stage": "observation",
                "dimension": "event_log",
                "class": PROVIDER_ADAPTER_GAP,
                "detail": "the obligation needs engine events and the pinned bridge exports "
                "no event log (EVENT_LOG_UNSUPPORTED)",
            }
        )
    if row.lane_obligation_kind == "scripted_decision_offered":
        # The scripted-decision contract observes token by token; a token it has
        # no observer for is named, never assumed (UNKNOWN, not PASS).
        for token in required:
            if not lane.scripted_token_observable(str(token)):
                family = _token_family(token)
                card = str(token).split(":", 1)[1].replace("_", " ") if ":" in str(token) else ""
                projected = PROJECTED_RESOLUTION.get(card) if family == "resolve" else None
                observing.append(
                    {
                        "stage": "observation",
                        "dimension": f"scripted_token:{token}",
                        # A family the readback cannot show is a provider gap;
                        # one the lane merely does not observe yet is the Lab's,
                        # as is a resolution whose effect the readback projects.
                        "class": LAB_EXECUTION_GAP
                        if projected is not None or family not in lane.SCRIPTED_TOKEN_UNOBSERVABLE
                        else PROVIDER_ADAPTER_GAP,
                        "detail": projected
                        or lane.SCRIPTED_TOKEN_UNOBSERVABLE.get(
                            family, f"the lane has no observer for {family!r} tokens"
                        ),
                    }
                )
    if row.lane_obligation_kind not in _LANE_OBLIGATION_KINDS:
        observing.append(
            {
                "stage": "observation",
                "dimension": "observation_contract",
                "class": LAB_EXECUTION_GAP,
                "detail": "the lane has no observation contract for this obligation's "
                "readback and decision-frame tokens",
            }
        )

    row.mechanisms = construction + readback + execution + observing
    return row


def row_reason(record: dict[str, Any]) -> str:
    return classify_row(record).reason()


def build_matrix(records: dict[str, dict[str, Any]], fixture_ids: list[str]) -> dict[str, Any]:
    """The Forge residual matrix for the given in-scope rows."""
    rows = [classify_row(records[fixture]).to_document() for fixture in sorted(fixture_ids)]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": "forge",
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "classifications": counts,
            "needs_event_log": sum(1 for row in rows if row["needs_event_log"]),
            "pass": 0,
        },
        "note": (
            "classification only: no row was executed and no receipt exists. A row becomes "
            "PASS only through a current source-bound execution receipt."
        ),
    }
