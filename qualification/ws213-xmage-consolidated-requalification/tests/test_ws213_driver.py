"""WS213 orchestrator/deck regression tests (no JVM required).

Guards the WS213 requalification inputs:
- production pin is the exact WS212 candidate;
- deck tables are the WS207-corrected tables re-tagged (card multisets
  byte-identical to the sealed WS207 authority);
- behavior prefs reuse WS205 tables plus documented WS213 extras;
- construction list covers every affected available scenario;
- qualified constructions use WS207 catalog seeds;
- budgets are never weakened below WS205/WS207 precedent (500).
"""

import sys
from pathlib import Path

WS213_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS213_ROOT))
sys.path.insert(
    0, str(WS213_ROOT.parent.parent / "qualification/ws207-xmage-qualified-scenario-setup")
)

import ws207_decks as _W207  # noqa: E402
import ws213_decks as decks  # noqa: E402

WS212_PIN = "db134b9737e951367d65ef5806ad986319cc73ab"


def test_engine_pin_is_ws212_production_candidate():
    assert decks.ENGINE_PIN == WS212_PIN


def test_deck_tables_match_ws207_authority():
    for slot, subcase in decks.CONSTRUCTIONS:
        ours = decks.build_decks(slot, subcase)
        sealed = _W207.build_decks(slot, subcase)
        assert set(ours) == set(sealed)
        for seat in ours:
            assert sorted(ours[seat]["mainboard"]) == sorted(sealed[seat]["mainboard"])
            assert sorted(ours[seat]["commanders"]) == sorted(sealed[seat]["commanders"])
            assert ours[seat]["deck_id"].startswith("ws213-")
            assert ours[seat]["deck_hash"] == ours[seat]["deck_id"]


def test_constructions_cover_affected_scenarios():
    keys = {slot if not sub else f"{slot}-{sub}" for slot, sub in decks.CONSTRUCTIONS}
    for required in (
        "RQ-C3-A03",
        "RQ-C3-B01",
        "RQ-C3-C01",
        "RQ-C3-C03",
        "RQ-C3-D06",
        "RQ-C3-E02",
        "RQ-C3-F01",
        "RQ-C3-G04",
        "RQ-C3-H01-HUMILITY_FIRST",
        "RQ-C3-H01-CLONE_FIRST",
        "RQ-C3-H01-NO_HUMILITY",
        "RQ-C3-I01",
    ):
        assert required in keys


def test_qualified_constructions_use_catalog_seeds():
    for key, seed in decks.CATALOG_SEEDS.items():
        assert decks.SEEDS[key] == seed
    assert decks.SEEDS["RQ-C3-A03"] == 9788
    assert decks.SEEDS["RQ-C3-F01"] == 13405
    assert decks.SEEDS["RQ-C3-H01-NO_HUMILITY"] == 16859


def test_budgets_never_weakened():
    assert decks.BUDGET == 500


def test_g04_concede_interrogation_scheduled():
    prefs = decks.build_behavior_prefs("RQ-C3-G04")
    assert prefs["_concede"] == {"after_decisions": 60, "seat": 3}


def test_combat_scan_presses_attack_and_block():
    prefs = decks.build_combat_scan_prefs("RQ-C3-E02")
    assert "declare_attacker" not in prefs
    assert "declare_blocker" not in prefs
    assert prefs["_attack_all"] == [1]
    assert prefs["_block_all"] == [0]
    assert prefs["_spoil_damage_once"] is True
