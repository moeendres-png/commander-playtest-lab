from __future__ import annotations

from commander_lab.tools.service import CommanderToolService
from commander_lab.whole_deck.orchestrator import (
    WholeDeckCampaignOrchestrator,
    WholeDeckCampaignSpecification,
)


def test_orchestrator_separates_primary_and_holdout_scenarios(repo_root) -> None:
    service = CommanderToolService(repo_root)
    baseline = service._deck("rogshai/current")
    variant = baseline.model_copy(
        update={"deck_id": "synthetic/whole-deck/orchestrator", "deck_hash": "orchestrator"}
    )
    result = WholeDeckCampaignOrchestrator(repo_root).run_pair(
        baseline=baseline,
        variant=variant,
        specification=WholeDeckCampaignSpecification(
            primary_games=2,
            holdout_games=2,
            seed=2026081412,
            max_turns=1,
        ),
    )

    assert result["campaign_specification"]["pod_size"] == 4
    assert len(result["opponent_deck_ids"]) == 8
    assert result["holdout"] is not None
    primary = result["primary"]
    holdout = result["holdout"]
    assert primary["evidence_axis"] == "primary_balanced_4p"
    assert holdout["evidence_axis"] == "holdout"
    assert holdout["construction_use"] is False
    assert {row["seed"] for row in primary["scenarios"]}.isdisjoint(
        {row["seed"] for row in holdout["scenarios"]}
    )
    assert result["sensitivity_boundary"]["three_player"].endswith("NOT_RUN")
    assert result["sensitivity_boundary"]["five_player"].endswith("NOT_RUN")
