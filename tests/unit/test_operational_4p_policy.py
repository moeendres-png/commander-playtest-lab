from __future__ import annotations

import pytest

from commander_lab.robustness import PolicyTournamentConfig


def test_policy_tournament_defaults_to_four_player_commander_only() -> None:
    assert PolicyTournamentConfig().pod_sizes == (4,)


@pytest.mark.parametrize("pod_sizes", [(3,), (5,), (3, 4, 5), (4, 5), (3, 4)])
def test_policy_tournament_rejects_non_four_player_operational_scope(
    pod_sizes: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError, match="4-player only"):
        PolicyTournamentConfig(pod_sizes=pod_sizes)


def test_structural_self_play_rejects_non_four_player_operational_scope(repo_root) -> None:
    from commander_lab.robustness import run_structural_self_play

    with pytest.raises(ValueError, match="4-player only"):
        run_structural_self_play(repo_root, pod_sizes=(3,))
