from __future__ import annotations

import os
from pathlib import Path

from commander_lab.storage.atomic import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    replace_file_atomic,
)


def test_atomic_write_bytes(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "payload.bin"

    result = atomic_write_bytes(target, b"commander-lab")

    assert result == target
    assert target.read_bytes() == b"commander-lab"


def test_atomic_write_text(tmp_path: Path) -> None:
    target = tmp_path / "payload.txt"

    atomic_write_text(target, "Korvold\n")

    assert target.read_text(encoding="utf-8") == "Korvold\n"


def test_atomic_write_json(tmp_path: Path) -> None:
    target = tmp_path / "payload.json"

    atomic_write_json(target, {"status": "ok"})

    assert '"status": "ok"' in target.read_text(encoding="utf-8")


def test_atomic_write_without_fchmod(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delattr(os, "fchmod", raising=False)
    target = tmp_path / "windows-compatible.txt"

    atomic_write_text(target, "works")

    assert target.read_text(encoding="utf-8") == "works"


def test_replace_file_atomic_retries_transient_windows_sharing_error(
    monkeypatch, tmp_path: Path
) -> None:
    import pytest

    src = tmp_path / "src.tmp"
    dst = tmp_path / "dst.json"
    src.write_text("new", encoding="utf-8")
    dst.write_text("old", encoding="utf-8")

    monkeypatch.setattr("commander_lab.storage.atomic.os.name", "nt")
    monkeypatch.setattr("commander_lab.storage.atomic.time.sleep", lambda _s: None)

    calls = 0
    real_replace = os.replace

    def flaky_replace(a, b) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            err = PermissionError("Access is denied")
            err.winerror = 5  # type: ignore[attr-defined]
            raise err
        real_replace(a, b)

    monkeypatch.setattr("commander_lab.storage.atomic.os.replace", flaky_replace)
    replace_file_atomic(src, dst, max_attempts=5, base_delay_seconds=0.0)
    assert calls == 3
    assert dst.read_text(encoding="utf-8") == "new"

    src2 = tmp_path / "src2.tmp"
    src2.write_text("fail", encoding="utf-8")

    def always_denied(a, b) -> None:
        err = PermissionError("Access is denied")
        err.winerror = 5  # type: ignore[attr-defined]
        raise err

    monkeypatch.setattr("commander_lab.storage.atomic.os.replace", always_denied)
    with pytest.raises(PermissionError):
        replace_file_atomic(src2, dst, max_attempts=3, base_delay_seconds=0.0)
