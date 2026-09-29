"""An echoed seed is not an engine acknowledgement.

PB-09 found this on the pristine upstream Forge candidate: the bridge installs a
seed through the engine's public deterministic-simulation setter, then reports
the value back. The value matches the request, so value-equality alone produced
``ACKNOWLEDGED_ENGINE_SEED`` with ``rng_credit=true`` even though that engine
exposes no seed accessor at all and therefore cannot prove what it accepted.

Credit now requires an explicit engine-side confirmation in the same response.
These tests pin that: echo without confirmation is uncontrolled, confirmation
with a matching value is acknowledged, and a confirmed-but-divergent value is
still uncontrolled.
"""

from __future__ import annotations

import pytest

from commander_lab.qualification.current_boundary.game_driver import (
    _engine_confirmed_seed,
)
from commander_lab.qualification.current_boundary.receipts import (
    SEED_ACKNOWLEDGED,
    SEED_UNCONTROLLED,
    classify_seed_binding,
)

SEED = 424242


def test_echoed_seed_without_engine_confirmation_is_uncontrolled() -> None:
    binding = classify_seed_binding(
        requested_seed=SEED,
        acknowledged_seed=SEED,
        source="create_commander_game_response",
        engine_verified=False,
    )
    assert binding.classification == SEED_UNCONTROLLED
    assert binding.to_document()["rng_credit"] is False


def test_confirmed_matching_seed_is_acknowledged() -> None:
    binding = classify_seed_binding(
        requested_seed=SEED,
        acknowledged_seed=SEED,
        source="create_commander_game_response",
        engine_verified=True,
    )
    assert binding.classification == SEED_ACKNOWLEDGED
    assert binding.to_document()["rng_credit"] is True


def test_confirmed_but_divergent_seed_stays_uncontrolled() -> None:
    binding = classify_seed_binding(
        requested_seed=SEED,
        acknowledged_seed=SEED + 1,
        source="create_commander_game_response",
        engine_verified=True,
    )
    assert binding.classification == SEED_UNCONTROLLED


def test_no_response_shape_is_never_confirmed() -> None:
    assert _engine_confirmed_seed(None) is False
    assert _engine_confirmed_seed({}) is False
    assert _engine_confirmed_seed({"rng": {}}) is False
    assert _engine_confirmed_seed({"rng": {"rules_seed": SEED}}) is False


def test_provider_statement_is_read_from_the_response() -> None:
    assert _engine_confirmed_seed({"rng": {"explicit_seed": True}}) is True
    assert _engine_confirmed_seed({"rng": {"explicit_seed": False}}) is False
    assert _engine_confirmed_seed({"engine_seed_verified": True}) is True


@pytest.mark.parametrize("value", ["true", 1, "yes"])
def test_non_boolean_confirmation_does_not_count(value: object) -> None:
    assert _engine_confirmed_seed({"rng": {"explicit_seed": value}}) is False
