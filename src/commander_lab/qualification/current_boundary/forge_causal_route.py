"""Forge causal stack route: a record's stack is cast, not injected (#520).

The Forge ``ScenarioBootstrap`` cannot place a spell on the stack. A record that
asks for one (for example P2's Doom Blade aimed at P1's commander) is reached
causally, exactly as the XMage lane reaches it (``XmageMidgameCausalBridge``):

1. **Pre-causal position.** The stack spell's card is placed in its controller's
   hand and the row's *declared fuel* (the lands that pay for it) on its owner's
   battlefield. Fuel is never inferred: it is the same declaration the XMage
   probe uses (``run_midgame_capability_probe.CAUSAL_ROWS`` through
   ``midgame_rows.causal_stack_entry``), and it is published in the evidence.
2. **Cause.** At the checkpoint every player before the spell's controller passes
   priority on the engine's own frame (scripted passes, not fallbacks) without
   leaving the pre-causal step; the controller casts the spell, chooses the
   record's targets and pays from the declared fuel, all through the shared
   fail-closed selector. Each stack entry is cast in the record's order.
3. **Verify.** A cast is complete only when the engine returns priority to its
   caster with the source on top of a stack one object taller (the XMage
   frame-complete predicate); the engine's stack then holds exactly the record's
   stack, top first, and the decision tape shows each cast of a declared source
   with the declared targets by the declared controller.
4. **Continue.** Every player passes until the engine offers the record's next
   scripted decision, which is answered through the same selector. A scripted
   priority cast takes the record's own following target and payment steps and
   pays only from the record's ``action_cost_state`` sources, under the same
   cast-complete predicate. The remaining scripted passes settle the stack.

Nothing here casts, pays, resolves or decides anything itself: every transition
is an engine-offered option on an engine frame, selected by
``scripted_selection``. A frame the route does not expect fails closed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from commander_lab.qualification.current_boundary import scripted_selection as ss
from commander_lab.qualification.current_boundary.bridge_launcher import BridgeProcess
from commander_lab.qualification.current_boundary.game_driver import (
    decision_identity_params,
    poll_decision,
)

ROUTE_SCHEMA_VERSION = "forge-causal-stack-route-1.0.0"
# The production probe's composed entry mode (``CAUSAL_STACK_ELIMINATION``):
# the record's stack is cast, verified, and only then is its controller
# eliminated. Checked against the probe's own constant when planned.
CAUSAL_STACK_ELIMINATION = "causal_stack_elimination"


class CausalRouteError(RuntimeError):
    """The causal route cannot be executed as declared (fail closed)."""


@dataclass(frozen=True)
class StackSpell:
    semantic_id: str
    card: str
    controller: str  # "p2"
    targets: tuple[str, ...]


@dataclass(frozen=True)
class FuelCard:
    semantic_id: str
    card: str
    owner: str  # "p2"


# The record's declared loss reason, mapped to the pinned engine's own
# ``GameLossReason`` name the readback reports (``loss_reason``). A reason not
# listed here is not routed: the Lab never guesses how an engine names a loss.
ENGINE_LOSS_REASONS: dict[str, str] = {"life_total_0": "LifeReachedZero"}


@dataclass(frozen=True)
class EliminationPlan:
    """A declared causal elimination after the record's stack is cast (CR 800.4a).

    The instruments are the shared declaration (``elimination_request`` of the
    production probe, the XMage lane's own): one Lightning Bolt in the actor's
    hand and one Mountain on the actor's battlefield per declared bolt. The
    victim's recorded life (the state-based-action-pending instant of CR 704.3,
    which no priority point shows) cannot be placed before the victim casts its
    spell, so the victim starts at its recorded starting life, openly
    substituted and published, and the engine alone deals the damage and
    applies the loss.
    """

    actor: str
    victim: str
    bolt_count: int
    bolts: tuple[FuelCard, ...]
    lands: tuple[FuelCard, ...]
    recorded_life: int
    starting_life: int
    engine_loss_reason: str
    survivors: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "victim": self.victim,
            "bolt_count": self.bolt_count,
            "instruments": [
                {"semantic_id": card.semantic_id, "card": card.card, "owner": card.owner}
                for card in (*self.bolts, *self.lands)
            ],
            "life_substitution": {
                "player_id": self.victim,
                "recorded_life": self.recorded_life,
                "placed_life": self.starting_life,
                "basis": (
                    "the recorded life is the state-based-action-pending instant (CR 704.3); "
                    "it is reached only by the engine dealing the declared bolts' damage"
                ),
            },
            "engine_loss_reason": self.engine_loss_reason,
            "survivors": list(self.survivors),
            "instrument_authority": (
                "run_midgame_capability_probe.CAUSAL_ROWS + elimination_request (shared with XMage)"
            ),
        }


@dataclass(frozen=True)
class CausalPlan:
    spells: tuple[StackSpell, ...]
    fuel: tuple[FuelCard, ...]
    elimination: EliminationPlan | None = None

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema_version": ROUTE_SCHEMA_VERSION,
            "spells": [
                {
                    "semantic_id": spell.semantic_id,
                    "card": spell.card,
                    "controller": spell.controller,
                    "targets": list(spell.targets),
                }
                for spell in self.spells
            ],
            "declared_fuel": [
                {"semantic_id": card.semantic_id, "card": card.card, "owner": card.owner}
                for card in self.fuel
            ],
            "fuel_authority": "run_midgame_capability_probe.CAUSAL_ROWS (shared with XMage)",
        }
        if self.elimination is not None:
            document["elimination"] = self.elimination.to_document()
        return document


def _principal(value: Any) -> str:
    return str(value or "").strip().lower()


def declared_causal_entry(fixture_id: str) -> dict[str, Any] | None:
    """The shared declared causal-stack entry for a row, or None."""
    from commander_lab.qualification.current_boundary import midgame_rows

    return midgame_rows.causal_stack_entry(
        fixture_id
    ) or midgame_rows.causal_stack_elimination_entry(fixture_id)


def _elimination_plan(record: dict[str, Any], entry: dict[str, Any]) -> EliminationPlan | None:
    """The declared elimination of a composed entry, or None when it is not executable.

    Only a composed stack-then-elimination entry without caused permanents is
    planned (a caused permanent needs an attachment and control readback the
    pinned bridge does not project). The instruments come from the shared
    declaration and must be exactly the declared count of bolts and lands; the
    victim must be the record's declared elimination at a declared reason the
    engine names, and at least one survivor must remain.
    """
    from commander_lab.qualification.current_boundary import midgame_rows

    probe = midgame_rows.probe_module()
    if (
        entry.get("entry_mode") != CAUSAL_STACK_ELIMINATION
        or getattr(probe, "CAUSAL_STACK_ELIMINATION", None) != CAUSAL_STACK_ELIMINATION
        or entry.get("caused_permanents")
    ):
        return None
    count = entry.get("bolt_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        return None
    request = probe.elimination_request(entry)
    actor = _principal(request.get("actor"))
    victim = _principal(request.get("victim"))
    instruments = [item for item in request.get("instruments") or () if isinstance(item, dict)]

    def declared(card: str, zone: str) -> tuple[FuelCard, ...]:
        return tuple(
            FuelCard(str(item["semantic_id"]), card, _principal(item.get("owner")))
            for item in instruments
            if item.get("card_identity") == card and item.get("zone") == zone
        )

    bolts = declared("Lightning Bolt", "hand")
    lands = declared("Mountain", "battlefield")
    if (
        len(bolts) != count
        or len(lands) != count
        or len(instruments) != 2 * count
        or any(card.owner != actor for card in (*bolts, *lands))
    ):
        return None
    trigger = record.get("elimination_trigger") or {}
    reason = ENGINE_LOSS_REASONS.get(str(trigger.get("reason")))
    players = {
        _principal(player.get("player_id")): player
        for player in record.get("players") or ()
        if isinstance(player, dict)
    }
    victim_row = players.get(victim) or {}
    recorded = victim_row.get("life")
    starting = victim_row.get("starting_life")
    survivors = tuple(sorted(player for player in players if player != victim))
    if (
        _principal(trigger.get("player")) != victim
        or reason is None
        or actor not in players
        or actor == victim
        or not isinstance(recorded, int)
        or not isinstance(starting, int)
        or recorded > 0
        or starting <= 0
        or not survivors
    ):
        return None
    return EliminationPlan(
        actor=actor,
        victim=victim,
        bolt_count=count,
        bolts=bolts,
        lands=lands,
        recorded_life=recorded,
        starting_life=starting,
        engine_loss_reason=reason,
        survivors=survivors,
    )


def causal_plan(record: dict[str, Any], entry: dict[str, Any] | None) -> CausalPlan | None:
    """The route for a record's requested stack, or None when it is not executable.

    Every stack entry must be a complete, paid, modeless spell (no mode selector
    exists, so a modal entry stays unsupported), and the row must have a
    declared fuel entry. Any number of entries is planned, in the record's
    order (bottom of the stack first); each is cast in turn and must complete
    before the next. Anything else stays an unsupported dimension.
    """
    stack = record.get("stack_state") or []
    if not stack or entry is None:
        return None
    objects = ss.semantic_objects(record)
    spells: list[StackSpell] = []
    for item in stack:
        if not isinstance(item, dict):
            return None
        source = objects.get(str(item.get("source_semantic_id")))
        if (
            source is None
            or item.get("modes")
            or item.get("cast_complete") is not True
            or item.get("costs_paid") is not True
        ):
            return None
        spells.append(
            StackSpell(
                semantic_id=source.semantic_id,
                card=source.name,
                controller=_principal(item.get("controller")),
                targets=tuple(str(target) for target in item.get("targets") or ()),
            )
        )
    fuel = tuple(
        FuelCard(
            semantic_id=str(card["semantic_id"]),
            card=str(card["card_identity"]),
            owner=_principal(card.get("owner")),
        )
        for card in entry.get("fuel") or ()
        if isinstance(card, dict)
    )
    elimination: EliminationPlan | None = None
    if entry.get("entry_mode") == CAUSAL_STACK_ELIMINATION:
        # A composed entry is planned only with its declared elimination.
        elimination = _elimination_plan(record, entry)
        if elimination is None:
            return None
    return CausalPlan(spells=tuple(spells), fuel=fuel, elimination=elimination)


def pre_causal_state(neutral: dict[str, Any], plan: CausalPlan) -> dict[str, Any]:
    """The bootstrap state plus each spell in its controller's hand and the fuel.

    The route casts the stack; it never injects one. A neutral state that
    already carries a stack is refused here, before it can reach the engine
    (whose ``ScenarioBootstrap`` refuses it too).
    """
    if "stack" in neutral or "decision_script" in neutral:
        raise CausalRouteError("the causal route never injects a stack or decisions")
    state = {key: value for key, value in neutral.items()}
    hands = {player: list(cards) for player, cards in (state.get("hands") or {}).items()}
    for spell in plan.spells:
        hands.setdefault(spell.controller, []).append(spell.card)
    elimination = plan.elimination
    lands = list(plan.fuel)
    if elimination is not None:
        # The declared instruments, and the victim's open life substitution
        # (published in the plan): the recorded life is reached by the engine.
        for card in elimination.bolts:
            hands.setdefault(card.owner, []).append(card.card)
        lands.extend(elimination.lands)
        life = dict(state.get("life") or {})
        if life.get(elimination.victim) != elimination.recorded_life:
            raise CausalRouteError(
                f"the neutral state's {elimination.victim} life {life.get(elimination.victim)!r} "
                f"is not the recorded {elimination.recorded_life}"
            )
        life[elimination.victim] = elimination.starting_life
        state["life"] = life
    state["hands"] = hands
    state["battlefield"] = [
        *(state.get("battlefield") or ()),
        *({"card": card.card, "controller": card.owner, "owner": card.owner} for card in lands),
    ]
    return state


@dataclass
class RouteFrame:
    kind: str
    actor: str
    revision: Any
    decision_class: str | None
    offered: list[str]
    chosen: str | None
    chosen_option_id: str | None
    reason: str
    refs: list[dict[str, Any]] = field(default_factory=list)
    offered_option_ids: list[str] = field(default_factory=list)
    chosen_kind: str | None = None
    chosen_source: str | None = None
    payment_source: str | None = None


@dataclass
class CausalRun:
    frames: list[RouteFrame] = field(default_factory=list)
    stack_after_cast: list[Any] | None = None
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    scripted_answers: list[dict[str, Any]] = field(default_factory=list)
    scripted_casts: list[dict[str, Any]] = field(default_factory=list)
    engine_assigned_targets: list[dict[str, Any]] = field(default_factory=list)
    pre_causal_position: dict[str, Any] | None = None
    failure: str | None = None
    # The declared instruments cast after the stack was verified, in order:
    # the instrument's declared id and the tape index of its cast frame.
    elimination_casts: list[dict[str, Any]] = field(default_factory=list)

    def to_document(self) -> dict[str, Any]:
        document = {
            "frames": [frame.__dict__ for frame in self.frames],
            "stack_after_cast": self.stack_after_cast,
            "snapshots": self.snapshots,
            "scripted_answers": self.scripted_answers,
            "scripted_casts": self.scripted_casts,
            "engine_assigned_targets": self.engine_assigned_targets,
            "pre_causal_position": self.pre_causal_position,
            "failure": self.failure,
        }
        if self.elimination_casts:
            document["elimination_casts"] = self.elimination_casts
        return document


@dataclass
class _Cast:
    """One cast in progress: from its cast option until the engine's next priority.

    XMage's frame-complete predicate (``XmageCausalStackReconstruction``): a
    cast is complete only when native priority returns with the source on the
    stack. Until then every frame must be the caster's own target, payment or
    cost-order frame of this cast; anything else fails closed.
    """

    actor: str
    semantic_id: str
    card: str
    prefix: str  # "causal" (the record's stack) or "scripted" (its decision script)
    targets: list[dict[str, Any]]
    sources: list[ss.SemanticObject]
    interchangeable: bool
    stack_before: int
    require_all_sources: bool
    used: set[str] = field(default_factory=set)


# How a payment frame of each kind of cast names its declared source in the tape.
_PAYMENT_LABELS = {"causal": "fuel", "scripted": "payment", "elimination": "instrument"}


def _submit(
    proc: BridgeProcess, game_id: str, frame: dict[str, Any], option: ss.OfferedOption
) -> None:
    action = option.raw or {}
    response = proc.request(
        "submit_action",
        {
            **decision_identity_params("forge", frame),
            "proposal": {
                "proposal_id": str(uuid.uuid4()),
                "actor_id": str((frame.get("decision") or {}).get("actor")),
                "legal_action_id": option.option_id,
                "action_type": str(action.get("action_type")),
            },
        },
        game_id=game_id,
        timeout_s=120.0,
    )
    if response.get("success") is not True:
        raise CausalRouteError(f"the engine refused {option.label!r}: {response.get('errors')}")


def _pass(proc: BridgeProcess, game_id: str, frame: dict[str, Any]) -> None:
    response = proc.request(
        "pass_priority", decision_identity_params("forge", frame), game_id=game_id, timeout_s=120.0
    )
    if response.get("success") is not True:
        raise CausalRouteError(f"pass_priority refused: {response.get('errors')}")


def _record(
    run: CausalRun,
    frame: dict[str, Any],
    decision_class: str | None,
    options: list[ss.OfferedOption],
    chosen: ss.OfferedOption | None,
    reason: str,
    payment_source: str | None = None,
) -> None:
    decision = frame.get("decision") or {}
    run.frames.append(
        RouteFrame(
            kind=str(decision.get("kind")),
            actor=str(decision.get("actor")),
            revision=decision.get("revision"),
            decision_class=decision_class,
            offered=[option.label for option in options],
            chosen=None if chosen is None else chosen.label,
            chosen_option_id=None if chosen is None else chosen.option_id,
            reason=reason,
            refs=[] if chosen is None else [ref.__dict__ for ref in chosen.refs],
            offered_option_ids=[option.option_id for option in options],
            chosen_kind=None if chosen is None else chosen.kind,
            chosen_source=None if chosen is None else chosen.source_name,
            payment_source=payment_source,
        )
    )


def _target_step(target: str) -> dict[str, Any]:
    kind = (
        "semantic_player"
        if target.upper().startswith("P") and target[1:].isdigit()
        else ("semantic_object")
    )
    return {
        "decision_family": "target",
        "forbidden_fallbacks": sorted(ss.FORBIDDEN_FALLBACKS),
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": kind,
            "semantic_value": target,
        },
    }


def _cast_step(semantic_id: str) -> dict[str, Any]:
    return {
        "decision_family": "priority",
        "forbidden_fallbacks": sorted(ss.FORBIDDEN_FALLBACKS),
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": {"action": "cast", "object": semantic_id},
        },
    }


def _stack(state: dict[str, Any]) -> list[str]:
    """The engine's stack readback, top object first."""
    return [str(entry) for entry in state.get("stack") or ()]


