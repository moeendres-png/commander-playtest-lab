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
   priority on the engine's own frame (scripted passes, not fallbacks); the
   controller casts the spell, chooses the record's targets and pays from the
   declared fuel, all through the shared fail-closed selector.
3. **Verify.** The engine's stack then holds exactly the requested number of
   objects, and the decision tape shows the cast of the declared source with the
   declared targets by the declared controller.
4. **Continue.** Every player passes until the engine offers the record's next
   scripted decision, which is answered through the same selector; then the
   remaining scripted passes settle the stack.

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


@dataclass(frozen=True)
class CausalPlan:
    spells: tuple[StackSpell, ...]
    fuel: tuple[FuelCard, ...]

    def to_document(self) -> dict[str, Any]:
        return {
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


def _principal(value: Any) -> str:
    return str(value or "").strip().lower()


def declared_causal_entry(fixture_id: str) -> dict[str, Any] | None:
    """The shared declared causal-stack entry for a row, or None."""
    from commander_lab.qualification.current_boundary import midgame_rows

    return midgame_rows.causal_stack_entry(fixture_id)


def causal_plan(record: dict[str, Any], entry: dict[str, Any] | None) -> CausalPlan | None:
    """The route for a record's requested stack, or None when it is not executable.

    Only a single, complete, modeless spell per stack entry with a declared fuel
    entry is executable; anything else stays an unsupported dimension.
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
    return CausalPlan(spells=tuple(spells), fuel=fuel)


def pre_causal_state(neutral: dict[str, Any], plan: CausalPlan) -> dict[str, Any]:
    """The bootstrap state plus each spell in its controller's hand and the fuel."""
    state = {key: value for key, value in neutral.items()}
    hands = {player: list(cards) for player, cards in (state.get("hands") or {}).items()}
    for spell in plan.spells:
        hands.setdefault(spell.controller, []).append(spell.card)
    state["hands"] = hands
    state["battlefield"] = [
        *(state.get("battlefield") or ()),
        *({"card": card.card, "controller": card.owner, "owner": card.owner} for card in plan.fuel),
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


@dataclass
class CausalRun:
    frames: list[RouteFrame] = field(default_factory=list)
    stack_after_cast: list[Any] | None = None
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    scripted_answers: list[dict[str, Any]] = field(default_factory=list)
    failure: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "frames": [frame.__dict__ for frame in self.frames],
            "stack_after_cast": self.stack_after_cast,
            "snapshots": self.snapshots,
            "scripted_answers": self.scripted_answers,
            "failure": self.failure,
        }


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
    each scripted decision and at the end so the obligation is judged from
    engine facts only.

    The record's scripted step is answered only on a frame of one of
    ``answer_frame_kinds`` and only once the requested stack exists; any other
    non-priority frame fails closed rather than receiving the record's answer.
    When ``checkpoint_priority`` first holds priority with the requested stack
    in place, the engine state is captured as the ``requested_checkpoint``
    snapshot: that, not the pre-causal position, is the record's checkpoint.
    """
    run = CausalRun()
    objects = ss.semantic_objects(record)
    fuel_objects = [
        ss.SemanticObject(card.semantic_id, card.card, card.owner, "battlefield")
        for card in plan.fuel
    ]
    pending_spells = list(plan.spells)
    pending_targets: list[str] = []
    used_fuel: set[str] = set()
    script = list(record.get("decision_script") or ())
    try:
        for _ in range(max_frames):
            frame = poll_decision(proc, game_id, seat_count=seat_count, candidate="forge")
            decision = frame.get("decision") or {}
            kind = str(decision.get("kind") or "").upper()
            actor = _principal(decision.get("actor"))
            if kind not in ss.FORGE_DECISION_CLASSES:
                _record(run, frame, None, [], None, "unexpected frame kind")
                raise CausalRouteError(f"unexpected engine frame {kind} for {actor}")
            decision_class, options = ss.forge_options(frame)
            if pending_targets:
                if decision_class != "target":
                    raise CausalRouteError(f"expected the spell's target frame, got {kind}")
                # The record's targets, consumed in declaration order.
                target = pending_targets.pop(0)
                chosen = ss.select(_target_step(target), decision_class, options, objects)
                _submit(proc, game_id, frame, chosen)
                _record(run, frame, decision_class, options, chosen, "causal target")
                continue
            if decision_class == "mana_payment":
                chosen, source = ss.select_mana_source(
                    options, fuel_objects, used_fuel, interchangeable_fuel=True
                )
                used_fuel.add(source.semantic_id)
                _submit(proc, game_id, frame, chosen)
                _record(
                    run,
                    frame,
                    decision_class,
                    options,
                    chosen,
                    f"declared fuel {source.semantic_id}",
                )
                continue
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
                cast_step = {
                    "decision_family": "priority",
                    "forbidden_fallbacks": sorted(ss.FORBIDDEN_FALLBACKS),
                    "selection": {
                        "matches_only_provider_offered_legal_options": True,
                        "on_multiple_match": "FAIL_CLOSED",
                        "on_zero_match": "FAIL_CLOSED",
                        "selector_kind": "semantic_action",
                        "semantic_value": {"action": "cast", "object": spell.semantic_id},
                    },
                }
                chosen = ss.select(cast_step, decision_class, options, objects)
                _submit(proc, game_id, frame, chosen)
                _record(
                    run, frame, decision_class, options, chosen, f"causal cast {spell.semantic_id}"
                )
                pending_spells.pop(0)
                pending_targets = list(spell.targets)
                continue
            if run.stack_after_cast is None and not pending_spells:
                state = observe(game_id)
                run.stack_after_cast = list(state.get("stack") or [])
                run.snapshots.append({"at": "stack_caused", "state": state})
                if len(run.stack_after_cast) != len(plan.spells):
                    raise CausalRouteError(
                        f"the engine stack holds {len(run.stack_after_cast)} objects, "
                        f"the record requests {len(plan.spells)}"
                    )
            step = script[0] if script else None
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
                if (
                    run.stack_after_cast is not None
                    and checkpoint_priority is not None
                    and actor == _principal(checkpoint_priority)
                    and not any(snap["at"] == "requested_checkpoint" for snap in run.snapshots)
                ):
                    state = observe(game_id)
                    if state.get("stack"):
                        run.snapshots.append({"at": "requested_checkpoint", "state": state})
                if not script and not (observe(game_id).get("stack") or []):
                    _record(run, frame, decision_class, options, None, "settled: empty stack")
                    run.snapshots.append({"at": "settled", "state": observe(game_id)})
                    return run
                passes = [option for option in options if option.kind == "pass"]
                chosen = ss._exactly_one(passes, "priority pass")
                _pass(proc, game_id, frame)
                _record(run, frame, decision_class, options, chosen, "scripted pass")
                continue
            raise CausalRouteError(f"no declared answer for the engine's {kind} frame for {actor}")
        raise CausalRouteError(f"the route did not settle within {max_frames} frames")
    except (CausalRouteError, ss.SelectionFailure) as error:
        run.failure = f"{type(error).__name__}: {error}"
        return run
