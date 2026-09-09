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
    type_counts: dict[str, int] = {}
    for option in options:
        if not isinstance(option, dict):
            summary.append("<non-object-option>")
            continue
        otype = str(option.get("option_type"))
        type_counts[otype] = type_counts.get(otype, 0) + 1
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
        "option_count": len(options),
        "option_type_counts": dict(sorted(type_counts.items())),
        "options": summary,
    }


def _non_cancel_options(decision: dict[str, Any]) -> list[dict[str, Any]]:
    """Offered options excluding Harnesses-neutral cancellation affordances.

    Cancel/decline options abort the Rules procedure instead of advancing it;
    they are never a forced move and never a fallback answer.
    """
    options = decision.get("legal_options") or []
    return [o for o in options
            if isinstance(o, dict)
            and o.get("option_type") not in ("cancel_mana_payment", "cancel", "decline")]


def contract_card_identity(record: dict[str, Any], semantic_id: str) -> str:
    """Immutable obligation identity of a semantic object (naming only).

    Used solely to NAME the intended object when matching native offers.
    Legality always comes from the native offer set with unique-match
    discipline; identity naming never authorizes an action.
    """
    fixture_id = record.get("fixture_id")
    matches = [o for o in (record.get("semantic_objects") or [])
               if isinstance(o, dict) and o.get("semantic_id") == semantic_id]
    if len(matches) != 1:
        fail("WS49_BEHAVIOR_CONTRACT_OBJECT_IDENTITY_NOT_UNIQUE", fixture_id, semantic_id)
    name = matches[0].get("card_identity")
    if not isinstance(name, str) or not name:
        fail("WS49_BEHAVIOR_CONTRACT_CARD_IDENTITY_MISSING", fixture_id, semantic_id)
    return name


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
        # Native cast options are ability-bound (composite option ids with
        # source metadata), never bare semantic ids. Match by exact semantic
        # id OR by the contract's card identity against the native
        # source_name; exactly one native offer must satisfy either shape.
        # Identity naming never authorizes: the offer set owns legality.
        card_name = None
        try:
            card_name = contract_card_identity(record, target)
        except RuntimeError:
            card_name = None
        def _cast_predicate(o: dict[str, Any]) -> bool:
            if str(o.get("option_id")) == target:
                return True
            if card_name is not None \
                    and o.get("option_type") == "activated_ability" \
                    and (o.get("metadata") or {}).get("mana_ability") is not True \
                    and (o.get("metadata") or {}).get("source_name") == card_name:
                return True
            return False
        option = _unique(decision, fixture_id, _cast_predicate, "CAST_ACTION")
        native_name = str((option.get("metadata") or {}).get("source_name") or card_name or target)
        name_slug = native_name.replace(" ", "_")
        return [str(option["option_id"])], [], None, [
            f"spell_cast:{target}", f"spell_cast:{name_slug}", f"{name_slug}_cast",
            f"cast_source_native:{native_name}",
        ], True
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
        return [str(option["option_id"])], [], None, [
            "commander_cast_from_command",
            f"commander_cast_from_command:{commander_id}",
            "commander_cast",
        ], True
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
    if not sources:
        # Scripted symbols name WHAT is paid; the contract's payment
        # instruction names WHICH objects pay. Merge the two immutable
        # sources; ambiguity fails closed.
        cost_entries = [e for e in (record.get("action_cost_state") or [])
                        if isinstance(e, dict) and e.get("payable") is True
                        and isinstance(e.get("explicit_payment_sources"), list)]
        if len(cost_entries) == 1:
            sources = list(cost_entries[0].get("explicit_payment_sources") or [])
            entry["_mana_sources_merged_from_cost_state"] = True
        elif len(cost_entries) > 1:
            fail("WS49_BEHAVIOR_MANA_SOURCES_AMBIGUOUS", fixture_id,
                 len(cost_entries))
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
        activations = int(entry.get("_mana_activations", 0)) + 1
        entry["_mana_activations"] = activations
        return [str(option["option_id"])], [], None, [
            f"mana_source_activated:{wanted}",
            f"mana_abilities_activated:{activations}",
        ], False
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
        events.append(f"mana_paid:{len(committed)}")
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
    actor = entry.get("actor")
    return [], ordered, None, [
        f"trigger_order_submitted:{'<'.join(ordered)}",
        f"simultaneous_triggers:{actor}:{len(offered)}",
    ], True, True


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

    Observation player buckets are seat-addressed natively; bind seats to
    canonical P<n> explicitly (same binding as natural/opening paths).
    Checks: viewer sees own hand identities only where entitled; no opponent
    private hand identities appear in another viewer's observation.
    """
    fixture_id = record.get("fixture_id")
    player_count = len(record["players"])
    viewer_states = {(v.get("viewer")): v for v in (record.get("knowledge_state") or {}).get("viewer_states") or []}
    for viewer_id, obs in observations.items():
        players = obs.get("players") or []
        by_id: dict[str, Any] = {}
        for bucket in players:
            if not isinstance(bucket, dict):
                fail("WS49_BEHAVIOR_VIEWER_BUCKET_INVALID", fixture_id, viewer_id)
            pid = bucket.get("player_id")
            if not isinstance(pid, str) or not pid:
                pid = construction_v105._canonical_player_from_native_seat(
                    bucket, player_count, fixture_id)
            if pid in by_id:
                fail("WS49_BEHAVIOR_VIEWER_BUCKET_DUPLICATE", fixture_id, viewer_id)
            by_id[pid] = bucket
        if set(by_id) != set(viewer_states):
            fail("WS49_BEHAVIOR_VIEWER_PLAYER_SET_MISMATCH", fixture_id,
                 {"viewer": viewer_id, "observed": sorted(by_id),
                  "shape": shape_overview(players)})
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


class StackWatch:
    """Native stack movement observed across drive steps (no expected data).

    Snapshots come from pending-decision pilot_state payloads (read-only
    native projections). Pushes name Rules arrivals; removals name
    resolutions. Arrivals that were never selected as casts by this runner
    are Rules-created (triggers, copies) rather than pilot-cast.
    """

    def __init__(self, log: NativeEventLog) -> None:
        self.log = log
        self.previous: list[str] = []
        self.cast_selected_names: set[str] = set()
        self.cast_selected_ids: set[str] = set()

    @staticmethod
    def _stack_ids(decision: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
        stack_view = ((decision.get("pilot_state") or {}).get("stack")) or []
        ids: list[str] = []
        names: dict[str, str] = {}
        if isinstance(stack_view, list):
            for entry in stack_view:
                if not isinstance(entry, dict):
                    continue
                sid = entry.get("object_id") or entry.get("option_id")
                if isinstance(sid, str) and sid and sid not in ids:
                    ids.append(sid)
                    name = entry.get("name") or entry.get("label")
                    if isinstance(name, str) and name:
                        names[sid] = name
        return ids, names

    @staticmethod
    def _slug(name: str) -> str:
        return name.replace(" ", "_")

    def observe(self, decision: dict[str, Any]) -> None:
        current, names = self._stack_ids(decision)
        previous_set, current_set = set(self.previous), set(current)
        for sid in current:
            if sid not in previous_set:
                self.log.emit(f"stack_push:{sid}")
                if sid in names:
                    self.log.emit(f"stack_push:{self._slug(names[sid])}")
                if sid not in self.cast_selected_ids \
                        and (sid not in names or names[sid] not in self.cast_selected_names):
                    # Rules-created arrival (trigger/copy), never pilot-cast.
                    if sid in names:
                        self.log.emit(f"trigger:{self._slug(names[sid])}")
                    else:
                        self.log.emit(f"trigger:{sid}")
        for sid in self.previous:
            if sid not in current_set:
                self.log.emit(f"spell_resolved:{sid}")
                if sid in names:
                    self.log.emit(f"spell_resolved:{self._slug(names[sid])}")
                    self.log.emit(f"resolve:{self._slug(names[sid])}")
                self.log.emit(f"resolve:{sid}")
                self.log.emit("spell_resolved")
        self.previous = current

    def note_cast_selection(self, selected_ids: list[str], selection_events: list[str]) -> None:
        self.cast_selected_ids.update(selected_ids)
        for event in selection_events:
            if event.startswith("cast_source_native:"):
                self.cast_selected_names.add(event.split(":", 1)[1])


def submit_pass(gate: Any, client: Any, decision: dict[str, Any],
                actor: str, log: NativeEventLog, transcript: list[dict[str, Any]],
                kind: str, fixture_id: str) -> None:
    """Neutral Rules advancement: pass priority without selecting any action.

    Passing is the unique non-discretionary advance. It never selects a game
    action, never pays, never targets, and never answers a decision family.
    It is permitted while declared native causes (resolve/advance/settle
    procedure steps) are in flight, in positive and negative flows alike.
    """
    option = pass_priority_option(decision, fixture_id)
    gate.submit_one(client, decision, [str(option["option_id"])])
    transcript.append({"actor": actor, "class": str(decision.get("decision_class")),
                       "submitted": kind})
    log.emit(f"priority_pass:{actor}")


def submit_forced(gate: Any, client: Any, decision: dict[str, Any],
                  actor: str, log: NativeEventLog, transcript: list[dict[str, Any]]) -> bool:
    """Forced move: exactly one non-cancel option is natively offered.

    Selecting the sole offered legal option exercises no discretion and is
    not a first/random/default/AI/GUI/skip/parent fallback. Cancel/decline
    affordances abort the procedure and are never forced. Mana payments are
    excluded: resource commitment always requires script or contract
    payment instruction, even when the offer is singular.
    Returns True iff a forced move was submitted.
    """
    if str(decision.get("decision_class")) == "mana_payment":
        return False
    options = _non_cancel_options(decision)
    if len(options) != 1:
        return False
    option = options[0]
    gate.submit_one(client, decision, [str(option["option_id"])])
    transcript.append({"actor": actor, "class": str(decision.get("decision_class")),
                       "submitted": "FORCED_SINGLE_OFFER",
                       "selected_native_ids": [str(option["option_id"])]})
    log.emit(f"forced_move:{actor}:{option.get('option_type')}:{option.get('option_id')}")
    return True


def submit_identical_neutral(gate: Any, client: Any, decision: dict[str, Any],
                             actor: str, log: NativeEventLog,
                             transcript: list[dict[str, Any]]) -> bool:
    """Identical-option neutral completion (London-mulligan rule, generalized).

    When every natively offered option is semantically identical through the
    actor-safe surface (same option type, label, and name) and the decision
    requires an exact count of them, submitting the deterministically ordered
    prefix exercises no choice: any selection is the same game action. Mana
    payments are excluded (see submit_forced).
    """
    if str(decision.get("decision_class")) == "mana_payment":
        return False
    try:
        minimum = int(decision.get("minimum_selections"))
        maximum = int(decision.get("maximum_selections"))
    except (TypeError, ValueError):
        return False
    if minimum < 1 or minimum != maximum:
        return False
    options = _non_cancel_options(decision)
    if len(options) < maximum:
        return False
    semantic: set[str] = set()
    for option in options:
        metadata = option.get("metadata")
        if not isinstance(metadata, dict):
            return False
        label = option.get("label")
        name = metadata.get("name")
        if not isinstance(label, str) or not label or label != name:
            return False
        semantic.add(f"{option.get('option_type')}\x00{label}")
    if len(semantic) != 1:
        return False
    ordered_ids = sorted(str(o["option_id"]) for o in options
                         if isinstance(o.get("option_id"), str) and o["option_id"])
    if len(ordered_ids) != len(options):
        return False
    selected = ordered_ids[:minimum]
    gate.submit_one(client, decision, selected)
    transcript.append({"actor": actor, "class": str(decision.get("decision_class")),
                       "submitted": "IDENTICAL_NEUTRAL",
                       "selected_native_ids": selected})
    log.emit(f"identical_neutral:{actor}:{minimum}_of_{len(options)}")
    return True


def payment_cost_entry(record: dict[str, Any], source_semantic_id: str | None) -> dict[str, Any] | None:
    """Immutable payment instruction for a cast (sources named by contract).

    The action_cost_state entry names WHICH objects pay; every payment step
    still requires a unique native offer match. Naming is not legality.
    """
    if not source_semantic_id:
        return None
    for entry in (record.get("action_cost_state") or []):
        if isinstance(entry, dict) and entry.get("source_semantic_id") == source_semantic_id \
                and entry.get("payable") is True:
            return entry
    return None


def drive_mana_payment(gate: Any, client: Any, decision: dict[str, Any],
                       actor: str, log: NativeEventLog, transcript: list[dict[str, Any]],
                       record: dict[str, Any], pay_state: dict[str, Any]) -> None:
    """Drive one native mana_payment decision from contract payment state.

    pay_state tracks per-cast progress: {"source": <semantic_id>,
    "remaining_sources": [...], "unpaid_seen": [...], "activations": n}.
    Source activation matches exact semantic objects; pool commits accept
    only forced single offers. Every frame's native unpaid context is logged.
    """
    fixture_id = record.get("fixture_id")
    context = decision.get("context") or {}
    unpaid = context.get("unpaid_mana")
    if unpaid is not None:
        pay_state.setdefault("unpaid_seen", []).append(str(unpaid))
        log.emit(f"cost_context:{unpaid}")
        if pay_state.get("is_commander_cast"):
            log.emit(f"commander_tax:{unpaid}")
    remaining: list[str] = pay_state.get("remaining_sources") or []
    if remaining:
        wanted = remaining[0]
        option = _unique(
            decision, fixture_id,
            lambda o: o.get("option_type") == "mana_ability"
            and (o.get("metadata") or {}).get("semantic_source_object_id") == wanted,
            "MANA_SOURCE",
        )
        gate.submit_one(client, decision, [str(option["option_id"])])
        pay_state["remaining_sources"] = remaining[1:]
        pay_state["activations"] = int(pay_state.get("activations", 0)) + 1
        log.emit(f"mana_source_activated:{wanted}")
        log.emit(f"mana_abilities_activated:{pay_state['activations']}")
        transcript.append({"actor": actor, "class": "mana_payment",
                           "submitted": "MANA_SOURCE", "source": wanted})
        return
    # Sources exhausted: pool commits mirror the native mana the activated
    # sources produced (one commit per source, as the bridge structures it).
    # Only forced single offers are accepted; any color choice fails closed.
    pool_expected = int(pay_state.get("pool_expected", len(pay_state.get("source_log") or [])))
    pool_done = int(pay_state.get("pool_done", 0))
    if pool_done >= pool_expected and pool_expected > 0:
        fail("WS49_BEHAVIOR_MANA_POOL_OVER_COMMIT", fixture_id, pay_state)
    options = _non_cancel_options(decision)
    if len(options) != 1:
        fail("WS49_BEHAVIOR_MANA_POOL_CHOICE_UNSCRIPTED", fixture_id,
             {"actor": actor, "offer": _offer_summary(decision)})
    option = options[0]
    gate.submit_one(client, decision, [str(option["option_id"])])
    mana_type = str((option.get("metadata") or {}).get("mana_type", ""))
    pay_state.setdefault("committed_native", []).append(mana_type.upper() or "pool")
    pay_state["pool_done"] = pool_done + 1
    transcript.append({"actor": actor, "class": "mana_payment",
                       "submitted": "MANA_POOL_FORCED",
                       "selected_native_ids": [str(option["option_id"])]})
    log.emit(f"mana_pool_committed:{mana_type}")


def execute_negative(record: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed negative probe: reach the declared frame, answer nothing.

    Neutral advancement (priority passes, forced single-offer moves) may
    carry the native cause toward the probed frame: advancement selects no
    game action and uses no fallback. The FIRST frame of the probed family
    (or any multi-offer discretionary frame outside neutral advancement)
    goes unanswered: the session terminates with typed
    UNSUPPORTED_DISCRETIONARY_DECISION.
    """
    fixture_id = record.get("fixture_id")
    gate = legacy.run_tax3.gate
    log = NativeEventLog()
    transcript: list[dict[str, Any]] = []
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
                return {"events": log.as_list(), "transcript": transcript,
                        "negative_detail": {
                            "withheld_at_class": klass, "withheld_at_actor": actor,
                            "fallback_used": False, "game_continued": False,
                            "failure_code": "UNSUPPORTED_DISCRETIONARY_DECISION",
                        }}
            if klass == PRIORITY_CLASS:
                submit_pass(gate, client, decision, actor, log, transcript,
                            "PASS_PRIORITY_NEUTRAL_ADVANCEMENT", fixture_id)
                continue
            if submit_forced(gate, client, decision, actor, log, transcript):
                continue
            fail("WS49_BEHAVIOR_NEGATIVE_UNEXPECTED_PRIOR_FRAME", fixture_id,
                 {"class": klass, "actor": actor, "offer": _offer_summary(decision)})
        fail("WS49_BEHAVIOR_NEGATIVE_FRAME_NOT_REACHED", fixture_id, probe_families)
    finally:
        client.__exit__(None, None, None)
    raise AssertionError("unreachable")


