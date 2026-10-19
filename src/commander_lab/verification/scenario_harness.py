"""K5: Scripted Scenario Harness for card behavior verification.

Runs scripted scenarios through the Full-Game-Bridge:
  Setup → Scripted Decisions → Assertions on Tape End-State

Strict mode: every presented option must be consumed or explicitly discarded.
If an unexpected option appears, the test fails (no silent skips).

This is PARTIAL coverage (scripted scenarios), not FULL (all interactions).
See: docs/evidence-standard.md (PARTIAL ≠ FULL)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CardSetup:
    """A card to put on the battlefield during setup."""
    name: str
    controller_seat: int = 0
    tapped: bool = False
    counters: dict[str, int] = field(default_factory=dict)


@dataclass
class ScriptedDecision:
    """A pre-scripted decision for the pilot."""
    # Match criteria (all must match)
    prompt_contains: str | None = None
    option_label: str | None = None
    # Action to take
    choose_option_index: int | None = None
    choose_label: str | None = None
    # If True, this decision MUST be presented (fail if not)
    required: bool = True


@dataclass
class ScenarioAssertion:
    """An assertion on the tape end-state."""
    # Path in the tape JSON (dot-separated)
    path: str
    # Expected value (or callable returning bool)
    expected: Any
    description: str


@dataclass
class Scenario:
    """A complete scripted scenario."""
    scenario_id: str
    description: str
    # Cards to set up
    setup_cards: list[CardSetup] = field(default_factory=list)
    # Scripted decisions in order
    decisions: list[ScriptedDecision] = field(default_factory=list)
    # Assertions on end state
    assertions: list[ScenarioAssertion] = field(default_factory=list)
    # Strict mode: fail on unconsumed options
    strict: bool = True


class ScenarioHarness:
    """Runs scripted scenarios through the bridge."""

    def __init__(self, strict: bool = True):
        self.strict = strict
        self._consumed_options: set[str] = set()
        self._discarded_options: set[str] = set()

    def consume_option(self, option_id: str) -> None:
        """Mark an option as consumed (used in a decision)."""
        self._consumed_options.add(option_id)

    def discard_option(self, option_id: str, reason: str) -> None:
        """Explicitly discard an option (must provide reason in strict mode)."""
        if self.strict and not reason:
            raise ValueError("Strict mode: discard reason required")
        self._discarded_options.add(option_id)

    def verify_strict(self, presented_options: list[str]) -> None:
        """Verify all presented options were consumed or discarded."""
        if not self.strict:
            return
        for opt_id in presented_options:
            if opt_id not in self._consumed_options and opt_id not in self._discarded_options:
                raise AssertionError(
                    f"Strict mode violation: option '{opt_id}' was presented "
                    f"but neither consumed nor explicitly discarded. "
                    f"This is a silent skip (fail-closed)."
                )

    def reset(self) -> None:
        """Reset for next scenario."""
        self._consumed_options.clear()
        self._discarded_options.clear()


# Start corpus: 5 cards with well-known behavior from Mage.Tests
# (Full 20-50 card corpus is future work; H3 showed 68s per test)
START_CORPUS = [
    "Lightning Bolt",      # Direct damage
    "Sol Ring",            # Mana acceleration
    "Command Tower",       # Mana fixing
    "Swords to Plowshares", # Removal
    "Cultivate",           # Ramp
]
