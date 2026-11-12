"""Source data is bound to one commander; figures of two commanders are never mixed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import builder, importers
from commander_lab.studio.__main__ import main
from commander_lab.studio.evidence import pool_evidence
from commander_lab.studio.queries import corpus_inclusion
from commander_lab.studio.store import LEGACY_COMMANDER, StudioStore
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_store import _card_row, _register_row, _write_csv

FIRST = ["Test Commander"]
SECOND = ["Second Commander"]


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    """Three distinct decks of the first commander, then two decks of a second one."""
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)  # binds d1..d4 to the first commander
    register = _write_csv(
        tmp_path / "second_register.csv",
        [_register_row("s1", "community"), _register_row("s2", "community")],
    )
    cards = _write_csv(
        tmp_path / "second_cards.csv",
        [
            {**_card_row("s1", "Forest", 10), "oracle_id": "oracle-forest"},
            {**_card_row("s2", "Forest", 12), "oracle_id": "oracle-forest"},
            {**_card_row("s2", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
        ],
    )
    importers.import_corpus_register(store, register)
    importers.import_corpus_cards(store, cards)
    return store


def test_decks_without_a_commander_are_counted_for_nobody(studio: StudioStore) -> None:
    binding = builder.corpus_binding(studio, FIRST)
    assert binding == {
        "commander": FIRST,
        "bound_decks": 3,
        "other_commander_decks": 0,
        "unbound_decks": 2,
    }
    assert builder.cohort_sizes(studio, FIRST)["all"] == 3
    assert builder.cohort_sizes(studio, SECOND) == {"all": 0}
    # the new decks hold Forest twice, yet the first commander's figure does not move
    pool = builder.pool_cards(studio, FIRST)
    cards = {card["name"]: card for card in pool["cards"]}  # type: ignore[union-attr]
    assert cards["Forest"]["decks"]["all"] == 2
    assert pool["corpus_binding"] == binding


def test_two_commanders_keep_their_own_numerators_and_denominators(studio: StudioStore) -> None:
    assert studio.bind_unbound("Second Commander") == 2
    assert studio.bind_unbound("Second Commander") == 0  # idempotent
    first, second = builder.cohort_sizes(studio, FIRST), builder.cohort_sizes(studio, SECOND)
    assert (first["all"], first["community"]) == (3, 2)
    assert second == {"all": 2, "community": 2}
    rat_first = corpus_inclusion(studio, "Swarm Rat", FIRST)
    rat_second = corpus_inclusion(studio, "Swarm Rat", SECOND)
    assert (rat_first["hits"], rat_first["denominator"]) == (2, 3)
    assert (rat_second["hits"], rat_second["denominator"]) == (1, 2)
    # a deck must be bound to every named commander: no deck has both
    both = corpus_inclusion(studio, "Swarm Rat", [*FIRST, *SECOND])
    assert (both["hits"], both["denominator"], both["share"]) == (0, 0, None)
    assert builder.corpus_binding(studio, SECOND)["other_commander_decks"] == 3
    co = builder.card_cooccurrence(studio, "card:project:0007", SECOND)
    assert co["card_decks"] == 1
    shapes = {s["cohort"]: s["decks"] for s in builder.cohort_shapes(studio, FIRST)}
    assert shapes["all"] == 3
    names = {item["name"]: item for item in builder.list_commanders(studio)}
    assert names["Test Commander"]["source_decks"] == 3
    assert names["Second Commander"]["source_decks"] == 2
    assert names["Second Commander"]["in_collection"] is False


def test_no_commander_means_no_deck_figure(studio: StudioStore) -> None:
    assert builder.cohort_sizes(studio, []) == {}
    assert builder.cohort_shapes(studio, []) == []
    pool = builder.pool_cards(studio, [])
    assert pool["cohorts"] == {}
    assert all(card["decks"] == {} and card["edhrec"] is None for card in pool["cards"])  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="commander name"):
        studio.bind_unbound("  ")
    with pytest.raises(ValueError):
        builder.bound_to("no_such_kind", "x", FIRST)


def test_observations_and_simulations_follow_the_commander(studio: StudioStore) -> None:
    source = studio.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    with studio.connection as db:
        db.execute(
            "INSERT INTO observation(card_id, card_name, metric, cohort, value, numerator, "
            "denominator, data_class, source_id) VALUES ('card:project:0002', 'Forest', "
            "'inclusion_pct', 'edhrec:second', 90.0, 9, 10, 'ORIGINAL_SOURCE', ?)",
            (source,),
        )
        db.execute(
            "INSERT INTO simulation_run(run_id, deck_id, pod, engine_pin, pilot_policy, seeds, "
            "games_planned, games_completed, games_failed, wins_fractional, hand_dwell_status, "
            "source_id) VALUES ('run-second', 'x', 'pod', 'pin', 'tuned', '[]', 1, 1, 0, 0.0, "
            "'OK', ?)",
            (source,),
        )
        db.execute(
            "INSERT INTO simulation_card(run_id, card_id, card_name, games_completed, "
            "games_offered, games_cast_after_offer, games_rotted, offered_castable, cast_count) "
            "VALUES ('run-second', 'card:project:0002', 'Forest', 1, 1, 1, 0, 1, 1)"
        )
    studio.bind_unbound("Second Commander")
    forest = "card:project:0002"
    mine = builder.card_detail(studio, forest, SECOND)
    assert [row["cohort"] for row in mine["observations"]] == ["edhrec:second"]  # type: ignore[union-attr]
    assert len(mine["simulations"]) == 1  # type: ignore[arg-type]
    assert [run["run_id"] for run in builder.list_simulations(studio, SECOND)] == ["run-second"]
    other = builder.card_detail(studio, forest, FIRST)
    assert other["observations"] == [] and other["simulations"] == []
    assert builder.list_simulations(studio, FIRST) == []
    pool = {c["name"]: c for c in builder.pool_cards(studio, FIRST)["cards"]}  # type: ignore[union-attr]
    assert pool["Forest"]["edhrec"] is None
    evidence = pool_evidence(studio, FIRST)
    cards = {str(c["name"]): c for c in evidence["cards"]}  # type: ignore[union-attr]
    layers = cards["Forest"]["layers"]
    assert layers["observed_deck"]["edhrec"]["widest_inclusion"] is None  # type: ignore[index]
    assert layers["simulated_result"]["totals"] is None  # type: ignore[index]
    assert evidence["corpus_binding"]["bound_decks"] == 3  # type: ignore[index]


def test_a_store_from_before_the_binding_is_bound_to_its_single_commander(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "old")
    register = _write_csv(tmp_path / "register.csv", [_register_row("d1", "community")])
    importers.import_corpus_register(store, register)
    with store.connection as db:
        db.execute("UPDATE meta SET value = '8' WHERE key = 'schema_version'")
    store.close()
    reopened = StudioStore.open(tmp_path / "old")
    try:
        assert builder.cohort_sizes(reopened, [LEGACY_COMMANDER])["all"] == 1
        rows = reopened.connection.execute(
            "SELECT kind, key, commander_name, basis FROM commander_binding"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            ("corpus_deck", "d1", LEGACY_COMMANDER, "LEGACY_SINGLE_COMMANDER_STORE")
        ]
    finally:
        reopened.close()


def test_import_commands_bind_to_the_named_commander(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    first = _write_csv(tmp_path / "first.csv", [_register_row("d1", "community")])
    second = _write_csv(tmp_path / "second.csv", [_register_row("s1", "community")])
    assert main(["--data", str(data), "import-corpus-register", str(first)]) == 0
    assert json.loads(capsys.readouterr().out)["commander"] == LEGACY_COMMANDER
    named = ["--commander", "Second Commander"]
    assert main(["--data", str(data), "import-corpus-register", str(second), *named]) == 0
    assert json.loads(capsys.readouterr().out)["commander_bindings_added"] == 1
    assert main(["--data", str(data), "commanders"]) == 0
    listed = {item["name"]: item["source_decks"] for item in json.loads(capsys.readouterr().out)}
    assert listed == {LEGACY_COMMANDER: 1, "Second Commander": 1}
    assert main(["--data", str(data), "inclusion", "Forest", *named]) == 0
    assert json.loads(capsys.readouterr().out)["denominator"] == 1


def test_web_serves_deck_figures_only_for_a_named_commander(studio: StudioStore) -> None:
    assert studio.path is not None
    folder = studio.path.parent
    studio.bind_unbound("Second Commander")
    studio.close()
    with TestClient(create_app(folder)) as client:
        first = client.get("/api/pool", params={"commander": "Test Commander"}).json()
        assert first["cohorts"]["all"] == 3
        assert first["corpus_binding"]["other_commander_decks"] == 2
        shapes = client.get("/api/cohorts", params={"commander": "Second Commander"}).json()
        assert {shape["cohort"]: shape["decks"] for shape in shapes}["all"] == 2
        assert client.get("/api/evidence", params={"view": "global"}).json()["cohorts"] == {}
