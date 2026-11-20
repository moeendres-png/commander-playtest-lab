"""Tests for the user-state export, import, start copies and the instance lock (#1668, K-2a).

All data is synthetic. No export file of a real store is, or may be, part of the repository.
"""

from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from commander_lab.studio import __main__ as studio_cli
from commander_lab.studio import cache, state_export
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.instance_lock import (
    LOCK_NAME,
    InstanceAlreadyRunning,
    InstanceLock,
)
from commander_lab.studio.state_export import (
    ExportBlocked,
    StateFileError,
    export_state,
    import_state,
    preflight,
    read_state,
    rotate_copies,
    verify_state_file,
    write_start_copy,
)
from commander_lab.studio.store import DataClass, StudioStore

SYNTHETIC_CARDS = {
    "c_lead": ("11111111-0000-4000-8000-000000000001", "Synthetic Leader"),
    "c_one": ("11111111-0000-4000-8000-000000000002", "Synthetic Spell One"),
    "c_two": ("11111111-0000-4000-8000-000000000003", "Synthetic Spell Två"),
    "c_land": ("11111111-0000-4000-8000-000000000004", "Synthetic Land"),
}


def _add_cards(store: StudioStore, source: str, *, without_oracle: tuple[str, ...] = ()) -> None:
    for card_id, (oracle, name) in SYNTHETIC_CARDS.items():
        store.connection.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, source_id) "
            "VALUES (?, ?, ?, 'G', ?)",
            (card_id, None if card_id in without_oracle else oracle, name, source),
        )


def _seed(folder: Path, *, without_oracle: tuple[str, ...] = ()) -> StudioStore:
    """A schema-21 store with every user table filled by synthetic rows."""
    store = StudioStore.open(folder)
    db = store.connection
    source = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title="synthetic source", sha256="a" * 64
    )
    _add_cards(store, source, without_oracle=without_oracle)
    revision = create_revision(
        store,
        deck_id="deck-a",
        name="Deck A",
        source_id=source,
        cards=[
            RevisionCard("c_lead", 1, "commander"),
            RevisionCard("c_one", 1, "main"),
            RevisionCard("c_land", 38, "main"),
        ],
    )
    child = create_revision(
        store,
        deck_id="deck-a",
        name="Deck A",
        parent_revision_id=revision,
        note="Tausch",
        branch="experiment",
        cards=[
            RevisionCard("c_lead", 1, "commander"),
            RevisionCard("c_two", 1, "main"),
            RevisionCard("c_land", 38, "main"),
        ],
    )
    db.execute(
        "INSERT INTO deck_draft(deck_id, branch, cards, base_revision_id, updated_at) "
        "VALUES ('deck-a', 'experiment', ?, ?, '2026-11-20T10:00:00Z')",
        (
            json.dumps(
                [
                    {"card_id": "c_lead", "quantity": 1, "zone": "commander"},
                    {"card_id": "c_one", "quantity": 1, "zone": "main"},
                ]
            ),
            child,
        ),
    )
    db.execute(
        "INSERT INTO deck_label(deck_id, label, created_at) VALUES ('deck-a', 'Ümlaut', 'x')"
    )
    db.execute(
        "INSERT INTO deck_primer(deck_id, content, updated_at) "
        "VALUES ('deck-a', 'Plan: früh Mana.\\nZeile 2', '2026-11-20T10:00:00Z')"
    )
    db.execute(
        "INSERT INTO deck_module(module_id, deck_id, name, role, sort_order, updated_at) "
        "VALUES ('m1', 'deck-a', 'Kern', 'core', 0, '2026-11-20T10:00:00Z')"
    )
    db.execute(
        "INSERT INTO deck_module_card(module_id, card_id, qty, is_commander) "
        "VALUES ('m1', 'c_lead', 1, 1)"
    )
    db.execute(
        "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
        "VALUES ('c_one', 1, 0, 'Liebling', '2026-11-20T10:00:00Z')"
    )
    db.execute("INSERT INTO card_label(card_id, label, created_at) VALUES ('c_one', 'Ramp', 'x')")
    db.execute(
        "INSERT INTO strength_profile(name, spec, created_at) "
        "VALUES ('profil', '{\"gewicht\": 0.5}', '2026-11-20T10:00:00Z')"
    )
    db.execute(
        "INSERT INTO universe_profile(profile_id, name, spec, created_at, version, updated_at) "
        "VALUES ('u1', 'Universum', '{\"n\": 3}', '2026-11-20T10:00:00Z', 2, '2026-11-20')"
    )
    db.commit()
    return store


