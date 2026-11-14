"""Archetype labels (schema 15): free-form labels on cards and saved decks. They are the
Owner's own marks: a filter and a display, never an input of tier, index or layers.
All data here is synthetic."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    builder,
    create_revision,
    labels,
    strength_view,
)
from commander_lab.studio import evidence as evidence_model
from commander_lab.studio.store import DATABASE_NAME, SCHEMA_VERSION
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill
from tests.unit.test_studio_strength import COMMANDER, _import, _write_signals

HEADER = {"X-Studio": "1"}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    _write_signals(tmp_path / "signals")
    yield opened
    opened.close()


def _card(store: StudioStore, name: str) -> str:
    card_id = store.card_id_by_name(name)
    assert card_id is not None
    return str(card_id)


def test_the_schema_is_15_and_holds_the_label_tables() -> None:
    store = StudioStore.in_memory()
    tables = {
        str(row[0])
        for row in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert SCHEMA_VERSION == 15
    assert {"card_label", "deck_label"} <= tables


def test_labels_are_cleaned_and_unique_ignoring_case() -> None:
    assert labels.clean(["  Tokens ", "tokens", "Aufbau   Spiel", ""]) == ["Aufbau Spiel", "Tokens"]
    with pytest.raises(ValueError):
        labels.clean(["x" * (labels.MAX_LABEL_LENGTH + 1)])
    with pytest.raises(ValueError):
        labels.clean([f"l{i}" for i in range(labels.MAX_LABELS + 1)])
    with pytest.raises(ValueError):
        labels.clean(["<b>"])


def test_set_and_read_card_labels(store: StudioStore) -> None:
    forest = _card(store, "Forest")
    assert labels.set_card_labels(store, forest, ["Tokens", "Ramp-Plan"]) == ["Ramp-Plan", "Tokens"]
    assert labels.card_labels(store)[forest] == ["Ramp-Plan", "Tokens"]
    assert labels.set_card_labels(store, forest, ["Tokens"]) == ["Tokens"]
    assert labels.set_card_labels(store, forest, []) == []
    assert forest not in labels.card_labels(store)
    with pytest.raises(KeyError):
        labels.set_card_labels(store, "card:nope", ["x"])


def test_set_and_read_deck_labels(store: StudioStore) -> None:
    create_revision(store, deck_id="test", name="Test", cards=_deck())
    assert labels.set_deck_labels(store, "test", ["Spielerabend"]) == ["Spielerabend"]
    deck = next(d for d in builder.list_decks(store) if d["deck_id"] == "test")
    assert deck["labels"] == ["Spielerabend"]
    with pytest.raises(KeyError):
        labels.set_deck_labels(store, "nope", ["x"])


def test_pool_cards_carry_their_labels(store: StudioStore) -> None:
    forest = _card(store, "Forest")
    labels.set_card_labels(store, forest, ["Tokens"])
    pool = builder.pool_cards(store, ["Test Commander"])["cards"]
    assert isinstance(pool, list)
    by_id = {str(card["card_id"]): card for card in pool}
    assert by_id[forest]["labels"] == ["Tokens"]
    assert any(card["labels"] == [] for card in pool)


def test_labels_never_change_tier_index_layers_or_evidence(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)

    def snapshot() -> str:
        index = strength_view.compute(store, COMMANDER, StrengthSettings())
        layers = strength_view.rating_layers(store, COMMANDER, 4)
        evidence = evidence_model.pool_evidence(store, [COMMANDER])["cards"]
        return json.dumps([index, layers, evidence], sort_keys=True, default=str)

    before = snapshot()
    pool = builder.pool_cards(store, [COMMANDER])["cards"]
    assert isinstance(pool, list)
    for card in pool[:8]:
        labels.set_card_labels(store, str(card["card_id"]), ["Lieblingsplan", "Tokens"])
    create_revision(store, deck_id="test", name="Test", cards=_deck())
    labels.set_deck_labels(store, "test", ["Lieblingsplan"])
    after = snapshot()
    assert after == before
    assert "Lieblingsplan" not in after


def test_the_never_inputs_name_the_labels() -> None:
    assert "archetype_label" in evidence_model.TIER_POLICY["never_inputs"]  # type: ignore[operator]


def test_a_schema_14_database_is_lifted_on_open_and_keeps_every_row(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    opened = StudioStore.open(folder)
    _fill(opened, tmp_path)
    create_revision(opened, deck_id="test", name="Test", cards=_deck())
    builder.set_mark(opened, _card(opened, "Forest"), favorite=True, excluded=False, note="n")
    opened.close()
    path = folder / DATABASE_NAME
    connection = sqlite3.connect(path)
    connection.execute("DROP TABLE card_label")
    connection.execute("DROP TABLE deck_label")
    connection.execute("UPDATE meta SET value = '14' WHERE key = 'schema_version'")
    connection.commit()
    names_before = {
        str(r[0]) for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    marks_before = connection.execute("SELECT * FROM card_mark ORDER BY card_id").fetchall()
    connection.close()
    assert "card_label" not in names_before

    lifted = StudioStore.open(folder)
    version = lifted.connection.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()[0]
    assert version == str(SCHEMA_VERSION) == "15"
    assert lifted.count("card_label") == 0 and lifted.count("deck_label") == 0
    marks_after = lifted.connection.execute("SELECT * FROM card_mark ORDER BY card_id").fetchall()
    assert [tuple(r) for r in marks_after] == [tuple(r) for r in marks_before]
    labels.set_card_labels(lifted, _card(lifted, "Forest"), ["Tokens"])
    lifted.close()
    again = StudioStore.open(folder)  # idempotent: a second open changes nothing
    assert labels.card_labels(again)[_card(again, "Forest")] == ["Tokens"]
    again.close()


def test_the_routes(tmp_path: Path) -> None:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    forest = _card(opened, "Forest")
    create_revision(opened, deck_id="test", name="Test", cards=_deck())
    opened.close()
    client = TestClient(create_app(tmp_path / "studio"), headers=HEADER)
    done = client.put(f"/api/cards/{forest}/labels", json={"labels": ["Tokens", " Aufbau "]})
    assert done.status_code == 200 and done.json()["labels"] == ["Aufbau", "Tokens"]
    assert client.put("/api/cards/card:nope/labels", json={"labels": []}).status_code == 404
    assert client.put(f"/api/cards/{forest}/labels", json={"labels": ["<b>"]}).status_code == 422
    deck = client.put("/api/decks/test/labels", json={"labels": ["Spielerabend"]})
    assert deck.json()["labels"] == ["Spielerabend"]
    assert client.put("/api/decks/nope/labels", json={"labels": []}).status_code == 404
    pool = client.get("/api/pool", params={"commander": "Test Commander"}).json()
    assert next(c for c in pool["cards"] if c["card_id"] == forest)["labels"] == [
        "Aufbau",
        "Tokens",
    ]
    assert next(d for d in client.get("/api/decks").json() if d["deck_id"] == "test")["labels"] == [
        "Spielerabend"
    ]
    assert "Aufbau" in client.get("/api/labels").json()["known"]
