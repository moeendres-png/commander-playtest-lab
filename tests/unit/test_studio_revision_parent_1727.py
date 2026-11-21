"""#1727: optimistic concurrency for saving a revision (``expected_parent``).

A client that sends ``expected_parent`` (the head of the target branch it last saw; ``null``
for a new branch) gets 409 when the head moved, and nothing is written: no revision, no branch
pointer, no deck row, the draft untouched. Old clients that leave the field out keep the old
behaviour. All data here is synthetic. A file of its own, as for other issue-bound Studio
checks (``test_studio_issue_1307.py``).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    RevisionCard,
    StudioStore,
    builder,
    create_revision,
    decks,
    import_all,
    importers,
    web,
)
from commander_lab.studio.decks import (
    NEW_BRANCH_EXISTS_MESSAGE,
    STALE_PARENT_MESSAGE,
    StaleParent,
    deck_hash,
    lab_snapshot,
)
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill, _insert_scryfall

MARKER = {"X-Studio": "1"}
STALE = "Zweig hat sich geändert; Entwurf ist veraltet"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        create_revision(store, deck_id="mein-deck", name="Mein Deck", cards=_deck()[:1])
    finally:
        store.close()
    return tmp_path / "studio"


def _json(cards: list[RevisionCard]) -> list[dict[str, object]]:
    return [{"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in cards]


def _rev_id(deck_id: str, cards: list[RevisionCard]) -> str:
    return f"{deck_id}@{deck_hash(decks._merge(cards))[:16]}"


def _state(folder: Path, deck_id: str = "mein-deck") -> dict[str, object]:
    """Everything a refused save must leave as it was."""
    store = StudioStore.open(folder)
    try:
        db = store.connection
        return {
            "branches": sorted(
                tuple(row)
                for row in db.execute(
                    "SELECT branch, revision_id FROM deck_branch WHERE deck_id = ?", (deck_id,)
                )
            ),
            "revisions": sorted(
                str(row[0])
                for row in db.execute(
                    "SELECT revision_id FROM deck_revision WHERE deck_id = ?", (deck_id,)
                )
            ),
            "revision_cards": db.execute("SELECT COUNT(*) FROM deck_revision_card").fetchone()[0],
            "drafts": sorted(
                tuple(row)
                for row in db.execute(
                    "SELECT branch, cards, base_revision_id, updated_at FROM deck_draft "
                    "WHERE deck_id = ?",
                    (deck_id,),
                )
            ),
            "decks": sorted(tuple(row) for row in db.execute("SELECT deck_id, name FROM deck")),
        }
    finally:
        store.close()


def _head(folder: Path, branch: str = "main", deck_id: str = "mein-deck") -> str | None:
    store = StudioStore.open(folder)
    try:
        return decks.branch_head(store.connection, deck_id, branch)
    finally:
        store.close()


def test_two_clients_on_the_same_head_the_second_gets_409_and_nothing_is_written(
    folder: Path,
) -> None:
    head0 = _head(folder)
    assert head0 is not None
    cards_a = _deck()
    cards_b = [*_deck()[:-1], RevisionCard("card:project:0002", 28)]
    url = "/api/decks/mein-deck/revisions"
    with TestClient(create_app(folder)) as client:
        saved_a = client.post(
            url, json={"cards": _json(cards_a), "expected_parent": head0}, headers=MARKER
        )
        assert saved_a.status_code == 200, saved_a.text
        rev_a = saved_a.json()["revision_id"]
        # client B still works on head0 and keeps a draft on main
        draft_url = "/api/decks/mein-deck/branches/main/draft"
        draft = {"cards": _json(cards_b[:10]), "base_revision_id": head0}
        assert client.put(draft_url, json=draft, headers=MARKER).status_code == 200
    before = _state(folder)
    with TestClient(create_app(folder)) as client:
        refused = client.post(
            url,
            json={"cards": _json(cards_b), "expected_parent": head0, "parent_revision_id": head0},
            headers=MARKER,
        )
    assert refused.status_code == 409
    assert refused.json()["detail"] == STALE_PARENT_MESSAGE
    assert STALE in refused.json()["detail"]
    assert "Traceback" not in refused.text
    assert _state(folder) == before
    assert _head(folder) == rev_a
    assert _rev_id("mein-deck", cards_b) not in before["revisions"]  # type: ignore[operator]
    assert before["drafts"]  # the draft was there and is still there
    # after reloading, B saves against the current head
    with TestClient(create_app(folder)) as client:
        again = client.post(
            url, json={"cards": _json(cards_b), "expected_parent": rev_a}, headers=MARKER
        )
        assert again.status_code == 200, again.text
        rev_b = again.json()["revision_id"]
    assert _head(folder) == rev_b
    assert _state(folder)["drafts"] == []
    store = StudioStore.open(folder)
    try:
        parent = store.connection.execute(
            "SELECT parent_revision_id FROM deck_revision WHERE revision_id = ?", (rev_b,)
        ).fetchone()[0]
    finally:
        store.close()
    assert parent == rev_a  # without parent_revision_id the expected head is the parent


def test_a_new_branch_with_the_name_of_an_existing_one_is_refused(folder: Path) -> None:
    url = "/api/decks/mein-deck/revisions"
    cards = _json(_deck())
    before = _state(folder)
    with TestClient(create_app(folder)) as client:
        taken = client.post(
            url, json={"cards": cards, "branch": "main", "expected_parent": None}, headers=MARKER
        )
        assert taken.status_code == 409
        assert taken.json()["detail"] == NEW_BRANCH_EXISTS_MESSAGE
        assert STALE in taken.json()["detail"]
        assert _state(folder) == before
        fresh = client.post(
            url, json={"cards": cards, "branch": "neu", "expected_parent": None}, headers=MARKER
        )
        assert fresh.status_code == 200, fresh.text
        second = client.post(
            url,
            json={"cards": _json(_deck()[:5]), "branch": "neu", "expected_parent": None},
            headers=MARKER,
        )
        assert second.status_code == 409
    assert _head(folder, "neu") == fresh.json()["revision_id"]


def test_an_old_client_without_the_field_still_moves_the_branch(folder: Path) -> None:
    head0 = _head(folder)
    url = "/api/decks/mein-deck/revisions"
    with TestClient(create_app(folder)) as client:
        first = client.post(url, json={"cards": _json(_deck())}, headers=MARKER)
        assert first.status_code == 200
        # unchecked as before, and the answer says the field was missing (#1727)
        assert first.json()["expected_parent_missing"] is True
        # stale parent, no expected_parent: moved unchecked as before #1727
        stale = client.post(
            url,
            json={"cards": _json(_deck()[:7]), "parent_revision_id": head0},
            headers=MARKER,
        )
        assert stale.status_code == 200
    assert _head(folder) == stale.json()["revision_id"]
    assert _head(folder) != first.json()["revision_id"]


def test_an_empty_expected_parent_is_a_422(folder: Path) -> None:
    before = _state(folder)
    with TestClient(create_app(folder)) as client:
        empty = client.post(
            "/api/decks/mein-deck/revisions",
            json={"cards": _json(_deck()), "expected_parent": ""},
            headers=MARKER,
        )
    assert empty.status_code == 422
    assert _state(folder) == before


def test_a_refused_save_with_an_unowned_card_writes_no_deck_state(folder: Path) -> None:
    """The one write before the check is the catalog row of a ``scryfall:`` card (idempotent);
    the revision, the branch and the draft stay as they were."""
    store = StudioStore.open(folder)
    try:
        _insert_scryfall(
            store, oracle_id="oracle-x1727", name="Outside Card", colors="G", type_line="Creature"
        )
        store.connection.commit()
    finally:
        store.close()
    before = _state(folder)
    cards = [*_json(_deck()[:-1]), {"card_id": "scryfall:oracle-x1727", "quantity": 1}]
    with TestClient(create_app(folder)) as client:
        refused = client.post(
            "/api/decks/mein-deck/revisions",
            json={"cards": cards, "expected_parent": "mein-deck@0000000000000000"},
            headers=MARKER,
        )
        assert refused.status_code == 409
        # the read caches stay right after the refused write
        listed = client.get("/api/decks").json()
    assert _state(folder) == before
    main = next(b for d in listed if d["deck_id"] == "mein-deck" for b in d["branches"])
    assert main["revision_id"] == _head(folder)


def test_check_and_write_share_one_write_lock(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Right after the head is read, a second connection tries to move the branch. It must be
    blocked; otherwise the save would overwrite that move unseen (lost update)."""
    store = StudioStore.open(folder)
    head0 = decks.branch_head(store.connection, "mein-deck", "main")
    other = create_revision(store, deck_id="mein-deck", name="x", cards=_deck()[:3], branch="x")
    store.close()
    store = StudioStore.open(folder)
    real_head = decks.branch_head
    intruder: dict[str, object] = {}

    def head_then_intrude(db: sqlite3.Connection, deck_id: str, branch: str) -> str | None:
        head = real_head(db, deck_id, branch)
        conn = sqlite3.connect(str(store.path), timeout=0)
        try:
            conn.execute(
                "UPDATE deck_branch SET revision_id = ? WHERE deck_id = ? AND branch = 'main'",
                (other, deck_id),
            )
            conn.commit()
            intruder["moved"] = True
        except sqlite3.OperationalError as error:
            conn.rollback()
            intruder["blocked"] = str(error)
        finally:
            conn.close()
        return head

    monkeypatch.setattr(decks, "branch_head", head_then_intrude)
    try:
        revision = create_revision(
            store, deck_id="mein-deck", name="x", cards=_deck(), expected_parent=head0
        )
    finally:
        store.close()
    monkeypatch.setattr(decks, "branch_head", real_head)
    assert "moved" not in intruder
    assert "locked" in str(intruder.get("blocked"))
    assert _head(folder) == revision


