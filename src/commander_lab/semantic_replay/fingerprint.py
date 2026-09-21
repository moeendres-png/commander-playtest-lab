"""WS218 semantic option identity + state digests (engine-neutral).

Identity version: ``semantic-option-identity-1.0.0``.

Design (persisted in CHOSEN_REPLAY_ARCHITECTURE):
- Fingerprints derive ONLY from authoritative decision data already
  offered by the Rules Core (decision class, redacted label, semantic
  metadata subset, and public observation-joined characteristics).
- Raw process-local identities (option_id UUIDs, object UUIDs, game UUIDs,
  player UUIDs, ability original ids, stableId hashes thereof) NEVER enter
  a fingerprint directly. Where a decision references a game object, the
  fingerprint joins the referenced UUID to its PUBLIC projection in the
  current actor observation (name, controller seat, tapped, power/
  toughness, damage, counters, ability text for face-up permanents,
  zone occurrence) with UUIDs mapped to seat/occurrence keys. Two objects
  with identical public projections share a fingerprint: the resolver then
  sees >1 native match and FAILS CLOSED with CHOSEN_OPTION_AMBIGUOUS
  (never first-option).
- Name-only matching is insufficient and is NOT used alone: the
  fingerprint always includes the observation-joined projection hash
  where the decision references objects. Labels alone distinguish only
  non-object decisions (mulligan keep/mulligan, boolean value, choice
  key/text, pile name multisets, mana type/source, mode text, numeric
  values).
- Legal sets are multisets: the digest sorts fingerprints, preserving
  multiplicities. A different-but-similar set is a mismatch.
- Observation digests are principal-scoped: actor UUIDs/game UUIDs map to
  seat keys; opponent hands/mana never appear (structural invariant
  checked); granted_library appears only inside an entitled window and is
  digested as sorted names (never raw hidden order).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .canonicalization import (
    CANONICALIZATION_VERSION,
    canonical_hash,
    redact_choice_text,
    redact_text,
)

SEMANTIC_OPTION_IDENTITY_VERSION = "semantic-option-identity-1.0.0"
STATE_DIGEST_VERSION = "semantic-state-digest-1.0.0"

_OBJECT_CLASSES = frozenset(
    {"target", "choose_object", "target_amount", "declare_attacker", "declare_blocker"}
)

_UUID_LIKE_KEYS = frozenset(
    {
        "option_id",
        "object_id",
        "source_object_id",
        "ability_original_id",
        "card_id",
        "defender_id",
        "attacker_id",
        "blocker_id",
        "mode_id",
        "player_id",
        "actor_id",
        "controller_id",
        "owner_id",
        "game_id",
        "decision_id",
    }
)


def seat_map_from_pilot_state(pilot_state: dict[str, Any]) -> dict[str, int]:
    """Map raw player UUID -> 0-based seat from the actor view."""
    mapping: dict[str, int] = {}
    players = pilot_state.get("players")
    if not isinstance(players, list):
        return mapping
    for entry in players:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("player_id")
        seat = entry.get("seat")
        if isinstance(pid, str) and isinstance(seat, int):
            mapping[pid] = seat
    return mapping


def seat_of(mapping: dict[str, int], raw: object) -> Any:
    if isinstance(raw, str) and raw in mapping:
        return {"seat": mapping[raw]}
    return {"seat_unknown": redact_text(raw)}


def _public_permanent_key(item: dict[str, Any], mapping: dict[str, int]) -> dict[str, Any]:
    """Project one battlefield permanent to semantic content (no raw ids)."""
    counters = item.get("counters")
    counter_rows: list[dict[str, Any]] = []
    if isinstance(counters, list):
        for row in counters:
            if not isinstance(row, dict):
                continue
            counter_rows.append({"count": row.get("count"), "type": row.get("type")})
    counter_rows.sort(key=lambda r: (str(r.get("type")), str(r.get("count"))))
    abilities = item.get("abilities")
    ability_list = sorted(
        [str(a) for a in abilities if isinstance(a, str)] if isinstance(abilities, list) else []
    )
    controller = item.get("controller_id")
    return {
        "abilities": ability_list,
        "ability_count": item.get("ability_count"),
        "controller": seat_of(mapping, controller),
        "counters": counter_rows,
        "damage": item.get("damage"),
        "name": item.get("name"),
        "power": item.get("power"),
        "tapped": item.get("tapped"),
        "toughness": item.get("toughness"),
    }


def build_object_index(
    pilot_state: dict[str, Any], mapping: dict[str, int]
) -> dict[str, dict[str, Any]]:
    """Index raw object UUID -> semantic public projection.

    Covers battlefield permanents, graveyard/command/hand cards (by name +
    controller/owner seat + occurrence), stack objects (by name + position),
    and players (by seat). Granted-library cards are indexed when present.
    """
    index: dict[str, dict[str, Any]] = {}
    players = pilot_state.get("players")
    if isinstance(players, list):
        for entry in players:
            if not isinstance(entry, dict):
                continue
            pid = entry.get("player_id")
            if isinstance(pid, str):
                index[pid] = {"kind": "player", **seat_of(mapping, pid)}
            for zone in ("battlefield", "graveyard", "command", "hand"):
                items = entry.get(zone)
                if not isinstance(items, list):
                    continue
                # Occurrence among same-name cards in this zone for stability.
                seen: Counter[str] = Counter()
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    oid = item.get("object_id")
                    name = item.get("name")
                    if not isinstance(oid, str):
                        continue
                    if zone == "battlefield":
                        proj = _public_permanent_key(item, mapping)
                        proj["kind"] = "permanent"
                        proj["zone"] = zone
                    else:
                        key_name = str(name)
                        occurrence = seen[key_name]
                        seen[key_name] += 1
                        proj = {
                            "kind": "card",
                            "name": name,
                            "occurrence": occurrence,
                            "owner": seat_of(mapping, entry.get("player_id")),
                            "zone": zone,
                        }
                    index[oid] = proj
            granted = entry.get("granted_library")
            if isinstance(granted, list):
                seen_g: Counter[str] = Counter()
                for item in granted:
                    if not isinstance(item, dict):
                        continue
                    oid = item.get("object_id")
                    name = item.get("name")
                    if not isinstance(oid, str):
                        continue
                    key_name = str(name)
                    occurrence = seen_g[key_name]
                    seen_g[key_name] += 1
                    index[oid] = {
                        "kind": "card",
                        "name": name,
                        "occurrence": occurrence,
                        "owner": seat_of(mapping, entry.get("player_id")),
                        "zone": "granted_library",
                    }
    stack = pilot_state.get("stack")
    if isinstance(stack, list):
        for position, item in enumerate(stack):
            if not isinstance(item, dict):
                continue
            oid = item.get("object_id")
            if isinstance(oid, str):
                index[oid] = {
                    "kind": "stack_object",
                    "name": item.get("name"),
                    "position": position,
                }
    return index


def _resolve(maybe_id: object, index: dict[str, dict[str, Any]]) -> Any:
    if isinstance(maybe_id, str) and maybe_id in index:
        return index[maybe_id]
    if isinstance(maybe_id, str):
        # Unresolved UUID: record only its redacted presence, never the raw.
        # Such options can only match by label; duplicates fail closed.
        return {"unresolved_reference": True}
    return None


def option_fingerprint(
    option: dict[str, Any],
    pilot_state: dict[str, Any] | None = None,
    mapping: dict[str, int] | None = None,
    index: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Stable semantic fingerprint for one authoritative legal option."""
    option_type = str(option.get("option_type", "generic"))
    label = redact_text(option.get("label", option.get("option_id", "")))
    metadata = option.get("metadata")
    meta: dict[str, Any] = metadata if isinstance(metadata, dict) else {}
    if pilot_state is not None and mapping is None:
        mapping = seat_map_from_pilot_state(pilot_state)
    if mapping is None:
        mapping = {}
    if pilot_state is not None and index is None:
        index = build_object_index(pilot_state, mapping)
    if index is None:
        index = {}

    semantic: dict[str, Any] = {"option_type": option_type, "label": label}

    if option_type in {"keep", "mulligan"}:
        semantic["choice"] = option_type
    elif option_type == "boolean":
        semantic["value"] = bool(meta.get("value"))
    elif option_type == "choice":
        if "choice_key" in meta:
            semantic["choice_key"] = meta.get("choice_key")
            semantic["choice"] = redact_choice_text(meta.get("choice"))
        else:
            semantic["choice"] = redact_choice_text(meta.get("choice", label))
    elif option_type == "pile":
        cards = meta.get("cards", [])
        names: list[str] = []
        if isinstance(cards, list):
            for card in cards:
                if isinstance(card, dict) and "name" in card:
                    names.append(str(card.get("name")))
        names.sort()
        semantic["cards"] = names
        semantic["card_count"] = len(names)
    elif option_type == "mana_pool":
        semantic["mana_type"] = str(meta.get("mana_type", "")).lower()
    elif option_type in {
        "mana_ability",
        "activated_ability",
        "cast_ability",
        "play_land_ability",
        "triggered_ability",
    }:
        semantic["ability_type"] = str(meta.get("ability_type", "")).lower()
        semantic["source_name"] = redact_text(meta.get("source_name", ""))
        semantic["mana_ability"] = bool(meta.get("mana_ability", False))
        # Disambiguate copies by joining the source card to its stable
        # hand/zone occurrence (duplicate-name systemic identity). Raw
        # UUIDs never enter; the joined projection does.
        for source_key in ("source_object_id", "card_id"):
            if meta.get(source_key) is not None:
                semantic["source"] = _resolve(meta.get(source_key), index)
                break
    elif option_type == "replacement_effect":
        semantic["source_name"] = redact_text(meta.get("source_name", ""))
        # xmage_key/index are positional/engine-internal; semantic content
        # is the redacted label + source. Index excluded (order is not
        # semantic); duplicates with identical label+source fail closed.
    elif option_type == "mode":
        semantic["mode_text"] = redact_choice_text(label)
    elif option_type in {"target", "choice", "target_amount"}:
        # option_id IS the target UUID for these classes.
        target_id = option.get("option_id")
        semantic["target"] = _resolve(target_id, index)
        semantic["target_name"] = meta.get("name", label)
    elif option_type == "hold_attacker":
        semantic["attacker"] = _resolve(meta.get("object_id"), index)
        semantic["attacker_name"] = meta.get("name", label)
    elif option_type == "declare_attacker":
        semantic["attacker"] = _resolve(meta.get("object_id"), index)
        semantic["attacker_name"] = meta.get("name", label)
        semantic["defender"] = seat_of(mapping, meta.get("defender_id"))
        semantic["defender_name"] = redact_text(
            _defender_name(meta.get("defender_id"), pilot_state)
        )
    elif option_type == "declare_blocker":
        semantic["blocker"] = _resolve(meta.get("blocker_id"), index)
        semantic["attacker"] = _resolve(meta.get("attacker_id"), index)
    elif option_type in {"pass_priority", "cancel_mana_payment"}:
        semantic["choice"] = option_type
    else:
        # Generic fallback: include only redacted label + non-UUID metadata
        # scalars. Never include raw UUID fields.
        safe_meta: dict[str, Any] = {}
        for key, value in meta.items():
            if key in _UUID_LIKE_KEYS:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_meta[key] = redact_text(value)
        semantic["metadata"] = safe_meta

    semantic["_identity_version"] = SEMANTIC_OPTION_IDENTITY_VERSION
    semantic["_canonicalization"] = CANONICALIZATION_VERSION
    return canonical_hash(semantic)