def _dump(db: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    """Independent oracle: every user table as sorted rows, read with plain SQL."""
    out: dict[str, list[tuple[object, ...]]] = {}
    for table in (
        "source",
        "deck",
        "deck_revision",
        "deck_revision_card",
        "deck_branch",
        "deck_draft",
        "deck_label",
        "deck_primer",
        "deck_module",
        "deck_module_card",
        "card_mark",
        "card_label",
        "strength_profile",
        "universe_profile",
    ):
        query = f"SELECT * FROM {table}"
        if table == "source":  # the import's own stub source is not user state
            query += " WHERE source_id IN (SELECT source_id FROM deck_revision)"
        rows = [tuple(row) for row in db.execute(query)]
        if table == "deck_draft":
            rows = [(r[0], r[1], json.loads(r[2]), r[3], r[4]) for r in rows]
        out[table] = sorted(rows, key=repr)
    return out


def _roundtrip_equal(tmp_path: Path) -> bool:
    """Seed, export, import into a fresh folder, export again: True when the rows are equal
    (independent dump) and both exports hash alike."""
    source_store = _seed(tmp_path / "from")
    first = export_state(source_store, tmp_path / "a.json.gz")
    target = StudioStore.open(tmp_path / "to")
    import_state(target, tmp_path / "a.json.gz")
    second = export_state(target, tmp_path / "b.json.gz")
    rows_equal = _dump(source_store.connection) == _dump(target.connection)
    source_store.close()
    target.close()
    return rows_equal and first["content_sha256"] == second["content_sha256"]


def _rewrite(path: Path, change: Callable[[dict[str, object]], None]) -> None:
    with gzip.open(path, "rb") as handle:
        envelope = json.loads(handle.read())
    change(envelope)
    with gzip.open(path, "wb") as handle:
        handle.write(json.dumps(envelope).encode())


def _tamper_deck_name(envelope: dict[str, object]) -> None:
    envelope["content"]["tables"]["deck"][0]["name"] = "Manipuliert"  # type: ignore[index]


def _tampered_import_refused(tmp_path: Path) -> bool:
    store = _seed(tmp_path / "from")
    export_state(store, tmp_path / "t.json.gz")
    store.close()
    _rewrite(tmp_path / "t.json.gz", _tamper_deck_name)
    target = StudioStore.open(tmp_path / "to")
    try:
        import_state(target, tmp_path / "t.json.gz")
    except StateFileError:
        return True
    finally:
        target.close()
    return False


# -- format and round trip ---------------------------------------------------------------------


def test_roundtrip_is_equal_on_a_schema_21_fixture(tmp_path: Path) -> None:
    assert _roundtrip_equal(tmp_path)


def test_export_content_shape_and_card_identity(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    header = export_state(store, tmp_path / "out.json.gz")
    state = read_state(tmp_path / "out.json.gz")
    assert state.declared_sha256 == header["content_sha256"]
    assert state.source_schema_version == 21
    tables = state.content["tables"]
    assert isinstance(tables, dict)
    card_row = next(r for r in tables["deck_revision_card"] if r["card_id"] == "c_two")
    assert card_row["oracle_id"] == SYNTHETIC_CARDS["c_two"][0]
    assert card_row["name"] == "Synthetic Spell Två"
    assert (card_row["zone"], card_row["quantity"]) == ("main", 1)
    assert {r["revision_id"] for r in tables["deck_branch"]} == {
        r["revision_id"] for r in tables["deck_revision"]
    }
    draft = tables["deck_draft"][0]["cards"]
    assert draft[0]["oracle_id"] == SYNTHETIC_CARDS["c_lead"][0]
    assert state.content["not_in_schema"] == ["setting", "table_preset"]
    # no import table is part of the file
    assert set(tables) == {
        "source",
        "deck",
        "deck_revision",
        "deck_revision_card",
        "deck_branch",
        "deck_draft",
        "deck_label",
        "deck_primer",
        "deck_module",
        "deck_module_card",
        "card_mark",
        "card_label",
        "strength_profile",
        "universe_profile",
    }


def test_content_hash_ignores_the_creation_time(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    first = export_state(store, tmp_path / "1.json.gz")
    _rewrite(tmp_path / "1.json.gz", lambda e: e.update(created_at="1999-01-01T00:00:00Z"))
    assert read_state(tmp_path / "1.json.gz").declared_sha256 == first["content_sha256"]
    assert export_state(store, tmp_path / "2.json.gz")["content_sha256"] == first["content_sha256"]


def test_import_stubs_unknown_cards_and_marks_them(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    export_state(store, tmp_path / "x.json.gz")
    target = StudioStore.open(tmp_path / "to")
    result = import_state(target, tmp_path / "x.json.gz")
    assert result["card_stubs"] == 4
    row = target.connection.execute(
        "SELECT identity_evidence, oracle_id FROM card WHERE card_id = 'c_one'"
    ).fetchone()
    assert tuple(row) == ("state_import_stub", SYNTHETIC_CARDS["c_one"][0])
    assert (
        target.connection.execute(
            "SELECT value FROM meta WHERE key = ?", (state_export.META_IMPORT_KEY,)
        ).fetchone()[0]
        == result["content_sha256"]
    )


def test_import_refuses_a_store_that_has_user_state(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    export_state(store, tmp_path / "x.json.gz")
    with pytest.raises(StateFileError, match="schon Nutzerdaten"):
        import_state(store, tmp_path / "x.json.gz")


def test_import_refuses_a_conflicting_oracle_id_and_rolls_back(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    export_state(store, tmp_path / "x.json.gz")
    target = StudioStore.open(tmp_path / "to")
    src = target.register_source(data_class=DataClass.UNKNOWN, title="t", sha256="b" * 64)
    target.connection.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, source_id) "
        "VALUES ('c_one', 'other-oracle', 'Synthetic Spell One', 'G', ?)",
        (src,),
    )
    target.connection.commit()
    with pytest.raises(StateFileError, match="es wird nicht geraten"):
        import_state(target, tmp_path / "x.json.gz")
    assert target.connection.execute("SELECT COUNT(*) FROM deck").fetchone()[0] == 0


def test_import_under_cache_check_mode_declares_its_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache, "CHECK", True)
    store = _seed(tmp_path / "data")
    export_state(store, tmp_path / "x.json.gz")
    target = StudioStore.open(tmp_path / "to")
    import_state(target, tmp_path / "x.json.gz")
    assert target.connection.execute("SELECT COUNT(*) FROM deck_revision").fetchone()[0] == 2


def test_verify_reports_rows_per_table_and_sha(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    export_state(store, tmp_path / "x.json.gz")
    report = verify_state_file(tmp_path / "x.json.gz")
    assert report["sha_ok"] is True
    rows = report["rows"]
    assert isinstance(rows, dict)
    assert rows["deck_revision"] == 2 and rows["deck_draft"] == 1 and rows["card_label"] == 1


def test_wrong_format_and_garbage_are_refused(tmp_path: Path) -> None:
    (tmp_path / "junk.json.gz").write_bytes(b"not gzip")
    with pytest.raises(StateFileError, match="keine lesbare"):
        read_state(tmp_path / "junk.json.gz")
    store = _seed(tmp_path / "data")
    export_state(store, tmp_path / "x.json.gz")
    _rewrite(tmp_path / "x.json.gz", lambda e: e.update(format="studio-user-state-9"))
    with pytest.raises(StateFileError, match="unbekanntes Format"):
        read_state(tmp_path / "x.json.gz")


def test_unknown_table_in_the_file_is_refused_not_dropped(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    export_state(store, tmp_path / "x.json.gz")

    def add_table(envelope: dict[str, object]) -> None:
        content = envelope["content"]
        content["tables"]["setting"] = [{"key": "k"}]  # type: ignore[index]
        envelope["content_sha256"] = state_export.content_sha256(content)

    _rewrite(tmp_path / "x.json.gz", add_table)
    with pytest.raises(StateFileError, match="ohne Ziel"):
        verify_state_file(tmp_path / "x.json.gz")


# -- no oracle_id: stop with the list ----------------------------------------------------------


def test_a_referenced_card_without_oracle_id_stops_the_export_with_a_list(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data", without_oracle=("c_one",))
    out = tmp_path / "out.json.gz"
    with pytest.raises(ExportBlocked) as caught:
        export_state(store, out)
    assert not out.exists()
    assert not list(tmp_path.glob("*.tmp"))
    reasons = {(b["table"], b["card_id"], b["reason"]) for b in caught.value.blocked}
    assert ("deck_revision_card", "c_one", "no_oracle_id") in reasons
    assert ("deck_draft", "c_one", "no_oracle_id") in reasons
    assert ("card_mark", "c_one", "no_oracle_id") in reasons


def test_preflight_counts_collection_cards_without_oracle_id_n_of_n(tmp_path: Path) -> None:
    store = _seed(tmp_path / "data")
    source = store.register_source(data_class=DataClass.UNKNOWN, title="inv", sha256="c" * 64)
    store.connection.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, source_id) "
        "VALUES ('c_free', NULL, 'Synthetic Free', 'G', ?)",
        (source,),
    )
    for card_id in ("c_one", "c_free"):
        store.connection.execute(
            "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
            "available_lower_bound, quantity_exact, source_id) VALUES (?, 1, 1, 0, 1, 1, ?)",
            (card_id, source),
        )
    store.connection.commit()
    report = preflight(store)
    assert report.collection_total == 2
    assert [m["card_id"] for m in report.collection_missing] == ["c_free"]
    # c_free is in no deck, mark or draft: it does not block
    assert report.ok


def test_a_card_without_oracle_id_stops_the_start_copy_and_keeps_older_copies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "data"
    store = _seed(folder)
    first = write_start_copy(store, folder)
    store.connection.execute("UPDATE card SET oracle_id = NULL WHERE card_id = 'c_one'")
    store.connection.commit()
    store.close()
    state_export.start_copy_best_effort(folder)
    assert "nicht angelegt" in capsys.readouterr().err
    assert [p.name for p in (folder / "state-exports").iterdir()] == [first.name]


# -- rotation and start copies -----------------------------------------------------------------


def _write_copies(folder: Path, count: int) -> list[str]:
    store = StudioStore.open(folder)
    try:
        return [write_start_copy(store, folder).name for _ in range(count)]
    finally:
        store.close()


def test_rotation_keeps_exactly_the_last_14_copies(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    names = _write_copies(folder, 17)
    left = sorted(p.name for p in (folder / "state-exports").iterdir())
    assert len(left) == 14
    assert set(left) == set(names[-14:])


def test_rotation_orders_same_second_copies_and_ignores_foreign_files(tmp_path: Path) -> None:
    folder = tmp_path / "copies"
    folder.mkdir()
    for name in (
        "studio-state-20260101-000000.json.gz",
        "studio-state-20260101-000000-2.json.gz",
        "studio-state-20260101-000000-3.json.gz",
        "notes.txt",
    ):
        (folder / name).write_bytes(b"x")
    removed = rotate_copies(folder, keep=2)
    assert [p.name for p in removed] == ["studio-state-20260101-000000.json.gz"]
    assert (folder / "notes.txt").exists()


# -- mutation probes: each mutation must turn its acceptance check red -------------------------


def test_m1_leaving_a_field_out_of_the_export_turns_the_roundtrip_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _roundtrip_equal(tmp_path / "clean")
    real = state_export.build_content

    def without_drafts(
        db: sqlite3.Connection,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        content, blocked = real(db)
        content["tables"]["deck_draft"] = []  # type: ignore[index]
        return content, blocked

    monkeypatch.setattr(state_export, "build_content", without_drafts)
    assert not _roundtrip_equal(tmp_path / "mutated")


def test_m2_not_checking_the_sha_lets_a_tampered_file_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _tampered_import_refused(tmp_path / "clean")
    monkeypatch.setattr(state_export, "_check_sha", lambda _state: None)
    assert not _tampered_import_refused(tmp_path / "mutated")


def test_m3_a_rotation_that_keeps_15_is_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state_export, "KEEP_COPIES", 15)
    _write_copies(tmp_path / "data", 17)
    assert len(list((tmp_path / "data" / "state-exports").iterdir())) != 14


# -- instance lock -----------------------------------------------------------------------------


def test_a_second_lock_on_the_same_folder_is_refused_with_the_holder(tmp_path: Path) -> None:
    with InstanceLock(tmp_path), pytest.raises(InstanceAlreadyRunning, match="läuft schon"):
        InstanceLock(tmp_path).acquire()
    assert not (tmp_path / LOCK_NAME).exists()
    with InstanceLock(tmp_path):  # free again after release
        pass


def test_a_stale_lock_is_taken_over(tmp_path: Path) -> None:
    (tmp_path / LOCK_NAME).write_text(
        json.dumps({"pid": 2**22 + 12345, "token": "old", "heartbeat_epoch": time.time() - 3600}),
        encoding="utf-8",
    )
    with InstanceLock(tmp_path) as lock:
        assert lock.held
        assert json.loads((tmp_path / LOCK_NAME).read_text())["token"] != "old"


def test_a_fresh_heartbeat_of_a_dead_pid_counts_as_stale(tmp_path: Path) -> None:
    (tmp_path / LOCK_NAME).write_text(
        json.dumps({"pid": 2**22 + 12345, "token": "old", "heartbeat_epoch": time.time()}),
        encoding="utf-8",
    )
    if sys.platform == "win32":
        pytest.skip("PID probe is not used on Windows (UNKNOWN there)")
    with InstanceLock(tmp_path):
        assert json.loads((tmp_path / LOCK_NAME).read_text())["pid"] == os.getpid()


def test_an_unreadable_fresh_lock_counts_as_live(tmp_path: Path) -> None:
    (tmp_path / LOCK_NAME).write_text("{half", encoding="utf-8")
    with pytest.raises(InstanceAlreadyRunning):
        InstanceLock(tmp_path).acquire()


def test_the_heartbeat_refreshes_the_lock(tmp_path: Path) -> None:
    lock = InstanceLock(tmp_path, heartbeat_seconds=0.05)
    lock.acquire()
    try:
        first = json.loads((tmp_path / LOCK_NAME).read_text())["heartbeat_epoch"]
        deadline = time.time() + 5
        while time.time() < deadline:
            if json.loads((tmp_path / LOCK_NAME).read_text())["heartbeat_epoch"] > first:
                break
            time.sleep(0.05)
        else:
            pytest.fail("heartbeat did not advance")
    finally:
        lock.release()


def test_a_second_serve_on_the_same_folder_ends_with_a_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import uvicorn

    folder = tmp_path / "data"
    second: list[int] = []

    def run_second_start(*_args: object, **_kwargs: object) -> None:
        second.append(studio_cli._serve(str(folder), 8765, False))

    monkeypatch.setattr(uvicorn, "run", run_second_start)
    monkeypatch.setattr(studio_cli, "_warm_caches", lambda _data: None)
    assert studio_cli._serve(str(folder), 8765, False) == 0
    assert second == [3]
    assert "läuft schon" in capsys.readouterr().err
    assert not (folder / LOCK_NAME).exists()
    assert len(list((folder / "state-exports").iterdir())) == 1  # the first start's copy


# -- commands ----------------------------------------------------------------------------------


def test_cli_export_check_import_verify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = _seed(tmp_path / "data")
    store.close()
    out = tmp_path / "out.json.gz"
    assert studio_cli.main(["--data", str(tmp_path / "data"), "export-state", "--check"]) == 0
    assert (
        studio_cli.main(["--data", str(tmp_path / "data"), "export-state", "--to", str(out)]) == 0
    )
    assert out.is_file()
    assert studio_cli.main(["import-state", str(out), "--verify"]) == 0
    assert studio_cli.main(["--data", str(tmp_path / "new"), "import-state", str(out)]) == 0
    text = capsys.readouterr().out
    assert "deck_revision: 2" in text and "Karten-Stubs angelegt: 4" in text
    assert studio_cli.main(["--data", str(tmp_path / "new"), "import-state", str(out)]) == 2


def test_cli_export_blocked_exits_2_and_writes_no_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path / "data", without_oracle=("c_land",)).close()
    out = tmp_path / "out.json.gz"
    code = studio_cli.main(["--data", str(tmp_path / "data"), "export-state", "--to", str(out)])
    assert code == 2
    assert not out.exists()
    assert "no_oracle_id" in capsys.readouterr().err


def test_cli_export_refuses_a_target_inside_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path / "data").close()
    repository = Path(state_export.__file__).resolve().parents[3]
    with pytest.raises(StateFileError, match="Repository"):
        studio_cli.main(
            [
                "--data",
                str(tmp_path / "data"),
                "export-state",
                "--to",
                str(repository / "x.json.gz"),
            ]
        )
    assert not (repository / "x.json.gz").exists()
