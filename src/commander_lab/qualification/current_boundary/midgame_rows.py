"""Exact placement obligations on the production midgame lane.

This closes the last two links of the documented PB-03 credit chain::

    production midgame transport -> record-aware admission -> external decision
    execution -> construction truth -> causal observation -> exact semantic
    obligation -> runner-bound native receipt -> qualification credit

For a declared set of rows whose requested state the lane constructs exactly by
placement, the obligation is executed through the lane and verified against the
engine's own public event tape (``get_midgame_events``) and its principal-neutral
observation. Only a fully verified row yields a positive fixture receipt; the
assembler credits nothing else.

The executor is not a Rules engine and chooses nothing on its own:

* the starting state is the frozen record, placed and read back by the engine;
  only an EXACT construction (or the lane's documented declaration-step priority
  allowance) proceeds;
* every answer is one of the engine's own offered options: the record's
  ``decision_script`` in order, engine-offered priority passes (which the
  records' native procedures script explicitly), and mana payment from the
  record's own mana sources in the declared order;
* any other decision stops the row unverified;
* every ``required_events`` token needs a positive observation on the tape or in
  the decision trace, and every terminal check must hold. A token kind this module
  cannot evaluate leaves the row unverified; nothing is inferred.

Causal-route rows (a stack spell or an elimination that must be caused) are not
executed here: their deviation from the record is a Coordinator question.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import midgame_lane as ml
from . import receipts as receipt_mod
from . import refusal as refusal_mod
from .starting_player import SEATS, midgame_starting_seat

REPO_ROOT = Path(__file__).resolve().parents[4]
PROBE_SCRIPT = REPO_ROOT / "scripts" / "run_midgame_capability_probe.py"
EXECUTION_MODE = "MIDGAME_LANE_PLACEMENT_OBLIGATION"
TEST_IDENTITY_PREFIX = "midgame-lane:placement-obligation#"
POSITIVE_FIXTURE_RECEIPT_SCHEMA = receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA
ACCEPTED_CONSTRUCTION = {"EXACT", "ALLOWED_VARIANCE"}
REQUESTED_COMBAT_FACT = (
    "the engine's declared attacks (and blocks, when requested) are exactly the record's "
    "combat_state"
)

#: The receipt assertion class a causal-elimination row carries when its only
#: non-exact construction disposition is the declared open life substitution.
#: It is the same class the Forge scenario lane carries for that disposition
#: (``forge_scenario_lane._receipt_assertion_class``): the variance is declared
#: by the Lab's shared causal route, never by the engine's own compare or the
#: fixture, so a receipt that relabelled it ``BEHAVIOUR_OBSERVED`` would hide it.
ASSERTION_LAB_DECLARED_CAUSAL_SUBSTITUTION = "BEHAVIOUR_OBSERVED_LAB_DECLARED_CAUSAL_SUBSTITUTION"

#: The variance source named for that substitution. The recorded life is the
#: state-based-action-pending instant of CR 704.3, which no priority point
#: shows, so the shared route's causal-elimination plan places the victim's
#: recorded starting life openly and reaches the recorded value only through
#: the engine's own damage; the plan publishes the substitution verbatim.
DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE = (
    "declared causal elimination (run_midgame_capability_probe.CAUSAL_ROWS, shared "
    "with Forge): the victim's recorded life is the state-based-action-pending "
    "instant (CR 704.3), placed openly as its starting life and reached only by "
    "the engine dealing the declared instruments' damage"
)


# A `*_object` value meaning "an object the tape does not name" (see
# matching_events); `None` means "no object at all".
UNNAMED_OBJECT = "<unnamed-object>"


def _declared_life_substitutions(
    plan: dict[str, Any],
) -> tuple[tuple[str, int, int], ...] | None:
    """The elimination plan's own declared substitutions, or None uninterpretable.

    Nothing is inferred: each entry must be the engine's plan payload shape
    (``player_id``, ``recorded_life``, ``placed_life``), and a list that does
    not parse leaves the substitution unestablished rather than absent.
    """
    raw = plan.get("life_substitutions")
    if not isinstance(raw, list):
        return None
    parsed: list[tuple[str, int, int]] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        player = item.get("player_id")
        recorded = item.get("recorded_life")
        placed = item.get("placed_life")
        if not isinstance(player, str) or not player:
            return None
        if isinstance(recorded, bool) or not isinstance(recorded, int):
            return None
        if isinstance(placed, bool) or not isinstance(placed, int):
            return None
        parsed.append((player, recorded, placed))
    return tuple(parsed)


#: The variance source of the engine's own declaration-step priority
#: allowance: during a declaration step the engine does not hold priority the
#: way its arrival readback reports it, so the engine's own field-level compare
#: is false with only the priority mismatches the lane models
#: (``midgame_lane.DECLARATION_STEP_PRIORITY_ALLOWANCE``). That allowance is
#: the engine's own disposition, not the Lab's causal life substitution, and a
#: row carrying both must name both.
ENGINE_DECLARATION_STEP_PRIORITY_ALLOWANCE_VARIANCE_SOURCE = (
    "engine declaration-step priority allowance "
    "(midgame_lane.DECLARATION_STEP_PRIORITY_ALLOWANCE): during a declaration step "
    "the engine does not hold priority the way its arrival readback reports it, so "
    "the engine's own field-level compare is false with only the priority "
    "mismatches it documents"
)


@dataclass(frozen=True)
class ConstructionDisposition:
    """The row's construction verdict and every declared variance behind it.

    ``variance_source`` names what makes the final verdict non-exact: the
    engine's own declaration-step priority allowance when the engine's verdict
    was already ``ALLOWED_VARIANCE``, or the Lab's declared causal life
    substitution when it turns an otherwise-``EXACT`` engine verdict into the
    declared variance. ``declared_substitution_source`` names the Lab's
    declared substitution whenever the elimination plan declares one, even
    beside an engine variance, so neither source ever overwrites the other.
    """

    verdict: str | None
    variance_source: str | None = None
    declared_substitution_source: str | None = None


def construction_with_declared_substitution(
    construction_verdict: str | None, created: dict[str, Any]
) -> ConstructionDisposition:
    """The row's construction disposition after its own declared life substitution.

    A causal-elimination record asks for the state-based-action-pending instant
    of CR 704.3, which no priority point shows. The engine's own plan therefore
    places the victim at its recorded starting life and publishes the
    substitution (``elimination_plan.life_substitutions``); the recorded value
    is then reached only by the engine dealing the declared instruments'
    damage.

    The overlay applies only to an engine verdict of ``EXACT``: an otherwise
    exact construction with a real, fully declared victim substitution becomes
    ``ALLOWED_VARIANCE`` with the Lab's own source and assertion class, exactly
    as the Forge scenario lane labels the same disposition. An engine
    ``ALLOWED_VARIANCE`` is the engine's own disposition (the declaration-step
    priority allowance, for example): it keeps its own ``variance_source`` and
    assertion class, and a Lab substitution the same plan declares is recorded
    beside it rather than in place of it.

    The refusal order matters. A construction mismatch, an uninterpretable
    engine verdict and every non-elimination row keep the engine's own verdict
    verbatim; only a real, fully declared substitution for the plan's victim
    turns an otherwise-exact construction into the declared variance. An
    elimination plan that cannot state its substitutions is not interpretable,
    so the row fails its construction closed instead of reading as exact.
    """
    plan = created.get("elimination_plan") if isinstance(created, dict) else None
    if not isinstance(plan, dict):
        return ConstructionDisposition(construction_verdict)
    if construction_verdict not in ("EXACT", "ALLOWED_VARIANCE"):
        # A real mismatch (or an unrecognized verdict) takes precedence.
        return ConstructionDisposition(construction_verdict)
    substitutions = _declared_life_substitutions(plan)
    victim = plan.get("victim")
    if substitutions is None or not isinstance(victim, str) or not victim:
        return ConstructionDisposition("UNRECOGNIZED")
    declared = [
        item for item in substitutions if item[0].lower() == victim.lower() and item[1] != item[2]
    ]
    declared_source = DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE if declared else None
    if construction_verdict == "ALLOWED_VARIANCE":
        # The engine's own variance already explains the verdict; the Lab
        # declaration the same plan carries is recorded beside it, never
        # overwritten by it, and the engine's assertion class is kept.
        return ConstructionDisposition(
            "ALLOWED_VARIANCE",
            ENGINE_DECLARATION_STEP_PRIORITY_ALLOWANCE_VARIANCE_SOURCE,
            declared_source,
        )
    if declared_source is None:
        return ConstructionDisposition("EXACT")
    return ConstructionDisposition("ALLOWED_VARIANCE", declared_source, declared_source)


@dataclass(frozen=True)
class TerminalCheck:
    """One explicit terminal postcondition, read from the engine's observation."""

    kind: str
    principal: str | None = None
    value: Any = None
    source_name: str | None = None
    card_identity: str | None = None
    # Event-pattern checks: the engine event type and the field constraints an
    # event must meet. A key ending in ``~`` matches a name by prefix (as the
    # trigger tokens do); every other key must equal the value exactly.
    event_type: str | None = None
    where: tuple[tuple[str, Any], ...] = ()
    # Decision-frame checks: text the engine's own selected offer label contains.
    label: str | None = None
    # Frame-window checks: the engine event patterns that open (``after``) and
    # close (``before``) the window of frames the check reads, by tape position.
    after: TerminalCheck | None = None
    before: TerminalCheck | None = None

    def describe(self) -> str:
        if self.kind == "stack_empty_after":
            constraints = ", ".join(f"{key}={value}" for key, value in self.where)
            return (
                f"the first priority frame after the first {self.event_type} event with "
                f"{constraints} shows an empty stack"
            )
        if self.kind == "events":
            constraints = ", ".join(f"{key}={value}" for key, value in self.where)
            amount = "at least one" if self.value is None else f"exactly {self.value}"
            return f"{amount} {self.event_type} event(s) with {constraints or 'any fields'}"
        if self.kind == "events_follow":
            earlier_type, earlier_where = self.value
            constraints = ", ".join(f"{key}={value}" for key, value in self.where)
            earlier = ", ".join(f"{key}={value}" for key, value in earlier_where)
            return (
                f"a {self.event_type} event with {constraints} follows the first "
                f"{earlier_type} event with {earlier}"
            )
        if self.kind == "events_precede":
            later_type, later_where = self.value
            later = ", ".join(f"{key}={value}" for key, value in later_where)
            earlier = ", ".join(f"{key}={value}" for key, value in self.where)
            return (
                f"every {self.event_type} event with {earlier} precedes the first "
                f"{later_type} event with {later}"
            )
        if self.kind == "in_graveyard":
            return f"{self.card_identity} is in {self.principal}'s graveyard"
        if self.kind == "selected_frame":
            return f"a scripted {self.value} frame selected an engine offer naming {self.label!r}"
        if self.kind == "scripted_key":
            decision_class, key = self.value
            return (
                f"the record's script answered {self.principal}'s {decision_class} frame "
                f"with {key!r}"
            )
        if self.kind == "scripted_frame":
            return (
                f"the engine asked {self.principal} a {self.value} frame whose prompt names "
                f"{self.label!r}, and the record's script answered it"
            )
        if self.kind == "no_frame":
            who = f" of {self.principal}" if self.principal else ""
            about = f" about {self.label!r}" if self.label else ""
            return f"the engine asked no {self.value} decision{who}{about}"
        if self.kind == "frame_count":
            decision_class, count = self.value
            who = f" of {self.principal}" if self.principal else ""
            return (
                f"the engine asked exactly {count} {decision_class} decision(s){who} "
                f"about {self.label!r}"
            )
        if self.kind == "pool_spend":
            return f"a mana payment spent {self.value} mana from the pool"
        if self.kind == "untapped_count":
            return (
                f"exactly {self.value} {self.card_identity} on {self.principal}'s battlefield "
                "are untapped"
            )
        if self.kind == "hand_count_min":
            return f"{self.principal} holds at least {self.value} cards"
        if self.kind == "hand_count":
            return f"{self.principal} holds exactly {self.value} cards"
        if self.kind == "not_on_battlefield":
            return f"no {self.card_identity} is on {self.principal}'s battlefield"
        if self.kind == "power_toughness":
            power, toughness = self.value
            return f"every {self.card_identity} on {self.principal}'s battlefield is {power}/{toughness}"
        if self.kind == "counters":
            return (
                f"every {self.card_identity} on {self.principal}'s battlefield has counters "
                f"{dict(self.value)}"
            )
        if self.kind == "colors":
            return (
                f"every {self.card_identity} on {self.principal}'s battlefield is "
                f"{'/'.join(self.value)}"
            )
        if self.kind == "keyword":
            return f"every {self.card_identity} on {self.principal}'s battlefield has {self.value}"
        if self.kind == "keyword_absent":
            return (
                f"every {self.card_identity} on {self.principal}'s battlefield lacks {self.value}"
            )
        if self.kind == "triggered_ability":
            trigger, effect = self.value
            return (
                f"every {self.card_identity} on {self.principal}'s battlefield has an "
                f"engine {trigger} triggered ability with a {effect}"
            )
        if self.kind == "battlefield_exact":
            return (
                f"{self.principal}'s battlefield is exactly {sorted(self.value)} "
                "(by card identity, as a multiset)"
            )
        if self.kind == "graveyard_mana_value":
            return (
                f"{self.card_identity} in {self.principal}'s graveyard has mana value {self.value}"
            )
        if self.kind == "frame_offers":
            decision_class, count = self.value
            return (
                f"a scripted {decision_class} frame about {self.label!r} offered exactly "
                f"{count} option(s)"
            )
        if self.kind == "selected_sequence":
            return (
                f"the scripted {self.value[0]} frames about {self.label!r} selected "
                f"{list(self.value[1])} in that order"
            )
        if self.kind == "token_count":
            return f"exactly {self.value} {self.card_identity} tokens are on {self.principal}'s battlefield"
        if self.kind == "life":
            return f"{self.principal} is at {self.value} life"
        if self.kind == "blocker_partition":
            return (
                f"every block the engine offered {self.principal} names an attacker attacking "
                f"{self.principal}"
            )
        if self.kind == "event_order":
            field_name, expected = self.value
            constraints = ", ".join(f"{key}={value}" for key, value in self.where)
            return (
                f"the {self.event_type} events with {constraints or 'any fields'} carry "
                f"{field_name} {list(expected)} in tape order"
            )
        if self.kind == "frame_order":
            decision_class, principals = self.value
            return (
                f"the engine's first {len(principals)} {decision_class} decisions went to "
                f"{list(principals)} in that order"
            )
        if self.kind == "cast_cost":
            return (
                f"the engine determined {self.value} for the scripted cast of {self.card_identity}"
            )
        if self.kind == "pending_extra_turns":
            return f"the engine's pending extra turns are {list(self.value)}, in the order taken"
        if self.kind == "extra_turn_created":
            return (
                f"the engine had no pending extra turn for {self.principal} when it asked the "
                f"run's first frame or any frame before the first {_window_name(self.after)}, "
                f"and pending extra turns {list(self.value)}, in the order taken, when it asked "
                "a frame after it"
            )
        if self.kind == "pending_extra_turns_between":
            return (
                f"the engine's pending extra turns read {list(self.value)} at a frame after the "
                f"first {_window_name(self.after)}"
                + (f" and before the first {_window_name(self.before)}" if self.before else "")
            )
        if self.kind == "player_in_game":
            return f"the engine reports {self.principal} neither lost nor left"
        if self.kind == "player_left":
            return f"the engine reports {self.principal} lost and left the game"
        if self.kind == "commander_damage":
            damaged, amount = self.value
            return (
                f"the engine's commander combat damage from {self.principal}'s "
                f"{self.card_identity} to {damaged} is {amount}"
            )
        if self.kind == "trigger_count":
            return f"{self.source_name} triggered exactly {self.value} time(s)"
        if self.kind == "commander_prior_casts":
            return f"{self.principal}'s commander cast count is {self.value}"
        if self.kind == "game_start_command_zone":
            return (
                f"{self.card_identity} begins in {self.principal}'s command zone as exactly "
                "one engine commander identity"
            )
        if self.kind == "on_battlefield":
            return f"{self.card_identity} is on {self.principal}'s battlefield"
        if self.kind == "tapped":
            return f"{self.card_identity} on {self.principal}'s battlefield is tapped={self.value}"
        if self.kind == "no_mana_payment":
            return "no mana payment was asked"
        if self.kind == "draws":
            return f"{self.principal} moved exactly {self.value} card(s) from library to hand"
        if self.kind == "tokens_created":
            return f"exactly {self.value} {self.card_identity} token(s) were created"
        if self.kind == "no_permanent_damage":
            return "no permanent was dealt damage"
        if self.kind == "stack_order":
            return f"{self.principal}'s triggered abilities went on the stack in the order {self.value}"
        if self.kind == "mana_charged":
            return f"the engine charged exactly {self.value} mana"
        if self.kind == "assignment_total":
            return f"the engine-accepted amount assignments total exactly {self.value}"
        if self.kind == "assignment_minimum":
            return f"every engine-accepted amount assignment is at least {self.value}"
        return self.kind


@dataclass(frozen=True)
class VocabularyToken:
    """A record token observed exactly as one engine-verified vocabulary token.

    Record tokens are free text; some name a fact the generic vocabulary
    already verifies against the engine (e.g. ``total_cost_determined`` is the
    engine's own payment frame, which ``cost_determined:base_plus_N_generic``
    verifies). The binding states that equivalence per fixture; the named
    token is then verified by the generic vocabulary, never by the free text.
    """

    token: str

    def describe(self) -> str:
        return f"engine-verified {self.token}"


@dataclass(frozen=True)
class RowSpec:
    """What the executor may answer for a row and what it must observe."""

    mana_sources: tuple[str, ...] = ()
    terminal_checks: tuple[TerminalCheck, ...] = ()
    max_decisions: int = 80
    # A card fact the record's own postcondition states (e.g. Rograkh costs {0}),
    # used to read commander tax as mana paid minus printed mana value.
    commander_printed_mana_value: int | None = None
    # A record's semantic mode key, bound to the text of the engine mode it names.
    # The key has no machine definition in the record; its meaning comes from the
    # record's own postcondition prose ("the Devil-token mode"). The bound text
    # must occur in exactly one engine-offered mode label or the row fails closed.
    mode_bindings: tuple[tuple[str, str], ...] = ()
    # A record's semantic ability key, bound to the activated ability it names:
    # (key, (source semantic id, a fragment of the ability's rules text)). The
    # source and fragment must match exactly one engine-offered activation or
    # the row fails closed.
    ability_bindings: tuple[tuple[str, tuple[str, str]], ...] = ()
    # The obligation is the game start itself (who takes the first turn, the
    # first turn's draw), which happens before the arrival checkpoint: the tape
    # is read from the engine's first event instead of from the arrival.
    observe_from_game_start: bool = False
    # The engine-authored cost obligation of the cast this row scripts:
    # (source semantic id, the record's declared base mana, the record's
    # declared total mana). The ``cost_determined:base_plus_N_generic`` token
    # is verified against the engine's own payment frame for this exact cast,
    # never against a Lab-computed rule.
    cost_obligation: tuple[str, str, str] | None = None
    # A record's required-event token, bound to the explicit check that observes
    # it. Record tokens are free text written before any engine existed; a
    # binding states, per fixture, which engine event pattern, decision frame or
    # engine-observed state the token names. An unbound token the generic
    # vocabulary does not understand stays unobserved.
    token_bindings: tuple[
        tuple[str, TerminalCheck | tuple[TerminalCheck, ...] | VocabularyToken], ...
    ] = ()
    # A record's scry 1 named as a yes/no ``choose_use`` step, bound by the
    # record's own decision_family_binding (CR 701.22a): XMage asks it as a
    # 0..1 card selection on its target frame. The value is the looked-at
    # library object; false is the empty selection, true that one card.
    scry_binding: str | None = None


# The record's decision family and the engine's decision class name the same
# decision differently for these families; every other family is spelled alike.
# The multi_amount record and the target_amount record both reach XMage's single
# divided-damage `choose_targets` frame (observed on the production mid-game
# lane); the record distinguishes the number of damage legs in its semantic
# value, not in the engine's class name.
ENGINE_DECISION_CLASS = {
    "choose_mode": "mode",
    "multi_amount": "target_amount",
    # A cleanup discard (CR 514.1) is XMage's own choose_object frame over the
    # discarding player's hand; the record names the family it scripts.
    "cleanup_discard": "choose_object",
}


def engine_decision_class(family: str) -> str:
    return ENGINE_DECISION_CLASS.get(family, family)


# XMage asks every yes/no question through one decision class, ``choose_use``
# (its chooseUse surface). A record step that answers a yes/no question with a
# boolean selector may name the question's rules family instead (the owner's
# commander zone choice is a ``choice`` or a ``replacement_effect`` in the
# records). The binding changes only which engine frame the step answers; the
# boolean selector still matches exactly the engine's own boolean offer that
# carries the record's value, and fails closed on anything else.
BOOLEAN_DECISION_CLASS = "choose_use"
BOOLEAN_QUESTION_FAMILIES = frozenset({"choice", "replacement_effect"})

# A pile split (Fact or Fiction's "an opponent separates"): XMage asks the
# separating player to select the cards of the first pile on its object frame
# (HIDDEN_13's reviewed route), and the record's ``partition`` names that
# first pile as ``pile_a`` (contract 1.0.21 PILOT_PILE partition_binding).
# The pile the chooser then takes is XMage's own ``pile`` frame.
PARTITION_DECISION_CLASS = "choose_object"


def step_decision_class(step: dict[str, Any]) -> str:
    """The engine decision class a record's scripted step answers."""
    family = str(step.get("decision_family") or "")
    selector = str((step.get("selection") or {}).get("selector_kind") or "")
    if selector == "boolean" and family in BOOLEAN_QUESTION_FAMILIES:
        return BOOLEAN_DECISION_CLASS
    if selector == "partition" and family == "pile":
        return PARTITION_DECISION_CLASS
    return engine_decision_class(family)


# The record's arrival transport steps: answered by the arrival driver itself
# (the starting-seat declaration CR 103.1, the pregame keeps CR 103.5, the
# priority pass-through CR 117.3d and the pre-checkpoint empty attack
# declaration CR 508.1), never by the obligation loop's engine-frame matching.
ARRIVAL_TRANSPORT_FAMILIES = frozenset(
    {"starting_player", "mulligan", "priority_pass_through", "declare_attackers"}
)


def _require_scripted_temporal_point(client: ml.MidgameLaneClient, step: dict[str, Any]) -> None:
    """Refuse a scripted step whose declared phase/turn is not the engine's point.

    A decision family can be asked at more than one point in a game (a cleanup
    discard happens every turn); a step that declares its own ``phase``/``turn``
    binds to exactly that point, and the same family at another point is an
    unscripted extra decision that fails closed.
    """
    declared_turn = step.get("turn")
    declared_phase = str(step.get("phase") or "").upper()
    if declared_turn is None and not declared_phase:
        return
    observation = client.complete_arrival().get("observation") or {}
    if declared_turn is not None and observation.get("turn_number") != declared_turn:
        raise ml.MidgameLaneError(
            f"the record scripts {step.get('decision_family')} for turn {declared_turn}; "
            f"the engine asked it in turn {observation.get('turn_number')}"
        )
    if declared_phase:
        tokens = {
            str(observation.get("phase") or "").upper(),
            str(observation.get("step") or "").upper(),
        }
        if declared_phase not in tokens:
            raise ml.MidgameLaneError(
                f"the record scripts {step.get('decision_family')} for {declared_phase}; "
                f"the engine asked it at {observation.get('phase')}/{observation.get('step')}"
            )


def declared_omission_probe(record: dict[str, Any]) -> tuple[str, str] | None:
    """The record's declared intentionally-omitted decision handler, if any.

    Some negative records declare their obligation directly on the fixture
    rather than in a ``decision_script`` step: ``negative_fallback_probe``
    names the engine decision class whose external handler is intentionally
    unavailable, and the record's ``NATIVE_RESOLVE_TOP_OF_STACK`` procedure
    step names the actor the frame is expected to ask. The obligation is the
    typed fail-closed refusal of exactly that frame, so the executor must
    refuse it instead of answering it. The actor is never guessed: a record
    without the procedure step's expected actor gets no probe.
    """
    probe = record.get("negative_fallback_probe")
    if not isinstance(probe, dict):
        return None
    if probe.get("external_decision_handler") != "INTENTIONALLY_UNSUPPORTED_FOR_PROBE":
        return None
    if probe.get("production_decision_reached_natively") is not True:
        return None
    family = probe.get("omitted_handler")
    if not isinstance(family, str) or not family:
        return None
    actor: str | None = None
    for step in record.get("native_procedure") or ():
        if not isinstance(step, dict):
            continue
        if str(step.get("operation")) != "NATIVE_RESOLVE_TOP_OF_STACK":
            continue
        details = step.get("details") or {}
        expected = details.get("expected_decision_actor")
        if isinstance(expected, str) and expected:
            actor = expected
        break
    if actor is None:
        return None
    return engine_decision_class(family), actor


def _life(principal: str, value: int) -> TerminalCheck:
    return TerminalCheck("life", principal=principal, value=value)


def _event(event_type: str, *where: tuple[str, Any], count: int | None = None) -> TerminalCheck:
    """Engine tape events of one type meeting every field constraint.

    ``count=None`` needs at least one; an integer needs exactly that many.
    """
    return TerminalCheck("events", value=count, event_type=event_type, where=tuple(where))


def _after(later: TerminalCheck, earlier: TerminalCheck) -> TerminalCheck:
    """Some event of ``later``'s pattern follows the first of ``earlier``'s."""
    return TerminalCheck(
        "events_follow",
        event_type=later.event_type,
        where=later.where,
        value=(earlier.event_type, earlier.where),
    )


def _before(earlier: TerminalCheck, later: TerminalCheck) -> TerminalCheck:
    """Every event of ``earlier``'s pattern precedes the first of ``later``'s."""
    return TerminalCheck(
        "events_precede",
        event_type=earlier.event_type,
        where=earlier.where,
        value=(later.event_type, later.where),
    )


def _commander_damage(owner: str, commander: str, damaged: str, amount: int) -> TerminalCheck:
    return TerminalCheck(
        "commander_damage", principal=owner, card_identity=commander, value=(damaged, amount)
    )


