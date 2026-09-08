#!/usr/bin/env python3
"""Freshly audit the exact 19 WS-46 construction-failure shapes in WS-47 v1.0.5.

This is contract/source evidence only. It grants no construction or behavior
credit. The v1.0.4 materialization is used solely as provenance for the exact
19 identities and to prove those requested states are unchanged in v1.0.5.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PRIOR_19 = (
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "WS05-CMD-MULL-2",
    "WS05-CMD-MULL-4",
    "HIDDEN_05",
    "HIDDEN_06",
    "HIDDEN_10",
    "HIDDEN_11",
    "WS05-MP-TURN-3",
    "WS05-MP-TURN-5",
    "WS05-MP-ELIM-OWNED-3",
    "WS05-MP-ELIM-CONTROL-3",
    "WS05-MP-ELIM-STACK-3",
    "WS05-MP-ELIM-PRIO-3",
    "WS05-MP-ELIM-TURN-3",
    "WS05-MP-ELIM-5",
)

NATURAL = set(PRIOR_19[:7])
FACE_DOWN_EXILE = {"HIDDEN_05", "HIDDEN_06"}
LIBRARY_RANGE = {"HIDDEN_10", "HIDDEN_11"}
EXTRA_TURN = {"WS05-MP-TURN-3", "WS05-MP-TURN-5"}
ELIMINATION = set(PRIOR_19[-6:])

STATE_KEYS = (
    "execution_entry_mode",
    "players",
    "deck_state",
    "commander_state",
    "semantic_objects",
    "temporal_state",
    "knowledge_state",
    "rules_randomness",
    "combat_state",
    "stack_state",
    "continuous_rules_effects",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
    "setup_validation",
)


def fail(label: str) -> None:
    raise SystemExit(f"WS49_PRIOR19_AUDIT_FAIL:{label}")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = value.get("records")
    if not isinstance(rows, list):
        fail(f"records:{path}")
    return value


def by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in contract["records"]:
        fid = row.get("fixture_id")
        if not isinstance(fid, str) or fid in out:
            fail(f"fixture-id:{fid}")
        out[fid] = row
    return out


def projection(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in STATE_KEYS if key in row}


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def walk(node: Any):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def contains_dict(node: Any, required: dict[str, Any]) -> bool:
    return any(
        isinstance(item, dict) and all(item.get(k) == v for k, v in required.items())
        for item in walk(node)
    )


def assert_natural(fid: str, row: dict[str, Any]) -> None:
    if row.get("execution_entry_mode") != "NATURAL_GAME_START":
        fail(f"natural-entry-mode:{fid}:{row.get('execution_entry_mode')}")
    decks = row.get("deck_state")
    if not isinstance(decks, list):
        fail(f"natural-deck-state-not-list:{fid}")
    players = row.get("players")
    if not isinstance(players, list):
        fail(f"natural-players-not-list:{fid}")
    expected_players = {p.get("player_id") for p in players if isinstance(p, dict)}
    if None in expected_players or len(expected_players) != len(players):
        fail(f"natural-player-ids:{fid}")
    by_player: dict[str, dict[str, Any]] = {}
    for deck in decks:
        if not isinstance(deck, dict):
            fail(f"natural-deck-entry:{fid}")
        player = deck.get("player_id")
        if not isinstance(player, str) or player in by_player:
            fail(f"natural-deck-player:{fid}:{player!r}")
        by_player[player] = deck
    if set(by_player) != expected_players:
        fail(f"natural-deck-player-set:{fid}:{sorted(by_player)}:{sorted(expected_players)}")

    commander_state = row.get("commander_state")
    commanders = commander_state.get("commanders") if isinstance(commander_state, dict) else None
    if not isinstance(commanders, list):
        fail(f"natural-commanders-not-list:{fid}")
    commander_by_id = {
        item.get("commander_id"): item
        for item in commanders
        if isinstance(item, dict) and isinstance(item.get("commander_id"), str)
    }
    if len(commander_by_id) != len(commanders):
        fail(f"natural-commander-id-uniqueness:{fid}")

    randomness = row.get("rules_randomness")
    channels = randomness.get("channels") if isinstance(randomness, dict) else None
    if not isinstance(channels, list):
        fail(f"natural-rng-channels:{fid}")

    for player in sorted(expected_players):
        deck = by_player[player]
        library = deck.get("library_template")
        if library is not None:
            if library != {"card_identity": "Mountain", "count": 99}:
                fail(f"natural-library-template:{fid}:{player}:{library!r}")
            if deck.get("opening_hand_size") != 7:
                fail(f"natural-opening-hand:{fid}:{player}:{deck.get('opening_hand_size')!r}")
            shuffle_channel = deck.get("shuffle_channel")
            if shuffle_channel != f"library_shuffle:{player}" or shuffle_channel not in channels:
                fail(f"natural-shuffle-binding:{fid}:{player}:{shuffle_channel!r}")
            commander_ids = deck.get("commander_ids")
            if not isinstance(commander_ids, list) or not commander_ids:
                fail(f"natural-commander-ids:{fid}:{player}:{commander_ids!r}")
            for commander_id in commander_ids:
                commander = commander_by_id.get(commander_id)
                if commander is None:
                    fail(f"natural-commander-ref:{fid}:{player}:{commander_id}")
                if commander.get("owner") != player:
                    fail(f"natural-commander-owner:{fid}:{player}:{commander_id}")
                if commander.get("card_identity") != "Rograkh, Son of Rohgahh":
                    fail(f"natural-commander-identity:{fid}:{player}:{commander_id}:{commander.get('card_identity')!r}")
            continue

        # WS-47 deliberately retains the direct deck-list representation for
        # two Commander mulligan records.  Validate it exactly; do not pretend
        # it has the newer template-only fields.
        if deck.get("main_deck") != [{"card_identity": "Mountain", "count": 99}]:
            fail(f"natural-main-deck:{fid}:{player}:{deck.get('main_deck')!r}")
        if deck.get("commander") != [{"card_identity": "Rograkh, Son of Rohgahh", "count": 1}]:
            fail(f"natural-direct-commander:{fid}:{player}:{deck.get('commander')!r}")
        if deck.get("exact_card_count") != 100:
            fail(f"natural-direct-card-count:{fid}:{player}:{deck.get('exact_card_count')!r}")
        if channels != ["INITIAL_LIBRARY_SHUFFLE"] or randomness.get("seed_binding") != "SCENARIO_SEED":
            fail(f"natural-initial-shuffle-binding:{fid}:{player}:{randomness!r}")
        matching = [
            commander for commander in commander_by_id.values()
            if commander.get("owner") == player and commander.get("card_identity") == "Rograkh, Son of Rohgahh"
        ]
        if len(matching) != 1:
            fail(f"natural-direct-commander-mapping:{fid}:{player}:matches={len(matching)}")


def assert_face_down_exile(fid: str, row: dict[str, Any]) -> None:
    objects = row.get("semantic_objects")
    if not isinstance(objects, list):
        fail(f"semantic-objects-shape:{fid}")
    target = next((x for x in objects if isinstance(x, dict) and x.get("semantic_id") == "obj:hidden-hand"), None)
    if target is None:
        fail(f"hidden-hand-object-missing:{fid}")
    required = {
        "identity": "Demonic Tutor",
        "owner": "P2",
        "controller": "P2",
        "zone": "exile",
        "face_down": True,
    }
    # Historical source used identity while current materialization uses
    # card_identity. Accept only the exact immutable card value, never a
    # provider substitution.
    identity = target.get("card_identity", target.get("identity"))
    if identity != required["identity"]:
        fail(f"hidden-hand-identity:{fid}:{identity!r}")
    for key in ("owner", "controller", "zone", "face_down"):
        expected = required[key]
        if target.get(key) != expected:
            fail(f"hidden-hand-{key}:{fid}:{target.get(key)!r}")


def assert_library_range(fid: str, row: dict[str, Any]) -> None:
    knowledge = row.get("knowledge_state")
    if knowledge is None:
        fail(f"knowledge-state-missing:{fid}")
    expected = (
        {"viewer": "P1", "player": "P1", "start": 0, "count": 2, "ordered": True}
        if fid == "HIDDEN_10"
        else {"viewer": "P1", "player": "P2", "start": 0, "count": 2, "ordered": True, "before_event": "shuffle"}
    )
    if not contains_dict(knowledge, expected):
        fail(f"library-range-shape:{fid}")


def assert_extra_turn(fid: str, row: dict[str, Any]) -> None:
    turns = row.get("extra_turn_creation")
    if not isinstance(turns, list) or len(turns) != 2:
        fail(f"extra-turn-count:{fid}")
    expected = (
        {"player": "P2", "source": "obj:mp-time-warp", "sequence": 1},
        {"player": "P3", "source": "obj:mp-nexus", "sequence": 2},
    )
    for item, want in zip(turns, expected):
        if not isinstance(item, dict) or any(item.get(k) != v for k, v in want.items()):
            fail(f"extra-turn-shape:{fid}:{item!r}")
        if "resolution_sequence" in item:
            fail(f"extra-turn-superseded-field:{fid}")


def assert_elimination(fid: str, row: dict[str, Any]) -> None:
    trigger = row.get("elimination_trigger")
    if not isinstance(trigger, dict):
        fail(f"elimination-trigger-shape:{fid}")
    if set(trigger) != {"player", "reason"} or trigger.get("reason") != "life_total_0":
        fail(f"elimination-trigger-value:{fid}:{trigger!r}")
    if "condition" in trigger:
        fail(f"elimination-superseded-condition:{fid}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v104", required=True, type=Path)
    parser.add_argument("--v105", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    old = by_id(load(args.v104))
    new = by_id(load(args.v105))
    rows: list[dict[str, Any]] = []

    if len(PRIOR_19) != 19 or len(set(PRIOR_19)) != 19:
        fail("prior19-identity-denominator")

    for fid in PRIOR_19:
        if fid not in old or fid not in new:
            fail(f"missing-fixture:{fid}")
        before = old[fid]
        after = new[fid]
        before_digest = before.get("requested_state_digest")
        after_digest = after.get("requested_state_digest")
        if before_digest != after_digest:
            fail(f"requested-state-changed:{fid}:{before_digest}:{after_digest}")
        if canonical_sha(projection(after)) != after_digest:
            fail(f"v105-requested-digest-recompute:{fid}")

        if fid in NATURAL:
            assert_natural(fid, after)
            klass = "NATURAL_GAME_START"
        elif fid in FACE_DOWN_EXILE:
            assert_face_down_exile(fid, after)
            klass = "FACE_DOWN_EXILE"
        elif fid in LIBRARY_RANGE:
            assert_library_range(fid, after)
            klass = "LIBRARY_RANGE"
        elif fid in EXTRA_TURN:
            assert_extra_turn(fid, after)
            klass = "EXTRA_TURN_CREATION"
        elif fid in ELIMINATION:
            assert_elimination(fid, after)
            klass = "ELIMINATION_TRIGGER"
        else:
            fail(f"unclassified:{fid}")

        rows.append({
            "fixture_id": fid,
            "failure_shape_class": klass,
            "requested_state_digest_v104": before_digest,
            "requested_state_digest_v105": after_digest,
            "requested_state_unchanged": True,
            "v105_projection": projection(after),
        })

    out = {
        "schema": "commander-lab.ws49-prior19-v105-shape-audit/1.0.1",
        "historical_runtime_credit_imported": 0,
        "prior_failure_denominator": 19,
        "all_19_present": True,
        "all_19_requested_states_unchanged_v104_to_v105": True,
        "shape_class_counts": {
            "NATURAL_GAME_START": 7,
            "FACE_DOWN_EXILE": 2,
            "LIBRARY_RANGE": 2,
            "EXTRA_TURN_CREATION": 2,
            "ELIMINATION_TRIGGER": 6,
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("WS49_PRIOR19_V105_SHAPE_AUDIT=PASS")
    print("WS49_PRIOR19_DENOMINATOR=19")
    print("WS49_PRIOR19_UNCHANGED=19/19")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
