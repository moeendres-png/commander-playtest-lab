"""Unit tests for #1412 TopDeck Mit/Ohne (With-vs-Without) tournament conversion."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, strength, tournament_conversion
from commander_lab.studio.web import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPDECK_20261115 = REPO_ROOT / "data" / "research" / "topdeck_20261115"


def _write_deck_csv(
    path: Path,
    decks: list[dict[str, object]],
) -> None:
    fieldnames = [
        "tournament",
        "date",
        "player",
        "wins",
        "draws",
        "losses",
        "card_name",
        "quantity",
        "section",
        "top_cut",
        "wins_bracket",
        "losses_bracket",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for deck in decks:
            commanders = deck.get("commanders", ["Test Commander"])
            assert isinstance(commanders, list)
            for cmd in commanders:
                writer.writerow(
                    {
                        "tournament": deck["tournament"],
                        "date": deck["date"],
                        "player": deck["player"],
                        "wins": deck.get("wins", 2),
                        "draws": deck.get("draws", 0),
                        "losses": deck.get("losses", 1),
                        "card_name": cmd,
                        "quantity": 1,
                        "section": "commander",
                        "top_cut": deck.get("top_cut", 4),
                        "wins_bracket": deck.get("wins_bracket", ""),
                        "losses_bracket": deck.get("losses_bracket", ""),
                    }
                )
            cards = deck.get("cards", [])
            assert isinstance(cards, list)
            for card in cards:
                writer.writerow(
                    {
                        "tournament": deck["tournament"],
                        "date": deck["date"],
                        "player": deck["player"],
                        "wins": deck.get("wins", 2),
                        "draws": deck.get("draws", 0),
                        "losses": deck.get("losses", 1),
                        "card_name": card,
                        "quantity": 1,
                        "section": "main",
                        "top_cut": deck.get("top_cut", 4),
                        "wins_bracket": deck.get("wins_bracket", ""),
                        "losses_bracket": deck.get("losses_bracket", ""),
                    }
                )
            for sb_card in deck.get("sideboard", []):  # type: ignore[union-attr]
                writer.writerow(
                    {
                        "tournament": deck["tournament"],
                        "date": deck["date"],
                        "player": deck["player"],
                        "wins": deck.get("wins", 2),
                        "draws": deck.get("draws", 0),
                        "losses": deck.get("losses", 1),
                        "card_name": sb_card,
                        "quantity": 1,
                        "section": "sideboard",
                        "top_cut": deck.get("top_cut", 4),
                        "wins_bracket": deck.get("wins_bracket", ""),
                        "losses_bracket": deck.get("losses_bracket", ""),
                    }
                )


def test_dedup_topcut_filtering_and_player_privacy(tmp_path: Path) -> None:
    decks = [
        # Duplicate across two files for same (tournament, date, player) -> counted once
        {
            "tournament": "Event A",
            "date": "2026-11-01",
            "player": "Alice Sensitive Name",
            "top_cut": 4,
            "wins_bracket": 1,
            "losses_bracket": 1,
            "commanders": ["Test Commander"],
            "cards": ["Sol Ring", "Rhystic Study"],
            "sideboard": ["Sideboard Foil"],
        },
        # Converted with 0 wins, 1 loss in bracket (played > 0 -> reached top cut)
        {
            "tournament": "Event A",
            "date": "2026-11-01",
            "player": "Bob Sensitive",
            "top_cut": 4,
            "wins_bracket": 0,
            "losses_bracket": 1,
            "commanders": ["Test Commander"],
            "cards": ["Sol Ring"],
        },
        # Known non-converted: top_cut=4, wins_bracket=0, losses_bracket=0
        {
            "tournament": "Event A",
            "date": "2026-11-01",
            "player": "Carol Sensitive",
            "top_cut": 4,
            "wins_bracket": 0,
            "losses_bracket": 0,
            "commanders": ["Test Commander"],
            "cards": ["Rhystic Study"],
        },
        # Unknown bracket: top_cut=0 -> excluded from total_known_decks
        {
            "tournament": "Event B",
            "date": "2026-11-02",
            "player": "Dave Sensitive",
            "top_cut": 0,
            "wins_bracket": 0,
            "losses_bracket": 0,
            "commanders": ["Test Commander"],
            "cards": ["Sol Ring"],
        },
        # Unknown bracket: wins_bracket & losses_bracket empty -> excluded from total_known_decks
        {
            "tournament": "Event C",
            "date": "2026-11-03",
            "player": "Eve Sensitive",
            "top_cut": 4,
            "wins_bracket": "",
            "losses_bracket": "",
            "commanders": ["Test Commander"],
            "cards": ["Sol Ring"],
        },
        # Partner pair including Test Commander -> MUST NOT count for single Test Commander
        {
            "tournament": "Event A",
            "date": "2026-11-01",
            "player": "Frank Partner",
            "top_cut": 4,
            "wins_bracket": 1,
            "losses_bracket": 0,
            "commanders": ["Test Commander", "Partner Commander"],
            "cards": ["Sol Ring"],
        },
    ]
    _write_deck_csv(tmp_path / "topdeck_test_commander_decks_1.csv", decks[:3])
    _write_deck_csv(tmp_path / "topdeck_test_commander_decks_2.csv", [decks[0], *decks[3:]])

    result = tournament_conversion.analyze_commander_conversion("Test Commander", tmp_path)
    assert result["commander"] == "Test Commander"
    assert result["cohort"] == "Bracket 5 (Turnier)"
    assert result["data_class"] == "DERIVED_DESCRIPTIVE"
    assert result["total_decks"] == 5  # Alice deduplicated, Frank partner excluded
    assert result["total_known_decks"] == 3  # Alice, Bob, Carol
    assert result["total_converted_decks"] == 2  # Alice, Bob
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["reason"] == "zu wenig Daten"
    assert result["baseline_conversion_rate"] is None

    by_card = {row["card_name"]: row for row in result["cards"]}
    assert "Sideboard Foil" not in by_card
    assert by_card["Sol Ring"]["with_known"] == 2
    assert by_card["Sol Ring"]["with_converted"] == 2
    assert by_card["Sol Ring"]["without_known"] == 1
    assert by_card["Sol Ring"]["without_converted"] == 0
    assert by_card["Sol Ring"]["with_rate"] is None
    assert by_card["Sol Ring"]["without_rate"] is None
    assert by_card["Sol Ring"]["diff_pp"] is None
    assert by_card["Sol Ring"]["status"] == "INSUFFICIENT_DATA"
    assert by_card["Sol Ring"]["reason"] == "zu wenig Daten"

    serialized = json.dumps(result)
    assert "Sensitive" not in serialized
    assert "Alice" not in serialized


def test_mit_ohne_wilson_and_diff_pp_thresholds(tmp_path: Path) -> None:
    assert tournament_conversion.MIN_CONVERSION == 20
    assert (
        strength.DEFAULT_MIN_DENOMINATORS[strength.MIN_CONVERSION]
        == tournament_conversion.MIN_CONVERSION
    )

    decks: list[dict[str, object]] = []
    # Build 50 known decks:
    # - Card A in decks 0..24 (25 known: 15 converted, 10 not)
    #   and absent in decks 25..49 (25 known: 5 converted, 20 not)
    # - Card B in decks 0..39 (40 known: 20 converted) -> without_known = 10 (< 20!)
    # - Card C in decks 0..9 (10 known: 5 converted) -> with_known = 10 (< 20!)
    for idx in range(50):
        in_a = idx < 25
        in_b = idx < 40
        in_c = idx < 10
        converted = idx < 15 if idx < 25 else idx < 30
        cards = []
        if in_a:
            cards.append("Card A")
        if in_b:
            cards.append("Card B")
        if in_c:
            cards.append("Card C")
        decks.append(
            {
                "tournament": "Grand Prix",
                "date": "2026-11-10",
                "player": f"Liste {idx + 1}",
                "top_cut": 16,
                "wins_bracket": 1 if converted else 0,
                "losses_bracket": 0,
                "commanders": ["Test Commander"],
                "cards": cards,
            }
        )
    _write_deck_csv(tmp_path / "topdeck_test_commander_decks.csv", decks)

    result = tournament_conversion.analyze_commander_conversion("Test Commander", tmp_path)
    assert result["status"] == "OK"
    assert result["reason"] is None
    assert result["total_known_decks"] == 50
    assert result["total_converted_decks"] == 20
    assert result["baseline_conversion_rate"] == pytest.approx(0.40)

    by_card = {row["card_name"]: row for row in result["cards"]}

    card_a = by_card["Card A"]
    assert card_a["status"] == "OK"
    assert card_a["reason"] is None
    assert card_a["with_known"] == 25
    assert card_a["with_converted"] == 15
    assert card_a["with_rate"] == pytest.approx(0.60)
    assert card_a["with_ci_low"] == pytest.approx(strength.wilson_lower(15, 25))
    assert 0.0 <= card_a["with_ci_low"] < card_a["with_rate"] < card_a["with_ci_high"] <= 1.0
    assert card_a["without_known"] == 25
    assert card_a["without_converted"] == 5
    assert card_a["without_rate"] == pytest.approx(0.20)
    assert card_a["without_ci_low"] == pytest.approx(strength.wilson_lower(5, 25))
    assert (
        0.0 <= card_a["without_ci_low"] < card_a["without_rate"] < card_a["without_ci_high"] <= 1.0
    )
    assert card_a["diff_pp"] == pytest.approx(40.0)

    card_b = by_card["Card B"]
    assert card_b["with_known"] == 40
    assert card_b["without_known"] == 10
    assert card_b["with_rate"] == pytest.approx(20 / 40)
    assert card_b["without_rate"] is None
    assert card_b["without_ci_low"] is None
    assert card_b["without_ci_high"] is None
    assert card_b["diff_pp"] is None  # without_known < 20 -> NEVER 0
    assert card_b["status"] == "PARTIAL"
    assert card_b["reason"] == "zu wenig Daten ohne Karte"

    card_c = by_card["Card C"]
    assert card_c["with_known"] == 10
    assert card_c["with_rate"] is None
    assert card_c["with_ci_low"] is None
    assert card_c["without_rate"] is None
    assert card_c["diff_pp"] is None
    assert card_c["status"] == "INSUFFICIENT_DATA"
    assert card_c["reason"] == "zu wenig Daten"


def test_total_known_below_20_never_scores_even_if_without_is_zero(tmp_path: Path) -> None:
    decks = [
        {
            "tournament": "Small Event",
            "date": "2026-11-11",
            "player": f"Liste {i + 1}",
            "top_cut": 4,
            "wins_bracket": 1 if i < 5 else 0,
            "losses_bracket": 0,
            "commanders": ["Small Commander"],
            "cards": ["Sol Ring"],
        }
        for i in range(19)
    ]
    _write_deck_csv(tmp_path / "topdeck_small_commander_decks.csv", decks)

    result = tournament_conversion.analyze_commander_conversion("Small Commander", tmp_path)
    assert result["total_known_decks"] == 19
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["reason"] == "zu wenig Daten"
    assert result["baseline_conversion_rate"] is None
    assert len(result["cards"]) == 1
    row = result["cards"][0]
    assert row["status"] == "INSUFFICIENT_DATA"
    assert row["reason"] == "zu wenig Daten"
    assert row["with_rate"] is None
    assert row["diff_pp"] is None


def test_real_topdeck_20261115_empirical_commanders() -> None:
    assert TOPDECK_20261115.is_dir()

    chulane = tournament_conversion.analyze_commander_conversion(
        "Chulane, Teller of Tales", TOPDECK_20261115
    )
    assert chulane["cohort"] == "Bracket 5 (Turnier)"
    assert chulane["data_class"] == "DERIVED_DESCRIPTIVE"
    assert chulane["total_decks"] == 7
    assert chulane["total_known_decks"] == 3
    assert chulane["total_converted_decks"] == 1
    assert chulane["status"] == "INSUFFICIENT_DATA"
    assert chulane["reason"] == "zu wenig Daten"
    assert chulane["baseline_conversion_rate"] is None
    assert len(chulane["cards"]) > 0
    for card in chulane["cards"]:
        assert card["status"] == "INSUFFICIENT_DATA"
        assert card["reason"] == "zu wenig Daten"
        assert card["with_rate"] is None
        assert card["diff_pp"] is None

    expected_totals = {
        "The Gitrog Monster": (99, 83, 19),
        "Korvold, Fae-Cursed King": (68, 55, 12),
        "Maralen, Fae Ascendant": (35, 28, 3),
    }
    for cmd, (tot, known, conv) in expected_totals.items():
        res = tournament_conversion.analyze_commander_conversion(cmd, TOPDECK_20261115)
        assert res["total_decks"] == tot
        assert res["total_known_decks"] == known
        assert res["total_converted_decks"] == conv
        assert res["status"] == "OK"
        assert res["baseline_conversion_rate"] == pytest.approx(conv / known)
        assert len(res["cards"]) > 0
        for card in res["cards"]:
            assert card["with_known"] + card["without_known"] == known
            assert card["with_converted"] + card["without_converted"] == conv
            if card["status"] == "OK":
                assert card["with_known"] >= 20
                assert card["without_known"] >= 20
                assert card["diff_pp"] == pytest.approx(
                    (card["with_rate"] - card["without_rate"]) * 100.0
                )
            else:
                assert card["diff_pp"] is None


def test_web_route_tournament_conversion(tmp_path: Path, monkeypatch) -> None:
    store = StudioStore.open(tmp_path / "studio")
    store.close()
    monkeypatch.setattr(tournament_conversion, "DEFAULT_RESEARCH_DIR", TOPDECK_20261115)

    with TestClient(create_app(tmp_path / "studio")) as client:
        r_chulane = client.get(
            "/api/tournament-conversion",
            params={"commander": "Chulane, Teller of Tales"},
        )
        assert r_chulane.status_code == 200
        body_c = r_chulane.json()
        assert body_c["status"] == "INSUFFICIENT_DATA"
        assert body_c["reason"] == "zu wenig Daten"
        assert body_c["total_decks"] == 7
        assert body_c["total_known_decks"] == 3

        r_gitrog = client.get(
            "/api/tournament-conversion",
            params={"commander": "The Gitrog Monster"},
        )
        assert r_gitrog.status_code == 200
        body_g = r_gitrog.json()
        assert body_g["status"] == "OK"
        assert body_g["total_known_decks"] == 83
        assert body_g["cohort"] == "Bracket 5 (Turnier)"

        r_missing = client.get(
            "/api/tournament-conversion",
            params={"commander": "Nonexistent Commander"},
        )
        assert r_missing.status_code == 200
        body_m = r_missing.json()
        assert body_m["status"] == "INSUFFICIENT_DATA"
        assert body_m["reason"] == "zu wenig Daten"
        assert body_m["total_known_decks"] == 0
        assert body_m["cards"] == []


def test_anonymized_player_labels_do_not_collide_across_commanders(tmp_path: Path) -> None:
    """Two commander CSVs sharing (tournament, date, 'Liste 1') must never drop or merge decks."""
    _write_deck_csv(
        tmp_path / "topdeck_adrix_decks.csv",
        [
            {
                "tournament": "Liga Mesao Presencial",
                "date": "2026-08-28",
                "player": "Liste 1",
                "top_cut": 4,
                "wins_bracket": 1,
                "losses_bracket": 1,
                "commanders": ["Adrix and Nev, Twincasters"],
                "cards": ["Sol Ring"],
            }
        ],
    )
    _write_deck_csv(
        tmp_path / "topdeck_rootha_decks.csv",
        [
            {
                "tournament": "Liga Mesao Presencial",
                "date": "2026-08-28",
                "player": "Liste 1",
                "top_cut": 4,
                "wins_bracket": 1,
                "losses_bracket": 1,
                "commanders": ["Rootha, Mastering the Moment"],
                "cards": ["Sol Ring"],
            }
        ],
    )
    # Multipart files of the same commander must still deduplicate on the same base stem.
    _write_deck_csv(
        tmp_path / "topdeck_rootha_decks_2.csv",
        [
            {
                "tournament": "Liga Mesao Presencial",
                "date": "2026-08-28",
                "player": "Liste 1",
                "top_cut": 4,
                "wins_bracket": 1,
                "losses_bracket": 1,
                "commanders": ["Rootha, Mastering the Moment"],
                "cards": ["Sol Ring"],
            }
        ],
    )

    res_adrix = tournament_conversion.analyze_commander_conversion(
        "Adrix and Nev, Twincasters", tmp_path
    )
    res_rootha = tournament_conversion.analyze_commander_conversion(
        "Rootha, Mastering the Moment", tmp_path
    )
    assert res_adrix["total_decks"] == 1
    assert res_adrix["total_known_decks"] == 1
    assert res_adrix["total_converted_decks"] == 1
    assert res_rootha["total_decks"] == 1
    assert res_rootha["total_known_decks"] == 1
    assert res_rootha["total_converted_decks"] == 1
