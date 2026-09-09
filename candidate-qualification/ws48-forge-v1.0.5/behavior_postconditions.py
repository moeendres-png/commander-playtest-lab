#!/usr/bin/env python3
"""WS-48 behavior terminal-postcondition registry (provider-neutral).

Each WS-47 v1.0.5 ``terminal_postconditions`` entry is a prose string. This
module maps normalized templates to checker functions with signature::

    checker(record, ctx) -> list[str]  # violation strings, empty on PASS

``record`` is the immutable materialization record. ``ctx`` carries:

- ``snapshot``: terminal native behavior snapshot (live-game cards with
  semantic refs where bound, life/zones/counters/stack/turn/phase);
- ``feed``: ordered native event strings emitted during the session;
- ``matches``: driver decision-match records proving each scripted selection
  was chosen from provider-offered legal options only;
- ``stop``: terminal stop descriptor (``stop_reason`` / typed failure code).

Checkers assert on native evidence only. Absence of evidence is failure;
nothing is inferred.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

Checker = Callable[[dict[str, Any], dict[str, Any]], list[str]]


def _norm(text: str) -> str:
    s = re.sub(r"obj:[A-Za-z0-9_-]+", "OBJ", text)
    s = re.sub(r"\bP[1-5]\b", "PX", s)
    s = re.sub(r"cmd:[A-Za-z0-9_-]+", "CMD", s)
    s = re.sub(r"\bstack:\d+", "STACK", s)
    s = re.sub(r"(?<!\{)\d+(?!\})", "N", s)
    return s


def _cards(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return list((snapshot or {}).get("cards") or [])


def _snapshot_cards(ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(c.get("semantic_id")): c
        for c in _cards(ctx.get("snapshot") or {})
        if c.get("semantic_id")
    }


def _record_object(record: dict[str, Any], ref: str) -> dict[str, Any] | None:
    for o in record.get("semantic_objects") or []:
        if o.get("semantic_id") == ref:
            return o
    return None


def _find_card(
    record: dict[str, Any], cards: list[dict[str, Any]], ref: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """Locate a semantic object in a behavior snapshot.

    Prefers the provider-bound semantic id; falls back to
    identity+controller matching with uniqueness enforcement, because zone
    changes create new object incarnations (the graveyard card is not the
    identical bound object). Returns (card, violations).
    """
    for c in cards:
        if str(c.get("semantic_id")) == ref:
            return c, []
    shape = _record_object(record, ref)
    if shape is None:
        return None, [f"OBJECT_UNKNOWN_REF:{ref}"]
    cands = [
        c
        for c in cards
        if c.get("card_identity") == shape.get("card_identity")
        and c.get("controller") == shape.get("controller")
    ]
    if len(cands) != 1:
        return None, [f"OBJECT_IDENTITY_NONUNIQUE:{ref}:{len(cands)}"]
    return cands[0], []


def _script_refs(record: dict[str, Any], families: set[str], key: str) -> list[str]:
    refs = []
    for d in record.get("decision_script") or []:
        if d.get("decision_family") in families:
            sv = d["selection"]["semantic_value"]
            if isinstance(sv, dict) and isinstance(sv.get(key), str):
                refs.append(sv[key])
            elif key == "target" and isinstance(sv, str):
                refs.append(sv)
    return refs


def _check_bears_survive_bolt(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Grizzly Bears survives Lightning Bolt because Giant Growth resolved first."""
    cards = _cards(ctx.get("snapshot") or {})
    by_sem = _snapshot_cards(ctx)
    targets = _script_refs(record, {"target"}, "target")
    if len(targets) != 1:
        return [f"SURVIVOR_TARGET_NONUNIQUE:{targets}"]
    target = by_sem.get(targets[0])
    if target is None:
        return [f"SURVIVOR_TARGET_ABSENT:{targets[0]}"]
    bad = []
    if target.get("zone") != "battlefield":
        bad.append(f"SURVIVOR_NOT_ON_BATTLEFIELD:{target.get('zone')}")
    damage = int(target.get("damage", 0) or 0)
    toughness = int(target.get("toughness", 0) or 0)
    if damage <= 0:
        bad.append("SURVIVOR_TOOK_NO_DAMAGE")
    if toughness <= damage:
        bad.append(f"SURVIVOR_DID_NOT_SURVIVE:toughness={toughness}:damage={damage}")
    for ref in _script_refs(record, {"priority"}, "object"):
        card, find_bad = _find_card(record, cards, ref)
        bad.extend(find_bad)
        if card is not None and card.get("zone") != "graveyard":
            bad.append(f"SURVIVOR_CAST_OBJECT_NOT_RESOLVED:{ref}:{card.get('zone')}")
    for item in record.get("stack_state") or []:
        ref = item.get("source_semantic_id")
        card, find_bad = _find_card(record, cards, ref)
        bad.extend(find_bad)
        if card is not None and card.get("zone") != "graveyard":
            bad.append(f"SURVIVOR_STACK_OBJECT_NOT_RESOLVED:{ref}:{card.get('zone')}")
    return bad