def stack_card(entry: Any) -> str:
    """The card name an engine stack entry (``"Name (id) - text"``) was cast from."""
    return str(entry).split(" (")[0]


# Record attributes that tell two same-name payment sources apart. Sources equal
# on all of them are indistinguishable instances (the XMage ``_interchangeable``
# rule); any difference keeps the order of their taps a choice the record must
# make, so it stays ambiguous and fails closed.
_INSTANCE_ATTRIBUTES = (
    "card_identity",
    "controller",
    "owner",
    "zone",
    "tapped",
    "counters",
    "face_down",
    "attached_to",
)


def declared_payment_sources(
    record: dict[str, Any], source_semantic_id: str, actor: str
) -> tuple[list[ss.SemanticObject], bool]:
    """The record's explicit payment sources for one scripted cast.

    Read from the record's own ``action_cost_state`` entry for the cast's source
    and actor; nothing is inferred. Each must be a battlefield object the actor
    controls. The flag says whether same-name sources are indistinguishable in
    every record attribute; the route then requires every declared source to pay,
    so no instance choice survives the payment.
    """
    entries = [
        entry
        for entry in record.get("action_cost_state") or ()
        if isinstance(entry, dict)
        and str(entry.get("source_semantic_id")) == source_semantic_id
        and _principal(entry.get("actor")) == actor
    ]
    if not entries:
        return [], False
    if len(entries) != 1:
        raise CausalRouteError(f"{len(entries)} action_cost_state entries for {source_semantic_id}")
    raw = {
        str(obj.get("semantic_id")): obj
        for obj in record.get("semantic_objects") or ()
        if isinstance(obj, dict) and obj.get("semantic_id")
    }
    objects = ss.semantic_objects(record)
    sources: list[ss.SemanticObject] = []
    for semantic_id in entries[0].get("explicit_payment_sources") or ():
        source = objects.get(str(semantic_id))
        if source is None or source.zone != "battlefield" or source.controller != actor:
            raise CausalRouteError(
                f"declared payment source {semantic_id!r} is not a battlefield object of {actor}"
            )
        # The route binds an engine tap to a declared source only by name, so a
        # declared source the record itself shows unable to pay (tapped, face
        # down with no abilities per CR 708.2, or phased out) would let an
        # undeclared untapped same-name source be credited under the declared
        # id. Refuse it before the engine; an unstated tapped flag is refused too.
        obj = raw.get(source.semantic_id) or {}
        if (
            obj.get("tapped") is not False
            or obj.get("face_down") is True
            or obj.get("phased_out") is True
        ):
            raise CausalRouteError(
                f"declared payment source {semantic_id!r} cannot pay per the record "
                f"(tapped={obj.get('tapped')!r}, face_down={obj.get('face_down')!r}, "
                f"phased_out={obj.get('phased_out')!r})"
            )
        sources.append(source)
    if len({source.semantic_id for source in sources}) != len(sources):
        raise CausalRouteError(f"duplicate declared payment sources for {source_semantic_id}")
    by_name: dict[str, set[tuple[str, ...]]] = {}
    for source in sources:
        obj = raw[source.semantic_id]
        by_name.setdefault(source.name, set()).add(
            tuple(repr(obj.get(attribute)) for attribute in _INSTANCE_ATTRIBUTES)
        )
    return sources, all(len(shapes) == 1 for shapes in by_name.values())


