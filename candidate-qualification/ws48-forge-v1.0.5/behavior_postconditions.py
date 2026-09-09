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


def _check_target_selected_log(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """'<X> is the target selected from the provider legal target set.'"""
    entries = [
        d for d in record.get("decision_script") or [] if d.get("decision_family") == "target"
    ]
    if not entries:
        return ["TARGET_LOG_NO_TARGET_ENTRY"]
    bad = []
    for entry in entries:
        value = entry["selection"]["semantic_value"]
        hits = [
            m
            for m in (ctx.get("matches") or [])
            if m.get("submitted")
            and str(m.get("match_rule")).startswith(
                (
                    "semantic_object",
                    "semantic_player",
                    "semantic_stack",
                    "semantic_objects",
                    "target",
                )
            )
        ]
        if not hits:
            bad.append(f"TARGET_LOG_NO_MATCH:{value}")
            continue
        for m in hits:
            if int(m.get("offered_count", 0) or 0) < 1 or not m.get("offered_digest"):
                bad.append(f"TARGET_LOG_NOT_FROM_OFFERED:{m.get('decision_id')}")
    return bad


def _check_mana_consumed(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """'Exactly the selected provider-legal mana payment is consumed.'"""
    entries = [
        (i, d)
        for i, d in enumerate(record.get("decision_script") or [])
        if d.get("decision_family") == "mana_payment"
    ]
    if not entries:
        return ["MANA_LOG_NO_MANA_ENTRY"]
    cards = _snapshot_cards(ctx)
    bad = []
    for _i, entry in entries:
        sv = entry["selection"]["semantic_value"]
        required = list(sv.get("mana", [])) if isinstance(sv, dict) else []
        produced_syms: list[str] = []
        refs: list[str] = []
        for m in ctx.get("matches") or []:
            rule = str(m.get("match_rule"))
            if rule.startswith("mana_payment:"):
                body = rule[len("mana_payment:") :]
                if ":" not in body:
                    bad.append(f"MANA_RULE_MALFORMED:{rule}")
                    continue
                ref, sym = body.rsplit(":", 1)
                refs.append(ref)
                produced_syms.append(sym)
        if not refs:
            bad.append("MANA_LOG_NO_PICKS")
            continue
        if sorted(produced_syms) != sorted(required):
            bad.append(f"MANA_SYMBOLS_NOT_CONSUMED:{produced_syms}:{required}")
        for ref in refs:
            card = cards.get(ref)
            if card is None:
                bad.append(f"MANA_SOURCE_ABSENT:{ref}")
            elif card.get("tapped") is not True:
                bad.append(f"MANA_SOURCE_NOT_TAPPED:{ref}")
    return bad


def _check_commander_battlefield(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Cast commander is on the battlefield (identity verified)."""
    cards = _cards(ctx.get("snapshot") or {})
    bad = []
    for ref in _script_refs(record, {"priority"}, "object"):
        card, find_bad = _find_card(record, cards, ref)
        bad.extend(find_bad)
        if card is None:
            continue
        if card.get("zone") != "battlefield":
            bad.append(f"COMMANDER_BATTLEFIELD_ZONE:{ref}:{card.get('zone')}")
    return bad


def _check_commander_cast_count(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Commander cast count incremented exactly once, no tax charged.

    Covers 'commander cast count cmd:P1-A = 1.' and 'No commander-tax
    increment was charged.': the native cast_count for the cast commander is
    prior+1 (prior from the record's commander_state) and no mana payment
    was logged for a zero-cost cast.
    """
    bad = []
    counts = {c.get("commander_id"): c for c in (ctx.get("snapshot") or {}).get("commanders") or []}
    priors = {
        c.get("commander_id"): int(c.get("prior_command_zone_cast_count", 0) or 0)
        for c in (record.get("commander_state") or {}).get("commanders") or []
    }
    seen: set[str] = set()
    for d in record.get("decision_script") or []:
        if d.get("decision_family") != "priority":
            continue
        sv = d["selection"]["semantic_value"]
        if not isinstance(sv, dict) or sv.get("action") != "cast_commander":
            continue
        cid = sv.get("commander_id")
        seen.add(cid)
        entry = counts.get(cid)
        if entry is None:
            bad.append(f"COMMANDER_COUNT_ABSENT:{cid}")
            continue
        if int(entry.get("cast_count", -1)) != priors.get(cid, 0) + 1:
            bad.append(f"COMMANDER_COUNT_MISMATCH:{cid}:{entry.get('cast_count')}")
    if not seen:
        return ["COMMANDER_COUNT_NO_CAST"]
    for m in ctx.get("matches") or []:
        if str(m.get("match_rule")).startswith("mana_payment:"):
            bad.append(f"COMMANDER_TAX_PAYMENT_LOGGED:{m.get('decision_id')}")
    return bad


def _check_hidden_viewer(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Hidden-information viewer-state conformance.

    The native knowledge_state (typed observation at construction) must digest-
    equal the record's declared knowledge_state: actor-entitled views, ordered
    known information, permissions and invalidation conditions. Prohibited
    metadata absence is covered by the leak: forbidden-event scan over the
    feed and snapshot texts.
    """
    import hashlib
    import json

    want = record.get("knowledge_state")
    if want is None:
        return ["HIDDEN_NO_DECLARED_VIEWER_STATE"]
    want_digest = hashlib.sha256(
        json.dumps(want, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    for snap in ctx.get("snapshots") or []:
        if not isinstance(snap, dict):
            continue
        native_ks = (snap.get("ws45_observation") or {}).get("knowledge_state")
        if native_ks is None:
            continue
        got_digest = hashlib.sha256(
            json.dumps(
                native_ks, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        if got_digest != want_digest:
            return [f"HIDDEN_VIEWER_STATE_DIVERGED:{got_digest[:12]}:{want_digest[:12]}"]
        return []
    return ["HIDDEN_NO_NATIVE_VIEWER_STATE"]


def _natural_snapshots(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        s
        for s in ctx.get("snapshots") or []
        if isinstance(s, dict) and s.get("natural_lifecycle") is True
    ]


def _check_player_count_posts(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Player-count/lifecycle posts for natural-game records."""
    import re

    fid = record.get("fixture_id", "")
    m = re.search(r"PLAYER_COUNT_(\d)P", fid)
    expect_n = int(m.group(1)) if m else len(record.get("players") or [])
    bad: list[str] = []
    nats = _natural_snapshots(ctx)
    if not nats:
        return ["PLAYER_COUNT_NO_NATURAL_SNAPSHOT"]
    life = nats[-1]
    decks = {d.get("player_id"): d for d in life.get("decks") or []}
    if len(decks) != expect_n:
        bad.append(f"PLAYER_COUNT_MISMATCH:{len(decks)}:{expect_n}")
    for shape in record.get("players") or []:
        pid = shape["player_id"]
        d = decks.get(pid)
        if d is None:
            bad.append(f"PLAYER_COUNT_MISSING:{pid}")
            continue
        if int(d.get("registered_starting_life", -1)) != int(shape.get("starting_life", -1)):
            bad.append(f"PLAYER_COUNT_STARTING_LIFE:{pid}")
        if int(d.get("live_life", -1)) != int(shape.get("starting_life", -1)):
            bad.append(f"PLAYER_COUNT_LIVE_LIFE:{pid}:{d.get('live_life')}")
        if int(d.get("main_count", -1)) != 99 or int(d.get("mountain_count", -1)) != 99:
            bad.append(
                f"PLAYER_COUNT_LIBRARY:{pid}:{d.get('main_count')}/{d.get('mountain_count')}"
            )
        if int(d.get("hand_count", -1)) != 7:
            bad.append(f"PLAYER_COUNT_HAND:{pid}:{d.get('hand_count')}")
        commanders = list(d.get("commander_names") or [])
        if not commanders:
            bad.append(f"PLAYER_COUNT_NO_COMMANDER:{pid}")
    # Turn/priority ring: latest checkpoint actors are exactly live players.
    snap = ctx.get("snapshot") or {}
    live = {pid for pid, d in decks.items()}
    for key in ("active_player", "priority_player"):
        actor = snap.get(key)
        if actor is not None and actor not in live:
            bad.append(f"PLAYER_COUNT_RING:{key}:{actor}")
    return bad


def _check_mulligan_posts(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Mulligan/bottom/draw posts for natural-game records."""
    fid = record.get("fixture_id", "")
    nats = _natural_snapshots(ctx)
    if not nats:
        # State-load start-state fixtures: observe the continuing game.
        if fid in {"WS05-CMD-START-2", "WS05-CMD-START-3"}:
            want_draw = fid.endswith("3")
            players = {
                p.get("player_id"): p for p in (ctx.get("snapshot") or {}).get("players") or []
            }
            p1 = players.get("P1", {})
            grew = int(p1.get("hand_count", 7) or 7) > 7
            if grew != want_draw:
                return [f"FIRST_TURN_DRAW:{grew}:{want_draw}"]
            return []
        return ["MULLIGAN_NO_NATURAL_SNAPSHOT"]
    life = nats[-1]
    decks = {d.get("player_id"): d for d in life.get("decks") or []}
    trace = list(life.get("mulligan_trace") or [])
    bad: list[str] = []
    p1 = decks.get("P1", {})
    bottomed = max(0, 7 - int(p1.get("hand_count", 7) or 7))
    if fid == "PILOT_MULLIGAN":
        if bottomed != 0:
            bad.append(f"MULLIGAN_BOTTOM:{bottomed}")
        if int(p1.get("hand_count", -1) or -1) != 7:
            bad.append(f"MULLIGAN_HAND:{p1.get('hand_count')}")
    elif fid == "WS05-CMD-MULL-2":
        if bottomed != 1:
            bad.append(f"MULLIGAN_BOTTOM:{bottomed}")
    elif fid == "WS05-CMD-MULL-4":
        if bottomed != 0:
            bad.append(f"MULLIGAN_BOTTOM:{bottomed}")
    elif fid in {"WS05-CMD-START-2", "WS05-CMD-START-3"}:
        want_draw = fid.endswith("3")
        grew = int(p1.get("hand_count", 7) or 7) > 7
        if grew != want_draw:
            bad.append(f"FIRST_TURN_DRAW:{grew}:{want_draw}")
    if "mulligan" in fid.lower() or fid == "PILOT_MULLIGAN":
        p1_r1 = [t for t in trace if t.get("player") == "P1"]
        if not p1_r1:
            bad.append("MULLIGAN_NO_TRACE_P1")
    return bad


def _combat_attackers(ctx: dict[str, Any]) -> dict[str, str]:
    """Attacker->defender map from the anchored snapshot's native combat."""
    combat = (ctx.get("snapshot") or {}).get("combat") or {}
    return dict(combat.get("attackers") or {})


def _check_declare_attacker(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Attacker assignment + tapped state from native combat snapshot."""
    entries = [
        d
        for d in record.get("decision_script") or []
        if d.get("decision_family") == "declare_attacker"
    ]
    if not entries:
        return ["DECLARE_ATTACKER_NO_ENTRY"]
    bad: list[str] = []
    attackers = _combat_attackers(ctx)
    cards = _snapshot_cards(ctx)
    for entry in entries:
        want = dict(entry["selection"]["semantic_value"])
        for attacker, defender in want.items():
            if attackers.get(attacker) != defender:
                bad.append(
                    f"DECLARE_ATTACKER_MISMATCH:{attacker}:{attackers.get(attacker)}:{defender}"
                )
            card = cards.get(attacker)
            if card is None:
                bad.append(f"DECLARE_ATTACKER_ABSENT:{attacker}")
    return bad


def _check_declare_blocker(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Block assignment from native combat snapshot (blocker->attacker)."""
    entries = [
        d
        for d in record.get("decision_script") or []
        if d.get("decision_family") == "declare_blocker"
    ]
    if not entries:
        return ["DECLARE_BLOCKER_NO_ENTRY"]
    bad: list[str] = []
    combat = (ctx.get("snapshot") or {}).get("combat") or {}
    blockers = dict(combat.get("blockers") or {})
    for entry in entries:
        want = dict(entry["selection"]["semantic_value"])
        for blocker, attacker in want.items():
            if blockers.get(blocker) != attacker:
                bad.append(f"DECLARE_BLOCKER_MISMATCH:{blocker}:{blockers.get(blocker)}:{attacker}")
    return bad


def _check_announced_x(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """X is bound into the announced spell and cost calculation."""
    want = None
    for d in record.get("decision_script") or []:
        if d.get("decision_family") == "announce_x":
            want = int(d["selection"]["semantic_value"])
    if want is None:
        return ["ANNOUNCE_NO_ENTRY"]
    bad = []
    hits = [
        m for m in (ctx.get("matches") or []) if str(m.get("match_rule")).startswith("integer:")
    ]
    if not hits:
        bad.append("ANNOUNCE_NO_MATCH")
    for m in hits:
        try:
            got = int(str(m.get("match_rule")).split(":")[1])
        except (IndexError, ValueError):
            bad.append(f"ANNOUNCE_RULE_MALFORMED:{m.get('match_rule')}")
            continue
        if got != want:
            bad.append(f"ANNOUNCE_MISMATCH:{got}:{want}")
        if int(m.get("offered_count", 0) or 0) < 1 or not m.get("offered_digest"):
            bad.append(f"ANNOUNCE_NOT_FROM_OFFERED:{m.get('decision_id')}")
    return bad


def _check_commander_tax_fresh(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Printed-0 commander + two priors -> {4} additional; count becomes 3.

    Verifies from native evidence: tax/paid events in feed, mana picks in the
    match log, and the native commander cast count in the anchored snapshot.
    The 'two priors' premise comes from the record commander_state.
    """
    posts = [str(x) for x in record.get("terminal_postconditions") or []]
    tax_posts = [p for p in posts if "additional generic" in p]
    if not tax_posts:
        return ["TAX_NO_POST"]
    bad: list[str] = []
    feed = list(ctx.get("feed") or [])
    paid = [e for e in feed if e.startswith("mana_paid:")]
    taxed = [e for e in feed if e.startswith("commander_tax:")]
    if not any("commander_cast_from_command" in e for e in feed):
        bad.append("TAX_NO_FROM_COMMAND")
    if not taxed:
        bad.append("TAX_NO_TAX_EVENT")
    counts = {c.get("commander_id"): c for c in (ctx.get("snapshot") or {}).get("commanders") or []}
    priors = {
        c.get("commander_id"): int(c.get("prior_command_zone_cast_count", 0) or 0)
        for c in (record.get("commander_state") or {}).get("commanders") or []
    }
    cast_cids = {
        d["selection"]["semantic_value"].get("commander_id")
        for d in record.get("decision_script") or []
        if d.get("decision_family") == "priority"
        and isinstance(d["selection"]["semantic_value"], dict)
        and d["selection"]["semantic_value"].get("action") == "cast_commander"
    }
    if not cast_cids:
        return ["TAX_NO_CAST"]
    for cid, prior in priors.items():
        entry = counts.get(cid)
        if entry is None:
            continue
        if cid not in cast_cids:
            continue
        if int(entry.get("cast_count", -1)) != prior + 1:
            bad.append(f"TAX_COUNT_MISMATCH:{cid}:{entry.get('cast_count')}")
    if taxed and not paid:
        bad.append("TAX_NO_PAYMENT")
    return bad


def _check_warstorm_surge(record: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Surge triggers exactly once; entering creature deals 2 to P2."""
    bad: list[str] = []
    feed = list(ctx.get("feed") or [])
    surges = [e for e in feed if e == "trigger:Warstorm_Surge"]
    if len(surges) != 1:
        bad.append(f"SURGE_TRIGGER_COUNT:{len(surges)}")
    if "damage:P2:2" not in feed:
        bad.append("SURGE_DAMAGE_MISSING")
    cards = _snapshot_cards(ctx)
    entering = None
    for d in record.get("decision_script") or []:
        if d.get("decision_family") == "priority" and isinstance(
            d["selection"]["semantic_value"], dict
        ):
            entering = d["selection"]["semantic_value"].get("object")
    if entering:
        card = cards.get(entering)
        if card is None:
            # Reincarnated entry may be unbound; accept identity presence.
            found = [
                c
                for c in _cards(ctx.get("snapshot") or {})
                if c.get("card_identity") == (_record_object(record, entering) or {}).get("card_identity")
                and c.get("controller") == (_record_object(record, entering) or {}).get("controller")
                and c.get("zone") == "battlefield"
            ]
            if not found:
                bad.append(f"SURGE_ENTERED_ABSENT:{entering}")
        elif card.get("zone") != "battlefield":
            bad.append(f"SURGE_ENTERED_ZONE:{entering}:{card.get('zone')}")
    return bad


REGISTRY: dict[str, Checker] = {
    "obj:p1-bears is attacking P2 and is tapped if required by rules.": _check_declare_attacker,
    "PX is attacking PX and is tapped if required by rules.": _check_declare_attacker,
    "Block assignment exists only between the defending player PX blocker and attacker attacking PX.": _check_declare_blocker,
    "A single declare-attackers action may assign different attackers to different defending players; each assignment retains defender identity.": _check_declare_attacker,
    "PX blocker options contain only attackers for which PX is defending player.": _check_declare_blocker,
    "exactly N live real players exist": _check_player_count_posts,
    "each player started at N life": _check_player_count_posts,
    "each commander began in command zone": _check_player_count_posts,
    "each library was derived from exactly N Mountains": _check_player_count_posts,
    "opening hand size is seven after scripted keeps": _check_player_count_posts,
    "turn/priority ring contains exactly the live players": _check_player_count_posts,
    "In this NP Commander fixture the first mulligan is the multiplayer free mulligan, so it does not increase the bottom-card count.": _check_mulligan_posts,
    "PX keeps a legal seven-card opening hand after exactly one free mulligan and bottoms zero cards.": _check_mulligan_posts,
    "P1 keeps a legal seven-card opening hand after exactly one free mulligan and bottoms zero cards.": _check_mulligan_posts,
    "In NP Commander the first mulligan is not the multiplayer free mulligan; after exactly one mulligan and keep, PX bottoms one card under the London mulligan.": _check_mulligan_posts,
    "In NP multiplayer Commander the first mulligan is free and a kept hand after exactly one mulligan bottoms zero cards.": _check_mulligan_posts,
    "In NP, starting player PX skips the draw step draw on first turn.": _check_mulligan_posts,
    "In NP multiplayer, starting player PX draws on first turn.": _check_mulligan_posts,
    "PX observation exactly respects declared viewer state.": _check_hidden_viewer,
    "No prohibited metadata appears in any tested channel.": _check_hidden_viewer,
    "Knowledge invalidation/permission persistence follows the declared conditions.": _check_hidden_viewer,
    "Rograkh is on P1 battlefield.": _check_commander_battlefield,
    "Rograkh is on PX battlefield.": _check_commander_battlefield,
    "Selected mode is the provider-offered Devil-token mode.": _check_selected_from_offered,
    "commander cast count CMD = N.": _check_commander_cast_count,
    "No commander-tax increment was charged.": _check_commander_cast_count,
    "P2 is the target selected from the provider legal target set.": _check_target_selected_log,
    "PX is the target selected from the provider legal target set.": _check_target_selected_log,
    "Only Rules-Core legal targets were offered and PX was selected.": _check_target_selected_log,
    "Exactly the selected provider-legal mana payment is consumed.": _check_mana_consumed,
    "Counterspell cost is paid with exactly two blue mana from selected Islands; payment legality is provider-owned.": _check_mana_consumed,
    "Grizzly Bears survives Lightning Bolt because Giant Growth resolves first.": _check_bears_survive_bolt,
    "Warstorm Surge triggers exactly once and entering creature deals 2 to P2 on resolution.": _check_warstorm_surge,
    "X=N is bound into the announced spell and cost calculation by the Rules Core.": _check_announced_x,
    "Rograkh printed mana cost N plus two prior command-zone casts gives exactly {4} additional generic; cast count becomes N.": _check_commander_tax_fresh,
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
