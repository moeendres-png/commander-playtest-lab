"""WS-42 provider translation for immutable WS-41 v1.0.3 records.

This layer reuses the proven WS-39 bootstrap/deck construction but extends only
provider-facing state-load metadata needed by the v1.0.3 denominator. It does
not calculate Magic legality, commander tax, replacement outcomes, or player
choices.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS39 = HERE.parents[0] / "ws39-xmage-successor"
sys.path.insert(0, str(WS39))

import canonical_v102 as base  # noqa: E402
from successor_contract_v103 import requested_state_digest, requested_state_projection  # noqa: E402


def _find_zone_entry(scenario: dict[str, Any], semantic_id: str) -> tuple[dict[str, Any], str]:
    matches: list[tuple[dict[str, Any], str]] = []
    for player in scenario["players"]:
        for zone, items in player["zones"].items():
            for item in items:
                if item.get("semantic_id") == semantic_id:
                    matches.append((item, zone))
    if len(matches) != 1:
        raise ValueError(f"WS42_SCENARIO_OBJECT_MAPPING_NOT_UNIQUE:{semantic_id}:matches={len(matches)}")
    return matches[0]


def _immutable_rules_seed(record: dict[str, Any]) -> int:
    randomness = record.get("rules_randomness")
    if not isinstance(randomness, dict):
        raise ValueError(f"WS42_RULES_RANDOMNESS_MISSING:{record.get('fixture_id')}")
    seed = randomness.get("rules_seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError(f"WS42_RULES_SEED_INVALID:{record.get('fixture_id')}:{seed!r}")
    return seed


def deck_and_scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Translate one v1.0.3 record into native-load inputs without rules shortcuts."""
    bootstrap = copy.deepcopy(record)

    # XMage models a reveal as visibility state over a card still physically in
    # its native zone. WS-39 did not admit the semantic pseudo-zone `revealed`.
    # Bootstrap that card through library binding, then the WS-42 overlay moves
    # it into the native Revealed registry and normalizes it back to `revealed`.
    revealed_ids: set[str] = set()
    for obj in bootstrap.get("semantic_objects") or []:
        if obj.get("zone") == "revealed":
            revealed_ids.add(str(obj["semantic_id"]))
            obj["zone"] = "library"

    decks, scenario = base.deck_and_scenario(bootstrap)
    scenario["scenario_id"] = f"WS42-{record['fixture_id']}"

    # The qualification-session constructor and XmageWs26Scenario.apply both
    # consume the top-level scenario seed. It is Rules RNG execution metadata,
    # so v1.0.3 must use the immutable contract seed exactly rather than the
    # legacy digest-derived seed used by the v1.0.2 translator.
    scenario["seed"] = _immutable_rules_seed(record)

    # Always restore the exact immutable v1.0.3 request after the WS-39 bootstrap
    # translation. The bootstrap may alter provider-only staging (for example a
    # revealed pseudo-zone), but it must never alter the semantic request used
    # for construction comparison.
    scenario["successor_requested_state"] = requested_state_projection(record)
    scenario["successor_requested_state_digest"] = requested_state_digest(record)
    if scenario["successor_requested_state_digest"] != record["requested_state_digest"]:
        raise ValueError("WS41_V103_REQUESTED_STATE_DIGEST_MISMATCH")
    if scenario["successor_requested_state"].get("rules_randomness") != record.get("rules_randomness"):
        raise ValueError(f"WS42_REQUESTED_RANDOMNESS_MUTATED:{record.get('fixture_id')}")

    # Preserve player-state load instructions that were intentionally absent
    # from the narrower WS-39 translator.
    by_player = {p["player_id"]: p for p in record["players"]}
    for scenario_player in scenario["players"]:
        pid = f"P{scenario_player['seat']}"
        source = by_player[pid]
        scenario_player["starting_life"] = int(source["starting_life"])
        scenario_player["poison"] = int(source["poison"])
        scenario_player["lost"] = bool(source["lost"])
        scenario_player["eliminated"] = bool(source["eliminated"])
        scenario_player["zones"].setdefault("revealed", [])

    source_by_id = {o["semantic_id"]: o for o in record.get("semantic_objects") or []}
    for semantic_id, source in source_by_id.items():
        if source.get("zone") == "command":
            continue
        entry, current_zone = _find_zone_entry(scenario, semantic_id)
        if "counters" in source:
            entry["counters"] = copy.deepcopy(source.get("counters") or {})
        if source.get("attached_to") is not None:
            entry["attached_to"] = source["attached_to"]
        if semantic_id in revealed_ids:
            if current_zone != "library":
                raise ValueError(f"WS42_REVEALED_BOOTSTRAP_ZONE_MISMATCH:{semantic_id}:{current_zone}")
            for player in scenario["players"]:
                library = player["zones"].get("library") or []
                found = [item for item in library if item.get("semantic_id") == semantic_id]
                if found:
                    if len(found) != 1:
                        raise ValueError(f"WS42_REVEALED_BOOTSTRAP_DUPLICATE:{semantic_id}")
                    library.remove(found[0])
                    player["zones"]["revealed"].append(found[0])
                    break

    # The following are execution-state load instructions. The Java overlay
    # must construct and independently read each through XMage-native state;
    # these objects are never accepted as construction proof by themselves.
    scenario["ws42_combat_state"] = copy.deepcopy(record.get("combat_state") or {})
    scenario["ws42_extra_turn_creation"] = copy.deepcopy(record.get("extra_turn_creation") or [])
    scenario["ws42_elimination_trigger"] = copy.deepcopy(record.get("elimination_trigger") or {})
    scenario["ws42_zone_move_event"] = copy.deepcopy(record.get("zone_move_event") or {})
    scenario["ws42_knowledge_state"] = copy.deepcopy(record.get("knowledge_state") or {})
    scenario["ws42_commander_damage_matrix"] = copy.deepcopy(
        (record.get("commander_state") or {}).get("commander_damage_matrix") or []
    )
    return decks, scenario
