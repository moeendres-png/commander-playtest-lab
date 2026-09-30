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

REPO_ROOT = Path(__file__).resolve().parents[4]
PROBE_SCRIPT = REPO_ROOT / "scripts" / "run_midgame_capability_probe.py"
EXECUTION_MODE = "MIDGAME_LANE_PLACEMENT_OBLIGATION"
TEST_IDENTITY_PREFIX = "midgame-lane:placement-obligation#"
POSITIVE_FIXTURE_RECEIPT_SCHEMA = receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA
ACCEPTED_CONSTRUCTION = {"EXACT", "ALLOWED_VARIANCE"}


@dataclass(frozen=True)
class TerminalCheck:
    """One explicit terminal postcondition, read from the engine's observation."""

    kind: str
    principal: str | None = None
    value: Any = None
    source_name: str | None = None
    card_identity: str | None = None

    def describe(self) -> str:
        if self.kind == "life":
            return f"{self.principal} is at {self.value} life"
        if self.kind == "trigger_count":
            return f"{self.source_name} triggered exactly {self.value} time(s)"
        if self.kind == "commander_prior_casts":
            return f"{self.principal}'s commander cast count is {self.value}"
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
        return self.kind


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
    # The obligation is the game start itself (who takes the first turn, the
    # first turn's draw), which happens before the arrival checkpoint: the tape
    # is read from the engine's first event instead of from the arrival.
    observe_from_game_start: bool = False


# The record's decision family and the engine's decision class name the same
# decision differently for these families; every other family is spelled alike.
ENGINE_DECISION_CLASS = {"choose_mode": "mode"}


def engine_decision_class(family: str) -> str:
    return ENGINE_DECISION_CLASS.get(family, family)


