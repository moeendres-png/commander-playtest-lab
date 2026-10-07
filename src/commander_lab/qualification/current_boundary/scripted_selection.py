"""Provider-neutral selection of one engine-offered option for a record's scripted step.

A record's ``decision_script`` names what a principal does in semantic terms
(``cast obj:micro-bolt``, ``target P2``, ``yes``). The engine offers its own
legal options on its own decision frames. This module matches one scripted step
against the options of one frame and returns exactly one offered option, or
raises :class:`SelectionFailure`. It never invents an option, never picks the
first of several, never defaults a yes/no and never consults an engine AI:
zero matches and multiple matches both fail closed, as every record's
``selection.on_zero_match`` / ``on_multiple_match`` require.

Each provider supplies a thin adapter that normalizes its frames into
:class:`OfferedOption`; the matching rules here are shared, so a provider lane
does not build its own generic selector. The reference semantics are the XMage
mid-game executor's (``midgame_rows._scripted_priority_action`` and
``_scripted_answer``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FAMILIES_WITH_SELECTORS: dict[str, frozenset[str]] = {
    "priority": frozenset({"semantic_action"}),
    "target": frozenset({"semantic_player", "semantic_object"}),
    "choice": frozenset({"boolean"}),
    "replacement_effect": frozenset({"boolean"}),
}
FORBIDDEN_FALLBACKS = frozenset(
    {
        "first_option",
        "random_option",
        "default_yes_no",
        "internal_ai",
        "gui_default",
        "silent_skip",
        "parent_class_fallback",
    }
)


_MANA_SYMBOLS = frozenset({"W", "U", "B", "R", "G", "C"})


class SelectionFailure(Exception):
    """The scripted step does not match exactly one offered option (fail closed)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ObjectRef:
    """An engine-published identity reference carried by an offered option."""

    kind: str  # "player" or "card"
    player_id: str | None = None
    card_id: str | None = None
    name: str | None = None
    controller: str | None = None
    zone: str | None = None


@dataclass(frozen=True)
class OfferedOption:
    """One engine-offered option, normalized by a provider adapter."""

    option_id: str
    decision_class: str
    kind: str
    label: str
    source_name: str | None = None
    refs: tuple[ObjectRef, ...] = ()
    boolean: bool | None = None
    raw: Any = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class SemanticObject:
    """A record's semantic object, as the selector needs it."""

    semantic_id: str
    name: str
    controller: str
    zone: str


def _principal(value: Any) -> str:
    return str(value or "").strip().lower()


def _zone(value: Any) -> str:
    return str(value or "").strip().lower()


def semantic_objects(record: dict[str, Any]) -> dict[str, SemanticObject]:
    """The record's semantic objects by id (name, controller, zone)."""
    objects: dict[str, SemanticObject] = {}
    for entry in record.get("semantic_objects") or ():
        if not isinstance(entry, dict) or not entry.get("semantic_id"):
            continue
        objects[str(entry["semantic_id"])] = SemanticObject(
            semantic_id=str(entry["semantic_id"]),
            name=str(entry.get("card_identity") or ""),
            controller=_principal(entry.get("controller")),
            zone=_zone(entry.get("zone")),
        )
    return objects


def _validate_contract(step: dict[str, Any]) -> dict[str, Any]:
    """The step's selection, once its fail-closed selection contract is checked."""
    selection = step.get("selection") or {}
    if selection.get("matches_only_provider_offered_legal_options") is not True:
        raise SelectionFailure(
            "selection_contract_missing", "the step does not bind offered options"
        )
    if (
        selection.get("on_zero_match") != "FAIL_CLOSED"
        or selection.get("on_multiple_match") != "FAIL_CLOSED"
    ):
        raise SelectionFailure("selection_contract_not_fail_closed", repr(selection))
    if not set(step.get("forbidden_fallbacks") or ()) >= FORBIDDEN_FALLBACKS:
        raise SelectionFailure(
            "forbidden_fallbacks_incomplete", repr(sorted(step.get("forbidden_fallbacks") or ()))
        )
    return dict(selection)


def validate_step(step: dict[str, Any]) -> tuple[str, str, Any]:
    """The step's family, selector kind and semantic value, or a fail-closed refusal."""
    family = str(step.get("decision_family") or "")
    selection = _validate_contract(step)
    selector_kind = str(selection.get("selector_kind") or "")
    if selector_kind not in FAMILIES_WITH_SELECTORS.get(family, frozenset()):
        raise SelectionFailure("selector_not_supported", f"{family}.{selector_kind}")
    return family, selector_kind, selection.get("semantic_value")


def _exactly_one(matches: list[OfferedOption], what: str) -> OfferedOption:
    if not matches:
        raise SelectionFailure("zero_match", f"the engine offered no option for {what}")
    if len(matches) > 1:
        raise SelectionFailure(
            "multiple_match",
            f"the engine offered {len(matches)} options for {what}: "
            f"{[option.label for option in matches]}",
        )
    return matches[0]


