"""Tapped land classes and the tempo figure (builder audit WP-4, L2) and the mana base
before/after in the variant comparison (WP-5, L5), #1404.

All decks are synthetic, with made-up names, so that no test can pass by reading a card name.
The Chulane-shaped deck has the land groups of the Chulane baseline and, per land, a rules text
of the same form as the real card (8 of 36 lands always tapped, 2 of 36 tapped unless the
player controls two or more basic lands, recounted on the store copy of the baseline). Hand
calculations are written as products or sums of binomial coefficients, independent of the code
under test. The tapped figures must leave every earlier castability and diff figure unchanged
(byte-equal hashes taken on main 138a50c2 before this change).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from math import comb
from pathlib import Path

import pytest

from commander_lab.studio import castability, deck_diff, number_contract
from commander_lab.studio.decks import RevisionCard

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"

ALWAYS = "This land enters tapped."
BOUNCE = ALWAYS + "\nWhen this land enters, return a land you control to its owner's hand."
SCRY = ALWAYS + "\nWhen this land enters, scry 1."
TWO_BASICS = "This land enters tapped unless you control two or more basic lands."
BASIC_SEARCH = (
    "{T}, Sacrifice this land: Search your library for a basic land card, put it onto the "
    "battlefield tapped, then shuffle."
)
ANY_COLOUR = "{T}: Add one mana of any color in your commander's color identity."

# Hashes of the earlier output, taken on main 138a50c2 (before WP-4/WP-5) with the scripts of
# this module: deck_castability of the Chulane-shaped deck of the WP-2 tests without the new
# keys, its number contracts without the new ids, and diff_impact of the store fixture of
# test_studio_deck_diff without the new key.
MAIN_CAST_SHA = "fb3728e3a2d293507e4946873598e4f638fd0d09ff79830d1519667390c680d2"
MAIN_ZAHLEN_SHA = "e85c32a3b5f9c9754f8a170ab7387999042b6bf7f9ad10ac27c3a6c415b226fb"
MAIN_DIFF_SHA = "3b978a789142a91f81e790a58d9e180efd045da8ba79b7ee802ace434bbafcf4"
NEW_CAST_KEYS = ("tapped", "colour_access")


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


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


# --- WP-4 stage 1: one class per land from the rules text ---------------------------------


@pytest.mark.parametrize(
    ("name", "text", "klass", "quote"),
    [
        ("Odd 1", ALWAYS, "immer_getappt", ALWAYS),
        ("Odd 2", BOUNCE, "immer_getappt", ALWAYS),
        ("Old Form", "Old Form enters the battlefield tapped.", "immer_getappt", None),
        ("Short, the Long", "Short enters tapped.", "immer_getappt", None),
        (
            "Odd 3",
            "This land enters tapped with two charge counters on it.",
            "immer_getappt",
            None,
        ),
        ("Odd 4", TWO_BASICS, "bedingt_getappt", TWO_BASICS),
        (
            "Odd 5",
            "This land enters tapped unless you control two or more other lands.",
            "bedingt_getappt",
            None,
        ),
        (
            "Odd 6",
            "This land enters tapped unless you control a Plains or an Island.",
            "bedingt_getappt",
            None,
        ),
        (
            "Odd 7",
            "As this land enters, you may pay 2 life. If you don't, it enters tapped.",
            "bedingt_getappt",
            "If you don't, it enters tapped.",
        ),
        (
            "Odd 8",
            "If you control two or more other lands, this land enters tapped.",
            "bedingt_getappt",
            None,
        ),
        ("Odd 9", "You may have this land enter tapped.", "bedingt_getappt", None),
        ("Odd 10", "{T}: Add {G}.", "ungetappt", None),
        ("Odd 11", "({T}: Add {G}.)", "ungetappt", None),
        ("Odd 12", "(This land enters tapped.)\n{T}: Add {G}.", "ungetappt", None),
        ("Odd 13", "{T}: Add {G}. // " + ALWAYS, "ungetappt", None),
        ("Odd 14", None, "unbekannt", None),
        ("Odd 15", "Creatures your opponents control enter tapped.", "unbekannt", None),
        ("Mine", "Other Card enters tapped.", "unbekannt", None),
        ("Odd 16", ALWAYS + "\nLands your opponents control enter tapped.", "unbekannt", None),
    ],
)
def test_tapped_class_from_rules_text(
    name: str, text: str | None, klass: str, quote: str | None
) -> None:
    info = castability.tapped_class(_land(name, "G", text=text))
    assert info["class"] == klass
    if quote is not None:
        assert info["quote"] == quote
    if klass in ("immer_getappt", "bedingt_getappt"):
        assert isinstance(info["quote"], str) and "tapped" in info["quote"]
    if klass == "unbekannt":
        assert info["reason"] in (castability.REASON_TAP_NO_TEXT, castability.REASON_TAP_UNREADABLE)


def test_the_class_never_comes_from_the_name() -> None:
    plain = castability.tapped_class(_land("Tapped Ruins of Tapping", "R", text="{T}: Add {R}."))
    assert plain["class"] == "ungetappt"
    for name in ("Quick Grove", "Fast Untapped Land", "Temple of Nothing"):
        assert castability.tapped_class(_land(name, "G", text=ALWAYS))["class"] == "immer_getappt"


def test_search_land_is_classed_by_its_own_entry_and_quotes_the_fetched_land() -> None:
    info = castability.tapped_class(_land("Seeker", "", text=BASIC_SEARCH))
    assert info["class"] == "ungetappt" and info["quote"] is None
    assert info["fetch_quote"] == BASIC_SEARCH


def _chulane_shaped() -> list[dict[str, object]]:
    """The 36 lands of the Chulane baseline as synthetic rows with rules texts of the same
    form, 26 coloured requirements reduced to three, and fillers to 99 cards."""
    rows = [_row("Commander GWU", zone="commander", mana_cost="{2}{G}{W}{U}", mana_value=5)]
    rows += [
        _land("Bounce WU", "WU", text=BOUNCE),
        _land("Typed WU", "WU", "Land — Plains Island", text=TWO_BASICS),
        _land("Scry WU", "WU", text=SCRY),
        _land("Typed WG", "WG", "Land — Forest Plains", text=TWO_BASICS),
        _land("Bounce WG", "WG", text=BOUNCE),
        _land("Filter WG", "WG", text="{1}, {T}: Add {G}{W}."),
        _land("Scry WG", "WG", text=SCRY),
        _land("Bounce UG", "UG", text=BOUNCE),
        _land("Scry UG", "UG", text=SCRY),
        _land("Tri WUG", "WUG", text=ALWAYS + "\n{T}: Add {G}, {W}, or {U}."),
        _land("Any 1", "WUBRG", text=ANY_COLOUR),
        _land("Any 2", "WUBRG", text="{T}: Add one mana of any color."),
        _land("Any 3", "WUBRG", text=ALWAYS + "\n" + ANY_COLOUR),
        _land("Woods", "G", "Basic Land — Forest", text="({T}: Add {G}.)", qty=8),
        _land("Isle", "U", "Basic Land — Island", text="({T}: Add {U}.)", qty=8),
        _land("Field", "W", "Basic Land — Plains", text="({T}: Add {W}.)", qty=4),
        _land("Seeker 1", "", text=BASIC_SEARCH),
        _land("Seeker 2", "", text=BASIC_SEARCH),
        _land("Seeker 3", "", text=BASIC_SEARCH),
        _spell("Spell W", "{W}", 1),
        _spell("Spell UU", "{1}{U}{U}", 3),
        _spell("Spell G", "{G}", 1),
        _row("Filler", type_line="Artifact", mana_cost="{3}", mana_value=3, quantity=60),
    ]
    return rows


def test_chulane_shaped_tapped_counts_8_and_2_of_36() -> None:
    tapped = castability.deck_castability(_chulane_shaped())["tapped"]
    assert tapped["counts"] == {
        "immer_getappt": 8,
        "bedingt_getappt": 2,
        "ungetappt": 26,
        "unbekannt": 0,
    }
    assert tapped["of"] == 36 and tapped["classified"] == 36
    by_name = {land["name"]: land for land in tapped["lands"]}
    assert by_name["Typed WU"]["quote"] == TWO_BASICS
    assert by_name["Bounce UG"]["quote"] == ALWAYS
    assert by_name["Seeker 2"]["fetch_quote"] == BASIC_SEARCH
    # the list starts with the always tapped lands, then the conditional ones
    assert [land["class"] for land in tapped["lands"][:10]] == ["immer_getappt"] * 8 + [
        "bedingt_getappt"
    ] * 2


def test_unknown_is_its_own_class_and_never_untapped() -> None:
    rows = [*_chulane_shaped(), _land("No Text", "G", text=None)]
    result = castability.deck_castability(rows)
    tapped = result["tapped"]
    assert tapped["counts"]["unbekannt"] == 1 and tapped["counts"]["ungetappt"] == 26
    assert tapped["classified"] == 36 and tapped["of"] == 37
    green = next(c for c in result["colour_access"]["colours"] if c["colour"] == "G")
    # the unknown land is a source in the upper bound only
    assert (green["untapped_low"], green["untapped_high"]) == (11, 13)


def test_land_without_colour_data_counts_in_the_upper_bounds_only() -> None:
    """Review round 1 of #1755: a land without colour data (``produced_mana`` None, no basic
    land type) is a source of every colour in the upper bounds and in none of the lower ones."""
    rows = [*_chulane_shaped(), _land("Blank Land", None, text="{T}: Add {C}.")]
    access = castability.deck_castability(rows)["colour_access"]
    assert access["library"] == 100 and access["lands_unknown_colours"] == 1
    white = next(c for c in access["colours"] if c["colour"] == "W")
    assert (white["sources"], white["untapped_low"], white["untapped_high"]) == (15, 7, 10)
    hand = white["opening_hand"]
    assert hand["p"] == round(float(_at_least_one(100, 15, 7)), 4)
    assert hand["p_high"] == round(float(_at_least_one(100, 16, 7)), 4)
    assert hand["p_high"] > hand["p"]
    for turn in white["turns"]:
        draws = 7 + turn["turn"]
        assert turn["p_low"] == round(float(_at_least_one(100, 7, draws)), 4)
        assert turn["p_high"] == round(float(_at_least_one(100, 10, draws)), 4)


# --- WP-4 stage 2: exact colour access, lower and upper bound -----------------------------


def _at_least_one(library: int, sources: int, draws: int) -> Fraction:
    """1 - P(no source in ``draws`` cards), written as a product (hand calculation)."""
    none = Fraction(1)
    for index in range(draws):
        none *= Fraction(library - sources - index, library - index)
    return 1 - none


def test_colour_access_equals_the_hand_calculation() -> None:
    access = castability.deck_castability(_chulane_shaped())["colour_access"]
    assert access["library"] == 99 and access["lands_unknown_colours"] == 0
    colours = {item["colour"]: item for item in access["colours"]}
    assert list(colours) == ["W", "U", "G"]  # only colours with a coloured symbol
    # W: 15 sources; untapped 7 (Filter, Any 1, Any 2, 4 Field), +2 conditional (Typed)
    # U: 17 sources; untapped 10, +1 conditional; G: 18 sources; untapped 11, +1 conditional
    expected = {"W": (15, 7, 9), "U": (17, 10, 11), "G": (18, 11, 12)}
    for colour, (sources, low, high) in expected.items():
        item = colours[colour]
        assert (item["sources"], item["untapped_low"], item["untapped_high"]) == (
            sources,
            low,
            high,
        )
        assert item["opening_hand"]["p"] == round(float(_at_least_one(99, sources, 7)), 4)
        assert item["opening_hand"]["p"] == item["opening_hand"]["p_high"]
        for turn in item["turns"]:
            draws = 7 + turn["turn"]
            assert turn["draws"] == draws
            assert turn["p_low"] == round(float(_at_least_one(99, low, draws)), 4)
            assert turn["p_high"] == round(float(_at_least_one(99, high, draws)), 4)
    # the same figures as on the store copy of the Chulane baseline
    assert [t["p_low"] for t in colours["W"]["turns"]] == [0.4563, 0.4981]
    assert [t["p_high"] for t in colours["W"]["turns"]] == [0.5472, 0.592]
    assert colours["U"]["opening_hand"]["p"] == 0.7446


def test_access_assumption_is_one_sentence_and_shown_with_the_rule() -> None:
    assumption = castability.TAPPED_ACCESS_ASSUMPTION
    body = assumption.split(":", 1)[1].strip()
    assert body.count(".") == 1 and body.endswith(".")
    assert "Nichtstartspieler" in castability.TAPPED_ACCESS_RULE
    assert "Untere Grenze" in castability.TAPPED_ACCESS_RULE
    assert "keine Suchländer" in castability.TAPPED_ACCESS_RULE


def test_access_is_unknown_when_the_library_is_smaller_than_the_draw() -> None:
    rows = [_land("Isle", "U", "Basic Land — Island", text="({T}: Add {U}.)", qty=3)]
    rows.append(_spell("Spell U", "{U}", 1, qty=4))
    item = castability.deck_castability(rows)["colour_access"]["colours"][0]
    assert item["opening_hand"]["p"] == 1.0  # 7 of 7 cards, all three sources drawn
    assert [t["p_low"] for t in item["turns"]] == [None, None]


# --- the tapped figures leave the earlier figures byte-equal (Hall assignment of #1751) ---


def _wp2_chulane() -> list[dict[str, object]]:
    from tests.unit.test_studio_castability_search_lands import _chulane_shaped as wp2

    return wp2()


def test_earlier_castability_figures_are_byte_equal_to_main() -> None:
    result = castability.deck_castability(_wp2_chulane())
    zahlen = number_contract.castability_zahlen(result)
    for key in NEW_CAST_KEYS:
        result.pop(key)
    assert _sha(result) == MAIN_CAST_SHA
    old = [z for z in zahlen if not str(z["id"]).startswith(("cast.tapped.", "cast.access."))]
    assert _sha(old) == MAIN_ZAHLEN_SHA
    assert zahlen[: len(old)] == old  # the new contracts are only appended


def test_earlier_diff_figures_are_byte_equal_to_main(tmp_path: Path) -> None:
    from tests.unit.test_studio_deck_diff import _store

    store, ids = _store(tmp_path)
    cmd = RevisionCard("card:project:0001", 1, "commander")
    base = [cmd, RevisionCard(ids["Filler 01"]), RevisionCard(ids["Filler 02"])]
    target = [cmd, RevisionCard(ids["Filler 01"]), RevisionCard(ids["Swarm Rat"], 2)]
    result = deck_diff.diff_impact(store, base, target)
    assert "manabase" in result
    result.pop("manabase")
    assert _sha(result) == MAIN_DIFF_SHA


def test_land_basis_gives_the_same_figures_as_deck_castability() -> None:
    rows = _wp2_chulane()
    basis = castability.LandBasis(rows)
    for item in castability.deck_castability(rows)["requirements"]:
        again = basis.requirement(item["need"], item["turn"])
        for key in ("p_land_drops", "p_colours_given_lands", "p_on_curve", "sources"):
            assert again[key] == item[key]
        assert again["with_search"] == item["with_search"]


# --- WP-5: mana base before/after, two synthetic states against a hand calculation --------


def _state(*, isles: int, tapped_u: int, woods: int, spell: tuple[str, str]) -> list[dict]:
    rows = [_row("Cmd", zone="commander", mana_cost="{1}{U}", mana_value=2)]
    rows.append(_land("Isle", "U", "Basic Land — Island", text="({T}: Add {U}.)", qty=isles))
    if tapped_u:
        rows.append(_land("Slow Isle", "U", text=ALWAYS + "\n{T}: Add {U}.", qty=tapped_u))
    rows.append(_land("Woods", "G", "Basic Land — Forest", text="({T}: Add {G}.)", qty=woods))
    rows.append(_spell("Twin", "{U}{U}", 2))
    rows.append(_spell(spell[0], spell[1], 1))
    rows.append(_row("Filler", type_line="Artifact", mana_cost="{3}", mana_value=3, quantity=10))
    return rows


BASE = _state(isles=4, tapped_u=2, woods=2, spell=("Sprout", "{G}"))
TARGET = _state(isles=7, tapped_u=0, woods=1, spell=("Spark", "{W}"))


def _colours_given_lands(library: int, lands: int, sources: int, draws: int, need: int) -> Fraction:
    """P(at least ``need`` sources | at least ``draws - 7`` lands), as sums (hand calculation)."""
    minimum = draws - 7
    lands_ok = both = 0
    for held in range(minimum, min(lands, draws) + 1):
        ways = comb(lands, held) * comb(library - lands, draws - held)
        lands_ok += ways
        good = sum(
            comb(sources, s) * comb(lands - sources, held - s)
            for s in range(need, min(sources, held) + 1)
        )
        both += good * comb(library - lands, draws - held)
    return Fraction(both, lands_ok)


def test_manabase_delta_equals_the_hand_calculation() -> None:
    mb = deck_diff.manabase_delta(BASE, TARGET)
    reqs = {(r["label"], r["turn"]): r for r in mb["requirements"]}
    assert set(reqs) == {("UU", 2), ("G", 1), ("W", 1)}
    uu = reqs[("UU", 2)]
    base_uu = round(float(_colours_given_lands(20, 8, 6, 9, 2)), 4)
    target_uu = round(float(_colours_given_lands(20, 8, 7, 9, 2)), 4)
    assert (base_uu, target_uu) == (0.9033, 0.9661)
    assert uu["base"]["p_colours_given_lands"] == base_uu
    assert uu["target"]["p_colours_given_lands"] == target_uu
    assert uu["delta_pp"]["p_colours_given_lands"] == 6.28
    assert uu["delta_pp"]["p_land_drops"] == 0.0  # same land count: land drops unchanged
    assert uu["in_base"] and uu["in_target"]
    # a requirement of one list only is computed exactly on the other land base too
    sprout = reqs[("G", 1)]
    assert sprout["in_base"] and not sprout["in_target"]
    assert sprout["base"]["p_colours_given_lands"] == round(
        float(_colours_given_lands(20, 8, 2, 8, 1)), 4
    )
    assert sprout["target"]["p_colours_given_lands"] == round(
        float(_colours_given_lands(20, 8, 1, 8, 1)), 4
    )
    spark = reqs[("W", 1)]
    assert not spark["in_base"] and spark["in_target"]
    assert spark["base"]["p_colours_given_lands"] == 0.0  # known: no white source, not unknown
    assert spark["delta_pp"]["p_colours_given_lands"] == 0.0


def test_manabase_delta_opening_hand_tapped_access_and_commander() -> None:
    mb = deck_diff.manabase_delta(BASE, TARGET)
    keep = Fraction(
        sum(comb(8, n) * (comb(12, 7 - n) - comb(10, 7 - n)) for n in range(2, 5)), comb(20, 7)
    )
    assert mb["opening_hand"]["base"] == round(float(keep), 4) == mb["opening_hand"]["target"]
    assert mb["opening_hand"]["delta_pp"] == 0.0
    assert (
        mb["tapped"]["base"]["immer_getappt"] == 2 and mb["tapped"]["target"]["immer_getappt"] == 0
    )
    assert mb["tapped"]["delta"] == {
        "immer_getappt": -2,
        "bedingt_getappt": 0,
        "ungetappt": 2,
        "unbekannt": 0,
    }
    assert (mb["tapped"]["base_of"], mb["tapped"]["target_of"]) == (8, 8)
    access = {row["colour"]: row for row in mb["colour_access"]}
    assert list(access) == ["W", "U", "G"]
    blue = access["U"]
    assert blue["base"]["turn1_low"] == round(float(_at_least_one(20, 4, 8)), 4)
    assert blue["target"]["turn1_low"] == round(float(_at_least_one(20, 7, 8)), 4)
    assert blue["base"]["hand"] == round(float(_at_least_one(20, 6, 7)), 4)
    expected = round(
        (round(float(_at_least_one(20, 7, 8)), 4) - round(float(_at_least_one(20, 4, 8)), 4)) * 100,
        2,
    )
    assert blue["delta_pp"]["turn1_low"] == expected
    assert access["W"]["in_target"] and not access["W"]["in_base"]
    assert access["G"]["in_base"] and not access["G"]["in_target"]
    (cmd,) = mb["commander"]["rows"]
    assert mb["commander"]["same"] and cmd["name"] == "Cmd"
    assert cmd["base"]["p_colours_given_lands"] == round(
        float(_colours_given_lands(20, 8, 6, 9, 1)), 4
    )
    assert cmd["delta_pp"]["p_colours_given_lands"] == round(
        (cmd["target"]["p_colours_given_lands"] - cmd["base"]["p_colours_given_lands"]) * 100, 2
    )


def test_manabase_delta_is_unknown_where_a_side_cannot_be_computed() -> None:
    no_lands = [r for r in BASE if "Land" not in str(r["type_line"])]
    mb = deck_diff.manabase_delta(no_lands, TARGET)
    uu = next(r for r in mb["requirements"] if r["label"] == "UU")
    assert uu["base"]["p_colours_given_lands"] is None  # no draw holds two lands: unknown
    assert uu["delta_pp"]["p_colours_given_lands"] is None
    assert uu["target"]["p_colours_given_lands"] is not None
    assert mb["opening_hand"]["delta_pp"] == round(
        (mb["opening_hand"]["target"] - mb["opening_hand"]["base"]) * 100, 2
    )


def test_different_commanders_get_no_commander_delta() -> None:
    other = [dict(r) for r in TARGET]
    other[0] = _row("Other Cmd", zone="commander", mana_cost="{1}{U}", mana_value=2)
    mb = deck_diff.manabase_delta(BASE, other)
    assert mb["commander"]["same"] is False
    assert {row["name"] for row in mb["commander"]["rows"]} == {"Cmd", "Other Cmd"}
    for row in mb["commander"]["rows"]:
        assert row["delta_pp"] is None
    cmd = next(row for row in mb["commander"]["rows"] if row["name"] == "Cmd")
    assert cmd["target"] is None and cmd["base"] is not None


def test_partner_sets_that_differ_get_no_commander_delta_even_for_the_shared_partner() -> None:
    partner_b = _row("Partner B", zone="commander", mana_cost="{G}", mana_value=1)
    partner_c = _row("Partner C", zone="commander", mana_cost="{W}", mana_value=1)
    mb = deck_diff.manabase_delta([*BASE, partner_b], [*TARGET, partner_c])
    assert mb["commander"]["same"] is False
    shared = next(row for row in mb["commander"]["rows"] if row["name"] == "Cmd")
    assert shared["base"] is not None and shared["target"] is not None
    assert shared["delta_pp"] is None  # two different commander sets are never compared


def test_diff_contracts_carry_the_manabase_as_exact_and_pp() -> None:
    zahlen = number_contract.diff_zahlen({"manabase": deck_diff.manabase_delta(BASE, TARGET)})
    by_id = {z["id"]: z for z in zahlen}
    assert all(not number_contract.check(z) for z in zahlen)
    assert by_id["manabase.UU.2.delta_pp"]["wert"] == 6.28
    assert by_id["manabase.UU.2.delta_pp"]["einheit"] == "pp"
    assert by_id["manabase.UU.2.base"]["einheit"] == "Anteil"
    tapped = by_id["manabase.tapped.immer_getappt.base"]
    assert (tapped["n"], tapped["N"]) == (2, 8)
    assert all(z["klasse"] == "EXAKT" for z in zahlen)


# --- the display under node ---------------------------------------------------------------


def _ui_prelude() -> str:
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
    part = ui[ui.index("function _formatDe(n, opts) {") : ui.index("// Simulator readiness codes")]
    return "globalThis.StudioUI = (() => {" + part + "return {num, pct, numFlex, numSig}; })();\n"


JS_RENDER = r"""
const vm = require("node:vm");
const fs = require("node:fs");
__PRELUDE__
globalThis.StudioZahl = require(__ZAHL__);
vm.runInThisContext(fs.readFileSync(__FILE__, "utf8"));
const h = (tag, props, ...kids) => ({ tag, props: props || {}, kids: kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== "") });
const text = (node) => (typeof node === "string" || typeof node === "number" ? String(node) : node.kids.map(text).join(""));
const byId = (node, id) => { if (!node || typeof node !== "object") return null; if (node.props.id === id) return node; for (const kid of node.kids) { const f = byId(kid, id); if (f) return f; } return null; };
const data = __DATA__;
const root = h("div", {}, ...__CALL__);
const out = {};
for (const id of __IDS__) { const node = byId(root, id); out[id] = node ? text(node) : null; }
process.stdout.write(JSON.stringify(out));
"""


def _render(file: str, call: str, data: object, ids: list[str]) -> dict[str, str | None]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: render test NOT_RUN, not a pass")
    script = (
        JS_RENDER.replace("__PRELUDE__", _ui_prelude())
        .replace("__ZAHL__", json.dumps(str(STATIC / "zahl.js")))
        .replace("__FILE__", json.dumps(str(STATIC / file)))
        .replace("__CALL__", call)
        .replace("__IDS__", json.dumps(ids))
        .replace("__DATA__", json.dumps(data, ensure_ascii=False))
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return dict(json.loads(done.stdout))


def test_castability_page_shows_classes_quotes_access_and_the_assumption() -> None:
    result = castability.deck_castability(_chulane_shaped())
    result["zahlen"] = number_contract.castability_zahlen(result)
    shown = _render(
        "castability.js",
        "castabilityNodes(h, data, () => {}, (k) => k)",
        result,
        ["tapped-classes", "tapped-lands", "colour-access", "access-assumption", "access-note"],
    )
    classes = shown["tapped-classes"] or ""
    assert "immer getappt 8 von 36" in classes and "bedingt getappt 2 von 36" in classes
    assert "unbekannt 0 von 36" in classes and "Klasse bestimmt für 36 von 36" in classes
    lands = shown["tapped-lands"] or ""
    assert f"„{TWO_BASICS}“" in lands and f"„{ALWAYS}“" in lands
    assert "Geholtes Land: „{T}, Sacrifice this land" in lands
    access = shown["colour-access"] or ""
    assert "45,6 % \u2013 54,7 %" in access  # W turn 1, lower and upper bound
    assert "74,5 %" in access  # U opening hand, one value
    assert "15 (7 \u2013 9)" in access
    assert (shown["access-assumption"] or "").startswith("Annahme (ein Satz):")
    note = shown["access-note"] or ""
    assert note.startswith("Keine Grenze des Farbzugriffs:")
    assert "getappte Länder aus Zug 1, die in Zug 2 schon Mana geben, sind nicht gezählt" in note
    source = (STATIC / "castability.js").read_text(encoding="utf-8")
    assert '"Ungetappte Quelle früh"' in source and "Farbzugriff früh (exakt)" not in source


def test_diff_page_shows_pp_deltas_only_in_and_unknown() -> None:
    no_lands = [r for r in BASE if "Land" not in str(r["type_line"])]
    other = [dict(r) for r in TARGET]
    other[0] = _row("Other Cmd", zone="commander", mana_cost="{1}{U}", mana_value=2)
    data = {
        "a": deck_diff.manabase_delta(BASE, TARGET),
        "b": deck_diff.manabase_delta(no_lands, other),
    }
    ids = [
        "diff-manabase",
        "diff-opening-hand",
        "diff-colour-access",
        "diff-access-note",
        "diff-tapped",
        "diff-commander",
    ]
    a = _render("diffimpact.js", "diffManabaseNodes(h, data.a)", data, ids)
    b = _render("diffimpact.js", "diffManabaseNodes(h, data.b)", data, ids)
    table = a["diff-manabase"] or ""
    assert "90,3 %" in table and "96,6 %" in table and "+6,3 pp" in table
    assert "G Zug 1 · nur in Basis" in table and "W Zug 1 · nur aktuell" in table
    assert "0,0 pp" in (a["diff-opening-hand"] or "")
    tapped = a["diff-tapped"] or ""
    assert "2 von 8" in tapped and "0 von 8" in tapped and "\u22122" in tapped
    assert "nur aktuell gebraucht" in (a["diff-colour-access"] or "")
    assert "ungetappte Quelle direkt Zug 1" in (a["diff-colour-access"] or "")
    assert (a["diff-access-note"] or "").startswith("Keine Grenze des Farbzugriffs:")
    assert "Cmd" in (a["diff-commander"] or "") and "pp" in (a["diff-commander"] or "")
    assert "unbekannt" in (b["diff-manabase"] or "")
    assert "kein Delta: anderer Commander" in (b["diff-commander"] or "")
