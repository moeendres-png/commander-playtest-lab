"""Tests for card_text_drift: engine rules text vs printed Oracle text."""

from commander_lab.engine.card_text_drift import (
    compare_card,
    is_basic_land,
    normalize_engine_rules,
    normalize_oracle_text,
    number_multiset,
    split_engine_faces,
    split_oracle_faces,
)


def _oracle(name: str, **kw: object) -> dict:
    base: dict = {
        "oracle_name": name,
        "name": name,
        "oracle_text": "",
        "mana_cost": "{1}{W}",
        "mana_value": 2,
        "type_line": "Creature \u2014 Human",
        "power": 2,
        "toughness": 2,
        "loyalty": None,
        "keywords": [],
    }
    base.update(kw)
    return base


def _facts(name: str, **kw: object) -> dict:
    base: dict = {
        "engine_name": name,
        "rules": [],
        "mana_cost": "{1}{W}",
        "mana_value": 2.0,
        "types": ["CREATURE"],
        "subtypes": ["Human"],
        "supertypes": [],
        "power": 2.0,
        "toughness": 2.0,
        "loyalty": None,
    }
    base.update(kw)
    return base


def test_equal_text_is_ok():
    # (a) a card with equal text is OK.
    o = _oracle("Test Card", oracle_text="Flying, vigilance", keywords=["Flying", "Vigilance"])
    f = _facts("Test Card", rules=["Flying", "Vigilance"])
    drift = compare_card(o, f, known_keywords=["Flying", "Vigilance"])
    assert drift.tier == "OK"
    assert drift.similarity == 1.0


def test_missing_keyword_is_tier_b():
    # (b) engine text lacking a printed keyword is tier B.
    o = _oracle(
        "Test Card",
        oracle_text="Flying, vigilance",
        keywords=["Flying", "Vigilance"],
    )
    f = _facts("Test Card", rules=["Flying"])
    drift = compare_card(o, f, known_keywords=["Flying", "Vigilance"])
    assert drift.tier == "B"
    assert "vigilance" in drift.keywords_only_oracle


def test_different_mana_cost_is_tier_a():
    # (c) a different mana cost is tier A.
    o = _oracle("Test Card", mana_cost="{2}{W}")
    f = _facts("Test Card", mana_cost="{1}{W}")
    drift = compare_card(o, f)
    assert drift.tier == "A"
    assert any(s.field == "mana_cost" for s in drift.structural)


def test_normalisation_strips_reminder_html_this():
    # (d) reminder text, {this}, HTML and entities normalise to equal strings.
    name = "Abomination, World Ravager"
    oracle = (
        "Menace, trample\n"
        "Mayhem {4}{R} (You may cast this card from your graveyard for "
        "{4}{R} if you discarded it this turn. Timing rules still apply.)"
    )
    engine = [
        "Mayhem {4}{R} <i>(You may cast this card from your graveyard for "
        "{4}{R} if you discarded it this turn. Timing rules still apply.)</i>",
        "Menace",
        "Trample",
    ]
    o_norm = normalize_oracle_text(oracle, name)
    e_norm = normalize_engine_rules(engine, name)
    # Same tokens, possibly in different order (oracle lists keywords first,
    # engine lists them as separate lines); punctuation-insensitive.
    import re as _re

    def _tok(s: str) -> list[str]:
        return sorted(_re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", t) for t in s.split())

    assert _tok(o_norm) == _tok(e_norm)

    # {this} normalisation.
    assert normalize_engine_rules(["{this} enters tapped."], "Some Land") == normalize_oracle_text(
        "Some Land enters tapped.", "Some Land"
    )

    # HTML entities.
    assert normalize_engine_rules(["A &mdash; B"], "X") == normalize_oracle_text("A \u2014 B", "X")


def test_split_card_face_by_face():
    # (e) a split card is compared face by face.
    o_faces = split_oracle_faces("Destroy target artifact.\n//\nDestroy target enchantment.")
    assert len(o_faces) == 2
    e_faces = split_engine_faces(
        [
            "Destroy target artifact.",
            "Destroy target enchantment.",
            "--------\nFuse <i>(reminder)</i>",
        ]
    )
    assert len(e_faces) == 2

    o = _oracle(
        "Wear // Tear",
        oracle_text="Destroy target artifact.\n//\nDestroy target enchantment.",
    )
    f = _facts(
        "Wear // Tear",
        rules=[
            "Destroy target artifact.",
            "Destroy target enchantment.",
            "--------\nFuse <i>(reminder)</i>",
        ],
    )
    drift = compare_card(o, f)
    assert drift.tier == "OK"


def test_vehicle_null_power_is_export_gap():
    # Oracle defines power, engine export has null for a Vehicle.
    o = _oracle("Test Vehicle", power=5, type_line="Artifact \u2014 Vehicle")
    f = _facts("Test Vehicle", power=None, types=["ARTIFACT"], subtypes=["Vehicle"])
    drift = compare_card(o, f)
    assert drift.tier == "EXPORT_GAP"


def test_basic_lands_excluded():
    for land in ("Plains", "Island", "Swamp", "Mountain", "Forest"):
        assert is_basic_land(land)
    assert not is_basic_land("Sol Ring")


def test_number_multiset():
    assert number_multiset("draw 2 cards then draw 3") == {"2": 1, "3": 1}
    assert number_multiset("no numbers here") == {}


def test_u2212_minus_normalises_to_ascii():
    # U+2212 (minus sign) must become ASCII "-" so planeswalker loyalty
    # costs compare equal: oracle "<U+2212>8" vs engine "-8".
    o = normalize_oracle_text("\u22128: deal 10 damage", "Chandra Nalaar")
    e = normalize_engine_rules(["-8: {this} deals 10 damage"], "Chandra Nalaar")
    assert "\u2212" not in o
    assert number_multiset(o) == number_multiset(e)


def test_coercive_impetus_numbers_differ_is_tier_b():
    # Real engine difference: +2/+2 vs printed +1/+1 must surface as
    # tier B with the differing numbers (triage maps it to DIFFERENT).
    o = _oracle(
        "Coercive Impetus",
        oracle_text=("Enchant creature\nEnchanted creature gets +1/+1 and is goaded."),
        keywords=["Goad"],
        power=None,
        toughness=None,
        type_line="Enchantment \u2014 Aura",
    )
    f = _facts(
        "Coercive Impetus",
        rules=["Enchant creature", "Enchanted creature gets +2/+2 and is goaded."],
        types=["ENCHANTMENT"],
        subtypes=["Aura"],
        power=None,
        toughness=None,
    )
    drift = compare_card(o, f, known_keywords=["Goad"])
    assert drift.tier == "B"
    assert set(drift.numbers_only_oracle) == {"1"}
    assert set(drift.numbers_only_engine) == {"2"}
