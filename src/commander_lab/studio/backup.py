"""Consistent local backup and restore for the Commander Studio data folder (#1532)."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from .games import GAMES_FOLDER
from .launch import _repository_root
from .store import DATABASE_NAME

SCHEMA_BACKUP = "studio-backup-1"
_CHUNK_BYTES = 1024 * 1024


def _sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _is_within(candidate: Path, parent: Path) -> bool:
    return candidate == parent or parent in candidate.parents


def _validate_manifest_rel_path(rel_raw: str) -> Path:
    if not rel_raw or "\\" in rel_raw or ":" in rel_raw or rel_raw.startswith("/"):
        raise ValueError(f"Ungültiger relativer Pfad im Manifest: {rel_raw!r}")
    win_path = PureWindowsPath(rel_raw)
    if win_path.drive or win_path.root:
        raise ValueError(f"Ungültiger relativer Pfad im Manifest: {rel_raw!r}")
    rel_path = Path(rel_raw)
    if rel_path.is_absolute() or ".." in rel_path.parts or "." in rel_path.parts:
        raise ValueError(f"Ungültiger relativer Pfad im Manifest: {rel_raw!r}")
    return rel_path


def _check_sqlite_integrity(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(f"Datenbank-Integritätsprüfung fehlgeschlagen: {exc}") from exc
    finally:
        conn.close()
    if row is None or row[0] != "ok":
        raise RuntimeError(f"Datenbank-Integritätsprüfung fehlgeschlagen: {row!r}")


def _validate_backup_destination(
    data_path: Path,
    dest_root: Path,
    repo_root: Path,
) -> None:
    if _is_within(dest_root, repo_root):
        raise ValueError("Das Sicherungsziel darf nicht im Repository liegen.")
    if _is_within(dest_root, data_path):
        raise ValueError("Das Sicherungsziel darf nicht im Studio-Datenordner liegen.")


def create_backup(
    data_folder: str | Path,
    destination_root: str | Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Create a timestamped, consistent backup of ``studio.sqlite3`` and ``games/``."""
    data_path = Path(data_folder).expanduser().resolve()
    dest_root = Path(destination_root).expanduser().resolve()
    repo = (repo_root if repo_root is not None else _repository_root()).resolve()
    _validate_backup_destination(data_path, dest_root, repo)

    db_src = data_path / DATABASE_NAME
    if not db_src.is_file():
        raise FileNotFoundError(f"Studio-Datenbank nicht gefunden: {db_src}")

    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    dest_root.mkdir(parents=True, exist_ok=True)
    backup_dir = dest_root / f"commander-studio-backup-{stamp}"
    suffix = 1
    while backup_dir.exists():
        suffix += 1
        backup_dir = dest_root / f"commander-studio-backup-{stamp}-{suffix}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    try:
        db_dst = backup_dir / DATABASE_NAME
        src_conn = sqlite3.connect(str(db_src), timeout=30.0)
        dst_conn = sqlite3.connect(str(db_dst))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
        _check_sqlite_integrity(db_dst)

        games_src = data_path / GAMES_FOLDER
        if games_src.is_dir():
            games_dst = backup_dir / GAMES_FOLDER
            for item in sorted(games_src.rglob("*")):
                if item.is_file():
                    rel = item.relative_to(games_src)
                    target = games_dst / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)

        files: list[dict[str, object]] = []
        checksum_lines: list[str] = []
        total_bytes = 0
        for file_path in sorted(p for p in backup_dir.rglob("*") if p.is_file()):
            rel_posix = file_path.relative_to(backup_dir).as_posix()
            size, sha256 = _sha256_file(file_path)
            total_bytes += size
            files.append({"path": rel_posix, "size": size, "sha256": sha256})
            checksum_lines.append(f"{sha256}  {rel_posix}")

        manifest: dict[str, object] = {
            "schema": SCHEMA_BACKUP,
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "backup_dir": str(backup_dir),
            "file_count": len(files),
            "total_bytes": total_bytes,
            "excluded": ["engine", "images"],
            "files": files,
        }
        (backup_dir / "backup_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (backup_dir / "SHA256SUMS.txt").write_text(
            "\n".join(checksum_lines) + ("\n" if checksum_lines else ""),
            encoding="utf-8",
        )
        return manifest
    except BaseException:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


def restore_backup(
    backup_dir: str | Path,
    target_data_folder: str | Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Verify checksums of a backup folder and restore it into an empty target folder."""
    src_dir = Path(backup_dir).expanduser().resolve()
    target_dir = Path(target_data_folder).expanduser().resolve()
    repo = (repo_root if repo_root is not None else _repository_root()).resolve()
    if _is_within(target_dir, repo):
        raise ValueError("Der Ziel-Datenordner darf nicht im Repository liegen.")

    manifest_path = src_dir / "backup_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Sicherungs-Manifest fehlt: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA_BACKUP:
        raise ValueError("Ungültiges Sicherungs-Manifest.")

    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Sicherungs-Manifest enthält keine Dateien.")

    if target_dir.exists():
        if not target_dir.is_dir():
            raise ValueError(f"Ziel ist kein Ordner: {target_dir}")
        if any(target_dir.iterdir()):
            raise ValueError(f"Zielordner für Rückspiel muss leer sein: {target_dir}")

    verified_entries: list[tuple[Path, Path, int, str]] = []
    has_db = False
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Ungültiger Dateieintrag im Manifest.")
        rel_raw = str(entry.get("path") or "")
        rel_path = _validate_manifest_rel_path(rel_raw)
        src_file = (src_dir / rel_path).resolve()
        if not _is_within(src_file, src_dir):
            raise ValueError(f"Ungültiger relativer Pfad im Manifest: {rel_raw!r}")
        if not _is_within((target_dir / rel_path).resolve(), target_dir):
            raise ValueError(f"Ungültiger relativer Pfad im Manifest: {rel_raw!r}")
        if not src_file.is_file():
            raise FileNotFoundError(f"Gesicherte Datei fehlt: {src_file}")
        size, sha256 = _sha256_file(src_file)
        if size != entry.get("size") or sha256 != entry.get("sha256"):
            raise ValueError(f"Prüfsumme oder Größe weicht ab für {rel_raw}")
        if rel_path.as_posix() == DATABASE_NAME:
            has_db = True
        verified_entries.append((rel_path, src_file, size, sha256))

    if not has_db:
        raise FileNotFoundError(f"Wiederhergestellte Datenbank fehlt im Manifest: {DATABASE_NAME}")

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = target_dir.parent / f".{target_dir.name}.restore-{uuid.uuid4().hex[:8]}.partial"
    staging_dir.mkdir(parents=True, exist_ok=False)
    try:
        for rel_path, src_file, expected_size, expected_sha in verified_entries:
            dst_file = staging_dir / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied_size, copied_sha = _sha256_file(dst_file)
            if copied_size != expected_size or copied_sha != expected_sha:
                raise RuntimeError(f"Prüfsumme der Kopie weicht ab für {rel_path.as_posix()}")

        _check_sqlite_integrity(staging_dir / DATABASE_NAME)
        if target_dir.exists():
            if any(target_dir.iterdir()):
                raise ValueError(f"Zielordner für Rückspiel muss leer sein: {target_dir}")
            target_dir.rmdir()
        staging_dir.rename(target_dir)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return {
        "schema": SCHEMA_BACKUP,
        "restored_to": str(target_dir),
        "files_verified": len(verified_entries),
        "integrity_check": "ok",
    }
