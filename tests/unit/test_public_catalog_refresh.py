"""Offline public catalog refresh: synthetic inputs only, with no owner data."""

from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _card(name: str, oracle_id: str, **fields: object) -> dict[str, object]:
    return {
        "name": name,
        "oracle_id": oracle_id,
        "lang": "en",
        "layout": "normal",
        "games": ["paper"],
        "legalities": {"commander": "legal"},
        "type_line": "Creature — Cat",
        "oracle_text": "Flying",
        "cmc": 2,
        "mana_cost": "{1}{U}",
        "colors": ["U"],
        "color_identity": ["U"],
        "keywords": ["Flying"],
        **fields,
    }


def test_all_engine_facts_bypass_names_and_preserve_distinct_exact_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script("export_xmage_card_facts")
    output = tmp_path / "facts.json"
    rows = [
        {
            "NAME": name,
            "P": "2",
            "T": "3",
            "L": "",
            "MV": "2",
            "TY": "CREATURE",
            "ST": "Cat",
            "SP": "",
            "MC": "{1}@@@{U}",
            "R": "Flying",
            "H": "FALSE",
            "F": "",
            "S": "",
            "O": "",
            "D": "",
        }
        for name in ("Élan", "Elan")
    ]

    def fake_export(_db: Path, _jar: Path, dest: Path) -> str:
        with dest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return "a" * 64

    monkeypatch.setattr(module, "export", fake_export)
    monkeypatch.setattr(module, "wanted_names", lambda *args: pytest.fail("private names read"))
    monkeypatch.setattr(
        sys, "argv", ["export", "--all-cards", "--out", str(output), "--engine-commit", "b" * 40]
    )
    assert module.main() == 0
    facts = json.loads(output.read_text())
    assert set(facts["cards"]) == {"Élan", "Elan"}
    assert facts["missing"] == []
    assert facts["provenance"]["database_sha256"] == "a" * 64
    assert facts["provenance"]["declared_engine_commit"] == "b" * 40
    assert facts["cards"]["Élan"]["engine_name"] == "Élan"


def test_bulk_extension_retains_existing_and_provenance_and_is_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script("build_pilot_card_knowledge")
    output = tmp_path / "pilot.json"
    original = {
        "source": "prior",
        "generated_at": "2026-11-11T00:00:00Z",
        "custom": 7,
        "cards": {"Old": {"name": "Old", "oracle_text": "newer"}},
    }
    output.write_text(json.dumps(original), encoding="utf-8")
    prior_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    bulk_file = tmp_path / "part.bin"
    records = [
        _card("Old", "one", oracle_text="older"),
        _card("New", "two"),
        _card("New", "two", id="another-printing"),
        _card("New", "token-id", layout="token"),
        _card("Foreign", "three", lang="de"),
        _card("Digital", "digital", games=["arena"]),
        _card("Not Legal", "notlegal", legalities={"commander": "not_legal"}),
        _card("Unclear", "unknown", legalities={}),
        _card("Banned", "banned", legalities={"commander": "banned"}),
        _card(
            "Front // Back",
            "four",
            layout="transform",
            card_faces=[
                {
                    "name": "Front",
                    "type_line": "Creature — Cat",
                    "oracle_text": "Front ability",
                    "mana_cost": "{U}",
                },
                {"name": "Back", "type_line": "Land", "oracle_text": "Back ability"},
            ],
        ),
    ]
    with gzip.open(bulk_file, "wt", encoding="utf-8") as handle:
        handle.writelines(json.dumps(card) + "\n" for card in records)
    monkeypatch.setattr(module, "deck_card_names", lambda *args: pytest.fail("deck names read"))
    monkeypatch.setattr(module, "listed_names", lambda *args: pytest.fail("names read"))
    monkeypatch.setattr(module, "fetch_cards", lambda *args: pytest.fail("network accessed"))
    assert (
        module.main(
            [
                "--all-cards",
                "--bulk-file",
                str(bulk_file),
                "--output",
                str(output),
                "--snapshot-at",
                "2026-11-09",
            ]
        )
        == 0
    )
    data = json.loads(output.read_text())
    assert set(data["cards"]) == {"Old", "New", "Front // Back", "Banned"}
    assert data["cards"]["Old"]["oracle_text"] == "newer"
    assert data["cards"]["Front // Back"]["oracle_text"] == "Front ability"
    assert "produced_mana" not in data["cards"]["New"]
    assert data["custom"] == 7
    assert (
        data["source"] == "Retained catalog and local Scryfall bulk snapshot (printed Oracle data)"
    )
    provenance = data["bulk_refresh"]
    assert provenance["retained_catalog_source"] == "prior"
    assert provenance["retained_catalog_sha256"] == prior_hash
    assert provenance["retained_catalog_generated_at"] == original["generated_at"]
    assert provenance["declared_snapshot_at"] == "2026-11-09"
    assert provenance["skipped_records"] == {
        "non_english": 1,
        "layout:token": 1,
        "non_paper": 1,
        "commander_not_legal": 1,
        "commander_unknown": 1,
    }
    assert provenance["inputs"] == [
        {"file": bulk_file.name, "sha256": hashlib.sha256(bulk_file.read_bytes()).hexdigest()}
    ]