def test_must_be_new_refuses_an_existing_deck_and_writes_nothing(folder: Path) -> None:
    before = _state(folder)
    store = StudioStore.open(folder)
    try:
        with pytest.raises(StaleParent):
            create_revision(
                store, deck_id="mein-deck", name="Anderer Name", cards=_deck(), expected_parent=None
            )
        with pytest.raises(StaleParent):
            create_revision(
                store,
                deck_id="neues-deck",
                name="Neu",
                cards=_deck(),
                expected_parent="neues-deck@ffffffffffffffff",
            )
        # the write lock is given back at once, not only when the connection closes
        assert not store.connection.in_transaction
    finally:
        store.close()
    assert _state(folder) == before  # no deck row for "neues-deck", the name unchanged


def test_module_compile_refuses_a_stale_expected_parent(folder: Path) -> None:
    store = StudioStore.open(folder)
    try:
        full = create_revision(store, deck_id="mein-deck", name="Mein Deck", cards=_deck())
    finally:
        store.close()
    with TestClient(create_app(folder)) as client:
        seeded = client.post(
            "/api/decks/mein-deck/modules/seed",
            json={"cards": _json(_deck()), "core_name": "Kern", "package_name": "Paket"},
            headers=MARKER,
        )
        assert seeded.status_code == 200, seeded.text
        module_ids = [m["module_id"] for m in seeded.json()["modules"]]
        compile_url = "/api/decks/mein-deck/modules/compile"
        body = {"module_ids": module_ids, "save": True, "branch": "main"}
        before = _state(folder)
        stale = client.post(
            compile_url, json={**body, "expected_parent": "mein-deck@0"}, headers=MARKER
        )
        assert stale.status_code == 409
        assert STALE in stale.json()["detail"]
        assert _state(folder) == before
        # main already holds exactly the compiled list with no parent: the same save, not a
        # conflict (idempotent); a different list under "new branch" is refused
        same = client.post(compile_url, json={**body, "expected_parent": None}, headers=MARKER)
        assert same.status_code == 200, same.text
        assert _state(folder) == before
        store = StudioStore.open(folder)
        try:
            create_revision(store, deck_id="mein-deck", name="x", cards=_deck()[:5], branch="x2")
        finally:
            store.close()
        taken = client.post(
            compile_url, json={**body, "branch": "x2", "expected_parent": None}, headers=MARKER
        )
        assert taken.status_code == 409
        assert taken.json()["detail"] == NEW_BRANCH_EXISTS_MESSAGE
        ok = client.post(compile_url, json={**body, "expected_parent": full}, headers=MARKER)
        assert ok.status_code == 200, ok.text
        assert ok.json()["saved"] is True
        old_client = client.post(compile_url, json=body, headers=MARKER)
        assert old_client.status_code == 200
    assert _head(folder) == full


