from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .common import FrozenModel, utc_now

RUN_IDENTITY_SCHEMA_VERSION = "1.0.0"


class IdentityStatus(StrEnum):
    PRESENT = "present"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    MISSING_REQUIRED = "missing_required"


class CanonicalInputStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    HISTORICAL_REPLAY = "historical_replay"


class RunIdentity(FrozenModel):
    schema_version: str = RUN_IDENTITY_SCHEMA_VERSION

    software_commit: str | None = None
    software_tree: str | None = None
    package_version: str | None = None

    deck_hashes: dict[str, str] = Field(default_factory=dict)
    commander_configuration_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    inventory_source_id: str | None = None
    inventory_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    opponent_profile_ids: tuple[str, ...] = ()
    opponent_profile_hashes: dict[str, str] = Field(default_factory=dict)
    opponent_ensemble_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    pilot_name: str | None = None
    pilot_version: str | None = None
    pilot_parameter_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    policy_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    scenario_set_id: str | None = None
    scenario_set_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    pod_size: int | None = Field(default=None, ge=1, le=10)
    seat: int | None = Field(default=None, ge=0, le=10)
    turn_order_policy: str | None = None

    seed: int | None = Field(default=None, ge=0)
    seed_set_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    simulation_config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_version: str | None = None

    engine_mode: str | None = None
    engine_provider: str | None = None
    engine_provider_version_or_pin: str | None = None
    engine_capability_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tactical_fixture_version: str | None = None

    data_source_manifest_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    component_status: dict[str, IdentityStatus] = Field(default_factory=dict)
    canonical_input_status: CanonicalInputStatus = CanonicalInputStatus.CURRENT
    stale_reasons: tuple[str, ...] = ()
    historical_replay: bool = False

    created_at: datetime = Field(default_factory=utc_now)
    run_identity_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_statuses(self) -> RunIdentity:
        required_components = {
            name
            for name, status in self.component_status.items()
            if status is IdentityStatus.MISSING_REQUIRED
        }
        if required_components and not self.historical_replay:
            raise ValueError(
                "run identity contains missing required components: "
                + ", ".join(sorted(required_components))
            )
        if (
            self.historical_replay
            and self.canonical_input_status is not CanonicalInputStatus.HISTORICAL_REPLAY
        ):
            raise ValueError("historical replay must use canonical_input_status=historical_replay")
        if self.stale_reasons and self.canonical_input_status is CanonicalInputStatus.CURRENT:
            raise ValueError("stale reasons require stale or historical_replay status")
        return self

    def semantic_payload(self) -> dict[str, Any]:
        return self.model_dump(
            mode="python",
            exclude={"created_at", "run_identity_hash"},
            exclude_none=False,
        )
