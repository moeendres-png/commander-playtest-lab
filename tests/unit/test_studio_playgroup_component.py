"""Playgroup atlas as a strength component: signal import and observed-correlation scoring.

All data here is synthetic. The atlas value is an observed correlation from other
players' games (win rate when a card was cast versus when it never left the library),
not a causal effect; it counts only from a minimum sample and shrunk towards zero.
The Owner's marks never enter the index.
"""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, builder, signals, strength, strength_view
from commander_lab.studio.strength import Observation, StrengthSettings
from tests.unit.test_studio_builder import _fill

COMMANDER = "Test Commander"

ATLAS_FIELDS = [
    "card_name",
    "fetch_status",
    "observed_winrate_gap_pp",
    "ci_95_lower_pp",
    "ci_95_upper_pp",
    "winrate_when_cast_pct",
    "winrate_when_cast_n",
    "winrate_when_in_library_pct",
    "winrate_when_in_library_n",
    "format_mode",
    "source_file",
    "retrieved_at_utc",
]


def _atlas_row(card: str, status: str, gap: object = "", n: object = "") -> dict[str, object]:
    return {
        "card_name": card,
        "fetch_status": status,
        "observed_winrate_gap_pp": gap,
        "ci_95_lower_pp": "",
        "ci_95_upper_pp": "",
        "winrate_when_cast_pct": "",
        "winrate_when_cast_n": n,
        "winrate_when_in_library_pct": "",
        "winrate_when_in_library_n": "",
        "format_mode": "multiplayer",
        "source_file": "playgroup_card_atlas.json",
        "retrieved_at_utc": "2026-11-12T00:00:00Z",
    }


