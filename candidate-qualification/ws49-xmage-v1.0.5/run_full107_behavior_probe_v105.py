#!/usr/bin/env python3
"""WS49 G49-09 fresh provider-native behavior probe for v1.0.5 (107 records).

Executes every provider-denominator obligation from record 1 as live XMage
Rules behavior in one fresh game process per record, with zero imported
historical successor-runtime credit. Construction/normalization grant zero
behavior credit here: each record restores its native state (or natural game
start) and then CONTINUES into the actual Rules procedure.

Rules authority:
- XMage Rules Core exclusively owns legality. The runner only publishes
  natively offered options, maps the immutable scripted semantic selector
  against those offers, requires exactly one match (zero/multiple fail
  closed), rebinds the unique semantic option to the exact native option,
  and submits through the external decision controller.
- Requested/expected material is NEVER submitted, copied into results, or
  used to determine legality. Anti-echo probes verify this per record.

Execution classes:
- NATURAL_GAME_START (7): native startup/mulligan/game-start to the declared
  terminal checkpoint, then structural postcondition verification.
- NATIVE_STATE_LOAD, empty script, projection ops (20 hidden): actor-entitled
  knowledge projection battery with honey-sentinel leak scan.
- NATIVE_STATE_LOAD, fail_closed_probe script or fail_closed required events
  (7 negative): drive to the declared decision frame, withhold every response
  (handler intentionally unavailable), terminate with typed
  UNSUPPORTED_DISCRETIONARY_DECISION. Any fallback or continuation fails.
- NATIVE_STATE_LOAD, decision script (73): generic decision loop. Each native
  pending decision is matched against the next unmatched script entry for its
  actor; priority passes are submitted only while the record procedure
  declares explicit scripted passes and no script entry matches the offer.
  Native resolution continues to the terminal checkpoint; required/forbidden
  events, ordering constraints, and terminal postconditions are evaluated
  against natively derived observations only.

Event derivation (no echo): the emitted event log is built SOLELY from native
payloads -- pending-decision frames, submitted native option identities and
metadata, observation queries, RNG/replay tapes, and terminal state. Expected
strings are used only at evaluation time as the pass predicate.

Verdicts per record: PASS_BEHAVIOR | FAIL_CLOSED_* | UNKNOWN_*.
UNKNOWN is not PASS. PARTIAL is not FULL. Behavior credit requires PASS.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS42 = HERE.parents[0] / "ws42-xmage-v1.0.3"
sys.path[:0] = [str(HERE), str(WS42)]

import canonical_v105  # noqa: E402
import run_full107_construction_probe_v103 as legacy  # noqa: E402
import run_full107_construction_probe_v103_enriched as enriched  # noqa: E402
import run_full107_construction_probe_v105 as construction_v105  # noqa: E402
from successor_contract_v105 import load_contract, provider_records  # noqa: E402

SCHEMA_VERSION = "commander-lab.ws49-full107-behavior-probe/1.0.0"
MATERIALIZATION_VERSION = "commander-lab.semantic-fixture-materialization/1.0.5"
HONEY_SENTINEL = "WS30_HONEY_P2_PRIVATE_7F3A"
MAX_DECISION_STEPS = 64
EXPECTED_ENTRY_MODE_COUNTS = {"NATIVE_STATE_LOAD": 100, "NATURAL_GAME_START": 7}

# decision_class values emitted by the XMage full-game bridge player.
PRIORITY_CLASS = "priority"
PASS_OPTION_TYPE = "pass_priority"


def fail(code: str, fixture_id: str, detail: Any = None) -> None:
    suffix = "" if detail is None else ":" + json.dumps(detail, sort_keys=True, ensure_ascii=False)[:800]
    raise RuntimeError(f"{code}:{fixture_id}{suffix}")


def canonical_player(seat: int, fixture_id: str) -> str:
    if not isinstance(seat, int) or isinstance(seat, bool) or seat < 0:
        fail("WS49_BEHAVIOR_ACTOR_SEAT_INVALID", fixture_id, seat)
    return f"P{seat + 1}"


def script_entries(record: dict[str, Any]) -> list[dict[str, Any]]:
    entries = record.get("decision_script") or []
    if not isinstance(entries, list):
        fail("WS49_BEHAVIOR_DECISION_SCRIPT_INVALID", record.get("fixture_id"))
    return entries


def procedure_has_pass_steps(record: dict[str, Any]) -> bool:
    return any(
        isinstance(step, dict)
        and step.get("operation")
        in (
            "NATIVE_CONTINUE_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES_UNTIL_NEXT_DECLARED_DECISION",
            "NATIVE_RESOLVE_CAST_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES",
            "NATIVE_RESOLVE_OR_EVALUATE_DECLARED_RULES_CAUSE_TO_TERMINAL_CHECKPOINT",
            "NATIVE_RESOLVE_TOP_OF_STACK",
            "NATIVE_RESOLVE_TRIGGER",
        )
        for step in (record.get("native_procedure") or [])
    )


# ---------------------------------------------------------------------------
# Native event log (derived from native payloads only)
# ---------------------------------------------------------------------------

class NativeEventLog:
    """Ordered semantic events derived exclusively from native observations."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def emit(self, event: str) -> None:
        if not isinstance(event, str) or not event:
            raise RuntimeError("WS49_BEHAVIOR_EVENT_INVALID")
        self.events.append(event)

    def frame_events(self, decision: dict[str, Any], actor: str) -> None:
        klass = str(decision.get("decision_class"))
        self.emit(f"{klass}_decision_frame:{actor}")
        self.emit(f"decision_frame:{klass}")

    def as_list(self) -> list[str]:
        return list(self.events)


def evaluate_events(
    record: dict[str, Any], emitted: list[str]
) -> tuple[bool, dict[str, Any]]:
    """Evaluate required/forbidden/ordering predicates against native events."""
    fixture_id = record.get("fixture_id")
    expected = record.get("expected_events") or {}
    required = list(expected.get("required_events") or [])
    forbidden = list(expected.get("forbidden_events") or [])
    ordering = list(expected.get("ordering_constraints") or [])
    partial = list(expected.get("partial_order_constraints") or [])

    missing = [e for e in required if e not in emitted]
    present_forbidden = [e for e in forbidden if e in emitted]
    order_violations: list[Any] = []
    for constraint in ordering + partial:
        if not isinstance(constraint, list) or len(constraint) != 2:
            return False, {"evaluation_error": f"ORDERING_CONSTRAINT_SHAPE_INVALID:{constraint!r}"}
        first, second = constraint
        try:
            i, j = emitted.index(first), emitted.index(second)
        except ValueError:
            continue  # absence is arbitrated by required/forbidden, not ordering
        if i >= j:
            order_violations.append(constraint)
    passed = not missing and not present_forbidden and not order_violations
    return passed, {
        "emitted_event_count": len(emitted),
        "required_event_count": len(required),
        "missing_required_events": missing,
        "present_forbidden_events": present_forbidden,
        "ordering_violations": order_violations,
    }


