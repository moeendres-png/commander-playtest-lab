"""Typed shapes for the XMage full-game bridge payloads.

These describe what the bridge sends (``json.loads`` of one JSONL reply) and what
the runner derives from it. Fields the peer controls are declared ``object`` and
narrowed with ``isinstance`` where they are read, so the fail-closed validation in
``full_game`` is unchanged; the types add key discipline, not trust. Nothing here
validates at runtime and no emitted JSON, field order or hash input changes.
"""

from __future__ import annotations

from typing import TypedDict


class BridgeRequestEnvelope(TypedDict):
    """One JSONL request written to the bridge (keys are dumped with sort_keys)."""

    protocol_version: str
    request_id: str
    engine: str
    message_type: str
    method: str
    payload: dict[str, object]
    params: dict[str, object]


class FullGameDeckPayload(TypedDict):
    deck_id: str
    deck_hash: str
    mainboard: list[str]
    commander_names: list[str]
    sideboard: list[str]


class StartEngineWire(TypedDict, total=False):
    lane: object


class ProviderIdentityWire(TypedDict, total=False):
    """``get_provider_version`` reply."""

    engine: object
    engine_commit: object
    engine_version: object


class FullGameLaneWire(TypedDict, total=False):
    lane: object
    decision_protocol_version: object
    min_players: object
    max_players: object
    evidence_class: object
    generic_capability_promotion: object
    one_game_per_process: object
    bit_exact_replay_validated: object


class CapabilitiesWire(TypedDict, total=False):
    """``get_capabilities`` reply."""

    full_game_lane: object
    capabilities: object


class FullGameResultWire(TypedDict, total=False):
    """``get_full_game_result`` reply."""

    evidence_class: object
    consumed_gameplay_evidence: object
    holdout_consumed: object
    official_campaign_eligible: object
    rules_authority: object
    decision_policy_authority: object
    bit_exact_replay_validated: object
    seed: object
    terminal: object
    outcomes: object
    transcript: object
    turn_number: object
    decision_count: object


class SemanticEventWire(TypedDict):
    sequence: object
    kind: object
    decision_class: object
    actor_seat: object
    prompt: object
    selected_option_types: object
    selected_option_labels: object
    numeric_choice: object


class SemanticOutcomeWire(TypedDict):
    seat: object
    life: object
    won: object
    lost: object
    left: object


class SemanticTranscript(TypedDict):
    """The replay-comparable projection of a result; its sha256 is a gate input."""

    seed: object
    turn_number: object
    decision_count: object
    events: list[SemanticEventWire]
    outcomes: list[SemanticOutcomeWire]


__all__ = [
    "BridgeRequestEnvelope",
    "CapabilitiesWire",
    "FullGameDeckPayload",
    "FullGameLaneWire",
    "FullGameResultWire",
    "ProviderIdentityWire",
    "SemanticEventWire",
    "SemanticOutcomeWire",
    "SemanticTranscript",
    "StartEngineWire",
]