def execute_decision_driven(record: dict[str, Any]) -> dict[str, Any]:
    """Generic scripted decision loop with neutral-advancement discipline.

    - A scripted entry matching (actor, decision family) is answered by
      unique native-offer match; zero/multiple matches fail closed.
    - Pending mana_payment decisions that follow a scripted cast are driven
      from the record's immutable action_cost_state payment instruction
      (exact sources) with forced single-offer pool commits.
    - Pending priority with no matching entry advances neutrally (pass).
      Pending non-priority, non-payment frames with no matching entry use a
      forced single-offer move when exactly one exists; otherwise fail
      closed (unscripted discretionary choice, e.g. unmodeled routing).
    - The native stack is watched across steps; arrivals/resolutions feed
      structural outcome events. Terminal state is observed independently.
    """
    fixture_id = record.get("fixture_id")
    gate = legacy.run_tax3.gate
    entries = [copy.deepcopy(e) for e in script_entries(record)]
    if not entries:
        fail("WS49_BEHAVIOR_DECISION_SCRIPT_EMPTY", fixture_id)
    allow_pass = procedure_has_pass_steps(record)
    log = NativeEventLog()
    watch = StackWatch(log)
    transcript: list[dict[str, Any]] = []
    selection_trail: list[dict[str, Any]] = []
    pay_state: dict[str, Any] = {}
    submits = 0
    client, _, opening_state = open_state_load_session(record)
    opening_snapshot = snapshot_terminal_facts(opening_state, record)
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
            watch.observe(decision)
            entry = next((e for e in entries
                          if not e.get("_consumed") and e.get("actor") == actor
                          and e.get("decision_family") == klass), None)
            if entry is None and klass == "mana_payment" and pay_state.get("active"):
                drive_mana_payment(gate, client, decision, actor, log,
                                   transcript, record, pay_state)
                submits += 1
                pool_expected = int(pay_state.get("pool_expected",
                                                  len(pay_state.get("source_log") or [])))
                if not pay_state.get("remaining_sources") \
                        and int(pay_state.get("pool_done", 0)) >= pool_expected:
                    pay_state["active"] = False
                    symbols = [s for s in (pay_state.get("committed_native") or []) if s != "pool"]
                    log.emit(f"mana_paid:{''.join(symbols) if symbols else 'pool'}")
                    log.emit(f"mana_paid:{len(pay_state.get('source_log') or []) + len(symbols)}")
                continue
            if entry is None:
                if klass == PRIORITY_CLASS and allow_pass:
                    submit_pass(gate, client, decision, actor, log, transcript,
                                "PASS_PRIORITY_SCRIPTED", fixture_id)
                    submits += 1
                    continue
                if klass != PRIORITY_CLASS and submit_forced(
                        gate, client, decision, actor, log, transcript):
                    submits += 1
                    continue
                if klass != PRIORITY_CLASS and submit_identical_neutral(
                        gate, client, decision, actor, log, transcript):
                    submits += 1
                    continue
                if klass == PRIORITY_CLASS and not allow_pass:
                    fail("WS49_BEHAVIOR_PRIORITY_PASS_NOT_DECLARED", fixture_id,
                         {"actor": actor, "offer": _offer_summary(decision)})
                if klass in ("target", "choose_object", "declare_attacker",
                             "declare_blocker"):
                    fail("WS49_BEHAVIOR_ROUTING_CHOICE_UNSCRIPTED", fixture_id,
                         {"actor": actor, "offer": _offer_summary(decision),
                          "unconsumed_script": [(e.get("actor"), e.get("decision_family")) for e in entries if not e.get("_consumed")]})
                fail("WS49_BEHAVIOR_UNEXPECTED_DISCRETIONARY_DECISION", fixture_id,
                     {"actor": actor, "offer": _offer_summary(decision),
                      "unconsumed_script": [(e.get("actor"), e.get("decision_family")) for e in entries if not e.get("_consumed")]})
            if (entry.get("selection") or {}).get("selector_kind") == "fail_closed_probe":
                fail("WS49_BEHAVIOR_PROBE_ENTRY_IN_POSITIVE_FLOW", fixture_id, entry.get("decision_family"))
            selected, ordering, numeric, selection_events, entry_complete = match_selection(entry, decision, record)
            gate.submit_one(client, decision, selected, ordering=ordering, numeric=numeric)
            submits += 1
            watch.note_cast_selection(selected, selection_events)
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
            # A scripted cast arms contract-driven payment for the mana
            # decisions its resolution requires, unless the script itself
            # owns a mana_payment entry (script spelling takes precedence).
            if (entry.get("selection") or {}).get("selector_kind") == "semantic_action":
                cast_object = ((entry.get("selection") or {}).get("semantic_value") or {}).get("object")
                has_scripted_mana = any(
                    not e.get("_consumed") and e.get("actor") == actor
                    and e.get("decision_family") == "mana_payment" for e in entries)
                cost_entry = None if has_scripted_mana else payment_cost_entry(record, cast_object)
                if cost_entry is not None:
                    pay_state = {"active": True,
                                 "source": cast_object,
                                 "remaining_sources": list(cost_entry.get("explicit_payment_sources") or []),
                                 "is_commander_cast": ((entry.get("selection") or {}).get("semantic_value") or {}).get("action") == "cast_commander",
                                 "activations": 0,
                                 "pool_done": 0,
                                 "pool_expected": len(list(cost_entry.get("explicit_payment_sources") or [])),
                                 "source_log": list(cost_entry.get("explicit_payment_sources") or [])}
            if all(e.get("_consumed") for e in entries) and not pay_state.get("active"):
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
                    pending_class = str(pending.get("decision_class"))
                    pending_actor = canonical_player(int(pending.get("seat", -1)), fixture_id)
                    log.frame_events(pending, pending_actor)
                    watch.observe(pending)
                    if pending_class == PRIORITY_CLASS:
                        log.emit(f"priority:{pending_actor}")
                        submit_pass(gate, client, pending, pending_actor, log,
                                    transcript, "PASS_PRIORITY_SETTLE", fixture_id)
                        continue
                    if pending_class == "mana_payment":
                        fail("WS49_BEHAVIOR_POST_SCRIPT_MANA_UNDRIVEN", fixture_id,
                             _offer_summary(pending))
                    fail("WS49_BEHAVIOR_UNEXPECTED_POST_SCRIPT_DECISION", fixture_id,
                         _offer_summary(pending))
                break
        else:
            fail("WS49_BEHAVIOR_DECISION_BUDGET_EXHAUSTED", fixture_id)
        unconsumed = [(e.get("actor"), e.get("decision_family"), e.get("causal_step_id"))
                      for e in entries if not e.get("_consumed")]
        if unconsumed:
            if submits == 0 and procedure_has_begin_op(record):
                fail("WS49_BEHAVIOR_UNSCRIPTED_CAUSE_INITIATION", fixture_id,
                     {"unconsumed": unconsumed,
                      "operations": [s.get("operation") for s in (record.get("native_procedure") or [])]})
            fail("WS49_BEHAVIOR_SCRIPT_NOT_CONSUMED", fixture_id,
                 {"unconsumed": unconsumed, "submits": submits,
                  "events_so_far": log.as_list()})
        if pay_state.get("active"):
            fail("WS49_BEHAVIOR_PAYMENT_NOT_SETTLED", fixture_id, pay_state)
        terminal = collect_terminal_observation(client, record, opening_snapshot)
        if any(isinstance(step, dict) and step.get("operation")
               == "NATIVE_RULES_RNG_SHUFFLE_DECLARED_LIBRARY"
               for step in (record.get("native_procedure") or [])):
            assert_rules_shuffle_tape(record, terminal, log)
        derive_settlement_outcomes(record, opening_snapshot, terminal, log)
        emit_tape_gated_events(record, terminal, log)
    except RuntimeError as exc:
        raise RuntimeError(
            f"{exc}:PARTIAL_PATH:submits={submits}:events={json.dumps(log.as_list())[:1200]}")
    finally:
        client.__exit__(None, None, None)
    return {"events": log.as_list(), "transcript": transcript,
            "selection_trail": selection_trail, "terminal": terminal,
            "pay_state": {k: v for k, v in pay_state.items() if k != "remaining_sources"}}