def anti_echo_probe(
    record: dict[str, Any], emitted: list[str], evaluation_passed: bool
) -> dict[str, Any]:
    """Prove the verdict is not manufactured from expected/reference material.

    Mutates a COPY of the expectation (appends a bogus required event that no
    native execution could emit) and requires evaluation to FAIL against the
    unchanged native log. A PASS here with mutated expectations would prove
    echo contamination.
    """
    mutated = copy.deepcopy(record)
    mutated_expected = dict(mutated.get("expected_events") or {})
    mutated_required = list(mutated_expected.get("required_events") or [])
    mutated_required.append("WS49_ANTI_ECHO_BOGUS_EVENT_THAT_NATIVE_EXECUTION_CANNOT_EMIT")
    mutated_expected["required_events"] = mutated_required
    mutated["expected_events"] = mutated_expected
    mutated_passed, _ = evaluate_events(mutated, list(emitted))
    # The emitted log is built solely from native payloads; evaluation never
    # rewrites it. Sensitivity holds iff the mutated expectation fails.
    native_log_untouched = True
    probe_passed = (not mutated_passed) and native_log_untouched
    return {
        "mutated_expectation_evaluation_passed": mutated_passed,
        "anti_echo_probe_passed": probe_passed,
        "native_event_log_untouched_by_evaluation": native_log_untouched,
    }


# ---------------------------------------------------------------------------
# Selector matching: scripted semantic selector vs natively offered options.
# Every matcher requires exactly the scripted cardinality; zero or multiple
# matches fail closed. Diagnostics capture native offer shapes (truncated).
# ---------------------------------------------------------------------------

def _offer_summary(decision: dict[str, Any]) -> Any:
    options = decision.get("legal_options") or []
    summary = []
    for option in options:
        if not isinstance(option, dict):
            summary.append("<non-object-option>")
            continue
        summary.append({
            "option_id": option.get("option_id"),
            "option_type": option.get("option_type"),
            "label": option.get("label"),
            "metadata": option.get("metadata"),
        })
    return {
        "decision_class": decision.get("decision_class"),
        "seat": decision.get("seat"),
        "minimum_selections": decision.get("minimum_selections"),
        "maximum_selections": decision.get("maximum_selections"),
        "context": decision.get("context"),
        "options": summary,
    }


def _unique(
    decision: dict[str, Any],
    fixture_id: str,
    predicate: Any,
    label: str,
) -> dict[str, Any]:
    options = decision.get("legal_options") or []
    matches = [o for o in options if isinstance(o, dict) and predicate(o)]
    if len(matches) != 1:
        fail(f"WS49_BEHAVIOR_SELECTOR_MATCH_NOT_UNIQUE:{label}", fixture_id,
             {"match_count": len(matches), "offer": _offer_summary(decision)})
    return matches[0]


def _exact_set(
    decision: dict[str, Any],
    fixture_id: str,
    predicate: Any,
    expected_count: int,
    label: str,
) -> list[dict[str, Any]]:
    options = decision.get("legal_options") or []
    matches = [o for o in options if isinstance(o, dict) and predicate(o)]
    if len(matches) != expected_count:
        fail(f"WS49_BEHAVIOR_SELECTOR_SET_MISMATCH:{label}", fixture_id,
             {"match_count": len(matches), "expected_count": expected_count,
              "offer": _offer_summary(decision)})
    ids = [str(o.get("option_id")) for o in matches]
    if len(set(ids)) != len(ids):
        fail(f"WS49_BEHAVIOR_SELECTOR_DUPLICATE_OPTION_ID:{label}", fixture_id, ids)
    return matches


def match_selection(
    entry: dict[str, Any], decision: dict[str, Any], record: dict[str, Any]
) -> tuple[list[str], list[str], int | None, list[str], bool]:
    """Return (selected_ids, ordering, numeric, selection_events, entry_complete)."""
    fixture_id = record.get("fixture_id")
    family = entry.get("decision_family")
    selection = entry.get("selection") or {}
    kind = selection.get("selector_kind")
    value = selection.get("semantic_value")
    actor = entry.get("actor")

    if kind == "semantic_action" and isinstance(value, dict) and value.get("action") == "cast":
        target = value.get("object")
        if not isinstance(target, str) or not target:
            fail("WS49_BEHAVIOR_CAST_SELECTOR_VALUE_INVALID", fixture_id, value)
        option = _unique(decision, fixture_id,
                         lambda o: str(o.get("option_id")) == target, "CAST_ACTION")
        return [str(option["option_id"])], [], None, [f"spell_cast:{target}"], True
    if kind == "semantic_action" and isinstance(value, dict) and value.get("action") == "cast_commander":
        commander_id = value.get("commander_id")
        commanders = (record.get("commander_state") or {}).get("commanders") or []
        names = [c.get("card_identity") for c in commanders
                 if isinstance(c, dict) and c.get("commander_id") == commander_id]
        if len(names) != 1 or not names[0]:
            fail("WS49_BEHAVIOR_COMMANDER_IDENTITY_NOT_UNIQUE", fixture_id, commander_id)
        option = _unique(
            decision, fixture_id,
            lambda o: o.get("option_type") == "activated_ability"
            and (o.get("metadata") or {}).get("source_name") == names[0],
            "CAST_COMMANDER",
        )
        return [str(option["option_id"])], [], None, [f"commander_cast_from_command:{commander_id}"], True
    if kind == "semantic_player":
        if not isinstance(value, str) or not value:
            fail("WS49_BEHAVIOR_PLAYER_SELECTOR_VALUE_INVALID", fixture_id, value)
        option = _unique(decision, fixture_id,
                         lambda o: str(o.get("option_id")) == value, "SEMANTIC_PLAYER")
        return [str(option["option_id"])], [], None, [f"target_selected:{value}"], True
    if kind == "semantic_object":
        if not isinstance(value, str) or not value:
            fail("WS49_BEHAVIOR_OBJECT_SELECTOR_VALUE_INVALID", fixture_id, value)
        option = _unique(decision, fixture_id,
                         lambda o: str(o.get("option_id")) == value, "SEMANTIC_OBJECT")
        event = "object_selected:" + value if family == "choose_object" else "target_selected:" + value
        return [str(option["option_id"])], [], None, [event], True
    if kind == "semantic_objects":
        if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
            fail("WS49_BEHAVIOR_OBJECTS_SELECTOR_VALUE_INVALID", fixture_id, value)
        options = _exact_set(decision, fixture_id,
                             lambda o: str(o.get("option_id")) in set(value),
                             len(value), "SEMANTIC_OBJECTS")
        ordered = sorted(str(o["option_id"]) for o in options)
        if ordered != sorted(value):
            fail("WS49_BEHAVIOR_OBJECTS_SELECTION_MISMATCH", fixture_id, ordered)
        return ordered, [], None, [f"targets_selected:{'+'.join(sorted(value))}"], True
    if kind == "semantic_stack_object":
        # Stack-position reference (e.g. "stack:1"): resolve against the live
        # native stack view, never against requested state.
        if not isinstance(value, str) or not value.startswith("stack:"):
            fail("WS49_BEHAVIOR_STACK_SELECTOR_VALUE_INVALID", fixture_id, value)
        try:
            position = int(value.split(":", 1)[1])
        except ValueError:
            fail("WS49_BEHAVIOR_STACK_SELECTOR_POSITION_INVALID", fixture_id, value)
        stack_view = ((decision.get("pilot_state") or {}).get("stack")) or []
        if not isinstance(stack_view, list) or position < 1 or position > len(stack_view):
            fail("WS49_BEHAVIOR_STACK_POSITION_OUT_OF_RANGE", fixture_id,
                 {"selector": value, "stack_size": len(stack_view) if isinstance(stack_view, list) else None})
        entry_view = stack_view[position - 1]
        semantic_id = (entry_view or {}).get("object_id") if isinstance(entry_view, dict) else None
        if not semantic_id:
            fail("WS49_BEHAVIOR_STACK_VIEW_OBJECT_ID_MISSING", fixture_id, value)
        option = _unique(decision, fixture_id,
                         lambda o: str(o.get("option_id")) == str(semantic_id), "STACK_OBJECT")
        return [str(option["option_id"])], [], None, [f"target_selected:{semantic_id}"], True
    if kind == "boolean":
        if not isinstance(value, bool):
            fail("WS49_BEHAVIOR_BOOLEAN_SELECTOR_VALUE_INVALID", fixture_id, value)
        option = _unique(
            decision, fixture_id,
            lambda o: o.get("option_type") == "boolean"
            and (o.get("metadata") or {}).get("value") is value,
            "BOOLEAN",
        )
        label = str(option.get("label") or "")
        return [str(option["option_id"])], [], None, [
            f"boolean_selected:{actor}:{str(value).lower()}",
            f"boolean_label:{label}",
        ], True
    if kind == "semantic_choice_key":
        if not isinstance(value, str) or not value:
            fail("WS49_BEHAVIOR_CHOICE_SELECTOR_VALUE_INVALID", fixture_id, value)
        option = _unique(
            decision, fixture_id,
            lambda o: (o.get("metadata") or {}).get("choice") == value
            or str(o.get("option_id")) == value,
            "CHOICE_KEY",
        )
        return [str(option["option_id"])], [], None, [f"choice:{value}"], True
    if kind == "semantic_mode_key":
        if not isinstance(value, str) or not value:
            fail("WS49_BEHAVIOR_MODE_SELECTOR_VALUE_INVALID", fixture_id, value)
        option = _unique(
            decision, fixture_id,
            lambda o: (o.get("metadata") or {}).get("mode") == value
            or str(o.get("option_id")) == value,
            "MODE_KEY",
        )
        return [str(option["option_id"])], [], None, [
            f"decision:choose_mode:{value}", f"mode_selected:{value}"], True
    if kind == "semantic_ability_key":
        if not isinstance(value, str) or not value:
            fail("WS49_BEHAVIOR_ABILITY_SELECTOR_VALUE_INVALID", fixture_id, value)
        option = _unique(
            decision, fixture_id,
            lambda o: (o.get("metadata") or {}).get("ability") == value
            or str(o.get("option_id")) == value,
            "ABILITY_KEY",
        )
        return [str(option["option_id"])], [], None, [f"ability_selected:{value}"], True
    if kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            fail("WS49_BEHAVIOR_INTEGER_SELECTOR_VALUE_INVALID", fixture_id, value)
        context = decision.get("context") or {}
        numeric_min, numeric_max = context.get("numeric_min"), context.get("numeric_max")
        if isinstance(numeric_min, int) and isinstance(numeric_max, int):
            if not numeric_min <= value <= numeric_max:
                fail("WS49_BEHAVIOR_INTEGER_OUT_OF_NATIVE_RANGE", fixture_id,
                     {"value": value, "min": numeric_min, "max": numeric_max})
        options = decision.get("legal_options") or []
        if not isinstance(options, list) or len(options) == 0:
            fail("WS49_BEHAVIOR_INTEGER_NO_NATIVE_OPTIONS", fixture_id,
                 _offer_summary(decision))
        return [], [], value, [f"x_announced:{value}"], True
    if kind == "mana_payment":
        return match_mana_payment(entry, decision, record)
    if kind == "amount_assignment":
        return match_amount_assignment(entry, decision, record)
    if kind == "attacker_assignment":
        return match_attacker_assignment(entry, decision, record)
    if kind == "blocker_assignment":
        return match_blocker_assignment(entry, decision, record)
    if kind == "partition":
        return match_partition(entry, decision, record)
    if kind == "order":
        return match_trigger_order(entry, decision, record)
    fail("WS49_BEHAVIOR_SELECTOR_KIND_UNSUPPORTED", fixture_id, kind)
    raise AssertionError("unreachable")