def _position(state: dict[str, Any]) -> dict[str, Any]:
    return {key: state.get(key) for key in ("turn_number", "phase", "step", "active_player_id")}


def _stack_id(entry: str) -> str | None:
    """The engine card id an entry (``"Name (id) - text"``) carries for its source."""
    head = str(entry).split(" - ", 1)[0]
    if not head.endswith(")") or " (" not in head:
        return None
    return head.rsplit(" (", 1)[1][:-1] or None


def _engine_assigned_targets(
    cast: _Cast, stack: list[str], objects: dict[str, ss.SemanticObject]
) -> list[dict[str, Any]]:
    """A declared target the engine assigned without asking, proven from the readback.

    The pinned bridge asks no TARGET_SELECTION frame when exactly one valid
    target set exists (``chooseTargetsFor``): there is no choice to make. The
    record's step is then not answered by the Lab; it must be *verified*: the
    declared target must be a spell on the stack below the new one, named by
    exactly one entry there, and the new spell's own engine text must name that
    entry's card id. Any other unasked target fails closed.
    """
    top = stack[0]
    text = top.split(" - ", 1)[1] if " - " in top else ""
    below = stack[1:]
    proven: list[dict[str, Any]] = []
    for step in cast.targets:
        selection = step.get("selection") or {}
        value = selection.get("semantic_value")
        wanted = objects.get(str(value))
        if selection.get("selector_kind") != "semantic_object" or wanted is None:
            raise CausalRouteError(
                f"the engine asked no target frame for {cast.semantic_id}; the declared target "
                f"{value!r} is verifiable from the readback only as a spell on the stack"
            )
        entries = [entry for entry in below if stack_card(entry) == wanted.name]
        card_id = _stack_id(entries[0]) if len(entries) == 1 else None
        if wanted.zone != "stack" or card_id is None or f"({card_id})" not in text:
            raise CausalRouteError(
                f"the engine assigned {cast.semantic_id}'s target without a frame and the "
                f"readback does not show it as the declared {wanted.semantic_id}: {stack}"
            )
        proven.append(
            {
                "semantic_id": wanted.semantic_id,
                "stack_entry": entries[0],
                "card_id": card_id,
                "cast_text": top,
                "basis": "sole valid target set: the bridge parks no frame; verified in readback",
            }
        )
    cast.targets.clear()
    return proven


