"""WS207 setup tests (no JVM required).

Validates denominator preservation, Commander singleton legality with the
B01/E01 setup-only corrections, setup-prefs hold invariants, Oracle
equivalence constants, and seed-scan determinism rules.
"""

import sys
from pathlib import Path

import pytest

WS207_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS207_ROOT))

import ws207_decks as decks  # noqa: E402

EXPECTED_ORDER = [
    "RQ-C3-A03",
    "RQ-C3-A04",
    "RQ-C3-B01",
    "RQ-C3-C01",
    "RQ-C3-C03",
    "RQ-C3-D06",
    "RQ-C3-E01",
    "RQ-C3-E02",
    "RQ-C3-F01",
    "RQ-C3-G02",
    "RQ-C3-G03",
    "RQ-C3-G04",
    "RQ-C3-H01",
    "RQ-C3-I01",
    "RQ-C3-J02",
]


def all_constructions():
    out = []
    for slot in decks.SLOT_ORDER:
        if slot == "RQ-C3-H01":
            for sub in ("HUMILITY_FIRST", "CLONE_FIRST", "NO_HUMILITY"):
                out.append((slot, sub))
        else:
            out.append((slot, ""))
    return out


def test_denominator_is_exactly_15_with_h01_as_one_slot():
    assert decks.SLOT_ORDER == EXPECTED_ORDER
    assert len(decks.SLOT_ORDER) == 15


def test_engine_pin_preserved():
    assert decks.ENGINE_PIN == "cfc36f445f917f101fa2ed588770e043f53bc44c"


def test_oracle_substitute_identities():
    assert decks.B01_SUBSTITUTE == "Essence Warden"
    assert decks.B01_REPLACED == "Soul Warden"
    assert decks.E01_SUBSTITUTE == "Grizzly Bears"
    assert decks.E01_REPLACED == "Runeclaw Bear"
    assert decks.B01_SUBSTITUTE != decks.B01_REPLACED
    assert decks.E01_SUBSTITUTE != decks.E01_REPLACED


@pytest.mark.parametrize("slot,sub", all_constructions())
def test_decks_are_commander_singleton_legal(slot, sub):
    built = decks.build_decks(slot, sub)
    assert set(built) == {"seat0", "seat1", "seat2", "seat3"}
    assert decks.check_singleton_legal(built) == []


def test_b01_singleton_correction_shape():
    built = decks.build_decks("RQ-C3-B01")
    p0 = built["seat0"]["mainboard"]
    assert "Soul Warden" in p0
    assert "Essence Warden" in p0
    assert "Llanowar Elves" in p0
    assert p0.count("Soul Warden") == 1
    for seat in ("seat1", "seat2", "seat3"):
        assert built[seat]["mainboard"].count("Soul Warden") == 1


def test_e01_singleton_correction_shape():
    built = decks.build_decks("RQ-C3-E01")
    p1 = built["seat1"]["mainboard"]
    assert "Runeclaw Bear" in p1
    assert "Grizzly Bears" in p1
    assert p1.count("Runeclaw Bear") == 1
    assert p1.count("Grizzly Bears") == 1


def test_b01_p0_can_pay_both_warden_costs():
    built = decks.build_decks("RQ-C3-B01")
    p0 = built["seat0"]["mainboard"]
    assert "Forest" in p0  # {G} for Essence Warden / Elves
    assert "Plains" in p0  # {W} for Soul Warden


@pytest.mark.parametrize("slot,sub", all_constructions())
def test_setup_prefs_never_wish_held_behavior_cards(slot, sub):
    prefs = decks.build_setup_prefs(slot, sub)
    held = decks.HELD_BEHAVIOR_CARDS.get(slot, [])
    wished: list[str] = []
    for section in ("priority", "choice", "target", "declare_attacker", "mode"):
        block = prefs.get(section, {})
        if isinstance(block, dict):
            for names in block.values():
                wished.extend(n.lower() for n in names)
    for card in held:
        assert card.lower() not in wished, f"{slot}: held {card} is wished"


def test_g03_prelude_attacks_with_commander():
    prefs = decks.build_setup_prefs("RQ-C3-G03")
    assert prefs["declare_attacker"] == {"0": ["Ghalta"]}
    assert prefs["priority"].get("0") == ["Ghalta"]


def test_seed_scan_ranges_are_fixed_and_disjoint():
    bases = [decks.seed_scan_base(slot) for slot in decks.SLOT_ORDER]
    assert len(set(bases)) == len(bases)
    for slot in decks.SLOT_ORDER:
        base = decks.seed_scan_base(slot)
        assert base == decks.SEED_SCAN_BASE + decks.SLOT_ORDER.index(slot) * decks.SEED_SCAN_STRIDE
    assert decks.SEED_SCAN_COUNT == 60


def test_opening_requirements_reference_deck_or_commander_cards():
    for slot in decks.SLOT_ORDER:
        if slot == "RQ-C3-G03":
            continue
        built = decks.build_decks(slot)
        pool: set[str] = set()
        for seat in built.values():
            pool.update(seat["mainboard"])
            pool.update(seat["commanders"])
        for _seat_key, cards in decks.OPENING_REQUIREMENTS.get(slot, {}).items():
            for card in cards:
                options = [o.strip() for o in card.split("|")]
                assert any(opt in pool for opt in options), (
                    f"{slot}: requirement {card} not in any deck"
                )


def test_scan_widths_cover_multi_card_openings():
    assert decks.SCAN_COUNT_DEFAULT == 60
    assert decks.SCAN_COUNT_WIDE == 300
    for slot in ("RQ-C3-A03", "RQ-C3-B01", "RQ-C3-H01", "RQ-C3-I01"):
        assert decks.SCAN_COUNT_PER_SLOT[slot] == 300
    for slot in ("RQ-C3-C03", "RQ-C3-F01", "RQ-C3-G02", "RQ-C3-G03"):
        assert decks.SCAN_COUNT_PER_SLOT.get(slot, decks.SCAN_COUNT_DEFAULT) == 60


def test_h01_no_humility_deck_has_no_humility():
    built = decks.build_decks("RQ-C3-H01", "NO_HUMILITY")
    pool: list[str] = []
    for seat in built.values():
        pool.extend(seat["mainboard"])
    assert "Humility" not in pool
    full = decks.build_decks("RQ-C3-H01", "HUMILITY_FIRST")
    pool_full: list[str] = []
    for seat in full.values():
        pool_full.extend(seat["mainboard"])
    assert "Humility" in pool_full
