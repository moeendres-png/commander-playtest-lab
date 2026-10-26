"""Meta-Lane PR5: Spellbook wiring as metadata-only (design §5.4, §6 PR5).

Combo lines are metadata, never rules knowledge: containment in a deck
says nothing about legality or strength. Snapshot packages become a
scoring input for the first time, with the PR4 veto live (vetoed
packages contribute exactly 0) and band separation enforced (a cEDH
line/package never counts for a casual band). No test here uses games,
collection data, or the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab.models import FormatBand, MetaCategory, MetaComboLine, MetaPackage
from commander_lab.whole_deck.meta import (
    known_combos_in_deck,
    load_snapshot_packages,
    load_spellbook_combos,
    snapshot_package_term,
)

ROOT = Path(__file__).resolve().parents[2]
ROGSHAI_PACKAGES = ROOT / "data/meta/packages/rogshai-2026-10-25.json"
CHULANE_PACKAGES = ROOT / "data/meta/packages/chulane-2026-10-25.json"
COMBOS = ROOT / "data/meta/spellbook_combos.json"


def _package(package_id: str, cards: tuple[str, ...], bands: tuple[str, ...]) -> MetaPackage:
    return MetaPackage(
        package_id=package_id,
        name=package_id,
        cards=cards,
        roles=("engine",),
        categories=tuple(MetaCategory(band) for band in bands),
        description="test package",
    )


def _combo(
    combo_id: str,
    cards: tuple[str, ...],
    bands: tuple[FormatBand, ...],
    any_of: tuple[tuple[str, ...], ...] = (),
) -> MetaComboLine:
    return MetaComboLine(
        combo_id=combo_id,
        commander="Test Commander",
        cards=cards,
        any_of=any_of,
        bands=bands,
        source="test",
        result="test result",
    )


def test_package_files_load_with_expected_counts() -> None:
    rogshai = load_snapshot_packages(ROGSHAI_PACKAGES)
    chulane = load_snapshot_packages(CHULANE_PACKAGES)
    assert rogshai
    assert chulane
    assert len(rogshai) == 7
    assert len(chulane) == 8
    assert {package.package_id for package in rogshai} == {
        "rogshai-cantrips",
        "rogshai-prowess-magecraft",
        "rogshai-jeska-kediss-finisher",
        "rogshai-rograkh-free-mana",
        "rogshai-engine-spam",
        "rogshai-polymorph",
        "rogshai-ishai-protection",
    }
    assert {package.package_id for package in chulane} == {
        "chulane-bounce-engine",
        "chulane-landfall",
        "chulane-etb-draw",
        "chulane-aluren-loop",
        "chulane-intruder-alarm-loop",
        "chulane-combat-finisher",
        "chulane-protection",
        "chulane-elf-ramp",
    }


def test_combo_file_loads_eleven_lines_and_no_dockside() -> None:
    combos = load_spellbook_combos(COMBOS)
    assert combos
    assert len(combos) == 11
    assert {combo.combo_id for combo in combos} == {
        "rogshai-breach-led-freeze",
        "rogshai-twinflame-loop",
        "rogshai-breach-grinding-station",
        "rogshai-breach-wheel-led",
        "chulane-drake-overburden",
        "chulane-bellringer-labmaniac",
        "chulane-aluren-drake",
        "chulane-intruder-alarm-bounce",
        "chulane-forager-turns",
        "chulane-sage-altered-ego",
        "chulane-ranger-symbiote",
    }
    for combo in combos:
        assert "Dockside Extortionist" not in combo.cards
        assert all("Dockside Extortionist" not in group for group in combo.any_of)
    # The name appears only in the provenance exclusion note, never as data.
    data = json.loads(COMBOS.read_text(encoding="utf-8"))
    excluded = data["provenance"]["excluded_lines"]
    assert len(excluded) == 1
    assert excluded[0]["cards"] == [
        "Chulane, Teller of Tales",
        "Dockside Extortionist",
        "Coercive Recruiter",
    ]


def test_containment_needs_every_named_card() -> None:
    combo = _combo(
        "test-line",
        ("Chulane, Teller of Tales", "Shrieking Drake", "Overburden"),
        (FormatBand.HIGH_POWER,),
    )
    full = ["Chulane, Teller of Tales", "Shrieking Drake", "Overburden", "Sol Ring"]
    assert known_combos_in_deck(full, [combo]) == (combo,)
    assert known_combos_in_deck(full[:2], [combo]) == ()
    assert known_combos_in_deck([], [combo]) == ()


def test_containment_normalizes_case_and_whitespace() -> None:
    combo = _combo(
        "test-line",
        ("Shrieking Drake", "Overburden"),
        (FormatBand.HIGH_POWER,),
    )
    assert known_combos_in_deck(["  shrieking drake ", "OVERBURDEN"], [combo]) == (combo,)


def test_containment_any_of_groups() -> None:
    combo = _combo(
        "test-line",
        ("Chulane, Teller of Tales", "Intruder Alarm"),
        (FormatBand.HIGH_POWER,),
        any_of=(("Whitemane Lion", "Shrieking Drake", "Stonecloaker"),),
    )
    assert known_combos_in_deck(
        ["Chulane, Teller of Tales", "Intruder Alarm", "Stonecloaker"], [combo]
    ) == (combo,)
    assert (
        known_combos_in_deck(["Chulane, Teller of Tales", "Intruder Alarm", "Sol Ring"], [combo])
        == ()
    )


def test_containment_band_filter() -> None:
    cedh_only = _combo(
        "cedh-line",
        ("Underworld Breach", "Lion's Eye Diamond", "Brain Freeze"),
        (FormatBand.CEDH_TOURNAMENT,),
    )
    deck = ["Underworld Breach", "Lion's Eye Diamond", "Brain Freeze"]
    assert known_combos_in_deck(deck, [cedh_only]) == (cedh_only,)
    assert known_combos_in_deck(deck, [cedh_only], band=FormatBand.CEDH_TOURNAMENT) == (cedh_only,)
    assert known_combos_in_deck(deck, [cedh_only], band=FormatBand.HIGH_POWER) == ()
    multi = _combo(
        "multi-band",
        ("Dualcaster Mage", "Twinflame"),
        (FormatBand.HIGH_POWER, FormatBand.CEDH_TOURNAMENT),
    )
    assert known_combos_in_deck(
        ["Dualcaster Mage", "Twinflame"], [multi], band=FormatBand.HIGH_POWER
    ) == (multi,)


def test_real_combo_lines_contained_by_target_shaped_decks() -> None:
    combos = load_spellbook_combos(COMBOS)
    assert combos
    chulane_deck = ["Chulane, Teller of Tales", "Shrieking Drake", "Overburden"]
    found = known_combos_in_deck(chulane_deck, combos, band=FormatBand.HIGH_POWER)
    assert [combo.combo_id for combo in found] == ["chulane-drake-overburden"]
    # The target decks contain no combo line: documentation, not a gap.
    assert known_combos_in_deck(["Sol Ring", "Arcane Signet"], combos) == ()


def test_package_term_shape_and_thresholds() -> None:
    package = _package("pkg", ("A", "B", "C"), ("high_power",))
    assert snapshot_package_term([package], [], FormatBand.HIGH_POWER) == 0.0
    assert snapshot_package_term([package], ["A"], FormatBand.HIGH_POWER) == 0.0
    assert snapshot_package_term([package], ["A", "B"], FormatBand.HIGH_POWER) == pytest.approx(
        -0.01
    )
    assert snapshot_package_term([package], ["A", "B", "C"], FormatBand.HIGH_POWER) == (
        pytest.approx(-0.04)
    )


def test_package_term_veto_and_band() -> None:
    vetoed = _package("pkg", ("A", "B"), ("high_power",)).model_copy(
        update={"vetoed_by_games": True}
    )
    assert snapshot_package_term([vetoed], ["A", "B"], FormatBand.HIGH_POWER) == 0.0
    cedh = _package("pkg", ("A", "B"), ("cedh_tournament",))
    assert snapshot_package_term([cedh], ["A", "B"], FormatBand.HIGH_POWER) == 0.0
    assert snapshot_package_term([cedh], ["A", "B"], FormatBand.CEDH_TOURNAMENT) == (
        pytest.approx(-0.01)
    )
    assert snapshot_package_term([], ["A", "B"], FormatBand.HIGH_POWER) == 0.0


def test_package_term_sums_qualifying_packages_only() -> None:
    first = _package("pkg1", ("A", "B"), ("high_power",))
    second = _package("pkg2", ("B", "C", "D"), ("high_power",))
    other_band = _package("pkg3", ("A", "B"), ("cedh_tournament",))
    term = snapshot_package_term(
        [first, second, other_band], ["A", "B", "C", "D"], FormatBand.HIGH_POWER
    )
    assert term == pytest.approx(-0.01 - 0.04)


def test_scoring_path_never_imports_spellbook_sync() -> None:
    src = ROOT / "src/commander_lab/whole_deck"
    for name in ("meta.py", "search_meta_score.py", "search_construct.py"):
        text = (src / name).read_text(encoding="utf-8")
        assert "commander_spellbook" not in text
        assert "sync_commander_spellbook_snapshot" not in text


def test_combo_model_rejects_empty_cards_and_groups() -> None:
    with pytest.raises(ValidationError):
        _combo("bad", (), (FormatBand.HIGH_POWER,))
    with pytest.raises(ValidationError):
        _combo("bad", ("A",), (FormatBand.HIGH_POWER,), any_of=((),))