def _cast_target_steps(record: dict[str, Any], steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The cast's scripted target steps, a stack target named by the record's stack."""
    from commander_lab.qualification.current_boundary import midgame_lane, midgame_rows

    resolved: list[dict[str, Any]] = []
    for step in steps:
        try:
            resolved.append(midgame_rows.stack_object_step(step, record))
        except midgame_lane.MidgameLaneError as error:
            raise CausalRouteError(str(error)) from error
    return resolved


def player_row(state: dict[str, Any] | None, player: str) -> dict[str, Any] | None:
    """One player's row of an engine readback, by its player id, or None."""
    rows = [
        row
        for row in (state or {}).get("players") or ()
        if isinstance(row, dict) and _principal(row.get("player_id")) == player
    ]
    return rows[0] if len(rows) == 1 else None


def has_lost(state: dict[str, Any] | None, player: str) -> bool | None:
    """The engine's own ``has_lost`` flag for a player, or None when it is not read back."""
    row = player_row(state, player)
    value = None if row is None else row.get("has_lost")
    return value if isinstance(value, bool) else None


def instrument_counts(state: dict[str, Any] | None, plan: EliminationPlan) -> dict[str, Any]:
    """The actor's own view of its declared instruments: bolts in hand, untapped lands.

    Read from the actor's principal-scoped readback only. The declared bolt and
    land counts must equal these engine facts before any instrument is cast.
    """
    zones = (player_row(state, plan.actor) or {}).get("zones") or {}
    bolt = plan.bolts[0].card if plan.bolts else None
    land = plan.lands[0].card if plan.lands else None
    hand = [str(card) for card in zones.get("hand") or ()]
    details = [item for item in zones.get("battlefield_details") or () if isinstance(item, dict)]
    return {
        "bolts_in_hand": sum(1 for card in hand if card == bolt),
        "lands": sum(1 for item in details if item.get("name") == land),
        "untapped_lands": sum(
            1 for item in details if item.get("name") == land and item.get("tapped") is False
        ),
    }


def select_instrument_cast(
    options: list[ss.OfferedOption], card: str, remaining: int
) -> ss.OfferedOption:
    """The cast of the next declared instrument, among identical engine offers only.

    The engine offers one cast per castable card. The offers of the instrument's
    name must be exactly as many as the declared instruments not yet cast, and
    identical (same label and source, no identity reference): they are then
    indistinguishable instances whose order is not a choice (the XMage lane's
    ``_interchangeable`` rule, as ``select_mana_source`` applies it to declared
    fuel). Any other count, including an engine-legal but undeclared instance of
    the same card, and any distinguishable offer fails closed.
    """
    casts = [
        option
        for option in options
        if option.decision_class == "priority"
        and option.kind == "cast"
        and option.source_name == card
    ]
    if len(casts) != remaining:
        raise ss.SelectionFailure(
            "instrument_count_mismatch",
            f"the engine offered {len(casts)} casts of {card}; {remaining} declared "
            "instruments remain",
        )
    if len({(o.label, o.source_name, o.refs) for o in casts}) != 1 or any(o.refs for o in casts):
        raise ss.SelectionFailure(
            "instrument_ambiguous", f"distinguishable casts of {card}: {[o.label for o in casts]}"
        )
    return casts[0]


def run_causal_route(
    proc: BridgeProcess,
    game_id: str,
    record: dict[str, Any],
    plan: CausalPlan,
    *,
    seat_count: int,
    observe: Any,
    answer_frame_kinds: frozenset[str],
    checkpoint_priority: str | None,
    max_frames: int = 200,
) -> CausalRun:
    """Cast the plan's stack, then run the record's script to its settled end.

    ``observe(game_id)`` returns the engine's state readback; it is called at
    each cast, each scripted decision and at the end so the obligation is judged
    from engine facts only.

    Every cast (the record's stack spells, in order, then each scripted cast)
    is complete only when the engine returns priority to its caster with the
    source on top of a stack one object taller; until then only that cast's own
    target, payment and cost-order frames are answered. A scripted cast takes
    the record's own following target and payment steps of the same causal
    step, and pays only from the record's ``action_cost_state`` sources.

    A non-priority scripted step is answered only on a frame of one of
    ``answer_frame_kinds`` and only once the requested stack exists; any other
    non-priority frame fails closed rather than receiving the record's answer.
    When ``checkpoint_priority`` first holds priority with the requested stack
    in place, the engine state is captured as the ``requested_checkpoint``
    snapshot: that, not the pre-causal position, is the record's checkpoint.
    """
    from commander_lab.qualification.current_boundary.game_driver import (
        DecisionUnsatisfied,
        select_cost_order_action,
    )

    run = CausalRun()
    objects = ss.semantic_objects(record)
    fuel_objects = [
        ss.SemanticObject(card.semantic_id, card.card, card.owner, "battlefield")
        for card in plan.fuel
    ]
    pending_spells = list(plan.spells)
    casting: _Cast | None = None
    used_fuel: set[str] = set()
    script = list(record.get("decision_script") or ())
    elimination = plan.elimination
    instrument_lands = (
        []
        if elimination is None
        else [
            ss.SemanticObject(card.semantic_id, card.card, card.owner, "battlefield")
            for card in elimination.lands
        ]
    )
    used_instruments: set[str] = set()
    resolved_instruments = 0
    frame_limit = max_frames + (0 if elimination is None else 8 * elimination.bolt_count)
    try:
        for _ in range(frame_limit):
            frame = poll_decision(proc, game_id, seat_count=seat_count, candidate="forge")
            decision = frame.get("decision") or {}
            kind = str(decision.get("kind") or "").upper()
            actor = _principal(decision.get("actor"))
            if kind not in ss.FORGE_DECISION_CLASSES:
                _record(run, frame, None, [], None, "unexpected frame kind")
                raise CausalRouteError(f"unexpected engine frame {kind} for {actor}")
            decision_class, options = ss.forge_options(frame)
            if run.pre_causal_position is None:
                run.pre_causal_position = _position(observe(game_id))
            if casting is not None and decision_class != "priority":
                if actor != casting.actor:
                    _record(run, frame, decision_class, options, None, "unauthorized frame")
                    raise CausalRouteError(
                        f"the engine asked {kind} of {actor} during {casting.actor}'s cast of "
                        f"{casting.semantic_id}"
                    )
                if decision_class == "target":
                    if not casting.targets:
                        raise CausalRouteError(
                            f"the engine asked a target the record does not declare for "
                            f"{casting.semantic_id}"
                        )
                    # The record's targets, consumed in declaration order.
                    chosen = ss.select(casting.targets.pop(0), decision_class, options, objects)
                    _submit(proc, game_id, frame, chosen)
                    _record(run, frame, decision_class, options, chosen, f"{casting.prefix} target")
                    continue
                if decision_class == "mana_payment":
                    chosen, source = ss.select_mana_source(
                        options,
                        casting.sources,
                        casting.used,
                        interchangeable_fuel=casting.interchangeable,
                    )
                    casting.used.add(source.semantic_id)
                    _submit(proc, game_id, frame, chosen)
                    _record(
                        run,
                        frame,
                        decision_class,
                        options,
                        chosen,
                        f"declared {_PAYMENT_LABELS[casting.prefix]} {source.semantic_id}",
                        payment_source=source.semantic_id,
                    )
                    continue
                if kind == "ORDER_CHOICE":
                    # CR 601.2h: the declared pilot policy (the provider's native
                    # CostPart order), shared with the scenario drive.
                    try:
                        action = select_cost_order_action([o.raw for o in options])
                    except DecisionUnsatisfied as error:
                        raise CausalRouteError(f"ORDER_CHOICE: {error}") from error
                    chosen = ss._exactly_one(
                        [o for o in options if o.option_id == str(action.get("action_id"))],
                        "the declared cost-order policy",
                    )
                    _submit(proc, game_id, frame, chosen)
                    _record(run, frame, decision_class, options, chosen, "native cost-order policy")
                    continue
                _record(run, frame, decision_class, options, None, "unauthorized frame")
                raise CausalRouteError(
                    f"no declared answer for the engine's {kind} frame during the cast of "
                    f"{casting.semantic_id}"
                )
            if casting is not None:
                # Priority returned: the cast is complete only with its source on
                # top of a stack one object taller, its targets all chosen, its
                # declared payment spent, and its caster holding priority.
                state = observe(game_id)
                stack = _stack(state)
                if len(stack) != casting.stack_before + 1:
                    raise CausalRouteError(
                        f"the engine stack holds {len(stack)} objects after the cast of "
                        f"{casting.semantic_id}; the record requests {casting.stack_before + 1}"
                    )
                if stack_card(stack[0]) != casting.card or actor != casting.actor:
                    raise CausalRouteError(
                        f"the cast of {casting.semantic_id} did not complete: the stack top is "
                        f"{stack_card(stack[0])!r} and {actor} holds priority"
                    )
                if casting.require_all_sources and casting.used != {
                    source.semantic_id for source in casting.sources
                }:
                    raise CausalRouteError(
                        f"the cast of {casting.semantic_id} left declared payment sources "
                        f"unused: {sorted({s.semantic_id for s in casting.sources} - casting.used)}"
                    )
                if casting.prefix == "elimination":
                    # The instrument went on top of the verified stack, which is
                    # otherwise untouched, and its target is still in the game.
                    assert elimination is not None
                    if stack[1:] != list(run.stack_after_cast or ()) or has_lost(
                        state, elimination.victim
                    ):
                        raise CausalRouteError(
                            f"the cast of {casting.semantic_id} did not keep the verified stack "
                            f"{run.stack_after_cast} under it with {elimination.victim} in the "
                            f"game: {stack}"
                        )
                if casting.targets:
                    assigned = _engine_assigned_targets(casting, stack, objects)
                    run.engine_assigned_targets.append(
                        {"source_semantic_id": casting.semantic_id, "targets": assigned}
                    )
                run.snapshots.append({"at": f"cast_complete:{casting.semantic_id}", "state": state})
                casting = None
                if run.stack_after_cast is None and not pending_spells:
                    run.stack_after_cast = list(state.get("stack") or [])
                    run.snapshots.append({"at": "stack_caused", "state": state})
                    requested = [spell.card for spell in reversed(plan.spells)]
                    if [stack_card(entry) for entry in stack] != requested:
                        raise CausalRouteError(
                            f"the engine stack {stack} is not the record's stack {requested} "
                            "(top first)"
                        )
            if pending_spells and decision_class == "priority":
                spell = pending_spells[0]
                if actor != spell.controller:
                    passes = [option for option in options if option.kind == "pass"]
                    chosen = ss._exactly_one(passes, "priority pass")
                    _pass(proc, game_id, frame)
                    _record(
                        run, frame, decision_class, options, chosen, "scripted pass to the caster"
                    )
                    continue
                chosen = ss.select(_cast_step(spell.semantic_id), decision_class, options, objects)
                position = observe(game_id)
                if _position(position) != run.pre_causal_position:
                    # Passing to the caster must not end the step: an all-pass
                    # ring on an empty stack advances the game (CR 117.4), so
                    # the cast would happen at another checkpoint than the
                    # record's. The pre-causal position is then past the caster.
                    raise CausalRouteError(
                        f"the engine left the pre-causal position {run.pre_causal_position} "
                        f"before {spell.controller} could cast {spell.semantic_id}: "
                        f"{_position(position)}"
                    )
                before = len(_stack(position))
                _submit(proc, game_id, frame, chosen)
                _record(
                    run, frame, decision_class, options, chosen, f"causal cast {spell.semantic_id}"
                )
                pending_spells.pop(0)
                casting = _Cast(
                    actor=spell.controller,
                    semantic_id=spell.semantic_id,
                    card=spell.card,
                    prefix="causal",
                    targets=[_target_step(target) for target in spell.targets],
                    sources=fuel_objects,
                    interchangeable=True,
                    stack_before=before,
                    require_all_sources=False,
                    used=used_fuel,
                )
                continue
            if decision_class == "priority" and (
                not pending_spells
                and checkpoint_priority is not None
                and actor == _principal(checkpoint_priority)
                and not any(snap["at"] == "requested_checkpoint" for snap in run.snapshots)
            ):
                state = observe(game_id)
                if state.get("stack"):
                    run.snapshots.append({"at": "requested_checkpoint", "state": state})
            if (
                elimination is not None
                and decision_class == "priority"
                and actor == elimination.actor
                and not pending_spells
                and run.stack_after_cast is not None
            ):
                # The declared elimination, only after the record's stack was
                # cast and verified at the requested checkpoint (CR 800.4a: the
                # victim's spell must be on the stack when the victim leaves).
                if script:
                    raise CausalRouteError("a declared elimination runs no decision script")
                if not any(snap["at"] == "requested_checkpoint" for snap in run.snapshots):
                    raise CausalRouteError(
                        f"{actor} holds priority before the requested checkpoint was captured"
                    )
                state = observe(game_id)
                stack = _stack(state)
                caused = list(run.stack_after_cast)
                if len(stack) == len(caused) + 1 and run.elimination_casts:
                    # An instrument is on top of the verified stack: every
                    # player passes so the engine resolves it.
                    passes = [option for option in options if option.kind == "pass"]
                    chosen = ss._exactly_one(passes, "priority pass")
                    _pass(proc, game_id, frame)
                    _record(run, frame, decision_class, options, chosen, "elimination pass")
                    continue
                if len(run.elimination_casts) > resolved_instruments:
                    resolved_instruments += 1
                    run.snapshots.append(
                        {"at": f"elimination_resolved:{resolved_instruments}", "state": state}
                    )
                if has_lost(state, elimination.victim):
                    if len(run.elimination_casts) != elimination.bolt_count:
                        # The loss must be the engine's answer to every declared
                        # instrument, after the stack was verified, never earlier.
                        raise CausalRouteError(
                            f"{elimination.victim} lost after {len(run.elimination_casts)} of "
                            f"{elimination.bolt_count} declared instruments"
                        )
                    _record(run, frame, decision_class, options, None, "eliminated: settled")
                    run.snapshots.append({"at": "after_loss", "state": state})
                    return run
                if stack != caused:
                    raise CausalRouteError(
                        f"the engine stack {stack} is not the verified stack {caused} while "
                        f"{elimination.victim} is in the game"
                    )
                if not run.elimination_casts:
                    counts = instrument_counts(state, elimination)
                    wanted = {
                        "bolts_in_hand": elimination.bolt_count,
                        "lands": elimination.bolt_count,
                        "untapped_lands": elimination.bolt_count,
                    }
                    if counts != wanted or has_lost(state, elimination.victim) is not False:
                        raise CausalRouteError(
                            f"the engine shows {actor}'s instruments {counts} and "
                            f"{elimination.victim} lost={has_lost(state, elimination.victim)!r}; "
                            f"declared {wanted} with {elimination.victim} in the game"
                        )
                    run.snapshots.append({"at": "elimination_start", "state": state})
                index = len(run.elimination_casts)
                if index >= elimination.bolt_count:
                    raise CausalRouteError(
                        f"all {elimination.bolt_count} declared instruments resolved and the "
                        f"engine did not eliminate {elimination.victim}"
                    )
                bolt = elimination.bolts[index]
                chosen = select_instrument_cast(options, bolt.card, elimination.bolt_count - index)
                _submit(proc, game_id, frame, chosen)
                _record(
                    run,
                    frame,
                    decision_class,
                    options,
                    chosen,
                    f"elimination cast {bolt.semantic_id}",
                )
                run.elimination_casts.append(
                    {"semantic_id": bolt.semantic_id, "frame_index": len(run.frames) - 1}
                )
                casting = _Cast(
                    actor=actor,
                    semantic_id=bolt.semantic_id,
                    card=bolt.card,
                    prefix="elimination",
                    targets=[_target_step(elimination.victim.upper())],
                    sources=instrument_lands,
                    interchangeable=True,
                    stack_before=len(stack),
                    require_all_sources=False,
                    used=used_instruments,
                )
                continue
            step = script[0] if script else None
            if (
                step is not None
                and _principal(step.get("actor")) == actor
                and decision_class == "priority"
                and step.get("decision_family") == "priority"
                and not pending_spells
            ):
                value = (step.get("selection") or {}).get("semantic_value")
                source_id = str(value.get("object")) if isinstance(value, dict) else ""
                cast_object = objects.get(source_id)
                if cast_object is None:
                    raise CausalRouteError(f"the scripted cast names no object: {value!r}")
                following: list[dict[str, Any]] = []
                for later in script[1:]:
                    if (
                        _principal(later.get("actor")) != actor
                        or not step.get("causal_step_id")
                        or later.get("causal_step_id") != step.get("causal_step_id")
                        or later.get("decision_family") not in ("target", "mana_payment")
                    ):
                        break
                    following.append(later)
                targets = _cast_target_steps(
                    record, [s for s in following if s.get("decision_family") == "target"]
                )
                payments = [s for s in following if s.get("decision_family") == "mana_payment"]
                if len(payments) > 1:
                    raise CausalRouteError(f"{len(payments)} payment steps for {source_id}")
                declared_mana = ss.payment_step_mana(payments[0]) if payments else None
                sources, interchangeable = declared_payment_sources(record, source_id, actor)
                state = observe(game_id)
                run.snapshots.append(
                    {"at": f"before_scripted_{len(run.scripted_answers)}", "state": state}
                )
                chosen = ss.select(step, decision_class, options, objects)
                _submit(proc, game_id, frame, chosen)
                _record(run, frame, decision_class, options, chosen, "scripted step")
                run.scripted_answers.append(
                    {
                        "step": step.get("causal_step_id"),
                        "frame_kind": kind,
                        "label": chosen.label,
                        "boolean": chosen.boolean,
                    }
                )
                run.scripted_casts.append(
                    {
                        "step": step.get("causal_step_id"),
                        "actor": actor,
                        "source_semantic_id": source_id,
                        "card": cast_object.name,
                        "cast_label": chosen.label,
                        # Copied from the record's own steps: what was declared, not
                        # what the engine showed. The observed target evidence is the
                        # tape and ``engine_assigned_targets``.
                        "declared_targets": [
                            (s.get("selection") or {}).get("semantic_value") for s in targets
                        ],
                        "declared_mana": None if declared_mana is None else list(declared_mana),
                        "declared_payment_sources": [s.semantic_id for s in sources],
                    }
                )
                del script[: 1 + len(following)]
                casting = _Cast(
                    actor=actor,
                    semantic_id=source_id,
                    card=cast_object.name,
                    prefix="scripted",
                    targets=targets,
                    sources=sources,
                    interchangeable=interchangeable,
                    stack_before=len(_stack(state)),
                    require_all_sources=True,
                )
                continue
            if (
                step is not None
                and _principal(step.get("actor")) == actor
                and decision_class != "priority"
            ):
                if run.stack_after_cast is None or kind not in answer_frame_kinds:
                    _record(run, frame, decision_class, options, None, "unauthorized frame")
                    raise CausalRouteError(
                        f"the engine asked {kind} of {actor}; the record's step "
                        f"{step.get('causal_step_id')} is answered only on "
                        f"{sorted(answer_frame_kinds)} after the requested stack is cast"
                    )
                state = observe(game_id)
                run.snapshots.append(
                    {"at": f"before_scripted_{len(run.scripted_answers)}", "state": state}
                )
                chosen = ss.select(step, decision_class, options, objects)
                _submit(proc, game_id, frame, chosen)
                _record(run, frame, decision_class, options, chosen, "scripted step")
                run.scripted_answers.append(
                    {
                        "step": step.get("causal_step_id"),
                        "frame_kind": kind,
                        "label": chosen.label,
                        "boolean": chosen.boolean,
                    }
                )
                script.pop(0)
                continue
            if decision_class == "priority":
                if not script and not (observe(game_id).get("stack") or []):
                    _record(run, frame, decision_class, options, None, "settled: empty stack")
                    run.snapshots.append({"at": "settled", "state": observe(game_id)})
                    return run
                passes = [option for option in options if option.kind == "pass"]
                chosen = ss._exactly_one(passes, "priority pass")
                _pass(proc, game_id, frame)
                _record(run, frame, decision_class, options, chosen, "scripted pass")
                continue
            _record(run, frame, decision_class, options, None, "unauthorized frame")
            raise CausalRouteError(f"no declared answer for the engine's {kind} frame for {actor}")
        raise CausalRouteError(f"the route did not settle within {max_frames} frames")
    except (CausalRouteError, ss.SelectionFailure) as error:
        run.failure = f"{type(error).__name__}: {error}"
        return run
