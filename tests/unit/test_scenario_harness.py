"""Tests for K5 scenario harness (strict mode, no silent skips)."""

from __future__ import annotations

import pytest

from commander_lab.verification.scenario_harness import (
    ScenarioHarness,
    START_CORPUS,
)


def test_strict_mode_requires_consume_or_discard():
    """Strict mode fails if an option is neither consumed nor discarded."""
    harness = ScenarioHarness(strict=True)
    # Present an option but don't consume/discard it
    with pytest.raises(AssertionError, match="Strict mode violation"):
        harness.verify_strict(["option-1"])


def test_strict_mode_passes_when_consumed():
    """Strict mode passes if option was consumed."""
    harness = ScenarioHarness(strict=True)
    harness.consume_option("option-1")
    # Should not raise
    harness.verify_strict(["option-1"])


def test_strict_mode_passes_when_discarded_with_reason():
    """Strict mode passes if option was explicitly discarded with reason."""
    harness = ScenarioHarness(strict=True)
    harness.discard_option("option-1", reason="Not relevant to scenario")
    # Should not raise
    harness.verify_strict(["option-1"])


def test_strict_mode_requires_discard_reason():
    """Strict mode requires a reason when discarding."""
    harness = ScenarioHarness(strict=True)
    with pytest.raises(ValueError, match="discard reason required"):
        harness.discard_option("option-1", reason="")


def test_non_strict_mode_allows_silent():
    """Non-strict mode does not enforce consume/discard."""
    harness = ScenarioHarness(strict=False)
    # Should not raise even though option-1 was never consumed
    harness.verify_strict(["option-1"])


def test_start_corpus_has_known_cards():
    """Start corpus contains cards with well-known behavior."""
    assert len(START_CORPUS) >= 5
    assert "Lightning Bolt" in START_CORPUS
    assert "Sol Ring" in START_CORPUS