def _combat_damage_to_player(source: str, player: str, amount: int) -> TerminalCheck:
    return _event(
        "DAMAGED_PLAYER",
        ("source_object", source),
        ("target_player", player),
        ("amount", amount),
        ("combat", True),
        count=1,
    )


def _player_loses(player: str) -> TerminalCheck:
    return _event("LOST", ("player_player", player), count=1)


def _commander_damage_loss(
    attacker: str, owner: str, commander: str, damaged: str
) -> tuple[tuple[str, Any], ...]:
    """CR 903.10a / 704.6c: one commander's combat damage takes a player to 21.

    The engine's own commander-damage readback reads 21 from that commander,
    the engine reports the loss, and the commander's combat damage precedes it.
    """
    damage = _combat_damage_to_player(attacker, damaged, 2)
    lost = _player_loses(damaged)
    return (
        (f"commander_damage_total:{damaged}:21", _commander_damage(owner, commander, damaged, 21)),
        (f"player_loses:{damaged}", (lost, _before(damage, lost))),
    )


def _named(event_type: str, key: str, name: str, *where: tuple[str, Any]) -> TerminalCheck:
    """Engine events of a type whose ``key`` is exactly the name ``name``."""
    return _event(event_type, (key, name), *where)


def _exactly(check: TerminalCheck, count: int) -> TerminalCheck:
    """The same event pattern, needing exactly ``count`` matching events."""
    return TerminalCheck("events", value=count, event_type=check.event_type, where=check.where)


def _extra_turn_spec() -> RowSpec:
    """WS05-MP-TURN-3/5: two extra turns, the later-created one taken first."""
    time_warp = _event("SPELL_CAST", ("source_object", "obj:mp-time-warp"), ("player_player", "P1"))
    nexus = _event("SPELL_CAST", ("source_object", "obj:mp-nexus"), ("player_player", "P3"))
    # Each spell leaves the stack as it resolves (Time Warp to the graveyard;
    # Nexus of Fate's replacement shuffles it into its owner's library): the
    # extra turn exists only from then on (CR 608.2).
    warp_resolved = _event("ZONE_CHANGE", ("target_object", "obj:mp-time-warp"), ("from", "STACK"))
    nexus_resolved = _event("ZONE_CHANGE", ("target_object", "obj:mp-nexus"), ("from", "STACK"))
    p3_turn = _event("BEGIN_TURN", ("player_player", "P3"))
    p2_turn = _event("BEGIN_TURN", ("player_player", "P2"))
    return RowSpec(
        mana_sources=(
            *(f"obj:turn-p1-island-{i}" for i in range(5)),
            *(f"obj:turn-p3-island-{i}" for i in range(7)),
        ),
        # The obligation passes through the rest of P1's turn, all of P3's and
        # into P2's, where the engine consumes P2's queued extra turn.
        max_decisions=320,
        token_bindings=(
            # XMage creates an extra turn as a pending turn modification and
            # announces nothing (its EXTRA_TURN event is only offered to
            # replacement effects when the turn is taken); the engine's own
            # pending queue is the observation, as for the coin-flip row's
            # extra_turn_created:P1. Each creation is ordered after its spell's
            # resolution: before it, no frame may read the new entry. Most
            # recently created is taken first (CR 500.7).
            (
                "extra_turn_created:P2",
                (
                    time_warp,
                    _before(time_warp, warp_resolved),
                    TerminalCheck(
                        "extra_turn_created", principal="P2", value=("P2",), after=warp_resolved
                    ),
                ),
            ),
            (
                "extra_turn_created:P3",
                (
                    nexus,
                    _before(nexus, nexus_resolved),
                    TerminalCheck(
                        "extra_turn_created",
                        principal="P3",
                        value=("P3", "P2"),
                        after=nexus_resolved,
                    ),
                ),
            ),
            ("next_turn:P3", (_before(time_warp, p3_turn), _before(nexus, p3_turn))),
            # P2's next turn is its queued extra turn, not its normal turn: the
            # engine still holds P2's entry while P3's extra turn runs, P2's turn
            # follows P3's, and once P2's turn has begun the entry is consumed.
            (
                "next_turn:P2",
                (
                    _before(p3_turn, p2_turn),
                    TerminalCheck(
                        "pending_extra_turns_between", value=("P2",), after=p3_turn, before=p2_turn
                    ),
                    TerminalCheck("pending_extra_turns_between", value=(), after=p2_turn),
                ),
            ),
        ),
    )


def _response_spec(responder: str, response: str, spell: str, target: str, forest: str) -> RowSpec:
    """MICRO_PRIORITY / MICRO_STACK: a response resolves before the spell it answers.

    ``responder`` casts the record's response through the engine's own
    legal-action domain while ``spell`` is on the stack; the response resolves
    first (CR 405.5), then the spell deals its 3 damage to the record's target,
    which survives, and leaves the stack: the stack is empty again.
    """
    cast = _event("SPELL_CAST", ("source_object", response), ("player_player", responder))
    pushed = _event("ZONE_CHANGE", ("target_object", response), ("from", "HAND"), ("to", "STACK"))
    resolved = _event(
        "ZONE_CHANGE", ("target_object", response), ("from", "STACK"), ("to", "GRAVEYARD")
    )
    damage = _event(
        "DAMAGED_PERMANENT", ("source_object", spell), ("target_object", target), ("amount", 3)
    )
    spell_resolved = _event(
        "ZONE_CHANGE", ("target_object", spell), ("from", "STACK"), ("to", "GRAVEYARD")
    )
    return RowSpec(
        mana_sources=(forest,),
        terminal_checks=(
            _exactly(_event("ZONE_CHANGE", ("target_object", target), ("from", "BATTLEFIELD")), 0),
        ),
        token_bindings=(
            (
                # The responder held priority: its scripted priority frame cast
                # the response, and the engine attributes the cast to it.
                f"priority:{responder}",
                (
                    TerminalCheck("selected_frame", value="priority", label="Giant Growth"),
                    _exactly(cast, 1),
                ),
            ),
            ("spell_cast:Giant_Growth", _exactly(cast, 1)),
            ("stack_push:Giant_Growth", (_exactly(pushed, 1), _before(pushed, cast))),
            ("resolve:Giant_Growth", (_exactly(resolved, 1), _before(resolved, damage))),
            (
                "resolve:Lightning_Bolt",
                (
                    _exactly(damage, 1),
                    _exactly(spell_resolved, 1),
                    _before(resolved, spell_resolved),
                ),
            ),
        ),
    )


def _apnap_triggers(source: str, seats: tuple[str, ...], entering: str) -> tuple[Any, ...]:
    """Simultaneous triggers of every seat's ``source`` put on the stack in APNAP order.

    One event (``entering`` enters the battlefield) triggers every seat's
    ``source`` at once: every trigger is put on the stack after that event and
    before the first of them resolves (CR 603.3b), in APNAP order from the
    active player (CR 101.4), so they resolve in the reverse order.
    """
    triggers = _named("TRIGGERED_ABILITY", "source_name", source)
    gains = _named("GAINED_LIFE", "source_name", source)
    enters = _event("ZONE_CHANGE", ("target_object", entering), ("to", "BATTLEFIELD"))
    return (
        (
            "simultaneous_trigger_event",
            (
                _exactly(triggers, len(seats)),
                _before(enters, triggers),
                _before(triggers, gains),
            ),
        ),
        (
            "APNAP_stack_order",
            (
                TerminalCheck(
                    "event_order",
                    event_type="TRIGGERED_ABILITY",
                    where=triggers.where,
                    value=("player_player", seats),
                ),
                TerminalCheck(
                    "event_order",
                    event_type="GAINED_LIFE",
                    where=gains.where,
                    value=("target_player", tuple(reversed(seats))),
                ),
            ),
        ),
    )


def _priority_response(seats: tuple[str, ...], responder: str) -> RowSpec:
    """WS05-MP-PRIO-N: the live priority ring and the pass count reset by an action.

    With P1's Bolt on the stack, priority passes P1..PN in seat order (CR
    117.3d, 800.4); the last seat responds, receives priority again (CR
    117.3c), and every other live player must pass again before the response
    resolves (CR 117.4). The Bolt resolves after the response.
    """
    ring = tuple(seats)
    reset = (*ring, responder, *ring[:-1])
    response, bolt = "obj:mp-response", "obj:mp-bolt"
    cast = _event("SPELL_CAST", ("source_object", response), ("player_player", responder), count=1)
    bolt_leaves = _event("ZONE_CHANGE", ("target_object", bolt), ("from", "STACK"))
    resolved = _event(
        "ZONE_CHANGE", ("target_object", response), ("from", "STACK"), ("to", "GRAVEYARD")
    )
    return RowSpec(
        mana_sources=(f"obj:ws05-prio{len(seats)}-green-0",),
        terminal_checks=(
            TerminalCheck("on_battlefield", principal=responder, card_identity="Grizzly Bears"),
        ),
        token_bindings=(
            ("priority_ring_live_order", TerminalCheck("frame_order", value=("priority", ring))),
            (
                "priority_action_resets_pass_count",
                (
                    TerminalCheck("frame_order", value=("priority", reset)),
                    _before(resolved, bolt_leaves),
                ),
            ),
            ("response_on_stack", (cast, _before(cast, bolt_leaves))),
        ),
    )


def _player_leaves(victim: str) -> tuple[tuple[str, Any], ...]:
    """CR 800.4a: the victim loses and leaves; everything it owns leaves too.

    The engine reports the loss, its readback shows the victim lost and gone,
    every move of the victim's objects out of the game follows the loss, and
    nothing the victim owns is left on the battlefield.
    """
    lost = _player_loses(victim)
    return (
        (f"player_leaves:{victim}", (lost, TerminalCheck("player_left", principal=victim))),
        (
            "multiplayer_cleanup:CR800.4",
            (
                _before(lost, _event("ZONE_CHANGE", ("player_player", victim), ("to", "OUTSIDE"))),
                TerminalCheck("battlefield_exact", principal=victim, value=()),
            ),
        ),
    )


def _ring_after_loss(victim: str, ring: tuple[str, ...]) -> tuple[TerminalCheck, ...]:
    """After the loss the engine asks priority of the live players in seat
    order only (CR 800.4a): never of the victim again."""
    return (
        TerminalCheck("frame_order", value=("priority", ring)),
        TerminalCheck("no_frame", principal=victim, value="priority"),
    )


