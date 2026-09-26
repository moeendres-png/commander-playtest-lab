from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from commander_lab.models import GameState
from commander_lab.models.common import FrozenModel
from commander_lab.storage.atomic import atomic_write_json
from commander_lab.storage.hashing import sha256_value


class ScenarioFixture(FrozenModel):
    schema_version: int = 1
    scenario_id: str
    description: str
    seed: int = Field(ge=0)
    initial_state: GameState
    known_library_tops: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    expected_properties: dict[str, Any] = Field(default_factory=dict)
    fixture_hash: str | None = None

    @model_validator(mode="after")
    def validate_hash(self) -> ScenarioFixture:
        value = self.model_dump(mode="json", exclude={"fixture_hash"})
        expected = sha256_value(value)
        if self.fixture_hash is not None and self.fixture_hash != expected:
            raise ValueError("scenario fixture hash mismatch")
        object.__setattr__(self, "fixture_hash", expected)
        return self


def save_scenario_fixture(path: str, fixture: ScenarioFixture) -> None:
    atomic_write_json(path, fixture.model_dump(mode="json"))
