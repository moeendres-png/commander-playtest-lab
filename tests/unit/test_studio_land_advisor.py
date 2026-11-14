"""Land advisor: an observation of the mana base against the coloured symbols, with the
figures of the comparison groups. No recommendation. All data here is synthetic."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, land_advisor
from commander_lab.studio.web import create_app


def _row(
    name: str,
    *,
    zone: str = "main",
    quantity: int = 1,
    type_line: str = "Creature",
    cost: str = "",
    produced: str = "",
    layout: str = "normal",
    identity: str = "",
) -> dict[str, object]:
    return {
        "oracle_name": name,
        "zone": zone,
        "quantity": quantity,
        "type_line": type_line,
        "mana_cost": cost,
        "produced_mana": produced,
        "layout": layout,
        "color_identity": identity,
    }


def _by_colour(profile: dict[str, object]) -> dict[str, dict[str, object]]:
    colours = profile["colours"]
    assert isinstance(colours, list)
    return {str(entry["colour"]): entry for entry in colours}


def test_pips_sources_and_shares_against_a_hand_count() -> None:
    rows = [
        _row("Cmdr", zone="commander", type_line="Legendary Creature", cost="{1}{G}{W}{U}",
             identity="GWU"),
        _row("Forest", quantity=10, type_line="Basic Land — Forest", produced="G"),
        _row("Island", quantity=6, type_line="Basic Land — Island", produced="U"),
        _row("Tri Land", quantity=2, type_line="Land", produced="GWU"),
        _row("Green Spell", quantity=3, cost="{2}{G}{G}"),
        _row("Blue Spell", quantity=2, cost="{U}"),
        _row("Gold Spell", quantity=1, cost="{G}{U}"),
        _row("Rock", type_line="Artifact", cost="{2}", produced="C"),
        _row("Green Rock", type_line="Artifact", cost="{3}", produced="G"),
    ]  # fmt: skip
    profile = land_advisor.deck_profile(rows)
    assert profile["lands"] == 18
    assert profile["nonland"] == 3 * 1 + 2 + 1 + 1 + 1
    colours = _by_colour(profile)
    # pips: G = 3*2 + 1 = 7, U = 2 + 1 = 3, W = 0; the commander's cost is not in the deck pips
    assert colours["G"]["pips"] == 7
    assert colours["U"]["pips"] == 3
    assert colours["W"]["pips"] == 0
    assert profile["total_pips"] == 10
    assert colours["G"]["pip_share"] == 0.7
    assert colours["U"]["pip_share"] == 0.3
    # land sources: G = 10 + 2, U = 6 + 2, W = 2 (the three-colour land counts for each colour)
    assert colours["G"]["land_sources"] == 12
    assert colours["U"]["land_sources"] == 8
    assert colours["W"]["land_sources"] == 2
    # a non-land producer is reported apart, never added to the land sources
    assert colours["G"]["other_sources"] == 1
    assert profile["commander_pips"] == {"G": 1, "W": 1, "U": 1}
    assert profile["identity"] == ["W", "U", "G"]


def test_hybrid_phyrexian_colourless_and_x_costs() -> None:
    rows = [
        _row("Cmdr", zone="commander", identity="GWU"),
        _row("Hybrid", cost="{W/U}{W/U}"),
        _row("Phyrexian", cost="{1}{G/P}"),
        _row("Generic Hybrid", cost="{2/W}"),
        _row("Colourless", cost="{C}{C}"),
        _row("Xspell", cost="{X}{X}{G}"),
    ]
    profile = land_advisor.deck_profile(rows)
    colours = _by_colour(profile)
    assert colours["W"]["pips"] == 2 + 1  # a hybrid symbol counts for both of its colours
    assert colours["U"]["pips"] == 2
    assert colours["G"]["pips"] == 2  # Phyrexian green and the X spell's green
    assert profile["colourless_pips"] == 2
    assert profile["total_pips"] == 3 + 2 + 2


def test_split_cards_count_both_halves_and_other_two_faced_cards_the_front() -> None:
    rows = [
        _row("Cmdr", zone="commander", identity="RU"),
        _row("Fire // Ice", type_line="Instant // Instant", cost="{1}{R} // {1}{U}",
             layout="split"),
        _row("Adventure", cost="{2}{R}{R} // {1}{U}", layout="adventure"),
    ]  # fmt: skip
    colours = _by_colour(land_advisor.deck_profile(rows))
    assert colours["R"]["pips"] == 1 + 2
    assert colours["U"]["pips"] == 1  # only the split card's second half


def test_a_modal_two_faced_spell_land_is_a_spell_with_its_land_side_named_apart() -> None:
    rows = [
        _row("Cmdr", zone="commander", identity="G"),
        _row("Spell Land", type_line="Sorcery // Land", cost="{2}{G} // ",
             produced="G", layout="modal_dfc"),
        _row("Forest", quantity=3, type_line="Basic Land — Forest", produced="G"),
    ]  # fmt: skip
    profile = land_advisor.deck_profile(rows)
    assert profile["lands"] == 3
    assert profile["nonland"] == 1
    assert profile["modal_land_backs"] == 1
    colours = _by_colour(profile)
    assert colours["G"]["land_sources"] == 3
    assert colours["G"]["modal_sources"] == 1
    assert colours["G"]["pips"] == 1


def test_a_land_without_a_known_colour_is_unknown_not_zero() -> None:
    rows = [
        _row("Cmdr", zone="commander", identity="G"),
        _row("Mystery Land", type_line="Land", produced=""),
        _row("Forest", type_line="Basic Land — Forest", produced=""),
    ]
    profile = land_advisor.deck_profile(rows)
    assert profile["lands_unknown_colours"] == 1  # the basic type tells its colour, the other not
    assert _by_colour(profile)["G"]["land_sources"] == 1


def test_a_colour_outside_the_commander_identity_is_marked() -> None:
    rows = [
        _row("Cmdr", zone="commander", identity="G"),
        _row("Stray", cost="{R}"),
    ]
    colours = _by_colour(land_advisor.deck_profile(rows))
    assert colours["G"]["in_identity"] is True
    assert colours["R"]["in_identity"] is False


def test_no_coloured_symbols_gives_no_share() -> None:
    profile = land_advisor.deck_profile([_row("Cmdr", zone="commander", identity="G")])
    assert profile["total_pips"] == 0
    assert _by_colour(profile)["G"]["pip_share"] is None


def test_the_profile_holds_no_advice_text() -> None:
    profile = land_advisor.deck_profile([_row("Cmdr", zone="commander", identity="G")])
    text = str(profile).casefold()
    for word in ("add ", "füge", "solltest", "empfehl", "mehr länder"):
        assert word not in text


def test_group_figures_have_median_middle_half_and_the_small_flag() -> None:
    decks = [
        {
            "lands": 36 + i % 3,
            "colours": {"G": {"land_sources": 10 + i, "pips": 20, "pip_share": 0.5}},
        }
        for i in range(5)
    ]
    group = land_advisor.group_figures("all", decks, decks_total=7)
    assert group["decks"] == 7 and group["decks_counted"] == 5
    assert group["small"] is True  # fewer than 30 decks
    assert group["colours"]["G"]["land_sources"] == {"median": 12.0, "p25": 11.0, "p75": 13.0}
    big = land_advisor.group_figures("all", decks * 7, decks_total=35)
    assert big["small"] is False


def test_an_empty_group_gives_no_figures_not_zeros() -> None:
    group = land_advisor.group_figures("all", [], decks_total=4)
    assert group["decks_counted"] == 0
    assert group["lands"] is None and group["colours"] == {}


def test_the_route_compares_with_the_source_decks_of_the_commander(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _deck, _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    body = client.post("/api/land-advisor", json={"cards": [c.__dict__ for c in _deck()]})
    assert body.status_code == 200
    payload = body.json()
    assert payload["deck"]["lands"] >= 0
    assert isinstance(payload["groups"], list)
    for group in payload["groups"]:
        assert group["small"] is (group["decks_counted"] < 30)


def test_source_deck_groups_match_a_hand_count(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    groups = {g["cohort"]: g for g in land_advisor.source_deck_groups(store, ["Test Commander"])}
    everyone = groups["all"]
    # d1: 30 Forests and one {1}{G} creature, d2: 36 Forests; d3 holds an unknown card (left out)
    assert (everyone["decks"], everyone["decks_counted"]) == (3, 2)
    assert everyone["lands"] == {"median": 33.0, "p25": 31.5, "p75": 34.5}
    green = everyone["colours"]["G"]
    assert green["land_sources"]["median"] == 33.0
    assert green["pips"] == {"median": 0.5, "p25": 0.25, "p75": 0.75}
    assert green["pip_share"]["median"] == 1.0  # d2 has no coloured symbols: no share, not 0
    assert groups["turnier_cedh"]["lands"] is None
    nobody = land_advisor.source_deck_groups(store, ["Nobody"])
    assert [(g["decks"], g["decks_counted"], g["lands"]) for g in nobody] == [(0, 0, None)]
    assert land_advisor.source_deck_groups(store, []) == []