def _defender_name(defender_id: object, pilot_state: dict[str, Any] | None) -> object:
    if not isinstance(defender_id, str) or pilot_state is None:
        return defender_id
    players = pilot_state.get("players")
    if isinstance(players, list):
        for entry in players:
            if isinstance(entry, dict) and entry.get("player_id") == defender_id:
                return f"seat:{entry.get('seat')}"
    return "unknown-defender"


def legal_set_fingerprints(
    legal_options: list[dict[str, Any]],
    pilot_state: dict[str, Any] | None = None,
) -> list[str]:
    mapping = seat_map_from_pilot_state(pilot_state) if pilot_state else {}
    index = build_object_index(pilot_state, mapping) if pilot_state else {}
    prints = [
        option_fingerprint(option, pilot_state, mapping, index)
        for option in legal_options
        if isinstance(option, dict)
    ]
    prints.sort()
    return prints


def legal_set_digest(
    legal_options: list[dict[str, Any]],
    pilot_state: dict[str, Any] | None = None,
) -> str:
    """Multiset digest: sorted fingerprints, multiplicities preserved."""
    return canonical_hash(
        {
            "fingerprints": legal_set_fingerprints(legal_options, pilot_state),
            "count": len(legal_options),
            "identity_version": SEMANTIC_OPTION_IDENTITY_VERSION,
            "canonicalization": CANONICALIZATION_VERSION,
        }
    )


