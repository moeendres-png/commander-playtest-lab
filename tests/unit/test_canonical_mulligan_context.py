from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.models.mulligan import MulliganContext
from commander_lab.mulligan import MulliganLab, MulliganLabError

ROOT = Path(__file__).resolve().parents[2]


def _context(lab: MulliganLab, deck_id: str, *, pod_size: int = 4) -> MulliganContext:
    deck = lab.deck(deck_id)
    return MulliganContext(deck_id=deck_id, deck_hash=deck.deck_hash, pod_size=pod_size)


def test_primary_rogshai_mulligan_context_uses_current_canonical_opponent_registry() -> None:
    lab = MulliganLab(ROOT)
    context = _context(lab, "rogshai/current")
    first = lab._opponent_ids(context)
    second = lab._opponent_ids(context)
    current = set(lab.project_context.holdout_deck_ids) | set(
        lab.project_context.primary_opponent_deck_ids("rogshai/current")
    )

    assert first == second
    assert len(first) == 3
    assert len(set(first)) == 3
    assert set(first) <= current


def test_unknown_former_deck_is_not_part_of_current_mulligan_context() -> None:
    lab = MulliganLab(ROOT)
    with pytest.raises(MulliganLabError, match="unknown deck"):
        lab.deck("former/current")
    assert lab.project_context.historical_own_deck_ids == ()


def test_non_four_player_context_fails_closed_instead_of_inventing_opponents() -> None:
    lab = MulliganLab(ROOT)
    with pytest.raises(MulliganLabError, match="require explicit opponent composition"):
        lab._opponent_ids(_context(lab, "rogshai/current", pod_size=5))


def test_holdout_sampling_is_domain_separated_but_uses_current_registry() -> None:
    lab = MulliganLab(ROOT)
    context = _context(lab, "rogshai/current")
    primary = lab._opponent_ids(context)
    holdout = lab._opponent_ids(context, holdout=1)
    current = set(lab.project_context.holdout_deck_ids) | set(
        lab.project_context.primary_opponent_deck_ids("rogshai/current")
    )

    assert len(holdout) == 3
    assert len(set(holdout)) == 3
    assert set(holdout) <= current
    assert holdout != primary
