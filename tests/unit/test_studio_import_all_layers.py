"""Layers added to ``import-all``: tagger roles, rulings, robustness. Synthetic data only."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import pytest

from commander_lab.studio.__main__ import main
from tests.unit.test_studio_import_all import (  # noqa: F401
    COMMANDER,
    _files,
    _layers,
    _no_repo_research,
)


def _tagger(path: Path, rows: list[tuple[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["oracle_id", "card_name", "category", "bulk_label", "weight"])
        for oracle_id, category in rows:
            writer.writerow([oracle_id, "x", category, "label", "median"])
    return path


def _run(tmp_path: Path, files: dict[str, Path], *extra: str) -> int:
    return main(
        [
            "--data", str(tmp_path / "studio"), "import-all", "--commander", COMMANDER,
            "--inventory", str(files["inventory"]), "--scryfall", str(files["scryfall"]),
            *extra,
        ]
    )  # fmt: skip


def test_tagger_roles_are_a_step_and_fill_the_roles_layer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    tagger = _tagger(
        tmp_path / "bulk.csv", [("oracle-filler-03", "ramp"), ("oracle-forest", "anthem")]
    )
    code = _run(tmp_path, files, "--tagger-roles", str(tagger))
    out = capsys.readouterr().out
    assert code == 0, out
    layers = _layers(out)
    assert layers["Rollen"] == "PARTIAL"
    assert "Tagger-Rollen" in out


def test_tagger_file_without_role_rows_fails_the_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    tagger = _tagger(tmp_path / "bulk.csv", [("oracle-forest", "anthem")])
    assert _run(tmp_path, files, "--tagger-roles", str(tagger)) == 1
    assert "unchanged" in capsys.readouterr().out


def test_a_cut_gzip_is_a_failed_step_with_a_table_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    raw = gzip.compress(b'{"a": 1}\n' * 2000)
    cut = tmp_path / "cut.jsonl.gz"
    cut.write_bytes(raw[: len(raw) // 2])
    files["scryfall"] = cut
    assert _run(tmp_path, files) == 1
    out = capsys.readouterr().out
    assert "EOFError" in out and "Vollständigkeit je Schicht" in out


def test_unknown_commander_message_lists_the_available_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    code = main(
        [
            "--data", str(tmp_path / "studio"), "import-all", "--commander", "Nobody",
            "--inventory", str(files["inventory"]), "--scryfall", str(files["scryfall"]),
        ]
    )  # fmt: skip
    assert code == 4
    assert COMMANDER in capsys.readouterr().err
