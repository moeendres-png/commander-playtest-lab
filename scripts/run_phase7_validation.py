from __future__ import annotations

import argparse
import json
from pathlib import Path

from commander_lab.models import (
    BeamSearchInput,
    CandidatePackage,
    LocalSearchInput,
    PackageSearchInput,
    ParetoFrontInput,
    ShapleyInput,
    SwapMatrixInput,
    ValidateUpgradeInput,
    VariantSwap,
)
from commander_lab.tools import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runs/phase7"


def dump(name: str, response) -> dict:
    payload = response.model_dump(mode="json")
    (OUT / f"{name}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return payload


def run(*, full: bool) -> dict[str, object]:
    OUT.mkdir(parents=True, exist_ok=True)
    service = CommanderToolService(ROOT)
    seed = 20260804
    local_iterations = 8 if full else 2
    validation_iterations = 20 if full else 4
    sensitivity_seeds = (20260804, 20260805, 20260806) if full else (20260804, 20260805)
    sensitivity_strengths = (
        "average", "strong", "near_optimal_heuristic"
    ) if full else ("average", "strong")

    korvold_matrix = dump(
        "korvold_complete_swap_matrix",
        service.generate_swap_matrix(
            SwapMatrixInput(
                deck_id="korvold/current",
                simulate_valid_cells=False,
                iterations_per_cell=1,
                seed=seed,
            )
        ),
    )
    rogshai_matrix = dump(
        "rogshai_complete_swap_matrix",
        service.generate_swap_matrix(
            SwapMatrixInput(
                deck_id="rogshai/current",
                simulate_valid_cells=False,
                iterations_per_cell=1,
                seed=seed,
            )
        ),
    )

    local_search = dump(
        "korvold_local_search",
        service.run_local_search(
            LocalSearchInput(
                deck_id="korvold/current",
                candidate_ids=("korvold/idol-of-oblivion", "korvold/lightning-greaves"),
                max_steps=2,
                cuts_per_step=8 if full else 4,
                iterations=local_iterations,
                seed=seed,
            )
        ),
    )
    beam_search = dump(
        "korvold_beam_search",
        service.run_beam_search(
            BeamSearchInput(
                deck_id="korvold/current",
                candidate_ids=("korvold/idol-of-oblivion", "korvold/lightning-greaves"),
                beam_width=4 if full else 2,
                depth=2,
                max_cuts_per_node=6 if full else 3,
                iterations=local_iterations,
                seed=seed,
            )
        ),
    )

    package = CandidatePackage(
        package_id="korvold-idol-greaves",
        swaps=(
            VariantSwap(remove="Scouring Swarm", add_candidate_id="korvold/idol-of-oblivion"),
            VariantSwap(remove="Evendo Brushrazer", add_candidate_id="korvold/lightning-greaves"),
        ),
    )
    package_search = dump(
        "korvold_package_search",
        service.run_package_search(
            PackageSearchInput(
                deck_id="korvold/current",
                packages=(package,),
                iterations=8 if full else 4,
                seed=seed,
            )
        ),
    )
    pareto = dump(
        "korvold_pareto_front",
        service.evaluate_pareto_front(
            ParetoFrontInput(
                deck_id="korvold/current",
                variants=(
                    (VariantSwap(remove="Scouring Swarm", add_candidate_id="korvold/idol-of-oblivion"),),
                    (VariantSwap(remove="Evendo Brushrazer", add_candidate_id="korvold/lightning-greaves"),),
                    package.swaps,
                ),
                iterations=8 if full else 4,
                seed=seed,
            )
        ),
    )
    shapley = dump(
        "korvold_shapley",
        service.estimate_shapley(
            ShapleyInput(
                deck_id="korvold/current",
                card_names=("Scouring Swarm", "Evendo Brushrazer", "Horizon Explorer"),
                permutations=256 if full else 64,
                iterations=8 if full else 4,
                seed=seed,
            )
        ),
    )

    common_validation = {
        "iterations": validation_iterations,
        "seed": seed,
        "minimum_place_delta": 0.0,
        "sensitivity_seeds": sensitivity_seeds,
        "sensitivity_strengths": sensitivity_strengths,
    }
    korvold_validation = dump(
        "korvold_upgrade_validation",
        service.validate_upgrade(
            ValidateUpgradeInput(
                deck_id="korvold/current",
                swaps=(VariantSwap(remove="Scouring Swarm", add_candidate_id="korvold/idol-of-oblivion"),),
                **common_validation,
            )
        ),
    )
    rogshai_validation = dump(
        "rogshai_upgrade_validation",
        service.validate_upgrade(
            ValidateUpgradeInput(
                deck_id="rogshai/current",
                swaps=(VariantSwap(remove="Izzet Signet", add_candidate_id="rogshai/talisman-of-creativity"),),
                **common_validation,
            )
        ),
    )

    summary = {
        "schema_version": "0.7.0",
        "estimate_type": "structural_model_estimates",
        "validation_mode": "full" if full else "quick",
        "generated_from_local_files_only": True,
        "google_drive_modified": False,
        "automatic_application": False,
        "complete_swap_matrices": {
            "korvold/current": {
                key: korvold_matrix["result"][key]
                for key in ("cells", "valid_cells", "simulated_cells", "matrix_complete")
            },
            "rogshai/current": {
                key: rogshai_matrix["result"][key]
                for key in ("cells", "valid_cells", "simulated_cells", "matrix_complete")
            },
        },
        "searches": {
            "local": local_search["result"],
            "beam": beam_search["result"],
            "package": package_search["result"],
        },
        "pareto_front": pareto["result"].get("pareto_front"),
        "shapley": shapley["result"],
        "validation_chains": {
            "korvold_scouring_swarm_to_idol": korvold_validation["result"],
            "rogshai_izzet_signet_to_talisman": rogshai_validation["result"],
        },
    }
    (ROOT / "PHASE7_VALIDATION_OUTPUT.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use larger validation samples. The default is a faster deterministic smoke run.",
    )
    args = parser.parse_args()
    summary = run(full=args.full)
    print(json.dumps({
        "validation_mode": summary["validation_mode"],
        "complete_swap_matrices": summary["complete_swap_matrices"],
        "korvold_decision": summary["validation_chains"]["korvold_scouring_swarm_to_idol"].get("decision"),
        "rogshai_decision": summary["validation_chains"]["rogshai_izzet_signet_to_talisman"].get("decision"),
        "automatic_application": summary["automatic_application"],
    }, indent=2))


if __name__ == "__main__":
    main()