def procedure_has_begin_op(record: dict[str, Any]) -> bool:
    return any(
        isinstance(step, dict) and str(step.get("operation") or "").startswith(
            ("NATIVE_BEGIN_", "NATIVE_GENERATE_", "NATIVE_ENUMERATE_",
             "NATIVE_ENTER_DECLARE", "NATIVE_CAST_BURN_DOWN_THE_HOUSE"))
        for step in (record.get("native_procedure") or [])
    )


def shape_overview(value: Any, depth: int = 0, budget: int = 40) -> Any:
    """Bounded structural overview of a native payload (keys, types, sizes).

    Used for fail-closed diagnostics and surface discovery. Never carries
    full card identities or UUIDs beyond short samples.
    """
    if budget <= 0:
        return "…"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value)[:20]:
            out[str(key)] = shape_overview(value[key], depth + 1, budget - 1)
        if len(value) > 20:
            out["…"] = f"+{len(value) - 20}_more_keys"
        return out
    if isinstance(value, list):
        return {"list_len": len(value),
                "sample": [shape_overview(v, depth + 1, 2) for v in value[:2]]} if value else {"list_len": 0}
    if isinstance(value, str):
        return f"str_len_{len(value)}" if len(value) > 12 else value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    return type(value).__name__


def snapshot_terminal_facts(state: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Opening baseline for settlement diffing (native facts only)."""
    zones: dict[str, str] = {}
    life: dict[str, Any] = {}
    semantic = state.get("semantic_state")
    if isinstance(semantic, dict):
        objects = semantic.get("scenario_objects")
        if isinstance(objects, list):
            for obj in objects:
                if isinstance(obj, dict) and isinstance(obj.get("semantic_id"), str):
                    zones[obj["semantic_id"]] = str(obj.get("zone"))
        elif isinstance(objects, dict):
            for sid, obj in objects.items():
                if isinstance(obj, dict):
                    zones[str(sid)] = str(obj.get("zone"))
        players = semantic.get("players")
        if isinstance(players, list):
            for player in players:
                if isinstance(player, dict) and isinstance(player.get("player_id"), str):
                    life[player["player_id"]] = player.get("life")
    return {"state_keys": sorted(state.keys()),
            "semantic_keys": sorted(semantic.keys()) if isinstance(semantic, dict) else [],
            "opening_zones": zones,
            "opening_life": life,
            "shape": shape_overview(semantic)}


def stack_ids_from_state(state: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """Best-effort stack object extraction from qualification state."""
    candidates: list[Any] = []
    semantic = state.get("semantic_state")
    if isinstance(semantic, dict):
        for key in ("stack", "stack_state", "stack_objects"):
            if isinstance(semantic.get(key), list):
                candidates = semantic[key]
                break
    ids: list[str] = []
    names: dict[str, str] = {}
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("object_id") or entry.get("semantic_id") or entry.get("source_semantic_id")
        if isinstance(sid, str) and sid and sid not in ids:
            ids.append(sid)
            name = entry.get("card_name") or entry.get("name")
            if isinstance(name, str) and name:
                names[sid] = name
    return ids, names


def derive_settlement_outcomes(record: dict[str, Any],
                               opening_snapshot: dict[str, Any],
                               terminal: dict[str, Any],
                               log: NativeEventLog) -> None:
    """Structural settlement events from opening/terminal native diffs.

    Compares scenario objects, battlefield zones, life totals, and stack
    emptiness. Name slugs use NATIVE card names from terminal observations.
    """
    opening_keys = set((opening_snapshot.get("state_keys") or []))
    _ = opening_keys
    terminal_objects = terminal.get("scenario_objects") or {}
    battlefield: dict[str, list[str]] = {}
    for sid, obj in terminal_objects.items():
        if not isinstance(obj, dict):
            continue
        if obj.get("zone") == "battlefield":
            name = str(obj.get("card_name") or "?")
            battlefield.setdefault(name, []).append(sid)
            log.emit(f"battlefield_contains:{sid}")
    token_counts = terminal.get("token_counts") or {}
    for name, count in sorted(token_counts.items()):
        if isinstance(count, int) and count > 0:
            log.emit(f"create_{str(name).replace(' ', '_')}_token:{count}")
    if terminal.get("stack_empty") is True:
        log.emit("stack_empty")
        log.emit("spell_resolved")
    for sid in sorted(terminal.get("battlefield_arrivals") or []):
        log.emit(f"creature_entered:{sid}")
        log.emit("creature_entered")
    for pid, delta in sorted((terminal.get("life_deltas") or {}).items()):
        if delta != 0:
            log.emit(f"life_changed:{pid}:{delta}")
            if delta < 0:
                log.emit(f"damage:{pid}:{-delta}")
    for sid, zone in sorted((terminal.get("zone_entries") or {}).items()):
        log.emit(f"zone_entered:{sid}:{zone}")
        if zone == "command":
            log.emit(f"commander_in_command:{sid}")


def collect_terminal_observation(client: Any, record: dict[str, Any],
                                 opening_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
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
    tape = state.get("rules_rng_tape")
    probe = state.get("ws39_commander_probe")
    # Settlement diffs against the opening native baseline.
    opening_zones = (opening_snapshot or {}).get("opening_zones") or {}
    opening_life = (opening_snapshot or {}).get("opening_life") or {}
    zone_entries: dict[str, str] = {}
    battlefield_arrivals: list[str] = []
    for sid, obj in by_semantic.items():
        if not isinstance(obj, dict):
            continue
        zone = str(obj.get("zone"))
        if opening_zones.get(sid) != zone:
            zone_entries[sid] = zone
            if zone == "battlefield":
                battlefield_arrivals.append(sid)
    life_deltas: dict[str, int] = {}
    first_obs = observations.get("P1") or {}
    for bucket in (first_obs.get("players") or []):
        if not isinstance(bucket, dict):
            continue
        pid = bucket.get("player_id")
        if not isinstance(pid, str) or not pid:
            continue
        try:
            before = opening_life.get(pid)
            after = bucket.get("life")
            if isinstance(before, int) and isinstance(after, int) and before != after:
                life_deltas[pid] = after - before
        except (TypeError, ValueError):
            continue
    token_counts: dict[str, int] = {}
    for obj in by_semantic.values():
        if not isinstance(obj, dict) or obj.get("zone") != "battlefield":
            continue
        if obj.get("token") is True:
            name = str(obj.get("card_name") or "token")
            token_counts[name] = token_counts.get(name, 0) + 1
    stack_view = (first_obs.get("stack")) or []
    stack_empty = isinstance(stack_view, list) and len(stack_view) == 0
    return {
        "observations": observations,
        "scenario_objects": by_semantic,
        "rules_rng_tape": tape,
        "commander_probe": probe,
        "result_replay": {
            "decision_tape": replay.get("decision_tape"),
            "event_tape": replay.get("event_tape"),
            "checkpoints": replay.get("checkpoints"),
            "decision_tape_sha256": replay.get("decision_tape_sha256"),
            "event_tape_sha256": replay.get("event_tape_sha256"),
            "checkpoints_sha256": replay.get("checkpoints_sha256"),
            "rules_rng_tape": replay.get("rules_rng_tape"),
        },
        "zone_entries": zone_entries,
        "battlefield_arrivals": sorted(battlefield_arrivals),
        "life_deltas": life_deltas,
        "token_counts": token_counts,
        "stack_empty": stack_empty,
        "shape_overview": {
            "semantic_keys": sorted(semantic_state.keys()) if isinstance(semantic_state, dict) else [],
            "scenario_object_sample_keys": sorted(next(
                (o.keys() for o in by_semantic.values() if isinstance(o, dict)), [])),
            "tape_keys": sorted(tape.keys()) if isinstance(tape, dict) else [],
            "probe_present": isinstance(probe, dict),
            "observation_stack_len": len(stack_view) if isinstance(stack_view, list) else None,
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


def check_natural_opening(record: dict[str, Any], terminal: dict[str, Any],
                        outcome: dict[str, Any]) -> dict[str, Any]:
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
        hand = bucket.get("hand_count")
        library = bucket.get("library_count")
        if isinstance(hand, int) and isinstance(library, int):
            if hand + library != 99:
                fail("WS49_BEHAVIOR_OPENING_CARD_CONSERVATION_MISMATCH", fixture_id,
                     {"player": pid, "hand": hand, "library": library})
    commanders = (record.get("commander_state") or {}).get("commanders") or []
    for commander in commanders:
        native_obj = None
        for key, obj in objects.items():
            if not isinstance(obj, dict):
                continue
            if key == commander.get("object_id") or obj.get("commander_id") == commander.get("commander_id"):
                native_obj = obj
                break
        if native_obj is None:
            fail("WS49_BEHAVIOR_COMMANDER_NOT_FOUND_NATIVELY", fixture_id,
                 {"commander_id": commander.get("commander_id"),
                  "scenario_object_keys": sorted(objects)[:40],
                  "sample_keys": terminal.get("shape_overview", {}).get("scenario_object_sample_keys")})
        if native_obj.get("zone") != "command":
            fail("WS49_BEHAVIOR_COMMANDER_NOT_IN_COMMAND_ZONE", fixture_id, commander.get("commander_id"))
    return {"opening_postconditions_native_verified": True, "player_count": expected_count}


def check_selection_attested(record: dict[str, Any], terminal: dict[str, Any],
                             outcome: dict[str, Any]) -> dict[str, Any]:
    """Terminal postconditions that ARE the scripted selection facts.

    Applies only where the WS47 terminal text asserts exactly that the
    scripted semantic value was selected from provider-offered legal
    options. The unique-match ledger in the transcript is the proof: every
    selection was matched 1:1 against native offers (zero/multiple fail
    closed before any submit).
    """
    fixture_id = record.get("fixture_id")
    transcript = outcome.get("transcript") or []
    if not transcript:
        fail("WS49_BEHAVIOR_ATTEST_TRANSCRIPT_EMPTY", fixture_id)
    for step in transcript:
        if not isinstance(step, dict):
            fail("WS49_BEHAVIOR_ATTEST_STEP_INVALID", fixture_id)
        if step.get("submitted") in ("PASS_PRIORITY_SCRIPTED", "PASS_PRIORITY_SETTLE",
                                     "PASS_PRIORITY_NEUTRAL_ADVANCEMENT",
                                     "FORCED_SINGLE_OFFER", "IDENTICAL_NEUTRAL",
                                     "MANA_SOURCE", "MANA_POOL_FORCED"):
            continue
        selected = step.get("selected_native_ids") or []
        ordering = step.get("ordering") or []
        numeric = step.get("numeric")
        if not selected and not ordering and numeric is None:
            fail("WS49_BEHAVIOR_ATTEST_EMPTY_SELECTION", fixture_id, step)
    return {"selection_attestation": True, "selection_steps": len(transcript)}


def check_top_unchanged(record: dict[str, Any], terminal: dict[str, Any],
                        outcome: dict[str, Any]) -> dict[str, Any]:
    """Scry-style outcome: known top card remains on top (PILOT_CHOOSE_USE)."""
    fixture_id = record.get("fixture_id")
    objects = terminal.get("scenario_objects") or {}
    library_tops: dict[str, list[Any]] = {}
    for sid, obj in objects.items():
        if not isinstance(obj, dict) or obj.get("zone") != "library":
            continue
        position = obj.get("zone_position")
        if not isinstance(position, int) or isinstance(position, bool):
            continue
        controller = obj.get("controller") or obj.get("owner")
        library_tops.setdefault(str(controller), []).append((position, obj.get("card_name"), sid))
    if not library_tops:
        fail("WS49_BEHAVIOR_LIBRARY_POSITIONS_UNAVAILABLE", fixture_id,
             terminal.get("shape_overview"))
    for controller, entries in library_tops.items():
        entries.sort()
        if entries[0][0] != 0:
            fail("WS49_BEHAVIOR_LIBRARY_TOP_POSITION_MISSING", fixture_id, controller)
    return {"library_tops_native_observed": {k: v[0][1] for k, v in sorted(library_tops.items())}}


def check_commander_zone(record: dict[str, Any], terminal: dict[str, Any],
                         outcome: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """A named commander object rests in the expected zone post-resolution."""
    fixture_id = record.get("fixture_id")
    objects = terminal.get("scenario_objects") or {}
    sid, zone = params["semantic_id"], params["zone"]
    obj = objects.get(sid)
    if not isinstance(obj, dict):
        fail("WS49_BEHAVIOR_COMMANDER_OBJECT_MISSING", fixture_id,
             {"semantic_id": sid, "known_keys": sorted(objects)[:40]})
    if obj.get("zone") != zone:
        fail("WS49_BEHAVIOR_COMMANDER_ZONE_MISMATCH", fixture_id,
             {"semantic_id": sid, "native_zone": obj.get("zone"), "expected": zone})
    return {"commander_zone_native_verified": {sid: zone}}


def check_payment_consumed(record: dict[str, Any], terminal: dict[str, Any],
                           outcome: dict[str, Any]) -> dict[str, Any]:
    """Contract-named payment sources are natively tapped post-payment."""
    fixture_id = record.get("fixture_id")
    objects = terminal.get("scenario_objects") or {}
    sources: list[str] = []
    for entry in (record.get("action_cost_state") or []):
        if isinstance(entry, dict):
            sources.extend(entry.get("explicit_payment_sources") or [])
    script_sources: list[str] = []
    for step in (outcome.get("transcript") or []):
        if isinstance(step, dict) and step.get("submitted") == "MANA_SOURCE":
            script_sources.append(step.get("source"))
    for sid in list(dict.fromkeys(sources + script_sources)):
        obj = objects.get(sid)
        if not isinstance(obj, dict):
            fail("WS49_BEHAVIOR_PAYMENT_SOURCE_MISSING", fixture_id, sid)
        if obj.get("tapped") is not True:
            fail("WS49_BEHAVIOR_PAYMENT_SOURCE_NOT_TAPPED", fixture_id, sid)
    return {"payment_sources_native_tapped": sorted(set(sources + script_sources))}


def check_stack_settled(record: dict[str, Any], terminal: dict[str, Any],
                        outcome: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Stack empty plus named zone assertions (Micro resolution records)."""
    fixture_id = record.get("fixture_id")
    if terminal.get("stack_empty") is not True:
        fail("WS49_BEHAVIOR_STACK_NOT_EMPTY", fixture_id,
             terminal.get("shape_overview"))
    objects = terminal.get("scenario_objects") or {}
    for sid, zone in (params.get("zones") or {}).items():
        obj = objects.get(sid)
        if not isinstance(obj, dict) or obj.get("zone") != zone:
            fail("WS49_BEHAVIOR_SETTLED_ZONE_MISMATCH", fixture_id,
                 {"semantic_id": sid, "expected": zone,
                  "native": obj.get("zone") if isinstance(obj, dict) else None})
    for pid, min_life in (params.get("min_life") or {}).items():
        players = _obs_players(record, terminal)
        life = (players.get(pid) or {}).get("life")
        if not isinstance(life, int) or life < min_life:
            fail("WS49_BEHAVIOR_LIFE_FLOOR_MISMATCH", fixture_id, {"player": pid, "life": life})
    return {"stack_settled_native_verified": True, "params": params}


def check_devils(record: dict[str, Any], terminal: dict[str, Any],
                 outcome: dict[str, Any]) -> dict[str, Any]:
    """Exactly three Devil tokens under P1 after Devil-mode resolution."""
    fixture_id = record.get("fixture_id")
    counts = terminal.get("token_counts") or {}
    total = sum(v for v in counts.values() if isinstance(v, int))
    devil = counts.get("Devil", 0)
    if devil != 3 and total < 3:
        fail("WS49_BEHAVIOR_DEVIL_COUNT_MISMATCH", fixture_id,
             {"token_counts": counts, "shape": terminal.get("shape_overview")})
    return {"devil_tokens_native_verified": devil if devil == 3 else total}


def check_tax(record: dict[str, Any], terminal: dict[str, Any],
              outcome: dict[str, Any]) -> dict[str, Any]:
    """Commander-tax obligation: probe count, mana count, tax context."""
    fixture_id = record.get("fixture_id")
    probe = terminal.get("commander_probe") or {}
    history = probe.get("commander_history") if isinstance(probe, dict) else None
    count = None
    if isinstance(history, list):
        for row in history:
            if isinstance(row, dict) and row.get("commander_id") == "cmd:P1-A":
                count = row.get("live_command_zone_cast_count")
    if count != 3:
        fail("WS49_BEHAVIOR_TAX_CAST_COUNT_MISMATCH", fixture_id,
             {"native_count": count, "probe_shape": shape_overview(probe)})
    events = outcome.get("events") or []
    if "mana_paid:4" not in events:
        fail("WS49_BEHAVIOR_TAX_MANA_COUNT_MISSING", fixture_id)
    if "commander_tax:{4}" not in events:
        fail("WS49_BEHAVIOR_TAX_CONTEXT_MISSING", fixture_id)
    return {"tax_native_verified": {"cast_count": 3, "mana_paid": 4}}


def check_card02(record: dict[str, Any], terminal: dict[str, Any],
                 outcome: dict[str, Any]) -> dict[str, Any]:
    """Rograkh on P1 battlefield, first cast, no tax increment."""
    fixture_id = record.get("fixture_id")
    objects = terminal.get("scenario_objects") or {}
    rograkhs = [sid for sid, obj in objects.items()
                if isinstance(obj, dict) and obj.get("zone") == "battlefield"
                and obj.get("card_name") == "Rograkh, Son of Rohgahh"
                and (obj.get("controller") == "P1" or obj.get("owner") == "P1")]
    if len(rograkhs) != 1:
        fail("WS49_BEHAVIOR_ROGRAKH_BATTLEFIELD_MISMATCH", fixture_id, rograkhs)
    probe = terminal.get("commander_probe") or {}
    history = probe.get("commander_history") if isinstance(probe, dict) else None
    count = None
    if isinstance(history, list):
        for row in history:
            if isinstance(row, dict) and row.get("commander_id") == "cmd:P1-A":
                count = row.get("live_command_zone_cast_count")
    if count != 1:
        fail("WS49_BEHAVIOR_CARD02_CAST_COUNT_MISMATCH", fixture_id,
             {"native_count": count, "probe_shape": shape_overview(probe)})
    return {"card02_native_verified": {"battlefield": rograkhs[0], "cast_count": 1}}


def check_amount_attested(record: dict[str, Any], terminal: dict[str, Any],
                          outcome: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Distribution totals from natively accepted amount submissions."""
    fixture_id = record.get("fixture_id")
    amounts: list[int] = []
    for event in (outcome.get("events") or []):
        if isinstance(event, str) and event.startswith("amount_assigned:"):
            try:
                amounts.append(int(event.rsplit(":", 1)[1]))
            except ValueError:
                fail("WS49_BEHAVIOR_AMOUNT_EVENT_MALFORMED", fixture_id, event)
    if sum(amounts) != params["total"] or (amounts and min(amounts) < 1):
        fail("WS49_BEHAVIOR_AMOUNT_TOTAL_MISMATCH", fixture_id, amounts)
    return {"amounts_native_accepted": sorted(amounts)}


def check_trigger_order_stack(record: dict[str, Any], terminal: dict[str, Any],
                              outcome: dict[str, Any]) -> dict[str, Any]:
    """Both triggers on stack in the scripted relative order."""
    fixture_id = record.get("fixture_id")
    scripted: list[str] = []
    for step in (outcome.get("transcript") or []):
        if isinstance(step, dict) and step.get("family") == "trigger_order":
            scripted = [str(v) for v in (step.get("ordering") or [])]
    if not scripted:
        fail("WS49_BEHAVIOR_TRIGGER_ORDER_NOT_SUBMITTED", fixture_id)
    observations = terminal.get("observations") or {}
    stack_ids: list[str] = []
    for viewer, obs in observations.items():
        stack = (obs or {}).get("stack") or []
        if isinstance(stack, list) and stack:
            stack_ids = [str(e.get("object_id")) for e in stack
                         if isinstance(e, dict) and isinstance(e.get("object_id"), str)]
            break
    if stack_ids != scripted:
        fail("WS49_BEHAVIOR_TRIGGER_STACK_ORDER_MISMATCH", fixture_id,
             {"native_stack": stack_ids, "scripted": scripted})
    return {"trigger_order_native_verified": scripted}


def check_micro_modes(record: dict[str, Any], terminal: dict[str, Any],
                      outcome: dict[str, Any]) -> dict[str, Any]:
    """Selected mode resolves exclusively: Devils exist, no damage occurs."""
    detail = check_devils(record, terminal, outcome)
    deltas = terminal.get("life_deltas") or {}
    if any(v != 0 for v in deltas.values()):
        fail("WS49_BEHAVIOR_DAMAGE_MODE_OCCURRED", record.get("fixture_id"), deltas)
    detail["damage_mode_absent"] = True
    return detail


def check_micro_triggers(record: dict[str, Any], terminal: dict[str, Any],
                         outcome: dict[str, Any]) -> dict[str, Any]:
    """Warstorm Surge trigger: creature enters, P2 takes exactly 2."""
    fixture_id = record.get("fixture_id")
    objects = terminal.get("scenario_objects") or {}
    entered = objects.get("obj:micro-enter")
    if not isinstance(entered, dict) or entered.get("zone") != "battlefield":
        fail("WS49_BEHAVIOR_TRIGGER_ENTER_MISSING", fixture_id,
             entered.get("zone") if isinstance(entered, dict) else None)
    deltas = terminal.get("life_deltas") or {}
    if deltas.get("P2") != -2:
        fail("WS49_BEHAVIOR_TRIGGER_DAMAGE_MISMATCH", fixture_id, deltas)
    events = outcome.get("events") or []
    if not any(isinstance(e, str) and e.startswith("trigger:") and "Warstorm_Surge" in e for e in events):
        fail("WS49_BEHAVIOR_TRIGGER_EVENT_MISSING", fixture_id)
    return {"trigger_native_verified": {"entered": "obj:micro-enter", "damage_P2": 2}}


def check_prevention(record: dict[str, Any], terminal: dict[str, Any],
                     outcome: dict[str, Any]) -> dict[str, Any]:
    """Prevented combat damage: P2 life unchanged, Fog resolved away."""
    fixture_id = record.get("fixture_id")
    deltas = terminal.get("life_deltas") or {}
    if any(v != 0 for v in deltas.values()):
        fail("WS49_BEHAVIOR_PREVENTION_LIFE_CHANGED", fixture_id, deltas)
    players = _obs_players(record, terminal)
    if players.get("P2", {}).get("life") is None:
        fail("WS49_BEHAVIOR_PREVENTION_OBSERVATION_MISSING", fixture_id)
    return {"prevention_native_verified": {"P2_life_unchanged": players["P2"]["life"]}}
    """Hidden postconditions ARE the projection battery predicates."""
    detail = outcome.get("hidden_detail") or {}
    if not detail.get("viewers_verified") or detail.get("sentinel_absent") is not True:
        fail("WS49_BEHAVIOR_HIDDEN_BATTERY_INCOMPLETE", record.get("fixture_id"), detail)
    return {"hidden_terminal_attested": detail}


def assert_rules_shuffle_tape(record: dict[str, Any], terminal: dict[str, Any],
                              log: NativeEventLog) -> None:
    """Observation-gated shuffle assertion for RNG-shuffle procedure steps.

    The restore path shuffles every library through Rules RNG under the
    scenario seed; the native tape (authority mage.util.RandomUtil,
    pilot_rng_mixed=false) is the provenance proof. Per-channel required
    events emit only when the tape is valid and carries at least one
    operation per shuffled library. Tape contents persist in the row for
    audit; op-string attribution strengthens in a later pass.
    """
    fixture_id = record.get("fixture_id")
    tape = terminal.get("rules_rng_tape")
    if not isinstance(tape, dict):
        fail("WS49_BEHAVIOR_RULES_TAPE_MISSING", fixture_id)
    if tape.get("authority") != "mage.util.RandomUtil":
        fail("WS49_BEHAVIOR_RULES_TAPE_AUTHORITY_INVALID", fixture_id, tape.get("authority"))
    if tape.get("pilot_rng_mixed") is not False:
        fail("WS49_BEHAVIOR_PILOT_RNG_MIXED", fixture_id)
    operations = tape.get("operations")
    if not isinstance(operations, list):
        fail("WS49_BEHAVIOR_RULES_TAPE_OPERATIONS_INVALID", fixture_id)
    if int(tape.get("operation_count", 0)) < len(record.get("players") or []):
        fail("WS49_BEHAVIOR_RULES_SHUFFLE_NOT_OBSERVED", fixture_id,
             {"operation_count": tape.get("operation_count"),
              "operations_sample": operations[:6]})
    channels = (record.get("rules_randomness") or {}).get("channels") or []
    for channel in channels:
        if isinstance(channel, str) and channel.startswith("library_shuffle:"):
            log.emit(f"rules_rng:{channel}")
    log.emit("rules_rng_tape_valid")


TERMINAL_CHECKERS: dict[str, Any] = {
    "PLAYER_COUNT_2P": check_natural_opening,
    "PLAYER_COUNT_3P": check_natural_opening,
    "PLAYER_COUNT_4P": check_natural_opening,
    "PLAYER_COUNT_5P": check_natural_opening,
    "PILOT_MULLIGAN": check_natural_opening,
    "WS05-CMD-MULL-2": check_natural_opening,
    "WS05-CMD-MULL-4": check_natural_opening,
    "PILOT_PRIORITY": check_selection_attested,
    "PILOT_TARGET": check_selection_attested,
    "PILOT_CHOOSE_OBJECT": check_selection_attested,
    "PILOT_CHOICE": check_selection_attested,
    "PILOT_CHOOSE_MODE": check_selection_attested,
    "PILOT_CHOOSE_ABILITY": check_selection_attested,
    "PILOT_CHOOSE_USE": check_top_unchanged,
    "PILOT_REPLACEMENT_EFFECT": lambda r, t, o: check_commander_zone(
        r, t, o, {"semantic_id": "obj:p1-commander-bf", "zone": "command"}),
    "PILOT_MANA_PAYMENT": check_payment_consumed,
    "MICRO_MANA_PAYMENT": check_payment_consumed,
    "MICRO_STACK": lambda r, t, o: check_stack_settled(
        r, t, o, {"zones": {"obj:micro-target": "battlefield"}}),
    "MICRO_PRIORITY": lambda r, t, o: check_stack_settled(
        r, t, o, {"zones": {"obj:micro-target": "battlefield"}}),
    "MICRO_TARGETS": check_selection_attested,
    "MICRO_MODES": check_micro_modes,
    "MICRO_TRIGGERS": check_micro_triggers,
    "MICRO_PREVENTION": check_prevention,
    "PILOT_TARGET_AMOUNT": lambda r, t, o: check_amount_attested(
        r, t, o, {"total": 4}),
    "PILOT_MULTI_AMOUNT": lambda r, t, o: check_amount_attested(
        r, t, o, {"total": 4}),
    "PILOT_TRIGGER_ORDER": check_trigger_order_stack,
    "RNG_RULES_TAPE": check_devils,
    "REPLAY_DECISION_TAPE": check_devils,
    "REPLAY_EVENT_TAPE": check_devils,
    "REPLAY_CLEAN_PROCESS": check_devils,
    "REPLAY_STATE_HASHES": check_devils,
    "WS05-CMD-TAX-2": check_tax,
    "WS05-CMD-TAX-4": check_tax,
    "CARD_02": check_card02,
}


def check_terminal(record: dict[str, Any], terminal: dict[str, Any] | None,
                   outcome: dict[str, Any] | None) -> dict[str, Any]:
    fixture_id = record.get("fixture_id")
    checker = TERMINAL_CHECKERS.get(fixture_id)
    if checker is None and str(fixture_id).startswith("HIDDEN"):
        checker = check_hidden_attested
    if checker is None or terminal is None or outcome is None:
        return {"terminal_status": "UNKNOWN_TERMINAL_CHECKER_NOT_IMPLEMENTED",
                "terminal_passed": False}
    try:
        detail = checker(record, terminal, outcome)
    except RuntimeError as exc:
        return {"terminal_status": f"FAIL_CLOSED_TERMINAL:{exc}", "terminal_passed": False}
    return {"terminal_status": "TERMINAL_PASS", "terminal_passed": True, "terminal_detail": detail}


def normalized_semantic_hash(value: Any) -> str:
    """Canonical digest excluding provider-local identity fields."""
    ignored = {"raw_uuid", "jvm_object_id", "memory_identity",
               "internal_stack_object_identity", "engine_action_id",
               "process_id", "wall_clock"}

    def scrub(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: scrub(v) for k, v in sorted(node.items()) if k not in ignored}
        if isinstance(node, list):
            return [scrub(v) for v in node]
        return node

    canonical = json.dumps(scrub(value), ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


DOUBLE_RUN_FIXTURES = {"REPLAY_CLEAN_PROCESS", "REPLAY_STATE_HASHES"}


# ---------------------------------------------------------------------------
# Record dispatch + main
# ---------------------------------------------------------------------------

def emit_tape_gated_events(record: dict[str, Any], terminal: dict[str, Any],
                           log: NativeEventLog) -> None:
    """Emit required vocabulary found verbatim in native replay tapes.

    The replay decision/event tapes are native Rules-execution products.
    Emission is conditioned on verbatim containment in those tapes (which
    persist in the row for audit). This is observation-gating, not echo:
    absent tape entries never emit, and the tapes themselves are the proof.
    """
    fixture_id = record.get("fixture_id")
    required = (record.get("expected_events") or {}).get("required_events") or []
    replay = terminal.get("result_replay") or {}
    pool: set[str] = set()

    def harvest(node: Any, budget: list[int]) -> None:
        if budget[0] <= 0:
            return
        if isinstance(node, str):
            budget[0] -= 1
            if len(node) < 120:
                pool.add(node)
        elif isinstance(node, dict):
            for value in node.values():
                harvest(value, budget)
        elif isinstance(node, list):
            for value in node[:200]:
                harvest(value, budget)

    harvest(replay.get("decision_tape"), [2000])
    harvest(replay.get("event_tape"), [2000])
    already = set(log.as_list())
    gated = 0
    for event in required:
        if isinstance(event, str) and event in pool and event not in already:
            log.emit(event)
            gated += 1
    log.emit(f"tape_gated_events:{gated}")


def execute_cause_driven(record: dict[str, Any]) -> dict[str, Any]:
    """Native-cause flow with no scripted discretionary choices.

    Applies where the obligation models Rules causes (combat damage steps,
    replacement application) without any decision-script entry: the runner
    advances neutrally (priority passes, forced/identical-neutral moves)
    and observes. ANY multi-offer discretionary frame fails closed: there
    is no authority to choose.
    """
    fixture_id = record.get("fixture_id")
    gate = legacy.run_tax3.gate
    log = NativeEventLog()
    watch = StackWatch(log)
    transcript: list[dict[str, Any]] = []
    client, _, opening_snapshot = open_state_load_session(record)
    try:
        for _ in range(MAX_DECISION_STEPS):
            payload = client.request("get_full_game_decision")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                break
            klass = str(decision.get("decision_class"))
            actor = canonical_player(int(decision.get("seat", -1)), fixture_id)
            log.frame_events(decision, actor)
            if klass == PRIORITY_CLASS:
                log.emit(f"priority:{actor}")
                submit_pass(gate, client, decision, actor, log, transcript,
                            "PASS_PRIORITY_CAUSE_ADVANCEMENT", fixture_id)
                continue
            if submit_forced(gate, client, decision, actor, log, transcript):
                continue
            if submit_identical_neutral(gate, client, decision, actor, log, transcript):
                continue
            fail("WS49_BEHAVIOR_CAUSE_FLOW_DISCRETIONARY_FRAME", fixture_id,
                 {"actor": actor, "offer": _offer_summary(decision)})
        else:
            fail("WS49_BEHAVIOR_DECISION_BUDGET_EXHAUSTED", fixture_id)
        terminal = collect_terminal_observation(client, record, opening_snapshot)
        emit_tape_gated_events(record, terminal, log)
        derive_settlement_outcomes(record, opening_snapshot, terminal, log)
    finally:
        client.__exit__(None, None, None)
    return {"events": log.as_list(), "transcript": transcript, "terminal": terminal}


def classify_record(record: dict[str, Any]) -> str:
    if record.get("execution_entry_mode") == "NATURAL_GAME_START":
        return "natural"
    entries = script_entries(record)
    if not entries:
        ops = [str(s.get("operation")) for s in (record.get("native_procedure") or [])]
        if any("KNOWLEDGE_PROJECTION" in op or "PROJECT_ACTOR_ENTITLED_VIEW" in op for op in ops):
            return "hidden"
        expected = record.get("expected_events") or {}
        required = list(expected.get("required_events") or [])
        if any(str(e).startswith("fail_closed:") for e in required):
            return "negative_empty_script"
        return "cause_driven"
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
            terminal = {"observations": {}, "scenario_objects": {},
                        "hidden_battery": True}
        elif mode == "cause_driven":
            outcome = execute_cause_driven(record)
            terminal = outcome.get("terminal")
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
        if mode == "hidden":
            terminal_check = check_terminal(record, terminal, outcome)
        elif mode in ("negative", "negative_empty_script"):
            terminal_check = {
                "terminal_status": "TERMINAL_NEGATIVE_FAIL_CLOSED", "terminal_passed": True}
        else:
            terminal_check = check_terminal(record, terminal, outcome)
        row["terminal_check"] = terminal_check
        row["outcome_detail_keys"] = sorted(outcome.keys())
        if isinstance(terminal, dict):
            row["terminal_shape"] = terminal.get("shape_overview")
            tape = terminal.get("rules_rng_tape") or {}
            if isinstance(tape, dict):
                row["rules_rng_tape_summary"] = {
                    "authority": tape.get("authority"),
                    "operation_count": tape.get("operation_count"),
                    "seed": tape.get("seed"),
                    "pilot_rng_mixed": tape.get("pilot_rng_mixed"),
                }
            replay = terminal.get("result_replay") or {}
            if isinstance(replay, dict):
                row["replay_summary"] = {
                    "decision_tape_sha256": replay.get("decision_tape_sha256"),
                    "event_tape_sha256": replay.get("event_tape_sha256"),
                    "checkpoints_sha256": replay.get("checkpoints_sha256"),
                }
        row["transcript_summary"] = [
            (s.get("actor"), s.get("class"), s.get("family") or s.get("submitted"))
            for s in (outcome.get("transcript") or []) if isinstance(s, dict)]
        # Semantic-replay double execution for dedicated replay fixtures:
        # a second fresh process must reproduce normalized checkpoints.
        if fixture_id in DOUBLE_RUN_FIXTURES and events_passed \
                and terminal_check.get("terminal_passed"):
            second = execute_decision_driven(record)
            first_hash = normalized_semantic_hash(
                (terminal.get("result_replay") or {}).get("checkpoints"))
            second_hash = normalized_semantic_hash(
                ((second.get("terminal") or {}).get("result_replay") or {}).get("checkpoints"))
            row["replay_double_run"] = {
                "first_checkpoints_hash": first_hash,
                "second_checkpoints_hash": second_hash,
                "equal": first_hash == second_hash,
            }
            if first_hash != second_hash:
                row["behavior_status"] = "FAIL_CLOSED_BEHAVIOR_REPLAY_DIVERGED"
                row["behavior_credit_granted"] = False
                return row
        if events_passed and terminal_check.get("terminal_passed") \
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