def test_new_deck_route_creates_main_as_a_new_branch(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``POST /api/decks`` reads a free id, then writes ``main`` as new: a parallel request that
    took the id in between gets 409, its ``main`` is not overwritten."""
    real = decks.branch_head
    sneaked: dict[str, str] = {}

    def taken_meanwhile(db: sqlite3.Connection, deck_id: str, branch: str) -> str | None:
        if deck_id == "spaet" and not sneaked:
            sneaked["rev"] = "spaet@aaaaaaaaaaaaaaaa"
            return sneaked["rev"]
        return real(db, deck_id, branch)

    monkeypatch.setattr(decks, "branch_head", taken_meanwhile)
    store = StudioStore.open(folder)
    try:
        commander = str(
            store.connection.execute(
                "SELECT card_id FROM card WHERE oracle_name = 'Test Commander'"
            ).fetchone()[0]
        )
    finally:
        store.close()
    with TestClient(create_app(folder)) as client:
        body = {"name": "Spaet", "commander_card_ids": [commander]}
        refused = client.post("/api/decks", json=body, headers=MARKER)
        assert refused.status_code == 409
        assert "gleichzeitig angelegt" in refused.json()["detail"]
        created = client.post("/api/decks", json=body, headers=MARKER)
        assert created.status_code == 200
    assert _state(folder, "spaet")["revisions"] == [created.json()["revision_id"]]


def test_cli_import_into_an_existing_branch_still_moves_it(folder: Path, tmp_path: Path) -> None:
    """The importers are Owner CLI commands that set a branch on purpose; they keep moving it
    unchecked (decision #1727; the missing parent link is a follow-up)."""
    store = StudioStore.open(folder)
    try:
        revision = create_revision(store, deck_id="mein-deck", name="Mein Deck", cards=_deck())
        snapshot = tmp_path / "snap.json"
        snapshot.write_text(json.dumps(lab_snapshot(store, revision)), encoding="utf-8")
        create_revision(store, deck_id="mein-deck", name="Mein Deck", cards=_deck()[:4])
        imported = importers.import_lab_deck_snapshot(
            store, snapshot, deck_id="mein-deck", name="Mein Deck", branch="main"
        )
    finally:
        store.close()
    assert imported["revision_id"] == revision
    assert _head(folder) == revision


def test_repo_seed_keeps_a_deck_created_since_its_check(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``import-all`` seeds ``main`` of a repo deck only while it is new; a deck created after
    its existence check is kept, the seed reports it as already present."""
    monkeypatch.setattr(
        decks, "repo_deck_file_for_commander", lambda *a, **k: Path("seed_deck_current.txt")
    )
    monkeypatch.setattr(decks, "resolve_repo_baseline_cards", lambda *a, **k: _deck())
    real = decks.branch_head
    monkeypatch.setattr(
        decks,
        "branch_head",
        lambda db, deck_id, branch: (
            "seed-deck-current@bbbbbbbbbbbbbbbb"
            if deck_id == "seed-deck-current"
            else real(db, deck_id, branch)
        ),
    )
    store = StudioStore.open(folder)
    try:
        assert builder.commander_identity(store, ["Test Commander"])
        result = import_all._seed_repo_deck(store, "Test Commander")
        assert result == {"seeded": 0, "already_present": 1}
        assert not store.connection.in_transaction
        monkeypatch.setattr(decks, "branch_head", real)
        assert import_all._seed_repo_deck(store, "Test Commander")["seeded"] == 1
    finally:
        store.close()
    assert _state(folder, "seed-deck-current")["branches"] == [
        ("main", _rev_id("seed-deck-current", _deck()))
    ]


def test_a_writer_waiting_for_the_lock_reads_the_new_head_and_gets_409(folder: Path) -> None:
    """Another process holds the write lock with an uncommitted move of ``main`` before the
    save starts. The save must wait for the lock (``BEGIN IMMEDIATE``), then see the moved head
    and refuse; a deferred ``BEGIN`` reads the old head and fails with "database is locked"."""
    store = StudioStore.open(folder)
    head0 = decks.branch_head(store.connection, "mein-deck", "main")
    other = create_revision(store, deck_id="mein-deck", name="x", cards=_deck()[:3], branch="x")
    path = str(store.path)
    store.close()
    intruder = sqlite3.connect(path, timeout=30, isolation_level=None)
    intruder.execute("BEGIN IMMEDIATE")
    intruder.execute(
        "UPDATE deck_branch SET revision_id = ? WHERE deck_id = 'mein-deck' AND branch = 'main'",
        (other,),
    )
    outcome: dict[str, object] = {}

    def save() -> None:
        writer = StudioStore.open(folder)
        try:
            outcome["rev"] = create_revision(
                writer, deck_id="mein-deck", name="x", cards=_deck(), expected_parent=head0
            )
        except BaseException as error:
            outcome["error"] = error
        finally:
            writer.close()

    thread = threading.Thread(target=save)
    thread.start()
    time.sleep(0.7)
    intruder.execute("COMMIT")
    intruder.close()
    thread.join(40)
    assert not thread.is_alive()
    assert isinstance(outcome.get("error"), StaleParent), outcome
    assert _head(folder) == other


def test_the_same_save_sent_twice_succeeds_twice_with_the_same_answer(folder: Path) -> None:
    head0 = _head(folder)
    url = "/api/decks/mein-deck/revisions"
    body = {"cards": _json(_deck()), "expected_parent": head0}
    draft_url = "/api/decks/mein-deck/branches/main/draft"
    with TestClient(create_app(folder)) as client:
        first = client.post(url, json=body, headers=MARKER)
        assert first.status_code == 200, first.text
        draft = {"cards": _json(_deck()[:10]), "base_revision_id": first.json()["revision_id"]}
        assert client.put(draft_url, json=draft, headers=MARKER).status_code == 200
        before = _state(folder)
        second = client.post(url, json=body, headers=MARKER)
        assert second.status_code == 200, second.text
        assert second.json() == first.json()
        # same content but a different parent is not the same save
        other_parent = client.post(
            url, json={**body, "parent_revision_id": "mein-deck@1111111111111111"}, headers=MARKER
        )
        assert other_parent.status_code == 409
    after = _state(folder)
    assert after["drafts"] == []  # the repeated save drops the draft as well
    assert {k: v for k, v in after.items() if k != "drafts"} == {
        k: v for k, v in before.items() if k != "drafts"
    }


def test_a_failing_draft_drop_after_the_commit_reports_the_saved_state(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head0 = _head(folder)
    url = "/api/decks/mein-deck/revisions"
    body = {"cards": _json(_deck()), "expected_parent": head0}
    real_drop = builder.drop_draft

    def locked(*_args: object, **_kwargs: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(builder, "drop_draft", locked)
    with TestClient(create_app(folder), raise_server_exceptions=False) as client:
        saved = client.post(url, json=body, headers=MARKER)
        assert saved.status_code == 200, saved.text
        assert saved.json()["draft_dropped"] is False
        assert "Stand gespeichert" in saved.json()["hinweis"]
        assert _head(folder) == saved.json()["revision_id"]
        monkeypatch.setattr(builder, "drop_draft", real_drop)
        retry = client.post(url, json=body, headers=MARKER)
        assert retry.status_code == 200, retry.text
        assert retry.json() == {"revision_id": saved.json()["revision_id"]}


def test_a_failure_in_the_middle_of_the_writes_leaves_nothing(folder: Path) -> None:
    before = _state(folder)
    store = StudioStore.open(folder)
    store.connection.execute(
        "CREATE TEMP TRIGGER fail_1727 BEFORE INSERT ON deck_branch "
        "BEGIN SELECT RAISE(ABORT, 'fail_1727'); END"
    )
    try:
        with pytest.raises(sqlite3.IntegrityError):
            create_revision(
                store, deck_id="mein-deck", name="x", cards=_deck(), expected_parent=_head(folder)
            )
        assert not store.connection.in_transaction
    finally:
        store.close()
    assert _state(folder) == before  # no revision, no cards, the branch unmoved


def test_a_busy_store_answers_503_not_500(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def busy(*_args: object, **_kwargs: object) -> str:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(web, "create_revision", busy)
    with TestClient(create_app(folder), raise_server_exceptions=False) as client:
        answer = client.post(
            "/api/decks/mein-deck/revisions",
            json={"cards": _json(_deck()), "expected_parent": None},
            headers=MARKER,
        )
    assert answer.status_code == 503
    assert answer.json()["detail"] == web.STORE_BUSY_MESSAGE
