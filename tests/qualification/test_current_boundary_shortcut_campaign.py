"""Forbidden-shortcut negative campaign against the production validation seam.

The point of the campaign is that it is behavioural: every case would succeed if
the forbidden shortcut were reachable, and the campaign fails if any of them does.
These tests also pin the limits of what it establishes, so the result cannot be
read as a global audit.
"""

from __future__ import annotations

import pytest

from commander_lab.qualification.current_boundary.shortcut_campaign import (
    run_negative_campaign,
)

OBLIGATIONS = (
    "NEGATIVE_FIRST_OPTION",
    "NEGATIVE_RANDOM_OPTION",
    "NEGATIVE_DEFAULT_YES_NO",
    "NEGATIVE_INTERNAL_AI",
    "NEGATIVE_GUI_DEFAULT",
    "NEGATIVE_SILENT_SKIP",
    "NEGATIVE_PARENT_CLASS_FALLBACK",
)


@pytest.fixture(scope="module")
def campaign() -> dict:
    return run_negative_campaign()


def test_all_seven_obligations_are_tested(campaign: dict) -> None:
    assert set(campaign["obligations"]) == set(OBLIGATIONS)
    assert campaign["counts"]["obligations_tested"] == 7


@pytest.mark.parametrize("obligation_id", OBLIGATIONS)
def test_each_forbidden_shortcut_fails_closed(obligation_id: str, campaign: dict) -> None:
    entry = campaign["obligations"][obligation_id]
    assert entry["outcome"] == "FAILS_CLOSED", entry
    assert entry["validator_message"], "a rejection must say why"


def test_no_shortcut_is_reachable_at_the_seam(campaign: dict) -> None:
    assert campaign["shortcuts_reachable"] == []
    assert campaign["counts"]["shortcut_reachable"] == 0
    assert campaign["counts"]["failed_closed"] == 7


def test_the_campaign_does_not_pass_by_rejecting_everything(campaign: dict) -> None:
    """A positive control proves the seam still accepts a correct proposal."""
    control = campaign["positive_control"]
    assert control["outcome"] == "ACCEPTED_AS_OFFERED"
    assert control["rejected"] is False


def test_the_returned_value_is_the_engine_object(campaign: dict) -> None:
    """The validator must never substitute an object of its own."""
    assert campaign["positive_control"]["returned_is_engine_object"] is True


def test_the_seam_under_test_is_the_production_validator(campaign: dict) -> None:
    assert campaign["seam_under_test"].endswith("validate_action_proposal")


def test_scope_is_narrow_and_stated(campaign: dict) -> None:
    assert "not an audit of every" in campaign["scope"]
    assert "does not claim the seven obligations are globally discharged" in campaign["scope"]


def test_the_campaign_does_not_claim_a_row_promotion(campaign: dict) -> None:
    joined = " ".join(campaign["what_it_does_not_establish"])
    assert "may be promoted to PASS" in joined
    assert "active owner" in joined


def test_engine_behaviour_is_not_claimed(campaign: dict) -> None:
    assert any("engine behaviour" in line for line in campaign["what_it_does_not_establish"])


def test_the_campaign_is_reproducible() -> None:
    """Two runs must agree, or the campaign is measuring noise."""
    first = run_negative_campaign()
    second = run_negative_campaign()
    assert first["obligations"] == second["obligations"]
    assert first["shortcuts_reachable"] == second["shortcuts_reachable"]
