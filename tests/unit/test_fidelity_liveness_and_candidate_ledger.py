from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.lab_context import EnrichedWholeDeckSearchEngine
from commander_lab.whole_deck.mechanics_fidelity import (
    assess_variant_mechanics,
    build_fidelity_liveness_audit,
)
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.optimizer_search import OptimizerSearchReport
from commander_lab.whole_deck.optimizer_v2 import QDConfig
from commander_lab.whole_deck.optimizer_v2_artifacts import build_candidate_ledger
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search_context import current_control_mainboard
from commander_lab.whole_deck.search_models import WholeDeckSearchConfig

ROOT = Path(__file__).resolve().parents[2]


def _control_engine(lab: WholeDeckDesignLab) -> EnrichedWholeDeckSearchEngine:
    return EnrichedWholeDeckSearchEngine(
        lab.context,
        get_policy(PolicyId.CURRENT_CONTROL),
        config=WholeDeckSearchConfig(
            seed=17,
            diversified_starts=0,
            max_steps_per_start=1,
            finalist_limit=1,
            archive_limit=32,
        ),
        enrichment=lab.enrichment,
        answer_map=lab.answer_map,
    )


def test_current_pool_fidelity_liveness_is_deterministic_and_nonconsuming() -> None:
    lab = WholeDeckDesignLab(ROOT)
    control = current_control_mainboard(ROOT)
    engine = _control_engine(lab)
    first = build_fidelity_liveness_audit(
        lab.context,
        control=control,
        control_engine=engine,
        qd_config=QDConfig(),
        seed=23,
    )
    second = build_fidelity_liveness_audit(
        lab.context,
        control=control,
        control_engine=engine,
        qd_config=QDConfig(),
        seed=23,
    )
    assert first == second
    assert first["evidence_consuming"] is False
    assert first["candidate_pool_count"] == 795
    assert first["decision_safe_card_count"] > 0
    assert first["decision_safe_legal_neighbor_count"] > 0
    assert first["fidelity_liveness"] == "PASS"


def test_fidelity_repair_emitter_finds_real_safe_noncontrol_neighbors() -> None:
    from commander_lab.whole_deck.optimizer_search import AdaptiveWholeDeckSearch
    from commander_lab.whole_deck.optimizer_v2 import LearningConfig, RacingConfig

    lab = WholeDeckDesignLab(ROOT)
    control = current_control_mainboard(ROOT)
    engine = _control_engine(lab)
    control_variant = engine.evaluate_mainboard(control, seed=31)

    class _NoSimulationEvaluator:
        def structural_decision_safe(self, variant):
            return assess_variant_mechanics(
                lab.context,
                control=control,
                candidate=variant.mainboard,
                deck_hash=variant.deck_hash,
            )["pass"]

        def __call__(self, *_args, **_kwargs):
            raise AssertionError("safe-neighborhood emission must not consume simulation evidence")

    evaluator = _NoSimulationEvaluator()
    evaluator.context = lab.context
    evaluator.control_mainboard = control
    evaluator.control = lab.context.materialize(control, label="test-control")

    search = AdaptiveWholeDeckSearch(
        {PolicyId.CURRENT_CONTROL.value: engine},
        evaluator=evaluator,
        seed=41,
        qd=QDConfig(),
        racing=RacingConfig(),
        learning=LearningConfig(),
    )
    proposals, _ = search._fidelity_repair_proposals(
        control_variant=control_variant,
        generation=1,
        limit=4,
        seen={control_variant.deck_hash: control_variant},
    )
    assert proposals
    assert all(row.deck_hash != control_variant.deck_hash for row in proposals)
    assert all(
        assess_variant_mechanics(
            lab.context,
            control=control,
            candidate=row.mainboard,
            deck_hash=row.deck_hash,
        )["pass"]
        for row in proposals
    )


def test_candidate_ledger_is_complete_hash_verified_and_diff_reconstructable(
    tmp_path: Path,
) -> None:
    lab = WholeDeckDesignLab(ROOT)
    control = current_control_mainboard(ROOT)
    engine = _control_engine(lab)
    variant = engine.evaluate_mainboard(control, seed=51)
    history = [
        {
            "budget": 2,
            "evaluation": {
                "budget": 2,
                "score": 0.0,
                "interval_low": 0.0,
                "interval_high": 0.0,
                "robust_lower_bound": 0.0,
                "generation": 0,
            },
            "payload": {},
        }
    ]
    evaluator = SimpleNamespace(
        variants_by_hash={variant.deck_hash: variant},
        evaluation_history_by_hash={variant.deck_hash: history},
        manifest=SimpleNamespace(qd=QDConfig()),
    )
    report = OptimizerSearchReport(
        generations=(),
        archive={"cells": {"x": [variant.deck_hash]}, "occupied_cells": 1, "elite_count": 1},
        operator_weights={},
        policy_weights={},
        unique_legal_decks=1,
        evaluation_calls=1,
        requested_scenario_pairs=2,
        feedback_changed_proposals=False,
        hypothesis_archive={"buckets": {"x": [variant.deck_hash]}},
    )
    ledger = build_candidate_ledger(
        context=lab.context,
        control_mainboard=control,
        evaluator=evaluator,
        search_report=report,
        control_deck_hash=variant.deck_hash,
    )
    assert ledger["candidate_count"] == 1
    row = ledger["rows"][0]
    assert len(row["exact_100_card_list"]) == 100
    assert row["deck_hash"] == variant.deck_hash
    assert row["exact_diff_vs_control"] == []
    assert row["confirmatory_eligible"] is False


def test_coverage_debt_emitter_is_deterministic_outcome_independent_and_legal() -> None:
    from commander_lab.whole_deck.optimizer_search import AdaptiveWholeDeckSearch
    from commander_lab.whole_deck.optimizer_v2 import LearningConfig, RacingConfig

    lab = WholeDeckDesignLab(ROOT)
    control = current_control_mainboard(ROOT)
    engine = _control_engine(lab)
    control_variant = engine.evaluate_mainboard(control, seed=61)

    class _NoSimulationEvaluator:
        def __call__(self, *_args, **_kwargs):
            raise AssertionError("coverage-debt emission must not consume simulation outcomes")

    evaluator = _NoSimulationEvaluator()
    evaluator.context = lab.context
    evaluator.control_mainboard = control
    evaluator.control = lab.context.materialize(control, label="test-control")

    search = AdaptiveWholeDeckSearch(
        {PolicyId.CURRENT_CONTROL.value: engine},
        evaluator=evaluator,
        seed=71,
        qd=QDConfig(),
        racing=RacingConfig(),
        learning=LearningConfig(),
    )
    seen = {control_variant.deck_hash: control_variant}
    first, first_counts = search._coverage_debt_proposals(
        control_variant=control_variant,
        generation=1,
        limit=4,
        seen=seen,
    )
    second, second_counts = search._coverage_debt_proposals(
        control_variant=control_variant,
        generation=1,
        limit=4,
        seen=seen,
    )

    assert first
    assert [row.deck_hash for row in first] == [row.deck_hash for row in second]
    assert first_counts == second_counts
    assert all(row.hard_gate.valid for row in first)
    assert all(row.mainboard != control for row in first)
    assert all(row.provenance["proposal_lane"] == "COVERAGE_DEBT" for row in first)
    assert all(row.provenance["coverage_only_parent"] is True for row in first)
    assert all(row.provenance["outcome_ranked"] is False for row in first)
    assert first_counts["newly_exposed_cards"]