def _life(principal: str, value: int) -> TerminalCheck:
    return TerminalCheck("life", principal=principal, value=value)


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

    def document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "verified": self.verified,
            "construction_verdict": self.construction_verdict,
            "detail": self.detail,
            "token_evidence": self.token_evidence,
            "missing_tokens": self.missing_tokens,
            "terminal_facts": self.terminal_facts,
            "decision_trace": self.decision_trace,
            "tape": self.tape,
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
    if match := re.fullmatch(r"([a-z_]+?)_(?:decision_)?frame:(P\d+)", token):
        family, principal = match.group(1), match.group(2)
        frames = [
            index
            for index, frame in enumerate(trace)
            if frame.decision_class == engine_decision_class(family)
            and frame.principal == principal
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
    return None


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
    return False


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
    probe = probe_module()
    value = (step.get("selection") or {}).get("semantic_value") or {}
    action = str(value.get("action"))
    if action == "cast":
        native = placed.get(str(value.get("object")))
    elif action == "cast_commander":
        native = commanders.get(str(value.get("commander_id")))
    else:
        raise ml.MidgameLaneError(
            f"scripted priority action {action!r} is not executed by this lane"
        )
    offer: dict[str, Any] | None = probe.find_source_cast(legal, native) if native else None
    if offer is None:
        raise ml.MidgameLaneError(f"the engine did not offer the scripted {action} of {value}")
    return offer


@dataclass(frozen=True)
class ScriptedAnswer:
    """The engine offer a script step names, plus what the step bound it to."""

    action: dict[str, Any]
    key: str | None = None
    numeric: int | None = None


def _option_type(action: dict[str, Any]) -> str:
    return str((action.get("metadata") or {}).get("option_type") or "")


def _scripted_answer(
    legal: dict[str, Any],
    step: dict[str, Any],
    placed: dict[str, str],
    spec: RowSpec,
    ordinal: int = 0,
) -> ScriptedAnswer:
    probe = probe_module()
    selection = step.get("selection") or {}
    kind = selection.get("selector_kind")
    value = selection.get("semantic_value")
    actions = list(legal.get("actions") or ())
    key: str | None = None
    numeric: int | None = None
    if kind == "semantic_player":
        label = probe.seat_label(str(value))
        matches = [a for a in actions if _label_of(a) == label]
    elif kind == "semantic_object":
        native = placed.get(str(value))
        matches = [
            a for a in actions if native and probe.find_native_offer({"actions": [a]}, native)
        ]
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
        wanted = re.fullmatch(r"trigger:(.+)", key)
        if wanted is None:
            raise ml.MidgameLaneError(f"order entry {key!r} names no triggered ability")
        name = wanted.group(1).replace("_", " ")
        matches = [
            a
            for a in actions
            if _option_type(a) == "triggered_ability"
            and ((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("source_name")
            == name
        ]
    else:
        raise ml.MidgameLaneError(f"selector {kind!r} is not executed by this lane")
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the scripted {step.get('decision_family')} {value!r} matched {len(matches)} engine offers"
        )
    return ScriptedAnswer(matches[0], key=key, numeric=numeric)


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


def _terminal_holds(
    client: ml.MidgameLaneClient, spec: RowSpec, tape: list[dict[str, Any]], trace: list[Frame]
) -> bool:
    if not spec.terminal_checks:
        return True
    observation = client.complete_arrival().get("observation") or {}
    return all(check_terminal(check, observation, tape, trace) for check in spec.terminal_checks)


def execute_row(
    client: ml.MidgameLaneClient,
    record: dict[str, Any],
    created: dict[str, Any],
    spec: RowSpec,
) -> RowExecution:
    """Arrive, execute the scripted obligation and verify it. Never raises for a
    lane-level refusal: an unverifiable row is returned unverified with the reason."""
    probe = probe_module()
    fixture_id = str(record["fixture_id"])
    if not (record.get("expected_events") or {}).get("required_events") and not (
        spec.terminal_checks
    ):
        # Nothing would be observed, so "verified" would hold for any behaviour.
        return RowExecution(
            fixture_id, False, None, "the obligation names no required event and no terminal check"
        )
    placed = {str(k): str(v) for k, v in (created.get("placed_objects") or {}).items()}
    commanders = {str(k): str(v) for k, v in (created.get("commander_objects") or {}).items()}
    semantic_commanders = {
        str(o["semantic_id"]) for o in record.get("semantic_objects") or () if o.get("commander_id")
    }
    trace: list[Frame] = []
    try:
        arrival = probe.drive_arrival(client, record)
    except ml.MidgameLaneError as exc:
        return RowExecution(fixture_id, False, None, f"arrival failed closed: {exc}")
    if arrival is None:
        return RowExecution(
            fixture_id, False, None, "the engine did not reach the record's checkpoint"
        )
    construction = arrival.construction_verdict
    if construction not in ACCEPTED_CONSTRUCTION:
        return RowExecution(
            fixture_id,
            False,
            construction,
            f"construction {construction}: {list(arrival.mismatches)}",
        )
    baseline = 0 if spec.observe_from_game_start else int(client.events(0)["latest_offset"])
    script = list(record.get("decision_script") or ())
    sources = [placed[s] for s in spec.mana_sources if s in placed]
    if len(sources) != len(spec.mana_sources):
        return RowExecution(
            fixture_id, False, construction, "a declared mana source was not placed"
        )
    required = list((record.get("expected_events") or {}).get("required_events") or ())
    position = 0
    ordinal = 0
    declaring = False
    placed_by_native = {native: semantic for semantic, native in placed.items()}
    detail = "bound reached"
    try:
        for _ in range(spec.max_decisions):
            tape = client.events(baseline)["events"]
            if (
                position >= len(script)
                and all(
                    verify_token(
                        t, tape, trace, semantic_commanders, spec.commander_printed_mana_value
                    )
                    is not None
                    for t in required
                )
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
            frame = Frame(decision_class, principal, _labels(legal))
            trace.append(frame)
            step = script[position] if position < len(script) else None
            if declaring and decision_class != "declare_attacker":
                # The attack declarations are complete: the assignment step is done.
                declaring = False
                position += 1
                step = script[position] if position < len(script) else None
            scripted = step is not None and step.get("actor") == principal
            if (
                decision_class == "declare_attacker"
                and scripted
                and step is not None
                and step.get("decision_family") == "declare_attacker"
            ):
                action = _attacker_answer(legal, step, placed_by_native)
                frame.selected_label, frame.scripted = _label_of(action), True
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                declaring = True
                continue
            if decision_class == "priority":
                if scripted and step is not None and step.get("decision_family") == "priority":
                    action = _scripted_priority_action(legal, step, placed, commanders)
                    frame.selected_label, frame.scripted = _label_of(action), True
                    probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                    position += 1
                    continue
                passed = probe.option_of_type(decision, "pass_priority")
                if passed is None:
                    raise ml.MidgameLaneError("the engine offered no pass")
                client.submit_options(decision, [passed])
                continue
            if decision_class == "mana_payment":
                offer = _mana_offer(legal, sources)
                if offer is None:
                    raise ml.MidgameLaneError(
                        "no declared mana source or single pool spend was offered"
                    )
                frame.selected_label = _label_of(offer)
                frame.selected_option_type = str((offer.get("metadata") or {}).get("option_type"))
                probe.submit_proposal(client, legal, offer, f"{fixture_id}-mana-{len(trace)}")
                continue
            if (
                scripted
                and step is not None
                and engine_decision_class(str(step.get("decision_family"))) == decision_class
            ):
                answer = _scripted_answer(legal, step, placed, spec, ordinal)
                frame.selected_label, frame.scripted = _label_of(answer.action), True
                frame.selected_key, frame.numeric = answer.key, answer.numeric
                probe.submit_proposal(
                    client,
                    legal,
                    answer.action,
                    f"{fixture_id}-{len(trace)}",
                    numeric_choice=answer.numeric,
                )
                selection = step.get("selection") or {}
                entries = selection.get("semantic_value")
                if (
                    selection.get("selector_kind") == "order"
                    and isinstance(entries, list)
                    and ordinal + 2 < len(entries)
                ):
                    # More than one ability is still to be ordered: the engine
                    # asks again, and the last one goes on the stack by itself.
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
    observation = client.complete_arrival().get("observation") or {}
    evidence: dict[str, Any] = {}
    missing: list[str] = []
    for token in required:
        found = verify_token(
            token, tape, trace, semantic_commanders, spec.commander_printed_mana_value
        )
        if found is None:
            missing.append(token)
        else:
            evidence[token] = found
    terminal = {
        check.describe(): check_terminal(check, observation, tape, trace)
        for check in spec.terminal_checks
    }
    verified = (
        detail == "obligation observed"
        and position >= len(script)
        and not missing
        and all(terminal.values())
    )
    return RowExecution(
        fixture_id,
        verified,
        construction,
        detail,
        token_evidence=evidence,
        missing_tokens=missing,
        terminal_facts=terminal,
        decision_trace=[frame.__dict__ for frame in trace],
        tape=tape,
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
        },
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "outcome": "PASS",
        "runtime_receipt_digest": receipt_mod._digest(execution.document()),
    }
    document["receipt_digest"] = receipt_mod._digest(document)
    return document


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
    for stale in out_dir.glob("*.json"):
        stale.unlink()
    executions: dict[str, Any] = {}
    for fixture_id in tuple(ROWS) if fixtures is None else fixtures:
        record = records[fixture_id]
        request = {
            "game_id": f"row-{fixture_id}",
            "plan_id": f"row-{fixture_id}",
            "seed": probe.SEED,
            "requested_starting_state": record,
        }
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
            execution = execute_row(client, record, created.get("payload") or {}, ROWS[fixture_id])
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
