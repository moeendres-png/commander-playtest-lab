from __future__ import annotations

import json
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_priority_racing_benchmark_reports_ship_or_justified_not_shipped(
    tmp_path: Path,
) -> None:
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
    assert result["decision"] in {"PASS_SHIP", "JUSTIFIED_NOT_SHIPPED"}
    assert result["decision_trace_reproducibility"] is True
    assert result["known_bad_rejection"] is True
    ship_quality = all(
        (
            result["simulation_reduction"] >= 0.30,
            result["finalist_recovery"] is True,
            result["top_k_overlap_k1"] == 1.0,
            result["known_good_recovery"] is True,
            result["known_bad_rejection"] is True,
        )
    )
    assert (result["decision"] == "PASS_SHIP") is ship_quality
    warnings.warn(
        "PRIORITY_RACING_BENCHMARK "
        f"decision={result['decision']} "
        f"reduction={result['simulation_reduction']:.6f} "
        f"finalists={result['finalist_ids']} "
        f"full_top={result['full_control_ranking'][0]} "
        f"racing_top={result['racing_ranking'][0] if result['racing_ranking'] else None} "
        f"control_pairs={result['full_control_paired_iterations']} "
        f"racing_pairs={result['racing_paired_iterations']}",
        UserWarning,
        stacklevel=1,
    )
