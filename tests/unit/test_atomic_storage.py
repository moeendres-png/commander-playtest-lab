from __future__ import annotations

import os
from pathlib import Path

from commander_lab.storage.atomic import atomic_write_bytes, atomic_write_json, atomic_write_text


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