def _ref_matches_object(ref: ObjectRef, wanted: SemanticObject) -> bool:
    return (
        ref.kind == "card"
        and ref.name == wanted.name
        and _principal(ref.controller) == wanted.controller
        and (not wanted.zone or _zone(ref.zone) == wanted.zone)
    )


def select(
    step: dict[str, Any],
    decision_class: str,
    options: list[OfferedOption],
    objects: dict[str, SemanticObject],
) -> OfferedOption:
    """The one offered option the scripted step names on this frame."""
    family, selector_kind, value = validate_step(step)
    if decision_class != family and not (
        family == "replacement_effect" and decision_class == "choice"
    ):
        raise SelectionFailure(
            "decision_class_mismatch", f"the step is {family}, the frame is {decision_class}"
        )
    offered = [option for option in options if option.decision_class == decision_class]
    if family == "priority":
        if not isinstance(value, dict) or value.get("action") != "cast":
            raise SelectionFailure("selector_not_supported", f"priority action {value!r}")
        wanted = objects.get(str(value.get("object")))
        if wanted is None or not wanted.name:
            raise SelectionFailure("unknown_semantic_object", repr(value.get("object")))
        return _exactly_one(
            [o for o in offered if o.kind == "cast" and o.source_name == wanted.name],
            f"cast {wanted.semantic_id} ({wanted.name})",
        )
    if family == "target" and selector_kind == "semantic_player":
        player = _principal(value)
        return _exactly_one(
            [
                o
                for o in offered
                if o.kind == "target"
                and len(o.refs) == 1
                and o.refs[0].kind == "player"
                and _principal(o.refs[0].player_id) == player
            ],
            f"target player {player}",
        )
    if family == "target" and selector_kind == "semantic_object":
        wanted = objects.get(str(value))
        if wanted is None:
            raise SelectionFailure("unknown_semantic_object", repr(value))
        return _exactly_one(
            [
                o
                for o in offered
                if o.kind == "target"
                and len(o.refs) == 1
                and _ref_matches_object(o.refs[0], wanted)
            ],
            f"target {wanted.semantic_id} ({wanted.name}, {wanted.controller}, {wanted.zone})",
        )
    if selector_kind == "boolean":
        if not isinstance(value, bool):
            raise SelectionFailure("boolean_value_missing", repr(value))
        return _exactly_one([o for o in offered if o.boolean is value], f"{family} answer {value}")
    raise SelectionFailure("selector_not_supported", f"{family}.{selector_kind}")


def payment_step_mana(step: dict[str, Any]) -> tuple[str, ...]:
    """The mana a scripted ``mana_payment.mana_payment`` step declares, or a refusal.

    The step is never answered by itself: its payment frames are answered only
    from the record's declared payment sources (``select_mana_source``), and the
    declared mana is what the engine's own payment must be judged against.
    """
    if str(step.get("decision_family") or "") != "mana_payment":
        raise SelectionFailure("selector_not_supported", repr(step.get("decision_family")))
    selection = _validate_contract(step)
    if selection.get("selector_kind") != "mana_payment":
        raise SelectionFailure(
            "selector_not_supported", f"mana_payment.{selection.get('selector_kind')}"
        )
    value = selection.get("semantic_value")
    mana = value.get("mana") if isinstance(value, dict) else None
    if (
        not isinstance(mana, list)
        or not mana
        or any(not isinstance(symbol, str) or symbol not in _MANA_SYMBOLS for symbol in mana)
    ):
        raise SelectionFailure("payment_mana_missing", repr(value))
    return tuple(mana)


def select_mana_source(
    options: list[OfferedOption],
    declared: list[SemanticObject],
    used: set[str],
    *,
    interchangeable_fuel: bool = False,
) -> tuple[OfferedOption, SemanticObject]:
    """Pay with the next declared source the engine offers to tap.

    The declared sources (a record's ``explicit_payment_sources`` or a causal
    route's declared fuel) name the sources. An option counts only if it taps a
    declared source not yet used; declining to pay is never chosen.

    Several offers for one card name are ambiguous and fail closed, with one
    exception the caller must opt into (``interchangeable_fuel``): offers for
    one card name that are identical options (same label, same source, no
    references), no more of them than the unused declared sources of that name.
    Those are indistinguishable instances, so their order is not a choice the
    record could make (the XMage lane's ``_interchangeable`` rule); the returned
    source is the next unused one of that name in declaration order. The causal
    route opts in for its own declared fuel, and for a record's declared payment
    sources only when every same-name source is identical in every record
    attribute (``declared_payment_sources``); it then sets
    ``require_all_sources``, so every declared source must pay and no instance
    choice survives the payment.
    """
    remaining = [source for source in declared if source.semantic_id not in used]
    for source in remaining:
        same_name = [other for other in remaining if other.name == source.name]
        matches = [
            o
            for o in options
            if o.decision_class == "mana_payment"
            and o.kind == "tap_mana_source"
            and o.source_name == source.name
        ]
        if not matches:
            continue
        if len(matches) == 1 and len(same_name) == 1:
            return matches[0], source
        identical = len({(o.label, o.source_name, o.refs) for o in matches}) == 1 and not any(
            o.refs for o in matches
        )
        if interchangeable_fuel and identical and len(matches) <= len(same_name):
            return matches[0], source
        raise SelectionFailure(
            "mana_source_ambiguous",
            f"{len(matches)} offers and {len(same_name)} declared sources named {source.name}",
        )
    raise SelectionFailure(
        "zero_match",
        f"no declared mana source is offered: declared {[s.semantic_id for s in remaining]}, "
        f"offered {[o.label for o in options]}",
    )