# FULL107 denominator rows, onboarded one at a time, each with its record's own
# mana sources and an explicit check for every terminal postcondition its prose
# states. (CARD_24 verifies too, but the actual-card corpus is AF07's obligation,
# not a denominator row, so it earns no FULL107 credit here.)
ROWS: dict[str, RowSpec] = {
    "MICRO_TRIGGERS": RowSpec(
        mana_sources=("obj:trigger-forest-1", "obj:trigger-forest-2"),
        terminal_checks=(
            TerminalCheck("trigger_count", source_name="Warstorm Surge", value=1),
            _life("P2", 38),
        ),
    ),
    "PILOT_PRIORITY": RowSpec(mana_sources=("obj:pilot-mountain",)),
    "PILOT_TARGET": RowSpec(mana_sources=("obj:pilot-mountain",)),
    "MICRO_TARGETS": RowSpec(mana_sources=("obj:pilot-mountain",)),
    "WS05-MP-COMBAT-4": RowSpec(),
    "WS05-MP-COMBAT-5": RowSpec(),
    "PILOT_DECLARE_ATTACKER": RowSpec(
        terminal_checks=(
            TerminalCheck("tapped", principal="P1", card_identity="Grizzly Bears", value=True),
        ),
    ),
    "WS05-CMD-TAX-2": RowSpec(
        mana_sources=tuple(f"obj:tax-mountain-{index}" for index in range(4)),
        terminal_checks=(TerminalCheck("commander_prior_casts", principal="P1", value=3),),
        commander_printed_mana_value=0,
    ),
    "CARD_02": RowSpec(
        terminal_checks=(
            TerminalCheck(
                "on_battlefield", principal="P1", card_identity="Rograkh, Son of Rohgahh"
            ),
            TerminalCheck("commander_prior_casts", principal="P1", value=1),
            TerminalCheck("no_mana_payment"),
        ),
    ),
    # The 4-player instance of WS05-CMD-TAX-2: same commander, same two prior
    # casts, same four declared Mountains, same postcondition.
    "WS05-CMD-TAX-4": RowSpec(
        mana_sources=tuple(f"obj:tax-mountain-{index}" for index in range(4)),
        terminal_checks=(TerminalCheck("commander_prior_casts", principal="P1", value=3),),
        commander_printed_mana_value=0,
    ),
    # Finale of Revelation costs {X}{U}{U}. "X=3 is bound into the announced
    # spell and cost calculation by the Rules Core": the engine charges X + 2
    # mana and the resolved spell draws X cards. Both are read from the engine,
    # not from the announced number.
    "PILOT_ANNOUNCE_X": RowSpec(
        mana_sources=tuple(f"obj:finale-island-{index}" for index in range(1, 6)),
        terminal_checks=(
            TerminalCheck("mana_charged", value=5),
            TerminalCheck("draws", principal="P1", value=3),
        ),
    ),
    # "In 3P multiplayer, starting player P1 draws on first turn" (CR 103.8a
    # exempts only a two-player game): the engine's first BEGIN_TURN is P1's and
    # P1 draws exactly one card in that turn's draw step, the record's checkpoint.
    "WS05-CMD-START-3": RowSpec(observe_from_game_start=True),
    # Phyrexian Arena and Mystic Remora trigger together at P1's upkeep; the
    # record orders Arena onto the stack first. "Both triggers are on stack in the
    # selected relative order" is read from the order the engine put them there.
    # (The record's counters {"age": 0} place no counter.)
    "PILOT_TRIGGER_ORDER": RowSpec(
        terminal_checks=(
            TerminalCheck(
                "stack_order", principal="P1", value=("Phyrexian Arena", "Mystic Remora")
            ),
        ),
    ),
    # "Selected mode is the provider-offered Devil-token mode": the spell resolves
    # exactly that mode, three Devils and no damage from the other mode.
    "PILOT_CHOOSE_MODE": RowSpec(
        mana_sources=tuple(f"obj:pilot-burn-mountain-{index}" for index in range(1, 6)),
        mode_bindings=(("create_devils", "Devil creature tokens"),),
        terminal_checks=(
            TerminalCheck("tokens_created", card_identity="Devil", value=3),
            TerminalCheck("no_permanent_damage"),
        ),
    ),
    # MICRO_MODES is the same mode obligation as PILOT_CHOOSE_MODE on a different
    # record; its 1.0.7 successor scripts the opening cast explicitly, so the
    # decision is reached through the engine's own legal-action domain.
    "MICRO_MODES": RowSpec(
        mana_sources=tuple(f"obj:micro-modes-mana-{index}" for index in range(5)),
        mode_bindings=(("create_devils", "Devil creature tokens"),),
        terminal_checks=(
            TerminalCheck("tokens_created", card_identity="Devil", value=3),
            TerminalCheck("no_permanent_damage"),
        ),
    ),
    # Magma Opus ({6}{U}{R}) deals 4 damage divided as you choose among any
    # number of targets. The engine asks for one target and its share per
    # divided-damage frame (class target_amount; context numeric_min/numeric_max
    # and amount_remaining); the record's amount_assignment names the semantic
    # target and the amount of each leg. The record's own terminal postcondition
    # is the assignment itself: exactly 4 total, every selected target at least
    # 1. The engine then asks for the spell's two tap targets (a required
    # min-2/max-2 frame) which the record does not script; the obligation is
    # already observed and the row stops there rather than inventing targets.
    "PILOT_TARGET_AMOUNT": RowSpec(
        mana_sources=tuple(
            [f"obj:pilot_target_amount-mountain-{index}" for index in range(7)]
            + ["obj:pilot_target_amount-island-0"]
        ),
        terminal_checks=(
            TerminalCheck("assignment_total", value=4),
            TerminalCheck("assignment_minimum", value=1),
        ),
    ),
    # PILOT_MULTI_AMOUNT is the same Magma Opus obligation on the multi_amount
    # record; the engine class mapping (multi_amount -> target_amount) is the
    # one already declared above.
    "PILOT_MULTI_AMOUNT": RowSpec(
        mana_sources=tuple(
            [f"obj:pilot_multi_amount-mountain-{index}" for index in range(7)]
            + ["obj:pilot_multi_amount-island-0"]
        ),
        terminal_checks=(
            TerminalCheck("assignment_total", value=4),
            TerminalCheck("assignment_minimum", value=1),
        ),
    ),
    # MICRO_COSTS: P2 casts Hex ({4}{B}{B}) targeting P1's two commanders and
    # four of P1's creatures while P1 controls Esior, whose static ability adds
    # {3} to an opponent's spell that targets a commander. The engine's own
    # payment frame exposes the determined cost ({7}{B}{B}); the verifier binds
    # that determination plus the mana actually charged to the scripted cast.
    "MICRO_COSTS": RowSpec(
        mana_sources=tuple(f"obj:cost-swamp-{index}" for index in range(1, 10)),
        cost_obligation=("obj:micro-hex", "{4}{B}{B}", "{7}{B}{B}"),
    ),
    # The fail-closed negatives: reach the decision frame the record names, then
    # refuse it explicitly and with no state mutation. The obligation is the
    # typed refusal itself, never a timeout and never a selected option.
    "NEGATIVE_FIRST_OPTION": RowSpec(
        mana_sources=tuple(f"obj:negative_first_option-mana-{index}" for index in range(5)),
    ),
    "NEGATIVE_GUI_DEFAULT": RowSpec(
        mana_sources=tuple(f"obj:negative_gui_default-mana-{index}" for index in range(5)),
    ),
    "NEGATIVE_RANDOM_OPTION": RowSpec(
        mana_sources=("obj:negative_random_option-mana-0",),
    ),
    "NEGATIVE_SILENT_SKIP": RowSpec(
        mana_sources=("obj:negative_silent_skip-mana-0",),
    ),
    # The sibling refusal on the engine's own attack declaration frame.
    "NEGATIVE_INTERNAL_AI": RowSpec(),
    # PILOT_CHOOSE_USE (contract 1.0.21 E1): P1 casts Keldon Marauders with
    # Path of Ancestry's mana; it shares a creature type with P1's commander,
    # so Path scries 1, and P1 keeps the known top card (the record's
    # choose_use false, bound by its decision_family_binding to XMage's 0..1
    # card frame as the empty selection).
    "PILOT_CHOOSE_USE": RowSpec(
        mana_sources=("obj:path", "obj:path-mountain"),
        scry_binding="obj:top-known",
        token_bindings=(
            (
                "choose_use_frame:P1",
                TerminalCheck("scripted_frame", principal="P1", value="target", label="(scry)"),
            ),
            (
                "scry_choice:keep_top",
                (
                    TerminalCheck("scripted_key", principal="P1", value=("target", "false")),
                    _exactly(_event("ZONE_CHANGE", ("target_object", "obj:top-known")), 0),
                ),
            ),
        ),
    ),
    # PILOT_PILE (contract 1.0.21 E3): P1 casts Fact or Fiction from its
    # declared Islands; on resolution P1 names P2 to separate, and XMage asks
    # P2 to select the first pile on its object frame (the record's pile_a:
    # two of the five revealed cards); P1 then takes "Pile 1". The partition
    # is what the engine did with the five cards: the first pile's two go to
    # P1's hand, the second pile's three (the record's pile_b) to the
    # graveyard, after P1's scripted pile choice.
    "PILOT_PILE": RowSpec(
        mana_sources=tuple(f"obj:fof-island-{index}" for index in range(4)),
        token_bindings=(
            (
                "pile_frame:P2",
                TerminalCheck(
                    "scripted_frame", principal="P2", value="choose_object", label="first pile"
                ),
            ),
            (
                "partition_created:2/3",
                (
                    *(
                        _exactly(
                            _event(
                                "ZONE_CHANGE",
                                ("target_object", obj),
                                ("from", "LIBRARY"),
                                ("to", "GRAVEYARD"),
                                ("source_object", "obj:fof"),
                            ),
                            1,
                        )
                        for obj in ("obj:fof-2", "obj:fof-3", "obj:fof-4")
                    ),
                    _exactly(
                        _event(
                            "ZONE_CHANGE",
                            ("from", "LIBRARY"),
                            ("to", "GRAVEYARD"),
                            ("source_object", "obj:fof"),
                        ),
                        3,
                    ),
                    _exactly(
                        _event(
                            "ZONE_CHANGE",
                            ("from", "LIBRARY"),
                            ("to", "HAND"),
                            ("source_object", "obj:fof"),
                        ),
                        2,
                    ),
                    TerminalCheck("selected_frame", value="pile", label="Pile 1"),
                ),
            ),
        ),
    ),
    # The yes/no sibling (contract 1.0.21 E2b): P1 casts Centaur Courser from
    # its declared Forests; it enters, P1's Garruk's Packleader triggers and the
    # engine asks "you may draw a card" on its own yes/no frame, which the
    # probe refuses explicitly.
    "NEGATIVE_DEFAULT_YES_NO": RowSpec(
        mana_sources=tuple(f"obj:neg-forest-{index}" for index in range(3)),
    ),
    # The parent-class sibling: the record declares its own
    # ``negative_fallback_probe`` (omitted_handler choose_object, external
    # handler intentionally unavailable) instead of a decision_script step, so
    # the executor refuses the engine's own frame from that declaration. The
    # obligation is the typed fail-closed refusal of the discard decision, with
    # no option selected and no state mutation.
    "NEGATIVE_PARENT_CLASS_FALLBACK": RowSpec(),
    # PILOT_CHOICE: P1's Utopia Sprawl (rebuilt on the stack through the declared
    # causal route) resolves onto the Forest and the engine asks P1 its
    # as-enters color on its own choice frame; the record's key names the
    # offer, "choice:RED" is that answer.
    "PILOT_CHOICE": RowSpec(),
    # PILOT_CHOOSE_ABILITY: Jeska stands at its checkpoint loyalty (3) and P1
    # chooses its 0 ability ("Choose target creature ... triple that damage"),
    # which XMage offers, with Jeska's other loyalty ability, on P1's priority
    # frame. The record's key names that ability.
    "PILOT_CHOOSE_ABILITY": RowSpec(
        ability_bindings=(("loyalty_0_triple_damage", ("obj:jeska", "0: Choose target creature")),),
    ),
    # The commander zone choice (CR 903.9): the opponent's removal spell is
    # rebuilt on the stack through the declared causal route and resolves; the
    # engine then asks the commander's owner, on its own yes/no frame, whether
    # the commander goes to the command zone. Graveyard and exile are a choice
    # after the move (CR 903.9a); hand and library replace the move (CR 903.9b).
    # The tokens are verified against the engine's zone-change events of the
    # record's commander object and the scripted answer on that frame.
    **{
        f"WS05-CMD-ZONE-{zone}-{answer}": RowSpec()
        for zone in ("GY", "EXILE", "HAND", "LIB")
        for answer in ("YES", "NO")
    },
    # PILOT_CHOOSE_OBJECT: P2's Raven's Crime resolves (rebuilt on the stack
    # through the declared causal route) and the engine asks P1, on its own
    # object frame, which card to discard. "object_selected:obj:p1-hand-a" is
    # what that answer does: the Mountain (hand-a) goes from P1's hand to the
    # graveyard and the Island (hand-b) does not move.
    "PILOT_CHOOSE_OBJECT": RowSpec(
        token_bindings=(
            (
                "object_selected:obj:p1-hand-a",
                (
                    _event(
                        "ZONE_CHANGE",
                        ("target_object", "obj:p1-hand-a"),
                        ("from", "HAND"),
                        ("to", "GRAVEYARD"),
                    ),
                    _exactly(
                        _event("ZONE_CHANGE", ("target_object", "obj:p1-hand-b"), ("from", "HAND")),
                        0,
                    ),
                ),
            ),
        ),
    ),
    # PILOT_REPLACEMENT_EFFECT: the scenario of WS05-CMD-ZONE-HAND-YES (P2's
    # Unsummon on P1's commander, CR 903.9b). The record names the owner's
    # command-zone answer "commander_replacement_chosen:command"; it is the
    # same engine-verified fact as the vocabulary's "commander_choice:command".
    # XMage asks the replacement as one yes/no question on its choose_use
    # surface ("Move ... to command zone instead of your hand?"), so
    # "replacement_effect_frame:P1" is that question asked of P1, exactly once.
    "PILOT_REPLACEMENT_EFFECT": RowSpec(
        token_bindings=(
            (
                "replacement_effect_frame:P1",
                TerminalCheck(
                    "frame_count",
                    principal="P1",
                    value=(BOOLEAN_DECISION_CLASS, 1),
                    label="to command zone instead of",
                ),
            ),
            ("commander_replacement_chosen:command", VocabularyToken("commander_choice:command")),
        ),
    ),
    # PILOT_MANA_PAYMENT: MICRO_MANA_PAYMENT's scenario. With P2's Bolt on the
    # stack (rebuilt causally), P1 casts Counterspell on it (the record's
    # stack:1) from its two declared Islands. "mana_paid:UU" is the engine
    # charging exactly two mana, spending blue from the pool, for the one
    # Counterspell cast; the engine itself refuses a non-blue payment of {U}{U}.
    "PILOT_MANA_PAYMENT": RowSpec(
        mana_sources=("obj:island-a", "obj:island-b"),
        token_bindings=(
            (
                "mana_paid:UU",
                (
                    TerminalCheck("mana_charged", value=2),
                    TerminalCheck("pool_spend", value="blue"),
                    _exactly(
                        _event(
                            "SPELL_CAST",
                            ("source_object", "obj:counterspell"),
                            ("player_player", "P1"),
                        ),
                        1,
                    ),
                ),
            ),
        ),
    ),
    # MICRO_COMBAT: the record's requested combat (P1's Bears attack P2 and
    # P2's Bears block it) is declared on the engine's own frames; the two 2/2s
    # deal combat damage to each other simultaneously and state-based actions
    # destroy both (CR 510.2, 704.5g): no source destroys them.
    "MICRO_COMBAT": RowSpec(
        token_bindings=(
            (
                "combat_damage:attacker_to_blocker:2",
                _event(
                    "DAMAGED_PERMANENT",
                    ("source_object", "obj:micro-attacker"),
                    ("target_object", "obj:micro-blocker"),
                    ("amount", 2),
                    ("combat", True),
                    count=1,
                ),
            ),
            (
                "combat_damage:blocker_to_attacker:2",
                _event(
                    "DAMAGED_PERMANENT",
                    ("source_object", "obj:micro-blocker"),
                    ("target_object", "obj:micro-attacker"),
                    ("amount", 2),
                    ("combat", True),
                    count=1,
                ),
            ),
            (
                "state_based_actions",
                (
                    _event(
                        "DESTROYED_PERMANENT",
                        ("target_object", "obj:micro-attacker"),
                        ("source_object", None),
                        count=1,
                    ),
                    _event(
                        "DESTROYED_PERMANENT",
                        ("target_object", "obj:micro-blocker"),
                        ("source_object", None),
                        count=1,
                    ),
                    _before(
                        _event("DAMAGED_PERMANENT", ("combat", True)),
                        _event("DESTROYED_PERMANENT"),
                    ),
                ),
            ),
            (
                "both_creatures_die",
                tuple(
                    _event(
                        "ZONE_CHANGE",
                        ("target_object", creature),
                        ("from", "BATTLEFIELD"),
                        ("to", "GRAVEYARD"),
                        count=1,
                    )
                    for creature in ("obj:micro-attacker", "obj:micro-blocker")
                ),
            ),
        ),
    ),
    # WS05-CMD-DMG-SAME-21: Isamaru (P1's commander) has dealt P2 19 combat
    # damage (restored and verified); the requested attack deals 2 more and
    # P2 loses for 21 commander damage from one commander while at 38 life.
    "WS05-CMD-DMG-SAME-21": RowSpec(
        terminal_checks=(_life("P2", 38),),
        token_bindings=(
            (
                "commander_combat_damage:P2:2",
                _combat_damage_to_player("obj:isamaru", "P2", 2),
            ),
            *_commander_damage_loss("obj:isamaru", "P1", "Isamaru, Hound of Konda", "P2"),
        ),
    ),
    # WS05-CMD-ELIM-4: the same commander-damage loss, then the multiplayer
    # cleanup (CR 800.4a): every object P2 owns leaves the game after the loss.
    "WS05-CMD-ELIM-4": RowSpec(
        terminal_checks=(_life("P2", 38),),
        token_bindings=(
            *_commander_damage_loss("obj:elim-isamaru", "P1", "Isamaru, Hound of Konda", "P2"),
            (
                "multiplayer_cleanup:CR800.4",
                _before(
                    _player_loses("P2"),
                    _event("ZONE_CHANGE", ("player_player", "P2"), ("to", "OUTSIDE")),
                ),
            ),
            (
                "object_leaves_game:obj:p2-owned",
                _event(
                    "ZONE_CHANGE",
                    ("target_object", "obj:p2-owned"),
                    ("from", "BATTLEFIELD"),
                    ("to", "OUTSIDE"),
                    count=1,
                ),
            ),
        ),
    ),
    # MICRO_ZONE_CHANGES: the Bolt on the stack (rebuilt through the declared
    # causal route) resolves and goes to its owner's graveyard as a new object
    # (CR 400.7): the engine reports the move made a new object.
    "MICRO_ZONE_CHANGES": RowSpec(
        token_bindings=(
            (
                "resolve:obj:micro-bolt-stack",
                (
                    _event(
                        "DAMAGED_PLAYER",
                        ("source_object", "obj:micro-bolt-stack"),
                        ("target_player", "P2"),
                        ("amount", 3),
                        count=1,
                    ),
                    _before(
                        _event("DAMAGED_PLAYER", ("source_object", "obj:micro-bolt-stack")),
                        _event(
                            "ZONE_CHANGE",
                            ("target_object", "obj:micro-bolt-stack"),
                            ("from", "STACK"),
                        ),
                    ),
                ),
            ),
            (
                "zone_change:stack->graveyard",
                _event(
                    "ZONE_CHANGE",
                    ("target_object", "obj:micro-bolt-stack"),
                    ("from", "STACK"),
                    ("to", "GRAVEYARD"),
                    count=1,
                ),
            ),
        ),
    ),
    # MICRO_STATE_BASED_ACTIONS: Night of Souls' Betrayal gives every creature
    # -1/-1; the engine shows it applied (P1's Grizzly Bears read 1/1). Memnite
    # (printed 1/1) is cast for {0}, enters, and is put into its owner's
    # graveyard by the toughness state-based action (CR 704.5f): nothing
    # destroys it and nothing damages it. The engine reports Memnite's
    # last-known 0/0 on that move.
    "MICRO_STATE_BASED_ACTIONS": RowSpec(
        token_bindings=(
            (
                # The engine's own last-known 0/0 of Memnite as it left the
                # battlefield, with the -1/-1 effect visibly applied elsewhere.
                "continuous_pt:obj:micro-zero:0/0",
                (
                    _exactly(
                        _event(
                            "ZONE_CHANGE",
                            ("target_object", "obj:micro-zero"),
                            ("from", "BATTLEFIELD"),
                            ("last_power", 0),
                            ("last_toughness", 0),
                        ),
                        1,
                    ),
                    TerminalCheck(
                        "power_toughness",
                        principal="P1",
                        card_identity="Grizzly Bears",
                        value=(1, 1),
                    ),
                ),
            ),
            (
                "state_based_actions",
                (
                    _event("DESTROYED_PERMANENT", ("target_object", "obj:micro-zero"), count=0),
                    _event("DAMAGED_PERMANENT", ("target_object", "obj:micro-zero"), count=0),
                    _before(
                        _event(
                            "ZONE_CHANGE",
                            ("target_object", "obj:micro-zero"),
                            ("to", "BATTLEFIELD"),
                        ),
                        _event(
                            "ZONE_CHANGE",
                            ("target_object", "obj:micro-zero"),
                            ("from", "BATTLEFIELD"),
                            ("to", "GRAVEYARD"),
                        ),
                    ),
                ),
            ),
            (
                "move_to_graveyard:obj:micro-zero",
                _event(
                    "ZONE_CHANGE",
                    ("target_object", "obj:micro-zero"),
                    ("from", "BATTLEFIELD"),
                    ("to", "GRAVEYARD"),
                    ("source_object", None),
                    count=1,
                ),
            ),
        ),
    ),
    "MICRO_PRIORITY": _response_spec(
        "P2", "obj:micro-growth", "obj:micro-bolt", "obj:micro-target", "obj:micro-forest"
    ),
    "MICRO_STACK": _response_spec(
        "P2", "obj:micro-growth", "obj:micro-bolt", "obj:micro-target", "obj:micro-forest"
    ),
    "WS05-MP-PRIO-3": _priority_response(("P1", "P2", "P3"), "P3"),
    "WS05-MP-PRIO-5": _priority_response(("P1", "P2", "P3", "P4", "P5"), "P5"),
    "WS05-MP-TRIG-3": RowSpec(
        mana_sources=("obj:mp-trigger-forest-1", "obj:mp-trigger-forest-2"),
        token_bindings=_apnap_triggers("Soul Warden", ("P1", "P2", "P3"), "obj:mp-enter"),
    ),
    "WS05-MP-TRIG-5": RowSpec(
        mana_sources=("obj:ws05-trig5-cast-0", "obj:ws05-trig5-cast-1"),
        token_bindings=_apnap_triggers(
            "Soul Warden", ("P1", "P2", "P3", "P4", "P5"), "obj:mp-enter"
        ),
    ),
    # MICRO_REPLACEMENT: Hill Giant (3 power) attacks P2 unblocked, as the
    # requested combat states; Gratuitous Violence doubles the combat damage it
    # would deal (CR 614.1a), so P2 is dealt 6, never 3 (CR 510.1a: a creature
    # assigns combat damage equal to its power).
    "MICRO_REPLACEMENT": RowSpec(
        terminal_checks=(_life("P2", 34),),
        token_bindings=(
            (
                "damage_would_be:P2:3",
                TerminalCheck(
                    "power_toughness", principal="P1", card_identity="Hill Giant", value=(3, 3)
                ),
            ),
            (
                "replacement_effect:double",
                (
                    TerminalCheck(
                        "on_battlefield", principal="P1", card_identity="Gratuitous Violence"
                    ),
                    _combat_damage_to_player("obj:micro-3power", "P2", 6),
                    _exactly(_event("DAMAGED_PLAYER", ("target_player", "P2")), 1),
                ),
            ),
        ),
    ),
    # WS05-MP-TURN-3/5 (contract 1.0.21, #441): P1 casts Time Warp on P2, then
    # P3 casts Nexus of Fate on P1's turn; the most recently created extra turn
    # is taken first (CR 500.7): P3's, then P2's. A creation is bound to its
    # spell's cast and the engine's pending extra turns read back after it;
    # the order taken to every turn's start (BEGIN_TURN). P1 and then P3
    # declare no attackers and each discards one template card at its cleanup
    # (scripted, CR 508.1, 514.1).
    "WS05-MP-TURN-3": _extra_turn_spec(),
    "WS05-MP-TURN-5": _extra_turn_spec(),
    # MICRO_LAYERS (contract 1.0.21, FIXTURE_OBSERVABILITY_ERRATUM, #441): the
    # layer tokens are applications of continuous effects when characteristics
    # are determined (CR 613), not events, so each is read from the engine's
    # characteristics of a permanent that discriminates it. Humility (P1) makes
    # every creature a 1/1 with no abilities (layers 6 and 7b); Glorious Anthem
    # gives P1's creatures +1/+1 (layer 7c, applied after 7b: CR 613.4b-c).
    # P2's Serra Angel (printed 4/4, flying, vigilance) proves layers 6 and 7b;
    # P1's Bears (2/2) proves 7c on top of 7b, and P3's Bears (1/1, no Anthem)
    # 7b without 7c. Humility ignored reads a 4/4 flier and 3/3 Bears; Anthem
    # ignored reads 1/1 Bears.
    "MICRO_LAYERS": RowSpec(
        token_bindings=(
            (
                "layer6_remove_abilities",
                (
                    TerminalCheck(
                        "keyword_absent",
                        principal="P2",
                        card_identity="Serra Angel",
                        value="flying",
                    ),
                    TerminalCheck(
                        "keyword_absent",
                        principal="P2",
                        card_identity="Serra Angel",
                        value="vigilance",
                    ),
                ),
            ),
            (
                "layer7b_set_pt:1/1",
                (
                    TerminalCheck(
                        "power_toughness", principal="P2", card_identity="Serra Angel", value=(1, 1)
                    ),
                    TerminalCheck(
                        "power_toughness",
                        principal="P3",
                        card_identity="Grizzly Bears",
                        value=(1, 1),
                    ),
                ),
            ),
            (
                "layer7c_modify_pt:+1/+1",
                TerminalCheck(
                    "power_toughness", principal="P1", card_identity="Grizzly Bears", value=(2, 2)
                ),
            ),
        ),
    ),
    # MICRO_CONTINUOUS_EFFECTS (1.0.20 obligation erratum): Psychosis Crawler's
    # power and toughness are a characteristic-defining ability (CR 604.3) the
    # engine evaluates from P1's hand size; at the reachable 13-card hand it
    # reads 13/13, and the Crawler triggers nothing in the obligation window.
    "MICRO_CONTINUOUS_EFFECTS": RowSpec(
        token_bindings=(
            (
                "continuous_pt_evaluated:13/13",
                (
                    TerminalCheck(
                        "power_toughness",
                        principal="P1",
                        card_identity="Psychosis Crawler",
                        value=(13, 13),
                    ),
                    TerminalCheck("hand_count", principal="P1", value=13),
                    _exactly(
                        _event("TRIGGERED_ABILITY", ("source_object", "obj:micro-crawler")), 0
                    ),
                ),
            ),
        ),
    ),
    # MICRO_PREVENTION: P1's 2-power attacker attacks P2 unblocked (the
    # requested combat); P2 casts Fog on its own priority in the declare
    # attackers step, and the engine prevents the 2 combat damage it would deal
    # P2 (CR 615.1): a prevention event and no damage, so P2 loses no life.
    "MICRO_PREVENTION": RowSpec(
        mana_sources=("obj:fog-forest-1",),
        terminal_checks=(_life("P2", 40),),
        token_bindings=(
            (
                "combat_damage_would_be:P2:2",
                (
                    TerminalCheck(
                        "power_toughness",
                        principal="P1",
                        card_identity="Grizzly Bears",
                        value=(2, 2),
                    ),
                    _exactly(_event("PREVENTED_DAMAGE", ("target_player", "P2"), ("amount", 2)), 1),
                ),
            ),
            (
                "prevention_applied",
                _exactly(
                    _event(
                        "PREVENTED_DAMAGE",
                        ("source_object", "obj:micro-fog"),
                        ("target_player", "P2"),
                    ),
                    1,
                ),
            ),
            (
                "combat_damage_prevented:P2:2",
                (
                    _exactly(_event("PREVENTED_DAMAGE", ("target_player", "P2"), ("amount", 2)), 1),
                    _exactly(_event("DAMAGED_PLAYER", ("target_player", "P2")), 0),
                ),
            ),
        ),
    ),
    "PILOT_DECLARE_BLOCKER": RowSpec(),
    # WS05-CMD-PARTNER-TAX (1.0.20 erratum): P1 casts both partners from the
    # command zone; the engine's own payment frame for each cast shows its tax
    # independently (CR 903.8): Rograkh ({0}, two prior casts) costs {4},
    # Kediss ({1}{R}, none) costs {1}{R}.
    "WS05-CMD-PARTNER-TAX": RowSpec(
        mana_sources=tuple(f"obj:partner-mountain-{index}" for index in range(6)),
        token_bindings=(
            ("tax:cmd:P1-A:+4", TerminalCheck("cast_cost", card_identity="cmd:P1-A", value="{4}")),
            (
                "tax:cmd:P1-B:+0",
                TerminalCheck("cast_cost", card_identity="cmd:P1-B", value="{1}{R}"),
            ),
        ),
    ),
    # WS05-CMD-PARTNER-ZONE: the record's game-start obligation is that both of
    # P1's partner commanders begin in the command zone as separate engine
    # identities (CR 903.4, 702.124). The evidence is the engine's own
    # constructed-state readback at the arrival checkpoint: each required
    # commander identity must be exactly one command-zone row of its owner's
    # seat. The two identities are distinct engine rows by construction, and
    # distinctness is read from those rows, never asserted from the record's
    # declared ``multiple_commander_relations``. Every other requested commander
    # (P2-A..P4-A) is covered by the construction verdict this executor already
    # requires, exactly as the native partner execution test's readback compare.
    "WS05-CMD-PARTNER-ZONE": RowSpec(
        observe_from_game_start=True,
        token_bindings=(
            (
                "game_start_command_zone:cmd:P1-A",
                TerminalCheck(
                    "game_start_command_zone",
                    principal="P1",
                    card_identity="Rograkh, Son of Rohgahh",
                ),
            ),
            (
                "game_start_command_zone:cmd:P1-B",
                TerminalCheck(
                    "game_start_command_zone",
                    principal="P1",
                    card_identity="Kediss, Emberclaw Familiar",
                ),
            ),
        ),
    ),
    # MICRO_CONTROL (1.0.20 caused-control erratum): P1 casts Control Magic on
    # P2's Grizzly Bears; once the Aura resolves, the engine moves control of
    # the Bears to P1 (CR 613.1b), its owner unchanged.
    "MICRO_CONTROL": RowSpec(
        mana_sources=tuple(f"obj:control-island-{index}" for index in range(4)),
        token_bindings=(
            (
                "control_effect_applied:P2->P1",
                (
                    _exactly(
                        _event(
                            "GAINED_CONTROL",
                            ("target_object", "obj:micro-controlled"),
                            ("player_player", "P1"),
                        ),
                        1,
                    ),
                    _before(
                        _event(
                            "ZONE_CHANGE",
                            ("target_object", "obj:micro-controlmagic"),
                            ("to", "BATTLEFIELD"),
                        ),
                        _event("GAINED_CONTROL", ("target_object", "obj:micro-controlled")),
                    ),
                ),
            ),
        ),
    ),
    # WS05-CMD-DMG-CONTROL (1.0.20 caused-control erratum): on P3's turn, P3
    # takes P1's commander Isamaru with Act of Treason and attacks P2 with it;
    # the 2 combat damage counts for Isamaru's own commander identity (CR
    # 903.10a), so P2 reaches 21 from it and loses while at 38 life.
    "WS05-CMD-DMG-CONTROL": RowSpec(
        mana_sources=tuple(f"obj:treason-mountain-{index}" for index in range(3)),
        terminal_checks=(_life("P2", 38),),
        token_bindings=(
            (
                "commander_combat_damage:P2:2:cmd:P1-A",
                (
                    _combat_damage_to_player("obj:isamaru-controlled", "P2", 2),
                    _before(
                        _event(
                            "GAINED_CONTROL",
                            ("target_object", "obj:isamaru-controlled"),
                            ("player_player", "P3"),
                        ),
                        _event("DAMAGED_PLAYER", ("source_object", "obj:isamaru-controlled")),
                    ),
                    _commander_damage("P1", "Isamaru, Hound of Konda", "P2", 21),
                ),
            ),
            (
                "player_loses:P2",
                (
                    _player_loses("P2"),
                    _before(
                        _combat_damage_to_player("obj:isamaru-controlled", "P2", 2),
                        _player_loses("P2"),
                    ),
                ),
            ),
        ),
    ),
    # MICRO_COPY: P1's Flare of Duplication (rebuilt causally above P2's Bolt)
    # copies the Bolt; the copy is created on the stack, never cast (CR
    # 707.10), keeps the copied target (the scripted choice), and resolves as a
    # distinct object before the original Bolt (CR 405.5).
    "MICRO_COPY": RowSpec(
        token_bindings=(
            (
                "copy_spell:Lightning_Bolt",
                (
                    _exactly(_named("COPIED_STACKOBJECT", "source_name", "Lightning Bolt"), 1),
                    _exactly(_named("SPELL_CAST", "source_name", "Lightning Bolt"), 0),
                ),
            ),
            (
                "copy_created_on_stack",
                (
                    _exactly(
                        _named(
                            "DAMAGED_PLAYER",
                            "source_name",
                            "Lightning Bolt",
                            ("target_player", "P2"),
                            ("amount", 3),
                            ("source_object", UNNAMED_OBJECT),
                        ),
                        1,
                    ),
                    _exactly(
                        _event(
                            "DAMAGED_PLAYER",
                            ("source_object", "obj:micro-bolt"),
                            ("target_player", "P2"),
                            ("amount", 3),
                        ),
                        1,
                    ),
                    _before(
                        _named("COPIED_STACKOBJECT", "source_name", "Lightning Bolt"),
                        _event("DAMAGED_PLAYER", ("source_object", "obj:micro-bolt")),
                    ),
                ),
            ),
        ),
    ),
    # MICRO_RULES_RANDOMNESS: P1 calls heads (scripted); the Rules RNG flips
    # under the record's own seed and the engine reports the result. The
    # record's predetermined result (HEADS) and its extra turn are observed
    # only if the engine's flip produced them; nothing sets the flip.
    "MICRO_RULES_RANDOMNESS": RowSpec(
        token_bindings=(
            (
                "rules_rng:coin_flip:HEADS",
                _exactly(
                    _event(
                        "COIN_FLIPPED",
                        ("source_object", "obj:micro-stitch"),
                        ("coin_result", "HEADS"),
                        ("coin_won", True),
                    ),
                    1,
                ),
            ),
            (
                # The won flip's extra turn is the engine's own pending turn
                # (taken after this one); it exists only if the flip was won.
                "extra_turn_created:P1",
                TerminalCheck("pending_extra_turns", value=("P1",)),
            ),
        ),
    ),
    # MICRO_MANA_PAYMENT: with P2's Bolt on the stack (rebuilt causally), P1
    # casts Counterspell on it (the record's stack:1), paying {U}{U} from its
    # two declared Islands; Counterspell counters the Bolt.
    "MICRO_MANA_PAYMENT": RowSpec(
        mana_sources=("obj:micro-island-a", "obj:micro-island-b"),
        token_bindings=(
            ("mana_abilities_activated:2", VocabularyToken("mana_paid:2")),
            (
                "mana_paid:UU",
                (
                    TerminalCheck("pool_spend", value="blue"),
                    _exactly(
                        _event(
                            "SPELL_CAST",
                            ("source_object", "obj:micro-counterspell"),
                            ("player_player", "P1"),
                        ),
                        1,
                    ),
                ),
            ),
            (
                "Counterspell_cast",
                (
                    _exactly(
                        _event(
                            "SPELL_CAST",
                            ("source_object", "obj:micro-counterspell"),
                            ("player_player", "P1"),
                        ),
                        1,
                    ),
                    _exactly(_event("COUNTERED", ("source_object", "obj:micro-counterspell")), 1),
                    _exactly(
                        _event(
                            "ZONE_CHANGE",
                            ("target_object", "obj:micro-bolt"),
                            ("source_object", "obj:micro-counterspell"),
                            ("from", "STACK"),
                            ("to", "GRAVEYARD"),
                        ),
                        1,
                    ),
                ),
            ),
        ),
    ),
    # WS05-MP-BLOCK-4: P1 attacks P2 (obj:mp-a2) and P3 (obj:mp-a3); every
    # block the engine offers P2 names only the attacker attacking P2.
    "WS05-MP-BLOCK-4": RowSpec(
        token_bindings=(
            (
                "legal_blocker_partition:P2",
                TerminalCheck(
                    "blocker_partition",
                    principal="P2",
                    value=(("obj:mp-a2",), ("obj:mp-a3",)),
                ),
            ),
        ),
    ),
    # The causal eliminations (WS05-MP-ELIM-*): the record asks for the victim
    # at 0 life before the state-based actions that remove it, which no
    # priority point shows (CR 704.3). The declared bolts are cast at the
    # victim through the engine's own frames; the engine deals the damage,
    # applies the loss (CR 704.5a) and the multiplayer cleanup (CR 800.4a).
    "WS05-MP-ELIM-OWNED-3": RowSpec(
        token_bindings=(
            *_player_leaves("P2"),
            (
                "object_leaves_game:obj:leave-owned",
                _exactly(
                    _event(
                        "ZONE_CHANGE",
                        ("target_object", "obj:leave-owned"),
                        ("from", "BATTLEFIELD"),
                        ("to", "OUTSIDE"),
                    ),
                    1,
                ),
            ),
        ),
        terminal_checks=(
            _before(
                _player_loses("P2"),
                _event("ZONE_CHANGE", ("target_object", "obj:leave-owned"), ("to", "OUTSIDE")),
            ),
        ),
    ),
    # WS05-MP-ELIM-STACK-3: P2's own Lightning Bolt (aimed at P1) is on the
    # stack when P2 loses. The engine removes P2's spell with P2 (CR 800.4a):
    # the stack is empty at the next priority, the Bolt never reaches the
    # graveyard by resolving, never deals its damage, and P1 stays at 40.
    "WS05-MP-ELIM-STACK-3": RowSpec(
        token_bindings=_player_leaves("P2"),
        terminal_checks=(
            # The engine removes the leaving player's spell from the stack
            # without an event (GameImpl.leave: getStack().removeIf); its own
            # stack after the loss is the evidence. The stack verifier showed
            # the spell on the stack before the loss was caused.
            TerminalCheck("stack_empty_after", event_type="LOST", where=(("player_player", "P2"),)),
            _exactly(
                _event("ZONE_CHANGE", ("target_object", "obj:leave-bolt"), ("to", "GRAVEYARD")), 0
            ),
            _exactly(_event("DAMAGED_PLAYER", ("source_object", "obj:leave-bolt")), 0),
            TerminalCheck("life", principal="P1", value=40),
        ),
    ),
    # WS05-MP-ELIM-CONTROL-3: P2's Control Magic (caused by its cast, verified
    # attached to P1's Bears with P2 controlling them) leaves the game with P2
    # (CR 800.4a), and the Bears stay on the battlefield, their control
    # returning to P1 when the Aura's effect ends (the engine's GAINED_CONTROL).
    "WS05-MP-ELIM-CONTROL-3": RowSpec(
        token_bindings=_player_leaves("P2"),
        terminal_checks=(
            _before(
                _player_loses("P2"),
                _event(
                    "ZONE_CHANGE",
                    ("target_object", "obj:leave-controlmagic"),
                    ("from", "BATTLEFIELD"),
                    ("to", "OUTSIDE"),
                ),
            ),
            _before(
                _player_loses("P2"),
                _event(
                    "GAINED_CONTROL",
                    ("target_object", "obj:p1-owned-controlled"),
                    ("player_player", "P1"),
                ),
            ),
            _exactly(
                _event(
                    "ZONE_CHANGE",
                    ("target_object", "obj:p1-owned-controlled"),
                    ("from", "BATTLEFIELD"),
                ),
                0,
            ),
        ),
    ),
    "WS05-MP-ELIM-PRIO-3": RowSpec(
        token_bindings=_player_leaves("P2"),
        terminal_checks=_ring_after_loss("P2", ("P1", "P3")),
    ),
    "WS05-MP-ELIM-5": RowSpec(
        token_bindings=_player_leaves("P3"),
        terminal_checks=_ring_after_loss("P3", ("P1", "P2", "P4", "P5")),
    ),
    # WS05-MP-ELIM-TURN-3: the victim is the active player. The turn continues
    # without an active player and the next turn is the next live player's
    # (CR 800.4a): P3's, never P2's.
    "WS05-MP-ELIM-TURN-3": RowSpec(
        token_bindings=_player_leaves("P2"),
        terminal_checks=(
            _before(
                _player_loses("P2"),
                _event("BEGIN_TURN", ("turn", 2), ("player_player", "P3")),
            ),
            _exactly(_event("BEGIN_TURN", ("player_player", "P2")), 0),
            TerminalCheck("no_frame", principal="P2", value="priority"),
        ),
    ),
    # WS05-CMD-PARTNER-DMG: the same per-commander rule for partners (12 from
    # Rograkh, 9 from Kediss): with a priority frame asked after the arrival
    # (state-based actions checked, CR 117.5), P2 has not lost and the engine
    # still reads each partner's damage separately (CR 903.10a, 702.124).
    "WS05-CMD-PARTNER-DMG": RowSpec(
        terminal_checks=(
            _commander_damage("P1", "Rograkh, Son of Rohgahh", "P2", 12),
            _commander_damage("P1", "Kediss, Emberclaw Familiar", "P2", 9),
            TerminalCheck("frame_count", principal="P1", value=("priority", 1), label=""),
            _event("LOST", count=0),
            TerminalCheck("player_in_game", principal="P2"),
        ),
    ),
    # WS05-CMD-DMG-SPLIT: P2 has 11 combat damage from Rograkh and 10 from
    # Kediss (21 in aggregate). The engine checks state-based actions before
    # every priority (CR 117.5): with a priority frame asked after the arrival,
    # P2 has not lost, and the engine's own readback still holds the damage
    # per commander (CR 903.10a counts each commander separately).
    "WS05-CMD-DMG-SPLIT": RowSpec(
        token_bindings=(
            (
                "commander_damage_checked_per_commander",
                (
                    _commander_damage("P1", "Rograkh, Son of Rohgahh", "P2", 11),
                    _commander_damage("P1", "Kediss, Emberclaw Familiar", "P2", 10),
                    TerminalCheck("frame_count", principal="P1", value=("priority", 1), label=""),
                    _event("LOST", count=0),
                    TerminalCheck("player_in_game", principal="P2"),
                ),
            ),
        ),
    ),
}