@pytest.mark.parametrize(
    "records",
    [
        [],
        [_card("A", "1"), _card("A", "1", oracle_text="different")],
        [_card("A", "1"), _card("A", "2")],
        [{"name": "A", "lang": "en"}],
        [{"name": "A", "oracle_id": "1"}],
    ],
)
def test_bulk_rejects_empty_conflicts_and_malformed(
    tmp_path: Path, records: list[dict[str, object]]
) -> None:
    module = _script("build_pilot_card_knowledge")
    path = tmp_path / "bulk.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError):
        module.load_bulk([path])


def test_offline_missing_name_never_requests_network_and_prints_count_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _script("build_pilot_card_knowledge")
    path = tmp_path / "bulk.json"
    path.write_text(json.dumps([_card("Known", "1")]), encoding="utf-8")
    output = tmp_path / "out.json"
    monkeypatch.setattr(module, "deck_card_names", lambda paths: ["Known", "Private Missing"])
    monkeypatch.setattr(module, "fetch_cards", lambda *args: pytest.fail("network accessed"))
    assert module.main(["--bulk-file", str(path), "--output", str(output)]) == 1
    assert "Private Missing" not in capsys.readouterr().out
    document = json.loads(output.read_text())
    assert set(document["cards"]) == {"Known"}
    assert document["source"] == "Local Scryfall bulk snapshot (printed Oracle data)"
    assert document["bulk_refresh"]["retained_catalog_source"] is None


def test_bulk_mixed_formats_and_face_names(tmp_path: Path) -> None:
    module = _script("build_pilot_card_knowledge")
    front = _card(
        "Front // Back",
        "1",
        layout="split",
        card_faces=[
            {"name": "Front", "type_line": "Instant", "oracle_text": "Left", "mana_cost": "{U}"},
            {"name": "Back", "type_line": "Sorcery", "oracle_text": "Right", "mana_cost": "{U}"},
        ],
    )
    one = tmp_path / "one.bin"
    two = tmp_path / "two.json"
    one.write_text(json.dumps(front) + "\n", encoding="utf-8")
    two.write_text(json.dumps([front]), encoding="utf-8")
    result = module.load_bulk([one, two])
    assert result["Front // Back"]["oracle_text"] == "Left\n//\nRight"


def test_malformed_json_fails_without_changing_output(tmp_path: Path) -> None:
    module = _script("build_pilot_card_knowledge")
    source = tmp_path / "bad.bin"
    source.write_text('{"broken":', encoding="utf-8")
    output = tmp_path / "out.json"
    original = '{"cards": {}}'
    output.write_text(original, encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        module.main(["--all-cards", "--bulk-file", str(source), "--output", str(output)])
    assert output.read_text(encoding="utf-8") == original


def test_engine_subset_keeps_missing_separate_from_all_rows() -> None:
    module = _script("export_xmage_card_facts")
    row = {
        "NAME": "Present",
        "P": "",
        "T": "",
        "L": "",
        "MV": "1",
        "TY": "ARTIFACT",
        "ST": "",
        "SP": "",
        "MC": "{1}",
        "R": "",
        "H": "FALSE",
        "F": "",
        "S": "",
        "O": "",
        "D": "",
    }
    result = module.build_facts([row], {"Present", "Searched But Missing"})
    assert set(result["cards"]) == {"Present"}
    assert result["missing"] == ["Searched But Missing"]


def test_engine_provenance_hashes_actual_copied_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script("export_xmage_card_facts")
    database = tmp_path / "source.db"
    database.write_bytes(b"public test database")
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: None)
    digest = module.export(database, tmp_path / "unused.jar", tmp_path / "unused.csv")
    assert digest == hashlib.sha256(b"public test database").hexdigest()