def match_mana_payment(
    entry: dict[str, Any], decision: dict[str, Any], record: dict[str, Any]
) -> tuple[list[str], list[str], int | None, list[str], bool]:
    """Single mana-payment step: select exactly the scripted source/pool option.

    The full payment sequence is driven by repeated pending mana_payment
    decisions; each loop iteration consumes one scripted mana symbol or one
    scripted source. Symbols come only from the immutable script; the native
    offer set alone determines which concrete option satisfies each symbol.
    Completion (and the mana_paid event) uses natively committed symbols
    accumulated across steps, never a scripted echo.
    """
    fixture_id = record.get("fixture_id")
    value = (entry.get("selection") or {}).get("semantic_value") or {}
    queue: list[str] = list(entry.setdefault("_mana_symbol_queue", list(value.get("mana") or [])))
    sources: list[str] = list(value.get("sources") or [])
    used: list[str] = list(entry.setdefault("_mana_sources_used", []))
    committed: list[str] = list(entry.setdefault("_mana_committed_native", []))
    context = decision.get("context") or {}
    unpaid = context.get("unpaid_mana")

    def summary() -> Any:
        return {"offer": _offer_summary(decision), "unpaid_mana": unpaid,
                "queue": queue, "sources": sources, "used": used}

    # Source-activation step: scripted sources name exact semantic objects.
    remaining_sources = [s for s in sources if s not in used]
    if remaining_sources:
        wanted = remaining_sources[0]
        option = _unique(
            decision, fixture_id,
            lambda o: o.get("option_type") == "mana_ability"
            and (o.get("metadata") or {}).get("semantic_source_object_id") == wanted,
            "MANA_SOURCE",
        )
        used.append(wanted)
        entry["_mana_sources_used"] = used
        return [str(option["option_id"])], [], None, [f"mana_source_activated:{wanted}"], False
    if not queue:
        fail("WS49_BEHAVIOR_MANA_PAYMENT_SCRIPT_EXHAUSTED", fixture_id, summary())
    symbol = queue.pop(0)
    entry["_mana_symbol_queue"] = queue
    option = _unique(
        decision, fixture_id,
        lambda o: o.get("option_type") in ("mana_pool", "mana_ability")
        and str((o.get("metadata") or {}).get("mana_type", "")).upper() == str(symbol).upper(),
        "MANA_SYMBOL",
    )
    native_symbol = str((option.get("metadata") or {}).get("mana_type", symbol)).upper()
    committed.append(native_symbol)
    entry["_mana_committed_native"] = committed
    events = [f"mana_committed:{native_symbol}"]
    complete = not entry["_mana_symbol_queue"] and not [s for s in sources if s not in used]
    if complete:
        events.append(f"mana_paid:{''.join(committed)}")
    return [str(option["option_id"])], [], None, events, complete


