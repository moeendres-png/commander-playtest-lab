"""Version comparison with counted deltas (#1414, #1404 option 8)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, deck_diff
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.web import create_app


def _store(tmp_path: Path) -> tuple[StudioStore, dict[str, str]]:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    ids = {
        str(row["oracle_name"]): str(row["card_id"])
        for row in store.connection.execute("SELECT card_id, oracle_name FROM card_fact")
    }
    return store, ids


def _commander(store: StudioStore) -> str:
    return str(
        store.connection.execute(
            "SELECT oracle_name FROM card_fact WHERE card_id = 'card:project:0001'"
        ).fetchone()[0]
    )


def test_diff_impact_counts_swaps_with_frequency_and_unknown(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    commander = _commander(store)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        db.execute(
            "INSERT INTO commander_combo(commander_name, ordinal, cards, num_decks, source_id) "
            "VALUES (?, 1, ?, 7, ?)",
            (commander, json.dumps(["Filler 01", "Swarm Rat"]), source_id),
        )
    cmd = RevisionCard("card:project:0001", 1, "commander")
    base = [cmd, RevisionCard(ids["Filler 01"]), RevisionCard(ids["Filler 02"])]
    target = [cmd, RevisionCard(ids["Filler 01"]), RevisionCard(ids["Swarm Rat"], 2)]
    diff = deck_diff.diff_impact(store, base, target)
    assert diff["schema"] == deck_diff.SCHEMA
    added = {item["name"]: item for item in diff["added"]}
    removed = {item["name"]: item for item in diff["removed"]}
    # Swarm Rat: in d1 and d3 of the three non-duplicate source decks (d4 duplicates d1).
    assert added["Swarm Rat"]["decks"] == 2
    assert added["Swarm Rat"]["of"] == 3
    # Filler 02: no source deck names it: unknown, never 0.
    assert removed["Filler 02"]["decks"] is None
    assert removed["Filler 02"]["of"] == 3
    assert diff["overlap"] == {
        "shared_slots": 2,
        "base_slots": 3,
        "target_slots": 4,
        "meaning": diff["overlap"]["meaning"],
    }
    assert diff["combo_delta"]["listed"] == 1
    assert diff["combo_delta"]["base_complete"] == 0
    assert diff["combo_delta"]["target_complete"] == 1
    assert diff["combo_delta"]["now_complete"] == [["Filler 01", "Swarm Rat"]]
    curve = diff["curve_deltas"]
    assert sum(v["base"] for v in curve.values()) == 2
    assert sum(v["target"] for v in curve.values()) == 3
    assert diff["cohort"] == {"key": "all", "decks": 3, "base_decks": 3, "small": True}
    # A group with its own denominator: picked holds d1 only.
    picked = deck_diff.diff_impact(store, base, target, cohort="picked")
    assert {i["name"]: (i["decks"], i["of"]) for i in picked["added"]} == {"Swarm Rat": (1, 1)}


def test_diff_impact_without_combo_list_is_unknown(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    cmd = RevisionCard("card:project:0001", 1, "commander")
    diff = deck_diff.diff_impact(
        store, [cmd, RevisionCard(ids["Filler 01"])], [cmd, RevisionCard(ids["Filler 03"])]
    )
    assert diff["combo_delta"]["listed"] == 0
    assert diff["combo_delta"]["base_complete"] is None
    assert diff["combo_delta"]["target_complete"] is None


def test_diff_route_passes_the_cohort(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    cmd = RevisionCard("card:project:0001", 1, "commander")
    revision = create_revision(
        store, deck_id="d", name="D", cards=[cmd, RevisionCard(ids["Filler 01"])]
    )
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [
        {"card_id": "card:project:0001", "quantity": 1, "zone": "commander"},
        {"card_id": ids["Swarm Rat"], "quantity": 1, "zone": "main"},
    ]
    response = client.post(
        "/api/diff", json={"base_revision_id": revision, "cards": cards, "cohort": "picked"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cohort"]["key"] == "picked"
    assert body["added"][0]["decks"] == 1
    assert body["added"][0]["of"] == 1


def test_different_commanders_are_never_mixed(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    commander = _commander(store)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        db.execute(
            "INSERT INTO commander_combo(commander_name, ordinal, cards, num_decks, source_id) "
            "VALUES (?, 1, ?, 7, ?)",
            (commander, json.dumps(["Filler 01", "Swarm Rat"]), source_id),
        )
    base = [
        RevisionCard("card:project:0001", 1, "commander"),
        RevisionCard(ids["Filler 01"]),
        RevisionCard(ids["Swarm Rat"]),
    ]
    target = [RevisionCard(ids["Filler 05"], 1, "commander"), RevisionCard(ids["Filler 01"])]
    diff = deck_diff.diff_impact(store, base, target)
    assert diff["commanders"]["same"] is False
    combo = diff["combo_delta"]
    assert combo["comparable"] is False
    # Each side against its own list: the base commander's list holds the complete combo,
    # the target commander has no list (unknown), and no transition is reported.
    assert combo["base_listed"] == 1 and combo["base_complete"] == 1
    assert combo["listed"] == 0 and combo["target_complete"] is None
    assert combo["now_complete"] == [] and combo["no_longer_complete"] == []
    removed = {item["name"]: item for item in diff["removed"]}
    # The removed card is counted against the base commander's source decks (2 of 3),
    # not against an empty pair group of both commanders.
    assert (removed["Swarm Rat"]["decks"], removed["Swarm Rat"]["of"]) == (2, 3)
