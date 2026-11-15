"""Comparison groups that name the same set of source decks are one group (#1404 D10).
Denominators and figures of the groups that differ stay as they are. Synthetic data only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, catalog
from commander_lab.studio.web import create_app
from tests.unit.test_studio_round2 import _node
from tests.unit.test_studio_store import _write_csv

COMMANDER = ["Test Commander"]


def _cohort(store: StudioStore, folder: Path, name: str, decks: list[str]) -> None:
    path = _write_csv(folder / f"{name}.csv", [{"deck_id": deck} for deck in decks])
    catalog.import_cohort(store, path, cohort=name)


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)  # all: d1 d2 d3; community: d1 d2; turnier_cedh: d3; picked: d1
    return store


def test_groups_with_the_same_decks_are_one_group_and_the_others_do_not_change(
    studio: StudioStore, tmp_path: Path
) -> None:
    before = {row["cohort"]: row for row in builder.cohort_shapes(studio, COMMANDER)}
    assert set(before) == {"all", "community", "turnier_cedh", "picked"}
    assert all("same_as" not in row for row in before.values())  # nothing is identical yet
    sizes = builder.cohort_sizes(studio, COMMANDER)
    _cohort(studio, tmp_path, "every deck", ["d1", "d2", "d3"])  # the same decks as "all"
    _cohort(studio, tmp_path, "the pair", ["d2", "d1"])  # the same decks as "community"
    after = {row["cohort"]: row for row in builder.cohort_shapes(studio, COMMANDER)}
    assert list(after) == ["all", "community", "turnier_cedh", "picked"]  # no group twice
    assert after["all"]["same_as"] == ["every deck"]
    assert after["community"]["same_as"] == ["the pair"]
    for key in ("turnier_cedh", "picked"):
        assert after[key] == before[key]  # a group that differs keeps every number
    for key in ("all", "community"):
        assert {k: v for k, v in after[key].items() if k != "same_as"} == before[key]
    # the denominators of every group, merged or not, are still counted
    grown = builder.cohort_sizes(studio, COMMANDER)
    assert grown == {**sizes, "every deck": 3, "the pair": 2}


def test_the_first_group_in_order_names_the_merged_one_and_an_empty_group_is_never_merged(
    studio: StudioStore, tmp_path: Path
) -> None:
    _cohort(studio, tmp_path, "z copy of picked", ["d1"])
    _cohort(studio, tmp_path, "nothing", ["nope"])  # no known deck: the group does not exist
    shapes = {row["cohort"]: row for row in builder.cohort_shapes(studio, COMMANDER)}
    assert shapes["picked"]["same_as"] == ["z copy of picked"]
    assert "nothing" not in shapes
    # another commander with no decks has no groups to merge
    assert builder.cohort_shapes(studio, ["Nobody"]) == [
        {"cohort": "all", "decks": 0, "decks_counted": 0}
    ]


def test_the_route_and_the_pool_keep_the_denominators(studio: StudioStore, tmp_path: Path) -> None:
    _cohort(studio, tmp_path, "every deck", ["d1", "d2", "d3"])
    studio.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    shapes = client.get("/api/cohorts", params={"commander": "Test Commander"}).json()
    assert [row["cohort"] for row in shapes] == ["all", "community", "turnier_cedh", "picked"]
    assert shapes[0]["same_as"] == ["every deck"]
    pool = client.get("/api/pool", params={"commander": "Test Commander"}).json()
    assert pool["cohorts"]["every deck"] == pool["cohorts"]["all"] == 3  # the page merges them


def test_the_page_merges_groups_by_the_server_answer_and_names_them_once() -> None:
    script = """
const C = require('./cohorts.js');
const shapes = [
  {cohort: 'all', same_as: ['community', 'commander:chulane']},
  {cohort: 'bracket:3'},
  {cohort: 'source:edhrec', same_as: ['variant:core']},
];
const entries = [['all', 2617], ['community', 2617], ['bracket:3', 887], ['commander:chulane', 2617],
  ['source:edhrec', 1929], ['variant:core', 1929]];
const name = (key) => ({all: 'alle Quelldecks', community: 'Community'})[key] || key;
console.log(JSON.stringify({
  aliases: [...C.aliasMap(shapes)],
  visible: C.visible(entries, shapes).map((entry) => entry[0]),
  merged: C.label('all', shapes, name),
  one: C.label('source:edhrec', shapes, name),
  plain: C.label('bracket:3', shapes, name),
  older: C.visible(entries, undefined).length,
}));
"""
    found = json.loads(_node(script))
    assert found["visible"] == ["all", "bracket:3", "source:edhrec"]
    assert found["aliases"] == [
        ["community", "all"],
        ["commander:chulane", "all"],
        ["variant:core", "source:edhrec"],
    ]
    assert found["merged"] == "alle Quelldecks (zugleich Community und commander:chulane)"
    assert found["one"] == "source:edhrec (zugleich variant:core)"
    assert found["plain"] == "bracket:3"
    assert found["older"] == 6  # a server without the answer: nothing is hidden


def test_the_builder_page_loads_the_file_and_no_longer_guesses_from_key_prefixes() -> None:
    from commander_lab.studio.web import STATIC

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert html.index('src="cohorts.js"') < html.index('src="app.js"')
    source = (STATIC / "cohorts.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source and "style=" not in source
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'startsWith("commander:")' not in script  # the old guess from a key's prefix
    assert script.count("cohortLabel(") >= 3  # dropdown, frequencies table, comparison table
