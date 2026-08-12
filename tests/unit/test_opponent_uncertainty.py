from __future__ import annotations

import pytest

from commander_lab.opponent_uncertainty import (
    OpponentScenarioEnvelope,
    OpponentScenarioEvidence,
    summarize_scenario_results,
)


def test_synthetic_scenario_can_never_be_promoted_to_observation() -> None:
    with pytest.raises(ValueError, match="synthetic"):
        OpponentScenarioEnvelope(
            scenario_id="morcant-high-denial",
            opponent_entity_id="opponent:alen_high_perfect_morcant",
            evidence_class=OpponentScenarioEvidence.PLAUSIBLE_ENVELOPE,
            assumptions=(("commander_denial", "high"),),
            canonical_observation=True,
        )


def test_observed_scenario_cannot_contain_synthetic_assumptions() -> None:
    with pytest.raises(ValueError, match="synthetic assumptions"):
        OpponentScenarioEnvelope(
            scenario_id="morcant-observed",
            opponent_entity_id="opponent:alen_high_perfect_morcant",
            evidence_class=OpponentScenarioEvidence.OBSERVED,
            assumptions=(("unknown_slots", "filled"),),
            canonical_observation=True,
        )


def test_scenario_summary_reports_nominal_worst_regret_and_spread_without_weights() -> None:
    observed = OpponentScenarioEnvelope(
        scenario_id="observed",
        opponent_entity_id="opponent:cosmic_spider_man",
        evidence_class=OpponentScenarioEvidence.OBSERVED,
        canonical_observation=True,
    )
    plausible = OpponentScenarioEnvelope(
        scenario_id="plausible-denial",
        opponent_entity_id="opponent:cosmic_spider_man",
        evidence_class=OpponentScenarioEvidence.PLAUSIBLE_ENVELOPE,
        assumptions=(("commander_denial", "high"),),
    )
    stress = OpponentScenarioEnvelope(
        scenario_id="stress",
        opponent_entity_id="opponent:cosmic_spider_man",
        evidence_class=OpponentScenarioEvidence.STRESS,
        assumptions=(("interaction_density", "adversarial"),),
    )
    summary = summarize_scenario_results(
        ((observed, 0.10), (plausible, -0.05), (stress, -0.20)),
        nominal_scenario_id="observed",
    )

    assert summary.nominal_result == 0.10
    assert summary.worst_plausible_result == -0.05
    assert summary.scenario_regret == pytest.approx(0.15)
    assert summary.lower_tail_result == -0.20
    assert summary.scenario_spread == pytest.approx(0.30)
    assert "weight" not in summary.as_dict()
