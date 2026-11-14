from __future__ import annotations

from pathlib import Path

from commander_lab.engine.structural import load_project_structural_decks


def test_current_opponent_profiles_are_loaded(project_root: Path = Path.cwd()) -> None:
    decks = load_project_structural_decks(
        project_root,
        include_synthetic_fixtures=True,
        include_current_opponents=True,
    )
    expected = {
        "opponent/morcant-elves",
        "opponent/cosmic-spiderman-midbudget",
        "opponent/blight-curse-precon",
        "kaervek/current",
        "opponent/doom-prevails-precon",
        "opponent/dance-elements-precon",
        "opponent/wakanda-forever-precon",
    }
    assert expected <= set(decks)
    assert all(len(decks[deck_id].cards) == 100 for deck_id in expected)