def canonical_actor_view(pilot_state: dict[str, Any]) -> dict[str, Any]:
    """Principal-scoped canonical observation (UUIDs -> seat/occurrence keys)."""
    mapping = seat_map_from_pilot_state(pilot_state)
    view: dict[str, Any] = {
        "actor": seat_of(mapping, pilot_state.get("actor_id")),
        "active_player": seat_of(mapping, pilot_state.get("active_player_id")),
        "priority_player": seat_of(mapping, pilot_state.get("priority_player_id")),
        "phase": pilot_state.get("phase"),
        "step": pilot_state.get("step"),
        "turn_number": pilot_state.get("turn_number"),
    }
    players_out: list[dict[str, Any]] = []
    players = pilot_state.get("players")
    if isinstance(players, list):
        for entry in sorted(
            [e for e in players if isinstance(e, dict)],
            key=lambda e: int(e.get("seat", 0)),
        ):
            row: dict[str, Any] = {
                "exile_count": entry.get("exile_count"),
                "graveyard_count": entry.get("graveyard_count"),
                "hand_count": entry.get("hand_count"),
                "has_lost": entry.get("has_lost"),
                "has_won": entry.get("has_won"),
                "is_actor": entry.get("is_actor"),
                "library_count": entry.get("library_count"),
                "life": entry.get("life"),
                "player": seat_of(mapping, entry.get("player_id")),
                "poison_counters": entry.get("poison_counters"),
                "seat": entry.get("seat"),
            }
            battlefield = entry.get("battlefield")
            if isinstance(battlefield, list):
                perms = [
                    _public_permanent_key(item, mapping)
                    for item in battlefield
                    if isinstance(item, dict)
                ]
                perms.sort(
                    key=lambda p: (
                        str(p.get("name")),
                        str(p.get("power")),
                        str(p.get("toughness")),
                        str(p.get("tapped")),
                        str(p.get("damage")),
                    )
                )
                row["battlefield"] = perms
            graveyard = entry.get("graveyard")
            if isinstance(graveyard, list):
                # Graveyard is ordered in paper; preserve order but drop ids.
                row["graveyard"] = [
                    {"name": item.get("name")} for item in graveyard if isinstance(item, dict)
                ]
            command = entry.get("command")
            if isinstance(command, list):
                cmds = [{"name": item.get("name")} for item in command if isinstance(item, dict)]
                cmds.sort(key=lambda c: str(c.get("name")))
                row["command"] = cmds
            if entry.get("is_actor") is True:
                hand = entry.get("hand")
                if isinstance(hand, list):
                    names = sorted(
                        str(item.get("name"))
                        for item in hand
                        if isinstance(item, dict) and item.get("name")
                    )
                    row["hand"] = [{"name": name} for name in names]
                if isinstance(entry.get("mana_pool"), dict):
                    row["mana_pool"] = dict(entry["mana_pool"])
                row["land_plays_remaining"] = entry.get("land_plays_remaining")
                granted = entry.get("granted_library")
                if isinstance(granted, list) and granted:
                    names_g = sorted(
                        str(item.get("name"))
                        for item in granted
                        if isinstance(item, dict) and item.get("name")
                    )
                    row["granted_library"] = [{"name": n} for n in names_g]
            players_out.append(row)
    view["players"] = players_out
    stack = pilot_state.get("stack")
    if isinstance(stack, list):
        # Stack order is semantic: preserve order, drop raw ids.
        view["stack"] = [{"name": item.get("name")} for item in stack if isinstance(item, dict)]
    commander_status = pilot_state.get("commander_status")
    if isinstance(commander_status, list):
        rows: list[dict[str, Any]] = []
        for item in commander_status:
            if not isinstance(item, dict):
                continue
            damage = item.get("commander_damage_to_player")
            damage_rows: list[dict[str, Any]] = []
            if isinstance(damage, list):
                for deal in damage:
                    if not isinstance(deal, dict):
                        continue
                    damage_rows.append(
                        {
                            "player": seat_of(mapping, deal.get("player_id")),
                            "total": deal.get("total"),
                        }
                    )
                damage_rows.sort(key=lambda d: str(d["player"]))
            rows.append(
                {
                    "casts_from_command": item.get("casts_from_command"),
                    "commander_damage_to_player": damage_rows,
                    "name": item.get("name"),
                    "owner": seat_of(mapping, item.get("owner_id")),
                }
            )
        rows.sort(key=lambda r: (str(r["owner"]), str(r["name"])))
        view["commander_status"] = rows
    view["_canonicalization"] = CANONICALIZATION_VERSION
    return view


