"""Unit tests for consistent Studio backup and restore (#1532)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

import pytest

from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.backup import create_backup, restore_backup
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.store import DATABASE_NAME, DataClass, StudioStore


def _seed_store(data_dir: Path) -> tuple[str, int, int]:
    store = StudioStore.open(data_dir)
    try:
        src = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title="backup_test_source",
            sha256="0" * 64,
        )
        store.connection.execute(
            "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
            "VALUES ('c_chulane', 'Chulane, Teller of Tales', 'WUG', ?)",
            (src,),
        )
        store.connection.execute(
            "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
            "VALUES ('c_forest', 'Forest', 'G', ?)",
            (src,),
        )
        cards = [
            RevisionCard("c_chulane", 1, "commander"),
            RevisionCard("c_forest", 99, "main"),
        ]
        rev_id = create_revision(
            store,
            deck_id="chulane-test",
            name="Chulane Test",
            cards=cards,
        )
        store.connection.execute(
            "INSERT OR REPLACE INTO card_mark(card_id, favorite, excluded, note, updated_at) "
            "VALUES(?, ?, ?, ?, ?)",
            ("c_forest", 1, 0, "Basis-Land", "2026-11-18T00:00:00Z"),
        )
        store.connection.commit()
        rev_count = int(
            store.connection.execute("SELECT COUNT(*) FROM deck_revision").fetchone()[0]
        )
        mark_count = int(store.connection.execute("SELECT COUNT(*) FROM card_mark").fetchone()[0])
        return rev_id, rev_count, mark_count
    finally:
        store.close()


def test_backup_creates_timestamped_folder_with_checksums_and_excludes_engine_and_images(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "studio_data"
    backup_root = tmp_path / "backups"
    _seed_store(data_dir)

    games_dir = data_dir / "games"
    games_dir.mkdir(parents=True)
    (games_dir / "g1.jsonl.gz").write_bytes(b"game-log-bytes")
    (games_dir / "paired_s1.series.json").write_text('{"series_id":"s1"}\n', encoding="utf-8")

    # Engine JAR and image cache must NOT be copied into backups
    (data_dir / "engine").mkdir(parents=True)
    (data_dir / "engine" / "xmage-engine-bridge.jar").write_bytes(b"jar-bytes")
    (data_dir / "images").mkdir(parents=True)
    (data_dir / "images" / "card.jpg").write_bytes(b"img-bytes")

    rc = studio_main(["--data", str(data_dir), "backup", "--to", str(backup_root), "--json"])
    assert rc == 0
    manifest = json.loads(capsys.readouterr().out)
    backup_dir = Path(str(manifest["backup_dir"]))
    assert backup_dir.is_dir()
    assert backup_dir.name.startswith("commander-studio-backup-")
    assert (backup_dir / DATABASE_NAME).is_file()
    assert (backup_dir / "games" / "g1.jsonl.gz").is_file()
    assert (backup_dir / "games" / "paired_s1.series.json").is_file()
    assert not (backup_dir / "engine").exists()
    assert not (backup_dir / "images").exists()
    assert (backup_dir / "SHA256SUMS.txt").is_file()

    files = manifest["files"]
    assert isinstance(files, list)
    paths = {entry["path"] for entry in files}
    assert DATABASE_NAME in paths
    assert "games/g1.jsonl.gz" in paths
    assert "games/paired_s1.series.json" in paths
    for entry in files:
        assert isinstance(entry["size"], int) and entry["size"] > 0
        assert isinstance(entry["sha256"], str) and len(entry["sha256"]) == 64

    # Must not contain environment variables or credentials
    manifest_text = (backup_dir / "backup_manifest.json").read_text(encoding="utf-8")
    for secret_key in ("GITHUB_TOKEN", "OPENAI_API_KEY", "HTTP_PROXY"):
        assert secret_key not in manifest_text
    assert str(dict(os.environ)) not in manifest_text


def test_backup_rejects_destination_inside_repo_or_data_dir(tmp_path: Path) -> None:
    data_dir = tmp_path / "studio_data"
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    _seed_store(data_dir)

    with pytest.raises(ValueError, match="Repository"):
        create_backup(data_dir, fake_repo / "sub", repo_root=fake_repo)

    with pytest.raises(ValueError, match="Studio-Datenordner"):
        create_backup(data_dir, data_dir / "nested", repo_root=fake_repo)


def test_backup_is_consistent_under_concurrent_writes_and_restores_cleanly(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "studio_data"
    backup_root = tmp_path / "backups"
    restore_dir = tmp_path / "restored_data"
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    rev_id, orig_revs, orig_marks = _seed_store(data_dir)
    (data_dir / "games").mkdir(parents=True)
    (data_dir / "games" / "series.json").write_text('{"id":"ser-1"}\n', encoding="utf-8")

    errors: list[BaseException] = []
    stop = threading.Event()

    def writer() -> None:
        conn = sqlite3.connect(str(data_dir / DATABASE_NAME), timeout=30.0)
        try:
            idx = 0
            while not stop.is_set():
                idx += 1
                conn.execute(
                    "UPDATE card_mark SET note = ? WHERE card_id = 'c_forest'",
                    (f"note-{idx}",),
                )
                conn.commit()
        except BaseException as exc:  # pragma: no cover - surfaced via errors list
            errors.append(exc)
        finally:
            conn.close()

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    try:
        manifest = create_backup(data_dir, backup_root, repo_root=fake_repo)
    finally:
        stop.set()
        thread.join(timeout=5.0)

    assert not errors
    backup_dir = Path(str(manifest["backup_dir"]))

    # Integrity check on backed-up DB
    conn = sqlite3.connect(str(backup_dir / DATABASE_NAME))
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        conn.close()

    # Restore into empty folder and verify counts + revision id
    restored = restore_backup(backup_dir, restore_dir, repo_root=fake_repo)
    assert restored["integrity_check"] == "ok"
    assert (restore_dir / "games" / "series.json").read_text(encoding="utf-8") == '{"id":"ser-1"}\n'

    restored_store = StudioStore.open(restore_dir)
    try:
        revs = int(
            restored_store.connection.execute("SELECT COUNT(*) FROM deck_revision").fetchone()[0]
        )
        marks = int(
            restored_store.connection.execute("SELECT COUNT(*) FROM card_mark").fetchone()[0]
        )
        found_rev = restored_store.connection.execute(
            "SELECT revision_id FROM deck_revision WHERE revision_id = ?", (rev_id,)
        ).fetchone()
        assert revs == orig_revs
        assert marks == orig_marks
        assert found_rev is not None and found_rev[0] == rev_id
    finally:
        restored_store.close()
