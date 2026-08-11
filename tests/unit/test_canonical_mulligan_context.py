from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.models.mulligan import MulliganContext
from commander_lab.mulligan import MulliganLab, MulliganLabError

ROOT = Path(__file__).resolve().parents[2]


def _context(lab: MulliganLab, deck_id: str, *, pod_size: int = 4) -> MulliganContext:
    deck = lab.deck(deck_id)
    return MulliganContext(deck_id=deck_id, deck_hash=deck.deck_hash, pod_size=pod_size)


def test_primary_rogshai_mulligan_context_uses_current_canonical_pod() -> None:
    lab = MulliganLab(ROOT)
    opponents = lab._opponent_ids(_context(lab, "rogshai/current"))
    assert opponents == (
        "opponent/morcant-elves",
        "opponent/doom-prevails-precon",
        "opponent/cosmic-spiderman-midbudget",
    )
    assert "opponent/blight-curse-precon" not in opponents


def test_primary_korvold_mulligan_context_uses_current_canonical_pod() -> None:
    lab = MulliganLab(ROOT)
    assert lab._opponent_ids(_context(lab, "korvold/current")) == (
        "opponent/morcant-elves",
        "opponent/doom-prevails-precon",
        "opponent/cosmic-spiderman-midbudget",
    )


def test_non_four_player_context_fails_closed_instead_of_inventing_opponents() -> None:
    lab = MulliganLab(ROOT)
    with pytest.raises(MulliganLabError, match="require explicit opponent composition"):
        lab._opponent_ids(_context(lab, "rogshai/current", pod_size=5))


def test_holdout_sampling_uses_only_canonical_holdout_pool() -> None:
    lab = MulliganLab(ROOT)
    opponents = lab._opponent_ids(_context(lab, "rogshai/current"), holdout=1)
    assert len(opponents) == 3
    assert set(opponents) <= set(lab.project_context.holdout_deck_ids)
    assert set(opponents).isdisjoint(
        {
            "opponent/morcant-elves",
            "opponent/doom-prevails-precon",
            "opponent/cosmic-spiderman-midbudget",
        }
    )
