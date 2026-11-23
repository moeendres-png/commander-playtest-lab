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

    # Restore into empty folder and verify counts + revision id + exact DB sha256
    from commander_lab.studio.backup import _sha256_file

    expected_db_hash = _sha256_file(backup_dir / DATABASE_NAME)
    restored = restore_backup(backup_dir, restore_dir, repo_root=fake_repo)
    assert restored["integrity_check"] == "ok"
    assert _sha256_file(restore_dir / DATABASE_NAME) == expected_db_hash
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


def test_restore_rejects_tampered_file_and_leaves_no_partial_artifacts(tmp_path: Path) -> None:
    data_dir = tmp_path / "studio_data"
    backup_root = tmp_path / "backups"
    restore_dir = tmp_path / "restored_tampered"
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    _seed_store(data_dir)
    (data_dir / "games").mkdir(parents=True)
    (data_dir / "games" / "a.json").write_text('{"ok":1}\n', encoding="utf-8")

    manifest = create_backup(data_dir, backup_root, repo_root=fake_repo)
    backup_dir = Path(str(manifest["backup_dir"]))
    (backup_dir / "games" / "a.json").write_text('{"ok":2}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Prüfsumme oder Größe"):
        restore_backup(backup_dir, restore_dir, repo_root=fake_repo)
    assert not restore_dir.exists()
    assert not list(tmp_path.glob(f".{restore_dir.name}.restore-*.partial"))


@pytest.mark.parametrize("bad_rel", ["../evil.txt", "/Windows/x", "\\\\evil\\x", "E:evil"])
def test_restore_rejects_windows_and_posix_traversal_paths(tmp_path: Path, bad_rel: str) -> None:
    data_dir = tmp_path / "studio_data"
    backup_root = tmp_path / "backups"
    restore_dir = tmp_path / "restored_traversal"
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    _seed_store(data_dir)

    manifest = create_backup(data_dir, backup_root, repo_root=fake_repo)
    backup_dir = Path(str(manifest["backup_dir"]))
    manifest_path = backup_dir / "backup_manifest.json"
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    doc["files"].append({"path": bad_rel, "size": 1, "sha256": "0" * 64})
    manifest_path.write_text(json.dumps(doc), encoding="utf-8")

    with pytest.raises(ValueError, match="Ungültiger relativer Pfad"):
        restore_backup(backup_dir, restore_dir, repo_root=fake_repo)
    assert not restore_dir.exists()


def test_restore_rejects_corrupt_db_missing_db_and_nonempty_target(tmp_path: Path) -> None:
    from commander_lab.studio.backup import _sha256_file

    data_dir = tmp_path / "studio_data"
    backup_root = tmp_path / "backups"
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    _seed_store(data_dir)
    (data_dir / "games").mkdir(parents=True)
    (data_dir / "games" / "g.json").write_text("{}\n", encoding="utf-8")

    manifest = create_backup(data_dir, backup_root, repo_root=fake_repo)
    backup_dir = Path(str(manifest["backup_dir"]))
    manifest_path = backup_dir / "backup_manifest.json"

    # 1) Non-empty target rejected
    non_empty = tmp_path / "non_empty"
    non_empty.mkdir()
    (non_empty / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="muss leer sein"):
        restore_backup(backup_dir, non_empty, repo_root=fake_repo)

    # 2) Corrupt DB (even with updated manifest checksum) fails in integrity_check with no leftovers
    corrupt_dir = tmp_path / "restored_corrupt"
    (backup_dir / DATABASE_NAME).write_bytes(b"not-a-sqlite-database-at-all")
    new_size, new_sha = _sha256_file(backup_dir / DATABASE_NAME)
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in doc["files"]:
        if entry["path"] == DATABASE_NAME:
            entry["size"] = new_size
            entry["sha256"] = new_sha
    manifest_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Integritätsprüfung"):
        restore_backup(backup_dir, corrupt_dir, repo_root=fake_repo)
    assert not corrupt_dir.exists()

    # 3) Missing DB in manifest fails before copying games/
    missing_db_dir = tmp_path / "restored_missing_db"
    doc["files"] = [entry for entry in doc["files"] if entry["path"] != DATABASE_NAME]
    manifest_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="Datenbank fehlt"):
        restore_backup(backup_dir, missing_db_dir, repo_root=fake_repo)
    assert not missing_db_dir.exists()


def test_backup_skips_reserve_files_and_tolerates_vanishing_transient_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Punkt 4 (#1737): *.reserve files are excluded and vanishing transient files do not fail."""
    import shutil

    from commander_lab.studio import backup as backup_module

    data_dir = tmp_path / "studio_data"
    backup_root = tmp_path / "backups"
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    _seed_store(data_dir)

    games_dir = data_dir / "games"
    paired_sub = games_dir / "paired_decks" / "paired-1"
    paired_sub.mkdir(parents=True)
    (games_dir / "keep.jsonl").write_text('{"ok": 1}\n', encoding="utf-8")
    (games_dir / "batch-1.reserve").write_text('{"pid": 1}\n', encoding="utf-8")
    (paired_sub / "nested.reserve").write_text('{"pid": 2}\n', encoding="utf-8")
    lock_file = paired_sub / "running.lock"
    lock_file.write_text('{"pid": 3}\n', encoding="utf-8")

    real_copy2 = shutil.copy2
    copied_names: list[str] = []

    def flaky_copy2(src: object, dst: object, *args: object, **kwargs: object) -> object:
        src_path = Path(str(src))
        copied_names.append(src_path.name)
        if src_path.name == "running.lock":
            src_path.unlink(missing_ok=True)
            raise FileNotFoundError(str(src_path))
        return real_copy2(src, dst, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(backup_module.shutil, "copy2", flaky_copy2)

    manifest = create_backup(data_dir, backup_root, repo_root=fake_repo)
    backup_dir = Path(str(manifest["backup_dir"]))
    assert backup_dir.is_dir()
    paths = {entry["path"] for entry in manifest["files"]}  # type: ignore[union-attr]
    assert "games/keep.jsonl" in paths
    assert "games/batch-1.reserve" not in paths
    assert "games/paired_decks/paired-1/nested.reserve" not in paths
    assert "games/paired_decks/paired-1/running.lock" not in paths
    assert "batch-1.reserve" not in copied_names
    assert "nested.reserve" not in copied_names
    assert "running.lock" in copied_names
    assert backup_module._is_transient_game_file(Path("x.reserve")) is True
    assert backup_module._is_transient_game_file(Path("running.lock")) is True
    assert backup_module._is_transient_game_file(Path("keep.jsonl")) is False

    # Also prove: a .reserve file vanishing right at copy2 is still safely ignored if reached,
    # whereas a real data file vanishing at copy2 fails closed and cleans up the partial backup.
    def real_file_vanishes(src: object, dst: object, *args: object, **kwargs: object) -> object:
        src_path = Path(str(src))
        if src_path.name == "keep.jsonl":
            raise FileNotFoundError(str(src_path))
        return real_copy2(src, dst, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(backup_module.shutil, "copy2", real_file_vanishes)
    before_dirs = set(backup_root.iterdir())
    with pytest.raises(FileNotFoundError):
        create_backup(data_dir, backup_root, repo_root=fake_repo)
    assert set(backup_root.iterdir()) == before_dirs