@dataclass
class Frame:
    decision_class: str
    principal: str
    offered_labels: list[str]
    selected_label: str | None = None
    selected_option_type: str | None = None
    scripted: bool = False
    # The record's semantic key the selected offer was bound to, or the number
    # submitted on a numeric frame the engine accepted.
    selected_key: str | None = None
    numeric: int | None = None
    # An explicit typed refusal of this frame (no option was selected at all).
    refused: bool = False
    refusal_kind: str | None = None
    # Engine-authored frame identity, kept verbatim so a verifier can bind an
    # observation to the exact decision the engine offered.
    decision_id: str | None = None
    prompt: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    # The native source object of the offer this frame submitted, when the
    # engine's own option metadata names one (used to bind a cost obligation to
    # the exact cast it belongs to).
    selected_source_object: str | None = None
    # Every engine-offered option id this frame submitted. A single-select
    # answer carries one; a multi-select answer carries the complete vector, so
    # the receipt shows exactly which targets the engine accepted.
    selected_option_ids: tuple[str, ...] = ()
    # On a block declaration frame: the record identities of the attackers the
    # engine offered this blocker (None for an attacker the record never
    # placed), so a verifier can read the engine's own legal-block partition.
    offered_attackers: tuple[str | None, ...] = ()
    # The last engine event sequence on the tape when the engine asked this
    # frame (None before any event), so a frame is ordered against the events.
    tape_sequence: int | None = None
    # The record identity (semantic object or commander id) of the source the
    # scripted priority action named, when the run placed it.
    selected_source_semantic: str | None = None
    # How many objects the engine's own stack held when it asked this frame
    # (the frame's pilot_state), or None when the frame shows no stack.
    stack_size: int | None = None
    # The engine's own pending extra turns (most recently created first), read
    # back when it asked this frame; only on a row that verifies an extra
    # turn's creation, and only on frames after which the tape had grown.
    pending_extra_turns: tuple[str, ...] | None = None
    # True when a readback was taken at this frame but carried no readable
    # queue: unlike a skipped readback, it is a failed observation.
    pending_read_failed: bool = False


@dataclass
class RowExecution:
    fixture_id: str
    verified: bool
    construction_verdict: str | None
    detail: str
    token_evidence: dict[str, Any] = field(default_factory=dict)
    missing_tokens: list[str] = field(default_factory=list)
    terminal_facts: dict[str, bool] = field(default_factory=dict)
    decision_trace: list[dict[str, Any]] = field(default_factory=list)
    tape: list[dict[str, Any]] = field(default_factory=list)
    # Explicit typed refusals this row performed, with their no-mutation proofs.
    refusals: list[dict[str, Any]] = field(default_factory=list)
    # A causal-stack entry's own facts: the engine-cast frames and the engine's
    # checkpoint-equivalence verdict. Absent for a placement row.
    causal_reconstruction: dict[str, Any] | None = None
    # Every scripted step was answered on an engine frame. Only a row that ran
    # its whole script can demonstrate that the engine's end state contradicts
    # the obligation; an unfinished script proves nothing either way.
    script_consumed: bool | None = None
    # The source of the non-exact construction verdict: the engine's own
    # declaration-step priority allowance when the engine's verdict was already
    # ALLOWED_VARIANCE, or the Lab's own declared causal life substitution when
    # it turned an otherwise-exact construction into the declared variance.
    # None for every exact row, and for a row whose engine ALLOWED_VARIANCE
    # carries no interpretable elimination plan.
    variance_source: str | None = None
    # The Lab's declared causal life substitution whenever the elimination plan
    # declares one, recorded even beside an engine variance so neither source
    # overwrites the other. None when no substitution is declared.
    declared_substitution_source: str | None = None

    def document(self) -> dict[str, Any]:
        document = self._base_document()
        if self.causal_reconstruction is not None:
            document["causal_reconstruction"] = self.causal_reconstruction
        if self.script_consumed is not None:
            document["script_consumed"] = self.script_consumed
        return document

    def _base_document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "verified": self.verified,
            "construction_verdict": self.construction_verdict,
            "variance_source": self.variance_source,
            "declared_substitution_source": self.declared_substitution_source,
            "detail": self.detail,
            "token_evidence": self.token_evidence,
            "missing_tokens": self.missing_tokens,
            "terminal_facts": self.terminal_facts,
            "decision_trace": self.decision_trace,
            "tape": self.tape,
            "refusals": self.refusals,
        }


_PROBE: Any = None


def probe_module() -> Any:
    """The midgame probe's pilot primitives (one implementation, not two)."""
    global _PROBE
    if _PROBE is None:
        spec = importlib.util.spec_from_file_location("midgame_probe_primitives", PROBE_SCRIPT)
        if spec is None or spec.loader is None:
            raise ml.MidgameLaneError(f"cannot load the midgame probe at {PROBE_SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PROBE = module
    return _PROBE


# --------------------------------------------------------------------------- #
# Token verification
# --------------------------------------------------------------------------- #


def _events(tape: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [event for event in tape if event.get("type") == event_type]


def _name_matches(event: dict[str, Any], key: str, name: str) -> bool:
    wanted = name.replace("_", " ").strip().lower()
    return str(event.get(key) or "").lower().startswith(wanted)


def verify_token(
    token: str,
    tape: list[dict[str, Any]],
    trace: list[Frame],
    commander_object_ids: set[str],
    commander_printed_mana_value: int | None = None,
    refusals: list[dict[str, Any]] | None = None,
    cost_obligation: tuple[str, str, str] | None = None,
) -> dict[str, Any] | None:
    """Positive evidence for one required-event token, or None.

    Returns the observed evidence (event sequences or decision frames). A token
    this function does not understand returns None: unverified, never assumed.
    """
    if match := re.fullmatch(r"creature_enters(?::(obj:.+))?|creature_entered", token):
        wanted = match.group(1) if match.group(1) else None
        hits = [
            e
            for e in _events(tape, "ZONE_CHANGE")
            if e.get("to") == "BATTLEFIELD"
            and e.get("from") in {"STACK", "HAND"}
            and (wanted is None or e.get("target_object") == wanted)
        ]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if match := re.fullmatch(r"trigger:(.+)|([A-Za-z]+)_trigger", token):
        name = match.group(1) or match.group(2)
        hits = [
            e for e in _events(tape, "TRIGGERED_ABILITY") if _name_matches(e, "source_name", name)
        ]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if match := re.fullmatch(r"(?:entering_creature_|noncombat_)?damage:(P\d+):(\d+)", token):
        principal, amount = match.group(1), int(match.group(2))
        noncombat = token.startswith("noncombat_")
        hits = [
            e
            for e in _events(tape, "DAMAGED_PLAYER")
            if e.get("target_player") == principal
            and e.get("amount") == amount
            and (not noncombat or e.get("combat") is False)
        ]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if match := re.fullmatch(r"spell_cast:(obj:.+)", token):
        hits = [e for e in _events(tape, "SPELL_CAST") if e.get("source_object") == match.group(1)]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if match := re.fullmatch(r"create_([A-Za-z][A-Za-z_]*)_token:(\d+)", token):
        # The engine's own CREATED_TOKEN events, by the token's name. The count
        # must be exact: a row that created a different number of tokens did not
        # satisfy the obligation.
        hits = [
            e
            for e in _events(tape, "CREATED_TOKEN")
            if _name_matches(e, "target_name", match.group(1))
        ]
        return (
            {"events": [e["sequence"] for e in hits]} if len(hits) == int(match.group(2)) else None
        )
    if match := re.fullmatch(r"attacker_declared:(obj:.+)->(P\d+)", token):
        hits = [
            e
            for e in _events(tape, "ATTACKER_DECLARED")
            if e.get("source_object") == match.group(1) and e.get("target_player") == match.group(2)
        ]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if match := re.fullmatch(r"blocker_declared:(obj:.+)->(obj:.+)", token):
        hits = [
            e
            for e in _events(tape, "BLOCKER_DECLARED")
            if e.get("source_object") == match.group(1) and e.get("target_object") == match.group(2)
        ]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if token in {"commander_cast", "commander_cast_from_command"}:
        # Only commanders are cards in the command zone, so a card moving from
        # the command zone onto the stack is a commander cast.
        hits = [
            e
            for e in _events(tape, "ZONE_CHANGE")
            if e.get("from") == "COMMAND" and e.get("to") == "STACK" and e.get("public_identity")
        ]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if token == "spell_resolved":
        hits = [
            e
            for e in _events(tape, "ZONE_CHANGE")
            if e.get("from") == "STACK" and e.get("to") in {"BATTLEFIELD", "GRAVEYARD"}
        ]
        return {"events": [e["sequence"] for e in hits]} if hits else None
    if match := re.fullmatch(r"choose_ability_frame:(P\d+)", token):
        # XMage asks which activated ability to activate on the priority
        # frame: the ability frame is the one the record's ability step
        # answered there, for that player, with an offer the engine made.
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "priority"
            and frame.principal == match.group(1)
            and frame.scripted
            and str(frame.selected_key or "").startswith(ABILITY_KEY_PREFIX)
            and frame.selected_label in frame.offered_labels
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"ability_selected:([a-z0-9_]+)", token):
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "priority"
            and frame.scripted
            and frame.selected_key == f"{ABILITY_KEY_PREFIX}{match.group(1)}"
            and frame.selected_label in frame.offered_labels
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"([a-z_]+?)_(?:decision_)?frame:(P\d+)", token):
        family, principal = match.group(1), match.group(2)
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == engine_decision_class(family)
            and frame.principal == principal
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"decision_frame:([a-z_]+)", token):
        # A frame token without a principal names the decision class only; the
        # engine's own offer set must still be non-empty, so a frame that
        # exposed nothing cannot satisfy it.
        family = match.group(1)
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == engine_decision_class(family) and frame.offered_labels
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"fail_closed:([A-Z_]+)", token):
        # The obligation is the explicit typed refusal, evidenced by a
        # well-formed refusal record bound to an engine-authored frame this run
        # refused. An absent, timeout-derived or malformed refusal never matches.
        wanted = match.group(1)
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.refused and frame.refusal_kind == wanted
        ]
        proofs = [
            str(item.get("frame_digest"))
            for item in refusals or ()
            if item.get("kind") == wanted and item.get("well_formed") is True
        ]
        return (
            {"decision_frames": frames, "refusal_frame_digests": proofs}
            if frames and proofs
            else None
        )
    if match := re.fullmatch(r"choice:([A-Z0-9_]+)", token):
        # The record's named choice is the key the scripted step submitted on
        # the engine's own choice frame, for an offer the engine made.
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "choice"
            and frame.scripted
            and frame.selected_key == match.group(1)
            and frame.selected_label in frame.offered_labels
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"mode_selected:([a-z_]+)", token):
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "mode"
            and frame.scripted
            and frame.selected_key == match.group(1)
            and frame.selected_label in frame.offered_labels
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"starting_player:(P\d+)", token):
        first = _first_turn(tape)
        return (
            {"events": [first["sequence"]]}
            if first is not None and first.get("player_player") == match.group(1)
            else None
        )
    if token == "first_turn_draw:true":
        first = _first_turn(tape)
        if first is None:
            return None
        draws = [
            e["sequence"]
            for e in _events(tape, "ZONE_CHANGE")
            if e.get("turn") == 1
            and e.get("step") == "DRAW"
            and e.get("from") == "LIBRARY"
            and e.get("to") == "HAND"
            and e.get("player_player") == first.get("player_player")
        ]
        return {"events": draws} if len(draws) == 1 else None
    if match := re.fullmatch(r"simultaneous_triggers:(P\d+):(\d+)", token):
        # The engine asks its controller to order triggered abilities only when
        # they are put on the stack together: an ordering frame offering exactly
        # n abilities, and n of that player's abilities put on the stack.
        principal, count = match.group(1), int(match.group(2))
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "trigger_order"
            and frame.principal == principal
            and len(frame.offered_labels) == count
        ]
        put = [
            e["sequence"]
            for e in _events(tape, "TRIGGERED_ABILITY")
            if e.get("player_player") == principal
        ]
        return {"decision_frames": frames, "events": put} if frames and len(put) == count else None
    if match := re.fullmatch(r"x_announced:(\d+)", token):
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "announce_x"
            and frame.scripted
            and frame.numeric == int(match.group(1))
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"target_selected:(P\d+)", token):
        label = probe_module().seat_label(match.group(1))
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "target"
            and frame.selected_label == label
            and label in frame.offered_labels
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"mana_paid:(\d+)", token):
        spent = _mana_charged(trace)
        return (
            {"decision_frames": spent}
            if spent is not None and len(spent) == int(match.group(1))
            else None
        )
    if match := re.fullmatch(r"commander_tax:\+(\d+)_generic", token):
        spent = _mana_charged(trace)
        if commander_printed_mana_value is None or spent is None:
            return None
        paid_tax = len(spent) - commander_printed_mana_value
        return (
            {"decision_frames": spent, "paid_minus_printed": paid_tax}
            if paid_tax == int(match.group(1))
            else None
        )
    if token == "legal_targets_exposed":
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "target" and frame.offered_labels
        ]
        return {"decision_frames": frames} if frames else None
    if match := re.fullmatch(r"amount_assignment:(\d+(?:\+\d+)*)", token):
        declared = [int(part) for part in match.group(1).split("+")]
        return _verify_amount_assignment(declared, trace)
    if match := re.fullmatch(r"commander_zone_event:(graveyard|exile|hand|library)", token):
        return _commander_zone_event(match.group(1), tape, trace, commander_object_ids)
    if match := re.fullmatch(r"commander_choice:(command|graveyard|exile|hand|library)", token):
        return _commander_choice(match.group(1), tape, trace, commander_object_ids)
    if match := re.fullmatch(r"cost_determined:base_plus_(\d+)_generic", token):
        return _verify_cost_determined(int(match.group(1)), trace, cost_obligation)
    if match := re.fullmatch(r"cost_determined:base_minus_(\d+)_generic", token):
        return _verify_cost_determined(-int(match.group(1)), trace, cost_obligation)
    return None


# The record's zone word and the engine's zone name for a commander leaving
# the battlefield.
COMMANDER_DESTINATIONS = {
    "graveyard": "GRAVEYARD",
    "exile": "EXILED",
    "hand": "HAND",
    "library": "LIBRARY",
}
# CR 903.9b: a commander that would be put into its owner's hand or library is
# a replacement, so the move to that zone never happens when the owner takes
# the command zone instead. The engine's own frame names the replaced zone.
REPLACED_DESTINATION_PROMPTS = {
    "hand": "instead of your hand",
    "library": "instead of your library",
}


def _commander_moves(
    tape: list[dict[str, Any]], commander_object_ids: set[str]
) -> list[dict[str, Any]]:
    return [
        e for e in _events(tape, "ZONE_CHANGE") if e.get("target_object") in commander_object_ids
    ]


def _commander_zone_frames(trace: list[Frame]) -> list[tuple[int, Frame]]:
    """The scripted yes/no frames this run answered about a commander's zone."""
    return [
        (index, frame)
        for index, frame in enumerate(trace)
        if frame.decision_class == BOOLEAN_DECISION_CLASS
        and frame.scripted
        and frame.selected_key in {"true", "false"}
        and frame.selected_label in frame.offered_labels
        and "command zone" in frame.prompt
    ]


def _commander_zone_event(
    zone: str,
    tape: list[dict[str, Any]],
    trace: list[Frame],
    commander_object_ids: set[str],
) -> dict[str, Any] | None:
    """A commander left the battlefield for ``zone`` (CR 903.9).

    Either the engine moved it there (graveyard and exile always; hand and
    library when the owner declined the command zone), or the engine asked its
    owner whether to replace the move to the hand or library (CR 903.9b) and
    the commander went from the battlefield straight to the command zone.
    """
    moves = _commander_moves(tape, commander_object_ids)
    direct = [
        e["sequence"]
        for e in moves
        if e.get("from") == "BATTLEFIELD" and e.get("to") == COMMANDER_DESTINATIONS[zone]
    ]
    if direct:
        return {"events": direct}
    replaced_prompt = REPLACED_DESTINATION_PROMPTS.get(zone)
    if replaced_prompt is None:
        return None
    frames = [
        index for index, frame in _commander_zone_frames(trace) if replaced_prompt in frame.prompt
    ]
    to_command = [
        e["sequence"] for e in moves if e.get("from") == "BATTLEFIELD" and e.get("to") == "COMMAND"
    ]
    return {"decision_frames": frames, "events": to_command} if frames and to_command else None


def _commander_choice(
    destination: str,
    tape: list[dict[str, Any]],
    trace: list[Frame],
    commander_object_ids: set[str],
) -> dict[str, Any] | None:
    """The owner's scripted command-zone answer and the engine's resulting zone.

    ``command`` is a "yes" on the engine's command-zone frame and a final move
    into the command zone; any other destination is a "no" and a final move
    into that zone with no later move to the command zone.
    """
    wanted = "true" if destination == "command" else "false"
    frames = [
        index for index, frame in _commander_zone_frames(trace) if frame.selected_key == wanted
    ]
    moves = _commander_moves(tape, commander_object_ids)
    if not frames or not moves:
        return None
    final = moves[-1]
    expected = "COMMAND" if destination == "command" else COMMANDER_DESTINATIONS[destination]
    if final.get("to") != expected:
        return None
    return {"decision_frames": frames, "events": [final["sequence"]]}