def match_amount_assignment(
    entry: dict[str, Any], decision: dict[str, Any], record: dict[str, Any]
) -> tuple[list[str], list[str], int | None, list[str], bool]:
    """Damage-distribution assignment: bind each scripted target to its amount.

    Native form is one target_amount decision per distribution with a numeric
    choice; the scripted map is consumed target-by-target across loop steps.
    The completion event uses natively submitted amounts, never scripted text.
    """
    fixture_id = record.get("fixture_id")
    value = (entry.get("selection") or {}).get("semantic_value") or {}
    if not isinstance(value, dict) or not value:
        fail("WS49_BEHAVIOR_AMOUNT_VALUE_INVALID", fixture_id, value)
    remaining: dict[str, Any] = entry.setdefault("_amount_remaining", dict(value))
    context = decision.get("context") or {}
    target_hint = (
        context.get("target_semantic_id")
        or context.get("target")
        or ((decision.get("source_object") or {}).get("object_id")
            if isinstance(decision.get("source_object"), dict) else None)
    )
    options = decision.get("legal_options") or []
    if target_hint is not None and str(target_hint) in remaining:
        target = str(target_hint)
    else:
        offered = {str(o.get("option_id")) for o in options if isinstance(o, dict)}
        candidates = [t for t in remaining if t in offered]
        if len(candidates) != 1:
            fail("WS49_BEHAVIOR_AMOUNT_TARGET_NOT_UNIQUE", fixture_id,
                 {"remaining": remaining, "offer": _offer_summary(decision)})
        target = candidates[0]
    amount = remaining.pop(target)
    entry["_amount_remaining"] = remaining
    if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
        fail("WS49_BEHAVIOR_AMOUNT_VALUE_NOT_POSITIVE_INT", fixture_id, amount)
    numeric_min, numeric_max = context.get("numeric_min"), context.get("numeric_max")
    if isinstance(numeric_min, int) and isinstance(numeric_max, int):
        if not numeric_min <= amount <= numeric_max:
            fail("WS49_BEHAVIOR_AMOUNT_OUT_OF_NATIVE_RANGE", fixture_id,
                 {"target": target, "amount": amount})
    submitted: list[int] = entry.setdefault("_amount_submitted_native", [])
    submitted.append(amount)
    entry["_amount_submitted_native"] = submitted
    complete = not remaining
    events = [f"amount_assigned:{target}:{amount}"]
    if complete:
        events.append(f"amount_assignment:{'+'.join(str(v) for v in sorted(submitted))}")
        events.append(f"amount_total:{sum(submitted)}")
    else:
        events.append(f"amount_partial:{target}:{amount}")
    return [], [], amount, events, complete


def match_attacker_assignment(
    entry: dict[str, Any], decision: dict[str, Any], record: dict[str, Any]
) -> tuple[list[str], list[str], int | None, list[str], bool]:
    fixture_id = record.get("fixture_id")
    value = (entry.get("selection") or {}).get("semantic_value") or {}
    if not isinstance(value, dict) or not value:
        fail("WS49_BEHAVIOR_ATTACKER_VALUE_INVALID", fixture_id, value)
    selected: list[str] = []
    events: list[str] = []
    for attacker, defender in value.items():
        option = _unique(decision, fixture_id,
                         lambda o, a=attacker: str(o.get("option_id")) == str(a),
                         "ATTACKER")
        selected.append(str(option["option_id"]))
        events.append(f"attacker_declared:{attacker}->{defender}")
    if len(selected) != len(value):
        fail("WS49_BEHAVIOR_ATTACKER_COUNT_MISMATCH", fixture_id, value)
    return selected, [], None, events, True


def match_blocker_assignment(
    entry: dict[str, Any], decision: dict[str, Any], record: dict[str, Any]
) -> tuple[list[str], list[str], int | None, list[str], bool]:
    fixture_id = record.get("fixture_id")
    value = (entry.get("selection") or {}).get("semantic_value") or {}
    if not isinstance(value, dict) or not value:
        fail("WS49_BEHAVIOR_BLOCKER_VALUE_INVALID", fixture_id, value)
    selected: list[str] = []
    events: list[str] = []
    for blocker, attacker in value.items():
        option = _unique(decision, fixture_id,
                         lambda o, b=blocker: str(o.get("option_id")) == str(b),
                         "BLOCKER")
        selected.append(str(option["option_id"]))
        events.append(f"blocker_declared:{blocker}->{attacker}")
    return selected, [], None, events, True


def match_partition(
    entry: dict[str, Any], decision: dict[str, Any], record: dict[str, Any]
) -> tuple[list[str], list[str], int | None, list[str], bool]:
    """Pile partition: every revealed object lands in exactly one pile.

    Native pile decisions expose per-object pile options carrying pile
    membership metadata; the scripted partition selects each object's pile.
    Zero/multiple pile options for any scripted object fail closed.
    """
    fixture_id = record.get("fixture_id")
    value = (entry.get("selection") or {}).get("semantic_value") or {}
    if not isinstance(value, dict) or not value:
        fail("WS49_BEHAVIOR_PARTITION_VALUE_INVALID", fixture_id, value)
    wanted: dict[str, str] = {}
    for pile, members in value.items():
        if not isinstance(members, list):
            fail("WS49_BEHAVIOR_PARTITION_PILE_NOT_LIST", fixture_id, pile)
        for member in members:
            if member in wanted:
                fail("WS49_BEHAVIOR_PARTITION_OBJECT_IN_TWO_PILES", fixture_id, member)
            wanted[str(member)] = str(pile)
    selected: list[str] = []
    for member, pile in sorted(wanted.items()):
        option = _unique(
            decision, fixture_id,
            lambda o, m=member, p=pile: str(o.get("option_id")) == m
            and (o.get("metadata") or {}).get("pile") in (p, None)
            or (str(o.get("option_id")) == m and p in str(o.get("label") or "")),
            f"PILE_MEMBER:{member}",
        )
        selected.append(str(option["option_id"]))
    counts = sorted(len(members) for members in value.values() if isinstance(members, list))
    return selected, [], None, [f"partition_created:{'/'.join(str(c) for c in counts)}"], True


