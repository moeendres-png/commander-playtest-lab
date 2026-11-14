"""The Chulane rating rubric as a strength component (issue #1358).

The importer reads ``summary.csv`` of a ``chulane_rubric_<date>`` folder; the component uses
``(H_mean - 1) / 9`` as the 0..1 score directly (no percentile, no share scale) and is specific
to the commander. All data here is synthetic except the check of the real file layout.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

import pytest

from commander_lab.studio import (
    StudioStore,
    import_all,
    repo_import,
    research_import,
    signals,
    strength,
    strength_view,
)
from commander_lab.studio.store import DataClass, sha256_file
from commander_lab.studio.strength import Observation, StrengthSettings
from tests.unit.test_studio_builder import _fill

CHULANE = "Chulane, Teller of Tales"
COMMANDER = "Test Commander"
REAL_FOLDER = Path(__file__).resolve().parents[2] / "data" / "research" / "chulane_rubric_20261114"


def _summary(
    folder: Path, rows: list[tuple[str, float, float, int, int]], header: list[str] | None = None
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "summary.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header or list(research_import.RUBRIC_COLUMNS))
        for card, h_mean, h_sd, raters, anchor in rows:
            writer.writerow([card, h_mean, h_sd, raters, anchor, 1.0, 1.0, 1.0, 1.0, 0.0])
    return folder


ROWS = [
    ("Filler 00", 10.0, 0.0, 0, 1),
    ("Filler 01", 7.33, 0.58, 3, 0),
    ("Filler 02", 1.0, 0.0, 3, 0),
    ("Filler 03", 4.0, 1.0, 3, 0),
]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    yield opened
    opened.close()


def _stored(store: StudioStore, commander: str = CHULANE) -> list[tuple[str, str, float]]:
    return [
        (str(row[0]), str(row[1]), float(row[2]))
        for row in store.connection.execute(
            "SELECT signal, card_name, value FROM card_signal WHERE commander_name = ? "
            "AND signal LIKE 'rubric_%' ORDER BY signal, card_name",
            (commander,),
        )
    ]


# ---------- import ----------


def test_rubric_import_stores_values_source_and_sha_under_the_commander(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = _summary(tmp_path / "chulane_rubric_20261114", ROWS)
    report = research_import.import_rubric(store, folder)
    assert report["commander"] == CHULANE and report["rows_read"] == 4
    assert report["rows_written"] == 12 and report["rows_replaced"] == 0
    assert report["rows_unmatched"] == 0 and report["anchors"] == 1
    stored = _stored(store)
    assert ("rubric_h_mean", "Filler 01", 7.33) in stored
    assert ("rubric_h_sd", "Filler 01", 0.58) in stored
    assert ("rubric_raters", "Filler 00", 0.0) in stored  # an anchor has no rater
    source = store.connection.execute(
        "SELECT source_id, data_class, sha256, title FROM source WHERE source_id = ?",
        (report["source_id"],),
    ).fetchone()
    digest = sha256_file(folder / "summary.csv")
    assert source["sha256"] == digest == report["sha256"]
    assert source["data_class"] == DataClass.HEURISTIC_MODEL.value
    assert source["title"] == "chulane_rubric_20261114/summary.csv"
    used = {
        row[0]
        for row in store.connection.execute(
            "SELECT DISTINCT source_id FROM card_signal WHERE signal LIKE 'rubric_%'"
        )
    }
    assert used == {report["source_id"]}


def test_rubric_import_is_idempotent_and_replaces_only_its_own_scope(
    store: StudioStore, tmp_path: Path
) -> None:
    store.connection.execute(
        "INSERT INTO card_signal VALUES (?, 'edhrec_commander_inclusion', 'Filler 00', 0.5, 5, "
        "10, (SELECT source_id FROM source LIMIT 1))",
        (CHULANE,),
    )
    store.connection.execute(
        "INSERT INTO card_signal VALUES (?, 'rubric_h_mean', 'Filler 00', 5.0, NULL, NULL, "
        "(SELECT source_id FROM source LIMIT 1))",
        (COMMANDER,),
    )
    store.connection.commit()
    folder = _summary(tmp_path / "chulane_rubric_20261114", ROWS)
    research_import.import_rubric(store, folder)
    first = _stored(store)
    sources = store.count("source")
    again = research_import.import_rubric(store, folder)
    assert _stored(store) == first and store.count("source") == sources
    assert again["rows_replaced"] == 12 and again["rows_written"] == 12
    # a changed file replaces the rubric rows of the commander and nothing else
    changed = _summary(tmp_path / "chulane_rubric_20261114", [("Filler 01", 9.0, 0.0, 3, 0)])
    research_import.import_rubric(store, changed)
    assert [item for item in _stored(store) if item[0] == "rubric_h_mean"] == [
        ("rubric_h_mean", "Filler 01", 9.0)
    ]
    kept = store.connection.execute(
        "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? "
        "AND signal = 'edhrec_commander_inclusion'",
        (CHULANE,),
    ).fetchone()[0]
    assert kept == 1
    assert _stored(store, COMMANDER) == [("rubric_h_mean", "Filler 00", 5.0)]


def test_rubric_import_reports_unmatched_cards_and_refuses_bad_files(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = _summary(tmp_path / "chulane_rubric_20261114", [*ROWS, ("No Such Card", 5.0, 0, 3, 0)])
    report = research_import.import_rubric(store, folder)
    assert report["rows_unmatched"] == 1 and report["unmatched"] == ["No Such Card"]
    wrong = _summary(
        tmp_path / "chulane_rubric_20261115",
        ROWS,
        header=[*research_import.RUBRIC_COLUMNS[:-1], "X_mean"],
    )
    with pytest.raises(ValueError, match="unknown column layout"):
        research_import.import_rubric(store, wrong)
    for bad in (
        [("Filler 00", 11.0, 0.0, 3, 0)],  # outside 1..10
        [("Filler 00", 5.0, 0.0, 3, 0), ("filler 00", 6.0, 0.0, 3, 0)],  # a card twice
        [("Filler 00", 5.0, -1.0, 3, 0)],  # negative spread
        [("Filler 00", 5.0, 0.0, 3, 2)],  # not an anchor flag
    ):
        with pytest.raises(ValueError):
            research_import.read_rubric(_summary(tmp_path / "bad", bad) / "summary.csv")
    with pytest.raises(ValueError, match="no rating row"):
        research_import.read_rubric(_summary(tmp_path / "none", []) / "summary.csv")


def test_only_a_folder_in_the_explicit_table_is_imported_no_guessing(
    store: StudioStore, tmp_path: Path
) -> None:
    assert research_import.RUBRIC_COMMANDERS == {"chulane_rubric": CHULANE}
    stranger = _summary(tmp_path / "research" / "someone_rubric_20261114", ROWS)
    with pytest.raises(ValueError, match="not a known rubric folder"):
        research_import.import_rubric(store, stranger)
    _summary(tmp_path / "research" / "chulane_rubric_20261110", ROWS)
    newer = _summary(tmp_path / "research" / "chulane_rubric_20261114", ROWS)
    (tmp_path / "research" / "chulane_rubric_20261120").mkdir()  # no summary.csv: not a rubric
    assert research_import.find_rubric_folders(tmp_path / "research") == [newer]
    assert repo_import.RepoFiles.discover(tmp_path / "research").rubric_folders == [newer]
    assert research_import.find_rubric_folders(tmp_path / "missing") == []


def test_the_real_rubric_file_has_the_known_layout_and_every_row_is_valid() -> None:
    path = REAL_FOLDER / "summary.csv"
    rows = research_import.read_rubric(path)  # raises on an unknown layout or a bad row
    assert len(rows) == 922
    assert sum(1 for row in rows if row["anchor"] == 1) == 10
    assert research_import.rubric_folder_key(REAL_FOLDER) == (CHULANE, "20261114")
    with path.open(newline="", encoding="utf-8") as handle:
        assert tuple(csv.DictReader(handle).fieldnames or ()) == research_import.RUBRIC_COLUMNS


# ---------- component ----------


def test_rubric_value_is_h_minus_one_over_nine_and_unknown_outside_the_range() -> None:
    assert strength.rubric_value(1.0) == 0.0 and strength.rubric_value(10.0) == 1.0
    assert strength.rubric_value(5.5) == pytest.approx(0.5)
    for outside in (0.99, 10.01, float("nan"), float("inf")):
        assert strength.rubric_value(outside) is None


def _only_rubric(**extra: object) -> StrengthSettings:
    weights = {name: 0.0 for name in strength.COMPONENTS} | {strength.RUBRIC: 1.0}
    return StrengthSettings(weights=weights, min_coverage=0.0, min_components=1, **extra)  # type: ignore[arg-type]


def test_rubric_is_used_as_a_direct_score_not_a_percentile_rank() -> None:
    values = {"a": 0.0, "b": 0.05, "c": 0.9, "d": 1.0}
    observations = {key: {strength.RUBRIC: Observation(value)} for key, value in values.items()}
    scored = strength.score_pool(_only_rubric(), observations, {strength.RUBRIC})
    # a rank would spread these four over 0, 1/3, 2/3, 1: the magnitude is kept instead
    assert {key: item["index"] for key, item in scored.items()} == {
        "a": 0.0,
        "b": 5.0,
        "c": 90.0,
        "d": 100.0,
    }
    row = next(item for item in scored["b"]["components"] if item["component"] == strength.RUBRIC)
    assert row["percentile"] == 0.05 and row["status"] == strength.PRESENT
    # the same under a rank group, and independent of the share scale
    for extra in ({"share_scale": "rank"}, {"rank_group": "mana_band"}):
        again = strength.score_pool(_only_rubric(**extra), observations, {strength.RUBRIC})
        assert {key: item["index"] for key, item in again.items()} == {
            key: item["index"] for key, item in scored.items()
        }
    # a score outside 0..1 is unknown, never clipped to a bound
    bad = {"a": {strength.RUBRIC: Observation(1.5)}, "b": {strength.RUBRIC: Observation(0.5)}}
    scored = strength.score_pool(_only_rubric(), bad, {strength.RUBRIC})
    assert scored["a"]["index"] is None
    assert scored["b"]["index"] == 50.0


def test_rubric_is_commander_specific_for_the_commander_signal_rule() -> None:
    assert strength.RUBRIC in strength.COMMANDER_SPECIFIC
    assert strength.is_commander_specific(strength.RUBRIC, strength.COMBO_SPELLBOOK)
    observations = {"a": {strength.RUBRIC: Observation(0.8)}}
    collected = {strength.RUBRIC}
    scored = strength.score_pool(_only_rubric(), observations, collected)
    assert scored["a"]["tier"] != strength.TIER_UNKNOWN
    assert scored["a"]["reason"] == "ENOUGH_DATA"
    # the commander-independent global inclusion alone still gives no tier
    weights = {name: 0.0 for name in strength.COMPONENTS} | {strength.GLOBAL_INCLUSION: 1.0}
    other = StrengthSettings(weights=weights, min_coverage=0.0, min_components=1)
    only_global = {
        "a": {strength.GLOBAL_INCLUSION: Observation(0.5, 50, 100)},
        "b": {strength.GLOBAL_INCLUSION: Observation(0.1, 10, 100)},
    }
    blocked = strength.score_pool(other, only_global, {strength.GLOBAL_INCLUSION})
    assert blocked["a"]["tier"] == strength.TIER_UNKNOWN and blocked["a"]["reason"] == (
        strength.NO_COMMANDER_SIGNAL
    )


def test_global_inclusion_alone_gives_no_tier_under_the_default_settings() -> None:
    # DEFAULT weights and the default missing_value (lowest): an unlisted card gets a lowest
    # value, which must not count as commander-specific evidence
    settings = StrengthSettings()
    assert settings.require_commander_signal
    assert settings.missing_value[strength.COMMANDER_INCLUSION] == strength.MISSING_LOWEST
    observations: dict[str, dict[str, Observation]] = {}
    for n in range(10):
        observations[f"c{n}"] = {
            strength.COMMANDER_INCLUSION: Observation(0.9 - n * 0.05, 900 - n * 50, 1000),
            strength.BRACKET_INCLUSION: Observation(0.9 - n * 0.05, 900 - n * 50, 1000),
            strength.GLOBAL_INCLUSION: Observation(0.5, 500, 1000),
        }
    observations["only global"] = {strength.GLOBAL_INCLUSION: Observation(0.9, 900, 1000)}
    collected = {
        strength.COMMANDER_INCLUSION,
        strength.BRACKET_INCLUSION,
        strength.GLOBAL_INCLUSION,
    }
    scored = strength.score_pool(settings, observations, collected)
    odd = scored["only global"]
    assert odd["tier"] == strength.TIER_UNKNOWN and odd["reason"] == strength.NO_COMMANDER_SIGNAL
    assert odd["index"] is not None  # the lowest value still counts for the index
    assert scored["c0"]["reason"] == "ENOUGH_DATA"


def test_the_rubric_is_expected_only_for_commanders_with_a_rubric_file(
    store: StudioStore,
) -> None:
    assert "rubric_h_mean" in strength_view.expected_signals(CHULANE)
    assert "rubric_h_mean" not in strength_view.expected_signals(COMMANDER)
    assert "rubric_h_mean" not in strength_view.expected_signals()
    coverage = strength_view.signal_coverage(store, COMMANDER)
    assert "rubric_h_mean" not in coverage
    layers = import_all.layer_overview(store, COMMANDER)["layers"]
    assert not any(str(item["key"]).startswith("signal:rubric") for item in layers)


# ---------- store side ----------


def test_store_side_gives_the_rubric_to_its_commander_with_h_spread_and_raters(
    store: StudioStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(research_import, "RUBRIC_COMMANDERS", {"chulane_rubric": COMMANDER})
    folder = _summary(tmp_path / "chulane_rubric_20261114", ROWS)
    research_import.import_rubric(store, folder)
    weights = {name: 0.0 for name in strength.COMPONENTS} | {strength.RUBRIC: 1.0}
    settings = StrengthSettings(weights=weights, min_coverage=0.0, min_components=1)
    result = strength_view.compute(store, COMMANDER, settings)
    assert "rubric" in result["collected"]
    cards = {card["name"]: card for card in result["cards"]}

    def row(name: str) -> strength.ComponentResult:
        return next(c for c in cards[name]["components"] if c["component"] == strength.RUBRIC)

    assert row("Filler 01")["percentile"] == pytest.approx((7.33 - 1) / 9)
    assert cards["Filler 01"]["index"] == pytest.approx(round(100 * (7.33 - 1) / 9, 1))
    assert row("Filler 01")["note"] == "H 7,33 von 10, Streuung 0,58, 3 Bewerter"
    assert "fester Ankerwert" in row("Filler 00")["note"]
    assert row("Filler 00")["percentile"] == 1.0 and row("Filler 02")["percentile"] == 0.0
    # a card the file does not list is a missing observation, not 0
    unlisted = row("Filler 05")
    assert unlisted["percentile"] is None and unlisted["status"] == strength.NO_VALUE
    assert cards["Filler 05"]["index"] is None
    assert row("Filler 01")["signal"] == "rubric_h_mean"
    assert "rubric_h_mean" in strength_view.expected_signals(COMMANDER)
    coverage = strength_view.signal_coverage(store, COMMANDER)
    assert coverage["rubric_h_mean"]["pool_cards_with_value"] == 4
    assert "rubric_h_sd" not in coverage and "rubric_raters" not in coverage


def test_for_another_commander_the_rubric_is_a_missing_source_never_zero(
    store: StudioStore, tmp_path: Path
) -> None:
    research_import.import_rubric(store, _summary(tmp_path / "chulane_rubric_20261114", ROWS))
    assert _stored(store)  # the rows belong to Chulane
    weights = {**strength.DEFAULT_WEIGHTS, strength.RUBRIC: 6.0}
    heavy = StrengthSettings(weights=weights)
    without = StrengthSettings(weights={**strength.DEFAULT_WEIGHTS, strength.RUBRIC: 0.0})
    result = strength_view.compute(store, COMMANDER, heavy)
    assert "rubric" not in result["collected"]
    for card in result["cards"]:
        item = next(c for c in card["components"] if c["component"] == strength.RUBRIC)
        expected = strength.NOT_RANKED if card["tier"] == "N" else strength.NOT_COLLECTED
        assert item["status"] == expected and item["percentile"] is None
    # and it does not lower the coverage of any card: the source cannot exist for this commander
    reference = {c["name"]: c for c in strength_view.compute(store, COMMANDER, without)["cards"]}
    for card in result["cards"]:
        assert card["coverage"] == reference[card["name"]]["coverage"]
        assert card["index"] == reference[card["name"]]["index"]
        assert card["tier"] == reference[card["name"]]["tier"]


def test_rubric_rows_of_another_commander_are_not_read(store: StudioStore, tmp_path: Path) -> None:
    research_import.import_rubric(store, _summary(tmp_path / "chulane_rubric_20261114", ROWS))
    rows = store.connection.execute(
        "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal = ?",
        (COMMANDER, signals.SIGNAL_RUBRIC),
    ).fetchone()[0]
    assert rows == 0
    observed, exists = strength_view._rubric_observations(store, COMMANDER, {}, {}, {})
    assert observed == {} and exists is False


# ---------- defaults, presets and the rules that hold ----------


def test_every_preset_weights_the_rubric_and_keeps_simulation_and_layers_at_zero() -> None:
    for name, settings in strength.PRESETS.items():
        assert settings.weights[strength.RUBRIC] > 0, name
        assert settings.weights[strength.SIMULATION] == 0.0, name
        assert all(weight == 0.0 for weight in settings.layer_weights.values()), name
        assert settings.weights[strength.PLAYGROUP_OBSERVED] == 0.0, name
    assert strength.PRESETS["Ausgewogen"] == StrengthSettings()
    # "Ausgewogen": the rubric is about 30 % of the present weight for a typical Chulane card, which has
    # commander, bracket, deck universe and global inclusion (and no tournament or combo row)
    weights = StrengthSettings().weights
    usage = sum(
        weights[key]
        for key in (
            strength.COMMANDER_INCLUSION,
            strength.BRACKET_INCLUSION,
            strength.DECK_UNIVERSE,
            strength.GLOBAL_INCLUSION,
        )
    )
    assert usage == 8.0 and weights[strength.RUBRIC] == 3.5
    assert weights[strength.RUBRIC] / (usage + weights[strength.RUBRIC]) == pytest.approx(
        0.304, abs=1e-3
    )
    assert strength.DEFAULT_WEIGHTS[strength.RUBRIC] == 3.5
    assert strength_view.presets()["components"]  # the page lists the rubric like every component
    keys = [item["key"] for item in strength_view.presets()["components"]]  # type: ignore[attr-defined]
    assert strength.RUBRIC in keys


def test_the_default_cuts_fall_strictly_and_are_the_recorded_derivation() -> None:
    assert strength.DEFAULT_CUTS == {"S": 47.0, "A": 17.0, "B": 9.0, "C": 4.0}
    assert StrengthSettings().tier_cuts == strength.DEFAULT_CUTS


def test_owner_marks_never_move_a_card_with_the_rubric_in_the_index(
    store: StudioStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import builder

    monkeypatch.setattr(research_import, "RUBRIC_COMMANDERS", {"chulane_rubric": COMMANDER})
    research_import.import_rubric(store, _summary(tmp_path / "chulane_rubric_20261114", ROWS))
    before = strength_view.compute(store, COMMANDER, StrengthSettings())
    assert "rubric" in before["collected"]
    pool = builder.pool_cards(store, [COMMANDER])["cards"]
    assert isinstance(pool, list)
    for card in pool[:6]:
        builder.set_mark(
            store, str(card["card_id"]), favorite=True, excluded=True, note="mein Liebling"
        )
    after = strength_view.compute(store, COMMANDER, StrengthSettings())
    assert before == after
    # and no simulation value is read: the component stays not collected
    assert "simulation" not in after["collected"]


def test_the_rubric_weight_has_a_german_panel_text_with_the_recommendation() -> None:
    panel = strength_view.presets()["panel"]
    assert "(empfohlen: 3,5)" in panel["labels"]["weights.rubric"]  # type: ignore[index]
    text = panel["help"]["weights.rubric"]  # type: ignore[index]
    assert "drei Bewertern" in text and "ICC 0,94" in text and "0 schaltet" in text
    assert "3,5" in text
