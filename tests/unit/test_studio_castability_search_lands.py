"""Search lands as sources, the commander on curve and the land count table (#1404, builder
audit WP-2 and WP-3).

All decks here are synthetic: land groups and costs only, with made-up names, so that no test
can pass by reading a card name. The Chulane-shaped deck copies the land groups and the 26
coloured requirements of the Chulane baseline as counts. Its expected values: UU on turn 3
65.2 -> 76.4 % (as in the builder audit); with one land per coloured symbol (review round 1 of
#1751) the mean gain over the 26 requirements is +5.6 pp (the audit's +5.5 pp counted a dual land
for both colours at once) and Chulane 2GWU on turn 5 is 45.6 % x 92.0 % = 42.0 % (audit: 92.8 %,
42.4 %). The multicoloured references enumerate every draw and assign lands to symbols by
backtracking, independent of the Hall condition the code uses.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path

import pytest

from commander_lab.studio import castability, land_advisor, number_contract

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"

BASIC_SEARCH = (
    "{T}, Sacrifice this land: Search your library for a basic land card, put it onto the "
    "battlefield tapped, then shuffle."
)
FETCH_PLAINS_ISLAND = (
    "{T}, Pay 1 life, Sacrifice this land: Search your library for a Plains or Island card, "
    "put it onto the battlefield, then shuffle."
)


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
        "oracle_text": "",
    }
    row.update(extra)
    return row


def _land(
    name: str, produced: str | None, type_line: str = "Land", text: str | None = "", qty: int = 1
) -> dict[str, object]:
    return _row(name, type_line=type_line, produced_mana=produced, oracle_text=text, quantity=qty)


def _spell(name: str, cost: str, mv: int, qty: int = 1) -> dict[str, object]:
    return _row(name, type_line="Instant", mana_cost=cost, mana_value=mv, quantity=qty)


# --- classification from card data and rules text ------------------------------------------


def test_classify_land_reads_rules_text_and_card_data_never_the_name() -> None:
    cases = [
        # (row, class, search alternatives or reason)
        (
            _land("Evolving Wilds", "", text="{T}: Add {C}. {T}: Untap target creature."),
            "ohne_farbe",
        ),
        (_land("Plain Utility", "C", text="{T}: Add {C}."), "ohne_farbe"),
        (_land("Odd Name 1", "", text=BASIC_SEARCH), "suchland"),
        (_land("Odd Name 2", None, text=FETCH_PLAINS_ISLAND), "suchland"),
        (_land("Odd Name 3", "G", "Land — Forest", text=FETCH_PLAINS_ISLAND), "direkt"),
        (_land("No Text", "", text=None), "unbekannt"),
        (_land("No Data", None, text="{T}: Add {C}."), "unbekannt"),
    ]
    assert len(cases) == 7
    for row, expected in cases:
        assert castability.classify_land(row)["class"] == expected, row["oracle_name"]


@pytest.mark.parametrize(
    ("text", "produced", "expected"),
    [
        (BASIC_SEARCH, "", ((True, None),)),
        (FETCH_PLAINS_ISLAND, "", ((False, frozenset({"Plains", "Island"})),)),
        (
            "{T}: Add {C}.\n{1}, {T}, Sacrifice this land: Search your library for a basic "
            "Forest, Plains, or Island card, put it onto the battlefield tapped, then shuffle.",
            "C",
            ((True, frozenset({"Forest", "Plains", "Island"})),),
        ),
        (
            "When this land enters, sacrifice it. When you do, search your library for a basic "
            "Mountain, Forest, or Plains card, put it onto the battlefield tapped, then shuffle "
            "and you gain 1 life.",
            "",
            ((True, frozenset({"Mountain", "Forest", "Plains"})),),
        ),
        (
            "{2}, {T}, Sacrifice this land: Search your library for a Forest card and a Plains "
            "card, put them onto the battlefield tapped, then shuffle.",
            "C",
            ((False, frozenset({"Forest"})), (False, frozenset({"Plains"}))),
        ),
        (
            "{2}, {T}, Sacrifice this land: Search your library for up to two basic land cards "
            "that share a land type, put them onto the battlefield tapped, then shuffle.",
            "C",
            ((True, None),),
        ),
        (
            "{T}, Sacrifice this land: Search your library for a land card with a basic land "
            "type, put it onto the battlefield, then shuffle.",
            "",
            ((False, frozenset({"Plains", "Island", "Swamp", "Mountain", "Forest"})),),
        ),
        (
            "{1}, {T}: Search your library for a basic land card, put that card onto the "
            "battlefield tapped, then shuffle.",
            "",
            ((True, None),),
        ),
    ],
)
def test_search_forms_are_read_as_their_searched_cards(
    text: str, produced: str, expected: tuple[castability.SearchAlternative, ...]
) -> None:
    result = castability.classify_land(_land("Some Land", produced, text=text))
    assert result["class"] == castability.LAND_SEARCH
    assert result["search"] == expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        # a Gate is no basic land type: the searchability is not derivable -> unknown
        (
            "{T}: Add {C}.\n{3}, {T}, Return this land to its owner's hand: Search your library "
            "for a Gate card, put it onto the battlefield, then shuffle.",
            castability.REASON_UNREADABLE_SEARCH,
        ),
        # into the hand, not onto the battlefield
        (
            "{T}: Search your library for a basic land card, reveal it, put it into your hand, "
            "then shuffle.",
            castability.REASON_UNREADABLE_SEARCH,
        ),
        # any land card: not a basic land and not a basic land type
        (
            "{3}, {T}, Sacrifice this land: Search your library for a land card, put it onto "
            "the battlefield tapped, then shuffle.",
            castability.REASON_UNREADABLE_SEARCH,
        ),
        # the search hangs on a target
        (
            "{T}: Add {C}.\n{2}, {T}, Sacrifice this land: Destroy target nonbasic land an "
            "opponent controls. You may search your library for a basic land card, put it onto "
            "the battlefield, then shuffle.",
            castability.REASON_TARGETED_SEARCH,
        ),
    ],
)
def test_search_text_that_is_no_basic_land_search_is_unknown(text: str, reason: str) -> None:
    result = castability.classify_land(_land("Some Land", "C", text=text))
    assert result["class"] == castability.LAND_UNKNOWN
    assert result["reason"] == reason


def test_their_library_is_unknown_and_reminder_text_is_no_search() -> None:
    their = _land(
        "Odd",
        "C",
        text="{T}: Add {C}.\n{2}, {T}, Sacrifice this land: That land's controller may "
        "search their library for a basic land card, put it onto the battlefield.",
    )
    each_player = _land(  # Field of Ruin: "each player" includes you, and it needs a target
        "Odd 3",
        "C",
        text="{T}: Add {C}.\n{2}, {T}, Sacrifice this land: Destroy target nonbasic land an "
        "opponent controls. Each player searches their library for a basic land card, puts it "
        "onto the battlefield, then shuffles.",
    )
    cycling = _land(
        "Odd 2",
        "C",
        text="{T}: Add {C}.\nBasic landcycling {1} ({1}, Discard this card: Search your library "
        "for a basic land card, reveal it, put it into your hand, then shuffle.)",
    )
    for row in (their, each_player):
        result = castability.classify_land(row)
        assert result["class"] == castability.LAND_UNKNOWN, row["oracle_name"]
        assert result["reason"] == castability.REASON_UNREADABLE_SEARCH
    assert castability.classify_land(cycling)["class"] == castability.LAND_NO_COLOUR


# --- reach over land types -------------------------------------------------------------


def test_reach_follows_land_types_not_names() -> None:
    rows = [
        _land("Fetch A", "", text=FETCH_PLAINS_ISLAND),
        _land("Forest Plains Dual", "GW", "Land — Forest Plains"),
        _land("Isle", "U", "Basic Land — Island", qty=3),
        _land("Woods", "G", "Basic Land — Forest", qty=3),
        _land("Plains Named Land", "R", "Land"),  # a name with "Plains", no Plains type
        _land("Basic Seeker", "", text=BASIC_SEARCH),
        _land("Other Seeker", "", text=BASIC_SEARCH, qty=2),
    ]
    entries = {str(e["name"]): e for e in castability.search_land_reach(rows)}
    fetch = entries["Fetch A"]
    # Plains or Island: the dual (Forest Plains) brings G and W, the Islands U; Forests do not
    # match, the land with "Plains" in its name does not either.
    assert fetch["reach"] == frozenset("GWU")
    assert fetch["targets"] == 4
    seeker = entries["Basic Seeker"]
    assert seeker["reach"] == frozenset("UG") and seeker["targets"] == 6


def test_search_land_without_target_is_a_known_zero_not_unknown() -> None:
    rows = [
        _row("Cmdr", zone="commander", mana_cost="{1}{U}", mana_value=2),
        _land("Seeker", "", text=BASIC_SEARCH),
        _land("Dual", "WU", "Land — Plains Island", qty=10),
        _spell("Spell", "{U}", 1, qty=20),
    ]
    result = castability.deck_castability(rows)
    classes = result["land_classes"]
    assert classes["counts"] == {"direkt": 10, "suchland": 1, "ohne_farbe": 0, "unbekannt": 0}
    assert classes["search_lands"] == [
        {
            "card_id": "Seeker",
            "name": "Seeker",
            "quantity": 1,
            "searches_for": "Standardland",
            "reach": [],
            "targets": 0,
        }
    ]
    assert result["land_sources_with_search"] == result["land_sources"]
    seeker = next(e for e in castability.search_land_reach(rows) if e["name"] == "Seeker")
    assert seeker["reach"] == frozenset() and seeker["targets"] == 0  # known, not None
    assert land_advisor.deck_profile(rows)["lands_search"] == 1


def test_unknown_land_is_neither_source_nor_zero_and_stays_in_the_denominator() -> None:
    gate = (
        "{3}, {T}, Return this land to its owner's hand: Search your library for a Gate card, "
        "put it onto the battlefield, then shuffle."
    )
    rows = [
        _land("Maze", "C", text=gate),
        _land("Seeker", "", text=BASIC_SEARCH),
        _land("Isle", "U", "Basic Land — Island", qty=9),
        _spell("Spell", "{U}{U}", 2, qty=20),
    ]
    result = castability.deck_castability(rows)
    classes = result["land_classes"]
    assert classes["of"] == 11 and classes["classified"] == 10
    assert classes["counts"]["unbekannt"] == 1
    assert classes["unknown"] == [
        {"card_id": "Maze", "name": "Maze", "reason": castability.REASON_UNREADABLE_SEARCH}
    ]
    item = result["requirements"][0]
    assert item["sources"] == {"U": 9}
    assert item["with_search"]["sources"] == {"U": 10}  # the seeker, never the maze
    assert result["lands"] == 11  # the unknown land is still a land of the draws


# --- the Chulane-shaped synthetic deck against the audit's hand calculation ---------------

# (label, turn) of the 26 coloured requirements of the Chulane baseline, as counts only.
CHULANE_REQUIREMENTS = (
    ("G", 1), ("U", 1), ("W", 1), ("G", 2), ("GU", 2), ("U", 2), ("W", 2), ("G", 3),
    ("GW", 3), ("U", 3), ("UU", 3), ("W", 3), ("G", 4), ("GU", 4), ("U", 4), ("UU", 4),
    ("W", 4), ("GU", 5), ("UW", 5), ("UU", 5), ("WW", 5), ("GG", 6), ("UU", 6), ("WW", 6),
    ("GGUU", 7), ("UU", 7),
)  # fmt: skip


def _chulane_shaped() -> list[dict[str, object]]:
    rows = [_row("Commander GWU", zone="commander", mana_cost="{2}{G}{W}{U}", mana_value=5)]
    rows += [
        _land("Bounce WU", "WU"),
        _land("Typed WU", "WU", "Land — Plains Island"),
        _land("Scry WU", "WU"),
        _land("Typed WG", "WG", "Land — Forest Plains"),
        _land("Bounce WG", "WG"),
        _land("Filter WG", "WG"),
        _land("Scry WG", "WG"),
        _land("Bounce UG", "UG"),
        _land("Scry UG", "UG"),
        _land("Tri WUG", "WUG"),
        _land("Any 1", "WUBRG"),
        _land("Any 2", "WUBRG"),
        _land("Any 3", "WUBRG"),
        _land("Woods", "G", "Basic Land — Forest", qty=8),
        _land("Isle", "U", "Basic Land — Island", qty=8),
        _land("Field", "W", "Basic Land — Plains", qty=4),
        _land("Seeker 1", "", text=BASIC_SEARCH),
        _land("Seeker 2", "", text=BASIC_SEARCH),
        _land("Seeker 3", "", text=BASIC_SEARCH),
    ]
    for index, (label, turn) in enumerate(CHULANE_REQUIREMENTS):
        cost = "{" + str(max(0, turn - len(label))) + "}" + "".join("{" + c + "}" for c in label)
        rows.append(_spell(f"Spell {index}", cost, turn))
    rows.append(_row("Filler", type_line="Artifact", mana_cost="{3}", mana_value=3, quantity=37))
    return rows


def test_chulane_shaped_deck_equals_the_audit_hand_calculation() -> None:
    rows = _chulane_shaped()
    result = castability.deck_castability(rows)
    assert result["lands"] == 36 and result["main_cards"] == 99
    assert result["land_classes"]["counts"]["suchland"] == 3
    assert result["land_classes"]["classified"] == 36 == result["land_classes"]["of"]
    assert result["land_sources"] == {"W": 15, "U": 17, "B": 3, "R": 3, "G": 18}
    assert result["land_sources_with_search"] == {"W": 18, "U": 20, "B": 3, "R": 3, "G": 21}
    items = result["requirements"]
    assert [(i["label"], i["turn"]) for i in items] == list(CHULANE_REQUIREMENTS)
    uu3 = next(i for i in items if (i["label"], i["turn"]) == ("UU", 3))
    assert uu3["p_colours_given_lands"] == 0.6523
    assert uu3["with_search"]["p_colours_given_lands"] == 0.7637
    assert uu3["with_search"]["sources"] == {"U": 20}
    # the mean over the 26 requirements, exact from the counts (no rounded inputs)
    direct_groups = [(frozenset(k), n) for k, n in _groups(search=False).items()]
    search_groups = [(frozenset(k), n) for k, n in _groups(search=True).items()]
    deltas = []
    for label, turn in CHULANE_REQUIREMENTS:
        need = {c: label.count(c) for c in set(label)}
        _, lands_a, both_a = castability._joint(direct_groups, 63, 7 + turn, turn, need)
        _, lands_b, both_b = castability._joint(search_groups, 63, 7 + turn, turn, need)
        assert lands_a == lands_b  # the land drops do not change
        deltas.append(Fraction(both_b - both_a, lands_a))
    mean = sum(deltas, Fraction(0)) / len(deltas)
    assert len(deltas) == 26
    assert round(float(mean) * 100, 3) == 5.571  # 5.476 when a dual paid two symbols
    assert round(float(min(deltas)) * 100, 1) == 1.8
    assert round(float(max(deltas)) * 100, 1) == 11.1


def _groups(*, search: bool) -> dict[str, int]:
    """The land groups of the Chulane-shaped deck, written out by hand."""
    groups = {"WU": 3, "WG": 4, "UG": 2, "WUG": 1, "WUBRG": 3, "G": 8, "U": 8, "W": 4}
    if search:
        groups["WUG"] += 3
    else:
        groups[""] = 3
    return groups


def test_commander_on_curve_from_the_command_zone() -> None:
    result = castability.deck_castability(_chulane_shaped())
    (commander,) = result["commander"]
    assert commander["known"] is True
    assert (commander["turn"], commander["draws"], commander["label"]) == (5, 12, "GUW")
    assert commander["p_land_drops"] == 0.4564
    assert commander["p_colours_given_lands"] == 0.9202  # 0.9283 before review round 1
    assert commander["p_on_curve"] == 0.4200
    assert commander["with_search"]["p_colours_given_lands"] == 0.9711
    assert commander["with_search"]["p_on_curve"] == 0.4432
    # the commander is no card of the library: 99 cards, 36 lands
    assert commander["sources"] == {"G": 18, "U": 17, "W": 15}
    # the same value as the shared function on the same groups (no new heuristic)
    groups = [(frozenset(k), n) for k, n in _groups(search=False).items()]
    same = castability.colour_probability(groups, 63, {"G": 1, "W": 1, "U": 1}, 5)
    for key in ("p_land_drops", "p_colours_given_lands", "p_on_curve"):
        assert commander[key] == same[key], key


def _assignable(lands: list[frozenset[str]], need: dict[str, int]) -> bool:
    """One distinct land per coloured symbol, by backtracking (not by the Hall condition)."""
    symbols = [colour for colour, n in sorted(need.items()) for _ in range(n)]

    def place(index: int, used: frozenset[int]) -> bool:
        if index == len(symbols):
            return True
        return any(
            place(index + 1, used | {i})
            for i, land in enumerate(lands)
            if i not in used and symbols[index] in land
        )

    return place(0, frozenset())


def _enumerate(
    deck: list[frozenset[str] | None], need: dict[str, int], turn: int, *, per_colour: bool = False
) -> tuple[float, float, float]:
    """Exact (land drops, colours given land drops, on curve) over every draw of 7 + turn
    cards; ``per_colour`` is the old rule (enough sources of each colour, a dual for both)."""
    total = lands_ok = both = 0
    for hand in combinations(range(len(deck)), 7 + turn):
        lands = [land for land in (deck[i] for i in hand) if land is not None]
        total += 1
        if len(lands) >= turn:
            lands_ok += 1
            if per_colour:
                ok = all(sum(c in land for land in lands) >= n for c, n in need.items())
            else:
                ok = _assignable(lands, need)
            both += ok
    return (
        round(lands_ok / total, 4),
        round(both / lands_ok, 4) if lands_ok else -1.0,
        round(both / total, 4),
    )


FOREST_OR_ISLAND = (
    "{T}, Sacrifice this land: Search your library for a Forest or Island card, put it onto the "
    "battlefield, then shuffle."
)
NONE = frozenset[str]()

# (name, commander cost, mana value, land rows, the drawn-land model of those rows written by
# hand as (direct, with search), whether the old per-colour rule gives another value)
ENUMERATION_CASES = [
    (
        "GW dual with colourless lands",
        "{G}{W}",
        2,
        [_land("Dual GW", "GW"), _land("Waste", "C", text="{T}: Add {C}.", qty=5)],
        ([frozenset("GW")] + [NONE] * 5, [frozenset("GW")] + [NONE] * 5),
        True,
    ),
    (
        "TAM 1GU with two duals",
        "{1}{G}{U}",
        3,
        [_land("Dual GU", "GU", qty=2), _land("Waste", "C", text="{T}: Add {C}.", qty=3)],
        ([frozenset("GU")] * 2 + [NONE] * 3, [frozenset("GU")] * 2 + [NONE] * 3),
        True,
    ),
    (
        "search land and typed dual, 1GU",
        "{1}{G}{U}",
        3,
        [
            _land("Fetch FI", "", text=FOREST_OR_ISLAND),
            _land("Typed GU", "GU", "Land — Forest Island"),
            _land("Woods", "G", "Basic Land — Forest"),
            _land("Waste", "C", text="{T}: Add {C}.", qty=2),
        ],
        (
            [NONE, frozenset("GU"), frozenset("G"), NONE, NONE],
            [frozenset("GU"), frozenset("GU"), frozenset("G"), NONE, NONE],
        ),
        True,
    ),
    (
        "three-colour commander GWU",
        "{G}{W}{U}",
        3,
        [
            _land("Tri", "WUG"),
            _land("Dual GW", "GW"),
            _land("Isle", "U", "Basic Land — Island"),
            _land("Seeker", "", text=BASIC_SEARCH),
            _land("Waste", "C", text="{T}: Add {C}."),
        ],
        (
            [frozenset("WUG"), frozenset("GW"), frozenset("U"), NONE, NONE],
            [frozenset("WUG"), frozenset("GW"), frozenset("U"), frozenset("U"), NONE],
        ),
        True,
    ),
]


@pytest.mark.parametrize(
    ("name", "cost", "mv", "lands", "model", "differs"),
    ENUMERATION_CASES,
    ids=[case[0] for case in ENUMERATION_CASES],
)
def test_commander_on_curve_by_full_enumeration_with_land_to_symbol_assignment(
    name: str,
    cost: str,
    mv: int,
    lands: list[dict[str, object]],
    model: tuple[list[frozenset[str]], list[frozenset[str]]],
    differs: bool,
) -> None:
    spells = 12 - sum(int(str(row["quantity"])) for row in lands)
    rows = [
        _row("Cmdr", zone="commander", mana_cost=cost, mana_value=mv),
        *lands,
        _spell("Spell", "{2}", 2, qty=spells),
    ]
    (commander,) = castability.deck_castability(rows)["commander"]
    need, _ = castability.requirement(cost)
    old_rule = []
    for drawn, key in zip(model, (None, "with_search"), strict=True):
        deck: list[frozenset[str] | None] = [*drawn, *([None] * spells)]
        shown = commander if key is None else {**commander, **commander[key]}
        expected = _enumerate(deck, need, mv)
        assert (
            shown["p_land_drops"],
            shown["p_colours_given_lands"],
            shown["p_on_curve"],
        ) == expected, (name, key)
        old_rule.append(_enumerate(deck, need, mv, per_colour=True) != expected)
    assert any(old_rule) is differs, name  # the case tells the two models apart


def test_dual_land_pays_one_symbol_never_two() -> None:
    # the reviewer's counter-example: one GW dual and 40 colourless lands, {G}{W} by turn 2
    groups = [(frozenset("GW"), 1), (frozenset(), 40)]
    result = castability.colour_probability(groups, 59, {"G": 1, "W": 1}, 2)
    assert result["p_colours_given_lands"] == 0.0 and result["p_on_curve"] == 0.0
    assert result["p_land_drops"] == round(1 - (comb(59, 9) + 41 * comb(59, 8)) / comb(100, 9), 4)


def test_commander_without_mana_value_is_unknown() -> None:
    rows = [
        _row("Cmdr", zone="commander", mana_cost="{G}", mana_value=None),
        _land("Woods", "G", "Basic Land — Forest", qty=10),
        _spell("Spell", "{G}", 1, qty=10),
    ]
    assert castability.deck_castability(rows)["commander"] == [
        {
            "card_id": "Cmdr",
            "name": "Cmdr",
            "mana_cost": "{G}",
            "known": False,
            "reason": "Manawert unbekannt",
        }
    ]


def test_deck_without_search_lands_has_equal_direct_and_search_values() -> None:
    rows = [
        _land("Woods", "G", "Basic Land — Forest", qty=12),
        _land("Isle", "U", "Basic Land — Island", qty=10),
        _spell("A", "{G}{U}", 2, qty=10),
        _spell("B", "{U}{U}", 3, qty=10),
    ]
    result = castability.deck_castability(rows)
    assert result["requirements"], "the deck has coloured requirements"
    for item in result["requirements"]:
        assert item["with_search"] == {
            "sources": item["sources"],
            "p_colours_given_lands": item["p_colours_given_lands"],
            "p_on_curve": item["p_on_curve"],
        }


# --- the land count table ----------------------------------------------------------------


def test_at_least_lands_matches_hand_calculation() -> None:
    # 10 cards, 4 lands, 3 drawn, at least 2 lands: (C(4,2) C(6,1) + C(4,3)) / C(10,3) = 40/120
    assert castability.at_least_lands(10, 4, 3, 2) == Fraction(1, 3)
    # 99 cards, 36 lands, turn 3 = 10 cards, at least 3 lands
    expected = 1 - Fraction(sum(comb(36, k) * comb(63, 10 - k) for k in range(3)), comb(99, 10))
    assert castability.at_least_lands(99, 36, 10, 3) == expected
    assert round(float(expected), 4) == 0.7805
    assert castability.at_least_lands(5, 2, 6, 1) is None  # more draws than cards: unknown
    assert castability.at_least_lands(10, 0, 3, 1) == 0  # no land: a real 0
    assert castability.at_least_lands(10, 10, 3, 3) == 1


def test_land_count_table_rows_30_to_40_and_the_deck_row() -> None:
    result = castability.deck_castability(_chulane_shaped())
    table = result["land_count_table"]
    assert table["library"] == 99 and table["deck_lands"] == 36
    assert table["turns"] == [2, 3, 4, 5, 6, 7]
    assert [row["lands"] for row in table["rows"]] == list(range(30, 41))
    deck_row = next(row for row in table["rows"] if row["deck"])
    assert deck_row["lands"] == 36
    # the deck's own row equals the land drops of the requirements of the same turn
    by_turn = {item["turn"]: item["p_land_drops"] for item in result["requirements"]}
    for cell in deck_row["cells"]:
        assert cell["draws"] == 7 + cell["turn"]
        assert cell["p"] == by_turn[cell["turn"]], cell
    for row in table["rows"]:
        exact = [castability.at_least_lands(99, row["lands"], 7 + t, t) for t in table["turns"]]
        assert [cell["p"] for cell in row["cells"]] == [round(float(p), 4) for p in exact]
    # more lands never lower the chance
    for turn_index in range(6):
        column = [row["cells"][turn_index]["p"] for row in table["rows"]]
        assert column == sorted(column)


def test_land_count_table_adds_a_deck_count_outside_30_to_40() -> None:
    table = castability.land_count_table(99, 28)
    assert [row["lands"] for row in table["rows"]] == [28, *range(30, 41)]
    first = table["rows"][0]
    assert first["deck"] is True and first["in_range"] is False


# --- land advisor and number contract ----------------------------------------------------


def test_land_advisor_counts_search_sources_apart_within_the_identity() -> None:
    rows = [
        _row("Cmdr", zone="commander", color_identity="WU", mana_cost="{W}{U}", mana_value=2),
        _land("Fetch A", "", text=FETCH_PLAINS_ISLAND),
        _land("Typed GW", "GW", "Land — Forest Plains"),
        _land("Isle", "U", "Basic Land — Island", qty=4),
        _land("Maze", "C", text="{3}, {T}: Search your library for a Gate card, put it onto "
              "the battlefield, then shuffle."),
        _spell("Spell", "{W}{U}", 2, qty=5),
        _spell("Off Colour", "{G}", 1),  # a green pip outside the identity shows the G row
    ]  # fmt: skip
    deck = land_advisor.deck_profile(rows)
    colours = {entry["colour"]: entry for entry in deck["colours"]}
    assert set(colours) == {"W", "U", "G"} and colours["G"]["in_identity"] is False
    assert {c: colours[c]["land_sources"] for c in colours} == {"W": 1, "U": 4, "G": 0}
    # the fetch reaches G through the Forest Plains dual, but G is outside the identity
    assert {c: colours[c]["search_sources"] for c in colours} == {"W": 1, "U": 1, "G": 0}
    assert deck["lands_search"] == 1 and deck["lands_search_unknown"] == 1


def test_land_without_rules_text_is_no_unreadable_search() -> None:
    # unknown for lack of text (and of colour data), but no search text: not "Suchtext unklar"
    rows = [
        _row("Cmdr", zone="commander", color_identity="U", mana_cost="{U}", mana_value=1),
        _land("Blank", "", text=None),
        _land("No Data", None, text=None),
        _land("Isle", "U", "Basic Land — Island", qty=4),
    ]
    deck = land_advisor.deck_profile(rows)
    assert deck["lands_search_unknown"] == 0 and deck["lands_search"] == 0
    classes = castability.deck_castability(rows)["land_classes"]
    assert classes["counts"]["unbekannt"] == 2 and classes["classified"] == 4
    assert deck["search_assumption"] == castability.LAND_SEARCH_ASSUMPTION


def test_contracts_carry_the_assumption_for_every_search_figure() -> None:
    result = castability.deck_castability(_chulane_shaped())
    zahlen = number_contract.castability_zahlen(result)
    search = [z for z in zahlen if "with_search" in str(z["id"])]
    assert len(search) == 26 + 2
    for item in search:
        assert item["klasse"] == "EXAKT"
        assert item["hinweise"] == [castability.LAND_SEARCH_ASSUMPTION]
    curve = {z["id"]: z["wert"] for z in zahlen if str(z["id"]).startswith("cast.commander.")}
    assert curve["cast.commander.Commander GWU.p_on_curve"] == 0.42
    assert curve["cast.commander.Commander GWU.p_on_curve_with_search"] == 0.4432


def test_assumption_names_what_is_left_out() -> None:
    text = castability.LAND_SEARCH_ASSUMPTION
    assert text.startswith("Rechenannahme, kein Regelurteil")
    for word in ("getappter Eintritt", "Lebenspunkte", "Aktivierungskosten", "nie nach Namen"):
        assert word in text, word


# --- the display under node --------------------------------------------------------------


def _ui_prelude() -> str:
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
    part = ui[ui.index("function _formatDe(n, opts) {") : ui.index("// Simulator readiness codes")]
    return "globalThis.StudioUI = (() => {" + part + "return {num, pct, numFlex, numSig}; })();\n"


JS_RENDER = r"""
const vm = require("node:vm");
const fs = require("node:fs");
__PRELUDE__
globalThis.StudioZahl = require(__ZAHL__);
vm.runInThisContext(fs.readFileSync(__CAST__, "utf8"));
const h = (tag, props, ...kids) => ({ tag, props: props || {}, kids: kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== "") });
const text = (node) => (typeof node === "string" || typeof node === "number" ? String(node) : node.kids.map(text).join(""));
const byId = (node, id) => { if (!node || typeof node !== "object") return null; if (node.props.id === id) return node; for (const kid of node.kids) { const f = byId(kid, id); if (f) return f; } return null; };
const data = __DATA__;
const root = h("div", {}, ...castabilityNodes(h, data, () => {}, (k) => k));
const out = {};
for (const id of ["castability", "commander-curve", "land-count-table", "land-classes", "search-lands", "search-assumption", "land-classes-unknown", "commander-start-note", "land-count-player"]) {
  const node = byId(root, id); out[id] = node ? text(node) : null;
}
process.stdout.write(JSON.stringify(out));
"""


def _render(data: dict[str, object]) -> dict[str, str | None]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: castability.js render test NOT_RUN, not a pass")
    script = (
        JS_RENDER.replace("__PRELUDE__", _ui_prelude())
        .replace("__ZAHL__", json.dumps(str(STATIC / "zahl.js")))
        .replace("__CAST__", json.dumps(str(STATIC / "castability.js")))
        .replace("__DATA__", json.dumps(data, ensure_ascii=False))
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return dict(json.loads(done.stdout))


def test_castability_display_shows_direct_search_commander_table_and_assumption() -> None:
    result = castability.deck_castability(_chulane_shaped())
    result["zahlen"] = number_contract.castability_zahlen(result)
    shown = _render(result)
    table = shown["castability"] or ""
    assert "Quellen direkt" in table and "Quellen über Suchland" in table
    assert "U 17" in table and "U 20 (+3)" in table
    assert "65,2 %" in table and "76,4 %" in table  # UU on turn 3, direct and with search
    curve = shown["commander-curve"] or ""
    assert "Commander GWU" in curve and "45,6 %" in curve and "92,0 %" in curve
    assert "42,0 %" in curve and "97,1 %" in curve and "44,3 %" in curve
    assert "Nichtstartspieler (zieht in Zug 1): in Zug 5 12 Karten" in (
        shown["commander-start-note"] or ""
    )
    assert "Startspieler sieht in Zug 5 nur 11 Karten" in (shown["commander-start-note"] or "")
    assert "Nichtstartspieler (zieht in Zug 1)" in (shown["land-count-player"] or "")
    land_table = shown["land-count-table"] or ""
    assert "Zug 3 · 10 Karten" in land_table and "36 (Deck)" in land_table
    assert "78,1 %" in land_table  # 36 lands, turn 3 = p_land_drops of the turn-3 rows
    assert "Klasse bestimmt für 36 von 36 Ländern" in (shown["land-classes"] or "")
    assert "erreichbare Farben WUG" in (shown["search-lands"] or "")
    assert (shown["search-assumption"] or "").startswith("Annahme: Rechenannahme")
    assert shown["land-classes-unknown"] is None


def test_castability_display_names_unknown_lands_apart() -> None:
    gate = "{3}, {T}: Search your library for a Gate card, put it onto the battlefield."
    result = castability.deck_castability([*_chulane_shaped(), _land("Maze", "C", text=gate)])
    result["zahlen"] = number_contract.castability_zahlen(result)
    shown = _render(result)
    assert "Klasse bestimmt für 36 von 37 Ländern" in (shown["land-classes"] or "")
    assert "unbekannt 1" in (shown["land-classes"] or "")
    unknown = shown["land-classes-unknown"] or ""
    assert "Maze" in unknown and "nicht 0" in unknown


def test_castability_display_shows_unknown_never_zero_for_missing_values() -> None:
    result = castability.deck_castability(_chulane_shaped())
    for item in result["requirements"]:
        item["with_search"] = {"sources": {}, "p_colours_given_lands": None, "p_on_curve": None}
    result["zahlen"] = []
    shown = _render(result)
    table = shown["castability"] or ""
    assert table.count("unbekannt") == 26


def _reference_joint(
    groups: list[tuple[frozenset[str], int]],
    nonland: int,
    draws: int,
    min_lands: int,
    need: dict[str, int],
) -> tuple[int, int, int]:
    """Unpruned reference Hall-condition DP on the raw land groups."""
    colours = sorted(need)
    masks = range(1, 1 << len(colours))
    caps = tuple(sum(need[c] for bit, c in enumerate(colours) if mask >> bit & 1) for mask in masks)
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, tuple(0 for _ in caps)): 1}
    for produced, size in groups:
        nxt: dict[tuple[int, tuple[int, ...]], int] = {}
        own = sum(1 << bit for bit, c in enumerate(colours) if c in produced)
        hits = tuple(1 if own & mask else 0 for mask in masks)
        for (lands, got), ways in states.items():
            for take in range(0, min(size, draws - lands) + 1):
                key = (
                    lands + take,
                    tuple(
                        min(cap, g + take * h) for cap, g, h in zip(caps, got, hits, strict=True)
                    ),
                )
                nxt[key] = nxt.get(key, 0) + ways * comb(size, take)
        states = nxt
    total = comb(sum(size for _, size in groups) + nonland, draws)
    with_lands = 0
    with_both = 0
    for (lands, got), ways in states.items():
        rest = draws - lands
        if rest < 0 or rest > nonland:
            continue
        count = ways * comb(nonland, rest)
        if lands >= min_lands:
            with_lands += count
            if got == caps:
                with_both += count
    return total, with_lands, with_both


def test_joint_matches_reference_and_worst_case_five_colour_is_fast() -> None:
    """Projected/pruned ``_joint`` is integer-identical to the raw DP and fast in the 5-colour
    worst case (27 land groups, 7 coloured symbols, 5 colours; Refs #1751)."""
    small_cases = [
        # duplicate projections + zero-colour lands + always-satisfied mask
        (
            [
                (frozenset({"W", "R"}), 2),
                (frozenset({"W", "B"}), 3),
                (frozenset({"U"}), 2),
                (frozenset({"R", "G"}), 2),
                (frozenset(), 3),
            ],
            8,
            6,
            3,
            {"W": 1, "U": 1},
        ),
        # all masks always satisfied when min_lands=5 (only 2 non-W lands in 7 total)
        (
            [(frozenset({"W"}), 5), (frozenset({"U"}), 2)],
            5,
            6,
            5,
            {"W": 3},
        ),
        # 5-colour small deck with 7 symbols
        (
            [
                (frozenset({"W"}), 2),
                (frozenset({"U"}), 2),
                (frozenset({"B", "R"}), 2),
                (frozenset({"G", "W"}), 2),
                (frozenset("WUBRG"), 2),
                (frozenset(), 2),
            ],
            8,
            10,
            7,
            {"W": 2, "U": 2, "B": 1, "R": 1, "G": 1},
        ),
        # impossible: too few sources for one colour
        (
            [(frozenset({"W"}), 1), (frozenset({"U"}), 4), (frozenset(), 2)],
            10,
            8,
            4,
            {"W": 2, "U": 1},
        ),
    ]
    for groups, nonland, draws, min_lands, need in small_cases:
        castability._joint_cached.cache_clear()
        assert castability._joint(groups, nonland, draws, min_lands, need) == _reference_joint(
            groups, nonland, draws, min_lands, need
        )

    # Worst case: 27 distinct land groups (5 mono, 10 dual, 10 tri, 1 five-colour, 1 colourless),
    # 7 coloured pips across all 5 colours, turn 7 (14 draws, 63 nonlands)
    worst_groups = (
        [(frozenset({c}), 2) for c in "WUBRG"]
        + [(frozenset(p), 1) for p in combinations("WUBRG", 2)]
        + [(frozenset(t), 1) for t in combinations("WUBRG", 3)]
        + [(frozenset("WUBRG"), 3), (frozenset(), 3)]
    )
    assert len(worst_groups) == 27
    worst_need = {"W": 2, "U": 2, "B": 1, "R": 1, "G": 1}
    castability._joint_cached.cache_clear()
    t0 = time.perf_counter()
    result = castability.colour_probability(worst_groups, 63, worst_need, 7)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"worst-case colour_probability took {elapsed:.3f}s (limit 0.5s)"
    assert result["p_land_drops"] == 0.1977
    assert result["p_colours_given_lands"] == 0.517
    assert result["p_on_curve"] == 0.1022
