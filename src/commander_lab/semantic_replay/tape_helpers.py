"""WS218 tape helpers shared by recorder/consumer (no legality, no RNG)."""

from __future__ import annotations

from typing import Any

from .canonicalization import canonical_hash, redact_text
from .fingerprint import (
    build_object_index,
    option_fingerprint,
    seat_map_from_pilot_state,
)


def actor_principal_from_decision(decision: dict[str, Any]) -> int:
    """1-based principal seat for a native decision (fail closed)."""
    seat = decision.get("seat")
    pilot_state = decision.get("pilot_state")
    if isinstance(pilot_state, dict) and isinstance(pilot_state.get("seat"), int):
        if isinstance(seat, int) and seat != pilot_state["seat"]:
            raise ValueError("decision seat disagrees with pilot_state seat")
        seat = pilot_state["seat"]
    if not isinstance(seat, int):
        raise ValueError("decision is missing integer seat")
    principal = seat + 1
    if not 1 <= principal <= 5:
        raise ValueError(f"actor principal out of range: {principal}")
    return principal


def selected_fingerprints_for_response(
    decision: dict[str, Any],
    selected_option_ids: list[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Fingerprints + redacted labels for the chosen native options."""
    pilot_state = decision.get("pilot_state")
    if not isinstance(pilot_state, dict):
        raise ValueError("decision is missing pilot_state")
    mapping = seat_map_from_pilot_state(pilot_state)
    index = build_object_index(pilot_state, mapping)
    by_id = {
        str(option.get("option_id")): option
        for option in decision.get("legal_options", [])
        if isinstance(option, dict) and option.get("option_id") is not None
    }
    prints: list[str] = []
    labels: list[str] = []
    for option_id in selected_option_ids:
        option = by_id.get(str(option_id))
        if option is None:
            raise ValueError(f"selected option is not in the legal set: {option_id}")
        prints.append(option_fingerprint(option, pilot_state, mapping, index))
        labels.append(str(redact_text(option.get("label", ""))))
    return tuple(prints), tuple(labels)


def event_digest_for_step(
    *,
    sequence: int,
    decision_class: str,
    actor_principal: int,
    selected_fingerprints: tuple[str, ...],
    numeric_choice: int | None,
    rng_calls_before: int,
    rng_calls_after: int | None,
    turn_before: int,
    turn_after: int | None,
    observation_digest: str,
    post_digest: str | None,
) -> str:
    """Semantic event digest (material transitions only, no debug strings)."""
    return canonical_hash(
        {
            "actor_principal": actor_principal,
            "decision_class": decision_class,
            "numeric_choice": numeric_choice,
            "observation_digest": observation_digest,
            "post_digest": post_digest,
            "rng_calls_after": rng_calls_after,
            "rng_calls_before": rng_calls_before,
            "selected_fingerprints": sorted(selected_fingerprints),
            "sequence": sequence,
            "turn_after": turn_after,
            "turn_before": turn_before,
        }
    )


def deck_content_digest(
    *, deck_id: str, commander_names: tuple[str, ...] | list[str], mainboard: tuple[str, ...] | list[str]
) -> str:
    """Tamper-evident domain digest over deck contents.

    Canonical input is (deck_id, sorted commanders, sorted mainboard).
    The recorder validates provided deck hashes against this digest;
    the consumer recomputes it from the manifest to detect hash/content
    tampering even when the bridge echoes a tampered hash.
    """
    return canonical_hash(
        {
            "commander_names": sorted(str(c) for c in commander_names),
            "deck_id": str(deck_id),
            "mainboard": sorted(str(c) for c in mainboard),
        }
    )


__all__ = [
    "actor_principal_from_decision",
    "deck_content_digest",
    "event_digest_for_step",
    "selected_fingerprints_for_response",
]
