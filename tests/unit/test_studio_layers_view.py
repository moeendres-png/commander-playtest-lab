"""Bewertungsebenen with a store: atlas matching, the tier endpoint, weight 0, settings texts.

All data here is synthetic. With every layer weight at 0 the tier result must be the same as
without layers, whatever data the layers hold.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, layers, layers_view, signals, strength, strength_view
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_strength import COMMANDER, _write_signals

HEADER = {"X-Studio": "1"}
TEXTS = {
    "Filler 04": "Each opponent loses 1 life.",
    "Filler 05": "Whenever an opponent casts a spell, draw a card.",
    "Filler 06": "Counter target spell.",
}


def _atlas(store: StudioStore, oracle_id: str, name: str, **fields: object) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    columns = ["oracle_id", "card_name", "slug", "source_id", "created_at", "updated_at", *fields]
    values = [oracle_id, name, "slug", source, "now", "now", *fields.values()]
    marks = ", ".join("?" for _ in columns)
    store.connection.execute(
        f"INSERT INTO playgroup_card_atlas({', '.join(columns)}) VALUES ({marks})", values
    )
    store.connection.commit()


def _full_row(on_curve: float, drawn: float, survive: float) -> dict[str, object]:
    return {
        "on_curve_pct": on_curve,
        "on_curve_count": round(on_curve),
        "on_curve_denominator": 100,
        "drawn_to_played_pct": drawn,
        "ever_drawn_n": 200,
        "first_cast_n": round(2 * drawn),
        "battlefield_survival_pct": survive,
        "reached_battlefield_n": 100,
        "still_on_board_at_end_n": round(survive),
    }


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
    opened.connection.commit()
    yield opened
    opened.close()


def _ids(store: StudioStore) -> dict[str, str]:
    rows = store.connection.execute("SELECT card_id, oracle_name FROM card_fact")
    return {str(row["oracle_name"]): str(row["card_id"]) for row in rows}


def _layers_of(store: StudioStore, settings: StrengthSettings | None = None) -> dict[str, dict]:
    result = strength_view.compute(store, COMMANDER, settings or StrengthSettings())
    return {card["name"]: card for card in result["cards"]}  # type: ignore[misc]


def test_an_atlas_row_belongs_to_the_card_with_its_oracle_id_then_its_name(
    store: StudioStore,
) -> None:
    _atlas(store, "oracle-filler-01", "A Different Spelling", **_full_row(10, 50, 50))
    _atlas(store, "no-such-oracle-id", "Filler 02", **_full_row(20, 60, 60))
    _atlas(store, "no-such-oracle-id-2", "filler 03", **_full_row(30, 70, 70))
    _atlas(store, "no-such-oracle-id-3", "Hidden Back", **_full_row(40, 80, 80))
    _atlas(store, "no-such-oracle-id-4", "Nobody At All", **_full_row(50, 90, 90))
    ids = _ids(store)
    wanted = [ids[name] for name in ("Filler 00", "Filler 01", "Filler 02", "Filler 03")]
    oracle = {
        card_id: str(row["oracle_id"])
        for card_id in wanted
        if (
            row := store.connection.execute(
                "SELECT oracle_id FROM card_fact WHERE card_id = ?", (card_id,)
            ).fetchone()
        )
    }
    claims = strength_view._claim_index(store, wanted)
    found = layers_view.atlas_records(store, oracle, claims)
    assert {name: ids[name] in found for name in ("Filler 00", "Filler 01", "Filler 02")} == {
        "Filler 00": False,  # only its back half was named: never a spelling of the card
        "Filler 01": True,  # by oracle id although the name differs
        "Filler 02": True,  # by exact oracle name
    }
    assert found[ids["Filler 03"]].on_curve_pct == 30.0  # casefolded name
    assert found[ids["Filler 01"]].on_curve_pct == 10.0


def test_the_oracle_id_wins_over_a_name_when_two_rows_resolve_to_one_card(
    store: StudioStore,
) -> None:
    _atlas(store, "oracle-filler-01", "Zzz Other Name", **_full_row(10, 50, 50))
    _atlas(store, "no-such-oracle-id", "Filler 01", **_full_row(99, 99, 99))
    ids = _ids(store)
    claims = strength_view._claim_index(store, [ids["Filler 01"]])
    found = layers_view.atlas_records(store, {ids["Filler 01"]: "oracle-filler-01"}, claims)
    assert found[ids["Filler 01"]].on_curve_pct == 10.0


def test_the_tier_result_carries_every_layer_per_card_and_a_summary(store: StudioStore) -> None:
    _atlas(store, "oracle-filler-01", "Filler 01", **_full_row(20, 50, 40))
    result = strength_view.compute(store, COMMANDER, StrengthSettings())
    cards = {card["name"]: card for card in result["cards"]}
    assert list(cards["Filler 01"]["layers"]) == list(layers.ALL_LAYER_KEYS)
    tempo = cards["Filler 01"]["layers"]["tempo"]
    assert (tempo["status"], tempo["n"], tempo["raw"]) == (layers.OK, 100, 0.2)
    assert cards["Filler 02"]["layers"]["tempo"]["status"] == layers.UNKNOWN
    assert cards["Filler 04"]["layers"]["pod_scaling"]["detail"]["class"] == layers.SCALES
    assert cards["Filler 05"]["layers"]["pod_scaling"]["detail"]["class"] == (
        layers.OPPONENT_TRIGGER
    )
    assert cards["Filler 06"]["layers"]["pod_scaling"]["detail"]["class"] == (layers.SINGLE_TARGET)
    summary = {item["key"]: item for item in result["layer_summary"]["layers"]}
    assert summary["tempo"]["with_value"] == 1
    assert summary["pod_scaling"]["pool_cards"] == len(result["cards"]) - 2  # commander, Forest
    assert result["layer_summary"]["weighted"] == []
    assert result["layer_summary"]["pod_size"] == 4


def test_the_commander_and_basic_lands_get_no_layer_value(store: StudioStore) -> None:
    cards = _layers_of(store)
    for name in ("Test Commander", "Forest"):
        assert cards[name]["tier"] == strength.TIER_NOT_RANKED
        for layer in layers.ALL_LAYER_KEYS:
            item = cards[name]["layers"][layer]
            assert (item["status"], item["reason"], item["value"]) == (
                layers.NOT_APPLICABLE,
                layers.NOT_RANKED,
                None,
            )


def _fingerprint(cards: dict[str, dict]) -> dict[str, tuple[object, ...]]:
    return {
        name: (
            card["tier"],
            card["index"],
            card["coverage"],
            card["present"],
            [row["component"] for row in card["components"]],
        )
        for name, card in cards.items()
    }


def test_with_every_layer_weight_zero_the_tier_result_is_the_same(store: StudioStore) -> None:
    before = _fingerprint(_layers_of(store))
    for index, name in enumerate(("Filler 01", "Filler 02", "Filler 04", "Filler 05")):
        oracle = f"oracle-{name.casefold().replace(' ', '-')}"
        _atlas(store, oracle, name, **_full_row(10 + 15 * index, 20 + 20 * index, 90 - 20 * index))
    after = _fingerprint(_layers_of(store))
    assert after == before
    assert all(len(components) == len(strength.COMPONENTS) for *_rest, components in after.values())
    bigger_pod = _fingerprint(_layers_of(store, StrengthSettings(pod_size=6)))
    assert bigger_pod == before  # the pod size is a display setting
    # and the tiers are not all one tier: the comparison saw real differences
    assert len({item[0] for item in before.values()}) > 1


def test_a_weighted_layer_joins_the_index_with_its_own_row(store: StudioStore) -> None:
    before = _layers_of(store)
    settings = StrengthSettings(layer_weights={"pod_scaling": 3.0})
    result = strength_view.compute(store, COMMANDER, settings)
    after = {card["name"]: card for card in result["cards"]}
    assert result["layer_summary"]["weighted"] == ["pod_scaling"]
    changed = [name for name in after if after[name]["index"] != before[name]["index"]]
    assert changed, "a weight on a layer with values must move the index of some card"
    row = after["Filler 04"]["components"][-1]
    assert (row["component"], row["label"], row["weight"], row["status"]) == (
        "layer_pod_scaling",
        "Großpod-Wirkung",
        3.0,
        strength.PRESENT,
    )
    assert row["percentile"] == 1.0  # the only SCALES card of the pool ranks first
    assert after["Test Commander"]["tier"] == strength.TIER_NOT_RANKED


def test_a_weighted_layer_without_any_value_is_noticed_and_changes_nothing(
    store: StudioStore,
) -> None:
    before = _fingerprint(_layers_of(store))
    result = strength_view.compute(store, COMMANDER, StrengthSettings(layer_weights={"tempo": 5.0}))
    assert "Tempo: keine Daten, Gewicht ohne Wirkung" in result["notices"]
    after = {card["name"]: card for card in result["cards"]}
    assert {
        name: (card["tier"], card["index"], card["coverage"], card["present"])
        for name, card in after.items()
    } == {name: item[:4] for name, item in before.items()}


def test_the_win_gap_column_is_the_index_component_not_a_second_reading(
    store: StudioStore,
) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    store.connection.execute(
        "INSERT INTO card_signal(commander_name, signal, card_name, value, numerator, "
        "denominator, source_id) VALUES ('', ?, 'Filler 01', 10.0, NULL, 100, ?)",
        (strength.signal_for(strength.PLAYGROUP_OBSERVED, "none"), source),
    )
    store.connection.commit()
    cards = _layers_of(store)
    gap = cards["Filler 01"]["layers"]["win_gap"]
    component = next(
        row for row in cards["Filler 01"]["components"] if row["component"] == "playgroup_observed"
    )
    assert (gap["status"], gap["n"], gap["raw"], gap["value"]) == (layers.OK, 100, 10.0, 8.0)
    assert component["denominator"] == gap["n"] and component["value"] == gap["raw"]
    assert strength.observed_gap(strength.Observation(10.0, None, 100)) == gap["value"]


# ---------- web ----------


@pytest.fixture
def client(store: StudioStore, tmp_path: Path) -> Iterator[TestClient]:
    _atlas(store, "oracle-filler-01", "Filler 01", **_full_row(20, 50, 40))
    store.close()
    with TestClient(create_app(tmp_path / "studio")) as test_client:
        yield test_client


def test_the_tier_endpoint_returns_layers_and_takes_the_layer_settings(
    client: TestClient,
) -> None:
    body = {
        "commander": COMMANDER,
        "settings": {"layer_weights": {"tempo": 2.0}, "pod_size": 6},
    }
    response = client.post("/api/strength", json=body, headers=HEADER)
    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["layer_weights"]["tempo"] == 2.0 and data["settings"]["pod_size"] == 6
    assert data["layer_summary"]["weighted"] == ["tempo"]
    first = next(card for card in data["cards"] if card["name"] == "Filler 04")
    assert first["layers"]["pod_scaling"]["detail"]["factor"] == "wirkt auf 5 Gegner"
    assert [row["component"] for row in first["components"]][-1] == "layer_tempo"
    for bad in (
        {"layer_weights": {"win_gap": 1}},
        {"pod_size": 9},
        {"layer_weights": {"tempo": -1}},
    ):
        refused = client.post(
            "/api/strength", json={"commander": COMMANDER, "settings": bad}, headers=HEADER
        )
        assert refused.status_code == 422, bad


def test_the_settings_panel_has_a_separate_group_with_the_recommendation_zero(
    client: TestClient,
) -> None:
    meta = client.get("/api/strength/presets").json()
    panel = meta["panel"]
    group = next(item for item in panel["groups"] if item["title"] == "Zusätzliche Ebenen")
    assert group["keys"] == [
        "layer_weights.pod_scaling",
        "layer_weights.tempo",
        "layer_weights.playability",
        "layer_weights.staying",
        "pod_size",
    ]
    for key in group["keys"][:4]:
        assert panel["labels"][key].endswith("(empfohlen: 0)"), key
    assert panel["labels"]["pod_size"] == "Pod-Größe (empfohlen: 4)"
    assert "nur die angezeigte Zahl" in panel["help"]["pod_size"]
    assert meta["recommended"]["layer_weights"] == {key: 0.0 for key in strength.LAYER_KEYS}
    assert [item["key"] for item in meta["layers"]] == list(layers.ALL_LAYER_KEYS)
    assert [item["weight_allowed"] for item in meta["layers"]] == [True, True, True, True, False]
    assert len(meta["presets"]) == 3
    for preset in meta["presets"]:
        assert preset["settings"]["layer_weights"] == meta["recommended"]["layer_weights"]
        assert preset["settings"]["weights"]["simulation"] == 0.0
    assert [item["key"] for item in meta["components"]] == list(strength.COMPONENTS)


def test_the_rating_layers_endpoint_serves_the_card_window(client: TestClient) -> None:
    response = client.get("/api/rating-layers", params={"commander": COMMANDER, "pod_size": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["pod_size"] == 3
    ids = {row["oracle_name"]: row["card_id"] for row in _ids_by_client(client)}
    assert (
        data["cards"][ids["Filler 04"]]["pod_scaling"]["detail"]["factor"] == "wirkt auf 2 Gegner"
    )
    assert data["cards"][ids["Filler 01"]]["tempo"]["n"] == 100
    assert [item["key"] for item in data["layers"]] == list(layers.ALL_LAYER_KEYS)
    assert (
        client.get("/api/rating-layers", params={"commander": COMMANDER, "pod_size": 7}).status_code
        == 422
    )
    assert (
        client.get("/api/rating-layers", params={"commander": "Nobody", "pod_size": 4}).status_code
        == 404
    )


def _ids_by_client(client: TestClient) -> list[dict[str, str]]:
    pool = client.get("/api/pool", params={"commander": COMMANDER}).json()
    return [{"oracle_name": card["name"], "card_id": card["card_id"]} for card in pool["cards"]]
