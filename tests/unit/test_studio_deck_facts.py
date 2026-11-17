"""Bracket check and data gaps of a deck list (#1404 options 1 and 10)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, deck_facts
from commander_lab.studio.web import create_app

from .test_studio_builder import _fill


def _row(card_id: str, name: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "card_id": card_id,
        "oracle_name": name,
        "zone": "main",
        "quantity": 1,
        "type_line": "Sorcery",
        "oracle_text": "",
        "game_changer": 0,
        "mana_value": 2,
        "produced_mana": "",
        "is_basic_land": 0,
        "fact_source": "scryfall",
    }
    row.update(extra)
    return row


def test_game_changer_limits_count_unknown_apart() -> None:
    rows = [
        _row("cmd", "Chulane", zone="commander", type_line="Legendary Creature"),
        _row("a", "Rhystic Study", game_changer=1),
        _row("b", "Smothering Tithe", game_changer=1),
        _row("c", "Cyclonic Rift", game_changer=1),
        _row("d", "Mystery Card", game_changer=None, fact_source="workbook"),
    ]
    facts = deck_facts.bracket_facts(rows, roles={}, combos=None)
    changers = facts["game_changers"]
    assert changers["count"] == 3
    assert changers["unknown"] == 1
    assert [card["name"] for card in changers["unknown_cards"]] == ["Mystery Card"]
    status = {item["bracket"]: item["status"] for item in changers["limits"]}
    # 3 known plus 1 unknown: bracket 3 (at most 3) can be neither confirmed nor refuted.
    assert status == {
        "1": "über der Grenze",
        "2": "über der Grenze",
        "3": "unbekannt",
        "4": "passt",
        "5": "passt",
    }


def test_game_changer_count_over_three_is_over_the_bracket_three_limit() -> None:
    rows = [_row(str(i), f"GC {i}", game_changer=1) for i in range(4)]
    status = {
        item["bracket"]: item["status"]
        for item in deck_facts.bracket_facts(rows, roles={}, combos=None)["game_changers"]["limits"]
    }
    assert status["3"] == "über der Grenze"
    assert status["4"] == "passt"


def test_extra_turns_and_land_denial_are_named_candidates() -> None:
    rows = [
        _row("t", "Time Warp", oracle_text="Target player takes an extra turn after this one."),
        _row("n", "Ugin's Nexus", oracle_text="If a player would begin an extra turn, that player "
             "skips that turn instead. ... Players can't take extra turns."),
        _row("a", "Armageddon", oracle_text="Destroy all lands."),
        _row("j", "Jokulhaups", oracle_text="Destroy all artifacts, creatures, and lands. They "
             "can't be regenerated."),
        _row("r", "Ruination", oracle_text="Destroy all nonbasic lands."),
        _row("w", "Winter Orb", oracle_text="As long as Winter Orb is untapped, players can't "
             "untap more than one land during their untap steps."),
        _row("q", "Rising Waters", oracle_text="Lands don't untap during their controllers' "
             "untap steps."),
        _row("b", "Blood Moon", oracle_text="Nonbasic lands are Mountains."),
        _row("s", "Swords to Plowshares", oracle_text="Exile target creature."),
        _row("k", "Harrow", oracle_text="As an additional cost, sacrifice a land. Search ..."),
        _row("g", "Lantern-Lit Graveyard", type_line="Land", oracle_text="Lantern-Lit Graveyard "
             "enters tapped. ... This land doesn't untap during your next untap step."),
        _row("e", "Elspeth Tirel", oracle_text="-5: Destroy all other permanents except for "
             "lands and tokens."),
        _row("c", "Scourglass", oracle_text="Sacrifice Scourglass: Destroy all permanents except "
             "for artifacts and lands."),
    ]  # fmt: skip
    facts = deck_facts.bracket_facts(rows, roles={}, combos=None)
    assert [card["name"] for card in facts["extra_turns"]["cards"]] == ["Time Warp"]
    denial = {card["name"]: card["rule"] for card in facts["mass_land_denial"]["cards"]}
    assert set(denial) == {
        "Armageddon", "Jokulhaups", "Ruination", "Winter Orb", "Rising Waters", "Blood Moon",
    }  # fmt: skip
    assert facts["mass_land_denial"]["count"] == 6
    assert facts["mass_land_denial"]["of"] == len(rows)
    assert facts["mass_land_denial"]["text_unknown"] == 0


def test_unknown_text_and_flags_are_counted_apart_with_denominators() -> None:
    rows = [
        _row("cmd", "Chulane", zone="commander", game_changer=0),
        _row("a", "Time Walk", oracle_text="Take an extra turn after this one.", quantity=1),
        _row("u", "Workbook Card", oracle_text=None, game_changer=None, fact_source="workbook"),
        _row("t", "Demonic Tutor", game_changer=1),
    ]
    facts = deck_facts.bracket_facts(rows, roles={"t": ["tutor"]}, combos=None)
    assert facts["extra_turns"]["count"] == 1
    assert facts["extra_turns"]["of"] == 2  # cards with known text, commander excluded
    assert facts["extra_turns"]["text_unknown"] == 1
    assert facts["game_changers"]["of"] == 4  # the commander counts
    assert [c["name"] for c in facts["game_changers"]["cards"]] == ["Demonic Tutor"]
    assert [c["name"] for c in facts["game_changers"]["unknown_cards"]] == ["Workbook Card"]
    assert facts["tutors"] == {**facts["tutors"], "count": 1, "of": 3}


def test_vanilla_creature_without_text_is_known_but_missing_card_facts_stay_unknown() -> None:
    rows = [
        _row("v", "Axebane Stag", type_line="Creature — Elk", oracle_text=None),
        _row("n", "Textless Spell", type_line="Sorcery", oracle_text=None),
        _row("w", "Workbook Bear", type_line="Creature", oracle_text=None, fact_source="workbook"),
        _row("e", "No Facts Bear", type_line="Creature", oracle_text=None, fact_source=None),
        _row("a", "Time Walk", oracle_text="Take an extra turn after this one."),
    ]
    facts = deck_facts.bracket_facts(rows, roles={}, combos=None)
    # Known: the vanilla creature (facts exist, no rules text) and Time Walk; unknown: the rest.
    assert facts["extra_turns"]["of"] == 2
    assert facts["extra_turns"]["text_unknown"] == 3
    assert facts["extra_turns"]["count"] == 1


def test_tutors_split_land_search_and_report_role_coverage() -> None:
    rows = [
        _row("e", "Enlightened Tutor"),
        _row("n", "Nature's Lore"),
        _row("x", "No Role Card"),
        _row("l", "Forest", type_line="Basic Land — Forest", is_basic_land=1),
    ]
    roles = {"e": ["tutor"], "n": ["land_ramp", "tutor"]}
    tutors = deck_facts.bracket_facts(rows, roles=roles, combos=None)["tutors"]
    assert tutors["count"] == 2
    assert tutors["land_search"] == 1
    assert [card["name"] for card in tutors["land_search_cards"]] == ["Nature's Lore"]
    # Lands are no tutors and do not count in the role coverage denominator.
    assert tutors["role_data"] == {"with_roles": 2, "of": 3}


def test_two_card_combos_unknown_without_a_list_never_zero() -> None:
    rows = [_row("a", "A")]
    assert deck_facts.bracket_facts(rows, roles={}, combos=None)["two_card_combos"]["count"] is None
    empty = {"listed": 0, "complete": []}
    assert (
        deck_facts.bracket_facts(rows, roles={}, combos=empty)["two_card_combos"]["count"] is None
    )
    listed = {
        "listed": 5,
        "complete": [
            {"cards": ["A", "B"], "num_decks": 9},
            {"cards": ["A", "B", "C"], "num_decks": 4},
        ],
    }
    combos = deck_facts.bracket_facts(rows, roles={}, combos=listed)["two_card_combos"]
    assert combos["count"] == 1
    assert combos["listed"] == 5
    assert combos["combos"] == [{"cards": ["A", "B"], "num_decks": 9}]


def test_data_gaps_name_each_reason_with_its_denominator() -> None:
    rows = [
        _row("cmd", "Chulane", zone="commander", fact_source="workbook"),
        _row("a", "Known Card"),
        _row("b", "Roleless Card"),
        _row("c", "Workbook Card", fact_source="workbook", mana_value=None),
        _row("d", "Odd Land", type_line="Land", produced_mana=None),
        _row("f", "Forest", type_line="Basic Land — Forest", produced_mana=None, is_basic_land=1),
    ]
    roles = {"a": ["ramp"], "c": ["removal"]}
    gaps = deck_facts.data_gaps(
        rows,
        roles=roles,
        in_source_decks=lambda name: name != "Odd Land",
        has_edhrec=lambda card_id, name: card_id in {"a", "b"},
    )
    assert gaps["cards_checked"] == 5  # the commander is not checked
    by_card = {item["name"]: item["reasons"] for item in gaps["gaps"]}
    assert by_card == {
        "Roleless Card": ["no_role"],
        "Workbook Card": ["no_card_data", "mana_value_unknown", "no_edhrec"],
        "Odd Land": ["land_colours_unknown", "no_source_deck", "no_edhrec"],
    }
    # Forest: colours known from its basic type; basics skip the source checks.
    assert gaps["by_reason"]["land_colours_unknown"] == {"count": 1, "of": 2}
    assert gaps["by_reason"]["no_role"] == {"count": 1, "of": 3}
    assert gaps["by_reason"]["no_edhrec"] == {"count": 2, "of": 4}
    assert gaps["sources_missing"] == []
    assert gaps["cards_with_gaps"] == 3


def test_data_gaps_without_a_source_report_it_once_not_per_card() -> None:
    rows = [_row("a", "A")]
    gaps = deck_facts.data_gaps(rows, roles={"a": ["ramp"]}, in_source_decks=None, has_edhrec=None)
    assert gaps["sources_missing"] == ["no_source_deck", "no_edhrec"]
    assert "no_source_deck" not in gaps["by_reason"]
    assert gaps["gaps"] == []


def test_deck_facts_route_on_a_store(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [{"card_id": "card:project:0001", "quantity": 1, "zone": "commander"}]
    cards += [
        {"card_id": f"card:project:{100 + i:04d}", "quantity": 1, "zone": "main"} for i in range(3)
    ]
    response = client.post("/api/deck-facts", json={"cards": cards})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["bracket"]["schema"] == deck_facts.SCHEMA
    assert body["bracket"]["game_changers"]["count"] == 0
    assert body["data_gaps"]["cards_checked"] == 3
    # No combo list is stored for the test commander: unknown, not 0.
    assert body["bracket"]["two_card_combos"]["count"] is None


# --- data gaps: EDHREC lookup by name, audit note, thin cohorts (#1404 option 10) ---


def _observe(store: StudioStore, name: str, card_id: str | None, value: float | None) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    store.connection.execute(
        "INSERT INTO observation(card_id, card_name, metric, cohort, value, numerator, "
        "denominator, data_class, source_id) VALUES (?, ?, 'inclusion_pct', 'edhrec:test', ?, "
        "1, 10, 'ORIGINAL_SOURCE', ?)",
        (card_id, name, value, source),
    )
    store.connection.commit()


def test_edhrec_lookup_finds_front_face_names_without_card_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import universe

    store = StudioStore.open(tmp_path / "studio")
    monkeypatch.setattr(
        universe,
        "_card_name_index",
        lambda _store: (
            {
                "Brazen Borrower // Petty Theft": frozenset(
                    {"brazen borrower // petty theft", "brazen borrower"}
                )
            },
            {
                "brazen borrower // petty theft": "Brazen Borrower // Petty Theft",
                "brazen borrower": "Brazen Borrower // Petty Theft",
            },
        ),
    )
    _fill(store, tmp_path)
    _observe(store, "Brazen Borrower", None, 12.5)
    _observe(store, "Linked Card", "card:project:0002", 9.0)
    _observe(store, "Empty Value", None, None)
    store.bind_unbound("Test Commander")
    lookup = deck_facts.edhrec_lookup(store, ["Test Commander"])
    assert lookup is not None
    assert lookup("x", "Brazen Borrower // Petty Theft")  # front face of a two-name card
    assert lookup("x", "brazen borrower")  # case-insensitive
    assert lookup("card:project:0002", "Other Spelling")  # linked by card id as before
    assert not lookup("y", "Empty Value")  # a NULL value is no observation
    assert not lookup("y", "Fleetfoot Panther")
    assert deck_facts.edhrec_lookup(store, ["Other Commander"]) is None
    store.close()


def test_edhrec_lookup_never_credits_a_card_through_a_shared_front_face(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import universe

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    _observe(store, "Fire", None, 8.0)  # the single-faced card Fire
    _observe(store, "Shared Front", None, 7.0)  # front face of two different cards
    _observe(store, "Solo Front", None, 6.0)  # front face of exactly one card
    store.bind_unbound("Test Commander")
    # "fire" names the card Fire; "shared front" names two cards (absent from `unique`).
    by_oracle = {
        "Fire": frozenset({"fire"}),
        "Fire // Ice": frozenset({"fire // ice"}),
        "Solo Front // Back": frozenset({"solo front // back", "solo front"}),
    }
    unique = {"fire": "Fire", "fire // ice": "Fire // Ice", "solo front": "Solo Front // Back"}
    monkeypatch.setattr(universe, "_card_name_index", lambda _store: (by_oracle, unique))
    lookup = deck_facts.edhrec_lookup(store, ["Test Commander"])
    assert lookup is not None
    assert lookup("x", "Fire")
    assert not lookup("x", "Fire // Ice")  # the observation belongs to Fire, not to Fire // Ice
    assert lookup("x", "Solo Front // Back")  # a front face owned by one card credits that card
    assert not lookup("x", "Shared Front // Other")  # a shared front face credits no card
    store.close()


def _gap_rows() -> list[dict[str, object]]:
    return [
        _row("cmd", "Chief", zone="commander"),
        _row("a", "Tuned Zero"),
        _row("b", "All Thin"),
        _row("c", "Fine Card"),
        _row("d", "No Deck Card"),
        _row("f", "Forest", type_line="Basic Land — Forest", is_basic_land=1),
    ]


def test_thin_in_cohort_names_n_of_n_and_keeps_zero_apart_from_unknown() -> None:
    hits = {
        "Tuned Zero": {"all": 200, "tuned": 0},
        "All Thin": {"all": 5, "tuned": 50},
        "Fine Card": {"all": 100, "tuned": 100},
    }
    gaps = deck_facts.data_gaps(
        _gap_rows(),
        roles={x: ["r"] for x in "abcdf"},
        in_source_decks=lambda name: name in hits,
        has_edhrec=lambda card_id, name: True,
        cohort_hits=hits,
        cohort_sizes={"all": 1500, "tuned": 1064},
    )
    by_card = {item["name"]: item for item in gaps["gaps"]}
    assert set(by_card) == {"Tuned Zero", "All Thin", "No Deck Card"}
    assert by_card["Tuned Zero"]["reasons"] == []  # a note, not a missing datum
    assert by_card["Tuned Zero"]["thin"] == [{"cohort": "tuned", "n": 0, "of": 1064}]
    assert by_card["All Thin"]["thin"] == [{"cohort": "all", "n": 5, "of": 1500}]
    # No source deck at all stays unknown and gets no cohort count.
    assert by_card["No Deck Card"]["reasons"] == ["no_source_deck"]
    assert "thin" not in by_card["No Deck Card"]
    assert gaps["by_reason"]["thin_in_cohort"] == {"count": 2, "of": 3}
    assert gaps["by_reason"]["no_source_deck"] == {"count": 1, "of": 4}
    # A thin count is a note about the sample, not a missing datum.
    assert gaps["cards_with_gaps"] == 1
    assert gaps["cards_with_thin"] == 2


def test_thin_in_cohort_is_off_without_cohort_data() -> None:
    gaps = deck_facts.data_gaps(
        _gap_rows(),
        roles={x: ["r"] for x in "abcdf"},
        in_source_decks=lambda name: True,
        has_edhrec=lambda card_id, name: True,
    )
    assert "thin_in_cohort" not in gaps["by_reason"]
    assert gaps["gaps"] == []


def test_edhrec_reason_text_names_audit_source_and_date_only_when_given() -> None:
    plain = deck_facts.data_gaps(
        _gap_rows(), roles={}, in_source_decks=None, has_edhrec=lambda c, n: False
    )
    assert "Mindestquote" not in plain["reason_labels"]["no_edhrec"]
    audited = deck_facts.data_gaps(
        _gap_rows(),
        roles={},
        in_source_decks=None,
        has_edhrec=lambda c, n: False,
        edhrec_note=deck_facts.EDHREC_THRESHOLD_NOTE,
    )
    text = audited["reason_labels"]["no_edhrec"]
    assert "Mindestquote" in text and "2026-11-12" in text
    assert "%" not in text  # no number the audit text does not carry for the card
