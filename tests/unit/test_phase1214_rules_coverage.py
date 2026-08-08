from __future__ import annotations

import json
from pathlib import Path


REQUIRED_CARD_FIELDS = {
    "oracle_name",
    "oracle_id",
    "deck_versions",
    "roles",
    "packages",
    "structural_support",
    "tactical_oracle_support",
    "xmage_recognized",
    "xmage_rules_verified",
    "forge_recognized",
    "forge_rules_verified",
    "multiplayer_targeting_verified",
    "commander_interaction_verified",
    "replay_verified",
    "known_provider_bug",
    "fallback_policy",
    "coverage_status",
    "evidence_files",
}

ALLOWED_COVERAGE = {
    "external_engine_verified",
    "external_engine_partial",
    "tactical_only",
    "structural_only",
    "unsupported",
    "provider_disagreement",
}


def _load(repo_root: Path, relative: str) -> dict:
    return json.loads((repo_root / relative).read_text(encoding="utf-8"))


def test_card_coverage_registry_has_complete_scope_and_strict_external_defaults(
    repo_root: Path,
) -> None:
    data = _load(repo_root, "data/rules/card_rules_coverage.json")
    assert data["schema_version"] == 2
    assert data["generated_from_read_only_canonical_drive_snapshot"] is True
    assert data["source_drive_files"] == {
        "decks": "1mO0pnm1thoRrjAg7TGuGSXmrTTYDivJHxrUCdEtY5GQ",
        "inventory": "1_HlokwIebhVKCeQuDvVOpr3BZWYwgKBd",
        "opponents": "1ioeN6CHMWTwYM5ThFn1la4FjFWeDhBaX",
    }
    assert data["external_engine_execution_status"] == "blocked"
    assert len(data["cards"]) == 1698
    assert data["inventory_candidate_count"] == 1335
    assert data["coverage_counts"] == {
        "unsupported": 1443,
        "tactical_only": 59,
        "structural_only": 196,
    }
    for card in data["cards"]:
        assert REQUIRED_CARD_FIELDS <= set(card)
        assert card["xmage_recognized"] is False
        assert card["xmage_rules_verified"] is False
        assert card["forge_recognized"] is False
        assert card["forge_rules_verified"] is False
        assert card["coverage_status"] in ALLOWED_COVERAGE

    stats = data["deck_statistics"]
    assert stats["korvold/current-2026-08-07"]["unique_oracle_names"] == 86
    assert stats["rogshai/current-2026-08-07"]["unique_oracle_names"] == 85
    assert stats["kaervek/maintained-2026-08-07"]["unique_oracle_names"] == 76
    assert stats["opponent/cosmic_spider_man/drive-2026-08-02"]["unique_oracle_names"] == 4
    assert stats["opponent/alen___high_perfect_morcant/drive-2026-08-02"]["unique_oracle_names"] == 54


def test_partial_opponents_do_not_invent_unknown_cards_as_confirmed(repo_root: Path) -> None:
    data = _load(repo_root, "data/rules/card_rules_coverage.json")
    cosmic_version = "opponent/cosmic_spider_man/drive-2026-08-02"
    cosmic = {row["oracle_name"] for row in data["cards"] if cosmic_version in row["deck_versions"]}
    assert cosmic == {
        "Cosmic Spider-Man",
        "Mary Jane Watson",
        "Scarlet Spider, Ben Reilly",
        "Guy in the Chair",
    }

    opponents = _load(repo_root, "data/canonical_import/2026-08-07/opponents.json")
    by_name = {row["deck"]: row for row in opponents["decks"]}
    assert by_name["Cosmic Spider-Man"]["known_card_count"] == 4
    assert by_name["Cosmic Spider-Man"]["unknown_slots"] == 96
    assert by_name["Alen – High Perfect Morcant"]["known_card_count"] == 54
    assert by_name["Alen – High Perfect Morcant"]["provisional_completion_count"] == 18
    assert by_name["Alen – High Perfect Morcant"]["synthetic_basic_count"] == 28
    assert by_name["Alen – High Perfect Morcant"]["unknown_slots"] == 0


def test_required_golden_scenarios_and_named_registry_exports_exist(repo_root: Path) -> None:
    canonical = _load(repo_root, "data/rules/golden_rules_scenarios.json")
    aliases = [
        _load(repo_root, "data/rules/rules_scenario_registry.json"),
        _load(repo_root, "data/rules/golden_rules_corpus.json"),
        _load(repo_root, "artifacts/phase12_14/RULES_SCENARIO_REGISTRY.json"),
        _load(repo_root, "artifacts/phase12_14/GOLDEN_RULES_CORPUS.json"),
    ]
    assert all(alias == canonical for alias in aliases)
    assert len(canonical["scenarios"]) == 37
    assert canonical["coverage_counts"] == {
        "tactical_only": 25,
        "structural_only": 9,
        "unsupported": 3,
    }
    ids = {row["scenario_id"] for row in canonical["scenarios"]}
    assert {
        "korvold_sacrifice_cost_and_trigger",
        "korvold_szarel",
        "rogshai_curiosity",
        "rogshai_sunhome",
        "rogshai_kediss_not_commander_damage",
        "opponent_kaervek_trigger_survives_counter",
        "opponent_minus_counters_vs_indestructible",
        "opponent_cosmic_spiderman_legends",
    } <= ids
    assert all(
        not row["xmage_verified"] and not row["forge_verified"]
        for row in canonical["scenarios"]
    )


def test_unsupported_and_provider_difference_registers_are_truthful(repo_root: Path) -> None:
    unsupported = _load(repo_root, "data/rules/unsupported_card_register.json")
    differences = _load(repo_root, "data/rules/provider_difference_register.json")
    assert unsupported["schema_version"] == 2
    assert len(unsupported["cards"]) == 1443
    assert all(row["coverage_status"] == "unsupported" for row in unsupported["cards"])
    assert differences["status"] == "not_run"
    assert differences["provider_comparisons"] == []
