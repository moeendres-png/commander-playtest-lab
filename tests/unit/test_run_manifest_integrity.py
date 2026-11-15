from __future__ import annotations

import json
from pathlib import Path

import pytest


def _manifest(root: Path) -> dict:
    return json.loads((root / "run-manifest.json").read_text(encoding="utf-8"))


def _replace(root: Path, payload: object) -> None:
    (root / "run-manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def _symlink(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable; covered by Linux CI")
        raise


def _write_seed_literal(root: Path, literal: str, *, nested: bool = False) -> None:
    payload = _manifest(root)
    payload["metadata"] = {"nested": {"seed": 1}} if nested else {"seed": 1}
    text = json.dumps(payload)
    marker = '"seed": 1'
    assert marker in text
    text = text.replace(marker, f'"seed": {literal}', 1)
    assert f'"seed": {literal}' in text
    (root / "run-manifest.json").write_text(text, encoding="utf-8")
