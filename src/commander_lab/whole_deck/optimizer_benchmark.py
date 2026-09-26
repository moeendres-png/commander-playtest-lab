from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from commander_lab.storage import atomic_write_json

from .optimizer_calibration import calibration_report

BENCHMARK_VERSION = "optimizer-v2-ab-0.1.0"


def _load_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"benchmark input must be a JSON object: {path}")
    return payload


def _number(mapping: dict[str, Any], key: str) -> float:
    value = mapping.get(key)
    if not isinstance(value, int | float):
        raise TypeError(f"benchmark field {key} must be numeric")
    return float(value)


def compare_legacy_to_v2(
    *,
    legacy_path: str | Path,
    v2_search_report_path: str | Path,
) -> dict[str, object]:
    legacy = _load_object(legacy_path)
    v2 = _load_object(v2_search_report_path)
    legacy_search = legacy.get("search")
    legacy_evaluation = legacy.get("evaluation")
    v2_search = v2.get("search")
    if not isinstance(legacy_search, dict) or not isinstance(legacy_evaluation, dict):
        raise TypeError("legacy benchmark reference is malformed")
    if not isinstance(v2_search, dict):
        raise TypeError("v2 search report is malformed")
    archive = v2_search.get("archive")
    if not isinstance(archive, dict):
        raise TypeError("v2 archive report is malformed")

    legacy_unique = _number(legacy_search, "unique_legal_decks")
    v2_unique = _number(v2_search, "unique_legal_decks")
    legacy_cells = _number(legacy_search, "qd_occupied_cells")
    v2_cells = _number(archive, "occupied_cells")
    legacy_pairs = _number(legacy_evaluation, "paired_scenario_evaluations")
    v2_pairs = _number(v2_search, "requested_scenario_pairs")
    legacy_pairs_per_deck = legacy_pairs / max(1.0, legacy_unique)
    v2_pairs_per_deck = v2_pairs / max(1.0, v2_unique)
    discovery_gain = v2_unique - legacy_unique
    qd_gain = v2_cells - legacy_cells
    efficiency_ratio = v2_pairs_per_deck / legacy_pairs_per_deck
    calibration = calibration_report()
    calibration_summary = calibration["summary"]
    assert isinstance(calibration_summary, dict)

    protected = (
        v2.get("confirmatory_partition_opened") is False
        and v2.get("sealed_holdout_partition_opened") is False
        and v2.get("official_winner_declared") is False
        and v2.get("canonical_deck_mutation") is False
    )
    material_benefit = discovery_gain > 0 or qd_gain > 0 or efficiency_ratio < 0.90
    return {
        "schema_version": "1.0.0",
        "benchmark_version": BENCHMARK_VERSION,
        "classification": "technical_system_benchmark_not_real_commander_winrate",
        "compute_normalization": {
            "legacy_paired_scenario_evaluations": int(legacy_pairs),
            "v2_requested_paired_scenario_evaluations": int(v2_pairs),
            "legacy_pairs_per_unique_legal_deck": legacy_pairs_per_deck,
            "v2_pairs_per_unique_legal_deck": v2_pairs_per_deck,
            "v2_to_legacy_pairs_per_deck_ratio": efficiency_ratio,
        },
        "discovery": {
            "legacy_unique_legal_decks": int(legacy_unique),
            "v2_unique_legal_decks": int(v2_unique),
            "unique_legal_deck_delta": int(discovery_gain),
            "legacy_qd_occupied_cells": int(legacy_cells),
            "v2_qd_occupied_cells": int(v2_cells),
            "qd_occupied_cell_delta": int(qd_gain),
            "v2_mean_archive_novelty": archive.get("mean_novelty"),
        },
        "decision_quality": {
            "legacy_calibration_suite": "NOT_AVAILABLE_HISTORICALLY",
            "v2_synthetic_calibration": calibration_summary,
            "decision_accuracy_delta": "not_numerically_comparable_to_uncalibrated_legacy",
        },
        "governance": {
            "confirmatory_unused": v2.get("confirmatory_partition_opened") is False,
            "sealed_holdout_unused": v2.get("sealed_holdout_partition_opened") is False,
            "official_winner_not_declared": v2.get("official_winner_declared") is False,
            "canonical_deck_unchanged_by_run": v2.get("canonical_deck_mutation") is False,
            "protected": protected,
        },
        "acceptance": {
            "material_benefit_on_at_least_one_axis": material_benefit,
            "no_governance_regression": protected,
            "v2_benchmark_pass": material_benefit and protected,
        },
        "truth_boundary": "Search and paired results are structural-model system evidence only.",
    }


def write_benchmark_report(
    *,
    legacy_path: str | Path,
    v2_search_report_path: str | Path,
    output_path: str | Path,
) -> Path:
    report = compare_legacy_to_v2(
        legacy_path=legacy_path,
        v2_search_report_path=v2_search_report_path,
    )
    return atomic_write_json(output_path, report)