def _write_atlas(folder: Path, rows: list[dict[str, object]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "playgroup_card_atlas_signals.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=ATLAS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    yield opened
    opened.close()


def _signal(
    store: StudioStore, card: str, signal: str = signals.SIGNAL_PLAYGROUP
) -> sqlite3.Row | None:
    return store.connection.execute(  # type: ignore[no-any-return]
        "SELECT * FROM card_signal WHERE commander_name = '' AND signal = ? AND card_name = ?",
        (signal, card),
    ).fetchone()


def _import(store: StudioStore, folder: Path) -> dict[str, object]:
    return signals.import_signals(store, folder, commander=COMMANDER)


# ---------- importer ----------


def test_import_stores_the_published_gap_with_its_sample(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "signals"
    alpha = _atlas_row("Alpha Card", "OK", gap=5.2, n=48149)
    _write_atlas(
        folder,
        [
            alpha,
            _atlas_row("Beta Card", "PARTIAL", gap=-1.9, n=30),
            _atlas_row("Gamma Card", "PARTIAL", gap=3.0, n=24),
            _atlas_row("Delta Card", "OK", gap="", n=100),
            _atlas_row("Epsilon Card", "NO_DATA"),
            _atlas_row("Zeta Card", "NOT_FOUND"),
            dict(alpha),  # the same card listed twice with the same figures
        ],
    )
    report = _import(store, folder)
    atlas = report["files"]["playgroup_card_atlas_signals"]  # type: ignore[index]
    assert atlas["status"] == "IMPORTED"
    assert atlas["rows_read"] == 7 and atlas["rows_written"] == 2
    assert atlas["skipped_reasons"] == {
        "SAMPLE_BELOW_MINIMUM": 1,
        "VALUE_NOT_PUBLISHED": 1,
        "FETCH_STATUS_NOT_AVAILABLE": 2,
        "DUPLICATE_SAME_FIGURES": 1,
    }
    row = _signal(store, "Alpha Card")
    assert row is not None
    # The published gap, no reconstructed numerator, the sample as the denominator.
    assert (row["value"], row["numerator"], row["denominator"]) == (5.2, None, 48149)
    beta = _signal(store, "Beta Card")
    assert beta is not None and beta["value"] == -1.9 and beta["denominator"] == 30
    for absent in ("Gamma Card", "Delta Card", "Epsilon Card", "Zeta Card"):
        assert _signal(store, absent) is None


def test_import_is_idempotent_and_the_file_is_optional(store: StudioStore, tmp_path: Path) -> None:
    folder = tmp_path / "signals"
    _write_atlas(folder, [_atlas_row("Alpha Card", "OK", gap=5.2, n=48149)])
    _import(store, folder)
    before = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    _import(store, folder)
    after = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    assert [tuple(row) for row in before] == [tuple(row) for row in after]

    empty = tmp_path / "empty"
    empty.mkdir()
    report = signals.import_signals(store, empty, commander=COMMANDER)
    atlas = report["files"]["playgroup_card_atlas_signals"]  # type: ignore[index]
    assert atlas["status"] == "ABSENT" and report["rows_written"] == 0


def test_import_rejects_an_atlas_file_without_its_columns(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    with (folder / "playgroup_card_atlas_signals.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["card_name", "fetch_status"])
        writer.writeheader()
        writer.writerow({"card_name": "Alpha Card", "fetch_status": "OK"})
    with pytest.raises(ValueError, match="missing column"):
        signals.import_signals(store, folder, commander=COMMANDER)


# ---------- pure scoring ----------


def _only_observed() -> StrengthSettings:
    weights = {name: 0.0 for name in strength.COMPONENTS}
    weights[strength.PLAYGROUP_OBSERVED] = 1.0
    return StrengthSettings(weights=weights, min_coverage=0.0, min_components=1)


def test_observed_gap_is_shrunk_by_its_sample_and_needs_the_minimum() -> None:
    observations = {
        "small": {strength.PLAYGROUP_OBSERVED: Observation(10.0, None, 25)},
        "large": {strength.PLAYGROUP_OBSERVED: Observation(10.0, None, 100)},
        "negative": {strength.PLAYGROUP_OBSERVED: Observation(-4.0, None, 100)},
        "thin": {strength.PLAYGROUP_OBSERVED: Observation(30.0, None, 24)},
        "no_sample": {strength.PLAYGROUP_OBSERVED: Observation(10.0)},
    }
    scored = strength.score_pool(_only_observed(), observations, {strength.PLAYGROUP_OBSERVED})

    def component(card: str) -> strength.ComponentResult:
        return next(
            item
            for item in scored[card]["components"]
            if item["component"] == strength.PLAYGROUP_OBSERVED
        )

    # The same published gap ranks higher on the larger sample: 10 * 25/50 = 5.0
    # against 10 * 100/125 = 8.0, and the negative gap ranks last.
    assert component("large")["percentile"] == 1.0
    assert component("small")["percentile"] == 0.5
    assert component("negative")["percentile"] == 0.0
    assert scored["large"]["index"] == 100.0 and scored["negative"]["index"] == 0.0
    # Below the minimum, or without a sample, the observation does not count at all.
    for card in ("thin", "no_sample"):
        result = component(card)
        assert result["status"] == strength.NO_VALUE and result["percentile"] is None
        assert scored[card]["index"] is None and scored[card]["tier"] == "U"
    # The breakdown keeps the published gap and its sample size next to the label.
    shown = component("small")
    assert shown["label"] == "Beobachtete Sieg-Korrelation (Playgroup)"
    assert shown["value"] == 10.0 and shown["denominator"] == 25
    assert shown["signal"] == "playgroup_observed_winrate_gap"


# ---------- store side ----------


def _by_name(result: strength_view.StrengthResult) -> dict[str, strength_view.StrengthCard]:
    return {card["name"]: card for card in result["cards"]}


def _component(card: strength_view.StrengthCard, name: str) -> strength.ComponentResult:
    return next(item for item in card["components"] if item["component"] == name)


def test_compute_reads_the_atlas_as_a_commander_independent_component(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "signals"
    _write_atlas(
        folder,
        [
            _atlas_row("Filler 01", "OK", gap=6.0, n=500),
            _atlas_row("Filler 02", "OK", gap=6.0, n=25),
        ],
    )
    _import(store, folder)
    result = strength_view.compute(store, COMMANDER, StrengthSettings())
    cards = _by_name(result)
    assert strength.PLAYGROUP_OBSERVED in result["collected"]
    strong = _component(cards["Filler 01"], strength.PLAYGROUP_OBSERVED)
    assert strong["status"] == strength.PRESENT
    assert strong["value"] == 6.0 and strong["denominator"] == 500
    edge = _component(cards["Filler 02"], strength.PLAYGROUP_OBSERVED)
    assert edge["status"] == strength.PRESENT and edge["denominator"] == 25
    # Same gap, smaller sample: the shrunk value ranks lower.
    assert (strong["percentile"] or 0) > (edge["percentile"] or 0)
    missing = _component(cards["Filler 03"], strength.PLAYGROUP_OBSERVED)
    assert missing["status"] == strength.NO_VALUE and missing["percentile"] is None


def test_marks_never_change_the_index_with_the_atlas_present(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "signals"
    _write_atlas(folder, [_atlas_row("Filler 01", "OK", gap=6.0, n=500)])
    _import(store, folder)
    before = strength_view.compute(store, COMMANDER, StrengthSettings())
    pool = builder.pool_cards(store, [COMMANDER])["cards"]
    assert isinstance(pool, list)
    target = next(card for card in pool if card["name"] == "Filler 01")
    builder.set_mark(
        store, str(target["card_id"]), favorite=True, excluded=True, note="mein Liebling"
    )
    after = strength_view.compute(store, COMMANDER, StrengthSettings())
    assert before == after


def test_presets_offer_the_component_with_its_observed_label() -> None:
    offered = {item["key"]: item for item in strength_view.presets()["components"]}  # type: ignore[union-attr]
    entry = offered[strength.PLAYGROUP_OBSERVED]
    assert "Beobachtete" in str(entry["label"]) and "Korrelation" in str(entry["label"])
    assert entry["default_weight"] == 1.0
    settings = StrengthSettings.from_dict({"weights": {strength.PLAYGROUP_OBSERVED: 2.5}})
    assert StrengthSettings.from_dict(settings.to_dict()) == settings
