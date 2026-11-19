"""German printed card names in the deck builder search and the deck list import (#1553)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from commander_lab.studio import DataClass, StudioStore, builder, decks, german_names
from commander_lab.studio.german_names import load_german_names, read_german_names

CMD = ["Chulane, Teller of Tales"]
STATIC_DIR = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"

# five German names of the checked-in print files -> Oracle id (read from the files)
FIVE = {
    "Verdammen": "377d31b5-0a48-4d5b-91bd-b5a62d4f7899",  # Condemn
    "Heilige Stärke": "9357de36-f8be-4f49-b2c8-9fe9eaf82b07",  # Holy Strength
    "Simic-Wachstumskammer": "046f5783-cc7b-416a-8cf6-2bcef9c2cc1a",
    "Rakdos-Gildeneingang": "361f534b-39d1-4421-b5a8-d3813c62f86d",
    "Finsterboggart": "9cc3b91b-ad70-4b01-b718-fda3819f84d0",  # Eclipsed Boggart
}
ZWANG = {
    "33d405ea-7a9a-4970-b70f-9c05d90dd6f0",  # Duress
    "68413337-ddb9-46f8-8c8e-f3d2d672c652",  # Coercion
}


def _row(oracle_id: str, name: str, german: list[str]) -> str:
    foreign = [{"language": "German", "name": n} for n in german]
    foreign.append({"language": "French", "name": "Autre"})
    return json.dumps({"oracle_id": oracle_id, "name": name, "foreign_names": foreign})


def test_five_german_names_resolve_to_their_oracle_id() -> None:
    names = load_german_names()
    assert len(FIVE) == 5
    for german, oracle_id in FIVE.items():
        assert names.oracle_ids(german) == {oracle_id}
        assert names.oracle_ids(german.upper()) == {oracle_id}  # case does not matter


def test_a_name_of_two_cards_returns_both() -> None:
    names = load_german_names()
    assert names.oracle_ids("Zwang") == ZWANG
    assert {names.oracle_name(i) for i in ZWANG} == {"Duress", "Coercion"}


def test_split_card_faces_resolve_to_the_card() -> None:
    names = load_german_names()
    assert names.oracle_ids("Abrieb") == names.oracle_ids("Abnutzung") != frozenset()


def test_every_card_of_the_collection_has_a_german_name() -> None:
    # 1.655 of 1.655 identities (data/research/deckbuilder_1655/README.md); an identity
    # without one would be unknown (None), never an empty list.
    names = load_german_names()
    assert names.card_count == 1655
    assert names.names_for("no-such-oracle-id") is None
    assert names.names_for(None) is None


def test_reader_orders_parts_numerically_and_skips_damage(tmp_path: Path) -> None:
    (tmp_path / "mtgjson_printings_1655_10.jsonl").write_text(
        _row("o2", "Two", ["Zwei"]) + "\n", encoding="utf-8"
    )
    (tmp_path / "mtgjson_printings_1655_2.jsonl").write_text(
        "not json\n" + _row("o1", "One", ["Eins", "Eins", "Ein"]) + "\n[1]\n", encoding="utf-8"
    )
    (tmp_path / "other.jsonl").write_text(_row("o3", "Three", ["Drei"]), encoding="utf-8")
    names = read_german_names(tmp_path)
    assert names.names == {"o1": ("Eins", "Ein"), "o2": ("Zwei",)}
    assert names.names_for("o3") is None
    assert read_german_names(tmp_path / "missing").card_count == 0


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StudioStore:
    folder = tmp_path / "prints"
    folder.mkdir()
    (folder / "mtgjson_printings_1655_1.jsonl").write_text(
        "\n".join(
            [
                _row("oid-c-sol", "Sol Ring", ["Sol-Ring"]),
                _row("oid-c-duress", "Duress", ["Zwang"]),
                _row("oid-c-coercion", "Coercion", ["Zwang"]),
                _row("oid-c-counter", "Counterspell", ["Gegenzauber"]),
                _row("oid-c-island", "Island", ["Insel"]),
                _row("oid-pub-only", "Wrath of God", ["Zorn Gottes"]),
                _row("oid-nowhere", "Nowhere Card", ["Nirgendwo"]),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    german = read_german_names(folder)
    monkeypatch.setattr(decks, "load_german_names", lambda: german)
    store = StudioStore.open(tmp_path / "studio")
    src = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE, title="coll.csv", sha256="a" * 64, snapshot_date="x"
    )
    cards = [
        ("cmd-chulane", "Chulane, Teller of Tales", "GWU"),
        ("c-sol", "Sol Ring", ""),
        ("c-duress", "Duress", "B"),
        ("c-coercion", "Coercion", "B"),
        ("c-counter", "Counterspell", "U"),
        ("c-island", "Island", "U"),
    ]
    with store.connection as db:
        for cid, name, identity in cards:
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, ?, '{1}', 1, 'Card', '', 0, 1, '2026-11-10', 'scryfall', ?)",
                (cid, "oid-" + cid, name, identity, src),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 2, 0, 2, 1, 1, '2026-11-10', ?)", (cid, src)
            )
        db.execute(
            "INSERT INTO scryfall_card (oracle_id, scryfall_id, name, front_name, layout, "
            "color_identity, commander_legality, keywords, produced_mana, source_id) "
            "VALUES ('oid-pub-only', 'sid', 'Wrath of God', 'Wrath of God', 'normal', 'W', "
            "'legal', '', '', ?)",
            (src,),
        )
    return store


def _summary(parsed: dict[str, object]) -> dict[str, int]:
    summary = parsed["summary"]
    assert isinstance(summary, dict)
    ambiguous = parsed["ambiguous"]
    assert isinstance(ambiguous, list)
    german = parsed["german_name_lines"]
    assert isinstance(german, int)
    return {
        **{str(k): int(v) for k, v in summary.items()},
        "german_name_lines": german,
        "ambiguous_lines": len(ambiguous),
    }


def test_german_name_resolves_and_is_shown_under_the_oracle_name(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "1 Sol-Ring\n1 gegenzauber\n1 Insel")
    matched = parsed["in_collection"]
    assert isinstance(matched, list)
    assert [(m["card_id"], m["name"]) for m in matched] == [
        ("c-sol", "Sol Ring"),
        ("c-counter", "Counterspell"),
        ("c-island", "Island"),
    ]
    summary = _summary(parsed)
    assert summary["in_collection_cards"] == 3
    assert summary["german_name_lines"] == 3
    assert summary["ambiguous_lines"] == 0


def test_english_names_are_unchanged_and_not_counted_as_german(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "1 Sol Ring\n1 Counterspell")
    summary = _summary(parsed)
    assert summary["in_collection_cards"] == 2
    assert summary["german_name_lines"] == 0
    assert parsed["ambiguous"] == []


def test_ambiguous_german_name_is_reported_with_both_cards_and_not_guessed(
    store: StudioStore,
) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "2 Zwang\n1 Sol Ring")
    ambiguous = parsed["ambiguous"]
    assert isinstance(ambiguous, list) and len(ambiguous) == 1
    entry = ambiguous[0]
    assert entry["status"] == "mehrdeutig" and entry["quantity"] == 2 and entry["line"] == 1
    assert {(c["name"], c["card_id"]) for c in entry["candidates"]} == {
        ("Duress", "c-duress"),
        ("Coercion", "c-coercion"),
    }
    summary = _summary(parsed)
    assert summary["in_collection_cards"] == 1  # only Sol Ring; the 2 x Zwang count nowhere
    assert summary["not_in_collection_cards"] == 0
    assert summary["ambiguous_lines"] == 1


def test_german_name_of_a_card_outside_the_collection_stays_neutral(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "1 Zorn Gottes\n1 Nirgendwo")
    missing = parsed["not_in_collection"]
    assert isinstance(missing, list)
    assert [(m["name"], m["status"]) for m in missing] == [
        ("Wrath of God", "nicht in deiner Sammlung"),
        ("Nowhere Card", "nicht in deiner Sammlung"),
    ]
    assert _summary(parsed)["not_in_collection_cards"] == 2


def test_unknown_name_is_not_resolved(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "1 Gibt es nicht")
    assert _summary(parsed)["german_name_lines"] == 0
    assert _summary(parsed)["not_in_collection_cards"] == 1


def test_pool_alias_names(monkeypatch: pytest.MonkeyPatch) -> None:
    german = german_names.GermanNames(
        names={"o1": ("Sol Ring", "Sol-Ring"), "o2": ("Zwei",)}, english={}, by_key={}
    )
    monkeypatch.setattr(builder, "load_german_names", lambda: german)
    assert builder._german_alias_names("o1", "Sol Ring") == ["Sol-Ring"]  # not the Oracle name
    assert builder._german_alias_names("o2", "Two") == ["Zwei"]
    assert builder._german_alias_names("o9", "Nine") is None  # unknown, not "none"
    assert builder._german_alias_names(None, "Nine") is None


def _node(script: str) -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, cwd=STATIC_DIR
    )
    return done.stdout.strip()


def test_search_ranks_german_names_and_keeps_english_behaviour() -> None:
    out = _node(
        """
const S = require('./search.js');
const condemn = { name: "Condemn", type_line: "Instant", text: "", names_de: ["Verdammen"] };
const duress = { name: "Duress", type_line: "Sorcery", text: "", names_de: ["Zwang"] };
const coercion = { name: "Coercion", type_line: "Sorcery", text: "", names_de: ["Zwang"] };
const plain = { name: "Sol Ring", type_line: "Artifact", text: "" };
const r = (card, q) => S.rank(card, q);
console.log(JSON.stringify([
  r(condemn, "verdammen"), r(condemn, "verd"), r(condemn, "ammen"), r(condemn, "xyz"),
  r(duress, "Zwang"), r(coercion, "Zwang"), r(plain, "Zwang"),
  r(condemn, 'n:verdammen'), r(condemn, '"verdammen"'),
  r(plain, "sol"), r(plain, "ring"), r(plain, "tifact"),
  S.sortByRank([plain, coercion, duress, condemn], "zwang").map((c) => c.name),
]));
"""
    )
    assert json.loads(out) == [
        0,
        1,
        3,
        None,
        0,
        0,
        None,
        0,
        0,
        1,
        2,
        4,
        ["Coercion", "Duress"],
    ]
