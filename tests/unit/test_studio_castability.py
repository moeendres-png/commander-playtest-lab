"""Castability conditioned on land drops (#1415, Karsten method) and opening hands."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import comb

from commander_lab.studio import castability


def _brute(
    groups: list[tuple[frozenset[str], int]], nonland: int, draws: int, turn: int, need: dict
) -> tuple[Fraction, Fraction]:
    """Reference by enumerating every subset of labelled cards."""
    cards: list[frozenset[str] | None] = []
    for produced, size in groups:
        cards += [produced] * size
    cards += [None] * nonland
    total = with_lands = with_both = 0
    for hand in combinations(range(len(cards)), draws):
        drawn = [cards[i] for i in hand]
        lands = [c for c in drawn if c is not None]
        total += 1
        if len(lands) >= turn:
            with_lands += 1
            if all(sum(colour in land for land in lands) >= n for colour, n in need.items()):
                with_both += 1
    return Fraction(with_lands, total), Fraction(with_both, with_lands)


def test_double_pip_is_one_compound_event_conditioned_on_lands() -> None:
    # 14 cards: 4 Forests, 2 Islands, 8 spells; a GG card on turn 2 (7 + 2 = 9 draws).
    groups = [(frozenset("G"), 4), (frozenset("U"), 2)]
    result = castability.colour_probability(groups, 8, {"G": 2}, 2)
    p_lands, p_colour = _brute(groups, 8, 9, 2, {"G": 2})
    assert result["p_land_drops"] == round(float(p_lands), 4)
    assert result["p_colours_given_lands"] == round(float(p_colour), 4)
    assert result["condition"] == "bedingt auf mindestens 2 Länder unter 9 gezogenen Karten"
    # The univariate build (one green source, squared) gives another, wrong value.
    single = castability.colour_probability(groups, 8, {"G": 1}, 2)["p_colours_given_lands"]
    assert isinstance(single, float)
    assert round(single * single, 4) != result["p_colours_given_lands"]


def test_hand_checked_double_pip_value() -> None:
    # 6 cards: 3 Forests, 1 Island, 2 spells; GG on turn 1 would ask for 8 draws: use a
    # direct small case instead: draws = 7 + 1 = 8 > 6 is impossible, so check turn 1 with
    # a 10-card deck by hand: 3 G lands, 2 other lands, 5 spells, GG, turn 1, 8 draws.
    groups = [(frozenset("G"), 3), (frozenset("U"), 2)]
    result = castability.colour_probability(groups, 5, {"G": 2}, 1)
    # Draws missing at most one of the 3 Forests among 8 of 10 cards: the 2 cards left out
    # include at most 1 Forest... P(>=2 Forests drawn) = 1 - P(2 Forests left out)
    # = 1 - C(3,2)/C(10,2) = 1 - 3/45 = 42/45. Every 8-card draw of this deck holds >= 1
    # land, so the condition is certain.
    assert result["p_land_drops"] == 1.0
    assert result["p_colours_given_lands"] == round(42 / 45, 4)


def test_multicolour_joint_event_counts_a_dual_land_once() -> None:
    groups = [(frozenset("GU"), 1), (frozenset("G"), 2), (frozenset("U"), 2), (frozenset(), 2)]
    need = {"G": 1, "U": 1}
    result = castability.colour_probability(groups, 11, need, 2)
    p_lands, p_colour = _brute(groups, 11, 9, 2, need)
    assert result["p_land_drops"] == round(float(p_lands), 4)
    assert result["p_colours_given_lands"] == round(float(p_colour), 4)
    assert result["sources"] == {"G": 3, "U": 3}
    # The product of the per-colour values is not the joint value.
    g = castability.colour_probability(groups, 11, {"G": 1}, 2)["p_colours_given_lands"]
    u = castability.colour_probability(groups, 11, {"U": 1}, 2)["p_colours_given_lands"]
    assert isinstance(g, float) and isinstance(u, float)
    assert round(g * u, 4) != result["p_colours_given_lands"]


def test_opening_hands_exact() -> None:
    result = castability.opening_hands(lands=5, early=3, other=4)
    keep = 0
    cards = ["L"] * 5 + ["E"] * 3 + ["O"] * 4
    hands = list(combinations(range(12), 7))
    for hand in hands:
        drawn = [cards[i] for i in hand]
        if 2 <= drawn.count("L") <= 4 and "E" in drawn:
            keep += 1
    assert result["p_keepable"] == round(keep / comb(12, 7), 4)


def test_requirement_skips_hybrid_and_reads_front_face() -> None:
    assert castability.requirement("{1}{G}{G}") == ({"G": 2}, False)
    assert castability.requirement("{G/U}{U}") == ({"U": 1}, True)
    assert castability.requirement("{2}{G/P}") == ({}, True)
    assert castability.requirement("{1}{U} // {3}{G}") == ({"U": 1}, False)


def _row(name: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "card_id": name,
        "oracle_name": name,
        "zone": "main",
        "quantity": 1,
        "type_line": "Sorcery",
        "mana_cost": "",
        "mana_value": 0,
        "produced_mana": "",
    }
    row.update(extra)
    return row


def test_deck_castability_groups_requirements_and_counts_land_data() -> None:
    rows = [
        _row("Chulane", zone="commander", mana_cost="{2}{G}{W}{U}", mana_value=5),
        _row("Forest", type_line="Basic Land — Forest", produced_mana=None, quantity=8),
        _row("Island", type_line="Basic Land — Island", produced_mana="U", quantity=6),
        _row("Breeding Pool", type_line="Land — Forest Island", produced_mana="GU"),
        _row("Evolving Wilds", type_line="Land", produced_mana=""),
        _row("Mystery Land", type_line="Land", produced_mana=None),
        _row("Llanowar Elves", type_line="Creature", mana_cost="{G}", mana_value=1),
        _row("Elvish Mystic", type_line="Creature", mana_cost="{G}", mana_value=1),
        _row("Cryptic Command", type_line="Instant", mana_cost="{1}{U}{U}{U}", mana_value=4),
        _row("Kitchen Finks", type_line="Creature", mana_cost="{1}{G/W}{G/W}", mana_value=3),
        _row("Unknown Spell", type_line="Sorcery", mana_cost="{G}", mana_value=None),
        _row("Filler", type_line="Artifact", mana_cost="{3}", mana_value=3, quantity=10),
    ]
    result = castability.deck_castability(rows)
    assert result["lands"] == 17
    assert result["land_sources"]["G"] == 9
    assert result["land_sources"]["U"] == 7
    assert result["lands_unknown_colours"] == 1
    assert result["lands_without_coloured_mana"] == 1
    assert result["cards_unknown_mana_value"] == 1
    assert result["hybrid_or_phyrexian_cards"] == ["Kitchen Finks"]
    labels = [(item["label"], item["turn"]) for item in result["requirements"]]
    assert labels == [("G", 1), ("UUU", 4)]
    assert [card["name"] for card in result["requirements"][0]["cards"]] == [
        "Elvish Mystic",
        "Llanowar Elves",
    ]
    for item in result["requirements"]:
        assert item["condition"].startswith("bedingt auf mindestens")
        assert item["p_colours_given_lands"] is not None
    assert result["opening_hand"]["early_actions"] == 2


def test_joint_matches_enumeration_on_random_small_decks() -> None:
    import random

    rng = random.Random(20261116)
    kinds = [frozenset("G"), frozenset("U"), frozenset("GU"), frozenset("GUW"), frozenset()]
    for _ in range(60):
        groups = [(kind, rng.randint(0, 2)) for kind in kinds]
        groups = [(kind, size) for kind, size in groups if size]
        nonland = rng.randint(0, 4)
        turn = rng.randint(1, 3)
        need = {c: rng.randint(1, 2) for c in rng.sample("GUW", rng.randint(1, 2))}
        size = sum(n for _, n in groups) + nonland
        draws = castability.draws_by_turn(turn)
        result = castability.colour_probability(groups, nonland, need, turn)
        if size < draws:
            assert result["p_land_drops"] is None
            continue
        total, with_lands, with_both = castability._joint(groups, nonland, draws, turn, need)
        cards: list[frozenset[str] | None] = [k for k, n in groups for _ in range(n)]
        cards += [None] * nonland
        ref_lands = ref_both = ref_total = 0
        hands = list(combinations(range(len(cards)), draws))
        assert hands
        for hand in hands:
            lands = [cards[i] for i in hand if cards[i] is not None]
            ref_total += 1
            if len(lands) >= turn:
                ref_lands += 1
                if all(sum(c in land for land in lands) >= n for c, n in need.items()):
                    ref_both += 1
        assert (total, with_lands, with_both) == (ref_total, ref_lands, ref_both)


def test_role_in_hand_matches_hand_calculation_and_edges() -> None:
    # 99 cards, 10 role cards: P(>= 1 in 7) = 1 - C(89,7) / C(99,7).
    seven = castability.role_in_hand(99, 10, 7)
    assert seven["p_at_least_1"] == round(1 - comb(89, 7) / comb(99, 7), 4)
    assert seven["p_none"] == round(comb(89, 7) / comb(99, 7), 4)
    # After 3 further cards the hand is 10 cards.
    ten = castability.role_in_hand(99, 10, 10)
    assert ten["p_at_least_1"] == round(1 - comb(89, 10) / comb(99, 10), 4)
    # One role card among 10 cards, 7 drawn: 7/10 exactly.
    assert castability.role_in_hand(10, 1, 7)["p_at_least_1"] == 0.7
    assert castability.role_in_hand(99, 0, 7) == {"draws": 7, "p_at_least_1": 0.0, "p_none": 1.0}
    assert castability.role_in_hand(99, 99, 7) == {"draws": 7, "p_at_least_1": 1.0, "p_none": 0.0}
    assert castability.role_in_hand(5, 1, 7)["p_at_least_1"] is None


def test_hand_roles_counts_double_roles_apart_and_names_unknown_cards() -> None:
    rows = [_row("Commander", zone="commander")]
    rows += [_row(f"Card {i}", card_id=f"c{i}") for i in range(97)]
    rows.append(_row("Forest", card_id="forest", type_line="Basic Land - Forest"))
    rows.append(_row("Forest 2", card_id="forest2", type_line="Basic Land - Forest"))
    roles = {f"c{i}": ["ramp"] for i in range(6)}
    roles.update({f"c{i}": ["ramp", "card_draw"] for i in range(6, 8)})
    roles.update({f"c{i}": ["removal"] for i in range(8, 12)})
    result = castability.hand_roles(rows, roles)
    assert result["library"] == 99
    assert result["cards_with_role_data"] == 12
    assert result["nonland_cards"] == 97
    assert result["nonland_with_role_data"] == 12
    assert result["roles_known"] is True
    items = {str(item["role"]): item for item in result["roles"]}  # type: ignore[attr-defined]
    assert sorted(items) == ["card_draw", "ramp", "removal"], "roles in the deck only"
    # The two double-role cards count for ramp AND card_draw; ramp is never 8 + 2 + 4.
    assert (items["ramp"]["cards"], items["card_draw"]["cards"], items["removal"]["cards"]) == (
        8,
        2,
        4,
    )
    hands = items["ramp"]["hands"]
    assert [hand["draws"] for hand in hands] == [7, 8, 9, 10]
    assert hands[0]["p_at_least_1"] == round(1 - comb(91, 7) / comb(99, 7), 4)
    assert hands[3]["p_none"] == round(comb(91, 10) / comb(99, 10), 4)
    assert "Untergrenzen" in str(result["assumption"])
    # Edge: every library card carries the role.
    full = castability.hand_roles([_row("A", card_id="a", quantity=99)], {"a": ["ramp"]})
    full_hands = full["roles"][0]["hands"]  # type: ignore[index]
    assert full_hands, "the role has hands"
    for hand in full_hands:
        assert hand["p_at_least_1"] == 1.0 and hand["p_none"] == 0.0


def test_hand_roles_without_role_data_is_unknown_not_zero() -> None:
    rows = [_row(f"Card {i}", card_id=f"c{i}") for i in range(99)]
    result = castability.hand_roles(rows, {})
    assert result["roles_known"] is False
    assert result["roles"] == []
    assert result["cards_with_role_data"] == 0
    assert result["library"] == 99


def test_hand_roles_names_modal_lands_without_changing_any_figure() -> None:
    plain = [_row(f"Card {i}", card_id=f"c{i}") for i in range(98)]
    face = _row("Valakut Awakening", card_id="m", type_line="Instant // Land")
    land = _row("Forest", card_id="f", type_line="Basic Land — Forest")
    roles = {"m": ["ramp"], "c0": ["ramp"]}
    with_modal = castability.hand_roles([*plain, face], roles)
    baseline = castability.hand_roles([*plain, _row("Valakut Awakening", card_id="m")], roles)
    assert with_modal["modal_land_cards"] == 1  # 1 of 99 nonland cards, counted as nonland
    assert with_modal["nonland_cards"] == 99
    assert baseline["modal_land_cards"] == 0
    assert with_modal["roles"] == baseline["roles"]  # the probabilities are the same
    assert castability.hand_roles([*plain, land], roles)["modal_land_cards"] == 0
    assert "Modal-Land" in str(with_modal["assumption"])


def test_castability_route_on_a_store(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from commander_lab.studio import StudioStore
    from commander_lab.studio.web import create_app
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [{"card_id": "card:project:0001", "quantity": 1, "zone": "commander"}]
    cards += [
        {"card_id": f"card:project:{100 + i:04d}", "quantity": 1, "zone": "main"} for i in range(70)
    ]
    cards.append({"card_id": "card:project:0002", "quantity": 29, "zone": "main"})
    response = client.post("/api/castability", json={"cards": cards})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == castability.SCHEMA
    assert body["main_cards"] == 99
    assert body["requirements"], "the fixture deck has coloured costs"
    hand = body["hand_roles"]
    assert hand["library"] == 99 and hand["hand"] == 7
    assert 0 <= hand["cards_with_role_data"] <= 99
    for role in hand["roles"]:
        assert role["of"] == 99 and 1 <= role["cards"] <= 99
        for entry in role["hands"]:
            assert abs(entry["p_at_least_1"] + entry["p_none"] - 1.0) <= 1e-4
    assert (
        client.post("/api/castability", json={"cards": cards}, headers={"X-Studio": ""}).status_code
        == 403
    )
    for item in body["requirements"]:
        assert "condition" in item and item["condition"].startswith("bedingt auf")


def test_draw_sample_hand_deterministic_mulligan_and_route(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from commander_lab.studio import StudioStore
    from commander_lab.studio.web import create_app
    from tests.unit.test_studio_builder import _fill

    rows = [
        _row("Chulane", zone="commander", mana_cost="{2}{G}{W}{U}", mana_value=5),
        _row("Forest", card_id="land_g", type_line="Basic Land — Forest", quantity=5),
        _row(
            "Llanowar Elves",
            card_id="elf_1",
            type_line="Creature",
            mana_cost="{G}",
            mana_value=1,
            quantity=5,
        ),
        _row(
            "Counterspell",
            card_id="cs_1",
            type_line="Instant",
            mana_cost="{U}{U}",
            mana_value=2,
            quantity=5,
        ),
    ]
    h1 = castability.draw_sample_hand(rows, seed=42, mulligans=0, draw_steps=2)
    h1_reversed = castability.draw_sample_hand(
        list(reversed(rows)), seed=42, mulligans=0, draw_steps=2
    )
    assert h1 == h1_reversed
    assert h1["schema"] == castability.SAMPLE_HAND_SCHEMA
    assert h1["data_class"] == "HEURISTIC_MODEL"
    assert h1["library_size"] == 15
    assert h1["bottom_required"] == 0
    assert len(h1["hand"]) == 7  # type: ignore[arg-type]
    assert len(h1["extra_draws"]) == 2  # type: ignore[arg-type]

    # Commander 1st mulligan is free (bottom_required == 0); 2nd mulligan requires 1 bottomed card
    m1 = castability.draw_sample_hand(rows, seed=42, mulligans=1)
    assert m1["bottom_required"] == 0
    m2 = castability.draw_sample_hand(rows, seed=42, mulligans=2, bottom_indices=[0, 2])
    assert m2["bottom_required"] == 1
    assert m2["bottom_indices"] == [0, 2]
    assert len(m2["kept_hand"]) == 5  # type: ignore[arg-type]

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [
        {"card_id": "card:project:0001", "quantity": 1, "zone": "commander"},
        {"card_id": "card:project:0002", "quantity": 10, "zone": "main"},
        {"card_id": "card:project:0100", "quantity": 5, "zone": "main"},
    ]
    res = client.post(
        "/api/sample-hand",
        json={"cards": cards, "seed": 7, "mulligans": 2, "draw_steps": 1, "bottom_indices": [1]},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["seed"] == 7
    assert payload["mulligans"] == 2
    assert payload["bottom_required"] == 1
    assert payload["summary"]["kept_cards"] == 6
    assert len(payload["extra_draws"]) == 1
