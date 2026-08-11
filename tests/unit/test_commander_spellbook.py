from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.commander_spellbook import (
    CommanderSpellbookError,
    build_find_my_combos_payload,
    combo_snapshot_summary,
    load_commander_spellbook_snapshot,
    sync_commander_spellbook_snapshot,
)
from commander_lab.engine.structural import load_project_structural_decks

ROOT = Path(__file__).resolve().parents[2]


def _response() -> dict:
    return {
        "count": None,
        "next": None,
        "previous": None,
        "results": {
            "identity": "URW",
            "included": [
                {
                    "id": "test-combo",
                    "uses": [
                        {"card": {"name": "Kediss, Emberclaw Familiar"}},
                        {"card": {"name": "Ishai, Ojutai Dragonspeaker"}},
                    ],
                    "produces": [{"feature": {"name": "Test finish"}}],
                    "description": "Fixture only.",
                }
            ],
            "includedByChangingCommanders": [],
            "almostIncluded": [],
            "almostIncludedByAddingColors": [],
            "almostIncludedByChangingCommanders": [],
            "almostIncludedByAddingColorsAndChangingCommanders": [],
        },
    }


def test_payload_keeps_commanders_separate_from_main() -> None:
    deck = load_project_structural_decks(ROOT)["rogshai/current"]
    payload = build_find_my_combos_payload(deck)
    commanders = {row["card"] for row in payload["commanders"]}
    main = {row["card"] for row in payload["main"]}
    assert commanders == {"Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"}
    assert commanders.isdisjoint(main)
    assert len(payload["main"]) + len(payload["commanders"]) == 100


def test_explicit_sync_writes_hash_bound_offline_snapshot(tmp_path: Path) -> None:
    deck = load_project_structural_decks(ROOT)["rogshai/current"]
    calls = 0

    def fetcher(payload: bytes, timeout: float, max_bytes: int) -> bytes:
        nonlocal calls
        calls += 1
        assert timeout == 3.0
        assert max_bytes == 100_000
        request = json.loads(payload)
        assert request["commanders"]
        return json.dumps(_response()).encode("utf-8")

    path = tmp_path / "spellbook.json"
    result = sync_commander_spellbook_snapshot(
        deck,
        path,
        timeout=3.0,
        max_response_bytes=100_000,
        fetcher=fetcher,
    )
    assert calls == 1
    assert result["included_combo_count"] == 1
    snapshot = load_commander_spellbook_snapshot(path, expected_deck_hash=deck.deck_hash)
    summary = combo_snapshot_summary(snapshot)
    assert summary["included"][0]["id"] == "test-combo"
    assert summary["included"][0]["produces"] == ["Test finish"]
    assert "!= proof" in summary["truth_boundary"]


def test_snapshot_fails_closed_on_deck_or_response_tampering(tmp_path: Path) -> None:
    deck = load_project_structural_decks(ROOT)["rogshai/current"]

    def fetcher(payload: bytes, timeout: float, max_bytes: int) -> bytes:
        del payload, timeout, max_bytes
        return json.dumps(_response()).encode("utf-8")

    path = tmp_path / "spellbook.json"
    sync_commander_spellbook_snapshot(deck, path, fetcher=fetcher)
    with pytest.raises(CommanderSpellbookError, match="deck hash is stale"):
        load_commander_spellbook_snapshot(path, expected_deck_hash="0" * 64)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["response"]["results"]["identity"] = "C"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommanderSpellbookError, match="response hash mismatch"):
        load_commander_spellbook_snapshot(path, expected_deck_hash=deck.deck_hash)