def new_incarnation_evidence(
    lineage: str,
    record: dict[str, Any],
    window: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """CR 400.7: the lineage's latest move in the window made a new object.

    An object that moves from one zone to another becomes a new object. The
    evidence is the engine's own public ZONE_CHANGE of a card of the record's
    lineage between two different zones, and it must be the lineage's last move
    in this obligation's window. Nothing about the card's earlier, hidden moves
    is read or reported.
    """
    objects = {
        str(o.get("semantic_id"))
        for o in record.get("semantic_objects") or ()
        if o.get("card_lineage_id") == lineage
    }
    moves = [e for e in _events(window, "ZONE_CHANGE") if e.get("target_object") in objects]
    if not objects or not moves:
        return None
    last = moves[-1]
    source, destination = last.get("from"), last.get("to")
    if (
        last.get("public_identity") is not True
        or not isinstance(source, str)
        or not isinstance(destination, str)
        or source == destination
    ):
        return None
    return {"events": [last["sequence"]], "from": source, "to": destination}


def _assignment_frames(trace: list[Frame]) -> list[Frame]:
    """The divided-damage assignment frames this run actually submitted.

    A frame counts only when the executor selected an engine-offered option on
    it, bound that option to a record semantic identity, submitted an explicit
    amount the engine accepted, and the frame carries the engine's own decision
    identity. A frame that was merely reached, or an unscripted one, is not
    assignment evidence.
    """
    return [
        frame
        for frame in trace
        if frame.decision_class == "target_amount"
        and frame.scripted
        and frame.selected_key is not None
        and frame.numeric is not None
        and frame.decision_id is not None
        and frame.selected_label in frame.offered_labels
    ]


def _verify_amount_assignment(declared: list[int], trace: list[Frame]) -> dict[str, Any] | None:
    """The engine-accepted divided-damage assignment, bound to its frames.

    The observed amounts must be exactly the record's ordered declared legs,
    each submitted on an engine-authored frame whose identity is recorded. The
    sum must also match the engine frame's own remaining total when the first
    frame exposes one: a record that assigns a different total than the engine
    asked to distribute fails closed instead of resolving for the wrong reason.
    """
    frames = _assignment_frames(trace)
    if [frame.numeric for frame in frames] != declared:
        return None
    total = sum(declared)
    first_remaining = frames[0].context.get("amount_remaining")
    if (
        isinstance(first_remaining, int)
        and not isinstance(first_remaining, bool)
        and total != first_remaining
    ):
        return None
    return {
        "decision_frames": [trace.index(frame) for frame in frames],
        "decision_ids": [frame.decision_id for frame in frames],
        "assignments": [
            {"target": frame.selected_key, "amount": frame.numeric} for frame in frames
        ],
        "total": total,
        "engine_amount_remaining": first_remaining if isinstance(first_remaining, int) else None,
    }


_MANA_SYMBOL_KEYS = {
    "W": "white",
    "U": "blue",
    "B": "black",
    "R": "red",
    "G": "green",
    "C": "colorless",
}


def _parse_mana(text: str) -> dict[str, int] | None:
    """The engine's own mana-string vocabulary as a symbol vector, or None.

    Only the plain symbols the engine prints for these obligations are read
    ({N}, {W}, {U}, {B}, {R}, {G}, {C}). Hybrid, phyrexian, X and any other
    symbol return None: the comparison refuses to answer rather than guess a
    cost structure the frame did not state.
    """
    if not isinstance(text, str) or not text:
        return None
    vector = {value: 0 for value in _MANA_SYMBOL_KEYS.values()}
    vector["generic"] = 0
    if re.sub(r"\{[^}]*\}", "", text).strip():
        return None
    for symbol in re.findall(r"\{([^}]*)\}", text):
        if symbol.isdigit():
            vector["generic"] += int(symbol)
        elif symbol in _MANA_SYMBOL_KEYS:
            vector[_MANA_SYMBOL_KEYS[symbol]] += 1
        else:
            return None
    return vector


def _mana_total(vector: dict[str, int]) -> int:
    return sum(vector.values())


def _verify_cost_determined(
    increase: int,
    trace: list[Frame],
    cost_obligation: tuple[str, str, str] | None,
) -> dict[str, Any] | None:
    """The exact cost the engine determined for the scripted cast, and charged.

    ``cost_obligation`` is the row's declaration: (native source object id, the
    record's base mana, the record's declared total). The evidence is the
    engine's own payment frame after that exact scripted cast: its
    ``unpaid_mana`` context must equal the declared total and equal the base
    plus exactly the named generic increase, and the run must actually have
    charged exactly that many mana (pool spends, with no floating tap). A row
    that merely reached a target frame, or whose payment was never completed,
    has no such evidence.
    """
    if cost_obligation is None:
        return None
    source_native, base_text, total_text = cost_obligation
    cast_indexes = [
        index
        for index, frame in enumerate(trace)
        if frame.decision_class == "priority"
        and frame.scripted
        and frame.selected_source_object == source_native
    ]
    if len(cast_indexes) != 1:
        return None
    payments = []
    for frame in trace[cast_indexes[0] + 1 :]:
        if frame.decision_class == "priority":
            break
        if frame.decision_class == "mana_payment":
            payments.append(frame)
    if not payments:
        return None
    determined = _parse_mana(str(payments[0].context.get("unpaid_mana") or ""))
    base = _parse_mana(base_text)
    total = _parse_mana(total_text)
    if determined is None or base is None or total is None:
        return None
    if determined != total:
        return None
    expected = dict(base)
    expected["generic"] += increase
    if expected["generic"] < 0 or determined != expected:
        return None
    charged = _mana_charged(payments)
    if charged is None or len(charged) != _mana_total(determined):
        return None
    decision_ids = [frame.decision_id for frame in payments]
    if any(not decision_id for decision_id in decision_ids):
        return None
    return {
        "payment_frames": [trace.index(frame) for frame in payments],
        "decision_ids": decision_ids,
        "unpaid_mana": payments[0].context.get("unpaid_mana"),
        "charged_mana": len(charged),
        "base_mana": base_text,
        "determined_mana": total_text,
    }


def _first_turn(tape: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The engine's BEGIN_TURN for turn 1, if the tape starts at the game start."""
    turns = _events(tape, "BEGIN_TURN")
    return turns[0] if turns and turns[0].get("turn") == 1 else None


def _mana_taps(trace: list[Frame]) -> list[int]:
    return [
        index
        for index, frame in enumerate(trace)
        if frame.decision_class == "mana_payment" and frame.selected_option_type == "mana_ability"
    ]


def _mana_spends(trace: list[Frame]) -> list[int]:
    return [
        index
        for index, frame in enumerate(trace)
        if frame.decision_class == "mana_payment" and frame.selected_option_type == "mana_pool"
    ]


def _mana_charged(trace: list[Frame]) -> list[int] | None:
    """The payment frames of the mana the engine actually charged, or None.

    A mana ability only adds mana to the pool; the engine charges the cost by
    asking for one pool spend per unit until the cost is paid. So the charged
    amount is the number of pool spends, never the number of sources tapped: a
    tapped source whose mana is not spent says nothing about the cost. Every
    tapped mana must also have been spent, otherwise mana floated and the tap
    count and the charge disagree; the measurement then refuses to answer.
    """
    spends = _mana_spends(trace)
    if len(_mana_taps(trace)) != len(spends):
        return None
    return spends


def check_terminal(
    check: TerminalCheck,
    observation: dict[str, Any],
    tape: list[dict[str, Any]],
    trace: list[Frame],
) -> bool:
    seats = {str(seat.get("player_id")): seat for seat in observation.get("seats") or ()}
    seat = seats.get(check.principal or "") or {}
    if check.kind == "life":
        return bool(seat.get("life") == check.value)
    if check.kind == "blocker_partition":
        # CR 802.4a: a defending player's creature may block only a creature
        # attacking that player. ``value`` is the record's requested combat split
        # (attackers of the principal, attackers of other players); the row's
        # requested-combat fact verifies it against the engine's own declaration
        # events. Every block frame the engine asked of the principal offered
        # only attackers of the principal, while another player was attacked.
        own, others = check.value
        frames = [
            frame
            for frame in trace
            if frame.decision_class == "declare_blocker" and frame.principal == check.principal
        ]
        return (
            bool(frames)
            and bool(others)
            and all(
                frame.offered_attackers
                and all(attacker in own for attacker in frame.offered_attackers)
                for frame in frames
            )
        )
    if check.kind == "event_order":
        field_name, expected = check.value
        hits = matching_events(
            TerminalCheck("events", event_type=check.event_type, where=check.where), tape
        )
        return [e.get(field_name) for e in hits] == list(expected)
    if check.kind == "frame_order":
        decision_class, principals = check.value
        order = [frame.principal for frame in trace if frame.decision_class == decision_class]
        return order[: len(principals)] == list(principals)
    if check.kind == "player_in_game":
        return bool(seat) and seat.get("lost") is False and seat.get("left") is False
    if check.kind == "player_left":
        return seat.get("left") is True and seat.get("lost") is True
    if check.kind == "cast_cost":
        # The engine's own determined cost for the one scripted cast of the
        # named source: the first payment frame after that cast.
        casts = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == "priority"
            and frame.scripted
            and frame.selected_source_semantic == check.card_identity
        ]
        if len(casts) != 1:
            return False
        for frame in trace[casts[0] + 1 :]:
            if frame.decision_class == "priority":
                return False
            if frame.decision_class == "mana_payment":
                return _parse_mana(str(frame.context.get("unpaid_mana") or "")) == _parse_mana(
                    str(check.value)
                )
        return False
    if check.kind == "pending_extra_turns":
        pending = _pending_extra_turns(observation)
        return pending is not None and list(pending) == list(check.value)
    if check.kind == "extra_turn_created":
        return bool(_extra_turn_frames(check, trace, tape))
    if check.kind == "pending_extra_turns_between":
        return bool(_pending_between_frames(check, trace, tape))
    if check.kind == "commander_damage":
        damaged, amount = check.value
        entries = [
            entry
            for entry in seat.get("commanders") or ()
            if entry.get("card_identity") == check.card_identity
        ]
        return (
            len(entries) == 1 and (entries[0].get("combat_damage_to") or {}).get(damaged) == amount
        )
    if check.kind == "trigger_count":
        hits = [
            e
            for e in _events(tape, "TRIGGERED_ABILITY")
            if _name_matches(e, "source_name", str(check.source_name))
        ]
        return bool(len(hits) == check.value)
    if check.kind == "commander_prior_casts":
        commanders = seat.get("commanders") or []
        return len(commanders) == 1 and commanders[0].get("prior_casts") == check.value
    if check.kind == "game_start_command_zone":
        # The engine's readback lists every genuine commander identity of the
        # seat with its current zone (never only the command-zone ones). The
        # obligation is that this identity is exactly one of the seat's
        # command-zone rows: an identity on the battlefield, in another seat, or
        # duplicated into two byte-identical rows is not the game-start fact.
        entries = [
            entry
            for entry in seat.get("commanders") or ()
            if entry.get("card_identity") == check.card_identity
            and str(entry.get("zone") or "").upper() == "COMMAND"
        ]
        return len(entries) == 1
    if check.kind == "on_battlefield":
        return any(
            card.get("card_identity") == check.card_identity
            for card in seat.get("battlefield") or ()
        )
    if check.kind == "tapped":
        return any(
            card.get("card_identity") == check.card_identity and card.get("tapped") is check.value
            for card in seat.get("battlefield") or ()
        )
    if check.kind == "no_mana_payment":
        return not any(frame.decision_class == "mana_payment" for frame in trace)
    if check.kind == "draws":
        # The engine reports a draw as its hidden LIBRARY -> HAND zone change for
        # the drawing player; the tape names the player but never the card.
        draws = [
            e
            for e in _events(tape, "ZONE_CHANGE")
            if e.get("from") == "LIBRARY"
            and e.get("to") == "HAND"
            and e.get("player_player") == check.principal
        ]
        return bool(len(draws) == check.value)
    if check.kind == "tokens_created":
        tokens = [
            e
            for e in _events(tape, "CREATED_TOKEN")
            if _name_matches(e, "target_name", str(check.card_identity))
        ]
        return bool(len(tokens) == check.value)
    if check.kind == "no_permanent_damage":
        return not _events(tape, "DAMAGED_PERMANENT")
    if check.kind == "stack_empty_after":
        # The engine's own stack, as shown on the first priority frame it asked
        # after the event: an object it removed without an event (CR 800.4a,
        # a leaving player's spells) is gone from it. The trace holds the frames
        # the obligation loop recorded; a causal route that ends at the event
        # (the elimination stops at the first life drop) leaves the engine
        # parked on exactly that first frame.
        anchors = matching_events(
            TerminalCheck("events", event_type=check.event_type, where=check.where), tape
        )
        if not anchors:
            return False
        anchor = int(anchors[0]["sequence"])
        after = [
            frame
            for frame in trace
            if frame.decision_class == "priority"
            and frame.tape_sequence is not None
            and frame.tape_sequence >= anchor
        ]
        return bool(after) and after[0].stack_size == 0
    if check.kind == "stack_order":
        # XMage reports TRIGGERED_ABILITY as each ability is put on the stack, so
        # the tape order is the stack order, bottom first.
        put = [
            str(e.get("source_name"))
            for e in _events(tape, "TRIGGERED_ABILITY")
            if e.get("player_player") == check.principal
        ]
        return put == list(check.value)
    if check.kind == "mana_charged":
        charged = _mana_charged(trace)
        return charged is not None and len(charged) == check.value
    if check.kind == "assignment_total":
        frames = _assignment_frames(trace)
        if not frames:
            return False
        total = sum(int(frame.numeric) for frame in frames if frame.numeric is not None)
        if total != check.value:
            return False
        remaining = frames[0].context.get("amount_remaining")
        if isinstance(remaining, int) and not isinstance(remaining, bool):
            return total == remaining
        return True
    if check.kind == "assignment_minimum":
        frames = _assignment_frames(trace)
        return bool(frames) and all(
            frame.numeric is not None and frame.numeric >= check.value for frame in frames
        )
    if check.kind == "events":
        hits = matching_events(check, tape)
        return bool(hits) if check.value is None else len(hits) == check.value
    if check.kind == "events_follow":
        return bool(_following_events(check, tape))
    if check.kind == "events_precede":
        later_type, later_where = check.value
        earlier = matching_events(check, tape)
        later = matching_events(
            TerminalCheck("events", event_type=later_type, where=tuple(later_where)), tape
        )
        return (
            bool(earlier)
            and bool(later)
            and (max(int(e["sequence"]) for e in earlier) < min(int(e["sequence"]) for e in later))
        )
    if check.kind == "in_graveyard":
        return check.card_identity in (seat.get("graveyard") or ())
    if check.kind == "selected_frame":
        return bool(_selected_frames(check, trace))
    if check.kind == "scripted_frame":
        return bool(_scripted_frames(check, trace))
    if check.kind == "scripted_key":
        return bool(_scripted_keys(check, trace))
    if check.kind == "no_frame":
        return not any(
            frame.decision_class == check.value
            and (check.principal is None or frame.principal == check.principal)
            and (check.label is None or str(check.label).lower() in frame.prompt.lower())
            for frame in trace
        )
    if check.kind == "frame_count":
        decision_class, count = check.value
        asked = [
            frame
            for frame in trace
            if frame.decision_class == decision_class
            and (check.principal is None or frame.principal == check.principal)
            and str(check.label or "").lower() in frame.prompt.lower()
        ]
        return bool(len(asked) == count)
    if check.kind == "pool_spend":
        # The executor spends the pool only from the record's declared sources;
        # the engine's own spend offer names the color it spends.
        return any(
            frame.decision_class == "mana_payment"
            and frame.selected_option_type == "mana_pool"
            and f"spend {str(check.value).lower()} mana" in str(frame.selected_label or "").lower()
            for frame in trace
        )
    if check.kind == "battlefield_exact":
        identities = sorted(
            str(card.get("card_identity")) for card in seat.get("battlefield") or ()
        )
        return bool(seat) and identities == sorted(check.value)
    if check.kind == "frame_offers":
        decision_class, count = check.value
        return any(
            frame.decision_class == decision_class
            and frame.scripted
            and str(check.label) in frame.prompt
            and len(frame.offered_labels) == count
            for frame in trace
        )
    if check.kind == "selected_sequence":
        decision_class, keys = check.value
        selected = [
            frame.selected_key
            for frame in trace
            if frame.decision_class == decision_class
            and frame.scripted
            and str(check.label) in frame.prompt
        ]
        return bool(selected) and selected == list(keys)
    if check.kind == "graveyard_mana_value":
        values = seat.get("graveyard_mana_values") or {}
        value = values.get(check.card_identity)
        return (
            check.card_identity in (seat.get("graveyard") or ())
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value == check.value
        )
    if check.kind == "hand_count_min":
        count = seat.get("hand_count")
        return isinstance(count, int) and count >= check.value
    if check.kind == "hand_count":
        count = seat.get("hand_count")
        return isinstance(count, int) and not isinstance(count, bool) and count == check.value
    cards = [
        card
        for card in seat.get("battlefield") or ()
        if card.get("card_identity") == check.card_identity
    ]
    if check.kind == "not_on_battlefield":
        return bool(seat) and not cards
    if check.kind == "untapped_count":
        return bool(seat) and sum(1 for card in cards if card.get("tapped") is False) == check.value
    # The permanent-state checks below hold for every permanent of the named
    # identity on the principal's battlefield, and need at least one.
    if check.kind == "power_toughness":
        power, toughness = check.value
        return bool(cards) and all(
            card.get("power") == power and card.get("toughness") == toughness for card in cards
        )
    if check.kind == "counters":
        return bool(cards) and all(
            (card.get("counters") or {}) == dict(check.value) for card in cards
        )
    if check.kind == "keyword":
        return bool(cards) and all(check.value in (card.get("keywords") or ()) for card in cards)
    if check.kind == "keyword_absent":
        # The engine reports a permanent's evergreen keywords only when present,
        # so absence is read from the same readback that reports presence.
        return bool(cards) and all(
            check.value not in (card.get("keywords") or ()) for card in cards
        )
    if check.kind == "token_count":
        # Every permanent of the identity counts, and each must be an engine
        # token: a card of the same name can never stand in for one.
        return (
            bool(seat)
            and len(cards) == check.value
            and all(card.get("token") is True for card in cards)
        )
    if check.kind == "triggered_ability":
        # The engine's own triggered-ability and effect classes, never the
        # rules text: the text is reported for reading only.
        trigger, effect = check.value
        return bool(cards) and all(
            any(
                ability.get("trigger") == trigger and effect in (ability.get("effects") or ())
                for ability in card.get("triggered_abilities") or ()
            )
            for card in cards
        )
    if check.kind == "colors":
        return bool(cards) and all(
            sorted(card.get("colors") or ()) == sorted(check.value) for card in cards
        )
    return False


def _following_events(check: TerminalCheck, tape: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The events of ``check``'s pattern after the first event of its anchor."""
    earlier_type, earlier_where = check.value
    anchors = matching_events(
        TerminalCheck("events", event_type=earlier_type, where=tuple(earlier_where)), tape
    )
    if not anchors:
        return []
    first = min(int(event["sequence"]) for event in anchors)
    return [event for event in matching_events(check, tape) if int(event["sequence"]) > first]


def matching_events(check: TerminalCheck, tape: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The engine events an ``events`` check's pattern matches, in tape order."""
    hits = []
    for event in _events(tape, str(check.event_type)):
        matched = True
        for key, value in check.where:
            if key.endswith("~"):
                matched = _name_matches(event, key[:-1], str(value))
            elif value == UNNAMED_OBJECT and key.endswith("_object"):
                # An object is in that role, and the tape names neither it nor
                # a player there: an object the record never requested (a copy).
                role = key[: -len("_object")]
                matched = (
                    event.get(key) is None
                    and event.get(f"{role}_player") is None
                    and event.get(f"{role}_present") is True
                )
            elif value is None and key.endswith("_object"):
                # "No such object" means no source/target at all: neither a
                # player in that role nor any object, named or not (the engine
                # reports `<role>_present` for an object the tape withholds or
                # cannot map).
                role = key[: -len("_object")]
                matched = (
                    event.get(key) is None
                    and event.get(f"{role}_player") is None
                    and event.get(f"{role}_present") is not True
                )
            else:
                matched = event.get(key) == value
            if not matched:
                break
        if matched:
            hits.append(event)
    return hits


def _selected_frames(check: TerminalCheck, trace: list[Frame]) -> list[int]:
    wanted = str(check.label or "").lower()
    return [
        index
        for index, frame in enumerate(trace)
        if frame.decision_class == check.value
        and frame.scripted
        and frame.selected_label is not None
        and frame.selected_label in frame.offered_labels
        and wanted
        and wanted in frame.selected_label.lower()
    ]


def _scripted_frames(check: TerminalCheck, trace: list[Frame]) -> list[int]:
    wanted = str(check.label or "").lower()
    return [
        index
        for index, frame in enumerate(trace)
        if frame.decision_class == check.value
        and frame.principal == check.principal
        and frame.scripted
        and wanted
        and wanted in frame.prompt.lower()
    ]


def _scripted_keys(check: TerminalCheck, trace: list[Frame]) -> list[int]:
    decision_class, key = check.value
    return [
        index
        for index, frame in enumerate(trace)
        if frame.decision_class == decision_class
        and frame.principal == check.principal
        and frame.scripted
        and frame.selected_key == key
    ]


LIBRARY_SHUFFLE_CHANNEL = re.compile(r"library_shuffle:(P\d+)")


def declared_shuffle_channels(
    record: dict[str, Any], tape: list[dict[str, Any]]
) -> dict[str, bool]:
    """Each declared ``library_shuffle:Pn`` channel and whether the run used it.

    A Rules-RNG library channel the record declares must show on the engine's
    own tape after the arrival: a LIBRARY_SHUFFLED event of that player.
    Otherwise the declared random transition never happened in this run and
    the row stays unverified. Other channel kinds (a coin flip) are bound by
    the row's own tokens.
    """
    channels = (record.get("rules_randomness") or {}).get("channels") or ()
    used: dict[str, bool] = {}
    for channel in channels:
        match = LIBRARY_SHUFFLE_CHANNEL.fullmatch(str(channel))
        if match is None:
            continue
        used[str(channel)] = any(
            event.get("type") == "LIBRARY_SHUFFLED" and event.get("player_player") == match.group(1)
            for event in tape
        )
    return used


def _window_name(pattern: TerminalCheck | None) -> str:
    if pattern is None:
        return "frame"
    constraints = ", ".join(f"{key}={value}" for key, value in pattern.where)
    return f"{pattern.event_type} event with {constraints}"


def _first_sequence(pattern: TerminalCheck | None, tape: list[dict[str, Any]]) -> int | None:
    """The tape sequence of the first event matching ``pattern``, or None."""
    if pattern is None:
        return None
    hits = matching_events(pattern, tape)
    return int(hits[0]["sequence"]) if hits else None


def _extra_turn_frames(
    check: TerminalCheck, trace: list[Frame], tape: list[dict[str, Any]]
) -> list[int]:
    """The frames whose readback shows the extra turn ``check`` names created.

    An extra turn is created by a resolving effect, not announced by any engine
    event, so the engine's own pending queue, read at parked frames, observes
    it. The creation is ordered against the creating spell: ``check.after`` is
    that spell's resolution, and every frame the engine asked before it must
    read back no pending extra turn for ``check.principal`` (the run's first
    frame included); the frames returned are those asked after it whose
    readback is exactly ``check.value``.
    """
    if not trace or trace[0].pending_extra_turns is None:
        return []
    if check.principal in trace[0].pending_extra_turns:
        return []
    opened = _first_sequence(check.after, tape)
    if check.after is not None and opened is None:
        return []
    found = []
    for index, frame in enumerate(trace):
        pending = frame.pending_extra_turns
        if opened is None:
            asked_after = index > 0
        else:
            asked_after = frame.tape_sequence is not None and frame.tape_sequence >= opened
        if index == 0:
            continue
        if not asked_after:
            # A frame asked before the resolution that read the entry back is a
            # creation the spell did not cause; a skipped readback says nothing,
            # but a readback that failed leaves that span unverified.
            if frame.pending_read_failed:
                return []
            if pending is not None and check.principal in pending:
                return []
            continue
        if pending is not None and list(pending) == list(check.value):
            found.append(index)
    return found


def _pending_extra_turns(readback: Any) -> tuple[str, ...] | None:
    """The engine's pending extra-turn queue as read back, or None when unread.

    The provider reports the queue on every readback, empty when it is empty. A
    readback without the field, or with anything but a list of seat names, says
    nothing about the queue, so it stays None and no check can be credited from
    it: an absent field is never read as a drained queue.
    """
    if not isinstance(readback, dict):
        return None
    pending = readback.get("pending_extra_turns")
    if not isinstance(pending, list) or not all(isinstance(seat, str) for seat in pending):
        return None
    return tuple(pending)


def _read_pending_extra_turns(frame: Frame, client: Any) -> None:
    """Read the parked engine's pending extra-turn queue into ``frame``."""
    readback = client.complete_arrival().get("observation") or {}
    frame.pending_extra_turns = _pending_extra_turns(readback)
    frame.pending_read_failed = frame.pending_extra_turns is None


def _pending_between_frames(
    check: TerminalCheck, trace: list[Frame], tape: list[dict[str, Any]]
) -> list[int]:
    """Frames asked inside the check's event window reading its pending queue."""
    opened = _first_sequence(check.after, tape)
    if opened is None:
        return []
    closed = _first_sequence(check.before, tape) if check.before is not None else None
    if check.before is not None and closed is None:
        return []
    return [
        index
        for index, frame in enumerate(trace)
        if frame.tape_sequence is not None
        and frame.tape_sequence >= opened
        and (closed is None or frame.tape_sequence < closed)
        and frame.pending_extra_turns is not None
        and list(frame.pending_extra_turns) == list(check.value)
    ]


def _reads_extra_turns(check: Any) -> bool:
    if isinstance(check, tuple):
        return any(_reads_extra_turns(part) for part in check)
    return getattr(check, "kind", None) in {"extra_turn_created", "pending_extra_turns_between"}


def bound_token_evidence(
    check: TerminalCheck | tuple[TerminalCheck, ...],
    observation: dict[str, Any],
    tape: list[dict[str, Any]],
    trace: list[Frame],
) -> dict[str, Any] | None:
    """Positive evidence for a bound record token, or None.

    The evidence names what the binding observed: the matching engine events,
    the matching decision frames, or the engine-observed state the check read.
    A token bound to several checks needs every one of them.
    """
    if isinstance(check, tuple):
        parts = [bound_token_evidence(part, observation, tape, trace) for part in check]
        if any(part is None for part in parts):
            return None
        return {"binding": [part["binding"] for part in parts if part], "parts": parts}
    if not check_terminal(check, observation, tape, trace):
        return None
    evidence: dict[str, Any] = {"binding": check.describe()}
    if check.kind == "events":
        evidence["events"] = [event["sequence"] for event in matching_events(check, tape)]
    elif check.kind == "events_follow":
        evidence["events"] = [event["sequence"] for event in _following_events(check, tape)]
    elif check.kind == "selected_frame":
        evidence["decision_frames"] = _selected_frames(check, trace)
    elif check.kind == "scripted_frame":
        evidence["decision_frames"] = _scripted_frames(check, trace)
    elif check.kind == "scripted_key":
        evidence["decision_frames"] = _scripted_keys(check, trace)
    elif check.kind == "extra_turn_created":
        evidence["decision_frames"] = _extra_turn_frames(check, trace, tape)
    elif check.kind == "pending_extra_turns_between":
        evidence["decision_frames"] = _pending_between_frames(check, trace, tape)
    else:
        evidence["observation"] = "engine terminal observation"
    return evidence


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #


def _labels(legal: dict[str, Any]) -> list[str]:
    return [str((a.get("metadata") or {}).get("label") or "") for a in legal.get("actions") or ()]


def _label_of(action: dict[str, Any]) -> str:
    return str((action.get("metadata") or {}).get("label") or "")


def _scripted_priority_action(
    legal: dict[str, Any], step: dict[str, Any], placed: dict[str, str], commanders: dict[str, str]
) -> dict[str, Any]:
    value = (step.get("selection") or {}).get("semantic_value") or {}
    action = str(value.get("action"))
    if action in ("activate", "activate_mana"):
        return _scripted_activation(legal, value, placed)
    if action in ("cast", "cast_split_half", "cast_fused"):
        native = placed.get(str(value.get("object")))
    elif action == "cast_commander":
        native = commanders.get(str(value.get("commander_id")))
    else:
        raise ml.MidgameLaneError(
            f"scripted priority action {action!r} is not executed by this lane"
        )
    if not native:
        raise ml.MidgameLaneError(f"the engine did not offer the scripted {action} of {value}")
    offers = _source_casts(legal, native)
    if not offers:
        raise ml.MidgameLaneError(f"the engine did not offer the scripted {action} of {value}")
    if action == "cast_split_half":
        # One half of a split card, by the half's own name (the engine's
        # offer for a half is sourced from the half, a part of the placed card).
        half = str(value.get("half") or "")
        named = [
            offer
            for offer in offers
            if (_engine_meta(offer).get("source_name") or "") == half and half
        ]
        if len(named) != 1:
            raise ml.MidgameLaneError(
                f"the half {half!r} matched {len(named)} engine casts of {value.get('object')}"
            )
        return named[0]
    if action == "cast_fused":
        fused = [offer for offer in offers if "cast fused" in _label_of(offer).lower()]
        if len(fused) != 1:
            raise ml.MidgameLaneError(
                f"the fused cast matched {len(fused)} engine casts of {value.get('object')}"
            )
        return fused[0]
    alternative = value.get("alternative_cost")
    if alternative:
        # The engine either offers the alternative cast as its own spell ability
        # (its label names it) or offers one cast and asks for the cost later.
        named = [offer for offer in offers if str(alternative).lower() in _label_of(offer).lower()]
        if len(named) == 1:
            return named[0]
        if not named and len(offers) == 1:
            return offers[0]
        raise ml.MidgameLaneError(
            f"the engine offered {len(offers)} casts of {value}, {len(named)} naming "
            f"the alternative cost {alternative!r}"
        )
    if len(offers) != 1:
        # Several ways to cast the same card (an overload, an adventure, a split
        # half): the record must name which, never the first offer.
        raise ml.MidgameLaneError(
            f"the engine offered {len(offers)} casts of {value} and the record names none"
        )
    return offers[0]


def _engine_meta(action: dict[str, Any]) -> dict[str, Any]:
    return dict((action.get("metadata") or {}).get("xmage_option_metadata") or {})


def _source_casts(legal: dict[str, Any], native_source_id: str) -> list[dict[str, Any]]:
    """Every engine-offered spell cast of one native card, its parts included.

    A part of a card (a split half, an adventure) is its own engine object; the
    engine's offer names the whole card it belongs to as its parent.
    """
    offers = []
    for action in legal.get("actions") or ():
        engine = _engine_meta(action)
        if engine.get("ability_type") == "spell" and native_source_id in (
            engine.get("source_object_id"),
            engine.get("source_parent_object_id"),
        ):
            offers.append(action)
    return offers


def _scripted_activation(
    legal: dict[str, Any], value: dict[str, Any], placed: dict[str, str]
) -> dict[str, Any]:
    """The engine's offer of the activated (or mana) ability the record names.

    The source is the record's semantic object; when it has several activated
    abilities, the record's ``ability`` names a fragment of the one's rules
    text. ``activate_mana`` additionally requires the offer to be a mana ability.
    """
    source = str(value.get("source") or "")
    native = placed.get(source)
    if native is None:
        raise ml.MidgameLaneError(f"the scripted activation source {source!r} was not placed")
    mana = value.get("action") == "activate_mana"
    offers: list[dict[str, Any]] = [
        action
        for action in legal.get("actions") or ()
        if _engine_meta(action).get("source_object_id") == native
        and _engine_meta(action).get("ability_type") not in (None, "spell", "play_land")
        and (not mana or bool(_engine_meta(action).get("mana_ability")))
    ]
    fragment = value.get("ability")
    if fragment:
        offers = [o for o in offers if str(fragment).lower() in _label_of(o).lower()]
    if len(offers) != 1:
        raise ml.MidgameLaneError(
            f"the scripted {value.get('action')} of {source} matched {len(offers)} engine offers"
        )
    return offers[0]


ABILITY_KEY_PREFIX = "ability:"


def _is_ability_choice(step: dict[str, Any]) -> bool:
    """A record step choosing one of a permanent's activated abilities by key."""
    selection = step.get("selection") or {}
    return (
        step.get("decision_family") == "choose_ability"
        and selection.get("selector_kind") == "semantic_ability_key"
    )


def _ability_choice_answer(
    legal: dict[str, Any], key: str, spec: RowSpec, placed: dict[str, str]
) -> dict[str, Any]:
    """The engine's activation offer a record's ability key names, or fail closed."""
    bound = dict(spec.ability_bindings).get(key)
    if bound is None:
        raise ml.MidgameLaneError(f"ability key {key!r} has no binding for this row")
    source, fragment = bound
    return _scripted_activation(
        legal, {"action": "activate", "source": source, "ability": fragment}, placed
    )


def _pending_cost_choices(step: dict[str, Any]) -> list[tuple[str, str]]:
    """The cost choices a scripted priority action still owes the engine.

    ``sacrifice_cost`` names the object to sacrifice; ``color`` the mana color
    an any-color mana ability produces. Each is answered on the engine's own
    frame for it, in the order the engine asks.
    """
    value = (step.get("selection") or {}).get("semantic_value") or {}
    owed: list[tuple[str, str]] = []
    if value.get("sacrifice_cost"):
        owed.append(("sacrifice", str(value["sacrifice_cost"])))
    if value.get("color"):
        owed.append(("color", str(value["color"])))
    return owed


_COLOR_NAMES = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}


def _pending_delve(step: dict[str, Any], placed: dict[str, str]) -> list[str]:
    """The native graveyard objects a scripted cast names to delve, in order."""
    value = (step.get("selection") or {}).get("semantic_value") or {}
    wanted = [str(item) for item in value.get("delve_objects") or ()]
    natives = [placed.get(item) for item in wanted]
    if any(native is None for native in natives):
        raise ml.MidgameLaneError(f"a delve object of {wanted} was not placed")
    return [str(native) for native in natives]


def _delve_offer(legal: dict[str, Any]) -> dict[str, Any]:
    """The engine's own delve special action on its payment frame, or fail closed."""
    matches = [
        action for action in legal.get("actions") or () if "delve" in _label_of(action).lower()
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(f"delve matched {len(matches)} engine payment offers")
    offer: dict[str, Any] = matches[0]
    return offer


def _delve_card_answer(legal: dict[str, Any], native: str) -> dict[str, Any]:
    """The engine's offer of the exact graveyard card the record delves next.

    The card is named by the engine's own object identity; a frame that does
    not offer it exactly once, or that is not the delve source's own
    graveyard choice, fails closed.
    """
    matches = []
    for action in legal.get("actions") or ():
        metadata = action.get("metadata") or {}
        engine = metadata.get("xmage_option_metadata") or {}
        source = metadata.get("source_object") or {}
        if (
            engine.get("object_id") == native
            and engine.get("zone") == "graveyard"
            and source.get("ability_type") == "special_mana_payment"
        ):
            matches.append(action)
    if len(matches) != 1:
        raise ml.MidgameLaneError(f"the delve card {native} matched {len(matches)} engine offers")
    card: dict[str, Any] = matches[0]
    return card


def _offers_cost(legal: dict[str, Any], kind: str, wanted: str, placed: dict[str, str]) -> bool:
    """Whether this engine frame offers the owed cost choice at all."""
    try:
        _cost_choice_answer(legal, kind, wanted, placed)
    except ml.MidgameLaneError:
        return False
    return True


def _cost_choice_answer(
    legal: dict[str, Any], kind: str, wanted: str, placed: dict[str, str]
) -> dict[str, Any]:
    """The engine's own offer for an owed cost choice, or fail closed."""
    actions = list(legal.get("actions") or ())
    if kind == "sacrifice":
        matches = _semantic_offers(wanted, actions, placed)
    else:
        name = _COLOR_NAMES.get(wanted.upper(), wanted).lower()
        matches = [a for a in actions if _label_of(a).strip().lower() in (name, wanted.lower())]
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the owed {kind} choice {wanted!r} matched {len(matches)} engine offers"
        )
    return matches[0]


def _pending_alternative_cost(step: dict[str, Any], selected: dict[str, Any]) -> str | None:
    """The alternative cost a scripted cast still owes the engine's cost choice."""
    value = (step.get("selection") or {}).get("semantic_value") or {}
    alternative = value.get("alternative_cost")
    if not alternative or str(alternative).lower() in _label_of(selected).lower():
        return None
    return str(alternative)


def _alternative_cost_answer(legal: dict[str, Any], alternative: str) -> dict[str, Any]:
    """The engine's own cost-choice offer naming the record's alternative cost."""
    matches: list[dict[str, Any]] = [
        action
        for action in legal.get("actions") or ()
        if _option_type(action) == "choice"
        and "alternative cost" in _label_of(action).lower()
        and alternative.lower() in _label_of(action).lower()
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the alternative cost {alternative!r} matched {len(matches)} engine cost offers"
        )
    return matches[0]


@dataclass(frozen=True)
class ScriptedAnswer:
    """The engine offer a script step names, plus what the step bound it to.

    ``option_ids`` carries every engine-offered option id the step submits.
    A single-target answer carries exactly the one id; a multi-select answer
    carries the complete set, so a submission can never silently drop or add an
    option the record did not request.
    """

    # None only for the empty selection an optional frame authorizes.
    action: dict[str, Any] | None
    key: str | None = None
    numeric: int | None = None
    option_ids: tuple[str, ...] = ()


def _option_type(action: dict[str, Any]) -> str:
    return str((action.get("metadata") or {}).get("option_type") or "")


def _normal_choice_key(raw: Any) -> str | None:
    """A choice key compared case- and spacing-insensitively, or None."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    return re.sub(r"\s+", "_", raw.strip()).upper()


def _choice_key(action: dict[str, Any]) -> str | None:
    """A choice offer's semantic key: its engine key, else its value text."""
    engine = (action.get("metadata") or {}).get("xmage_option_metadata") or {}
    return _normal_choice_key(engine.get("choice_key") or engine.get("choice"))


def _option_id(action: dict[str, Any]) -> str:
    return str((action.get("metadata") or {}).get("option_id") or "")


def _source_of(action: dict[str, Any]) -> str | None:
    """The native source object the engine's own option metadata names, if any."""
    engine = (action.get("metadata") or {}).get("xmage_option_metadata") or {}
    value = engine.get("source_object_id")
    return str(value) if value else None


def _single_option_id(action: dict[str, Any]) -> tuple[str, ...]:
    """The offered option id of a single-select action, or an empty tuple."""
    option_id = _option_id(action)
    return (option_id,) if option_id else ()


LIBRARY_POSITION_PREFIX = "library-position:"


def library_positions(record: dict[str, Any], placed: dict[str, str]) -> dict[str, str]:
    """The record's library objects, keyed for ``_semantic_offers``.

    Each library object the restoration did not report a native id for is
    named by its checkpoint position and card identity. Valid while the
    library is unchanged since the checkpoint; a moved card no longer matches
    its position and identity, and the selection fails closed.
    """
    keyed: dict[str, str] = {}
    for obj in record.get("semantic_objects") or ():
        semantic = str(obj.get("semantic_id") or "")
        position = obj.get("zone_position")
        if (
            obj.get("zone") != "library"
            or semantic in placed
            or not isinstance(position, int)
            or isinstance(position, bool)
        ):
            continue
        keyed[semantic] = f"{LIBRARY_POSITION_PREFIX}{position}:{obj.get('card_identity')}"
    return keyed


def _library_changed(tape: list[dict[str, Any]]) -> bool:
    """Whether any library has changed since the checkpoint, per the engine's tape."""
    return any(
        event.get("from") == "LIBRARY"
        or event.get("to") == "LIBRARY"
        or "SHUFFLE" in str(event.get("type") or "")
        for event in tape
    )


def _bind_library_objects(
    legal: dict[str, Any], unresolved: dict[str, str], tape: list[dict[str, Any]]
) -> dict[str, str]:
    """Bind library objects to the engine's own object ids at first sight.

    The first frame that offers library cards, while the engine's tape shows
    no library change since the checkpoint, still shows the checkpoint
    positions: each requested object offered exactly once at its position with
    its identity is bound to that offer's engine object id, which then names it
    for the rest of the row however the library moves. After any library
    change nothing is bound, and an unbound object's selection fails closed.
    """
    offers = [
        meta
        for action in legal.get("actions") or ()
        if (meta := ((action.get("metadata") or {}).get("xmage_option_metadata") or {})).get("zone")
        == "library"
    ]
    if not offers or _library_changed(tape):
        return {}
    bound: dict[str, str] = {}
    for semantic, key in unresolved.items():
        position, name = _library_position(key)
        hits = [
            meta
            for meta in offers
            if meta.get("zone_index") == position and meta.get("name") == name
        ]
        if len(hits) == 1 and hits[0].get("object_id"):
            bound[semantic] = str(hits[0]["object_id"])
    return bound


def _next_frame_continues(client: Any, decision_class: str, principal: str | None) -> bool:
    """Whether the engine's next pending decision is the same class for the same principal."""
    decision = client.pending_decision(attempts=5)
    if decision is None:
        return False
    if str(decision.get("decision_class")) != decision_class:
        return False
    legal = probe_module().legal_actions(client)
    return bool(probe_module().decision_principal(decision, legal) == principal)


def _library_position(key: str) -> tuple[int, str]:
    position, _, name = key[len(LIBRARY_POSITION_PREFIX) :].partition(":")
    return int(position), name


def _semantic_offers(
    key: str, actions: list[dict[str, Any]], placed: dict[str, str]
) -> list[dict[str, Any]]:
    """The engine offers a semantic identity maps to, in the engine's own domain.

    Two namespaces are authoritative and disjoint: a fixture semantic object id
    (bound to a native object id the engine placed) and a principal label
    (``P<n>``). An identity outside both namespaces maps to nothing; the caller
    fails closed rather than guessing. Nothing here computes legality, targets
    or ordering: only the engine's offered option metadata is read.
    """
    native = placed.get(key)
    if native is not None and native.startswith(LIBRARY_POSITION_PREFIX):
        # A library object: the lane reports no hidden object's native id, so it
        # is named by the record's checkpoint position and identity, both of
        # which the engine's own offer to the looking player carries.
        position, name = _library_position(native)
        return [
            action
            for action in actions
            if (meta := ((action.get("metadata") or {}).get("xmage_option_metadata") or {})).get(
                "zone"
            )
            == "library"
            and meta.get("zone_index") == position
            and meta.get("name") == name
        ]
    if native is not None:
        return [
            action
            for action in actions
            if probe_module().find_native_offer({"actions": [action]}, native)
        ]
    if re.fullmatch(r"P\d+", key):
        label = probe_module().seat_label(key)
        return [action for action in actions if _label_of(action) == label]
    return []


SCRY_DECISION_CLASS = "target"


def _is_bound_scry(step: dict[str, Any], spec: RowSpec) -> bool:
    selection = step.get("selection") or {}
    return (
        spec.scry_binding is not None
        and step.get("decision_family") == "choose_use"
        and selection.get("selector_kind") == "boolean"
    )


def answers_frame(step: dict[str, Any], decision_class: str, spec: RowSpec) -> bool:
    """Whether a scripted step answers a pending frame of ``decision_class``."""
    if _is_bound_scry(step, spec):
        return decision_class == SCRY_DECISION_CLASS
    return step_decision_class(step) == decision_class


def _scry_answer(
    legal: dict[str, Any], value: Any, placed: dict[str, str], looked_at: str
) -> ScriptedAnswer:
    """A scry 1 answered on XMage's 0..1 card frame (CR 701.22a).

    The frame must offer exactly the one looked-at card and allow selecting
    none or it; false (keep on top) is the empty selection, true (bottom) is
    that card. Any other frame shape fails closed.
    """
    if not isinstance(value, bool):
        raise ml.MidgameLaneError(f"the scry answer carries {value!r}")
    actions = list(legal.get("actions") or ())
    offers = _semantic_offers(looked_at, actions, placed)
    if len(actions) != 1 or offers != actions:
        raise ml.MidgameLaneError(
            f"the scry frame must offer exactly the looked-at card {looked_at!r}"
        )
    (looked_offer,) = offers
    if _engine_selection_bounds(legal) != (0, 1):
        raise ml.MidgameLaneError(
            f"the scry frame asks {_engine_selection_bounds(legal)}, not a 0..1 selection"
        )
    if not value:
        return ScriptedAnswer(None, key="false")
    option_id = _option_id(looked_offer)
    if not option_id:
        raise ml.MidgameLaneError("the looked-at card's offer carries no option id")
    return ScriptedAnswer(looked_offer, key="true", option_ids=(option_id,))


def _partition_first_pile(value: Any) -> Any:
    """The first pile of a record's partition, which the engine asks as a selection.

    Both piles must be disjoint, non-empty lists, so the second pile is what
    the selection leaves; anything else fails closed.
    """
    if not isinstance(value, dict) or set(value) != {"pile_a", "pile_b"}:
        raise ml.MidgameLaneError(f"partition carries {value!r}")
    first, second = value["pile_a"], value["pile_b"]
    if not isinstance(first, list) or not isinstance(second, list) or not first or not second:
        raise ml.MidgameLaneError(f"partition piles must be non-empty lists: {value!r}")
    if set(map(str, first)) & set(map(str, second)):
        raise ml.MidgameLaneError(f"partition piles overlap: {value!r}")
    return first


def _requested_objects(value: Any) -> list[str]:
    """The ordered semantic object identities a multi-select value names."""
    if not isinstance(value, list) or not value:
        raise ml.MidgameLaneError(f"semantic_objects carries no requested objects: {value!r}")
    keys: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ml.MidgameLaneError(f"semantic_objects carries a malformed identity: {item!r}")
        keys.append(item)
    if len(set(keys)) != len(keys):
        raise ml.MidgameLaneError(f"semantic_objects repeats a requested identity: {value!r}")
    return keys


def _assignment_entries(value: Any) -> list[tuple[str, int]]:
    """The ordered (semantic target, amount) legs a record declares.

    The declaration is the record's own assignment plan; every amount is an
    explicit positive integer. Malformed entries fail closed; nothing is
    defaulted or clamped here. Whether each amount is *authorized* is decided
    against the engine's pending frame, never against this declaration.
    """
    if not isinstance(value, dict) or not value:
        raise ml.MidgameLaneError(f"amount_assignment carries no assignment: {value!r}")
    entries: list[tuple[str, int]] = []
    seen: set[str] = set()
    for raw_key, raw_amount in value.items():
        key = str(raw_key)
        if key in seen:
            raise ml.MidgameLaneError(f"amount_assignment repeats a target: {key!r}")
        seen.add(key)
        if not isinstance(raw_amount, int) or isinstance(raw_amount, bool) or raw_amount < 1:
            raise ml.MidgameLaneError(
                f"amount_assignment for {key!r} is not a positive integer: {raw_amount!r}"
            )
        entries.append((key, raw_amount))
    return entries


def _engine_numeric_bounds(legal: dict[str, Any]) -> tuple[int, int] | None:
    """The pending engine frame's own numeric bounds, or None when it exposes none."""
    decision = legal.get("decision")
    context = (decision or {}).get("context") if isinstance(decision, dict) else None
    if not isinstance(context, dict):
        return None
    low, high = context.get("numeric_min"), context.get("numeric_max")
    if not isinstance(low, int) or isinstance(low, bool):
        return None
    if not isinstance(high, int) or isinstance(high, bool):
        return None
    return low, high


def _engine_selection_bounds(legal: dict[str, Any]) -> tuple[int, int] | None:
    """The pending engine frame's own selection-count bounds, or None when absent."""
    decision = legal.get("decision")
    if not isinstance(decision, dict):
        return None
    low = decision.get("minimum_selections")
    high = decision.get("maximum_selections")
    if not isinstance(low, int) or isinstance(low, bool):
        return None
    if not isinstance(high, int) or isinstance(high, bool):
        return None
    return low, high


def _spent_color(label: str | None) -> str:
    """The color a pool spend offer names ("Spend blue mana from pool")."""
    match = re.fullmatch(r"spend (\w+) mana from pool", str(label or "").strip().lower())
    if match is None:
        raise ml.MidgameLaneError(f"a pool spend names no color: {label!r}")
    return match.group(1)


def _scripted_answer(
    legal: dict[str, Any],
    step: dict[str, Any],
    placed: dict[str, str],
    spec: RowSpec,
    ordinal: int = 0,
) -> ScriptedAnswer:
    selection = step.get("selection") or {}
    kind = selection.get("selector_kind")
    value = selection.get("semantic_value")
    actions = list(legal.get("actions") or ())
    key: str | None = None
    numeric: int | None = None
    if _is_bound_scry(step, spec):
        return _scry_answer(legal, value, placed, str(spec.scry_binding))
    if kind in ("semantic_player", "semantic_object"):
        matches = _semantic_offers(str(value), actions, placed)
    elif kind == "semantic_objects" and value == []:
        # The record selects nothing on an optional frame ("up to N"). Only a
        # frame whose own minimum is zero authorizes the empty selection.
        bounds = _engine_selection_bounds(legal)
        if bounds is None or bounds[0] != 0:
            raise ml.MidgameLaneError(
                f"the record selects nothing, the engine frame requires {bounds}"
            )
        return ScriptedAnswer(None, key="none")
    elif kind in ("semantic_objects", "partition"):
        # A multi-select target frame: the record names the complete requested
        # set; every identity must map to exactly one engine-offered target and
        # the set's cardinality must be authorized by the pending frame itself.
        # A partition is answered as the selection of its first pile.
        requested = _requested_objects(
            _partition_first_pile(value) if kind == "partition" else value
        )
        selected = []
        for requested_key in requested:
            found = _semantic_offers(requested_key, actions, placed)
            if len(found) != 1:
                raise ml.MidgameLaneError(
                    f"the scripted {step.get('decision_family')} object {requested_key!r} matched "
                    f"{len(found)} engine offers"
                )
            selected.append(found[0])
        requested_option_ids = [_option_id(action) for action in selected]
        if any(not option_id for option_id in requested_option_ids):
            raise ml.MidgameLaneError(
                f"an engine offer for semantic_objects carries no option id: {value!r}"
            )
        if len(set(requested_option_ids)) != len(requested_option_ids):
            raise ml.MidgameLaneError(
                f"semantic_objects maps two requested identities to one engine offer: {value!r}"
            )
        selection_bounds = _engine_selection_bounds(legal)
        if selection_bounds is None:
            raise ml.MidgameLaneError("the engine frame exposes no selection-count bounds")
        bounds_low, bounds_high = selection_bounds
        if not bounds_low <= len(requested_option_ids) <= bounds_high:
            raise ml.MidgameLaneError(
                f"the record requests {len(requested_option_ids)} targets, the engine frame asks "
                f"{bounds_low}..{bounds_high}"
            )
        return ScriptedAnswer(selected[0], option_ids=tuple(requested_option_ids))
    elif kind == "card_identity_multiset":
        return _card_identity_answer(legal, step, placed)
    elif kind == "amount_assignment":
        # A divided-damage assignment frame: the engine asks for one target and
        # its share per call. The record's ordered legs name both; the share is
        # only submitted when the engine's own pending frame authorizes it.
        entries = _assignment_entries(value)
        if ordinal >= len(entries):
            raise ml.MidgameLaneError(
                f"the engine asked for another amount assignment after all {len(entries)} "
                "declared legs were assigned"
            )
        key, numeric = entries[ordinal]
        matches = _semantic_offers(key, actions, placed)
        if len(matches) != 1:
            raise ml.MidgameLaneError(
                f"the assignment target {key!r} matched {len(matches)} engine offers"
            )
        numeric_bounds = _engine_numeric_bounds(legal)
        if numeric_bounds is None:
            raise ml.MidgameLaneError("the engine frame exposes no numeric bounds")
        numeric_low, numeric_high = numeric_bounds
        if not numeric_low <= numeric <= numeric_high:
            raise ml.MidgameLaneError(
                f"the record assigns {numeric} to {key!r}, outside the engine frame's "
                f"{numeric_low}..{numeric_high}"
            )
        if not _option_id(matches[0]):
            raise ml.MidgameLaneError(f"the engine offer for {key!r} carries no option id")
        return ScriptedAnswer(
            matches[0], key=key, numeric=numeric, option_ids=(_option_id(matches[0]),)
        )
    elif kind == "semantic_mode_key":
        key = str(value)
        bound = dict(spec.mode_bindings).get(key)
        if bound is None:
            raise ml.MidgameLaneError(f"mode key {key!r} has no binding for this row")
        matches = [
            a
            for a in actions
            if _option_type(a) == "mode" and bound.lower() in _label_of(a).lower()
        ]
    elif kind == "semantic_choice_key":
        # A named choice (a color, a creature type, a keyed menu entry): the
        # engine's own choice offer whose key, or for a plain choice its value,
        # is the record's key. Case and spacing are the only normalization,
        # applied alike to both sides; a partial match never selects.
        normal = _normal_choice_key(value)
        if normal is None:
            raise ml.MidgameLaneError(f"semantic_choice_key selector carries {value!r}")
        key = normal
        matches = [a for a in actions if _option_type(a) == "choice" and _choice_key(a) == key]
    elif kind == "pile_label":
        # A pile frame offers its piles by label ("Pile 1", "Pile 2"); exactly
        # one engine offer must carry the record's label (HIDDEN_13's route).
        if not isinstance(value, str) or not value.strip():
            raise ml.MidgameLaneError(f"pile_label selector carries {value!r}")
        key = value.strip()
        matches = [a for a in actions if _label_of(a).strip() == key]
    elif kind == "boolean":
        # A yes/no frame: the engine's own boolean offer whose value is the
        # record's answer; the label is never read.
        if not isinstance(value, bool):
            raise ml.MidgameLaneError(f"boolean selector carries {value!r}")
        key = "true" if value else "false"
        matches = [
            a
            for a in actions
            if _option_type(a) == "boolean"
            and ((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("value") is value
        ]
    elif kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ml.MidgameLaneError(f"integer selector carries {value!r}")
        numeric = value
        matches = [a for a in actions if _option_type(a) == "numeric_choice"]
    elif kind == "order":
        # XMage asks "choose next triggered ability" once per ability still to be
        # put on the stack: the listed order is the order onto the stack, and
        # the ordinal-th frame of this step names the ordinal-th entry.
        if not isinstance(value, list) or ordinal >= len(value):
            raise ml.MidgameLaneError(f"order selector has no entry {ordinal} in {value!r}")
        key = str(value[ordinal])
        if not key.startswith("trigger:"):
            # An ordered set of objects (cards put on the bottom of a library in
            # a chosen order): the ordinal-th frame names the ordinal-th object
            # by its engine identity.
            matches = _semantic_offers(key, actions, placed)
            if len(matches) != 1:
                raise ml.MidgameLaneError(
                    f"the ordered object {key!r} matched {len(matches)} engine offers"
                )
            return ScriptedAnswer(matches[0], key=key)
        # ``trigger:<source>`` names a source's ability; ``trigger:<source>|<text>``
        # also names a fragment of the ability's own rules text, for a source
        # with several triggered abilities.
        wanted = re.fullmatch(r"trigger:([^|]+)(?:\|(.+))?", key)
        if wanted is None:
            raise ml.MidgameLaneError(f"order entry {key!r} names no triggered ability")
        name = wanted.group(1).replace("_", " ")
        text = wanted.group(2)
        matches = [
            a
            for a in actions
            if _option_type(a) == "triggered_ability"
            and ((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("source_name")
            == name
            and (text is None or text.lower() in _label_of(a).lower())
        ]
        if len(matches) > 1 and value.count(key) == len(matches) and _interchangeable(matches):
            # The record lists this ability once per instance and the engine
            # offers exactly that many instances of one ability of one source:
            # the instances are indistinguishable, so their relative order is
            # not a choice the record could make. Any other ambiguity fails
            # closed below.
            matches = matches[:1]
    else:
        raise ml.MidgameLaneError(f"selector {kind!r} is not executed by this lane")
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the scripted {step.get('decision_family')} {value!r} matched {len(matches)} engine offers"
        )
    return ScriptedAnswer(matches[0], key=key, numeric=numeric)


def _card_identity_answer(
    legal: dict[str, Any], step: dict[str, Any], placed: dict[str, str]
) -> ScriptedAnswer:
    """A selection named by the multiset of card identities it selects.

    The record names how many cards of each identity are chosen (a cleanup
    discard of template cards, CR 514.1), not which object: every offered card
    of that identity that is no named record object is the same semantic
    selection, so the least offered option id among those identical cards is
    submitted, as among indistinguishable trigger instances. That pick is
    content-independent and outcome-equivalent only because the copies share
    one identity; it is never positional. An offer of that identity that is a
    named record object, fewer such cards than requested, or a total the engine
    frame does not authorize fails closed.
    """
    value = (step.get("selection") or {}).get("semantic_value")
    if (
        not isinstance(value, dict)
        or not value
        or any(
            not isinstance(name, str)
            or not name
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 1
            for name, count in value.items()
        )
    ):
        raise ml.MidgameLaneError(f"card_identity_multiset carries {value!r}")
    named = set(placed.values())
    selected: list[dict[str, Any]] = []
    for name, count in sorted(value.items()):
        offers = [
            action
            for action in legal.get("actions") or ()
            if ((action.get("metadata") or {}).get("xmage_option_metadata") or {}).get("name")
            == name
        ]
        natives = [
            str(((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("object_id"))
            for a in offers
        ]
        if any(native in named for native in natives):
            raise ml.MidgameLaneError(
                f"the engine offers a named record object as {name!r}; the multiset selection "
                "is defined only over identical template cards"
            )
        if len(offers) < count:
            raise ml.MidgameLaneError(
                f"the record selects {count} {name!r}, the engine offers {len(offers)}"
            )
        # Deterministic least-option-id pick among the same-name copies. This is
        # content-independent and outcome-equivalent only because the chosen
        # copies share one card identity (same name, same rules text, same
        # identity for every game decision): no outcome distinction remains
        # between them, so the choice is not a player choice the record could
        # have made differently. Never positional: the engine's offer order is
        # not read as a preference.
        selected.extend(sorted(offers, key=_option_id)[:count])
    option_ids = tuple(_option_id(action) for action in selected)
    if any(not option_id for option_id in option_ids) or len(set(option_ids)) != len(option_ids):
        raise ml.MidgameLaneError(f"the engine offers for {value!r} carry no distinct option ids")
    bounds = _engine_selection_bounds(legal)
    if bounds is None or not bounds[0] <= len(option_ids) <= bounds[1]:
        raise ml.MidgameLaneError(
            f"the record selects {len(option_ids)} cards, the engine frame asks {bounds}"
        )
    key = ",".join(f"{name}:{count}" for name, count in sorted(value.items()))
    return ScriptedAnswer(selected[0], key=key, option_ids=option_ids)


def stack_object_step(step: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """A ``semantic_stack_object`` selection, named by the record's own stack.

    ``stack:N`` names the record's N-th requested stack entry (1-based, in the
    record's own ``stack_state`` order): the spell cast from that entry's
    source object. The step then selects that object exactly as a
    ``semantic_object`` selection does, so the engine's stack spell is matched
    by the card it was cast from and anything else fails closed.
    """
    selection = step.get("selection") or {}
    if selection.get("selector_kind") != "semantic_stack_object":
        return step
    value = str(selection.get("semantic_value") or "")
    match = re.fullmatch(r"stack:([1-9][0-9]*)", value)
    stack = list(record.get("stack_state") or ())
    if match is None or int(match.group(1)) > len(stack):
        raise ml.MidgameLaneError(f"the stack object {value!r} names no requested stack entry")
    source = stack[int(match.group(1)) - 1].get("source_semantic_id")
    if not source:
        raise ml.MidgameLaneError(f"the stack entry {value!r} names no source object")
    return {
        **step,
        "selection": {**selection, "selector_kind": "semantic_object", "semantic_value": source},
    }


def _interchangeable(actions: list[dict[str, Any]]) -> bool:
    """Whether offers are instances of one ability of one source, alike in label."""
    identities = {
        (
            ((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get(
                "ability_original_id"
            ),
            ((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("source_object_id"),
            _label_of(a),
        )
        for a in actions
    }
    return len(identities) == 1 and None not in next(iter(identities))


def _blocker_answer(
    legal: dict[str, Any],
    step: dict[str, Any],
    placed: dict[str, str],
    placed_by_native: dict[str, str],
) -> tuple[str | None, dict[str, Any] | None]:
    """The engine offer the record's blocker assignment names for this blocker.

    XMage asks once per creature able to block, offering exactly the attackers
    it may legally block (CR 509.1a, 802.4a). The assignment is complete for the
    defending player: a listed creature blocks its named attacker, every other
    creature blocks nothing, and the empty selection is answered only on a frame
    whose own minimum is zero. Returns the blocker's semantic id and the offer
    (None for no block).
    """
    assignment = (step.get("selection") or {}).get("semantic_value") or {}
    if not isinstance(assignment, dict):
        raise ml.MidgameLaneError(f"a block assignment is not a mapping: {assignment!r}")
    actions = list(legal.get("actions") or ())
    blockers = {
        str(((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("blocker_id"))
        for a in actions
    }
    if len(blockers) != 1:
        raise ml.MidgameLaneError(f"a block declaration names {len(blockers)} blockers")
    semantic = placed_by_native.get(blockers.pop())
    if semantic not in assignment:
        bounds = _engine_selection_bounds(legal)
        if bounds is None or bounds[0] != 0:
            raise ml.MidgameLaneError(
                f"{semantic or 'an unplaced creature'} blocks nothing in the record, "
                f"the engine frame requires {bounds}"
            )
        return semantic, None
    attacker = placed.get(str(assignment[semantic]))
    matches = [
        a
        for a in actions
        if (a.get("metadata") or {}).get("option_type") == "declare_blocker"
        and ((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("attacker_id")
        == attacker
        and attacker is not None
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the block of {assignment[semantic]} by {semantic} matched {len(matches)} engine offers"
        )
    return semantic, matches[0]


def _attacker_answer(
    legal: dict[str, Any], step: dict[str, Any], placed_by_native: dict[str, str]
) -> dict[str, Any]:
    """The engine offer the record's attacker assignment names for this creature.

    The assignment is complete for the declaring player: a listed creature
    attacks its named player, every other creature is held.
    """
    probe = probe_module()
    assignment = (step.get("selection") or {}).get("semantic_value") or {}
    actions = list(legal.get("actions") or ())
    creatures = {
        str(((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("object_id"))
        for a in actions
    }
    if len(creatures) != 1:
        raise ml.MidgameLaneError(f"an attack declaration names {len(creatures)} creatures")
    native = creatures.pop()
    semantic = placed_by_native.get(native)
    if semantic in assignment:
        wanted_type, suffix = (
            "declare_attacker",
            "attacks " + probe.seat_label(str(assignment[semantic])),
        )
    else:
        wanted_type, suffix = "hold_attacker", ""
    matches = [
        a
        for a in actions
        if (a.get("metadata") or {}).get("option_type") == wanted_type
        and _label_of(a).endswith(suffix)
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the assignment for {semantic or 'an unplaced creature'} matched {len(matches)} engine offers"
        )
    chosen: dict[str, Any] = matches[0]
    return chosen


@dataclass(frozen=True)
class RequestedCombat:
    """The record's own requested combat (its ``combat_state``).

    ``attackers`` maps each attacking creature to the player it attacks; every
    other creature of the attacking player is held. ``blocks`` maps each
    blocking creature to the attacker it blocks, or is None when the record
    leaves the blocks to its own decision script. A record that lists no
    blocks but names every attacker unblocked requests that nothing blocks.
    """

    attackers: tuple[tuple[str, str], ...]
    blocks: tuple[tuple[str, str], ...] | None

    def attack_step(self) -> dict[str, Any]:
        return {"selection": {"semantic_value": dict(self.attackers)}}

    def block_step(self) -> dict[str, Any]:
        return {"selection": {"semantic_value": dict(self.blocks or ())}}


def requested_combat(record: dict[str, Any]) -> RequestedCombat | None:
    """The record's requested combat, or None when it requests none."""
    combat = record.get("combat_state")
    if not combat:
        return None
    attackers = combat.get("attackers") or {}
    if not isinstance(attackers, dict):
        raise ml.MidgameLaneError(f"combat_state.attackers is not a mapping: {attackers!r}")
    if not attackers:
        # No attacker requested: the record's combat (if any) is its script's.
        return None
    blockers = combat.get("blockers")
    if blockers is None:
        unblocked = {str(o) for o in combat.get("unblocked") or ()} | {
            str(o) for o in combat.get("unblocked_attackers") or ()
        }
        blockers = {} if attackers and unblocked >= {str(a) for a in attackers} else None
    if blockers is not None and not isinstance(blockers, dict):
        raise ml.MidgameLaneError(f"combat_state.blockers is not a mapping: {blockers!r}")
    return RequestedCombat(
        attackers=tuple(sorted((str(k), str(v)) for k, v in attackers.items())),
        blocks=(
            None
            if blockers is None
            else tuple(sorted((str(k), str(v)) for k, v in blockers.items()))
        ),
    )


def _scripts_family(record: dict[str, Any], family: str) -> bool:
    return any(
        step.get("decision_family") == family for step in record.get("decision_script") or ()
    )


def _offered_attackers(
    legal: dict[str, Any], placed_by_native: dict[str, str]
) -> tuple[str | None, ...]:
    return tuple(
        placed_by_native.get(
            str(((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("attacker_id"))
        )
        for a in legal.get("actions") or ()
        if (a.get("metadata") or {}).get("option_type") == "declare_blocker"
    )


def answer_requested_combat(
    client: ml.MidgameLaneClient,
    record: dict[str, Any],
    decision: dict[str, Any],
    decision_class: str,
    combat: RequestedCombat,
    placed: dict[str, str],
    placed_by_native: dict[str, str],
    tag: str,
) -> Frame:
    """Answer one engine declaration frame from the record's requested combat.

    Only engine-offered options are submitted, matched by semantic identity;
    a frame the requested combat does not determine fails closed.
    """
    probe = probe_module()
    legal = probe.legal_actions(client)
    principal = probe.decision_principal(decision, legal)
    temporal = record.get("temporal_state") or {}
    observed_turn = (client.complete_arrival().get("observation") or {}).get("turn_number")
    if observed_turn != temporal.get("turn_number"):
        raise ml.MidgameLaneError(
            f"the requested combat belongs to turn {temporal.get('turn_number')}; the engine "
            f"asked {decision_class} in turn {observed_turn}"
        )
    if decision_class == "declare_attacker" and principal != temporal.get("active_player"):
        raise ml.MidgameLaneError(
            f"the requested combat is {temporal.get('active_player')}'s; the engine asked "
            f"{principal} to declare attackers"
        )
    if decision_class == "declare_blocker" and principal not in {
        defender for _, defender in combat.attackers
    }:
        raise ml.MidgameLaneError(
            f"the requested combat attacks no creature of {principal}; the engine asked it "
            "to declare blockers"
        )
    frame = Frame(
        decision_class,
        principal,
        _labels(legal),
        scripted=True,
        decision_id=str(decision.get("decision_id") or "") or None,
        prompt=str(decision.get("prompt") or ""),
        context=dict(decision.get("context") or {}),
        selected_key="requested_combat",
    )
    if decision_class == "declare_attacker":
        action = _attacker_answer(legal, combat.attack_step(), placed_by_native)
        frame.selected_label = _label_of(action)
        frame.selected_option_ids = _single_option_id(action)
        probe.submit_proposal(client, legal, action, tag)
        return frame
    if decision_class == "declare_blocker" and combat.blocks is not None:
        _, offer = _blocker_answer(legal, combat.block_step(), placed, placed_by_native)
        if offer is None:
            client.submit_options(decision, [])
        else:
            frame.selected_label = _label_of(offer)
            frame.selected_option_ids = _single_option_id(offer)
            probe.submit_proposal(client, legal, offer, tag)
        return frame
    raise ml.MidgameLaneError(
        f"the record's requested combat does not determine the engine's {decision_class} frame"
    )


def combat_matches_request(
    combat: RequestedCombat, tape: list[dict[str, Any]], *, compare_attacks: bool = True
) -> dict[str, Any]:
    """Whether the engine's own declaration events are exactly the requested combat."""
    attacks = sorted(
        (str(e.get("source_object")), str(e.get("target_player")))
        for e in _events(tape, "ATTACKER_DECLARED")
    )
    blocks = sorted(
        (str(e.get("source_object")), str(e.get("target_object")))
        for e in _events(tape, "BLOCKER_DECLARED")
    )
    # A run whose attacks are scripted still needs a combat to have happened.
    attacks_match = attacks == sorted(combat.attackers) if compare_attacks else bool(attacks)
    blocks_match = combat.blocks is None or blocks == sorted(combat.blocks)
    return {
        "holds": attacks_match and blocks_match,
        "declared_attacks": attacks,
        "declared_blocks": blocks,
    }


def _mana_offer(legal: dict[str, Any], sources: list[str]) -> dict[str, Any] | None:
    """The one advancing pool spend, else the next declared mana source.

    Mana already in the pool is spent before another source is tapped, so a
    source is tapped only while the charged cost still needs mana and nothing
    floats: tapping every declared source first would make the tap count
    describe the declaration, not the cost. Pool mana is spent only when exactly
    one advancing spend is offered, so no colour choice is ever made on the
    pilot's behalf. Declared sources are tried in the record's order; the engine
    never re-offers a tapped land.
    """
    actions = list(legal.get("actions") or ())
    spend = _single_pool_spend(actions)
    if spend is not None:
        return spend
    for native in sources:
        for action in actions:
            metadata = action.get("metadata") or {}
            engine = metadata.get("xmage_option_metadata") or {}
            if (
                metadata.get("option_type") == "mana_ability"
                and engine.get("source_object_id") == native
            ):
                found: dict[str, Any] = action
                return found
    return None


def _single_pool_spend(actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    spends = []
    for action in actions:
        metadata = action.get("metadata") or {}
        if metadata.get("option_type") != "mana_pool":
            continue
        engine = metadata.get("xmage_option_metadata") or {}
        if engine.get("advances_payment") is None or bool(engine.get("advances_payment")):
            spends.append(action)
    return spends[0] if len(spends) == 1 else None


def _timing_allows(step: dict[str, Any], decision: dict[str, Any]) -> bool:
    """Whether a scripted priority action may be taken at this priority.

    A step whose value declares ``timing: empty_stack`` starts its own event:
    it waits, passing priority, until everything already on the stack resolved.
    A step without a timing is taken at the actor's first priority, as before.
    """
    value = (step.get("selection") or {}).get("semantic_value") or {}
    timing = value.get("timing")
    if timing is None:
        return True
    if timing != "empty_stack":
        raise ml.MidgameLaneError(f"scripted timing {timing!r} is not executed by this lane")
    stack = (decision.get("pilot_state") or {}).get("stack")
    if not isinstance(stack, list):
        raise ml.MidgameLaneError("the engine's priority frame exposes no stack")
    return not stack


# The check kinds that read the engine's state readback; every other kind reads
# only the event tape or the decision trace.
OBSERVATION_KINDS = frozenset(
    {
        "life",
        "commander_prior_casts",
        "game_start_command_zone",
        "on_battlefield",
        "tapped",
        "hand_count_min",
        "hand_count",
        "in_graveyard",
        "not_on_battlefield",
        "untapped_count",
        "power_toughness",
        "counters",
        "keyword",
        "keyword_absent",
        "colors",
        "token_count",
        "triggered_ability",
        "battlefield_exact",
        "graveyard_mana_value",
        "commander_damage",
        "player_left",
        "player_in_game",
        "pending_extra_turns",
    }
)


def needs_observation(check: Any) -> bool:
    """Whether a check (or a bound tuple of checks) reads the engine readback."""
    if isinstance(check, tuple):
        return any(needs_observation(part) for part in check)
    if isinstance(check, VocabularyToken):
        return False
    return bool(getattr(check, "kind", None) in OBSERVATION_KINDS)


def _terminal_holds(
    client: ml.MidgameLaneClient, spec: RowSpec, tape: list[dict[str, Any]], trace: list[Frame]
) -> bool:
    if not spec.terminal_checks:
        return True
    observation = (
        client.complete_arrival().get("observation") or {}
        if any(needs_observation(check) for check in spec.terminal_checks)
        else {}
    )
    return all(check_terminal(check, observation, tape, trace) for check in spec.terminal_checks)


def execute_row(
    client: ml.MidgameLaneClient,
    record: dict[str, Any],
    created: dict[str, Any],
    spec: RowSpec,
    causal: dict[str, Any] | None = None,
) -> RowExecution:
    """Arrive, execute the scripted obligation and verify it. Never raises for a
    lane-level refusal: an unverifiable row is returned unverified with the reason.

    ``causal`` is a causal-stack entry (its declared fuel): the record's stack is
    never placed. After the pre-causal arrival the engine casts every stack
    frame, and the engine's own reconstruction verdict must match the requested
    stack exactly before the record's script runs. The tape baseline is the
    reconstructed checkpoint, so only the obligation's own events count.
    """
    probe = probe_module()
    fixture_id = str(record["fixture_id"])
    # The construction disposition this row's verdict carries: the engine's own
    # declaration-step priority allowance and/or the Lab's declared causal life
    # substitution, if any. Both are attached to every return below so a row
    # that stops unverified still states why its verdict is not exact.
    variance_source: str | None = None
    declared_substitution_source: str | None = None

    def row_execution(*args: Any, **kwargs: Any) -> RowExecution:
        kwargs.setdefault("variance_source", variance_source)
        kwargs.setdefault("declared_substitution_source", declared_substitution_source)
        return RowExecution(*args, **kwargs)

    if not (record.get("expected_events") or {}).get("required_events") and not (
        spec.terminal_checks
    ):
        # Nothing would be observed, so "verified" would hold for any behaviour.
        return row_execution(
            fixture_id, False, None, "the obligation names no required event and no terminal check"
        )
    placed = {str(k): str(v) for k, v in (created.get("placed_objects") or {}).items()}
    causal_plan = created.get("causal_plan") or created.get("elimination_plan") or {}
    if causal is not None:
        placed.update(
            {str(k): str(v) for k, v in (causal_plan.get("placed_objects") or {}).items()}
        )
    placed.update(library_positions(record, placed))
    commanders = {str(k): str(v) for k, v in (created.get("commander_objects") or {}).items()}
    semantic_commanders = {
        str(o["semantic_id"]) for o in record.get("semantic_objects") or () if o.get("commander_id")
    }
    trace: list[Frame] = []
    placed_by_native = {native: semantic for semantic, native in placed.items()}
    combat = requested_combat(record)
    # The record's own scripted decisions. A step the engine asks during the
    # arrival (a turn-1 cleanup discard, CR 514.1) is answered there and is
    # consumed here, so the obligation loop starts at the first step the
    # arrival did not answer.
    script = list(record.get("decision_script") or ())
    arrival_consumed = [0]

    def answer_scripted_arrival(
        decision: dict[str, Any],
        decision_class: str,
        principal: str,
        legal: dict[str, Any],
    ) -> bool:
        """Answer the next scripted arrival frame from the record, or refuse.

        The frame is answered only when the record's own next unconsumed step
        scripts this decision class: a cleanup discard is transported from the
        record's card-name multiset (least option id among same-name copies;
        outcome-equivalent only because the copies share one identity). A wrong
        actor, a missing name, a count mismatch, a malformed frame and an
        unscripted extra discard all fail closed with the exact reason; the Lab
        never chooses a card for a player.
        """
        position_ = arrival_consumed[0]
        while position_ < len(script) and (
            str(script[position_].get("decision_family")) in ARRIVAL_TRANSPORT_FAMILIES
        ):
            # The arrival transport steps are not engine choose_object frames:
            # the starting_player step is the record's setup declaration (CR
            # 103.1), the mulligan steps are the pregame keeps (CR 103.5), and
            # the priority_pass_through / declare_attackers steps are answered
            # by the arrival driver itself. The cursor steps over them instead
            # of demanding a same-class engine frame.
            position_ += 1
            arrival_consumed[0] = position_
        if position_ < len(script):
            step = script[position_]
            if step_decision_class(step) == decision_class:
                _require_scripted_temporal_point(client, step)
                actor = str(step.get("actor"))
                if actor != principal:
                    raise ml.MidgameLaneError(
                        f"the engine asked the scripted {decision_class} of {principal}, "
                        f"but the record scripts it for {actor}"
                    )
                answer = _scripted_answer(legal, stack_object_step(step, record), placed, spec, 0)
                trace.append(
                    Frame(
                        decision_class,
                        principal,
                        _labels(legal),
                        decision_id=str(decision.get("decision_id") or "") or None,
                        prompt=str(decision.get("prompt") or ""),
                        context=dict(decision.get("context") or {}),
                        selected_label=_label_of(answer.action) if answer.action else None,
                        selected_key=answer.key,
                        selected_option_ids=answer.option_ids,
                        scripted=True,
                    )
                )
                if answer.action is None:
                    client.submit_options(decision, [])
                else:
                    probe.submit_proposal(
                        client,
                        legal,
                        answer.action,
                        f"{fixture_id}-arrival-{len(trace)}",
                        selected_option_ids=list(answer.option_ids) or None,
                    )
                arrival_consumed[0] = position_ + 1
                return True
        consumed = [
            step for step in script[:position_] if step_decision_class(step) == decision_class
        ]
        if any(str(step.get("actor")) == principal for step in consumed):
            raise ml.MidgameLaneError(
                f"unscripted extra {decision_class} for {principal}: the record scripts "
                f"{len(consumed)} such decision(s) and no more"
            )
        return False

    def declare(decision: dict[str, Any], decision_class: str) -> bool:
        # A combat checkpoint: the record's requested combat is declared on
        # the engine's own frames before it. A declaration the record's own
        # script makes is not the requested combat's to answer.
        assert combat is not None
        if decision_class == "declare_attacker" and _scripts_family(record, "declare_attacker"):
            return False
        if decision_class == "declare_blocker" and (
            combat.blocks is None or _scripts_family(record, "declare_blocker")
        ):
            return False
        if decision_class not in {"declare_attacker", "declare_blocker"}:
            return False
        trace.append(
            answer_requested_combat(
                client,
                record,
                decision,
                decision_class,
                combat,
                placed,
                placed_by_native,
                f"{fixture_id}-arrival-{len(trace)}",
            )
        )
        return True

    try:
        arrival = probe.drive_arrival(
            client,
            record,
            declare=declare if combat is not None else None,
            answer_scripted=answer_scripted_arrival,
        )
    except ml.MidgameLaneError as exc:
        return row_execution(fixture_id, False, None, f"arrival failed closed: {exc}")
    if arrival is None:
        return row_execution(
            fixture_id, False, None, "the engine did not reach the record's checkpoint"
        )
    # The declared causal elimination openly substitutes the victim's recorded
    # life at the pre-causal position (CR 704.3); that substitution is a
    # Lab-declared variance and can never read as an exact construction. An
    # engine verdict that was already ALLOWED_VARIANCE keeps its own source and
    # only records the Lab declaration beside it.
    disposition = construction_with_declared_substitution(arrival.construction_verdict, created)
    construction = disposition.verdict
    variance_source = disposition.variance_source
    declared_substitution_source = disposition.declared_substitution_source
    if construction not in ACCEPTED_CONSTRUCTION:
        return row_execution(
            fixture_id,
            False,
            construction,
            f"construction {construction}: {list(arrival.mismatches)}",
        )
    reconstruction: dict[str, Any] | None = None
    elimination_baseline: int | None = None
    mode = causal.get("entry_mode") if causal is not None else None
    composed = mode == probe.CAUSAL_STACK_ELIMINATION
    # A composed entry builds the victim's stack first (and requires the stack
    # verifier's match), then eliminates the victim with that stack intact.
    if causal is not None and mode in ("causal_stack", probe.CAUSAL_STACK_ELIMINATION):
        declared_fuel = [str(card["semantic_id"]) for card in causal.get("fuel") or ()]
        fuel = [placed[semantic] for semantic in declared_fuel if semantic in placed]
        # A composed row's document names both halves even when the stack never ran.
        unbuilt = (
            {"entry_mode": probe.CAUSAL_STACK_ELIMINATION, "stack": None, "elimination": None}
            if composed
            else None
        )
        if len(fuel) != len(declared_fuel):
            return row_execution(
                fixture_id,
                False,
                construction,
                "a declared fuel card was not placed",
                causal_reconstruction=unbuilt,
            )
        try:
            probe.causal_stack_frames(client, f"{fixture_id}-causal", causal_plan, placed, fuel)
            verdict = probe.complete_causal(client, "stack").get("verdict") or {}
        except ml.MidgameLaneError as exc:
            return row_execution(
                fixture_id,
                False,
                construction,
                f"causal reconstruction failed closed: {exc}",
                causal_reconstruction=unbuilt,
            )
        reconstruction = {
            "entry_mode": "causal_stack",
            "fuel": declared_fuel,
            "frames_bottom_to_top": [
                str(frame.get("semantic_id"))
                for frame in causal_plan.get("frames_bottom_to_top") or ()
            ],
            "verdict": verdict,
        }
        if not verdict.get("causal_match") or verdict.get("mismatches"):
            return row_execution(
                fixture_id,
                False,
                construction,
                f"the causal reconstruction does not match the requested stack: {verdict}",
                causal_reconstruction=(
                    {
                        "entry_mode": probe.CAUSAL_STACK_ELIMINATION,
                        "stack": reconstruction,
                        "elimination": None,
                    }
                    if composed
                    else reconstruction
                ),
            )
    if composed and causal is not None and causal.get("caused_permanents"):
        # Caused permanents exist once their casts resolve; the verifier then
        # compares attachment and control with the record before the loss.
        try:
            probe.resolve_stack(client, f"{fixture_id}-causal-resolve")
            permanents = probe.complete_causal(client, "permanents").get("verdict") or {}
        except ml.MidgameLaneError as exc:
            return row_execution(
                fixture_id,
                False,
                construction,
                f"caused permanents failed closed: {exc}",
                causal_reconstruction={
                    "entry_mode": probe.CAUSAL_STACK_ELIMINATION,
                    "stack": reconstruction,
                    "permanents": None,
                    "elimination": None,
                },
            )
        assert reconstruction is not None
        reconstruction["permanents"] = permanents
        if not permanents.get("causal_match") or permanents.get("mismatches"):
            return row_execution(
                fixture_id,
                False,
                construction,
                f"the caused permanents do not match the record: {permanents}",
                causal_reconstruction={
                    "entry_mode": probe.CAUSAL_STACK_ELIMINATION,
                    "stack": reconstruction,
                    "permanents": permanents,
                    "elimination": None,
                },
            )
    stack_reconstruction = reconstruction if composed else None

    def composed_document(elimination: dict[str, Any] | None) -> dict[str, Any] | None:
        # A composed row keeps both halves on every exit, success or not.
        if not composed:
            return elimination
        return {
            "entry_mode": probe.CAUSAL_STACK_ELIMINATION,
            "stack": stack_reconstruction,
            "elimination": elimination,
        }

    if causal is not None and mode in ("causal_elimination", probe.CAUSAL_STACK_ELIMINATION):
        # The requested checkpoint is the state-based-action-pending instant
        # inside the causal cause, so the obligation window opens before it.
        elimination_baseline = int(client.events(0)["latest_offset"])
        try:
            verdict = probe.eliminate_causally(client, f"{fixture_id}-causal", created, causal)
        except ml.MidgameLaneError as exc:
            return row_execution(
                fixture_id,
                False,
                construction,
                f"causal elimination failed closed: {exc}",
                causal_reconstruction=composed_document(None),
            )
        reconstruction = composed_document(
            {
                "entry_mode": "causal_elimination",
                "actor": str(causal.get("elimination_actor")),
                "victim": str(causal.get("elimination_victim")),
                "bolt_count": int(causal.get("bolt_count") or 0),
                "verdict": verdict,
            }
        )
        if not (verdict.get("victim_lost") is True or verdict.get("victim_left") is True):
            return row_execution(
                fixture_id,
                False,
                construction,
                f"the engine did not eliminate the victim causally: {verdict}",
                causal_reconstruction=reconstruction,
            )
    if spec.observe_from_game_start:
        baseline = 0
    elif elimination_baseline is not None:
        baseline = elimination_baseline
    else:
        baseline = int(client.events(0)["latest_offset"])
    sources = [placed[s] for s in spec.mana_sources if s in placed]
    if len(sources) != len(spec.mana_sources):
        return row_execution(
            fixture_id, False, construction, "a declared mana source was not placed"
        )
    cost_obligation: tuple[str, str, str] | None = None
    if spec.cost_obligation is not None:
        cost_source, cost_base, cost_total = spec.cost_obligation
        native_cost_source = placed.get(cost_source)
        if native_cost_source is None:
            return row_execution(
                fixture_id, False, construction, "the declared cost source was not placed"
            )
        cost_obligation = (native_cost_source, cost_base, cost_total)
    required = list((record.get("expected_events") or {}).get("required_events") or ())
    # The arrival already answered its own scripted steps (a turn-1 cleanup
    # discard); the obligation loop starts at the first unconsumed step.
    position = arrival_consumed[0]
    ordinal = 0
    declaring = False
    blocking = False
    answered_blockers: set[str] = set()
    paying = False
    spent_colors: list[str] = []
    placed_by_native = {native: semantic for semantic, native in placed.items()}
    answers_attacks = combat is not None and not _scripts_family(record, "declare_attacker")
    answers_blocks = (
        combat is not None
        and combat.blocks is not None
        and not _scripts_family(record, "declare_blocker")
    )
    unresolved_library = {
        semantic: native
        for semantic, native in placed.items()
        if native.startswith(LIBRARY_POSITION_PREFIX)
    }
    refusals: list[dict[str, Any]] = []
    omission_probe = declared_omission_probe(record)
    omission_refused = False
    bindings = dict(spec.token_bindings)
    pending_alternative: str | None = None
    pending_costs: list[tuple[str, str]] = []
    pending_delve: list[str] = []
    delving = False

    def token_evidence(
        token: str, tape: list[dict[str, Any]], observation: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if match := re.fullmatch(r"new_object_incarnation:(line:.+)", token):
            return new_incarnation_evidence(match.group(1), record, tape)
        check = bindings.get(token)
        if isinstance(check, VocabularyToken):
            evidence = verify_token(
                check.token,
                tape,
                trace,
                semantic_commanders,
                spec.commander_printed_mana_value,
                refusals,
                cost_obligation,
            )
            return None if evidence is None else {"binding": check.describe(), **evidence}
        if check is not None:
            if observation is None:
                observation = (
                    client.complete_arrival().get("observation") or {}
                    if needs_observation(check)
                    else {}
                )
            return bound_token_evidence(check, observation, tape, trace)
        return verify_token(
            token,
            tape,
            trace,
            semantic_commanders,
            spec.commander_printed_mana_value,
            refusals,
            cost_obligation,
        )

    def observed_all(tape: list[dict[str, Any]]) -> bool:
        observation = (
            client.complete_arrival().get("observation") or {}
            if any(token in bindings and needs_observation(bindings[token]) for token in required)
            else None
        )
        return all(token_evidence(t, tape, observation) is not None for t in required)

    reads_extra_turns = any(_reads_extra_turns(check) for check in bindings.values()) or any(
        _reads_extra_turns(check) for check in spec.terminal_checks
    )
    read_at: int | None = None
    detail = "bound reached"
    try:
        for _ in range(spec.max_decisions):
            tape = client.events(baseline)["events"]
            if (
                position >= len(script)
                and observed_all(tape)
                and _terminal_holds(client, spec, tape, trace)
            ):
                detail = "obligation observed"
                break
            decision = client.pending_decision(attempts=5)
            if decision is None:
                detail = "the engine went terminal"
                break
            decision_class = str(decision.get("decision_class"))
            legal = probe.legal_actions(client)
            principal = probe.decision_principal(decision, legal)
            frame = Frame(
                decision_class,
                principal,
                _labels(legal),
                decision_id=str(decision.get("decision_id") or "") or None,
                prompt=str(decision.get("prompt") or ""),
                context=dict(decision.get("context") or {}),
            )
            if decision_class == "declare_blocker":
                frame.offered_attackers = _offered_attackers(legal, placed_by_native)
            pilot_stack = (decision.get("pilot_state") or {}).get("stack")
            if isinstance(pilot_stack, list):
                frame.stack_size = len(pilot_stack)
            seen = client.events(baseline)["events"]
            frame.tape_sequence = int(seen[-1]["sequence"]) if seen else None
            if reads_extra_turns and (not trace or frame.tape_sequence != read_at):
                # A pure query of the parked engine, repeated only once the
                # tape has grown: a skipped readback can only leave a creation
                # unobserved (the row then fails closed), never invent one.
                _read_pending_extra_turns(frame, client)
                read_at = frame.tape_sequence
            trace.append(frame)
            if unresolved_library:
                bound = _bind_library_objects(legal, unresolved_library, tape)
                for semantic, native in bound.items():
                    placed[semantic] = native
                    placed_by_native[native] = semantic
                    unresolved_library.pop(semantic)
            step = script[position] if position < len(script) else None
            if declaring and decision_class != "declare_attacker":
                # The attack declarations are complete: the assignment step is done.
                declaring = False
                position += 1
                step = script[position] if position < len(script) else None
            if paying and decision_class != "mana_payment":
                # The scripted payment is complete: the engine spent exactly
                # the record's declared mana, color for color.
                paying = False
                declared = ((step or {}).get("selection") or {}).get("semantic_value") or {}
                declared_colors = sorted(
                    _COLOR_NAMES.get(str(m).upper(), str(m)).lower()
                    for m in (declared.get("mana") or ())
                )
                if sorted(spent_colors) != declared_colors:
                    raise ml.MidgameLaneError(
                        f"the engine spent {sorted(spent_colors)}, the record declares "
                        f"{declared_colors}"
                    )
                spent_colors = []
                position += 1
                step = script[position] if position < len(script) else None
            if blocking and (
                decision_class != "declare_blocker" or principal != (step or {}).get("actor")
            ):
                # The step's block declarations are complete: the engine asks
                # something else, or asks the next defending player. Every
                # creature the record names as a blocker must have been asked
                # about by the engine.
                blocking = False
                assigned = ((step or {}).get("selection") or {}).get("semantic_value") or {}
                unasked = sorted(set(assigned) - answered_blockers)
                if unasked:
                    raise ml.MidgameLaneError(
                        f"the engine never asked about the record's blockers {unasked}"
                    )
                answered_blockers = set()
                position += 1
                step = script[position] if position < len(script) else None
            scripted = step is not None and step.get("actor") == principal
            if (
                scripted
                and step is not None
                and str((step.get("selection") or {}).get("selector_kind")) == "fail_closed_probe"
                and step_decision_class(step) == decision_class
            ):
                # The record's obligation is the explicit typed refusal of a
                # decision class the handler does not support. Nothing is
                # selected, nothing is submitted and the engine state cannot
                # change; a malformed refusal fails the row closed. Only a
                # frame of the probe's own decision class is refused: the
                # actor's priority before that frame is not the probed decision.
                try:
                    typed = refusal_mod.refuse_pending_decision(client, decision, legal=legal)
                except refusal_mod.RefusalError as exc:
                    raise ml.MidgameLaneError(
                        f"the typed unsupported-decision refusal failed closed: {exc}"
                    ) from exc
                frame.refused = True
                frame.refusal_kind = typed.kind
                refusals.append(typed.document())
                position += 1
                continue
            if (
                omission_probe is not None
                and not omission_refused
                and decision_class == omission_probe[0]
                and principal == omission_probe[1]
            ):
                # The record declares this frame's external handler
                # intentionally unavailable (``negative_fallback_probe``) and
                # its obligation is the typed fail-closed refusal: nothing is
                # selected, nothing is submitted, and the engine's own frame
                # must still be pending afterwards with its event offset
                # unchanged. A malformed refusal fails the row closed. A second
                # frame of the class is not refused again: it falls through to
                # the unscripted stop below, because the record scripts one
                # omission only.
                try:
                    typed = refusal_mod.refuse_pending_decision(client, decision, legal=legal)
                except refusal_mod.RefusalError as exc:
                    raise ml.MidgameLaneError(
                        f"the declared omission refusal failed closed: {exc}"
                    ) from exc
                frame.refused = True
                frame.refusal_kind = typed.kind
                refusals.append(typed.document())
                omission_refused = True
                continue
            if (
                decision_class == "declare_attacker"
                and scripted
                and step is not None
                and step.get("decision_family") == "declare_attacker"
            ):
                action = _attacker_answer(legal, step, placed_by_native)
                frame.selected_label, frame.scripted = _label_of(action), True
                frame.selected_option_ids = _single_option_id(action)
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                declaring = True
                continue
            if (
                decision_class == "declare_blocker"
                and scripted
                and step is not None
                and step.get("decision_family") == "declare_blocker"
                and str((step.get("selection") or {}).get("selector_kind")) == "blocker_assignment"
            ):
                blocker, block_offer = _blocker_answer(legal, step, placed, placed_by_native)
                frame.scripted = True
                if blocker is not None:
                    answered_blockers.add(blocker)
                if block_offer is None:
                    client.submit_options(decision, [])
                    frame.selected_key = "none"
                else:
                    frame.selected_label = _label_of(block_offer)
                    frame.selected_option_ids = _single_option_id(block_offer)
                    probe.submit_proposal(client, legal, block_offer, f"{fixture_id}-{len(trace)}")
                blocking = True
                continue
            if (decision_class == "declare_attacker" and answers_attacks) or (
                decision_class == "declare_blocker" and answers_blocks
            ):
                assert combat is not None
                trace[-1] = answer_requested_combat(
                    client,
                    record,
                    decision,
                    decision_class,
                    combat,
                    placed,
                    placed_by_native,
                    f"{fixture_id}-{len(trace)}",
                )
                continue
            if decision_class == "priority":
                if (
                    scripted
                    and step is not None
                    and step.get("decision_family") == "priority"
                    and _timing_allows(step, decision)
                ):
                    action = _scripted_priority_action(legal, step, placed, commanders)
                    frame.selected_label, frame.scripted = _label_of(action), True
                    frame.selected_source_object = _source_of(action)
                    source_native = frame.selected_source_object
                    frame.selected_source_semantic = placed_by_native.get(
                        str(source_native)
                    ) or next(
                        (cid for cid, native in commanders.items() if native == source_native),
                        None,
                    )
                    frame.selected_option_ids = _single_option_id(action)
                    probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                    pending_alternative = _pending_alternative_cost(step, action)
                    pending_costs = _pending_cost_choices(step)
                    pending_delve = _pending_delve(step, placed)
                    position += 1
                    continue
                if scripted and step is not None and _is_ability_choice(step):
                    # XMage enumerates a permanent's legal activated abilities
                    # on the priority frame; choosing one is activating it.
                    key = str((step.get("selection") or {}).get("semantic_value"))
                    action = _ability_choice_answer(legal, key, spec, placed)
                    frame.selected_label, frame.scripted = _label_of(action), True
                    frame.selected_key = f"{ABILITY_KEY_PREFIX}{key}"
                    frame.selected_source_object = _source_of(action)
                    frame.selected_option_ids = _single_option_id(action)
                    probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                    position += 1
                    continue
                passed = probe.option_of_type(decision, "pass_priority")
                if passed is None:
                    raise ml.MidgameLaneError("the engine offered no pass")
                client.submit_options(decision, [passed])
                continue
            if decision_class == "choice" and pending_alternative is not None:
                # The engine asks for the cost of the cast the record just made;
                # the record's own step named the alternative cost to pay. The
                # cost choice comes first: a sacrifice it requires is asked after.
                action = _alternative_cost_answer(legal, pending_alternative)
                frame.selected_label, frame.scripted = _label_of(action), True
                frame.selected_key = pending_alternative
                frame.selected_option_ids = _single_option_id(action)
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                pending_alternative = None
                continue
            if (
                pending_costs
                and decision_class in ("choose_object", "target", "choice")
                and _offers_cost(legal, *pending_costs[0], placed)
            ):
                # The engine asks for a cost of the action the record just
                # took; the record's own step named it. A frame that does not
                # offer the owed cost (the spell's target, asked first) is the
                # scripted step's own.
                kind, wanted = pending_costs[0]
                action = _cost_choice_answer(legal, kind, wanted, placed)
                frame.selected_label, frame.scripted = _label_of(action), True
                frame.selected_key = f"{kind}:{wanted}"
                frame.selected_option_ids = _single_option_id(action)
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                pending_costs = pending_costs[1:]
                continue
            if (
                decision_class == "mana_payment"
                and pending_delve
                and not delving
                and _mana_offer(legal, sources) is None
            ):
                # The record's cast names the graveyard cards it delves. XMage
                # offers delve as its own special action on the payment frame,
                # then asks for one graveyard card per activation. The declared
                # mana sources pay first: once delve has been activated, XMage
                # no longer offers the other mana abilities on that payment.
                delve_offer = _delve_offer(legal)
                frame.selected_label, frame.scripted = _label_of(delve_offer), True
                frame.selected_key = "delve"
                frame.selected_option_ids = _single_option_id(delve_offer)
                probe.submit_proposal(
                    client, legal, delve_offer, f"{fixture_id}-delve-{len(trace)}"
                )
                delving = True
                continue
            if delving:
                if decision_class != "choose_object":
                    raise ml.MidgameLaneError(
                        f"delve was activated but the engine asked {decision_class}, "
                        "not the graveyard card"
                    )
                action = _delve_card_answer(legal, pending_delve[0])
                frame.selected_label, frame.scripted = _label_of(action), True
                frame.selected_key = f"delve:{placed_by_native.get(pending_delve[0])}"
                frame.selected_option_ids = _single_option_id(action)
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                pending_delve = pending_delve[1:]
                delving = False
                continue
            if decision_class == "mana_payment":
                offer = _mana_offer(legal, sources)
                if offer is None:
                    raise ml.MidgameLaneError(
                        "no declared mana source or single pool spend was offered"
                    )
                frame.selected_label = _label_of(offer)
                frame.selected_option_type = str((offer.get("metadata") or {}).get("option_type"))
                frame.selected_option_ids = _single_option_id(offer)
                probe.submit_proposal(client, legal, offer, f"{fixture_id}-mana-{len(trace)}")
                if scripted and step is not None and step.get("decision_family") == "mana_payment":
                    # The record scripts this payment: the payment frames are
                    # its step, and the colors the engine spent are checked
                    # against the step's declared mana when the payment ends.
                    frame.scripted = True
                    paying = True
                    if frame.selected_option_type == "mana_pool":
                        spent_colors.append(_spent_color(frame.selected_label))
                continue
            if scripted and step is not None and answers_frame(step, decision_class, spec):
                answer = _scripted_answer(
                    legal, stack_object_step(step, record), placed, spec, ordinal
                )
                if answer.action is None:
                    client.submit_options(decision, [])
                    frame.scripted, frame.selected_key = True, answer.key
                    ordinal = 0
                    position += 1
                    continue
                frame.selected_label, frame.scripted = _label_of(answer.action), True
                frame.selected_key, frame.numeric = answer.key, answer.numeric
                frame.selected_source_object = _source_of(answer.action)
                frame.selected_option_ids = answer.option_ids
                probe.submit_proposal(
                    client,
                    legal,
                    answer.action,
                    f"{fixture_id}-{len(trace)}",
                    numeric_choice=answer.numeric,
                    selected_option_ids=list(answer.option_ids) or None,
                )
                selection = step.get("selection") or {}
                entries = selection.get("semantic_value")
                selector_kind = selection.get("selector_kind")
                if (
                    selector_kind == "order"
                    and isinstance(entries, list)
                    and ordinal + 2 < len(entries)
                ):
                    # More than one ability is still to be ordered: the engine
                    # asks again, and the last one goes on the stack by itself.
                    ordinal += 1
                    continue
                if (
                    selector_kind == "order"
                    and isinstance(entries, list)
                    and ordinal + 1 < len(entries)
                    and not str(entries[ordinal + 1]).startswith("trigger:")
                    and _next_frame_continues(client, decision_class, principal)
                ):
                    # An ordered object set: the engine asks once per object it
                    # still needs placed; a last object it places by itself
                    # ends the step.
                    ordinal += 1
                    continue
                if selector_kind == "amount_assignment":
                    # One engine frame per declared leg: the next frame of this
                    # step answers the next leg; the step is done only when
                    # every leg has been assigned. A further frame after that is
                    # an extra assignment and fails closed in the selector.
                    legs = _assignment_entries(entries)
                    if ordinal + 1 < len(legs):
                        ordinal += 1
                        continue
                ordinal = 0
                position += 1
                continue
            detail = f"unscripted {decision_class} for {principal}: the row stops unverified"
            break
    except ml.MidgameLaneError as exc:
        detail = f"execution failed closed: {exc}"
    tape = client.events(baseline)["events"]
    readback_needed = any(needs_observation(check) for check in spec.terminal_checks) or any(
        needs_observation(bindings[token]) for token in required if token in bindings
    )
    try:
        # The final readback is a pure query of a parked engine: wait until the
        # engine has parked on its next decision (or ended) before asking.
        client.pending_decision(attempts=5)
        observation = client.complete_arrival().get("observation") or {}
    except ml.MidgameLaneError as exc:
        if not readback_needed:
            # Nothing this row verifies reads the readback: the tape and the
            # decision trace are the whole evidence.
            observation = {}
        else:
            return row_execution(
                fixture_id,
                False,
                construction,
                f"{detail}; the final engine readback failed closed: {exc}",
                decision_trace=[frame.__dict__ for frame in trace],
                tape=tape,
                refusals=refusals,
                causal_reconstruction=reconstruction,
            )
    evidence: dict[str, Any] = {}
    missing: list[str] = []
    for token in required:
        found = token_evidence(token, tape, observation)
        if found is None:
            missing.append(token)
        else:
            evidence[token] = found
    terminal = {
        check.describe(): check_terminal(check, observation, tape, trace)
        for check in spec.terminal_checks
    }
    scripted_attacks = _scripts_family(record, "declare_attacker")
    scripted_blocks = _scripts_family(record, "declare_blocker")
    if combat is not None and (
        not scripted_attacks or (combat.blocks is not None and not scripted_blocks)
    ):
        # The requested combat is part of the requested state: the engine's
        # own declaration events (from game start) must be exactly the part
        # of it this run answered. Declarations the record's own script makes
        # are verified by its script and tokens, not here.
        declared = combat_matches_request(
            RequestedCombat(
                attackers=combat.attackers,
                blocks=None if scripted_blocks else combat.blocks,
            ),
            client.events(0)["events"],
            compare_attacks=not scripted_attacks,
        )
        terminal[REQUESTED_COMBAT_FACT] = bool(declared["holds"])
    for channel, used in declared_shuffle_channels(record, tape).items():
        terminal[f"rules_randomness channel {channel} used"] = used
    verified = (
        detail == "obligation observed"
        and position >= len(script)
        and not missing
        and all(terminal.values())
    )
    return row_execution(
        fixture_id,
        verified,
        construction,
        detail,
        token_evidence=evidence,
        missing_tokens=missing,
        terminal_facts=terminal,
        decision_trace=[frame.__dict__ for frame in trace],
        tape=tape,
        refusals=refusals,
        causal_reconstruction=reconstruction,
        script_consumed=position >= len(script),
    )


def positive_receipt(
    execution: RowExecution,
    record: dict[str, Any],
    *,
    candidate_commit: str,
    runner_digest: str,
) -> dict[str, Any]:
    """The runner-bound positive fixture receipt for a verified row."""
    if not execution.verified:
        raise ValueError(f"{execution.fixture_id} is not verified; no positive receipt")
    required = list((record.get("expected_events") or {}).get("required_events") or ())
    document: dict[str, Any] = {
        "schema_version": POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": "xmage",
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "fixture_id": execution.fixture_id,
        "test_identity": TEST_IDENTITY_PREFIX + execution.fixture_id,
        "execution_mode": EXECUTION_MODE,
        "construction_verdict": execution.construction_verdict,
        # The source of a non-exact verdict: the engine's own declaration-step
        # priority allowance, or the Lab's own declared causal life
        # substitution. It is carried beside the verdict, never folded into the
        # token evidence.
        "variance_source": execution.variance_source,
        # The Lab's declared causal life substitution whenever the elimination
        # plan declares one, recorded even beside an engine variance so the
        # engine's own disposition is never overwritten.
        "declared_substitution_source": execution.declared_substitution_source,
        "obligation_exercised": {
            "required_events": required,
            "terminal_postconditions": list(record.get("terminal_postconditions") or ()),
            "terminal_checks": sorted(execution.terminal_facts),
            "requested_state_digest": record.get("requested_state_digest"),
            "obligation_digest": record.get("obligation_digest"),
        },
        "observed_assertion": {
            "token_evidence": execution.token_evidence,
            "terminal_facts": execution.terminal_facts,
            # For a fail-closed obligation the observed assertion is the typed
            # refusal itself, with its no-mutation proof. It is a positive
            # observation of the required behaviour, not an absent one, and it
            # is never derived from a timeout.
            "typed_refusals": execution.refusals,
        },
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        # A typed refusal is its own class. Otherwise the Lab's declared causal
        # life substitution names itself only when it is the verdict's own
        # source, exactly as the Forge scenario lane labels that disposition. An
        # engine ALLOWED_VARIANCE keeps its own class even beside a Lab
        # declaration, which the separate ``declared_substitution_source``
        # still records.
        "assertion_class": (
            "TYPED_FAIL_CLOSED_REFUSAL"
            if execution.refusals
            else ASSERTION_LAB_DECLARED_CAUSAL_SUBSTITUTION
            if execution.variance_source == DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE
            else "BEHAVIOUR_OBSERVED"
        ),
        "outcome": "PASS",
        "runtime_receipt_digest": receipt_mod._digest(execution.document()),
    }
    if execution.causal_reconstruction is not None:
        # The engine's own verdict that the causal route rebuilt exactly the
        # requested stack before the record's script ran.
        document["causal_reconstruction"] = execution.causal_reconstruction
    document["receipt_digest"] = receipt_mod._digest(document)
    return document


def causal_stack_entry(fixture_id: str) -> dict[str, Any] | None:
    """The production probe's declared causal-stack entry for a row, or None."""
    entry = (getattr(probe_module(), "CAUSAL_ROWS", {}) or {}).get(fixture_id)
    if not isinstance(entry, dict) or entry.get("entry_mode") != "causal_stack":
        return None
    return dict(entry)


def causal_elimination_entry(fixture_id: str) -> dict[str, Any] | None:
    """The production probe's declared causal-elimination entry for a row, or None."""
    entry = (getattr(probe_module(), "CAUSAL_ROWS", {}) or {}).get(fixture_id)
    if not isinstance(entry, dict) or entry.get("entry_mode") != "causal_elimination":
        return None
    return dict(entry)


def causal_stack_elimination_entry(fixture_id: str) -> dict[str, Any] | None:
    """The production probe's declared composed stack-then-elimination entry, or None."""
    probe = probe_module()
    entry = (getattr(probe, "CAUSAL_ROWS", {}) or {}).get(fixture_id)
    composed = getattr(probe, "CAUSAL_STACK_ELIMINATION", None)
    if not isinstance(entry, dict) or composed is None or entry.get("entry_mode") != composed:
        return None
    return dict(entry)


def execute_and_persist(
    *,
    workspace: Path,
    records: dict[str, dict[str, Any]],
    candidate_commit: str,
    runner_digest: str,
    out_dir: Path,
    fixtures: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Execute every declared row on a fresh lane process and persist receipts.

    Earlier positive receipts are removed first: a row that no longer verifies
    must not keep credit from a previous run. Only verified rows get a receipt;
    every row's execution document is returned for the evidence summary.
    """
    probe = probe_module()
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = tuple(ROWS) if fixtures is None else fixtures
    # This producer owns only the unprefixed receipts for its declared rows.
    # R-4 adds other direct producers to the same positive-receipt directory;
    # deleting every JSON here would erase their evidence before assembly.
    for fixture_id in selected:
        stale = out_dir / f"{fixture_id}.json"
        if stale.is_file():
            stale.unlink()
    executions: dict[str, Any] = {}
    for fixture_id in selected:
        record = records[fixture_id]
        # The starting seat comes from the record's own starting-seat
        # declaration (``starting_player`` step/field; a turn-1 checkpoint's
        # active player is the starter by CR 103.1). It is never derived from a
        # later checkpoint's active player: at turn 2 the active player is the
        # second seat, and the seat arithmetic "active - (turn - 1)" would
        # invent a start the record never declared. No declaration means no run
        # (#572).
        starting_seat, _starting_source = midgame_starting_seat(record)
        if starting_seat is None:
            executions[fixture_id] = {
                "verified": False,
                "detail": (
                    "the record declares no starting seat for this checkpoint, so the lane "
                    "cannot declare a starting/choosing seat and refuses to run; the Lab "
                    "never derives or chooses it"
                ),
            }
            continue
        starting_seat_index = SEATS.index(starting_seat)
        request = {
            "game_id": f"row-{fixture_id}",
            "plan_id": f"row-{fixture_id}",
            "seed": probe.SEED,
            "starting_player_seat": starting_seat_index,
            "requested_starting_state": record,
        }
        # A record whose stack holds spells enters through the production
        # probe's declared causal-stack route, exactly as the actual-card
        # campaign does: the engine casts the frames, verifies the position
        # and only then runs the record's script.
        causal = causal_stack_entry(fixture_id)
        if causal is not None:
            request["entry_mode"] = "causal_stack"
            request["fuel"] = list(causal.get("fuel") or ())
        elimination = causal_elimination_entry(fixture_id)
        if elimination is not None:
            # The record asks for a player at 0 life before the state-based
            # actions that remove it (CR 704.3: no priority point shows that
            # state). The engine reaches it only causally: the declared bolts
            # are cast at the victim through the engine's own frames.
            request["entry_mode"] = "causal_elimination"
            request["elimination"] = probe.elimination_request(elimination)
            causal = elimination
        composed = causal_stack_elimination_entry(fixture_id)
        if composed is not None:
            # The record's stack must exist while its controller is eliminated
            # (CR 800.4a): the engine casts the frames, the stack verifier
            # confirms them, and only then is the loss caused.
            request["entry_mode"] = probe.CAUSAL_STACK_ELIMINATION
            request["fuel"] = list(composed.get("fuel") or ())
            request["elimination"] = probe.elimination_request(composed)
            if composed.get("caused_permanents"):
                request["caused_permanents"] = list(composed["caused_permanents"])
            causal = composed
        with probe.open_client(workspace) as client:
            client.request("get_provider_version", None)
            client.read_dimension_manifest()
            created = client.request("create_midgame_game", request)
            if not created.get("success"):
                executions[fixture_id] = {
                    "verified": False,
                    "detail": f"creation refused: {created.get('errors')}",
                }
                continue
            client.request("start_midgame_game", None)
            execution = execute_row(
                client, record, created.get("payload") or {}, ROWS[fixture_id], causal=causal
            )
        document = execution.document()
        if client.engine_commit != candidate_commit:
            document["verified"] = False
            document["detail"] = (
                f"engine reported {client.engine_commit}, not the candidate {candidate_commit}"
            )
        elif execution.verified:
            receipt = positive_receipt(
                execution, record, candidate_commit=candidate_commit, runner_digest=runner_digest
            )
            receipt_mod.persist(out_dir / f"{fixture_id}.json", receipt)
            document["receipt_digest"] = receipt["receipt_digest"]
        executions[fixture_id] = document
    return {
        "schema_version": "commander-lab.midgame-row-executions/1.0.0",
        "execution_mode": EXECUTION_MODE,
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "rows_declared": len(executions),
        "rows_verified": sum(1 for doc in executions.values() if doc.get("verified")),
        "rows": executions,
    }