def _by_semantic(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c.get("semantic_id"): c for c in _cards(snapshot) if c.get("semantic_id")}


def _check_selected_from_offered(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    matches = list((ctx or {}).get("matches") or [])
    script = list((record or {}).get("decision_script") or [])
    if len(matches) < len(script):
        return [f"DECISION_LOG_INCOMPLETE:{len(matches)}<{len(script)}"]
    bad = []
    for m in matches:
        if not m.get("offered_digest") or int(m.get("offered_count", 0)) < 1:
            bad.append(f"DECISION_NOT_FROM_OFFERED:{m.get('decision_id')}")
        if m.get("match_rule") in {"first_option", "random_option", "default_yes_no"}:
            bad.append(f"FORBIDDEN_MATCH_RULE:{m.get('match_rule')}")
    return bad


def _check_no_fallback_mechanism(mechanism: str) -> Checker:
    def check(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
        feed = list((ctx or {}).get("feed") or [])
        matches = list((ctx or {}).get("matches") or [])
        bad = [f"FALLBACK_USED:{mechanism}:{e}" for e in feed if mechanism in e]
        bad += [
            f"FALLBACK_MATCH_RULE:{mechanism}:{m.get('decision_id')}"
            for m in matches
            if mechanism in str(m.get("match_rule") or "")
        ]
        return bad

    return check


def _check_typed_fail_closed(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    stop = dict((ctx or {}).get("stop") or {})
    code = str(stop.get("code") or stop.get("stop_reason") or "")
    if "UNSUPPORTED_DISCRETIONARY_DECISION" not in code and "FAIL_CLOSED" not in code:
        return [f"NO_TYPED_FAIL_CLOSED_TERMINATION:{code!r}"]
    matches = list((ctx or {}).get("matches") or [])
    if [m for m in matches if m.get("submitted")]:
        return ["FAIL_CLOSED_BUT_OPTION_SUBMITTED"]
    return []


def _check_stack_empty(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    stack = ((ctx or {}).get("snapshot") or {}).get("stack")
    if stack is None:
        return ["STACK_STATE_ABSENT"]
    if list(stack):
        return [f"STACK_NOT_EMPTY:{len(stack)}"]
    return []


REGISTRY: dict[str, Checker] = {
    "Grizzly Bears survives Lightning Bolt because Giant Growth resolves first.": _check_bears_survive_bolt,
    "Selected cast action was among provider-offered legal options and no adapter legality was invented.": _check_selected_from_offered,
    "Stack is empty after both spells resolve.": _check_stack_empty,
    "Session/fixture terminates with typed unsupported discretionary-decision failure.": _check_typed_fail_closed,
    "No first_option behavior selected an option.": _check_no_fallback_mechanism("first_option"),
    "No random_option behavior selected an option.": _check_no_fallback_mechanism("random_option"),
    "No default_yes_no behavior selected an option.": _check_no_fallback_mechanism(
        "default_yes_no"
    ),
    "No internal_ai behavior selected an option.": _check_no_fallback_mechanism("internal_ai"),
    "No gui_default behavior selected an option.": _check_no_fallback_mechanism("gui_default"),
    "No silent_skip behavior selected an option.": _check_no_fallback_mechanism("silent_skip"),
    "No parent_class_fallback behavior selected an option.": _check_no_fallback_mechanism(
        "parent_class_fallback"
    ),
}

UNIMPLEMENTED_PREFIX = "POSTCONDITION_CHECKER_UNIMPLEMENTED"


def check_one(postcondition: str, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Check a single concrete postcondition string. Unknown templates FAIL."""
    fn = REGISTRY.get(postcondition) or REGISTRY.get(_norm(postcondition))
    if fn is None:
        return {"status": "FAIL", "violations": [f"{UNIMPLEMENTED_PREFIX}:{postcondition[:160]}"]}
    violations = fn(record, ctx)
    return {"status": "PASS" if not violations else "FAIL", "violations": violations}


def check_all(
    postconditions: list[str], record: dict[str, Any], ctx: dict[str, Any]
) -> dict[str, Any]:
    """Check every postcondition. PASS iff all pass."""
    detail = [check_one(p, record, ctx) for p in postconditions]
    bad = [v for d in detail for v in d["violations"]]
    return {"status": "PASS" if not bad else "FAIL", "violations": bad, "detail": detail}
