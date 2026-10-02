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
    # Event-pattern checks: the engine event type and the field constraints an
    # event must meet. A key ending in ``~`` matches a name by prefix (as the
    # trigger tokens do); every other key must equal the value exactly.
    event_type: str | None = None
    where: tuple[tuple[str, Any], ...] = ()
    # Decision-frame checks: text the engine's own selected offer label contains.
    label: str | None = None

    def describe(self) -> str:
        if self.kind == "events":
            constraints = ", ".join(f"{key}={value}" for key, value in self.where)
            amount = "at least one" if self.value is None else f"exactly {self.value}"
            return f"{amount} {self.event_type} event(s) with {constraints or 'any fields'}"
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
        if self.kind == "assignment_total":
            return f"the engine-accepted amount assignments total exactly {self.value}"
        if self.kind == "assignment_minimum":
            return f"every engine-accepted amount assignment is at least {self.value}"
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
    token_bindings: tuple[tuple[str, TerminalCheck | tuple[TerminalCheck, ...]], ...] = ()


# The record's decision family and the engine's decision class name the same
# decision differently for these families; every other family is spelled alike.
# The multi_amount record and the target_amount record both reach XMage's single
# divided-damage `choose_targets` frame (observed on the production mid-game
# lane); the record distinguishes the number of damage legs in its semantic
# value, not in the engine's class name.
ENGINE_DECISION_CLASS = {"choose_mode": "mode", "multi_amount": "target_amount"}


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
    if match := re.fullmatch(r"cost_determined:base_plus_(\d+)_generic", token):
        return _verify_cost_determined(int(match.group(1)), trace, cost_obligation)
    return None


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
    if determined != expected:
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
    if check.kind == "hand_count_min":
        count = seat.get("hand_count")
        return isinstance(count, int) and count >= check.value
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
    if check.kind == "colors":
        return bool(cards) and all(
            sorted(card.get("colors") or ()) == sorted(check.value) for card in cards
        )
    return False


def matching_events(check: TerminalCheck, tape: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The engine events an ``events`` check's pattern matches, in tape order."""
    hits = []
    for event in _events(tape, str(check.event_type)):
        matched = True
        for key, value in check.where:
            if key.endswith("~"):
                matched = _name_matches(event, key[:-1], str(value))
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
    elif check.kind == "selected_frame":
        evidence["decision_frames"] = _selected_frames(check, trace)
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
    elif kind == "semantic_objects":
        # A multi-select target frame: the record names the complete requested
        # set; every identity must map to exactly one engine-offered target and
        # the set's cardinality must be authorized by the pending frame itself.
        requested = _requested_objects(value)
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
    cost_obligation: tuple[str, str, str] | None = None
    if spec.cost_obligation is not None:
        cost_source, cost_base, cost_total = spec.cost_obligation
        native_cost_source = placed.get(cost_source)
        if native_cost_source is None:
            return RowExecution(
                fixture_id, False, construction, "the declared cost source was not placed"
            )
        cost_obligation = (native_cost_source, cost_base, cost_total)
    required = list((record.get("expected_events") or {}).get("required_events") or ())
    position = 0
    ordinal = 0
    declaring = False
    placed_by_native = {native: semantic for semantic, native in placed.items()}
    refusals: list[dict[str, Any]] = []
    bindings = dict(spec.token_bindings)
    pending_alternative: str | None = None
    pending_costs: list[tuple[str, str]] = []

    def token_evidence(
        token: str, tape: list[dict[str, Any]], observation: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        check = bindings.get(token)
        if check is not None:
            if observation is None:
                observation = client.complete_arrival().get("observation") or {}
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
            if any(token in bindings for token in required)
            else None
        )
        return all(token_evidence(t, tape, observation) is not None for t in required)

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
            trace.append(frame)
            step = script[position] if position < len(script) else None
            if declaring and decision_class != "declare_attacker":
                # The attack declarations are complete: the assignment step is done.
                declaring = False
                position += 1
                step = script[position] if position < len(script) else None
            scripted = step is not None and step.get("actor") == principal
            if (
                scripted
                and step is not None
                and str((step.get("selection") or {}).get("selector_kind")) == "fail_closed_probe"
            ):
                # The record's obligation is the explicit typed refusal of a
                # decision class the handler does not support. Nothing is
                # selected, nothing is submitted and the engine state cannot
                # change; a malformed refusal fails the row closed.
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
                    frame.selected_option_ids = _single_option_id(action)
                    probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                    pending_alternative = _pending_alternative_cost(step, action)
                    pending_costs = _pending_cost_choices(step)
                    position += 1
                    continue
                passed = probe.option_of_type(decision, "pass_priority")
                if passed is None:
                    raise ml.MidgameLaneError("the engine offered no pass")
                client.submit_options(decision, [passed])
                continue
            if pending_costs and decision_class in ("choose_object", "target", "choice"):
                # The engine asks for a cost of the action the record just
                # took; the record's own step named it.
                kind, wanted = pending_costs[0]
                action = _cost_choice_answer(legal, kind, wanted, placed)
                frame.selected_label, frame.scripted = _label_of(action), True
                frame.selected_key = f"{kind}:{wanted}"
                frame.selected_option_ids = _single_option_id(action)
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                pending_costs = pending_costs[1:]
                continue
            if decision_class == "choice" and pending_alternative is not None:
                # The engine asks for the cost of the cast the record just made;
                # the record's own step named the alternative cost to pay.
                action = _alternative_cost_answer(legal, pending_alternative)
                frame.selected_label, frame.scripted = _label_of(action), True
                frame.selected_key = pending_alternative
                frame.selected_option_ids = _single_option_id(action)
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
                pending_alternative = None
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
                continue
            if (
                scripted
                and step is not None
                and engine_decision_class(str(step.get("decision_family"))) == decision_class
            ):
                answer = _scripted_answer(legal, step, placed, spec, ordinal)
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
    observation = client.complete_arrival().get("observation") or {}
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
        refusals=refusals,
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
            # For a fail-closed obligation the observed assertion is the typed
            # refusal itself, with its no-mutation proof. It is a positive
            # observation of the required behaviour, not an absent one, and it
            # is never derived from a timeout.
            "typed_refusals": execution.refusals,
        },
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "assertion_class": (
            "TYPED_FAIL_CLOSED_REFUSAL" if execution.refusals else "BEHAVIOUR_OBSERVED"
        ),
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
