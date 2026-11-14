"""One card into the working list of a variant or out of it (the tier list's "ins Deck"):
the builder's limits hold, the change is a draft and never a saved state, marks stay marks."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import builder
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.store import StudioStore
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill

STATIC = Path(builder.__file__).parent / "static"
FILLER_IN = "card:project:0100"  # in the saved deck
FILLER_OUT = "card:project:0169"  # legal, free, not in the saved deck (it holds 100..168)
FOREST = "card:project:0002"  # basic land, 2 in the saved deck
COMMANDER = "card:project:0001"


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _free(store: StudioStore, card_id: str) -> int:
    row = store.connection.execute(
        "SELECT available_lower_bound FROM inventory WHERE card_id = ?", (card_id,)
    ).fetchone()
    return int(row[0])


def _saved(store: StudioStore) -> str:
    cards = [RevisionCard(COMMANDER, 1, "commander")]
    cards += [RevisionCard(f"card:project:{100 + i:04d}") for i in range(69)]
    cards.append(RevisionCard(FOREST, 2))
    return create_revision(store, deck_id="test", name="Test", cards=cards)


def test_a_card_joins_the_working_list_as_a_draft_and_the_saved_state_stays(
    studio: StudioStore,
) -> None:
    revision = _saved(studio)
    assert builder.read_draft(studio, "test", "main") is None
    assert _free(studio, FILLER_OUT) >= 1
    result = builder.change_draft_card(studio, "test", "main", FILLER_OUT, 1)
    assert result == {
        "card_id": FILLER_OUT,
        "name": "Filler 69",
        "quantity": 1,
        "deck_cards": 73,
        "draft": True,
    }
    draft = builder.read_draft(studio, "test", "main")
    assert draft is not None and draft["base_revision_id"] == revision
    cards = {(c["card_id"], c["zone"]): c["quantity"] for c in draft["cards"]}  # type: ignore[attr-defined]
    assert cards[(FILLER_OUT, "main")] == 1
    assert cards[(COMMANDER, "commander")] == 1  # the commander row is kept
    assert len(cards) == 72  # commander, 69 fillers, the land row, the new card
    stored = studio.connection.execute(
        "SELECT COUNT(*) FROM deck_revision_card WHERE revision_id = ?", (revision,)
    ).fetchone()[0]
    assert stored == 71  # nothing was saved as a state


def test_a_second_change_builds_on_the_draft_and_a_removal_takes_one_copy(
    studio: StudioStore,
) -> None:
    _saved(studio)
    builder.change_draft_card(studio, "test", "main", FILLER_OUT, 1)
    out = builder.change_draft_card(studio, "test", "main", FILLER_IN, -1)
    assert (out["quantity"], out["deck_cards"]) == (0, 72)
    draft = builder.read_draft(studio, "test", "main")
    assert draft is not None
    ids = [c["card_id"] for c in draft["cards"]]  # type: ignore[attr-defined]
    assert FILLER_OUT in ids and FILLER_IN not in ids


def test_the_builders_copy_limits_hold(studio: StudioStore) -> None:
    _saved(studio)
    with pytest.raises(builder.DraftChangeRefused, match="schon im Deck"):
        builder.change_draft_card(studio, "test", "main", FILLER_IN, 1)
    with pytest.raises(builder.DraftChangeRefused, match="Commander"):
        builder.change_draft_card(studio, "test", "main", COMMANDER, 1)
    with pytest.raises(builder.DraftChangeRefused, match="nicht im Deck"):
        builder.change_draft_card(studio, "test", "main", FILLER_OUT, -1)
    # a basic land takes as many copies as are free, and no more
    free = _free(studio, FOREST)
    assert free >= 3
    for wanted in range(3, free + 1):
        assert builder.change_draft_card(studio, "test", "main", FOREST, 1)["quantity"] == wanted
    with pytest.raises(builder.DraftChangeRefused, match="Alle freien Kopien"):
        builder.change_draft_card(studio, "test", "main", FOREST, 1)
    # a card without a free copy is refused, whatever the list holds
    studio.connection.execute(
        "UPDATE inventory SET available_lower_bound = 0 WHERE card_id = ?", (FILLER_OUT,)
    )
    studio.connection.commit()
    with pytest.raises(builder.DraftChangeRefused, match="keine freie Kopie"):
        builder.change_draft_card(studio, "test", "main", FILLER_OUT, 1)
    assert builder.read_draft(studio, "test", "main") is not None


def test_unknown_deck_variant_card_and_step_are_refused(studio: StudioStore) -> None:
    _saved(studio)
    for deck, branch, card in [
        ("nope", "main", FILLER_OUT),
        ("test", "nope", FILLER_OUT),
        ("test", "main", "card:project:9999"),
    ]:
        with pytest.raises(KeyError):
            builder.change_draft_card(studio, deck, branch, card, 1)
    with pytest.raises(ValueError, match="delta"):
        builder.change_draft_card(studio, "test", "main", FILLER_OUT, 2)
    assert builder.read_draft(studio, "test", "main") is None


def test_the_endpoint_needs_the_marker_and_answers_in_german(studio: StudioStore) -> None:
    _saved(studio)
    assert studio.path is not None
    folder = studio.path.parent
    studio.close()
    marker = {"X-Studio": "1"}
    url = "/api/decks/test/branches/main/draft/card"
    with TestClient(create_app(folder)) as client:
        assert client.post(url, json={"card_id": FILLER_OUT}).status_code == 403
        added = client.post(url, json={"card_id": FILLER_OUT}, headers=marker)
        assert (added.status_code, added.json()["quantity"]) == (200, 1)
        again = client.post(url, json={"card_id": FILLER_OUT, "delta": 1}, headers=marker)
        assert again.status_code == 409
        assert "schon im Deck" in again.json()["detail"]
        assert (
            client.post(url, json={"card_id": "x", "delta": 1}, headers=marker).status_code == 404
        )
        assert (
            client.post(url, json={"card_id": FILLER_OUT, "delta": 5}, headers=marker).status_code
            == 422
        )
        gone = client.post(url, json={"card_id": FILLER_OUT, "delta": -1}, headers=marker)
        assert gone.json()["quantity"] == 0
        listed = client.get("/api/decks").json()
        assert listed[0]["branches"][0]["has_draft"] == 1


def test_a_deck_change_never_touches_marks_or_the_rating(studio: StudioStore) -> None:
    _saved(studio)
    builder.set_mark(studio, FILLER_OUT, favorite=True, excluded=False, note="merken")
    before = studio.connection.execute("SELECT * FROM card_mark ORDER BY card_id").fetchall()
    builder.change_draft_card(studio, "test", "main", FILLER_OUT, 1)
    after = studio.connection.execute("SELECT * FROM card_mark ORDER BY card_id").fetchall()
    assert [tuple(row) for row in before] == [tuple(row) for row in after]


def test_the_tier_page_offers_favourite_and_deck_and_the_builder_shows_the_tier() -> None:
    tier = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert '"Favorit / Deck"' in tier
    assert "/draft/card`" in tier
    assert "/favorite`" in tier and "/mark`" not in tier  # the page never sends a whole mark
    assert 'id="deck-select"' in (STATIC / "tierliste.html").read_text(encoding="utf-8")
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'id="f-tier"' in page and "Stufe zeigen" in page
    assert "studio.builder.show-tier" in app and "function tierMark" in app
    # shown messages of a refused change reach the page as written
    assert "im Deck" in (STATIC / "ui.js").read_text(encoding="utf-8")


def test_a_favourite_click_keeps_note_and_exclusion_also_for_an_unknown_mark(
    studio: StudioStore,
) -> None:
    """The tier list sends only the favorite. A note or exclusion set elsewhere (another
    commander's builder, another tab) survives, and a card without a mark gets a clean one."""
    builder.set_mark(studio, FILLER_OUT, favorite=False, excluded=True, note="keep")
    assert builder.set_favorite(studio, FILLER_OUT, True) == {
        "card_id": FILLER_OUT,
        "favorite": True,
        "excluded": True,
        "note": "keep",
    }
    assert builder.set_favorite(studio, FILLER_OUT, False)["note"] == "keep"
    assert builder.set_favorite(studio, FILLER_IN, True) == {
        "card_id": FILLER_IN,
        "favorite": True,
        "excluded": False,
        "note": "",
    }
    with pytest.raises(KeyError):
        builder.set_favorite(studio, "card:project:9999", True)
    assert studio.path is not None
    folder = studio.path.parent
    studio.close()
    with TestClient(create_app(folder)) as client:
        url = f"/api/cards/{FILLER_OUT}/favorite"
        assert client.put(url, json={"favorite": True}).status_code == 403
        done = client.put(url, json={"favorite": True}, headers={"X-Studio": "1"})
        assert (done.status_code, done.json()["note"], done.json()["excluded"]) == (
            200,
            "keep",
            True,
        )
        assert client.put(url, json={}, headers={"X-Studio": "1"}).status_code == 422
        gone = client.put(
            "/api/cards/nope/favorite", json={"favorite": True}, headers={"X-Studio": "1"}
        )
        assert gone.status_code == 404


def test_only_a_card_of_the_commanders_pool_joins_the_deck(studio: StudioStore) -> None:
    _saved(studio)
    names = {
        "Red Outsider": "Farbidentität",  # red card, the commander is green, white and blue
        "Banned Relic": "nicht erlaubt",
    }
    for name, reason in names.items():
        card_id = studio.connection.execute(
            "SELECT card_id FROM card_fact WHERE oracle_name = ?", (name,)
        ).fetchone()[0]
        with pytest.raises(builder.DraftChangeRefused, match=reason):
            builder.change_draft_card(studio, "test", "main", card_id, 1)
    studio.connection.execute("DELETE FROM inventory WHERE card_id = ?", (FILLER_OUT,))
    studio.connection.commit()
    with pytest.raises(builder.DraftChangeRefused, match="nicht in deiner Sammlung"):
        builder.change_draft_card(studio, "test", "main", FILLER_OUT, 1)
    assert builder.read_draft(studio, "test", "main") is None


def test_changes_at_the_same_time_lose_no_card(studio: StudioStore) -> None:
    """Four connections add different cards to the same working list at once."""
    import threading

    create_revision(
        studio,
        deck_id="test",
        name="Test",
        cards=[RevisionCard(COMMANDER, 1, "commander"), RevisionCard(FOREST, 2)],
    )
    assert studio.path is not None
    folder = studio.path.parent
    studio.close()
    wanted = [f"card:project:{100 + i:04d}" for i in range(40)]
    errors: list[BaseException] = []

    def work(part: list[str]) -> None:
        store = StudioStore.open(folder)
        try:
            for card_id in part:
                builder.change_draft_card(store, "test", "main", card_id, 1)
        except BaseException as error:  # reported by the assertion below
            errors.append(error)
        finally:
            store.close()

    threads = [threading.Thread(target=work, args=(wanted[i::4],)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    store = StudioStore.open(folder)
    draft = builder.read_draft(store, "test", "main")
    store.close()
    assert draft is not None
    stored = {c["card_id"] for c in draft["cards"]}  # type: ignore[attr-defined]
    assert set(wanted) <= stored


def test_a_refused_change_leaves_no_open_transaction(studio: StudioStore) -> None:
    _saved(studio)
    with pytest.raises(builder.DraftChangeRefused):
        builder.change_draft_card(studio, "test", "main", FILLER_IN, 1)
    assert not studio.connection.in_transaction
    assert builder.change_draft_card(studio, "test", "main", FILLER_OUT, 1)["quantity"] == 1
    assert not studio.connection.in_transaction
