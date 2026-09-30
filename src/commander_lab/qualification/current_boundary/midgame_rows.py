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
}


@dataclass
class Frame:
    decision_class: str
    principal: str
    offered_labels: list[str]
    selected_label: str | None = None
    selected_option_type: str | None = None
    scripted: bool = False


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
            if frame.decision_class == family and frame.principal == principal
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
        taps = _mana_taps(trace)
        return {"decision_frames": taps} if len(taps) == int(match.group(1)) else None
    if match := re.fullmatch(r"commander_tax:\+(\d+)_generic", token):
        if commander_printed_mana_value is None:
            return None
        taps = _mana_taps(trace)
        paid_tax = len(taps) - commander_printed_mana_value
        return (
            {"decision_frames": taps, "paid_minus_printed": paid_tax}
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


def _mana_taps(trace: list[Frame]) -> list[int]:
    return [
        index
        for index, frame in enumerate(trace)
        if frame.decision_class == "mana_payment" and frame.selected_option_type == "mana_ability"
    ]


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


def _scripted_answer(
    legal: dict[str, Any], step: dict[str, Any], placed: dict[str, str]
) -> dict[str, Any]:
    probe = probe_module()
    selection = step.get("selection") or {}
    kind = selection.get("selector_kind")
    value = selection.get("semantic_value")
    actions = list(legal.get("actions") or ())
    if kind == "semantic_player":
        label = probe.seat_label(str(value))
        matches = [a for a in actions if _label_of(a) == label]
    elif kind == "semantic_object":
        native = placed.get(str(value))
        matches = [
            a for a in actions if native and probe.find_native_offer({"actions": [a]}, native)
        ]
    else:
        raise ml.MidgameLaneError(f"selector {kind!r} is not executed by this lane")
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the scripted {step.get('decision_family')} {value!r} matched {len(matches)} engine offers"
        )
    chosen: dict[str, Any] = matches[0]
    return chosen


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
    """The first declared mana source the engine offers, else the one advancing pool spend.

    Declared sources are tried in the record's order; the engine never re-offers a
    tapped land. Pool mana is spent only when exactly one advancing spend is
    offered, so no colour choice is ever made on the pilot's behalf.
    """
    actions = list(legal.get("actions") or ())
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
    baseline = int(client.events(0)["latest_offset"])
    script = list(record.get("decision_script") or ())
    sources = [placed[s] for s in spec.mana_sources if s in placed]
    if len(sources) != len(spec.mana_sources):
        return RowExecution(
            fixture_id, False, construction, "a declared mana source was not placed"
        )
    required = list((record.get("expected_events") or {}).get("required_events") or ())
    position = 0
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
            if scripted and step is not None and step.get("decision_family") == decision_class:
                action = _scripted_answer(legal, step, placed)
                frame.selected_label, frame.scripted = _label_of(action), True
                probe.submit_proposal(client, legal, action, f"{fixture_id}-{len(trace)}")
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