def test_offline_lookup_does_not_accept_wrong_back_face(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script("build_pilot_card_knowledge")
    source = tmp_path / "cards.bin"
    source.write_text(
        json.dumps(
            _card(
                "Front // Back",
                "id",
                layout="transform",
                card_faces=[
                    {
                        "name": "Front",
                        "type_line": "Creature",
                        "oracle_text": "",
                        "mana_cost": "{U}",
                    },
                    {"name": "Back", "type_line": "Land", "oracle_text": "", "mana_cost": ""},
                ],
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "deck_card_names", lambda paths: ["Front // Different"])
    monkeypatch.setattr(module, "fetch_cards", lambda *args: pytest.fail("network accessed"))
    output = tmp_path / "out.json"
    assert module.main(["--bulk-file", str(source), "--output", str(output)]) == 1
    assert json.loads(output.read_text())["cards"] == {}


@pytest.mark.parametrize(
    "change",
    [
        {"cmc": None},
        {"cmc": True},
        {"cmc": float("nan")},
        {"cmc": -1},
        {"type_line": None},
        {"type_line": ""},
        {"oracle_text": None},
        {"mana_cost": None},
        {"colors": "U"},
        {"color_identity": [3]},
        {"keywords": "Flying"},
        {"produced_mana": ["garbage"]},
        {"layout": "unknown_future_layout"},
        {"layout": "transform", "card_faces": [{"name": "Front"}]},
        {"card_faces": []},
    ],
)
def test_incomplete_printed_facts_fail_before_output_write(
    tmp_path: Path, change: dict[str, object]
) -> None:
    module = _script("build_pilot_card_knowledge")
    source = tmp_path / "bad.json"
    source.write_text(
        json.dumps([_card("Valid", "1"), _card("Bad", "2", **change)]), encoding="utf-8"
    )
    output = tmp_path / "out.json"
    original = '{"cards": {"Retained": {"name": "Retained"}}}'
    output.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError):
        module.main(["--all-cards", "--bulk-file", str(source), "--output", str(output)])
    assert output.read_text(encoding="utf-8") == original


def test_missing_required_data_and_broken_face_are_rejected(tmp_path: Path) -> None:
    module = _script("build_pilot_card_knowledge")
    path = tmp_path / "bad.json"
    base = _card("Ordinary", "id")
    for field in (
        "cmc",
        "type_line",
        "oracle_text",
        "mana_cost",
        "colors",
        "color_identity",
        "keywords",
    ):
        malformed = dict(base)
        del malformed[field]
        path.write_text(json.dumps([malformed]), encoding="utf-8")
        with pytest.raises(ValueError):
            module.load_bulk([path])
    bad_face = _card(
        "Front // Back",
        "id",
        layout="transform",
        card_faces=[
            {"name": "Front", "type_line": "Creature", "oracle_text": "", "mana_cost": "{U}"},
            {"name": "Wrong", "type_line": "Land", "oracle_text": "", "mana_cost": ""},
        ],
    )
    path.write_text(json.dumps([bad_face]), encoding="utf-8")
    with pytest.raises(ValueError, match="face names"):
        module.load_bulk([path])


def test_vanilla_and_land_can_have_empty_printed_fields(tmp_path: Path) -> None:
    module = _script("build_pilot_card_knowledge")
    land = _card("Land", "land", type_line="Basic Land — Island", oracle_text="", colors=[])
    del land["mana_cost"]
    path = tmp_path / "cards.json"
    path.write_text(json.dumps([land]), encoding="utf-8")
    result = module.load_bulk([path])["Land"]
    assert result["oracle_text"] == "" and result["mana_cost"] == ""
    assert "produced_mana" not in result


@pytest.mark.parametrize("field", ["name", "type_line", "oracle_text", "mana_cost"])
def test_incomplete_nonland_face_fails_before_output_write(tmp_path: Path, field: str) -> None:
    module = _script("build_pilot_card_knowledge")
    face = {"name": "Front", "type_line": "Creature", "oracle_text": "", "mana_cost": "{U}"}
    del face[field]
    card = _card(
        "Front // Back",
        "id",
        layout="transform",
        card_faces=[
            face,
            {"name": "Back", "type_line": "Land", "oracle_text": "", "mana_cost": ""},
        ],
    )
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([card]), encoding="utf-8")
    output = tmp_path / "out.json"
    output.write_text('{"cards": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        module.main(["--all-cards", "--bulk-file", str(path), "--output", str(output)])
    assert output.read_text(encoding="utf-8") == '{"cards": {}}'


def test_network_requires_explicit_public_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script("build_pilot_card_knowledge")
    monkeypatch.setattr(module, "fetch_cards", lambda *args: pytest.fail("network accessed"))
    monkeypatch.setattr(module, "deck_card_names", lambda *args: pytest.fail("deck names read"))
    with pytest.raises(SystemExit):
        module.main(["--output", str(tmp_path / "out.json")])
    with pytest.raises(SystemExit):
        module.main(["--public-api", "--output", str(tmp_path / "out.json")])
