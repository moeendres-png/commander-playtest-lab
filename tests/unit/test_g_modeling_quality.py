from __future__ import annotations

import json

from commander_lab.engine.structural.fixtures import build_current_opponent_profiles
from commander_lab.models import CardRole, FormatBand, MetaCategory, StructuralMechanic


def _by_name(deck):
    return {card.oracle_name: card for card in deck.cards}


def test_opponent_evidence_statuses_and_unknowns_are_explicit(repo_root) -> None:
    raw = json.loads((repo_root / "data/opponents/current_structural_profiles.json").read_text(encoding="utf-8"))
    specs = {row["deck_id"]: row for row in raw["profiles"]}
    allowed = {"verified", "observed", "reported", "synthetic", "unknown"}
    assert all(spec.get("evidence_status") in allowed for spec in specs.values())
    cosmic = specs["opponent/cosmic-spiderman-midbudget"]
    assert cosmic["confirmed_card_count"] == 4
    assert cosmic["unknown_slot_count"] == 96
    morcant = specs["opponent/morcant-elves"]
    assert morcant["confirmed_card_count"] == 54
    assert morcant["provisional_completion_count"] == 18
    assert morcant["synthetic_basic_count"] == 28
    doom = specs["opponent/doom-prevails-precon"]
    assert doom["baseline_precon_cards"] == 100
    assert doom["upgrade_slots_unknown"] is True


def test_official_precon_commanders_and_native_decision_cards_are_structurally_named(repo_root) -> None:
    decks = build_current_opponent_profiles(
        repo_root / "data/opponents/current_structural_profiles.json",
        data_snapshot_hash="0" * 64,
    )
    doom = decks["opponent/doom-prevails-precon"]
    dance = decks["opponent/dance-elements-precon"]
    wakanda = decks["opponent/wakanda-forever-precon"]
    assert doom.commander_names == ("Doctor Doom, King of Latveria",)
    assert doom.commander_base_costs["Doctor Doom, King of Latveria"] == 4.0
    assert doom.commander_base_power["Doctor Doom, King of Latveria"] == 3.0
    assert dance.commander_names == ("Ashling, the Limitless",)
    assert dance.commander_base_costs["Ashling, the Limitless"] == 3.0
    assert wakanda.commander_names == ("T'Challa, the Black Panther",)
    assert wakanda.commander_base_costs["T'Challa, the Black Panther"] == 3.0

    assert {"Black Market Connections", "Toxic Deluge", "Vandalblast"}.issubset(_by_name(doom))
    assert {"Muldrotha, the Gravetide", "Risen Reef", "Bane of Progress"}.issubset(_by_name(dance))
    assert {"Conduit of Worlds", "Trading Post", "Overwhelming Stampede"}.issubset(_by_name(wakanda))
    assert all(len(deck.cards) == 100 for deck in (doom, dance, wakanda))


def test_partial_opponents_gain_native_cards_without_faking_completion(repo_root) -> None:
    decks = build_current_opponent_profiles(
        repo_root / "data/opponents/current_structural_profiles.json",
        data_snapshot_hash="0" * 64,
    )
    morcant = _by_name(decks["opponent/morcant-elves"])
    cosmic = _by_name(decks["opponent/cosmic-spiderman-midbudget"])
    assert {"Elvish Archdruid", "Flourishing Defenses", "Hapatra, Vizier of Poisons", "Deathreap Ritual"}.issubset(morcant)
    assert {"Cosmic Spider-Man", "Mary Jane Watson", "Scarlet Spider, Ben Reilly", "Guy in the Chair"}.issubset(cosmic)
    # The model stays a 100-card structural completion; only the four hard-known Cosmic names are represented natively.
    assert len(decks["opponent/cosmic-spiderman-midbudget"].cards) == 100
    assert sum("role card" in card.oracle_name for card in decks["opponent/cosmic-spiderman-midbudget"].cards) > 0


def test_kaervek_native_nonbasic_utility_and_color_production(repo_root) -> None:
    decks = build_current_opponent_profiles(
        repo_root / "data/opponents/current_structural_profiles.json",
        data_snapshot_hash="0" * 64,
    )
    cards = _by_name(decks["kaervek/current"])
    assert CardRole.SELECTION in cards["Temple of Malice"].roles
    assert CardRole.SELECTION in cards["Barren Moor"].roles
    assert CardRole.SELECTION in cards["Path of Ancestry"].roles
    assert CardRole.GRAVEYARD_HATE in cards["Bojuka Bog"].roles
    assert {color.value for color in cards["Barren Moor"].produces_colors} == {"B"}
    assert {color.value for color in cards["Bojuka Bog"].produces_colors} == {"B"}
    assert {color.value for color in cards["Mountain"].produces_colors} == {"R"}


def test_mechanic_tags_distinguish_table_and_commander_damage_and_rebuild(structural_profiles) -> None:
    kediss = structural_profiles.resolve("Kediss, Emberclaw Familiar")
    jeska = structural_profiles.resolve("Jeska, Thrice Reborn")
    bats = structural_profiles.resolve("Mirkwood Bats")
    analyst = structural_profiles.resolve("Aftermath Analyst")
    counterspell = structural_profiles.resolve("Counterspell")

    assert StructuralMechanic.TABLE_DAMAGE in kediss.mechanic_tags
    assert StructuralMechanic.COMMANDER_DAMAGE_SUPPORT not in kediss.mechanic_tags
    assert StructuralMechanic.COMMANDER_DAMAGE_SUPPORT in jeska.mechanic_tags
    assert StructuralMechanic.TABLE_DAMAGE not in jeska.mechanic_tags
    assert StructuralMechanic.TABLE_DAMAGE in bats.mechanic_tags
    assert {StructuralMechanic.REBUILD, StructuralMechanic.LAND_RECURSION}.issubset(analyst.mechanic_tags)
    assert StructuralMechanic.STACK_INTERACTION in counterspell.mechanic_tags


def test_meta_context_has_explicit_three_four_and_five_player_bands() -> None:
    assert MetaCategory.COMMANDER_THREE_PLAYER.value == "commander_3_player"
    assert MetaCategory.NORMAL_FOUR_PLAYER.value == "normal_four_player"
    assert MetaCategory.COMMANDER_FIVE_PLAYER.value == "commander_5_player"
    assert FormatBand.COMMANDER_THREE_PLAYER.value == "commander_3_player"
    assert FormatBand.NORMAL_FOUR_PLAYER.value == "normal_four_player"
    assert FormatBand.COMMANDER_FIVE_PLAYER.value == "commander_5_player"