# ---------------------------------------------------------------------------
# Forge adapter: Protocol-2 bridge frames
# ---------------------------------------------------------------------------
FORGE_DECISION_CLASSES: dict[str, str] = {
    "PRIORITY": "priority",
    "TARGET_SELECTION": "target",
    "MANA_PAYMENT": "mana_payment",
    "GENERIC_CONFIRM": "choice",
    "REPLACEMENT_CONFIRM": "choice",
    "STATIC_CHOICE": "choice",
    "TRIGGER_PLAY": "choice",
    # CR 903.9: "may put it into the command zone", a [Yes]/[No] frame.
    "COMMANDER_MOVE": "choice",
    # Mapped so a frame of these kinds is named and recorded, never guessed. A
    # mapping is not a selector: no scripted family answers these classes here
    # (FAMILIES_WITH_SELECTORS), so ``select`` refuses them, and a route answers
    # one only through its own declared policy (ORDER_CHOICE through
    # ``game_driver.select_cost_order_action``) or fails closed.
    "MODE_SELECTION": "mode",
    "COST_SELECTION": "cost",
    "ORDER_CHOICE": "cost_order",
    "AMOUNT_DISTRIBUTION": "amount",
    "X_ANNOUNCE": "amount",
    "TRIGGER_ORDER": "order",
}
_FORGE_KINDS: dict[str, str] = {
    "cast_spell": "cast",
    "activate_ability": "activate",
    "play_land": "play_land",
    "pass_priority": "pass",
    "concede": "concede",
    "target": "target",
    "tap_mana_source": "tap_mana_source",
}


def _forge_ref(ref: dict[str, Any]) -> ObjectRef:
    return ObjectRef(
        kind=str(ref.get("kind") or ""),
        player_id=None if ref.get("player_id") is None else str(ref.get("player_id")),
        card_id=None if ref.get("card_id") is None else str(ref.get("card_id")),
        name=None if ref.get("name") is None else str(ref.get("name")),
        controller=None if ref.get("controller") is None else str(ref.get("controller")),
        zone=None if ref.get("zone") is None else str(ref.get("zone")),
    )


def forge_options(frame: dict[str, Any]) -> tuple[str, list[OfferedOption]]:
    """A Forge Protocol-2 frame's decision class and normalized offered options.

    A frame kind this adapter does not map raises instead of being guessed.
    """
    decision = frame.get("decision") or {}
    kind = str(decision.get("kind") or "").upper()
    if kind not in FORGE_DECISION_CLASSES:
        raise SelectionFailure("frame_kind_not_mapped", kind)
    decision_class = FORGE_DECISION_CLASSES[kind]
    options: list[OfferedOption] = []
    for action in frame.get("actions") or ():
        if not isinstance(action, dict) or not action.get("action_id"):
            continue
        metadata = action.get("metadata") or {}
        action_type = str(action.get("action_type") or "")
        label = str(metadata.get("label") or "")
        boolean: bool | None = None
        if decision_class == "choice":
            # Forge's parkBinary projects a yes/no frame as two confirm options
            # whose labels end in exactly " [Yes]" or " [No]"; the answer is not a
            # separate field. Only that suffix maps; any other label stays
            # unmapped, so a boolean step can never default.
            if label.endswith(" [Yes]"):
                boolean = True
            elif label.endswith(" [No]"):
                boolean = False
        options.append(
            OfferedOption(
                option_id=str(action["action_id"]),
                decision_class=decision_class,
                kind=_FORGE_KINDS.get(action_type, action_type),
                label=label,
                source_name=(
                    None
                    if action.get("source_object_id") is None
                    else str(action.get("source_object_id"))
                ),
                refs=tuple(
                    _forge_ref(ref)
                    for ref in metadata.get("object_refs") or ()
                    if isinstance(ref, dict)
                ),
                boolean=boolean,
                raw=action,
            )
        )
    return decision_class, options