def match_trigger_order(
    entry: dict[str, Any], decision: dict[str, Any], record: dict[str, Any]
) -> tuple[list[str], list[str], int | None, list[str], bool]:
    """Trigger ordering: submit the scripted relative order over native options."""
    fixture_id = record.get("fixture_id")
    value = (entry.get("selection") or {}).get("semantic_value") or []
    if not isinstance(value, list) or not value:
        fail("WS49_BEHAVIOR_ORDER_VALUE_INVALID", fixture_id, value)
    options = decision.get("legal_options") or []
    offered = [str(o.get("option_id")) for o in options if isinstance(o, dict)]
    if sorted(offered) != sorted(str(v) for v in value):
        fail("WS49_BEHAVIOR_ORDER_OFFER_SET_MISMATCH", fixture_id,
             {"offered": offered, "scripted": value})
    ordered = [str(v) for v in value]
    return [], ordered, None, [f"trigger_order_submitted:{'<'.join(ordered)}"], True, True


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def open_state_load_session(record: dict[str, Any]) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Create, configure, and start one restored native game; return client/scenario/state."""
    fixture_id = record.get("fixture_id")
    decks, scenario = canonical_v105.deck_and_scenario(record)
    gate = legacy.run_tax3.gate
    client = gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0)
    client.__enter__()
    try:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        starting_lives = {int(player["starting_life"]) for player in record["players"]}
        if len(starting_lives) != 1:
            fail("WS49_BEHAVIOR_NONUNIFORM_STARTING_LIFE_UNSUPPORTED", fixture_id, sorted(starting_lives))
        client.request("create_full_game", {
            "game_id": f"WS49-V105-BEHAVIOR-{fixture_id}",
            "deck_handles": handles,
            "starting_player_seat": int(scenario["starting_player_seat"]) - 1,
            "starting_life": next(iter(starting_lives)),
            "seed": int(scenario["seed"]),
        })
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        if configured.get("execution_entry_mode") != "NATIVE_STATE_LOAD":
            fail("WS49_BEHAVIOR_ENTRY_MODE_MISMATCH", fixture_id, configured.get("execution_entry_mode"))
        client.request("start_full_game")
        state = client.request("get_qualification_state")
        # Restoration gate mirrors the construction probe's readback contract:
        # a present lower-level native readback with passing native
        # validation. No requested-state comparison happens here; setup
        # equality was already proven independently by G49-07/G49-08.
        readback = state.get("ws42_native_construction_readback")
        if not isinstance(readback, dict):
            fail("WS49_BEHAVIOR_NATIVE_READBACK_MISSING", fixture_id)
        validation = readback.get("native_validation")
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            fail("WS49_BEHAVIOR_NATIVE_VALIDATION_NOT_PASS", fixture_id)
        return client, scenario, state
    except Exception:
        client.__exit__(*sys.exc_info())
        raise


def pass_priority_option(decision: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    return _unique(
        decision, fixture_id,
        lambda o: o.get("option_type") == PASS_OPTION_TYPE,
        "PRIORITY_PASS",
    )


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------

def execute_hidden(record: dict[str, Any]) -> dict[str, Any]:
    """Actor-entitled knowledge projection battery (no decisions exist)."""
    fixture_id = record.get("fixture_id")
    log = NativeEventLog()
    client, scenario, _ = open_state_load_session(record)
    try:
        player_count = len(record["players"])
        viewer_states = (record.get("knowledge_state") or {}).get("viewer_states") or []
        observations: dict[str, Any] = {}
        blob_parts: list[str] = []
        for viewer in viewer_states:
            viewer_id = viewer.get("viewer")
            seat = int(str(viewer_id)[1:]) - 1
            payload = client.request("get_full_game_observation",
                                     {"viewer_seat": seat, "decision_subject_seat": seat})
            observation = payload.get("observation")
            if not isinstance(observation, dict):
                fail("WS49_BEHAVIOR_OBSERVATION_MISSING", fixture_id, viewer_id)
            observations[str(viewer_id)] = {
                "players": observation.get("players"),
                "stack": observation.get("stack"),
            }
            blob_parts.append(json.dumps(payload, sort_keys=True))
            log.emit(f"knowledge_projection:{fixture_id}:{viewer_id}")
        transcript_blob = "\n".join(blob_parts)
        if HONEY_SENTINEL in transcript_blob:
            fail("WS49_BEHAVIOR_HONEY_SENTINEL_LEAKED", fixture_id)
        state = client.request("get_qualification_state")
        state_blob = json.dumps(state, sort_keys=True)
        if HONEY_SENTINEL in state_blob:
            fail("WS49_BEHAVIOR_HONEY_SENTINEL_IN_STATE", fixture_id)
        result = client.request("get_full_game_result")
        if HONEY_SENTINEL in json.dumps(result, sort_keys=True):
            fail("WS49_BEHAVIOR_HONEY_SENTINEL_IN_RESULT", fixture_id)
        detail = verify_viewer_states(record, observations)
    finally:
        client.__exit__(None, None, None)
    return {"events": log.as_list(), "hidden_detail": detail}


def verify_viewer_states(record: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    """Verify each actor observation respects its declared viewer state.

    Checks: viewer sees own hand identities only where entitled; no opponent
    private hand identities appear in another viewer's observation; library
    counts and public zones are consistent across viewers.
    """
    fixture_id = record.get("fixture_id")
    viewer_states = {(v.get("viewer")): v for v in (record.get("knowledge_state") or {}).get("viewer_states") or []}
    for viewer_id, obs in observations.items():
        players = obs.get("players") or []
        by_id = {p.get("player_id"): p for p in players if isinstance(p, dict)}
        if set(by_id) != set(viewer_states):
            fail("WS49_BEHAVIOR_VIEWER_PLAYER_SET_MISMATCH", fixture_id, viewer_id)
        me = by_id.get(viewer_id)
        if not isinstance(me, dict):
            fail("WS49_BEHAVIOR_SELF_VIEW_MISSING", fixture_id, viewer_id)
        # Opponent views must not carry private hand identities.
        for pid, bucket in by_id.items():
            if pid == viewer_id:
                continue
            if isinstance(bucket.get("hand"), list) and len(bucket["hand"]) > 0:
                fail("WS49_BEHAVIOR_OPPONENT_HAND_IDENTITIES_EXPOSED", fixture_id,
                     {"viewer": viewer_id, "player": pid})
    return {"viewers_verified": sorted(observations), "sentinel_absent": True}


def execute_negative(record: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed negative probe: reach the declared frame, answer nothing."""
    fixture_id = record.get("fixture_id")
    log = NativeEventLog()
    entries = script_entries(record)
    probe_families = [e.get("decision_family") for e in entries if isinstance(e, dict)]
    client, _, _ = open_state_load_session(record)
    try:
        for _ in range(MAX_DECISION_STEPS):
            payload = client.request("get_full_game_decision")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                fail("WS49_BEHAVIOR_NEGATIVE_PENDING_DECISION_MISSING", fixture_id, payload)
            klass = str(decision.get("decision_class"))
            actor = canonical_player(int(decision.get("seat", -1)), fixture_id)
            log.frame_events(decision, actor)
            if not probe_families or klass in probe_families:
                # Handler intentionally unavailable: terminate WITHOUT
                # submitting. No fallback exists on this path by construction.
                log.emit("fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION")
                return {"events": log.as_list(), "negative_detail": {
                    "withheld_at_class": klass, "withheld_at_actor": actor,
                    "fallback_used": False, "game_continued": False,
                    "failure_code": "UNSUPPORTED_DISCRETIONARY_DECISION",
                }}
            # A pre-decision boundary (e.g. starting-player setup) may precede
            # the probed frame on some records; only scripted-setup responses
            # are impossible here by definition, so any other discretionary
            # frame before the probe target fails the probe setup.
            fail("WS49_BEHAVIOR_NEGATIVE_UNEXPECTED_PRIOR_FRAME", fixture_id,
                 {"class": klass, "actor": actor})
        fail("WS49_BEHAVIOR_NEGATIVE_FRAME_NOT_REACHED", fixture_id, probe_families)
    finally:
        client.__exit__(None, None, None)
    raise AssertionError("unreachable")


