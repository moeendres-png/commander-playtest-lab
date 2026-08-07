from __future__ import annotations

import json
from pathlib import Path


def test_card_coverage_registry_has_strict_external_defaults(repo_root: Path) -> None:
    data = json.loads((repo_root / "data/rules/card_rules_coverage.json").read_text())
    assert data["external_engine_execution_status"] == "blocked"
    assert data["cards"]
    for card in data["cards"]:
        assert card["xmage_rules_verified"] is False
        assert card["forge_rules_verified"] is False
        assert card["coverage_status"] in {
            "external_engine_verified", "external_engine_partial", "tactical_only",
            "structural_only", "unsupported", "provider_disagreement",
        }
    assert data["deck_statistics"]["korvold/current-2026-08-07"]["unique_oracle_names"] == 85
    assert data["deck_statistics"]["rogshai/current-2026-08-07"]["unique_oracle_names"] == 82
    assert data["deck_statistics"]["kaervek/maintained-2026-08-07"]["unique_oracle_names"] == 76


def test_required_golden_scenarios_exist_without_false_external_claims(repo_root: Path) -> None:
    data = json.loads((repo_root / "data/rules/golden_rules_scenarios.json").read_text())
    ids = {row["scenario_id"] for row in data["scenarios"]}
    assert {
        "korvold_szarel", "rogshai_curiosity", "rogshai_sunhome",
        "opponent_kaervek_trigger_survives_counter",
        "opponent_minus_counters_vs_indestructible",
        "opponent_cosmic_spiderman_legends",
    } <= ids
    assert all(not row["xmage_verified"] and not row["forge_verified"] for row in data["scenarios"])
