from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_adaptive_budget_policy_gate_preserves_material_finalists(tmp_path: Path) -> None:
    output = tmp_path / "adaptive_budget_benchmark.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/benchmark_priority_racing.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["decision"] == "PASS_SHIP"
    assert result["production_scheduler_shipped"] is True
    assert result["execution_mode"] == "deterministic_policy_safety_gate_no_structural_game_rerun"
    assert result["decision_trace_reproducibility"] is True
    assert result["decision_agreement"] is True
    assert result["material_finalist_recall"] == 1.0
    assert result["false_elimination_rate_of_material_finalists"] == 0.0
    assert result["full_control_paired_iterations"] == 144
    assert result["conservative_paired_iterations"] == 96
    assert result["simulation_reduction"] >= 0.30
    assert result["noisy_early_elimination_allowed"] is False
    assert result["aggressive_control"]["production_allowed"] is False
    assert result["aggressive_control"]["historical_reference_is_current_measurement"] is False