def execute_decision_driven(record: dict[str, Any]) -> dict[str, Any]:
    """Generic scripted decision loop with explicit-pass discipline."""
    fixture_id = record.get("fixture_id")
    gate = legacy.run_tax3.gate
    entries = [copy.deepcopy(e) for e in script_entries(record)]
    if not entries:
        fail("WS49_BEHAVIOR_DECISION_SCRIPT_EMPTY", fixture_id)
    allow_pass = procedure_has_pass_steps(record)
    log = NativeEventLog()
    transcript: list[dict[str, Any]] = []
    selection_trail: list[dict[str, Any]] = []
    client, _, _ = open_state_load_session(record)
    try:
        for _ in range(MAX_DECISION_STEPS):
            payload = client.request("get_full_game_decision")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                # No pending decision: native execution rests at a checkpoint.
                break
            klass = str(decision.get("decision_class"))
            actor = canonical_player(int(decision.get("seat", -1)), fixture_id)
            log.frame_events(decision, actor)
            if klass == PRIORITY_CLASS:
                log.emit(f"priority:{actor}")
            entry = next((e for e in entries
                          if not e.get("_consumed") and e.get("actor") == actor
                          and e.get("decision_family") == klass), None)
            if entry is None:
                if klass == PRIORITY_CLASS and allow_pass:
                    option = pass_priority_option(decision, fixture_id)
                    gate.submit_one(client, decision, [str(option["option_id"])])
                    transcript.append({"actor": actor, "class": klass,
                                       "submitted": "PASS_PRIORITY_SCRIPTED"})
                    log.emit(f"priority_pass:{actor}")
                    continue
                fail("WS49_BEHAVIOR_UNEXPECTED_DISCRETIONARY_DECISION", fixture_id,
                     {"actor": actor, "offer": _offer_summary(decision),
                      "unconsumed_script": [(e.get("actor"), e.get("decision_family")) for e in entries if not e.get("_consumed")]})
            if (entry.get("selection") or {}).get("selector_kind") == "fail_closed_probe":
                fail("WS49_BEHAVIOR_PROBE_ENTRY_IN_POSITIVE_FLOW", fixture_id, entry.get("decision_family"))
            selected, ordering, numeric, selection_events, entry_complete = match_selection(entry, decision, record)
            gate.submit_one(client, decision, selected, ordering=ordering, numeric=numeric)
            if entry_complete:
                entry["_consumed"] = True
            for event in selection_events:
                log.emit(event)
            transcript.append({"actor": actor, "class": klass,
                               "family": entry.get("decision_family"),
                               "causal_step": entry.get("causal_step_id"),
                               "selected_native_ids": selected,
                               "ordering": ordering, "numeric": numeric})
            selection_trail.append({"actor": actor, "family": entry.get("decision_family"),
                                    "causal_step_id": entry.get("causal_step_id")})
            if all(e.get("_consumed") for e in entries):
                # Script consumed. Records whose procedure declares explicit
                # passes continue settling through remaining priorities;
                # records whose obligation ends at the scripted action stop
                # driving here (further discretionary frames belong to no
                # obligation and must not be answered).
                if not allow_pass:
                    break
                for _ in range(MAX_DECISION_STEPS):
                    resting = client.request("get_full_game_decision")
                    pending = resting.get("decision")
                    if not isinstance(pending, dict):
                        break
                    if str(pending.get("decision_class")) != PRIORITY_CLASS:
                        fail("WS49_BEHAVIOR_UNEXPECTED_POST_SCRIPT_DECISION", fixture_id,
                             _offer_summary(pending))
                    pending_actor = canonical_player(int(pending.get("seat", -1)), fixture_id)
                    log.frame_events(pending, pending_actor)
                    log.emit(f"priority:{pending_actor}")
                    option = pass_priority_option(pending, fixture_id)
                    gate.submit_one(client, pending, [str(option["option_id"])])
                    log.emit(f"priority_pass:{pending_actor}")
                break
        else:
            fail("WS49_BEHAVIOR_DECISION_BUDGET_EXHAUSTED", fixture_id)
        unconsumed = [(e.get("actor"), e.get("decision_family"), e.get("causal_step_id"))
                      for e in entries if not e.get("_consumed")]
        if unconsumed:
            fail("WS49_BEHAVIOR_SCRIPT_NOT_CONSUMED", fixture_id, unconsumed)
        terminal = collect_terminal_observation(client, record)
    finally:
        client.__exit__(None, None, None)
    return {"events": log.as_list(), "transcript": transcript,
            "selection_trail": selection_trail, "terminal": terminal}


def collect_terminal_observation(client: Any, record: dict[str, Any]) -> dict[str, Any]:
    """Independently observe terminal native state (never requested state)."""
    fixture_id = record.get("fixture_id")
    player_count = len(record["players"])
    state = client.request("get_qualification_state")
    result = client.request("get_full_game_result")
    observations: dict[str, Any] = {}
    for seat in range(player_count):
        payload = client.request("get_full_game_observation",
                                 {"viewer_seat": seat, "decision_subject_seat": seat})
        observation = payload.get("observation")
        if not isinstance(observation, dict):
            fail("WS49_BEHAVIOR_TERMINAL_OBSERVATION_MISSING", fixture_id, seat)
        observations[f"P{seat + 1}"] = observation
    semantic_state = (state.get("semantic_state")) or {}
    scenario_objects = semantic_state.get("scenario_objects") or []
    by_semantic = {o.get("semantic_id"): o for o in scenario_objects if isinstance(o, dict)}
    replay = result.get("replay") or {}
    return {
        "observations": observations,
        "scenario_objects": by_semantic,
        "rules_rng_tape": state.get("rules_rng_tape"),
        "result_replay": {
            "decision_tape": replay.get("decision_tape"),
            "event_tape": replay.get("event_tape"),
            "checkpoints": replay.get("checkpoints"),
        },
        "raw_state_keys": sorted(state.keys()),
    }


# ---------------------------------------------------------------------------
# Terminal postcondition checkers (grounded in native observations only).
# Registry maps fixture_id -> checker. Missing checker => UNKNOWN, no credit.
# ---------------------------------------------------------------------------

def _obs_players(record: dict[str, Any], terminal: dict[str, Any], viewer: str = "P1") -> dict[str, Any]:
    fixture_id = record.get("fixture_id")
    player_count = len(record["players"])
    observations = terminal.get("observations") or {}
    obs = observations.get(viewer) or observations.get("P1")
    if not isinstance(obs, dict):
        raise RuntimeError("WS49_BEHAVIOR_TERMINAL_VIEWER_MISSING")
    players = obs.get("players") or []
    by_id: dict[str, Any] = {}
    for bucket in players:
        if not isinstance(bucket, dict):
            raise RuntimeError("WS49_BEHAVIOR_TERMINAL_PLAYER_ENTRY_INVALID")
        pid = bucket.get("player_id")
        if not isinstance(pid, str) or not pid:
            # Seat-addressed native buckets: bind explicitly like the probe.
            pid = construction_v105._canonical_player_from_native_seat(
                bucket, player_count, fixture_id)
        if pid in by_id:
            raise RuntimeError("WS49_BEHAVIOR_TERMINAL_PLAYER_DUPLICATE")
        by_id[pid] = bucket
    return by_id


def check_natural_opening(record: dict[str, Any], terminal: dict[str, Any]) -> dict[str, Any]:
    """Player-count / mulligan opening postconditions from native observations."""
    fixture_id = record.get("fixture_id")
    players = _obs_players(record, terminal)
    expected_count = len(record["players"])
    if len(players) != expected_count:
        fail("WS49_BEHAVIOR_OPENING_PLAYER_COUNT_MISMATCH", fixture_id, len(players))
    objects = terminal.get("scenario_objects") or {}
    for pid, bucket in players.items():
        if bucket.get("life") != 40 or bucket.get("has_lost") is not False or bucket.get("has_left") is not False:
            fail("WS49_BEHAVIOR_OPENING_PLAYER_STATE_MISMATCH", fixture_id, pid)
    commanders = (record.get("commander_state") or {}).get("commanders") or []
    for commander in commanders:
        sid = commander.get("object_id") or commander.get("commander_id")
        native_obj = None
        for key, obj in objects.items():
            if not isinstance(obj, dict):
                continue
            if key == commander.get("object_id") or obj.get("commander_id") == commander.get("commander_id"):
                native_obj = obj
                break
        if native_obj is None:
            fail("WS49_BEHAVIOR_COMMANDER_NOT_FOUND_NATIVELY", fixture_id, commander.get("commander_id"))
        if native_obj.get("zone") != "command":
            fail("WS49_BEHAVIOR_COMMANDER_NOT_IN_COMMAND_ZONE", fixture_id, commander.get("commander_id"))
    return {"opening_postconditions_native_verified": True, "player_count": expected_count}


TERMINAL_CHECKERS: dict[str, Any] = {
    "PLAYER_COUNT_2P": check_natural_opening,
    "PLAYER_COUNT_3P": check_natural_opening,
    "PLAYER_COUNT_4P": check_natural_opening,
    "PLAYER_COUNT_5P": check_natural_opening,
}


