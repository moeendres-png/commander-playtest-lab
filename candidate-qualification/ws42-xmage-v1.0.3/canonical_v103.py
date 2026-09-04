"""WS-42 provider translation for immutable WS-41 v1.0.3 records.

This layer reuses the proven WS-39 bootstrap/deck construction but extends only
provider-facing state-load metadata actually required by each v1.0.3 record.
It does not calculate Magic legality, commander tax, replacement outcomes, or
player choices.
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


def _bind_execution_seed(record: dict[str, Any], scenario: dict[str, Any]) -> tuple[int, str]:
    """Apply the exact immutable Rules-RNG seed semantics.

    WS-41 has two distinct forms:
    * fixed ``rules_seed``: the provider execution seed must equal that integer;
    * ``seed_binding == SCENARIO_SEED``: the contract intentionally does not
      prescribe a numeric seed. The already deterministic provider scenario seed
      is retained and Rules RNG is bound to that value.

    This function changes provider execution metadata only. It never changes the
    immutable ``rules_randomness`` object embedded in the requested state.
    """
    randomness = record.get("rules_randomness")
    if not isinstance(randomness, dict):
        raise ValueError(f"WS42_RULES_RANDOMNESS_MISSING:{record.get('fixture_id')}")

    fixed = randomness.get("rules_seed")
    if isinstance(fixed, int) and not isinstance(fixed, bool):
        scenario["seed"] = fixed
        return fixed, "CONTRACT_FIXED_RULES_SEED"

    if fixed is not None:
        raise ValueError(f"WS42_RULES_SEED_INVALID:{record.get('fixture_id')}:{fixed!r}")
    if randomness.get("seed_binding") != "SCENARIO_SEED":
        raise ValueError(f"WS42_RULES_SEED_BINDING_MISSING:{record.get('fixture_id')}")

    seed = scenario.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError(f"WS42_PROVIDER_SCENARIO_SEED_INVALID:{record.get('fixture_id')}:{seed!r}")
    return seed, "CONTRACT_SCENARIO_SEED_BINDING"


def _has_knowledge_grants(record: dict[str, Any]) -> bool:
    for viewer in (record.get("knowledge_state") or {}).get("viewer_states") or []:
        if any(
            viewer.get(key) not in (None, {}, [], "", False)
            for key in (
                "face_down_look_permissions",
                "known_library_ranges",
                "known_object_identities",
                "temporary_permissions",
                "invalidation_conditions",
            )
        ):
            return True
    return False


def _put_nonempty(scenario: dict[str, Any], key: str, value: Any) -> None:
    if value not in (None, {}, [], "", False):
        scenario[key] = copy.deepcopy(value)


def _bootstrap_record(record: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """Return provider-staging input for the legacy WS39 translator only.

    The returned digest is never WS41 authority. It exists solely because the
    inherited translator self-checks any staging mutation before producing deck
    and scenario objects. The immutable v1.0.3 request is restored afterwards.
    """
    bootstrap = copy.deepcopy(record)
    revealed_ids: set[str] = set()
    for obj in bootstrap.get("semantic_objects") or []:
        if obj.get("zone") == "revealed":
            revealed_ids.add(str(obj["semantic_id"]))
            obj["zone"] = "library"
    bootstrap["requested_state_digest"] = base.requested_state_digest(bootstrap)
    return bootstrap, revealed_ids


def bootstrap_digest_for_translation(record: dict[str, Any]) -> str:
    """Expose the non-authoritative staging digest for audit evidence only."""
    bootstrap, _ = _bootstrap_record(record)
    return str(bootstrap["requested_state_digest"])


def deck_and_scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Translate one v1.0.3 record into native-load inputs without rules shortcuts."""
    bootstrap, revealed_ids = _bootstrap_record(record)

    # XMage represents public reveal state through a native visibility registry,
    # not a physical `revealed` Zone enum. The only semantic staging mutation is
    # therefore revealed -> library for native card binding. Its recalculated
    # digest above is translator-internal and is never compared as WS41 proof.
    decks, scenario = base.deck_and_scenario(bootstrap)
    scenario["scenario_id"] = f"WS42-{record['fixture_id']}"

    # Fixed Rules seeds are copied exactly. SCENARIO_SEED-bound records retain
    # the deterministic provider scenario seed created by the bootstrap layer.
    # No WS42-only audit field is inserted into the native scenario because its
    # parser deliberately rejects unknown keys.
    _bind_execution_seed(record, scenario)

    # Restore the exact immutable v1.0.3 request immediately after staging.
    # WS-42 construction proof explicitly ignores the inherited whole-object
    # echo and uses lower-level native readback instead.
    scenario["successor_requested_state"] = requested_state_projection(record)
    scenario["successor_requested_state_digest"] = requested_state_digest(record)
    if scenario["successor_requested_state_digest"] != record["requested_state_digest"]:
        raise ValueError("WS41_V103_REQUESTED_STATE_DIGEST_MISMATCH")
    if scenario["successor_requested_state"].get("rules_randomness") != record.get("rules_randomness"):
        raise ValueError(f"WS42_REQUESTED_RANDOMNESS_MUTATED:{record.get('fixture_id')}")

    source_by_id = {o["semantic_id"]: o for o in record.get("semantic_objects") or []}
    for semantic_id, source in source_by_id.items():
        if source.get("zone") == "command":
            continue
        entry, current_zone = _find_zone_entry(scenario, semantic_id)
        # Empty counters are the semantic default and must not widen the native
        # scenario schema. Only material counters require the WS-42 extension.
        if source.get("counters"):
            entry["counters"] = copy.deepcopy(source["counters"])
        if source.get("attached_to") is not None:
            entry["attached_to"] = source["attached_to"]
        if semantic_id in revealed_ids:
            if current_zone != "library":
                raise ValueError(f"WS42_REVEALED_BOOTSTRAP_ZONE_MISMATCH:{semantic_id}:{current_zone}")
            moved = False
            for player in scenario["players"]:
                library = player["zones"].get("library") or []
                found = [item for item in library if item.get("semantic_id") == semantic_id]
                if not found:
                    continue
                if len(found) != 1 or moved:
                    raise ValueError(f"WS42_REVEALED_BOOTSTRAP_DUPLICATE:{semantic_id}")
                library.remove(found[0])
                player["zones"].setdefault("revealed", []).append(found[0])
                moved = True
            if not moved:
                raise ValueError(f"WS42_REVEALED_BOOTSTRAP_NOT_FOUND:{semantic_id}")

    # Provider-extension keys are emitted only when the immutable record really
    # requires the dimension. This preserves the native parser's rejectUnknown
    # boundary and prevents empty WS-42 metadata from silently widening it.
    _put_nonempty(scenario, "ws42_combat_state", record.get("combat_state"))
    _put_nonempty(scenario, "ws42_extra_turn_creation", record.get("extra_turn_creation"))
    _put_nonempty(scenario, "ws42_elimination_trigger", record.get("elimination_trigger"))
    _put_nonempty(scenario, "ws42_zone_move_event", record.get("zone_move_event"))
    if _has_knowledge_grants(record):
        scenario["ws42_knowledge_state"] = copy.deepcopy(record["knowledge_state"])
    _put_nonempty(
        scenario,
        "ws42_commander_damage_matrix",
        (record.get("commander_state") or {}).get("commander_damage_matrix"),
    )
    return decks, scenario
