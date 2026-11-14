"""With every layer weight at 0 the index does not depend on the layer data at all.

The default settings and the three presets keep every rating layer and the simulation out of the
index; the tier and the index of each card are the same with and without layer data.

All data here is synthetic.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, layers, layers_view, signals, strength, strength_view
from commander_lab.studio.strength import StrengthSettings
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_strength import COMMANDER, _write_signals

TEXTS = {
    "Filler 04": "Each opponent loses 1 life.",
    "Filler 05": "Whenever an opponent casts a spell, draw a card.",
    "Filler 06": "Counter target spell.",
}
ATLAS = {"Filler 01": 80.0, "Filler 02": 50.0, "Filler 03": 20.0}
PRESET_NAMES = ["Ausgewogen", "Commander-nah", "Turniernah"]


def _atlas(store: StudioStore, name: str, on_curve: float) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    store.connection.execute(
        "INSERT INTO playgroup_card_atlas(oracle_id, card_name, slug, on_curve_pct, "
        "on_curve_count, on_curve_denominator, drawn_to_played_pct, ever_drawn_n, first_cast_n, "
        "battlefield_survival_pct, reached_battlefield_n, still_on_board_at_end_n, source_id, "
        "created_at, updated_at) VALUES (?, ?, 'slug', ?, ?, 100, ?, 200, ?, ?, 100, ?, ?, "
        "'now', 'now')",
        (
            f"oracle-{name.casefold().replace(' ', '-')}",
            name,
            on_curve,
            round(on_curve),
            on_curve,
            round(2 * on_curve),
            on_curve,
            round(on_curve),
            source,
        ),
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    _write_signals(tmp_path / "signals")
    signals.import_signals(opened, tmp_path / "signals", commander=COMMANDER)
    for name, text in TEXTS.items():
        opened.connection.execute(
            "UPDATE scryfall_card SET oracle_text = ? WHERE oracle_id = ?",
            (text, f"oracle-{name.casefold().replace(' ', '-')}"),
        )
    for name, on_curve in ATLAS.items():
        _atlas(opened, name, on_curve)
    opened.connection.commit()
    yield opened
    opened.close()


def _all_settings() -> dict[str, StrengthSettings]:
    assert list(strength.PRESETS) == PRESET_NAMES
    return {"default": StrengthSettings(), **strength.PRESETS}


def _rows(store: StudioStore, settings: StrengthSettings) -> list[tuple[str, str, object]]:
    result = strength_view.compute(store, COMMANDER, settings)
    return [(card["card_id"], card["tier"], card["index"]) for card in result["cards"]]


def test_default_and_presets_give_every_layer_and_the_simulation_weight_zero() -> None:
    assert strength.LAYER_KEYS
    for label, settings in _all_settings().items():
        assert set(settings.layer_weights) == set(strength.LAYER_KEYS), label
        assert all(weight == 0 for weight in settings.layer_weights.values()), label
        assert settings.weights[strength.SIMULATION] == 0, label
        assert settings.active_layers() == (), label


def test_layer_data_does_not_change_tier_or_index_at_weight_zero(
    store: StudioStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The layer data exists: the page layers carry values for the cards with atlas or text data.
    page = strength_view.compute(store, COMMANDER, StrengthSettings())
    valued = [
        card["name"]
        for card in page["cards"]
        if any(item["status"] == layers.OK for item in card["layers"].values())
    ]
    assert {"Filler 01", "Filler 02", "Filler 03"} <= set(valued)
    with_layers = {label: _rows(store, s) for label, s in _all_settings().items()}
    assert all(any(tier != strength.TIER_UNKNOWN or index is not None for _, tier, index in rows)
               for rows in with_layers.values())  # fmt: skip

    # The layer source is made empty: no atlas record and no oracle text for any card.
    monkeypatch.setattr(layers_view, "atlas_records", lambda *args, **kwargs: {})
    monkeypatch.setattr(layers_view, "pool_texts", lambda *args, **kwargs: {})
    emptied = strength_view.compute(store, COMMANDER, StrengthSettings())
    assert not any(
        item["status"] == layers.OK for card in emptied["cards"] for item in card["layers"].values()
    )
    without_layers = {label: _rows(store, s) for label, s in _all_settings().items()}
    assert without_layers == with_layers
