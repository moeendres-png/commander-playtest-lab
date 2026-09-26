from __future__ import annotations

from commander_lab.engine.structural import StructuralSimulator, derive_match_seed
from commander_lab.models import StructuralAbortLimits, StructuralMatchConfig


def test_derived_seeds_are_stable_and_distinct() -> None:
    first = [derive_match_seed(7, "run", index) for index in range(100)]
    second = [derive_match_seed(7, "run", index) for index in range(100)]
    assert first == second
    assert len(set(first)) == 100


def test_placements_form_valid_range_for_many_seeds(structural_decks) -> None:
    simulator = StructuralSimulator(structural_decks)
    deck_ids = ("rogshai/current", "kaervek/current", "synthetic/aggro", "synthetic/control")
    for seed in range(12):
        result = simulator.simulate(
            StructuralMatchConfig(
                match_id=f"placement-{seed}",
                seed=seed,
                deck_ids=deck_ids,
                limits=StructuralAbortLimits(
                    max_turns=30, max_events=20_000, max_no_progress_turns=20
                ),
            )
        )
        assert set(result.placements) == {"p1", "p2", "p3", "p4"}
        assert all(1 <= placement <= 4 for placement in result.placements.values())
        assert result.estimate_type == "structural_model_estimates"
