from __future__ import annotations

from commander_lab.models.tooling import DeckDecisionDiagnoseInput
from commander_lab.tools import CommanderToolService


def test_public_diagnose_forwards_cohort_context(repo_root):
    service = CommanderToolService(repo_root)
    comparison = {
        "status": "completed",
        "paired": {
            "placement_improvement": 0.0,
            "confidence_interval": [-0.10, 0.10],
            "monte_carlo_standard_error": 0.05,
            "baseline_place_1_share": 0.95,
        },
        "paired_observations": [
            {"starting_player_seat": 1, "baseline_placement": 1},
            {"starting_player_seat": 2, "baseline_placement": 1},
        ],
        "precision_context": {
            "current_iterations": 64,
            "preregistered_precision_ceiling": 1024,
            "additional_precision_authorized": False,
        },
    }
    cohort = tuple(dict(comparison) for _ in range(8))
    request = DeckDecisionDiagnoseInput(
        comparison=comparison,
        cohort_comparisons=cohort,
        opponent_evidence_quality={"synthetic_assumption": 8},
        failure_mode_metrics=("average_placement", "average_commander_damage"),
    )

    response = service.deck_decision_diagnose(request)

    assert response.status.value == "completed"
    assert response.result["model_informativeness"]["status"] == "MODEL_INFORMATION_LIMIT"
    assert response.result["decision_information_state"]["status"] == "MODEL_NEEDS_DIFFERENT_METRIC"
    assert response.result["next_experiment"] == "diagnose_model_information_before_more_seed_work"
