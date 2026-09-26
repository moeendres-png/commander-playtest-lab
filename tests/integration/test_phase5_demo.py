from pathlib import Path

from commander_lab.agents.demo import run_phase5_demo

ROOT = Path(__file__).resolve().parents[2]


def test_phase5_demo_end_to_end(tmp_path) -> None:
    # Demo writes only beneath repository data/runs and the phase output file.
    result = run_phase5_demo(ROOT, iterations=3, seed=99)
    assert result["estimate_type"] == "structural_model_estimates"
    assert result["validation"]["status"] == "completed"
    assert result["matchup"]["status"] == "completed"
    assert result["candidate_screening"]["status"] == "completed"
    assert result["paired_test"]["status"] == "completed"
    assert result["upgrade_validation"]["status"] == "completed"
    assert result["upgrade_validation"]["result"]["decision"] in {"confirmed", "rejected"}
    assert Path(result["report"]["result"]["report_path"]).exists()
