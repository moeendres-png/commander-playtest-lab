"""WS218 versioned tape schema: ``semantic-replay-tape/1.0.0`` (engine-neutral).

Top-level binds: schema_version, tape_id, source_lock, game_manifest,
rng_contract, initial_checkpoint, ordered steps, terminal checkpoint,
seal/digests. No wall-clock metadata enters semantic digests. No state
or outcome injection fields exist anywhere in this schema.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TAPE_SCHEMA_VERSION = "semantic-replay-tape/1.0.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TapeSourceLock(_Strict):
    lab_repository: str
    lab_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    lab_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    provider_identity: Literal["xmage"] = "xmage"
    engine_repository: str
    engine_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    engine_tree: str | None = None
    engine_version: str
    adapter_identity: str
    protocol_version: str
    decision_protocol_version: str
    protocol_schema_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rules_authority_identity: Literal["xmage"] = "xmage"
    oracle_snapshot_identity: str | None = None
    rulings_snapshot_identity: str | None = None
    commander_authority_identity: str | None = None


class TapeDeckRef(_Strict):
    deck_id: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    commander_names: tuple[str, ...]
    mainboard: tuple[str, ...]


class TapeSeatPrincipal(_Strict):
    seat: int = Field(ge=1, le=5)
    deck_id: str
    pilot_identity: str
    pilot_version: str
    decision_policy_version: str


class TapeGameManifest(_Strict):
    format: Literal["commander-ffa"] = "commander-ffa"
    player_count: int = Field(ge=2, le=5)
    seat_principals: tuple[TapeSeatPrincipal, ...]
    decks: tuple[TapeDeckRef, ...]
    commander_identities: tuple[str, ...]
    starting_life: int = Field(ge=1)
    starting_player_selection_contract: str
    mulligan_contract: str
    rules_seed: int = Field(ge=0)
    rules_seed_explicit_required: Literal[True] = True
    pilot_seed_derivation: str
    process_isolation_contract: str


class TapeRngContract(_Strict):
    root_rules_seed: int = Field(ge=0)
    rules_seed_explicit: Literal[True] = True
    require_explicit_seed: Literal[True] = True
    # Per-operation native RNG attribution is via call-count coordinates
    # plus state transition (the pinned engine exposes no stable per-op
    # kind tap without an engine change; results are never injected).
    attribution_model: str = "calls-coordinate-plus-state-transition"


class TapeCheckpoint(_Strict):
    rules_seed: int = Field(ge=0)
    rules_random_calls: int = Field(ge=0)
    turn_number: int = Field(ge=1)
    phase: str | None = None
    step: str | None = None
    decision_sequence: int = Field(ge=0)
    event_offset: int = Field(ge=0)
    semantic_state_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_state_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    principal_digests: dict[str, str]


class TapeReplayStep(_Strict):
    sequence: int = Field(ge=1)
    step_kind: Literal["decision", "lifecycle_concede"] = "decision"
    decision_class: str
    actor_principal: int = Field(ge=1, le=5)
    decision_revision: int = Field(ge=1, description="authoritative decision_offset")
    principal_observation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    legal_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    legal_set_size: int = Field(ge=0)
    # Recorded semantic choice: fingerprints of the chosen native options
    # (empty for numeric-only or empty-selection decisions) plus the
    # numeric choice where the authoritative context carries bounds.
    selected_fingerprints: tuple[str, ...] = ()
    selected_labels: tuple[str, ...] = ()
    numeric_choice: int | None = None
    numeric_min: int | None = None
    numeric_max: int | None = None
    rng_calls_before: int = Field(ge=0)
    rng_calls_after: int | None = None
    event_offset_before: int = Field(ge=0)
    event_offset_after: int | None = None
    event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    post_checkpoint_digest: str | None = None

    @model_validator(mode="after")
    def numeric_coherent(self) -> TapeReplayStep:
        bounds = (self.numeric_min is not None) or (self.numeric_max is not None)
        if bounds and (self.numeric_min is None or self.numeric_max is None):
            raise ValueError("numeric bounds must appear together")
        if self.numeric_choice is not None and not bounds:
            raise ValueError("numeric_choice without authoritative bounds")
        if bounds and self.numeric_choice is not None:
            assert self.numeric_min is not None and self.numeric_max is not None
            if not self.numeric_min <= self.numeric_choice <= self.numeric_max:
                raise ValueError("recorded numeric_choice outside recorded bounds")
        return self


class TapeTerminal(_Strict):
    terminal: Literal[True] = True
    turn_number: int = Field(ge=1)
    rules_random_calls: int = Field(ge=0)
    outcomes: tuple[dict[str, Any], ...]
    semantic_state_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_state_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SemanticReplayTape(_Strict):
    schema_version: Literal["semantic-replay-tape/1.0.0"] = TAPE_SCHEMA_VERSION
    tape_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_lock: TapeSourceLock
    game_manifest: TapeGameManifest
    rng_contract: TapeRngContract
    initial_checkpoint: TapeCheckpoint
    steps: tuple[TapeReplayStep, ...]
    terminal_checkpoint: TapeTerminal
    seal: dict[str, str]

    @model_validator(mode="after")
    def steps_ordered(self) -> SemanticReplayTape:
        sequences = [step.sequence for step in self.steps]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("replay steps must be densely ordered from 1")
        revisions = [step.decision_revision for step in self.steps if step.step_kind == "decision"]
        if revisions != sorted(revisions) or len(set(revisions)) != len(revisions):
            raise ValueError("decision revisions must be strictly increasing")
        if self.game_manifest.player_count != len(self.game_manifest.seat_principals):
            raise ValueError("seat_principals cardinality must equal player_count")
        if self.game_manifest.player_count != len(self.game_manifest.decks):
            raise ValueError("decks cardinality must equal player_count")
        return self


__all__ = [
    "TAPE_SCHEMA_VERSION",
    "SemanticReplayTape",
    "TapeCheckpoint",
    "TapeDeckRef",
    "TapeGameManifest",
    "TapeReplayStep",
    "TapeRngContract",
    "TapeSeatPrincipal",
    "TapeSourceLock",
    "TapeTerminal",
]
