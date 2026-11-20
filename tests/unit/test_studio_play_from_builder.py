""" "Mit diesem Stand eine Partie spielen": the builder hands a saved revision to the Partien
page. All data here is synthetic."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, create_revision, play
from commander_lab.studio.decks import RevisionCard, lab_snapshot
from commander_lab.studio.web import STATIC, create_app
from tests.unit.test_studio_builder import _deck, _fill

ROOT = Path(__file__).resolve().parents[2]
PRECON = ROOT / "data/decks/precons/2011_counterpunch.json"
HEX64 = re.compile(r"[0-9a-f]{64}")


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    revision = create_revision(store, deck_id="test", name="Test", cards=_deck())
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    return client, str(getattr(revision, "revision_id", revision))


def test_the_table_lists_the_saved_revision_the_button_hands_over(tmp_path: Path) -> None:
    client, revision_id = _client(tmp_path)
    table = client.get("/api/table").json()
    revisions = [b["revision_id"] for deck in table["decks"] for b in deck["branches"]]
    assert revision_id in revisions  # the page preselects exactly this id


def test_the_builder_page_has_the_button_and_hands_over_only_a_saved_state() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'id="play-state"' in page
    assert "Mit diesem Stand eine Partie spielen" in page
    assert "partie.html?neu=1&revision=" in script
    # an unsaved draft is named on the button and never handed over
    assert "Erst als Stand speichern, dann spielen" in script
    assert "if (state.dirty || !state.baseRevision)" in script


def test_the_partie_page_reads_the_parameters() -> None:
    script = (STATIC / "partie.js").read_text(encoding="utf-8")
    address = "partie.html?neu=1&revision=rev%40test%2Fmain%2F1"
    query = parse_qs(urlparse(address).query)
    assert query == {"neu": ["1"], "revision": ["rev@test/main/1"]}
    assert 'query.get("neu") === "1"' in script
    assert 'query.get("revision")' in script
    assert "own.value = wantedRevision" in script
    # the parameters leave the address once the dialog is open, so a reload does not reopen it
    assert script.index("history.replaceState") < script.index("await newGame(query.get")


# --- the deck state of every seat in the log header (#1657) ------------------------------


def _snapshot_paths(tmp_path: Path) -> tuple[str, str, Path, Path, Path]:
    """Two saved revisions of one deck, the first written twice as a game snapshot."""
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    first = create_revision(store, deck_id="test", name="Test", cards=_deck())
    changed = [*_deck()[:-1], RevisionCard("card:project:0002", 28)]
    changed.append(RevisionCard("card:project:0003", 1))
    second = create_revision(store, deck_id="test", name="Test", cards=changed)
    paths = []
    for index, revision in enumerate((first, first, second)):
        path = tmp_path / f"own-{index}.json"
        path.write_text(json.dumps(lab_snapshot(store, revision)), encoding="utf-8")
        paths.append(path)
    store.close()
    return first, second, paths[0], paths[1], paths[2]


def _prepared(own: Path, **kwargs: object) -> play.PreparedGame:
    decks = play.load_decks([own, PRECON])
    return play.prepare_game(
        decks, seed=7, game_id="g", jar_sha256="0" * 64, qualification={}, **kwargs
    )  # type: ignore[arg-type]


def test_every_seat_of_the_header_names_its_deck_state(tmp_path: Path) -> None:
    first, _second, own, _again, _other = _snapshot_paths(tmp_path)
    prepared = _prepared(own)
    seats = prepared.header["seats"]
    assert isinstance(seats, list) and len(seats) == 2
    for row in seats:
        assert HEX64.fullmatch(str(row["deck_hash"]))
    # the own seat names the hash its scenario plays and the revision it was written from
    assert seats[0]["deck_hash"] == prepared.scenario.deck_hash
    assert seats[0]["studio_revision_id"] == first
    # a precon names no revision: none is guessed
    assert "studio_revision_id" not in seats[1]
    human = _prepared(
        own, human_seats=[0], decision_timeout_seconds=play.HUMAN_SEAT_TIMEOUT_SECONDS
    )
    human_seats = human.header["seats"]
    assert isinstance(human_seats, list)
    assert [row["pilot"] for row in human_seats] == ["Mensch", "KI"]
    assert [row["deck_hash"] for row in human_seats] == [row["deck_hash"] for row in seats]


def test_one_revision_is_one_deck_state_and_another_revision_another(tmp_path: Path) -> None:
    _first, _second, own, again, other = _snapshot_paths(tmp_path)
    hashes = [_prepared(path).header["seats"][0]["deck_hash"] for path in (own, again, other)]  # type: ignore[index]
    assert hashes[0] == hashes[1]  # written twice, the same state
    assert hashes[0] != hashes[2]  # one card changed, another state
    assert play.snapshot_deck_hash(own) == hashes[0]
    assert play.snapshot_deck_hash(tmp_path / "missing.json") is None
