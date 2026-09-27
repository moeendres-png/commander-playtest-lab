from pathlib import Path

from commander_lab.models.tooling import DeckDecisionRunInput, GenerateCandidateSwapsInput
from commander_lab.tools import CommanderToolService, ToolRegistry

ROOT = Path(__file__).resolve().parents[2]


def _candidate_id(service: CommanderToolService, name: str) -> str:
    return next(
        candidate_id
        for candidate_id, candidate in service.candidates.items()
        if candidate.card.oracle_name == name
    )


def test_semantic_frontier_uses_decision_weighted_evidence_without_inventory_penalty() -> None:
    service = CommanderToolService(ROOT)
    evendo_id = _candidate_id(service, "Evendo Brushrazer")
    opt_id = _candidate_id(service, "Opt")
    response = service.generate_candidate_swaps(
        GenerateCandidateSwapsInput(
            deck_id="rogshai/current",
            candidate_ids=(evendo_id, opt_id),
            max_candidates=50,
        )
    )
    assert response.status.value == "completed"
    result = response.result
    assert result["semantic_frontier_gate"]["authority"] == "semantic_evidence_summary"
    assert result["semantic_frontier_gate"]["legacy_semantic_quality_is_authoritative"] is False
    assert result["semantic_frontier_gate"]["unmodeled_is_negative_evidence"] is False
    rows = result["all_screened_candidates"]
    assert rows
    assert all(row["screening_uncertainty_penalty"] == 0.0 for row in rows)
    evendo_rows = [row for row in rows if row["candidate_id"] == evendo_id]
    assert evendo_rows
    assert all(str(row["legacy_semantic_quality"]) for row in evendo_rows)
    assert any(row["legacy_screening_uncertainty_penalty"] == 2.5 for row in evendo_rows)
    assert all(row["screening_uncertainty_penalty"] == 0.0 for row in evendo_rows)
    assert any(row["semantic_evidence"].get("evidence_type") != "UNKNOWN" for row in evendo_rows)
    opt_rows = [row for row in rows if row["candidate_id"] == opt_id]
    assert opt_rows
    assert all(row["semantic_authority"] == "semantic_evidence_summary" for row in rows)
    assert all(not row["requires_semantic_adjudication"] for row in result["candidates"])


def test_public_paired_execution_falls_back_to_one_worker_and_limit_is_identity_neutral() -> None:
    service = CommanderToolService(ROOT)
    registry = ToolRegistry(service, surface="public")
    assert (
        DeckDecisionRunInput(remove="Preordain", add_candidate_id="rogshai/opt-smoke").workers == 1
    )
    common = {
        "deck_id": "rogshai/current",
        "remove": "Preordain",
        "add_candidate_id": "rogshai/opt-smoke",
        "iterations": 2,
        "seed": 2026081203,
        "max_turns": 10,
    }
    one = registry.invoke("deck_decision_run", common | {"workers": 1})
    two = registry.invoke(
        "deck_decision_run",
        common | {"workers": 2, "max_simulation_seconds": 300.0},
    )
    assert one.status.value == "completed"
    assert two.status.value == "completed"
    assert one.result["paired"] == two.result["paired"]
    assert one.metadata.run_identity_hash == two.metadata.run_identity_hash
    assert two.result["execution_workers"] == {
        "requested": 2,
        "effective": 1,
        "fallback_applied": True,
        "policy": "validated_single_worker_policy_1_18",
        "deck_quality_evidence": False,
    }
    envelope = two.result["execution_envelope"]
    assert envelope["effective_workers"] == 1
    assert envelope["effective_max_simulation_seconds"] == 300.0
    assert envelope["classification"] == "execution_envelope_only_not_deck_quality_evidence"
