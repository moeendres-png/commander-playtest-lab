"""Counted deck-list universes: signal import, the choice of the universe, scoring with a
counted zero, the commander-specific tier rule. All data is synthetic."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    builder,
    import_all,
    signals,
    strength,
    strength_view,
    universe,
    universe_choice,
)
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_store import _synthetic_cards, _workbook
from tests.unit.test_studio_strength import (
    COMMANDER,
    OTHER,
    _by_name,
    _component,
    _import,
    _write,
    _write_signals,
)
from tests.unit.test_studio_universe_web import _deck

FIELDS = [
    "card_name",
    "source",
    "bracket",
    "decks_with_card",
    "universe_decks",
    "share",
    "universe_snapshot",
]
FILE = "synthetic_decklist_inclusion_20261112.csv"
HEADER = {"X-Studio": "1"}


def _rows(
    source: str,
    bracket: int,
    total: int,
    counts: dict[str, int],
    *,
    commander: str = COMMANDER,
    own: int | None = None,
) -> list[dict[str, object]]:
    snapshot = f"universe:{source}{bracket}:{total}"
    listed = {commander: total if own is None else own, **counts}
    return [
        {
            "card_name": name,
            "source": source,
            "bracket": bracket,
            "decks_with_card": count,
            "universe_decks": total,
            "share": f"{count / total:.4f}",
            "universe_snapshot": snapshot,
        }
        for name, count in listed.items()
    ]


def _write_counted(folder: Path, rows: list[dict[str, object]], name: str = FILE) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _write(folder / name, rows, FIELDS)
    return folder


def _both(commander: str = COMMANDER) -> list[dict[str, object]]:
    """Two universes: edhrec bracket 3 (200 decks) and archidekt bracket 4 (500 decks)."""
    return _rows("edhrec", 3, 200, {"Filler 01": 150, "Filler 02": 20, "Filler 03": 5}) + _rows(
        "archidekt", 4, 500, {"Filler 01": 100, "Filler 04": 400}, commander=commander
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    _write_signals(tmp_path / "signals")
    yield opened
    opened.close()


def _stored(store: StudioStore, commander: str = COMMANDER) -> int:
    return int(
        store.connection.execute(
            "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal LIKE ?",
            (commander, "decklist_universe:%"),
        ).fetchone()[0]
    )


def _import_counted(
    store: StudioStore, folder: Path, commander: str = COMMANDER
) -> dict[str, object]:
    return signals.import_signals(store, folder, commander=commander)


def _file_report(report: dict[str, object]) -> signals.FileReport:
    files = report["files"]
    assert isinstance(files, dict)
    return files["synthetic_decklist_inclusion_20261112"]  # type: ignore[no-any-return]


def _compute(store: StudioStore, **settings: object) -> strength_view.StrengthResult:
    return strength_view.compute(store, COMMANDER, StrengthSettings(**settings))  # type: ignore[arg-type]


# ---------- import ----------


def test_each_universe_is_stored_as_its_own_signal_with_counts_and_snapshot(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = _write_counted(tmp_path / "counted", [*_both(), _both()[1]])  # one duplicate row
    report = _import_counted(store, folder)
    file_report = _file_report(report)
    assert file_report["status"] == "IMPORTED" and report["files_refused"] == 0
    assert file_report["skipped_reasons"] == {"DUPLICATE_SAME_FIGURES": 1}
    row = store.connection.execute(
        "SELECT * FROM card_signal WHERE commander_name = ? AND signal = ? AND card_name = ?",
        (COMMANDER, "decklist_universe:edhrec:3", "Filler 01"),
    ).fetchone()
    assert row is not None
    assert (row["numerator"], row["denominator"], row["value"]) == (150, 200, 0.75)
    assert row["source_id"].startswith("src:")
    found = universe_choice.counted_universes(store, COMMANDER)
    assert [(item["source"], item["bracket"], item["denominator"]) for item in found] == [
        ("archidekt", "4", 500),
        ("edhrec", "3", 200),
    ]
    assert found[1]["snapshot_id"] == "universe:edhrec3:200"
    assert found[1]["label"] == "Gezählte Decklisten (Repo): EDHREC, Bracket 3, 200 Decks"
    assert _import_counted(store, folder)["rows_replaced"] == _stored(store)  # idempotent


def test_numbered_parts_are_read_in_order(store: StudioStore, tmp_path: Path) -> None:
    rows = _both()
    folder = tmp_path / "parts"
    _write_counted(folder, rows[:3], "synthetic_decklist_inclusion_20261112_1.csv")
    _write_counted(folder, rows[3:], "synthetic_decklist_inclusion_20261112_2.csv")
    report = _import_counted(store, folder)
    parts = _file_report(report)["parts"]
    assert parts == [
        "synthetic_decklist_inclusion_20261112_1.csv",
        "synthetic_decklist_inclusion_20261112_2.csv",
    ]
    assert len(universe_choice.counted_universes(store, COMMANDER)) == 2


def test_only_the_universe_that_fails_the_commander_check_is_refused(
    store: StudioStore, tmp_path: Path
) -> None:
    # Three universes; the archidekt one lists the commander in 499 of 500 decks.
    rows = (
        _rows("edhrec", 3, 200, {"Filler 01": 150})
        + _rows("edhrec", 4, 300, {"Filler 01": 90})
        + _rows("archidekt", 3, 500, {"Filler 01": 100}, own=499)
    )
    report = _import_counted(store, _write_counted(tmp_path / "bad", rows))
    file_report = _file_report(report)
    assert file_report["status"] == "IMPORTED" and report["files_refused"] == 0
    assert report["universes_refused"] == 1
    assert file_report["skipped_reasons"] == {signals.COMMANDER_NOT_IN_EVERY_DECK: 1}
    assert file_report["universes_refused"] == [
        {
            "source": "archidekt",
            "bracket": "3",
            "reason": signals.COMMANDER_NOT_IN_EVERY_DECK,
            "commander_decks": 499,
            "universe_decks": 500,
            "rows_removed": 0,
        }
    ]
    stored = universe_choice.counted_universes(store, COMMANDER)
    assert [(item["source"], item["bracket"]) for item in stored] == [
        ("edhrec", "3"),
        ("edhrec", "4"),
    ]
    assert _stored(store) == file_report["rows_written"] > 0
    # The refused universe is no option: not listed, and asking for it names nothing.
    result = _compute(store, universe_source="counted:archidekt:3")
    assert result["universe_choice"]["kind"] == universe_choice.KIND_NONE


def test_a_refused_universe_loses_its_old_rows_and_is_no_longer_selectable(
    store: StudioStore, tmp_path: Path
) -> None:
    _import_counted(store, _write_counted(tmp_path / "good", _both()))
    before = {item["value"] for item in universe_choice.counted_universes(store, COMMANDER)}
    assert before == {"counted:edhrec:3", "counted:archidekt:4"}
    assert _choice(store)["counted"] == "counted:edhrec:3"  # the bracket-matching one
    # Re-import: edhrec 3 now lists the commander in 199 of 200 decks, archidekt 4 is fine.
    broken = _rows("edhrec", 3, 200, {"Filler 01": 150}, own=199) + _rows(
        "archidekt", 4, 500, {"Filler 01": 100, "Filler 04": 400}
    )
    report = _import_counted(store, _write_counted(tmp_path / "broken", broken))
    refused = _file_report(report)["universes_refused"]
    assert [(item["source"], item["bracket"], item["rows_removed"]) for item in refused] == [
        ("edhrec", "3", 4)
    ]
    assert [item["value"] for item in universe_choice.counted_universes(store, COMMANDER)] == [
        "counted:archidekt:4"
    ]
    assert _stored(store) > 0
    chosen = _choice(store)  # auto can no longer take the refused universe
    assert chosen["counted"] == "counted:archidekt:4" and chosen["kind"] == "counted"
    asked = _choice(store, universe_source="counted:edhrec:3")
    assert asked["kind"] == universe_choice.KIND_NONE


@pytest.mark.parametrize("field", ["source", "bracket"])
def test_a_universe_name_with_a_colon_is_refused_with_its_own_reason(
    store: StudioStore, tmp_path: Path, field: str
) -> None:
    bad = [{**row, field: f"{row[field]}:x"} for row in _rows("edhrec", 3, 200, {"Filler 01": 9})]
    good = _rows("edhrec", 4, 300, {"Filler 01": 90})
    report = _import_counted(store, _write_counted(tmp_path / "colon", bad + good))
    refused = _file_report(report)["universes_refused"]
    assert [item["reason"] for item in refused] == [signals.INVALID_UNIVERSE_NAME]
    assert [item["value"] for item in universe_choice.counted_universes(store, COMMANDER)] == [
        "counted:edhrec:4"
    ]


def test_a_card_whose_front_face_is_withheld_stays_unknown_not_zero(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    # Two Studio cards share the front face "Fire": the double-faced card does not claim it.
    for card_id, name in (("card:project:0130", "Fire // Ice"), ("card:project:0131", "Fire")):
        store.connection.execute(
            "UPDATE card SET oracle_name = ?, oracle_id = NULL WHERE card_id = ?", (name, card_id)
        )
    store.connection.commit()
    counts = {"Fire": 50, "Filler 01": 150}
    rows = _rows("edhrec", 3, 200, counts)
    _import_counted(store, _write_counted(tmp_path / "counted", rows))
    cards = _by_name(_compute(store, universe_source="counted:edhrec:3"))
    assert _component(cards["Fire"], "deck_universe")["numerator"] == 50  # the row is Fire's own
    double = _component(cards["Fire // Ice"], "deck_universe")
    assert double["status"] == strength.NO_VALUE and double["numerator"] is None
    assert double["status"] != strength.ZERO_COUNT
    # A card that is merely absent from the file is still a counted zero.
    assert _component(cards["Filler 20"], "deck_universe")["status"] == strength.ZERO_COUNT


def test_rows_that_match_no_store_card_are_counted_and_named(
    store: StudioStore, tmp_path: Path
) -> None:
    unknown = {"Nowhere Card": 120, "Curly \u2019Apostrophe\u2019 Card": 80, "Filler 01": 150}
    rows = _rows("edhrec", 3, 200, unknown) + _rows("archidekt", 4, 500, {"Nowhere Card": 3})
    report = _import_counted(store, _write_counted(tmp_path / "counted", rows))
    file_report = _file_report(report)
    unmatched = {(u["source"], u["bracket"]): u for u in file_report["universes_unmatched"]}
    assert set(unmatched) == {("edhrec", "3"), ("archidekt", "4")}
    first = unmatched[("edhrec", "3")]
    assert first["rows"] == 2 and first["examples"] == [
        "Nowhere Card",
        "Curly \u2019Apostrophe\u2019 Card",
    ]
    assert unmatched[("archidekt", "4")]["rows"] == 1
    assert report["rows_unmatched"] == 3
    assert _stored(store) > 0  # a notice, never a refusal
    client = TestClient(create_app(tmp_path / "studio"))
    listed = {
        (item["source"], item["bracket"]): item
        for item in client.get("/api/universe/counted", params={"commander": COMMANDER}).json()
    }
    assert listed[("edhrec", "3")]["unmatched_rows"] == 2
    assert listed[("edhrec", "3")]["unmatched_examples"] == [
        "Nowhere Card",
        "Curly \u2019Apostrophe\u2019 Card",
    ]
    assert "2 Zeilen" in listed[("edhrec", "3")]["notice"]
    # A fully matched universe has no notice.
    clean = _write_counted(tmp_path / "clean", _rows("edhrec", 3, 200, {"Filler 01": 150}))
    _import_counted(store, clean)
    again = client.get("/api/universe/counted", params={"commander": COMMANDER}).json()
    assert next(item for item in again if item["bracket"] == "3")["unmatched_rows"] == 0


def test_the_step_report_of_import_all_names_the_refused_universe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    research = tmp_path / "research"
    rows = _rows("edhrec", 3, 200, {"Filler 01": 1}) + _rows(
        "archidekt", 4, 199, {"Filler 01": 1}, own=198
    )
    _write_counted(research, rows)
    monkeypatch.setattr(import_all, "_RESEARCH", research)
    store = StudioStore.open(tmp_path / "all")
    steps = {step["step"]: step for step in import_all.run(_all_args(tmp_path), store)["steps"]}
    detail = steps["Signale research"]["detail"]
    assert "files_refused=0" in detail
    assert "Universum archidekt/4 abgelehnt" in detail
    assert "Commander in 198 von 199 Decks" in detail
    assert [item["source"] for item in universe_choice.counted_universes(store, COMMANDER)] == [
        "edhrec"
    ]
    store.close()


def test_a_file_of_another_commander_is_refused_for_this_one(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = _write_counted(
        tmp_path / "other", _rows("edhrec", 3, 200, {"Filler 01": 9}, commander=OTHER)
    )
    report = _import_counted(store, folder)  # imported for COMMANDER, built around OTHER
    assert _file_report(report)["status"] == signals.REFUSED
    assert _stored(store) == 0 and _stored(store, OTHER) == 0
    # Imported for the commander it was built around, it is accepted and stays that one's.
    _import_counted(store, folder, commander=OTHER)
    assert _stored(store, OTHER) > 0 and _stored(store) == 0
    assert universe_choice.counted_universes(store, COMMANDER) == []
    result = _compute(store, universe_source="counted:edhrec:3")
    assert result["universe_choice"]["kind"] == universe_choice.KIND_NONE
    assert strength.DECK_UNIVERSE not in result["collected"]


def test_a_commander_row_missing_from_a_universe_refuses_the_file(
    store: StudioStore, tmp_path: Path
) -> None:
    rows = [
        row for row in _rows("edhrec", 3, 200, {"Filler 01": 9}) if row["card_name"] != COMMANDER
    ]
    report = _import_counted(store, _write_counted(tmp_path / "nocmd", rows))
    assert _file_report(report)["skipped_reasons"] == {signals.COMMANDER_NOT_IN_EVERY_DECK: 1}
    assert _stored(store) == 0


def test_mixed_denominators_refuse_only_that_universe(store: StudioStore, tmp_path: Path) -> None:
    rows = _rows("edhrec", 3, 200, {"Filler 01": 150})
    rows[1]["universe_decks"] = 199
    report = _import_counted(store, _write_counted(tmp_path / "mixed", rows))
    file_report = _file_report(report)
    assert file_report["status"] == signals.REFUSED
    assert file_report["skipped_reasons"] == {signals.MIXED_DENOMINATORS: 1}
    assert _stored(store) == 0
    # Next to a clean universe only the mixed one is refused.
    both = _write_counted(tmp_path / "mixed2", rows + _rows("archidekt", 4, 50, {"Filler 01": 5}))
    file_report = _file_report(_import_counted(store, both))
    assert file_report["status"] == "IMPORTED"
    assert [item["reason"] for item in file_report["universes_refused"]] == [
        signals.MIXED_DENOMINATORS
    ]
    assert [item["source"] for item in universe_choice.counted_universes(store, COMMANDER)] == [
        "archidekt"
    ]


@pytest.mark.parametrize("bad", ["201", "-1", "x", "1.5"])
def test_an_invalid_count_refuses_the_file_instead_of_becoming_a_zero(
    store: StudioStore, tmp_path: Path, bad: str
) -> None:
    rows = _rows("edhrec", 3, 200, {"Filler 01": 150})
    rows[1]["decks_with_card"] = bad
    report = _import_counted(store, _write_counted(tmp_path / "invalid", rows))
    assert _file_report(report)["skipped_reasons"] == {signals.INVALID_COUNT: 1}
    assert _stored(store) == 0


def test_conflicting_duplicates_keep_the_first_row(store: StudioStore, tmp_path: Path) -> None:
    rows = _rows("edhrec", 3, 200, {"Filler 01": 150})
    rows.append({**rows[1], "decks_with_card": 3})
    report = _import_counted(store, _write_counted(tmp_path / "dup", rows))
    assert _file_report(report)["skipped_reasons"] == {"DUPLICATE_CONFLICT": 1}
    row = store.connection.execute(
        "SELECT numerator FROM card_signal WHERE signal = 'decklist_universe:edhrec:3' "
        "AND card_name = 'Filler 01'"
    ).fetchone()
    assert row["numerator"] == 150


# ---------- scoring: the counted zero ----------


def test_a_card_without_a_row_is_a_counted_zero_ranked_with_the_universe_denominator(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    result = _compute(store, universe_source="counted:edhrec:3")
    cards = _by_name(result)
    listed = _component(cards["Filler 02"], "deck_universe")
    zero = _component(cards["Filler 20"], "deck_universe")
    assert listed["status"] == strength.PRESENT and (
        listed["numerator"],
        listed["denominator"],
    ) == (20, 200)
    assert zero["status"] == strength.ZERO_COUNT
    assert (zero["numerator"], zero["denominator"]) == (0, 200)
    assert zero["percentile"] is not None and zero["percentile"] < listed["percentile"]
    assert "gezählt" in zero["note"] and "0 von 200" in zero["note"]
    assert result["universe_choice"]["denominator"] == 200
    assert result["universe_choice"]["snapshot_id"] == "universe:edhrec3:200"
    # Only the chosen universe counts: the 500-deck universe is never combined with it.
    assert {
        _component(card, "deck_universe")["denominator"]
        for card in cards.values()
        if _component(card, "deck_universe")["denominator"]
    } == {200}


def test_a_stored_profile_universe_treats_cards_in_no_deck_the_same_way(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    for index in range(10):
        _deck(store, f"s{index}", "edhrec", 3, ["Filler 01"] + (["Filler 02"] if index < 3 else []))
    store.connection.commit()
    universe.save_profile(store, "alle", {"min_universe": 10})
    result = _compute(store, universe_profile="alle")
    zero = _component(_by_name(result)["Filler 05"], "deck_universe")
    assert zero["status"] == strength.ZERO_COUNT
    assert (
        zero["numerator"] == 0 and zero["denominator"] == result["universe_choice"]["denominator"]
    )
    assert zero["percentile"] is not None


def test_unlisted_card_coverage_with_the_new_default_reaches_the_minimum(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    without = _by_name(_compute(store, universe_source="none"))
    with_universe = _by_name(_compute(store))  # the recommended "auto" picks the counted file
    # Weights 3 + 2 + 2 + 1 + 1 + 1 + 1 + 1 (playgroup) = 12; simulation is 0. Filler 09 is in no
    # commander signal and has no playgroup observation; global inclusion and combos exist.
    total = sum(strength.DEFAULT_WEIGHTS.values())
    assert total == 12.0
    assert without["Filler 09"]["coverage"] == pytest.approx(2 / total, abs=1e-4)
    assert without["Filler 09"]["tier"] == strength.TIER_UNKNOWN
    # deck universe 2 + global 1 + combos 1 = 4 of 12 = 0.33, above the minimum 0.3 even
    # WITHOUT a playgroup observation (with one it would be 5 of 12)
    assert with_universe["Filler 09"]["coverage"] == pytest.approx(4 / total, abs=1e-4)
    assert 4 / total >= StrengthSettings().min_coverage
    assert StrengthSettings().min_coverage == 0.3
    assert with_universe["Filler 09"]["tier"] in strength.TIERS
    assert with_universe["Filler 09"]["tier"] != strength.TIER_UNKNOWN


def test_a_zero_weight_universe_adds_neither_value_nor_coverage(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    off = _compute(store, weights={strength.DECK_UNIVERSE: 0.0})
    baseline = _compute(store, universe_source="none", weights={strength.DECK_UNIVERSE: 0.0})
    assert off["universe_choice"]["kind"] == universe_choice.KIND_COUNTED
    for card in off["cards"]:
        other = next(item for item in baseline["cards"] if item["card_id"] == card["card_id"])
        assert (card["index"], card["coverage"], card["tier"]) == (
            other["index"],
            other["coverage"],
            other["tier"],
        )
    unlisted = _by_name(off)["Filler 09"]
    assert _component(unlisted, "deck_universe")["weight"] == 0.0
    # 10 = the weights without the universe (3 + 2 + 1 + 1 + 1 + 1 + 1); global and combos exist
    assert unlisted["coverage"] == pytest.approx(2 / 10, abs=1e-4)


# ---------- the choice of the universe ----------


def _local_decks(store: StudioStore, total: int) -> None:
    """Add decks bound to the commander until it has ``total`` (the fixture holds a few)."""
    index = int(store.connection.execute("SELECT COUNT(*) FROM corpus_deck").fetchone()[0])
    while universe_choice.local_deck_count(store, COMMANDER) < total:
        _deck(store, f"l{index}", "edhrec", 3, ["Filler 01"] + (["Filler 02"] if index < 5 else []))
        store.connection.commit()
        index += 1
    assert universe_choice.local_deck_count(store, COMMANDER) == total


def _choice(store: StudioStore, **settings: object) -> universe_choice.UniverseChoice:
    return _compute(store, **settings)["universe_choice"]  # type: ignore[arg-type]


def test_the_recommended_source_is_automatic_and_none_switches_the_universe_off(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    assert StrengthSettings().universe_source == "auto"
    assert _choice(store)["kind"] == universe_choice.KIND_NONE  # nothing to choose from
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    chosen = _choice(store)
    assert chosen["kind"] == universe_choice.KIND_COUNTED and chosen["automatic"] is True
    assert strength.DECK_UNIVERSE in _compute(store)["collected"]
    none = _compute(store, universe_source="none")
    assert none["universe_choice"]["kind"] == universe_choice.KIND_NONE
    assert strength.DECK_UNIVERSE not in none["collected"]
    universe.save_profile(store, "p", {})
    only = _choice(store, universe_source="profile")
    assert only["kind"] == universe_choice.KIND_NONE  # "profile" without a selected profile
    assert _choice(store, universe_source="profile", universe_profile="p")["profile"] == "p"
    assert _choice(store, universe_source="none", universe_profile="p")["kind"] == "none"


def test_with_no_universe_only_the_commander_signal_rule_changes_a_tier(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    # Without the data minimum the rule is the only thing that keeps a card with just global
    # inclusion and combos from a tier.
    loose = {"universe_source": "none", "min_coverage": 0.0, "min_components": 1}
    recommended = _by_name(_compute(store, **loose))
    assert recommended
    without_rule = _by_name(_compute(store, require_commander_signal=False, **loose))
    changed = {n for n, card in recommended.items() if card["tier"] != without_rule[n]["tier"]}
    assert changed  # the rule really turns some tiers into "zu wenig Daten"
    for name in changed:  # the rule only ever turns a tier into "zu wenig Daten"
        assert recommended[name]["tier"] == strength.TIER_UNKNOWN
        assert recommended[name]["reason"] == strength.NO_COMMANDER_SIGNAL
    # Cards without a commander-specific ranked value are U, whatever global and combos say.
    only_independent = {name: 0.0 for name in strength.COMPONENTS}
    only_independent |= {strength.GLOBAL_INCLUSION: 5.0, strength.COMBOS: 5.0}
    on = _by_name(_compute(store, weights=only_independent, min_components=1))
    off = _by_name(
        _compute(store, weights=only_independent, min_components=1, require_commander_signal=False)
    )
    assert on["Filler 05"]["tier"] == strength.TIER_UNKNOWN
    assert on["Filler 05"]["reason"] == strength.NO_COMMANDER_SIGNAL
    assert on["Filler 05"]["note"] == "kein Signal speziell für diesen Commander"
    assert off["Filler 05"]["tier"] in strength.TIERS
    assert off["Filler 05"]["reason"] == "ENOUGH_DATA"


def test_require_commander_signal_counts_only_commander_specific_ranked_components(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    weights = {name: 0.0 for name in strength.COMPONENTS}
    weights |= {strength.GLOBAL_INCLUSION: 3.0, strength.COMBOS: 3.0, strength.SYNERGY: 3.0}
    settings = {"weights": weights, "min_coverage": 0.0, "min_components": 1}
    on = _by_name(_compute(store, **settings))
    # Filler 00 has no synergy value, Filler 05 has one: only the second has a commander signal.
    assert on["Filler 00"]["tier"] == strength.TIER_UNKNOWN
    assert on["Filler 05"]["tier"] in strength.TIERS
    # A commander-specific component with weight 0 does not count either.
    zero_weight = {**weights, strength.SYNERGY: 0.0}
    again = _by_name(_compute(store, weights=zero_weight, min_coverage=0.0, min_components=1))
    assert again["Filler 05"]["reason"] == strength.NO_COMMANDER_SIGNAL


def test_auto_prefers_a_profile_then_local_decks_then_counted_then_none(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    auto = {"universe_source": "auto"}
    assert _choice(store, **auto)["kind"] == universe_choice.KIND_NONE  # nothing at all
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    # counted, bracket "upgraded" = 3: the matching universe, although 500 decks is larger
    matching = _choice(store, **auto)
    assert (matching["kind"], matching["source"], matching["bracket"]) == ("counted", "edhrec", "3")
    assert matching["automatic"] is True and "automatisch gewählt" in matching["reason"]
    # optimized = 4 matches the other source's universe
    assert _choice(store, bracket="optimized", **auto)["source"] == "archidekt"
    # no bracket, or a bracket without a universe (cedh = 5): the largest denominator
    for bracket in ("none", "cedh"):
        largest = _choice(store, bracket=bracket, **auto)
        assert (largest["source"], largest["denominator"]) == ("archidekt", 500)
    # fewer local decks than the minimum universe do not count
    _local_decks(store, 29)
    assert _choice(store, **auto)["kind"] == universe_choice.KIND_COUNTED
    # local decks (>= 30) win over the counted file
    _local_decks(store, 30)
    local = _choice(store, **auto)
    assert (local["kind"], local["denominator"]) == (universe_choice.KIND_LOCAL, 30)
    # a selected stored profile wins over everything
    universe.save_profile(store, "p", {"min_universe": 1})
    picked = _choice(store, universe_profile="p", **auto)
    assert (picked["kind"], picked["profile"]) == (universe_choice.KIND_PROFILE, "p")


def test_auto_takes_the_local_universe_with_its_denominator_over_the_counted_one(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))  # 200 and 500 decks
    _local_decks(store, 31)
    chosen = _compute(store)["universe_choice"]
    assert (chosen["kind"], chosen["denominator"]) == (universe_choice.KIND_LOCAL, 31)
    assert chosen["counted"] == "" and chosen["automatic"] is True
    # Asking for the counted universe by name still gives exactly that one.
    named = _choice(store, universe_source="counted:archidekt:4")
    assert (named["kind"], named["denominator"]) == (universe_choice.KIND_COUNTED, 500)


def test_the_larger_denominator_wins_among_sources_of_the_matching_bracket(
    store: StudioStore, tmp_path: Path
) -> None:
    rows = _rows("edhrec", 3, 200, {"Filler 01": 1}) + _rows("archidekt", 3, 300, {"Filler 01": 1})
    _import_counted(store, _write_counted(tmp_path / "counted", rows))
    assert _choice(store, universe_source="auto")["source"] == "archidekt"


def test_auto_with_local_decks_counts_cards_in_no_deck_as_zero(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    _local_decks(store, 30)
    result = _compute(store, universe_source="auto")
    assert result["universe_choice"]["kind"] == universe_choice.KIND_LOCAL
    cards = _by_name(result)
    assert _component(cards["Filler 01"], "deck_universe")["status"] == strength.PRESENT
    zero = _component(cards["Filler 20"], "deck_universe")
    assert (zero["status"], zero["numerator"], zero["denominator"]) == (strength.ZERO_COUNT, 0, 30)


def test_an_explicit_counted_universe_that_is_not_stored_says_so(
    store: StudioStore, tmp_path: Path
) -> None:
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    result = _compute(store, universe_source="counted:edhrec:4")
    assert result["universe_choice"]["kind"] == universe_choice.KIND_NONE
    assert any("edhrec" in notice for notice in result["notices"])


def test_universe_source_values_and_stored_profiles_without_the_new_keys() -> None:
    assert strength.parse_universe_source("counted:edhrec:3") == ("counted", "edhrec", "3")
    for bad in ("counted:edhrec", "counted::3", "elsewhere", "counted:a:b:c"):
        assert strength.parse_universe_source(bad) is None
        with pytest.raises(ValueError, match="universe_source"):
            StrengthSettings(universe_source=bad)
    settings, ignored = StrengthSettings.from_stored({"weights": {"synergy": 2.0}})
    assert ignored == []
    assert settings.universe_source == "auto" and settings.require_commander_signal is True
    assert settings.min_coverage == 0.3
    with pytest.raises(ValueError, match="require_commander_signal"):
        StrengthSettings.from_dict({"require_commander_signal": "yes"})


def test_the_panel_texts_name_the_new_recommendations() -> None:
    panel = strength_view.presets()["panel"]
    assert isinstance(panel, dict)
    labels = panel["labels"]
    assert labels["universe_source"] == "Decklisten-Universum (empfohlen: automatisch)"
    assert "(empfohlen: an)" in labels["require_commander_signal"]
    choices = panel["choices"]["universe_source"]
    assert [item["value"] for item in choices if item["recommended"]] == ["auto"]
    assert "none" in [item["value"] for item in choices]
    help_text = panel["help"]["weights.deck_universe"]
    assert (
        help_text == "Wie stark die Verbreitung in gezählten Decklisten zählt. 0 schaltet sie ab."
    )
    assert labels["min_coverage"].startswith("Mindest-Datenlage")
    assert "keine Schwelle für den Anteil in Decks" in panel["help"]["min_coverage"]
    assert all(
        item["settings"]["require_commander_signal"] for item in strength_view.presets()["presets"]
    )  # type: ignore[attr-defined,index]


# ---------- signals listing, import-all, web, builder ----------


def test_completeness_lists_the_counted_universes_or_one_generic_missing_row(
    store: StudioStore, tmp_path: Path
) -> None:
    def layers() -> dict[str, import_all.LayerResult]:
        return {item["key"]: item for item in import_all.completeness(store, COMMANDER)[1]}

    assert layers()["signal:decklist_universe"]["status"] == "MISSING"
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    found = layers()
    assert "signal:decklist_universe" not in found
    edhrec = found["signal:decklist_universe:edhrec:3"]
    assert edhrec["rows"] == 4 and edhrec["status"] == "COMPLETE"  # every pool card has a count
    assert "signal:decklist_universe:archidekt:4" in found


def _all_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        commander=COMMANDER,
        inventory=str(_workbook(tmp_path / "cards.xlsx", _synthetic_cards())),
        scryfall=None,
        roles=None,
        rulings=None,
        from_repo=False,
        signals=None,
        decklists=None,
        decklist_format="edhrec",
        marks=None,
        expect_pool=None,
    )


def test_import_all_picks_up_the_counted_file_of_the_research_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    research = tmp_path / "research"
    _write_counted(research, _both())
    (research / "sub").mkdir()
    monkeypatch.setattr(import_all, "_RESEARCH", research)
    assert import_all.default_signal_folders() == [research]
    store = StudioStore.open(tmp_path / "all")
    result = import_all.run(_all_args(tmp_path), store)
    steps = {step["step"]: step for step in result["steps"]}
    assert steps["Signale research"]["status"] == "IMPORTED"
    assert "files_refused=0" in steps["Signale research"]["detail"]
    keys = {layer["key"]: layer for layer in result["layers"]}
    assert keys["signal:decklist_universe:edhrec:3"]["rows"] == 4
    monkeypatch.setattr(import_all, "_RESEARCH", tmp_path / "nowhere")
    assert import_all.default_signal_folders() == []


def test_import_all_reports_a_refused_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    research = tmp_path / "research"
    _write_counted(research, _rows("edhrec", 3, 200, {"Filler 01": 1}, own=100))
    monkeypatch.setattr(import_all, "_RESEARCH", research)
    store = StudioStore.open(tmp_path / "all")
    steps = {step["step"]: step for step in import_all.run(_all_args(tmp_path), store)["steps"]}
    assert "files_refused=1" in steps["Signale research"]["detail"]
    assert _stored(store) == 0


def test_the_web_lists_only_the_counted_universes_of_the_asked_commander(
    store: StudioStore, tmp_path: Path
) -> None:
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    client = TestClient(create_app(tmp_path / "studio"))
    body = client.get("/api/universe/counted", params={"commander": COMMANDER}).json()
    assert [item["value"] for item in body] == ["counted:archidekt:4", "counted:edhrec:3"]
    assert client.get("/api/universe/counted", params={"commander": OTHER}).json() == []
    sent = client.post(
        "/api/strength",
        json={"commander": COMMANDER, "settings": {"universe_source": "counted:edhrec:3"}},
        headers=HEADER,
    ).json()
    assert sent["universe_choice"]["label"].startswith("Gezählte Decklisten (Repo): EDHREC")
    assert sent["settings"]["universe_source"] == "counted:edhrec:3"


def test_the_builder_takes_the_same_universe_as_the_tier_list(
    store: StudioStore, tmp_path: Path
) -> None:
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    # The fixture holds a few local decks (below the minimum of 30): the tier list takes the
    # counted universe, so the builder shows it too.
    few = builder.pool_cards(store, [COMMANDER])
    assert universe_choice.local_deck_count(store, COMMANDER) < 30
    chosen = _choice(store)
    block = few["counted_universe"]
    assert chosen["kind"] == universe_choice.KIND_COUNTED
    assert isinstance(block, dict) and block["counted"] == chosen["counted"]
    assert block["denominator"] == chosen["denominator"] == 200
    # With 30 local decks the tier list takes them, and the builder shows no counted column.
    _local_decks(store, 30)
    assert _choice(store)["kind"] == universe_choice.KIND_LOCAL
    many = builder.pool_cards(store, [COMMANDER])
    assert "counted_universe" not in many
    assert all("counted" not in card for card in many["cards"])  # type: ignore[attr-defined]
    store.connection.execute("DELETE FROM commander_binding WHERE kind = 'corpus_deck'")
    store.connection.commit()
    chosen = builder.pool_cards(store, [COMMANDER])
    block = chosen["counted_universe"]
    assert isinstance(block, dict) and block["denominator"] == 200 and block["automatic"] is True
    assert block["label"] == "Gezählte Decklisten (Repo): EDHREC, Bracket 3, 200 Decks"
    by_name = {str(card["name"]): card for card in chosen["cards"]}  # type: ignore[attr-defined]
    assert by_name["Filler 01"]["counted"] == {"hits": 150, "denominator": 200, "share": 0.75}
    assert by_name["Filler 20"]["counted"]["hits"] == 0  # counted zero


# ---------- review residuals of the counted universes ----------


def test_a_wrong_commander_file_keeps_the_rows_stored_for_this_commander(
    store: StudioStore, tmp_path: Path
) -> None:
    _import_counted(store, _write_counted(tmp_path / "good", _both()))
    before = _stored(store)
    assert before > 0
    wrong = _write_counted(
        tmp_path / "wrong", _rows("edhrec", 3, 200, {"Filler 01": 9}, commander=OTHER)
    )
    report = _import_counted(store, wrong)  # built around OTHER, imported for COMMANDER
    refused = _file_report(report)["universes_refused"]
    assert [(item["reason"], item["rows_removed"]) for item in refused] == [
        (signals.COMMANDER_NOT_IN_EVERY_DECK, 0)
    ]
    assert _stored(store) == before
    # A file that names the commander but not in every deck still removes the stale rows.
    broken = _rows("edhrec", 3, 200, {"Filler 01": 150}, own=199)
    report = _import_counted(store, _write_counted(tmp_path / "broken", broken))
    assert _file_report(report)["universes_refused"][0]["rows_removed"] == 4


def test_the_tier_result_notices_unmatched_rows_of_the_counted_universe(
    store: StudioStore, tmp_path: Path
) -> None:
    clean = _import_counted(store, _write_counted(tmp_path / "clean", _both()))
    assert clean["rows_unmatched"] == 0
    assert not [n for n in _compute(store)["notices"] if "Zeilen" in n]
    rows = _rows("edhrec", 3, 200, {"Nowhere Card": 120, "Filler 01": 150}) + _rows(
        "archidekt", 4, 500, {"Filler 01": 100}
    )
    _import_counted(store, _write_counted(tmp_path / "unknown", rows))
    result = _compute(store)
    assert result["universe_choice"]["counted"] == "counted:edhrec:3"
    found = [n for n in result["notices"] if "Nowhere Card" in n]
    assert len(found) == 1 and "1 Zeilen" in found[0]
    # The universe that was not used does not add a notice.
    other = _compute(store, universe_source="counted:archidekt:4")
    assert not [n for n in other["notices"] if "Nowhere Card" in n]
    script = (Path(import_all.__file__).parent / "static" / "tierliste.js").read_text("utf-8")
    assert "result.notices" in script and "Index berechnet mit" in script


def test_the_builder_follows_the_strength_settings_of_the_tier_list(
    store: StudioStore, tmp_path: Path
) -> None:
    _import_counted(store, _write_counted(tmp_path / "counted", _both()))
    assert universe_choice.local_deck_count(store, COMMANDER) < 30

    default = builder.pool_cards(store, [COMMANDER])["counted_universe"]
    assert default["counted"] == "counted:edhrec:3"  # type: ignore[index]
    asked = StrengthSettings(universe_source="counted:archidekt:4")
    pool = builder.pool_cards(store, [COMMANDER], strength=asked)
    assert pool["counted_universe"]["counted"] == "counted:archidekt:4"  # type: ignore[index]
    assert pool["counted_universe"]["counted"] == _choice(store, universe_source="counted:archidekt:4")["counted"]  # type: ignore[index]
    off = builder.pool_cards(store, [COMMANDER], strength=StrengthSettings(universe_source="none"))
    assert "counted_universe" not in off
    client = TestClient(create_app(tmp_path / "studio"))
    body = client.get(
        "/api/pool",
        params={"commander": COMMANDER, "strength_universe": "counted:archidekt:4"},
    ).json()
    assert body["counted_universe"]["counted"] == "counted:archidekt:4"
    stale = client.get(
        "/api/pool", params={"commander": COMMANDER, "strength_universe": "garbage:x"}
    )
    assert stale.status_code == 200  # a stale remembered value is ignored
    assert stale.json()["counted_universe"]["counted"] == "counted:edhrec:3"