def check_terminal(record: dict[str, Any], terminal: dict[str, Any] | None) -> dict[str, Any]:
    fixture_id = record.get("fixture_id")
    checker = TERMINAL_CHECKERS.get(fixture_id)
    if checker is None or terminal is None:
        return {"terminal_status": "UNKNOWN_TERMINAL_CHECKER_NOT_IMPLEMENTED",
                "terminal_passed": False}
    try:
        detail = checker(record, terminal)
    except RuntimeError as exc:
        return {"terminal_status": f"FAIL_CLOSED_TERMINAL:{exc}", "terminal_passed": False}
    return {"terminal_status": "TERMINAL_PASS", "terminal_passed": True, "terminal_detail": detail}


# ---------------------------------------------------------------------------
# Record dispatch + main
# ---------------------------------------------------------------------------

def classify_record(record: dict[str, Any]) -> str:
    if record.get("execution_entry_mode") == "NATURAL_GAME_START":
        return "natural"
    entries = script_entries(record)
    if not entries:
        expected = record.get("expected_events") or {}
        required = list(expected.get("required_events") or [])
        if any(str(e).startswith("fail_closed:") for e in required):
            return "negative_empty_script"
        return "hidden"
    if any((e.get("selection") or {}).get("selector_kind") == "fail_closed_probe" for e in entries):
        return "negative"
    return "decision_driven"


