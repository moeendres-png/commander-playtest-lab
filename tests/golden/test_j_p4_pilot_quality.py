from __future__ import annotations

import hashlib
import json

REQUIRED_DIMENSIONS = {
    "survival",
    "mana_efficiency",
    "card_advantage",
    "tempo",
    "engine_development",
    "interaction_reserve",
    "commander_value",
    "threat_reduction",
    "win_progress",
    "political_visibility",
    "rebuild_capacity",
}


def test_j_p4_holdout_bytes_match_pre_tuning_seal_without_evaluating(repo_root) -> None:
    seal = json.loads((repo_root / "docs/J_P4_HOLDOUT_SEAL.json").read_text(encoding="utf-8"))
    holdout = repo_root / seal["holdout_path"]
    assert hashlib.sha256(holdout.read_bytes()).hexdigest() == seal["sha256"]
    payload = json.loads(holdout.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == seal["case_count"] == 24
    assert seal["outcomes_evaluated_at_seal"] is False
    assert seal["immutable_after_seal"] is True
    # This test intentionally does not call run_golden_cases on the holdout.
