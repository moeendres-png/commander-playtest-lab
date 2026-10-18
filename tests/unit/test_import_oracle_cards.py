"""scripts/import_oracle_cards.py adds named cards to the oracle catalog on demand (#877).

No network: Scryfall answers are hand-made card objects and ``fetch_cards`` is replaced.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.cards.catalog import CardCatalog
from commander_lab.models.cards import CardIdentity

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "import_oracle_cards_under_test", ROOT / "scripts" / "import_oracle_cards.py"
)
assert spec and spec.loader
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

NOW = "2026-10-18T10:00:00Z"
URL = "https://api.scryfall.com/cards/collection"

MIND_STONE: dict[str, Any] = {
    "name": "Mind Stone",
    "oracle_id": "00000000-0000-0000-0000-000000000001",
    "cmc": 2.0,
    "mana_cost": "{2}",
    "type_line": "Artifact",
    "oracle_text": "{T}: Add {C}.\n{1}, {T}, Sacrifice Mind Stone: Draw a card.",
    "colors": [],
    "color_identity": [],
    "keywords": [],
    "legalities": {"commander": "legal"},
}
FOREST: dict[str, Any] = {
    "name": "Forest",
    "oracle_id": "00000000-0000-0000-0000-000000000002",
    "cmc": 0.0,
    "mana_cost": "",
    "type_line": "Basic Land — Forest",
    "oracle_text": "({T}: Add {G}.)",
    "colors": [],
    "color_identity": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal"},
}
PARTNER: dict[str, Any] = {
    "name": "Pir, Imaginative Rascal",
    "oracle_id": "00000000-0000-0000-0000-000000000003",
    "cmc": 2.0,
    "mana_cost": "{1}{G}",
    "type_line": "Legendary Creature — Human",
    "oracle_text": "Partner with Toothy, Imaginary Friend\nIf one or more counters would be put on a permanent...",
    "colors": ["G"],
    "color_identity": ["G"],
    "keywords": ["Partner with"],
    "legalities": {"commander": "legal"},
}
# Real Scryfall shapes. A split card has both halves on one face: the card object carries the
# combined colours and mana value, the halves only name, cost, type and text.
SPLIT: dict[str, Any] = {
    "name": "Wear // Tear",
    "oracle_id": "00000000-0000-0000-0000-000000000004",
    "layout": "split",
    "cmc": 3.0,
    "mana_cost": "{1}{R} // {W}",
    "type_line": "Instant // Instant",
    "colors": ["R", "W"],
    "color_identity": ["R", "W"],
    "keywords": ["Fuse"],
    "legalities": {"commander": "legal"},
    "card_faces": [
        {
            "name": "Wear",
            "mana_cost": "{1}{R}",
            "oracle_text": "Destroy target artifact.",
            "type_line": "Instant",
        },
        {
            "name": "Tear",
            "mana_cost": "{W}",
            "oracle_text": "Destroy target enchantment.",
            "type_line": "Instant",
        },
    ],
}
# A transform card has a front and a back face: colours and cost live on the faces.
TRANSFORM: dict[str, Any] = {
    "name": "Delver of Secrets // Insectile Aberration",
    "oracle_id": "00000000-0000-0000-0000-000000000005",
    "layout": "transform",
    "cmc": 1.0,
    "type_line": "Creature — Human Wizard // Creature — Human Insect",
    "color_identity": ["U"],
    "keywords": ["Flying", "Transform"],
    "legalities": {"commander": "legal"},
    "card_faces": [
        {
            "name": "Delver of Secrets",
            "mana_cost": "{U}",
            "colors": ["U"],
            "oracle_text": "At the beginning of your upkeep, look at the top card of your library.",
            "type_line": "Creature — Human Wizard",
        },
        {
            "name": "Insectile Aberration",
            "mana_cost": "",
            "colors": ["U"],
            "oracle_text": "Flying",
            "type_line": "Creature — Human Insect",
        },
    ],
}


def _entry(card: dict[str, Any]) -> dict[str, Any]:
    return imp.entry_from_scryfall(card, retrieved_at=NOW, source_url=URL)


def test_a_plain_card_becomes_a_valid_authoritative_entry() -> None:
    entry = _entry(MIND_STONE)
    CardIdentity.model_validate(entry)
    assert entry["oracle_name"] == "Mind Stone"
    assert entry["aliases"] == []
    assert entry["mana_value"] == 2.0
    assert entry["data_quality"] == "authoritative"
    assert entry["is_basic_land"] is False and entry["max_deck_copies"] == 1
    assert entry["can_be_commander"] is False
    provenance = entry["provenance"][0]
    assert provenance["source_type"] == "scryfall_api" and provenance["retrieved_at"] == NOW


def test_a_basic_land_may_be_played_in_any_number() -> None:
    entry = _entry(FOREST)
    CardIdentity.model_validate(entry)
    assert entry["is_basic_land"] is True and entry["max_deck_copies"] is None


def test_a_legendary_creature_can_be_commander_and_names_its_partner() -> None:
    entry = _entry(PARTNER)
    CardIdentity.model_validate(entry)
    assert entry["can_be_commander"] is True
    assert entry["partner_with"] == ["Toothy, Imaginary Friend"]


def test_a_split_card_keeps_both_halves_on_one_card_and_the_front_cost_and_alias() -> None:
    entry = _entry(SPLIT)
    CardIdentity.model_validate(entry)
    assert entry["aliases"] == ["Wear"]
    assert entry["mana_cost"] == "{1}{R}"  # one half, as the drift report compares it
    assert entry["mana_value"] == 3.0  # the card's combined value, not the front half's
    assert entry["colors"] == ["R", "W"]  # both halves are on the card
    assert entry["oracle_text"] == "Destroy target artifact.\n//\nDestroy target enchantment."


def test_a_transform_card_takes_cost_and_colours_from_its_front_face() -> None:
    entry = _entry(TRANSFORM)
    CardIdentity.model_validate(entry)
    assert entry["aliases"] == ["Delver of Secrets"]
    assert entry["mana_cost"] == "{U}" and entry["mana_value"] == 1.0
    assert entry["colors"] == ["U"] and entry["color_identity"] == ["U"]


def _catalog(names: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "0.2.0",
        "catalog_scope": "Cards of the current decks.",
        "cards": [
            {**_entry({**MIND_STONE, "name": n, "oracle_id": f"id-{i}"})}
            for i, n in enumerate(names)
        ],
    }


def test_missing_names_skips_known_names_and_aliases_and_repeats() -> None:
    catalog = _catalog(["Sol Ring"])
    catalog["cards"][0]["aliases"] = ["Ring Of Sol"]
    wanted = ["sol ring", "Mind Stone", "Mind Stone", "ring of sol", "Forest"]
    assert imp.missing_names(catalog, wanted) == ["Mind Stone", "Forest"]


def test_merged_catalog_is_sorted_and_says_once_that_cards_come_on_demand() -> None:
    catalog = _catalog(["Sol Ring"])
    once = imp.merged_catalog(catalog, [_entry(MIND_STONE)])
    assert [c["oracle_name"] for c in once["cards"]] == ["Mind Stone", "Sol Ring"]
    assert once["catalog_scope"].count("import_oracle_cards.py") == 1
    twice = imp.merged_catalog(once, [_entry(FOREST)])
    assert twice["catalog_scope"].count("import_oracle_cards.py") == 1
    assert imp.merged_catalog(catalog, [])["catalog_scope"] == catalog["catalog_scope"]


def _write_catalog(path: Path, names: list[str]) -> None:
    path.write_text(
        json.dumps(_catalog(names), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def test_main_adds_only_the_missing_cards_and_changes_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "oracle_subset.json"
    _write_catalog(path, ["Sol Ring"])
    before = json.loads(path.read_text(encoding="utf-8"))
    asked: list[list[str]] = []

    def fake_fetch(names: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
        asked.append(list(names))
        return {"Mind Stone": MIND_STONE}, []

    monkeypatch.setattr(imp, "fetch_cards", fake_fetch)
    code = imp.main(["--catalog", str(path), "--name", "Mind Stone", "--name", "Sol Ring"])
    assert code == 0
    assert asked == [["Mind Stone"]]
    after = json.loads(path.read_text(encoding="utf-8"))
    assert [c["oracle_name"] for c in after["cards"]] == ["Mind Stone", "Sol Ring"]
    assert after["cards"][1] == before["cards"][0]  # the existing entry is verbatim
    assert after["schema_version"] == before["schema_version"]
    assert "added 1 card(s): Mind Stone" in capsys.readouterr().out
    CardCatalog.from_json(path)  # the written file loads: no duplicate identity, no ambiguous alias


def test_a_second_run_finds_nothing_to_do(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "oracle_subset.json"
    _write_catalog(path, ["Sol Ring"])
    monkeypatch.setattr(imp, "fetch_cards", lambda names: ({n: MIND_STONE for n in names}, []))
    assert imp.main(["--catalog", str(path), "--name", "Mind Stone"]) == 0
    first = path.read_text(encoding="utf-8")

    def refuse(names: list[str]) -> Any:
        raise AssertionError("nothing should be fetched")

    monkeypatch.setattr(imp, "fetch_cards", refuse)
    assert imp.main(["--catalog", str(path), "--name", "Mind Stone"]) == 0
    assert path.read_text(encoding="utf-8") == first


def test_dry_run_writes_and_fetches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "oracle_subset.json"
    _write_catalog(path, ["Sol Ring"])
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        imp, "fetch_cards", lambda names: (_ for _ in ()).throw(AssertionError("no fetch"))
    )
    assert imp.main(["--catalog", str(path), "--name", "Mind Stone", "--dry-run"]) == 0
    assert path.read_text(encoding="utf-8") == before
    assert "would fetch 1 card(s): Mind Stone" in capsys.readouterr().out


def test_a_card_scryfall_does_not_know_is_reported_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "oracle_subset.json"
    _write_catalog(path, ["Sol Ring"])
    monkeypatch.setattr(
        imp, "fetch_cards", lambda names: ({"Mind Stone": MIND_STONE}, ["Nonexistent Card"])
    )
    code = imp.main(["--catalog", str(path), "--name", "Mind Stone", "--name", "Nonexistent Card"])
    assert code == 1
    assert "Mind Stone" in path.read_text(encoding="utf-8")  # the known card is still added
    assert "Nonexistent Card" in capsys.readouterr().err


def test_names_file_and_deck_files_are_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "oracle_subset.json"
    _write_catalog(path, ["Sol Ring"])
    names_file = tmp_path / "names.txt"
    names_file.write_text("Mind Stone\n\n  Forest  \n", encoding="utf-8")
    asked: list[list[str]] = []

    def fake_fetch(names: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
        asked.append(list(names))
        return {"Mind Stone": MIND_STONE, "Forest": FOREST}, []

    monkeypatch.setattr(imp, "fetch_cards", fake_fetch)
    assert imp.main(["--catalog", str(path), "--names-file", str(names_file)]) == 0
    assert asked == [["Mind Stone", "Forest"]]
    deck = imp.wanted_names([ROOT / "data/decks/rogshai_current.json"], [], [])
    assert "Ishai, Ojutai Dragonspeaker" in deck and "Rograkh, Son of Rohgahh" in deck


def test_main_needs_something_to_import(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stopped:
        imp.main(["--catalog", str(tmp_path / "x.json")])
    assert stopped.value.code == 2


# --- deck overlays: the tools load them next to the catalog -----------------------------------


def _overlay(path: Path, names: list[str]) -> Path:
    path.write_text(json.dumps(_catalog(names)), encoding="utf-8")
    return path


def test_cards_of_a_deck_overlay_are_known_and_not_imported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # An imported card that an overlay also defines would be a "duplicate conflicting card
    # identity" for the code that loads both.
    catalog_path = tmp_path / "oracle_subset.json"
    _write_catalog(catalog_path, ["Sol Ring"])
    overlay = _overlay(tmp_path / "deck_card_catalog_overrides.json", ["Mind Stone"])
    monkeypatch.setattr(
        imp, "fetch_cards", lambda names: (_ for _ in ()).throw(AssertionError("no fetch"))
    )
    code = imp.main(
        ["--catalog", str(catalog_path), "--overlay", str(overlay), "--name", "Mind Stone"]
    )
    assert code == 0
    assert "already in the catalog or its deck overlay" in capsys.readouterr().out
    assert [c["oracle_name"] for c in json.loads(catalog_path.read_text())["cards"]] == ["Sol Ring"]


def test_an_overlay_card_is_skipped_even_when_scryfall_returns_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog_path = tmp_path / "oracle_subset.json"
    _write_catalog(catalog_path, ["Sol Ring"])
    overlay = _overlay(tmp_path / "o.json", ["Forest"])
    monkeypatch.setattr(
        imp, "fetch_cards", lambda names: ({"Mind Stone": MIND_STONE, "Forest": FOREST}, [])
    )
    imp.main(
        [
            "--catalog", str(catalog_path), "--overlay", str(overlay),
            "--name", "Mind Stone", "--name", "Forest",
        ]
    )  # fmt: skip
    names = [c["oracle_name"] for c in json.loads(catalog_path.read_text())["cards"]]
    assert names == ["Mind Stone", "Sol Ring"]


def test_only_the_repository_catalog_gets_the_repository_overlays(tmp_path: Path) -> None:
    overlays = imp.default_overlays(imp.CATALOG)
    assert ROOT / "data/decks/rogshai_current_card_catalog_overrides.json" in overlays
    assert imp.default_overlays(tmp_path / "other.json") == []


def test_every_card_of_the_own_deck_is_known_to_the_catalog_and_its_overlay() -> None:
    # The effective catalog of the tools is the subset plus the deck overlay; asking the importer
    # for the own deck must find nothing to fetch (no network).
    catalog = json.loads(imp.CATALOG.read_text(encoding="utf-8"))
    overlaid = imp.overlay_keys(imp.default_overlays(imp.CATALOG))
    wanted = imp.wanted_names([ROOT / "data/decks/rogshai_current.json"], [], [])
    assert imp.missing_names(catalog, wanted, overlaid) == []
    assert imp.missing_names(catalog, wanted)  # without the overlay the subset alone lacks some
