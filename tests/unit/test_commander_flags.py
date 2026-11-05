"""Game Changers and Commander bans from a local Scryfall bulk file (E11, R2-01).

No network: the bulk file is a hand-made fixture and every socket is closed for these tests.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import socket
from pathlib import Path
from typing import Any

import pytest

from commander_lab.cards import commander_flags as cf
from commander_lab.cards.normalize import oracle_lookup_key

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "build_commander_flags_under_test", ROOT / "scripts" / "build_commander_flags.py"
)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def _card(
    name: str, n: int, *, commander: str = "legal", game_changer: bool = False
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "oracle_id": f"00000000-0000-0000-0000-{n:012d}",
        "legalities": {"commander": commander},
    }
    if game_changer:
        row["game_changer"] = True
    return row


BULK_CARDS = [
    _card("Rhystic Study", 1, game_changer=True),
    _card("Tergrid, God of Fright // Tergrid's Lantern", 2, game_changer=True),
    _card("Cyclonic Rift", 3, game_changer=True),
    _card("Dockside Extortionist", 4, commander="banned"),
    _card("Sol Ring", 5),
    _card("Mind Stone", 6),
    _card("Plains", 7),
    _card("Silver-Border Joke", 8, commander="not_legal"),
]


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the flags code must not open a network connection")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def bulk(tmp_path: Path) -> Path:
    path = tmp_path / "oracle-cards-20261101120000.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for card in BULK_CARDS:
            handle.write(json.dumps(card) + "\n")
    return path


@pytest.fixture
def flags_file(bulk: Path, tmp_path: Path) -> Path:
    out = tmp_path / "commander_flags.json"
    out.write_text(builder.render(cf.derive_flags(bulk)), encoding="utf-8")
    return out


def test_derive_collects_game_changers_and_bans_with_the_bulk_identity(bulk: Path) -> None:
    payload = cf.derive_flags(bulk)
    assert [row["name"] for row in payload["game_changers"]] == [
        "Cyclonic Rift",
        "Rhystic Study",
        "Tergrid, God of Fright // Tergrid's Lantern",
    ]
    assert [row["name"] for row in payload["commander_banned"]] == ["Dockside Extortionist"]
    source = payload["source"]
    assert source["data_as_of"] == "2026-11-01T12:00:00Z"
    assert source["card_count"] == len(BULK_CARDS)
    assert source["commander_legality_counts"] == {"banned": 1, "legal": 6, "not_legal": 1}
    assert source["bulk_sha256"] == cf._sha256_file(bulk)


def test_a_deck_with_three_game_changers_is_labelled_three(flags_file: Path) -> None:
    flags = cf.load_flags(flags_file)
    label = cf.label_deck(
        [
            "Rhystic Study",
            "Rhystic Study",  # a repeated line is still one card
            "Tergrid, God of Fright",  # a deck may name a double-faced card by its front face
            "cyclonic rift",
            "Sol Ring",
            "Mind Stone",
            "Plains",
            "Card The Bulk Never Heard Of",
        ],
        flags,
    )
    assert label.game_changer_count == 3
    assert label.game_changers == (
        "Cyclonic Rift",
        "Rhystic Study",
        "Tergrid, God of Fright // Tergrid's Lantern",
    )
    assert label.commander_banned == ()
    assert label.data_as_of == "2026-11-01T12:00:00Z"


def test_banned_cards_are_listed_apart_from_game_changers(flags_file: Path) -> None:
    label = cf.label_deck(["Dockside Extortionist", "Sol Ring"], cf.load_flags(flags_file))
    assert label.game_changer_count == 0
    assert label.commander_banned == ("Dockside Extortionist",)


def test_the_label_states_its_own_scope(flags_file: Path) -> None:
    label = cf.label_deck(["Sol Ring"], cf.load_flags(flags_file))
    assert "Not a Commander Brackets assessment" in label.scope
    assert label.as_dict()["game_changer_count"] == 0


def test_a_bulk_file_with_another_name_is_refused_not_dated_by_guess(tmp_path: Path) -> None:
    path = tmp_path / "cards.jsonl"
    path.write_text(json.dumps(BULK_CARDS[0]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="oracle-cards-YYYYMMDDHHMMSS"):
        cf.derive_flags(path)


def test_an_empty_bulk_file_is_an_error_not_an_empty_flag_set(tmp_path: Path) -> None:
    path = tmp_path / "oracle-cards-20261101120000.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="holds no cards"):
        cf.derive_flags(path)


def test_a_malformed_flags_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "commander_flags.json"
    path.write_text(json.dumps({"schema": "other"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected schema"):
        cf.load_flags(path)


def test_build_check_detects_a_stale_file(bulk: Path, flags_file: Path) -> None:
    assert builder.main(["--bulk", str(bulk), "--out", str(flags_file), "--check"]) == 0
    flags_file.write_text(flags_file.read_text(encoding="utf-8").replace("Rift", "Rifts"), "utf-8")
    assert builder.main(["--bulk", str(bulk), "--out", str(flags_file), "--check"]) == 1


def test_the_committed_file_is_loadable_and_names_its_bulk() -> None:
    flags = cf.load_flags()
    assert flags.game_changers
    assert flags.commander_banned
    assert str(flags.source["bulk_file"]).startswith("oracle-cards-")
    assert len(str(flags.source["bulk_sha256"])) == 64


def test_the_committed_bans_agree_with_the_catalog_legalities() -> None:
    """Wrong-reason control: the catalog's own Commander legality, read from a second source,
    must agree with the bulk-derived ban list for every card the catalog holds."""
    flags = cf.load_flags()
    catalog = json.loads((ROOT / "data/cards/oracle_subset.json").read_text(encoding="utf-8"))
    checked = 0
    for card in catalog["cards"]:
        status = (card.get("legalities") or {}).get("commander")
        if status not in {"legal", "banned"}:
            continue
        keys = {oracle_lookup_key(n) for n in (card["oracle_name"], *card.get("aliases", []))}
        is_banned = bool(keys & set(flags.commander_banned))
        assert is_banned == (status == "banned"), card["oracle_name"]
        checked += 1
    assert checked > 100
