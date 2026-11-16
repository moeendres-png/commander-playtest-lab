"""Guided cut to exactly 100 cards with locks (#1418)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, cut_lab
from commander_lab.studio.decks import RevisionCard
from commander_lab.studio.web import create_app

CMD = "card:project:0001"


def _store(tmp_path: Path) -> tuple[StudioStore, dict[str, str]]:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    ids = {
        str(row["oracle_name"]): str(row["card_id"])
        for row in store.connection.execute("SELECT card_id, oracle_name FROM card_fact")
    }
    return store, ids


def _draft(ids: dict[str, str]) -> list[RevisionCard]:
    cards = [RevisionCard(CMD, 1, "commander")]
    cards += [RevisionCard(ids[f"Filler {i:02d}"]) for i in range(1, 70)]
    cards.append(RevisionCard(ids["Swarm Rat"], 30))
    cards.append(RevisionCard(ids["Forest"], 20))
    return cards


def _total(cards: list[RevisionCard]) -> int:
    return sum(card.quantity for card in cards)


def _cut_one(cards: list[RevisionCard], card_id: str) -> list[RevisionCard]:
    out = []
    for card in cards:
        if card.card_id == card_id and card.zone == "main":
            if card.quantity > 1:
                out.append(RevisionCard(card.card_id, card.quantity - 1, card.zone))
            continue
        out.append(card)
    return out


def test_a_120_card_draft_reaches_exactly_100_without_suggesting_a_locked_card(
    tmp_path: Path,
) -> None:
    store, ids = _store(tmp_path)
    cards = _draft(ids)
    assert _total(cards) == 120
    locked = [ids[f"Filler {i:02d}"] for i in range(1, 11)] + [ids["Swarm Rat"]]
    suggested: set[str] = set()
    steps = 0
    while _total(cards) > 100:
        result = cut_lab.cut_suggestions(store, cards, locked=locked)
        assert result["excess"] == _total(cards) - 100
        suggestions = result["suggestions"]
        assert suggestions, "a draft over 100 with unlocked cards has suggestions"
        for item in suggestions:
            assert item["card_id"] not in locked
            assert item["card_id"] != CMD
            assert item["card_id"] != ids["Forest"]  # basics are tuned apart
        first = suggestions[0]
        suggested.add(str(first["card_id"]))
        cards = _cut_one(cards, str(first["card_id"]))
        steps += 1
    assert _total(cards) == 100
    assert steps == 20
    assert not suggested & set(locked)


def test_order_is_measured_frequency_unknown_apart_marks_never_count(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    # Swarm Rat is named by source decks (2 of 3); the fillers are not (unknown).
    cards = [RevisionCard(CMD, 1, "commander"), RevisionCard(ids["Swarm Rat"], 2)]
    cards += [RevisionCard(ids["Filler 03"]), RevisionCard(ids["Filler 02"])]
    with store.connection as db:
        db.execute(
            "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
            "VALUES (?, 1, 0, '', '2026-11-16')",
            (ids["Filler 02"],),
        )
    result = cut_lab.cut_suggestions(store, cards)
    order = [(item["name"], item["group"]) for item in result["suggestions"]]
    assert order == [("Swarm Rat", "known"), ("Filler 02", "unknown"), ("Filler 03", "unknown")]
    rat = result["suggestions"][0]
    assert (rat["decks"], rat["of"]) == (2, 3)
    assert result["suggestions"][1]["decks"] is None


def test_role_minimum_guardrail_moves_a_cut_back_and_deferred_go_last(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    oracle = str(
        store.connection.execute(
            "SELECT oracle_id FROM card_fact WHERE card_id = ?", (ids["Filler 02"],)
        ).fetchone()[0]
    )
    with store.connection as db:
        db.execute("INSERT INTO card_role VALUES (?, 'removal', ?)", (oracle, source_id))
    cards = [RevisionCard(CMD, 1, "commander")]
    cards += [RevisionCard(ids[f"Filler {i:02d}"]) for i in (2, 3, 4)]
    result = cut_lab.cut_suggestions(store, cards, role_minimums={"removal": 1})
    names = [item["name"] for item in result["suggestions"]]
    assert names[-1] == "Filler 02"
    last = result["suggestions"][-1]
    assert last["below_minimum"] == ["removal"]
    assert last["role_change"]["removal"] == {"before": 1, "after": 0, "minimum": 1}
    deferred = cut_lab.cut_suggestions(store, cards, deferred=[ids["Filler 03"]])
    assert deferred["suggestions"][-1]["name"] == "Filler 03"
    rejected = cut_lab.cut_suggestions(store, cards, rejected=[ids["Filler 03"]])
    assert "Filler 03" not in [item["name"] for item in rejected["suggestions"]]


def test_finish_patch_matches_the_target_list(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    start = [
        RevisionCard(CMD, 1, "commander"),
        RevisionCard(ids["Filler 01"]),
        RevisionCard(ids["Filler 02"]),
    ]
    target = [
        RevisionCard(CMD, 1, "commander"),
        RevisionCard(ids["Filler 01"]),
        RevisionCard(ids["Filler 05"]),
    ]
    result = cut_lab.finish(store, start, target)
    assert result["patch_text"].splitlines() == ["CUT 1 Filler 02", "ADD 1 Filler 05"]
    assert result["exactly_100"] is False
    # Applying the patch to the start list gives the target list.
    lines = result["patch_text"].splitlines()
    names = {name: card_id for name, card_id in ids.items()}
    applied = {(c.card_id, c.zone): c.quantity for c in start}
    for line in lines:
        word, count, name = line.split(" ", 2)
        key = (names[name], "main")
        applied[key] = applied.get(key, 0) + (int(count) if word == "ADD" else -int(count))
    assert {k: v for k, v in applied.items() if v} == {
        (c.card_id, c.zone): c.quantity for c in target
    }


def test_cut_lab_routes(tmp_path: Path) -> None:
    store, ids = _store(tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [{"card_id": CMD, "quantity": 1, "zone": "commander"}]
    cards += [
        {"card_id": ids[f"Filler {i:02d}"], "quantity": 1, "zone": "main"} for i in range(1, 5)
    ]
    body = client.post("/api/cut-lab", json={"cards": cards, "locked": [ids["Filler 01"]]}).json()
    assert body["schema"] == cut_lab.SCHEMA
    assert body["suggestions"]
    assert ids["Filler 01"] not in [item["card_id"] for item in body["suggestions"]]
    finish = client.post("/api/cut-lab/finish", json={"start": cards, "cards": cards[:-1]}).json()
    assert finish["patch_text"] == "CUT 1 Filler 04"
