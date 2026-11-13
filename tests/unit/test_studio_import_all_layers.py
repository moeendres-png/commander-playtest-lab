"""Layers added to ``import-all``: tagger roles, rulings, robustness. Synthetic data only."""

from __future__ import annotations

import csv
import gzip
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


def test_salt_and_combo_signals_are_layers_with_their_own_owner(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    folder = files["signals"]
    (folder / "edhrec_salt.csv").write_text("card_name,salt,rank\nFiller 03,2.5,1\n", "utf-8")
    (folder / "edhrec_test_commander_combos.csv").write_text(
        f"combo_label,cards,num_decks\nx,{COMMANDER};Filler 03;Filler 04,10\n", "utf-8"
    )
    code = _run(tmp_path, files, "--signals", str(folder))
    out = capsys.readouterr().out
    assert code == 0, out
    layers = _layers(out)
    assert layers["Signal edhrec_salt"] == "PARTIAL"
    assert layers["Signal edhrec_combo_decks"] == "PARTIAL"


def _claims(tmp_path: Path) -> int:
    from commander_lab.studio import StudioStore

    store = StudioStore.open(tmp_path / "studio")
    try:
        return int(store.connection.execute("SELECT COUNT(*) FROM card_role_claim").fetchone()[0])
    finally:
        store.close()


def _four(tmp_path: Path) -> Path:
    return _tagger(
        tmp_path / "bulk.csv", [(f"oracle-filler-0{n}", "ramp") for n in (1, 2, 3, 4)]
    )


def test_tagger_guard_warns_visibly_and_changes_nothing_above_half(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    assert _run(tmp_path, files, "--tagger-roles", str(_four(tmp_path))) == 0
    before = _claims(tmp_path)
    capsys.readouterr()
    _tagger(tmp_path / "bulk.csv", [("oracle-filler-01", "ramp")])  # drops 3 of 4: more than half
    code = _run(tmp_path, files, "--tagger-roles", str(tmp_path / "bulk.csv"))
    out = capsys.readouterr().out
    assert code == 0  # nothing was changed
    assert _claims(tmp_path) == before
    assert any(line.startswith("Warnung: Tagger-Rollen") and "--force" in line for line in out.splitlines())
    assert "WARNING" in out


def test_tagger_guard_allows_exactly_half(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    _run(tmp_path, files, "--tagger-roles", str(_four(tmp_path)))
    before = _claims(tmp_path)
    capsys.readouterr()
    _tagger(tmp_path / "bulk.csv", [("oracle-filler-01", "ramp"), ("oracle-filler-02", "ramp")])
    assert _run(tmp_path, files, "--tagger-roles", str(tmp_path / "bulk.csv")) == 0
    out = capsys.readouterr().out
    assert "Warnung:" not in out
    assert _claims(tmp_path) == before - 2


def test_tagger_force_replaces_more_than_half(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    _run(tmp_path, files, "--tagger-roles", str(_four(tmp_path)))
    before = _claims(tmp_path)
    capsys.readouterr()
    _tagger(tmp_path / "bulk.csv", [("oracle-filler-01", "ramp")])
    code = _run(tmp_path, files, "--tagger-roles", str(tmp_path / "bulk.csv"), "--force")
    assert code == 0
    assert "Warnung:" not in capsys.readouterr().out
    assert _claims(tmp_path) == before - 3


def test_the_help_text_says_a_tagger_warning_changes_nothing_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["import-all", "--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "Exit-Code 0" in text or "exit code 0" in text
