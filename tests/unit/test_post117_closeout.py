from pathlib import Path

from commander_lab.decision_information import DecisionInformationStatus, build_decision_information_state
from commander_lab.models.tooling import DeckDecisionRunInput
from commander_lab.tools.post117_service import (
    Post117CommanderToolService,
    build_fresh_candidate_cut_frontier,
    semantic_frontier_decision,
)

ROOT = Path(__file__).resolve().parents[2]


def _candidate_id(service: Post117CommanderToolService, oracle_name: str) -> str:
    return next(
        candidate_id
        for candidate_id, candidate in service.candidates.items()
        if candidate.card.oracle_name == oracle_name
    )


def test_evendo_conflict_preserves_provenance_and_defers_simulation() -> None:
    service = Post117CommanderToolService(ROOT)
    decision = semantic_frontier_decision(ROOT, service, _candidate_id(service, "Evendo Brushrazer"))
    assert decision.status == "requires_semantic_adjudication"
    assert decision.simulation_allowed is False
    assert decision.automatic_rejection is False
    assert decision.semantic_evidence["evidence_type"] == "PROJECT_DERIVED"
    assert decision.legacy_semantic_provenance["semantic_quality"] == "keyword_inferred_structural_only"
    assert decision.conflict_reasons


def test_opt_is_semantically_ready_for_paired_simulation() -> None:
    service = Post117CommanderToolService(ROOT)
    decision = semantic_frontier_decision(ROOT, service, _candidate_id(service, "Opt"))
    assert decision.status == "ready_for_paired_simulation"
    assert decision.simulation_allowed is True
    assert decision.requires_semantic_adjudication is False


def test_fresh_frontier_preserves_full_recall_and_caps_pairs() -> None:
    service = Post117CommanderToolService(ROOT)
    frontier = build_fresh_candidate_cut_frontier(ROOT, service, limit=50)
    assert frontier["physical_legal_candidate_count"] == 795
    assert frontier["discoverable_candidate_count"] == 795
    assert frontier["candidate_recall"] == 1.0
    assert frontier["simulation_ready_pair_count"] <= 50
    assert frontier["noisy_early_elimination_allowed"] is False
    assert frontier["static_deprioritization_only_before_simulation"] is True


def test_semantic_defer_routes_to_different_metric() -> None:
    state = build_decision_information_state(
        {
            "status": "requires_semantic_adjudication",
            "missing_semantic_axes": ["roles", "packages"],
        }
    )
    assert state.status == DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC
    assert state.next_recommended_experiment == "resolve_decision_material_semantic_axes"


def test_public_run_workers_two_falls_back_to_one_without_seed_change() -> None:
    service = Post117CommanderToolService(ROOT)
    opt_id = _candidate_id(service, "Opt")
    response = service.deck_decision_run(
        DeckDecisionRunInput(
            remove="Preordain",
            add_candidate_id=opt_id,
            iterations=2,
            seed=2026081203,
            max_turns=8,
            workers=2,
        )
    )
    assert response.status.value == "completed"
    policy = response.result["execution_policy"]
    assert policy["requested_workers"] == 2
    assert policy["effective_workers"] == 1
    assert policy["worker_fallback_applied"] is True
    assert policy["execution_metadata_is_deck_evidence"] is False
    assert policy["seed_and_run_semantics_unchanged"] is True


def test_1024_uses_bounded_execution_envelope_only() -> None:
    service = Post117CommanderToolService(ROOT)
    assert service.HIGH_BUDGET_EXECUTION_SECONDS == 300.0
    assert service.SAFE_WORKERS == 1
