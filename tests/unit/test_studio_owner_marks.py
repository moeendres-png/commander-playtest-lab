"""Owner marks import (Refs #1182 G2). All data here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore
from commander_lab.studio.__main__ import main
from commander_lab.studio.marks import import_owner_marks
from tests.unit.test_studio_builder import _fill


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _mark(store: StudioStore, card_id: str) -> tuple[int, int, str] | None:
    row = store.connection.execute(
        "SELECT favorite, excluded, note FROM card_mark WHERE card_id = ?", (card_id,)
    ).fetchone()
    return None if row is None else (row["favorite"], row["excluded"], row["note"])


def _id(store: StudioStore, name: str) -> str:
    card_id = store.card_id_by_name(name)
    assert card_id is not None
    return card_id


def test_import_merges_resolves_by_id_then_name_and_is_idempotent(
    studio: StudioStore, tmp_path: Path
) -> None:
    forest = _id(studio, "Forest")
    rat = _id(studio, "Swarm Rat")
    studio.connection.execute(
        "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
        "VALUES (?, 0, 1, 'keep this note', '2026-11-01')",
        (rat,),
    )
    path = _write(
        tmp_path / "marks.json",
        {
            "format": "studio-marks-1",
            "marks": [
                {"card_id": forest, "favorite": True},
                {"card_id": "card:project:missing", "card_name": "Swarm Rat", "favorite": True},
                {"card_id": "card:project:nobody", "card_name": "No Such Card", "favorite": True},
                {"card_id": forest},  # states nothing, so it is not an entry that changes anything
            ],
        },
    )
    report = import_owner_marks(studio, path)
    assert report == {
        "entries": 4,
        "resolved": 2,
        "unresolved": 1,
        "changed": 2,
        "favorites_after": 2,
        "ignored_fields": {},
    }
    assert _mark(studio, forest) == (1, 0, "")
    assert _mark(studio, rat) == (1, 1, "keep this note")  # exclusion and note were not mentioned
    again = import_owner_marks(studio, path)
    assert again["changed"] == 0
    assert again["favorites_after"] == 2


def test_old_studio_export_reads_favorites_and_notes_but_not_tier_values(
    studio: StudioStore, tmp_path: Path
) -> None:
    forest = _id(studio, "Forest")
    rat = _id(studio, "Swarm Rat")
    export = {
        "app": "chulane-studio",
        "version": 1,
        "state": {
            "fav": {forest: True, rat: False},
            "notes": {rat: "mine", forest: "  "},
            "wish": {forest: 1},
            "variants": {},
            "tierOverride": {forest: "S", rat: "A"},
        },
    }
    report = import_owner_marks(studio, _write(tmp_path / "state.json", export))
    assert report["resolved"] == 2
    assert report["ignored_fields"] == {"wish": 1, "tierOverride": 2}
    assert _mark(studio, forest) == (1, 0, "")
    assert _mark(studio, rat) == (0, 0, "mine")


def test_an_empty_old_export_changes_nothing_and_says_so(
    studio: StudioStore, tmp_path: Path
) -> None:
    export = {"app": "chulane-studio", "state": {"fav": {}, "notes": {}, "tierOverride": {}}}
    report = import_owner_marks(studio, _write(tmp_path / "empty.json", export))
    assert report["entries"] == 0
    assert report["changed"] == 0
    assert studio.count("card_mark") == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"nothing": "known"},
        {"format": "studio-marks-1", "marks": "no list"},
        {"format": "studio-marks-1", "marks": [{"card_name": "Forest", "favorite": "yes"}]},
        {"format": "studio-marks-1", "marks": [{"card_name": "Forest", "note": 5}]},
    ],
)
def test_a_bad_file_is_refused_before_anything_is_written(
    studio: StudioStore, tmp_path: Path, payload: object
) -> None:
    good = {"card_name": "Swarm Rat", "favorite": True}
    if isinstance(payload, dict) and isinstance(payload.get("marks"), list):
        payload["marks"].insert(0, good)
    with pytest.raises(ValueError):
        import_owner_marks(studio, _write(tmp_path / "bad.json", payload))
    assert studio.count("card_mark") == 0


def test_command_prints_counts_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data"
    store = StudioStore.open(data)
    _fill(store, tmp_path)
    store.close()
    path = _write(
        tmp_path / "marks.json",
        {"format": "studio-marks-1", "marks": [{"card_name": "Forest", "favorite": True}]},
    )
    assert main(["--data", str(data), "import-owner-marks", str(path)]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["favorites_after"] == 1
    assert "Forest" not in out