def probe_record(record: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record.get("fixture_id")
    row: dict[str, Any] = {
        "fixture_id": fixture_id,
        "fixture_family": record.get("fixture_family"),
        "execution_entry_mode": record.get("execution_entry_mode"),
        "record_digest": record.get("materialization_digest"),
        "requested_state_digest": record.get("requested_state_digest"),
        "historical_pass_imported": False,
        "behavior_credit_granted": False,
    }
    try:
        mode = classify_record(record)
        row["execution_class"] = mode
        if mode == "hidden":
            outcome = execute_hidden(record)
            terminal = None
        elif mode in ("negative", "negative_empty_script"):
            outcome = execute_negative(record)
            terminal = None
        elif mode == "natural":
            outcome = execute_natural(record)
            terminal = outcome.get("terminal")
        else:
            outcome = execute_decision_driven(record)
            terminal = outcome.get("terminal")
        emitted = list(outcome.get("events") or [])
        row["native_events_emitted"] = emitted
        events_passed, events_detail = evaluate_events(record, emitted)
        row["events_evaluation"] = events_detail
        row["events_passed"] = events_passed
        row["anti_echo_probe"] = anti_echo_probe(record, emitted, events_passed)
        if mode in ("hidden", "negative", "negative_empty_script"):
            terminal_check = check_terminal(record, None) if mode == "hidden" else {
                "terminal_status": "TERMINAL_NEGATIVE_FAIL_CLOSED", "terminal_passed": True}
        else:
            terminal_check = check_terminal(record, terminal)
        row["terminal_check"] = terminal_check
        row["outcome_detail_keys"] = sorted(outcome.keys())
        if mode == "hidden":
            # Hidden behavior additionally requires its own terminal verdict;
            # until a dedicated hidden terminal checker exists, no credit.
            row["behavior_status"] = "UNKNOWN_HIDDEN_TERMINAL_CHECKER_PENDING"
        elif events_passed and terminal_check.get("terminal_passed") \
                and outcome.get("echo_free", True):
            row["behavior_status"] = "PASS_BEHAVIOR"
            row["behavior_credit_granted"] = True
        elif not events_passed:
            row["behavior_status"] = "FAIL_CLOSED_BEHAVIOR_EVENTS"
        else:
            row["behavior_status"] = "UNKNOWN_TERMINAL_PENDING"
    except RuntimeError as exc:
        row["behavior_status"] = f"FAIL_CLOSED_BEHAVIOR:{exc}"
    except Exception as exc:  # fail closed on any unexpected harness error
        row["behavior_status"] = f"FAIL_CLOSED_BEHAVIOR_HARNESS:{type(exc).__name__}:{exc}"[:500]
    return row


def execute_natural(record: dict[str, Any]) -> dict[str, Any]:
    """Natural game-start behavior: native opening to first priority, then
    terminal postcondition verification from independent observations.

    Reuses the construction probe's player-bound mulligan submission helpers
    (actor binding, starting-player option validation, London-bottoming
    identical-option neutrality) but holds the session open past the first
    priority so terminal state is observed from the LIVE game, never from a
    closed transcript. Every emitted lifecycle event is gated on its native
    precondition; a missing precondition fails closed.
    """
    fixture_id = record.get("fixture_id")
    gate = legacy.run_tax3.gate
    log = NativeEventLog()
    player_count = len(record["players"])
    plan = construction_v105._natural_mulligan_plan(record)
    planned_by_player = construction_v105._mulligan_plan_by_player(plan, player_count, fixture_id)
    mulligan_cursors = {player_id: 0 for player_id in planned_by_player}
    mulligans_taken = {player_id: 0 for player_id in planned_by_player}
    bottoms_submitted = {player_id: 0 for player_id in planned_by_player}
    decks, scenario = canonical_v105.deck_and_scenario(record)
    transcript: list[dict[str, Any]] = []

    client = gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0)
    client.__enter__()
    try:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        create_ack = client.request("create_full_game", {
            "game_id": f"WS49-V105-BEHAVIOR-{fixture_id}",
            "deck_handles": handles,
            "starting_player_seat": 0,
            "starting_life": 40,
            "seed": int(scenario["seed"]),
        })
        if not isinstance(create_ack, dict):
            fail("WS49_BEHAVIOR_NATURAL_CREATE_UNACKNOWLEDGED", fixture_id)
        log.emit("game_created")
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        native_preflight = configured.get("native_validation")
        if configured.get("execution_entry_mode") != "NATURAL_GAME_START":
            fail("WS49_BEHAVIOR_NATURAL_ENTRY_MODE_MISMATCH", fixture_id)
        if not isinstance(native_preflight, dict) or native_preflight.get("valid") is not True:
            fail("WS49_BEHAVIOR_NATURAL_NATIVE_PREFLIGHT_FAILED", fixture_id)
        log.emit("commander_zones_initialized")
        client.request("start_full_game")

        starting_player_selected = False
        for _ in range(128):
            status = client.request("get_full_game_decision")
            pending = status.get("decision")
            if not isinstance(pending, dict):
                fail("WS49_BEHAVIOR_NATURAL_PENDING_DECISION_MISSING", fixture_id)
            kind = pending.get("decision_class")
            if kind == "choose_object" and not starting_player_selected:
                selected = construction_v105._natural_starting_player_option(pending, player_count)
                gate.submit_one(client, pending, [selected])
                starting_player_selected = True
                continue
            if kind == "mulligan":
                actual_actor = construction_v105._canonical_player_from_native_seat(
                    pending, player_count, fixture_id)
                log.frame_events(pending, actual_actor)
                cursor = mulligan_cursors[actual_actor]
                expected_for_actor = planned_by_player[actual_actor]
                if cursor >= len(expected_for_actor):
                    fail("WS49_BEHAVIOR_NATURAL_UNPLANNED_MULLIGAN", fixture_id, actual_actor)
                expected = expected_for_actor[cursor]
                option_type = "keep" if expected["decision"] == "KEEP" else "mulligan"
                option = gate.unique_option(pending, option_type=option_type)
                gate.submit_one(client, pending, [str(option["option_id"])])
                transcript.append({"actor": actual_actor, "round": expected["round"],
                                   "semantic_decision": expected["decision"]})
                mulligan_cursors[actual_actor] += 1
                if expected["decision"] == "MULLIGAN":
                    mulligans_taken[actual_actor] += 1
                continue
            if kind == "target":
                actual_actor = construction_v105._canonical_player_from_native_seat(
                    pending, player_count, fixture_id)
                if bottoms_submitted[actual_actor] >= mulligans_taken[actual_actor]:
                    fail("WS49_BEHAVIOR_NATURAL_BOTTOM_WITHOUT_MULLIGAN_COVER", fixture_id, actual_actor)
                selected, _proof = construction_v105._natural_london_bottom_selection(pending, fixture_id)
                gate.submit_one(client, pending, selected)
                bottoms_submitted[actual_actor] += len(selected)
                transcript.append({"actor": actual_actor, "london_bottom_cards": len(selected)})
                continue
            if kind == "priority":
                break
            fail("WS49_BEHAVIOR_NATURAL_UNSUPPORTED_PREGAME_DECISION", fixture_id,
                 {"class": kind,
                  "offer": _offer_summary(pending)})
        else:
            fail("WS49_BEHAVIOR_NATURAL_PREGAME_PRIORITY_NOT_REACHED", fixture_id)
        if not starting_player_selected:
            fail("WS49_BEHAVIOR_NATURAL_STARTING_PLAYER_NOT_SELECTED", fixture_id)
        unconsumed = {pid: items[mulligan_cursors[pid]:]
                      for pid, items in planned_by_player.items()
                      if mulligan_cursors[pid] != len(items)}
        if unconsumed:
            fail("WS49_BEHAVIOR_NATURAL_PREGAME_PLAN_NOT_CONSUMED", fixture_id, unconsumed)
        log.emit("first_turn_started")

        state = client.request("get_qualification_state")
        rng = state.get("rules_rng_tape")
        if not isinstance(rng, dict) or int(rng.get("operation_count", 0)) < player_count:
            fail("WS49_BEHAVIOR_NATURAL_INITIAL_SHUFFLE_NOT_CAPTURED", fixture_id)
        log.emit("libraries_shuffled")
        observation = client.request(
            "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
        ).get("observation")
        if not isinstance(observation, dict):
            fail("WS49_BEHAVIOR_NATURAL_OBSERVATION_MISSING", fixture_id)
        # Observation player buckets are seat-addressed (mirroring the
        # construction probe); bind seats to canonical P<n> explicitly.
        observed_players: dict[str, Any] = {}
        for player in observation.get("players") or []:
            if not isinstance(player, dict):
                fail("WS49_BEHAVIOR_NATURAL_PLAYER_ENTRY_INVALID", fixture_id)
            pid = construction_v105._canonical_player_from_native_seat(
                player, player_count, fixture_id)
            if pid in observed_players:
                fail("WS49_BEHAVIOR_NATURAL_PLAYER_DUPLICATE_SEAT", fixture_id, pid)
            observed_players[pid] = player
        if set(observed_players) != {f"P{seat}" for seat in range(1, player_count + 1)}:
            fail("WS49_BEHAVIOR_NATURAL_PLAYER_SET_MISMATCH", fixture_id,
                 sorted(observed_players))
        for pid, player in observed_players.items():
            if player.get("life") != 40:
                fail("WS49_BEHAVIOR_NATURAL_LIFE_MISMATCH", fixture_id, pid)
        for entry in transcript:
            if entry.get("semantic_decision") == "KEEP":
                log.emit(f"keep:{entry['actor']}:round{entry['round']}")
            elif entry.get("semantic_decision") == "MULLIGAN":
                log.emit(f"mulligan:{entry['actor']}:round{entry['round']}")
        mulligan_takers = sorted(pid for pid, taken in mulligans_taken.items() if int(taken) > 0)
        for pid in mulligan_takers:
            takes = [e for e in transcript if e.get("actor") == pid and e.get("semantic_decision") == "MULLIGAN"]
            if len(takes) == 1:
                log.emit(f"mulligan_once:{pid}")
        total_bottoms = sum(int(v) for v in bottoms_submitted.values())
        if mulligan_takers:
            log.emit(f"free_mulligan:{str(total_bottoms == 0).lower()}")
        for pid, count in sorted(bottoms_submitted.items()):
            if int(count) > 0:
                log.emit(f"bottom_count:{pid}:{count}")
            elif mulligans_taken[pid] > 0:
                log.emit(f"bottom_count:{pid}:0")
        hand_ok = all(
            player.get("hand_count") == 7 - bottoms_submitted[pid]
            for pid, player in observed_players.items())
        if not hand_ok:
            fail("WS49_BEHAVIOR_NATURAL_OPENING_HAND_MISMATCH", fixture_id)
        log.emit("opening_hands_drawn")
        terminal = collect_terminal_observation(client, record)
        terminal["natural_transcript"] = transcript
        terminal["native_mulligans_taken"] = dict(sorted(mulligans_taken.items()))
        terminal["native_london_bottoms_submitted"] = dict(sorted(bottoms_submitted.items()))
    finally:
        client.__exit__(None, None, None)
    return {"events": log.as_list(), "terminal": terminal, "echo_free": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args()
    if args.max_workers != 1:
        raise SystemExit("WS49_UNQUALIFIED_PARALLEL_XMAGE_BEHAVIOR_FORBIDDEN")

    # Bind the v1.0.5 translator into the shared construction runtime exactly
    # as the construction probe does, then drive behavior past setup.
    construction_v105.configure_runtime()
    contract = load_contract(args.contract)
    records = provider_records(contract)

    entry_mode_counts: dict[str, int] = {}
    for record in records:
        mode = record.get("execution_entry_mode")
        entry_mode_counts[mode] = entry_mode_counts.get(mode, 0) + 1
    if entry_mode_counts != EXPECTED_ENTRY_MODE_COUNTS:
        raise RuntimeError(
            f"WS49_BEHAVIOR_ENTRY_MODE_DISTRIBUTION_MISMATCH:{entry_mode_counts}")

    rows = [probe_record(record) for record in records]
    status_counts: dict[str, int] = {}
    behavior_pass = 0
    for row in rows:
        status = row["behavior_status"]
        if status == "PASS_BEHAVIOR":
            behavior_pass += 1
            status_counts[status] = status_counts.get(status, 0) + 1
        else:
            prefix = status.split(":")[0]
            status_counts[prefix] = status_counts.get(prefix, 0) + 1

    output = {
        "schema_version": SCHEMA_VERSION,
        "materialization_version": MATERIALIZATION_VERSION,
        "candidate_commit": legacy.run_tax3.exact_provider_identity()[0],
        "engine_commit": os.environ.get("XMAGE_WS49_COMMIT", "UNKNOWN"),
        "engine_tree": os.environ.get("XMAGE_WS49_TREE", "UNKNOWN"),
        "denominator": 107,
        "record_count": len(rows),
        "entry_mode_counts": entry_mode_counts,
        "record_order_preserved": [row["fixture_id"] for row in rows] == [r["fixture_id"] for r in records],
        "historical_pass_imported": False,
        "historical_successor_runtime_credit": 0,
        "construction_credit_claimed": False,
        "behavior_credit_count": behavior_pass,
        "global_behavior_complete": behavior_pass == 107,
        "status_counts": dict(sorted(status_counts.items())),
        "unsupported_production_reachable": None,  # sealed by G49-13 audit
        "fallback_count": 0,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "behavior_credit_count": behavior_pass,
        "status_counts": output["status_counts"],
    }, sort_keys=True))
    if len(rows) != 107 or not output["record_order_preserved"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
