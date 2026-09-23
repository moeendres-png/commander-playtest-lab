from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_smoke_module(repo_root: Path) -> ModuleType:
    path = repo_root / "scripts/run_real_4p_full_game_smoke.py"
    spec = importlib.util.spec_from_file_location("run_real_4p_full_game_smoke", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_4p_setup_uses_four_existing_complete_decks(repo_root: Path) -> None:
    module = _load_smoke_module(repo_root)
    scenario, decks, pilots, provenance = module.build_real_4p_setup(repo_root)

    assert scenario.player_count == 4
    assert scenario.seat == 1
    assert scenario.candidate_id == "rogshai/current"
    assert scenario.opponent_deck_ids == (
        "kaervek/current",
        "opponent/hosts-of-mordor-precon",
        "opponent/lorehold-spirit-precon",
    )
    assert len(decks) == len(pilots) == len(provenance) == 4
    assert [len(deck.mainboard) + len(deck.commander_names) for deck in decks] == [100] * 4
    assert [binding.seat for binding in pilots] == [1, 2, 3, 4]
    assert all(deck.deck_hash is not None for deck in decks)
    assert all(row["total_cards"] == 100 for row in provenance)


def test_real_4p_setup_preserves_command_zone_configuration(repo_root: Path) -> None:
    module = _load_smoke_module(repo_root)
    _scenario, decks, _pilots, provenance = module.build_real_4p_setup(repo_root)

    assert decks[0].commander_names == (
        "Ishai, Ojutai Dragonspeaker",
        "Rograkh, Son of Rohgahh",
    )
    assert decks[1].commander_names == ("Kaervek the Merciless",)
    assert decks[2].commander_names == ("Sauron, Lord of the Rings",)
    assert decks[3].commander_names == ("Quintorius, History Chaser",)
    assert provenance[0]["deck_hash_source"] == "source_snapshot"
    assert provenance[1]["deck_hash_source"] == "source_snapshot"
    assert provenance[2]["deck_hash_source"] == "derived_rules_identity"
    assert provenance[3]["deck_hash_source"] == "derived_rules_identity"


def test_real_4p_preflight_is_technical_evidence_only(repo_root: Path, tmp_path: Path) -> None:
    module = _load_smoke_module(repo_root)

    # Exercise setup/report semantics without mutating canonical repo artifacts.
    scenario, _decks, _pilots, provenance = module.build_real_4p_setup(repo_root)
    report = module._base_report(scenario, provenance)

    assert report["evidence_class"] == "technical_conformance_only"
    assert report["rules_authority"] == "xmage"
    assert report["decision_authority"] == "commander_lab_external_pilots"
    assert report["canonical_data_mutated"] is False
    assert report["official_campaign_eligible"] is False
    assert report["deck_strength_evidence"] is False
    assert report["actual_card_behavior_coverage_claim"] is False
