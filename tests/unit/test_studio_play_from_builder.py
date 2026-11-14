""" "Mit diesem Stand eine Partie spielen": the builder hands a saved revision to the Partien
page. All data here is synthetic."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, create_revision
from commander_lab.studio.web import STATIC, create_app
from tests.unit.test_studio_builder import _deck, _fill


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
