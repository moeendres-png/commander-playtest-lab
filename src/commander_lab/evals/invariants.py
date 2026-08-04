from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from commander_lab.storage import canonical_json_bytes


ACTION_EVENT_TYPES = frozenset(
    {
        "turn_started",
        "cards_drawn",
        "land_played",
        "pilot_decision",
        "spell_cast",
        "commander_cast",
        "counter_resolved",
        "protection_resolved",
        "board_protected",
        "combat_damage",
        "graveyard_hate_resolved",
        "recursion_resolved",
        "finisher_resolved",
        "sacrifice_event",
    }
)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def event_log_sha256(events: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for event in events:
        digest.update(canonical_json_bytes(event))
        digest.update(b"\n")
    return digest.hexdigest()


def validate_event_log(events: list[dict[str, Any]]) -> tuple[str, ...]:
    errors: list[str] = []
    if not events:
        return ("event log is empty",)
    sequences = [event.get("sequence") for event in events]
    if sequences != list(range(len(events))):
        errors.append("event sequences are not contiguous from zero")
    game_ids = {event.get("game_id") for event in events}
    if len(game_ids) != 1:
        errors.append("event log contains multiple game ids")
    for index, event in enumerate(events):
        if event.get("estimate_type") != "structural_model_estimates":
            errors.append(f"event {index} lacks structural_model_estimates label")
        expected_suffix = f":{index:06d}"
        if not str(event.get("event_id", "")).endswith(expected_suffix):
            errors.append(f"event {index} has inconsistent event_id")
    if sum(event.get("event_type") == "game_started" for event in events) != 1:
        errors.append("event log must contain exactly one game_started event")
    if sum(event.get("event_type") == "game_ended" for event in events) != 1:
        errors.append("event log must contain exactly one game_ended event")
    if events[-1].get("event_type") != "game_ended":
        errors.append("game_ended must be the final event")

    eliminated_at: dict[str, int] = {}
    checkpoint_count = 0
    for event in events:
        event_type = str(event.get("event_type"))
        actor = event.get("actor_id")
        sequence = int(event.get("sequence", -1))
        if event_type == "player_eliminated" and actor:
            eliminated_at[str(actor)] = sequence
        elif actor in eliminated_at and event_type in ACTION_EVENT_TYPES:
            errors.append(
                f"eliminated player {actor} acted at event {sequence}: {event_type}"
            )
        if event_type != "state_checkpoint":
            continue
        checkpoint_count += 1
        players = event.get("payload", {}).get("players", [])
        if not players:
            errors.append(f"checkpoint at event {sequence} has no players")
            continue
        for snapshot in players:
            player_id = snapshot.get("player_id", "unknown")
            counts = snapshot.get("counts", {})
            if any(not isinstance(value, int) or value < 0 for value in counts.values()):
                errors.append(f"negative or noninteger zone count for {player_id}")
            total = sum(counts.values())
            if total != snapshot.get("total_physical_cards"):
                errors.append(f"zone total does not match stored total for {player_id}")
            if total != snapshot.get("expected_deck_cards"):
                errors.append(f"card conservation failed for {player_id}: {total}")
            if snapshot.get("current_multiset_hash") != snapshot.get("expected_multiset_hash"):
                errors.append(f"card multiset changed for {player_id}")
    if checkpoint_count < 2:
        errors.append("event log lacks sufficient state checkpoints")
    return tuple(errors)
