"""Search lands as sources, the commander on curve and the land count table (#1404, builder
audit WP-2 and WP-3).

All decks here are synthetic: land groups and costs only, with made-up names, so that no test
can pass by reading a card name. The Chulane-shaped deck copies the land groups and the 26
coloured requirements of the Chulane baseline as counts; its expected values are the hand
calculation of the builder audit (UU on turn 3 65.2 -> 76.4 %, mean +5.5 pp over 26
requirements, Chulane 2GWU on turn 5 45.6 % x 92.8 % = 42.4 %), checked again exactly here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
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


def test_their_library_and_reminder_text_are_no_own_search() -> None:
    their = _land(
        "Odd",
        "C",
        text="{T}: Add {C}.\n{2}, {T}, Sacrifice this land: That land's controller may "
        "search their library for a basic land card, put it onto the battlefield.",
    )
    cycling = _land(
        "Odd 2",
        "C",
        text="{T}: Add {C}.\nBasic landcycling {1} ({1}, Discard this card: Search your library "
        "for a basic land card, reveal it, put it into your hand, then shuffle.)",
    )
    assert castability.classify_land(their)["class"] == castability.LAND_NO_COLOUR
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
    assert round(float(mean) * 100, 1) == 5.5
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
    assert commander["p_colours_given_lands"] == 0.9283
    assert commander["p_on_curve"] == 0.4237
    assert commander["with_search"]["p_colours_given_lands"] == 0.9732
    assert commander["with_search"]["p_on_curve"] == 0.4442
    # the commander is no card of the library: 99 cards, 36 lands
    assert commander["sources"] == {"G": 18, "U": 17, "W": 15}
    # the same value as the shared function on the same groups (no new heuristic)
    groups = [(frozenset(k), n) for k, n in _groups(search=False).items()]
    same = castability.colour_probability(groups, 63, {"G": 1, "W": 1, "U": 1}, 5)
    for key in ("p_land_drops", "p_colours_given_lands", "p_on_curve"):
        assert commander[key] == same[key], key


def test_tam_shaped_commander_1gu_by_enumeration() -> None:
    # a 12-card mini deck: 5 lands (2 U, 1 G, 1 GU fetch target, 1 search land), 7 spells
    rows = [
        _row("Commander GU", zone="commander", mana_cost="{1}{G}{U}", mana_value=3),
        _land("Isle", "U", "Basic Land — Island", qty=2),
        _land("Woods", "G", "Basic Land — Forest"),
        _land("Typed GU", "GU", "Land — Forest Island"),
        _land("Fetch FI", "", text="{T}, Sacrifice this land: Search your library for a Forest "
              "or Island card, put it onto the battlefield, then shuffle."),
        _spell("Spell", "{2}", 2, qty=7),
    ]  # fmt: skip
    (commander,) = castability.deck_castability(rows)["commander"]
    assert (commander["turn"], commander["draws"], commander["label"]) == (3, 10, "GU")
    cards: list[frozenset[str] | None] = [frozenset("U")] * 2 + [frozenset("G"), frozenset("GU")]
    for search, key in ((False, None), (True, "with_search")):
        deck = [*cards, frozenset("GU") if search else frozenset(), *([None] * 7)]
        total = lands_ok = both = 0
        for hand in combinations(range(12), 10):
            lands = [deck[i] for i in hand if deck[i] is not None]
            total += 1
            if len(lands) >= 3:
                lands_ok += 1
                if any("G" in land for land in lands) and any("U" in land for land in lands):
                    both += 1
        shown = commander if key is None else {**commander, **commander[key]}
        assert shown["p_land_drops"] == round(lands_ok / total, 4)
        assert shown["p_colours_given_lands"] == round(both / lands_ok, 4)
        assert shown["p_on_curve"] == round(both / total, 4)


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
    ]  # fmt: skip
    deck = land_advisor.deck_profile(rows)
    colours = {entry["colour"]: entry for entry in deck["colours"]}
    assert set(colours) == {"W", "U"}
    assert {c: colours[c]["land_sources"] for c in colours} == {"W": 1, "U": 4}
    # the fetch reaches G through the Forest Plains dual, but G is outside the identity
    assert {c: colours[c]["search_sources"] for c in colours} == {"W": 1, "U": 1}
    assert deck["lands_search"] == 1 and deck["lands_search_unknown"] == 1
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
    assert curve["cast.commander.Commander GWU.p_on_curve"] == 0.4237
    assert curve["cast.commander.Commander GWU.p_on_curve_with_search"] == 0.4442


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
for (const id of ["castability", "commander-curve", "land-count-table", "land-classes", "search-lands", "search-assumption", "land-classes-unknown"]) {
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
    assert "Commander GWU" in curve and "45,6 %" in curve and "92,8 %" in curve
    assert "42,4 %" in curve and "97,3 %" in curve and "44,4 %" in curve
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