def principal_observation_digest(pilot_state: dict[str, Any]) -> str:
    return canonical_hash(
        {
            "observation": canonical_actor_view(pilot_state),
            "digest_version": STATE_DIGEST_VERSION,
            "canonicalization": CANONICALIZATION_VERSION,
        }
    )


def public_state_digest(pilot_state: dict[str, Any]) -> str:
    """Public-only digest (no hand, mana, or granted library)."""
    view = canonical_actor_view(pilot_state)
    public_players: list[dict[str, Any]] = []
    for entry in view.get("players", []):
        public_players.append(
            {
                k: entry.get(k)
                for k in (
                    "battlefield",
                    "command",
                    "exile_count",
                    "graveyard",
                    "graveyard_count",
                    "hand_count",
                    "has_lost",
                    "has_won",
                    "is_actor",
                    "library_count",
                    "life",
                    "player",
                    "poison_counters",
                    "seat",
                )
            }
        )
    return canonical_hash(
        {
            "active_player": view.get("active_player"),
            "commander_status": view.get("commander_status"),
            "phase": view.get("phase"),
            "players": public_players,
            "priority_player": view.get("priority_player"),
            "stack": view.get("stack"),
            "step": view.get("step"),
            "turn_number": view.get("turn_number"),
            "digest_version": STATE_DIGEST_VERSION,
            "canonicalization": CANONICALIZATION_VERSION,
        }
    )


def internal_checkpoint_digest(
    *,
    pilot_state: dict[str, Any],
    legal_options: list[dict[str, Any]],
    rules_seed: int,
    rules_random_calls: int,
    turn_number: int,
    decision_offset: int,
) -> str:
    return canonical_hash(
        {
            "calls": rules_random_calls,
            "decision_offset": decision_offset,
            "legal_set": legal_set_fingerprints(legal_options, pilot_state),
            "observation": canonical_actor_view(pilot_state),
            "seed": rules_seed,
            "turn_number": turn_number,
            "digest_version": STATE_DIGEST_VERSION,
            "canonicalization": CANONICALIZATION_VERSION,
        }
    )


__all__ = [
    "SEMANTIC_OPTION_IDENTITY_VERSION",
    "STATE_DIGEST_VERSION",
    "build_object_index",
    "canonical_actor_view",
    "internal_checkpoint_digest",
    "legal_set_digest",
    "legal_set_fingerprints",
    "option_fingerprint",
    "principal_observation_digest",
    "public_state_digest",
    "seat_map_from_pilot_state",
]
