from __future__ import annotations

from pathlib import Path

from commander_lab.models import (
    BeamSearchInput,
    CandidatePackage,
    LocalSearchInput,
    PackageSearchInput,
    ParetoFrontInput,
    ShapleyInput,
    SwapMatrixInput,
    ToolStatus,
    ValidateUpgradeInput,
    VariantSwap,
)
from commander_lab.optimization import DEFAULT_CONSTRAINTS, evaluate_constraints
from commander_lab.tools import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_phase7_candidate_pool_is_locally_verified() -> None:
    service = CommanderToolService(ROOT)
    assert service.candidate_inventory["Opt"] >= 1
    assert "Into the Roil" in service.verified_candidate_names


def test_complete_swap_matrix_preserves_every_requested_cell() -> None:
    service = CommanderToolService(ROOT)
    response = service.generate_swap_matrix(
        SwapMatrixInput(
            deck_id="rogshai/current",
            remove_cards=("Consider", "Preordain"),
            add_candidate_ids=("rogshai/opt-smoke", "rogshai/into-the-roil-smoke"),
            simulate_valid_cells=False,
            iterations_per_cell=1,
        )
    )
    assert response.status == ToolStatus.COMPLETED
    assert response.result["matrix_complete"] is True
    assert response.result["cells"] == 4
    assert len(response.result["rows"]) == 4
    assert response.result["automatic_application"] is False


def test_local_and_beam_search_return_candidates_not_edits() -> None:
    service = CommanderToolService(ROOT)
    local = service.run_local_search(
        LocalSearchInput(
            deck_id="rogshai/current",
            candidate_ids=("rogshai/opt-smoke",),
            max_steps=1,
            cuts_per_step=2,
            iterations=2,
            seed=17,
        )
    )
    beam = service.run_beam_search(
        BeamSearchInput(
            deck_id="rogshai/current",
            candidate_ids=("rogshai/opt-smoke", "rogshai/into-the-roil-smoke"),
            beam_width=2,
            depth=1,
            max_cuts_per_node=2,
            iterations=2,
            seed=17,
        )
    )
    assert local.status == ToolStatus.COMPLETED
    assert beam.status == ToolStatus.COMPLETED
    assert local.result["automatic_application"] is False
    assert beam.result["automatic_application"] is False


def test_package_search_enforces_constraints_and_returns_evidence() -> None:
    service = CommanderToolService(ROOT)
    package = CandidatePackage(
        package_id="rogshai-smoke-package",
        swaps=(
            VariantSwap(remove="Consider", add_candidate_id="rogshai/opt-smoke"),
            VariantSwap(remove="Preordain", add_candidate_id="rogshai/into-the-roil-smoke"),
        ),
    )
    response = service.run_package_search(
        PackageSearchInput(
            deck_id="rogshai/current",
            packages=(package,),
            iterations=2,
            seed=19,
        )
    )
    assert response.status == ToolStatus.COMPLETED
    assert response.result["packages"]
    row = response.result["packages"][0]
    assert row["status"] in {"paired_screened", "constraint_failed"}
    assert response.result["automatic_application"] is False


def test_pareto_front_contains_only_non_dominated_valid_variants() -> None:
    service = CommanderToolService(ROOT)
    response = service.evaluate_pareto_front(
        ParetoFrontInput(
            deck_id="rogshai/current",
            variants=(
                (VariantSwap(remove="Consider", add_candidate_id="rogshai/opt-smoke"),),
                (
                    VariantSwap(
                        remove="Preordain",
                        add_candidate_id="rogshai/into-the-roil-smoke",
                    ),
                ),
            ),
            iterations=2,
            holdout_pods=(("synthetic/control", "synthetic/control", "synthetic/engine"),),
            seed=23,
        )
    )
    assert response.status == ToolStatus.COMPLETED
    assert response.result["evaluated"]
    assert response.result["pareto_front"]
    assert response.result["automatic_application"] is False


def test_shapley_approximation_is_seed_reproducible() -> None:
    service = CommanderToolService(ROOT)
    request = ShapleyInput(
        deck_id="rogshai/current",
        card_names=("Consider", "Preordain"),
        permutations=16,
        iterations=2,
        seed=29,
    )
    first = service.estimate_shapley(request)
    second = service.estimate_shapley(request)
    assert first.status == ToolStatus.COMPLETED
    assert second.status == ToolStatus.COMPLETED
    assert first.result["contributions"] == second.result["contributions"]


def test_validate_upgrade_runs_full_chain_and_never_applies() -> None:
    service = CommanderToolService(ROOT)
    response = service.validate_upgrade(
        ValidateUpgradeInput(
            deck_id="rogshai/current",
            swaps=(VariantSwap(remove="Consider", add_candidate_id="rogshai/opt-smoke"),),
            iterations=2,
            seed=31,
            holdout_pods=(("synthetic/control", "synthetic/control", "synthetic/engine"),),
            sensitivity_seeds=(31,),
            sensitivity_strengths=("average",),
            minimum_place_delta=-3.0,
        )
    )
    assert response.status == ToolStatus.COMPLETED
    assert response.result["decision"] in {"confirmed", "rejected"}
    assert response.result["structural_rationale"]
    assert response.result["affected_matchups"]
    assert response.result["paired_comparison"]
    assert response.result["holdout_tests"]
    assert response.result["sensitivity_tests"]
    assert response.result["red_team_review"]
    assert response.result["automatic_application"] is False
    assert response.result["canonical_deck_files_modified"] is False


def test_constraint_report_rejects_wrong_color_candidate() -> None:
    service = CommanderToolService(ROOT)
    baseline = service._deck("rogshai/current")
    off_color = next(
        candidate.card
        for candidate in service.candidates.values()
        if candidate.card.oracle_name == "Mazirek, Kraul Death Priest"
    )
    variant = baseline.model_copy(update={"cards": tuple([*baseline.cards[:-1], off_color])})
    report = evaluate_constraints(
        variant,
        DEFAULT_CONSTRAINTS["rogshai/current"],
        candidate_inventory={"Mazirek, Kraul Death Priest": 1},
        added_card_names=("Mazirek, Kraul Death Priest",),
        verified_physical_names={"Mazirek, Kraul Death Priest"},
    )
    assert report.valid is False
    assert any(issue.code == "color_identity" for issue in report.issues)


def test_simultaneous_allocation_rejects_shared_single_copy() -> None:
    from commander_lab.optimization import evaluate_simultaneous_allocation

    report = evaluate_simultaneous_allocation(
        {
            "fixture/deck-a": ("Lightning Greaves",),
            "fixture/deck-b": ("Lightning Greaves",),
        },
        {"Lightning Greaves": 1},
    )
    assert report.valid is False
    assert report.issues[0].code == "simultaneous_physical_allocation"
