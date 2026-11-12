"""Unit tests verifying integrity of Scryfall research artifacts (rulings & prices)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

RULINGS_PATH = Path("data/research/scryfall_rulings_1414.jsonl")
PRICES_PATH = Path("data/research/scryfall_prices_20261112.csv")


def test_scryfall_rulings_artifact_integrity() -> None:
    assert RULINGS_PATH.is_file(), "Rulings artifact must exist"

    total_rulings = 0
    oracle_ids: set[str] = set()
    with RULINGS_PATH.open("r", encoding="utf-8") as f:
        for _idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            ruling = json.loads(line_str)
            assert "oracle_id" in ruling
            assert "source" in ruling
            assert "published_at" in ruling
            assert "comment" in ruling
            assert ruling["source"] in ("wotc", "scryfall")
            oracle_ids.add(ruling["oracle_id"])
            total_rulings += 1

    assert total_rulings == 2669, f"Expected 2669 rulings, got {total_rulings}"
    assert len(oracle_ids) == 822, f"Expected 822 cards with rulings, got {len(oracle_ids)}"


def test_scryfall_prices_artifact_integrity() -> None:
    assert PRICES_PATH.is_file(), "Prices artifact must exist"

    with PRICES_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1414, f"Expected 1414 price rows, got {len(rows)}"

    has_eur = sum(1 for r in rows if r.get("eur"))
    has_any_eur = sum(1 for r in rows if r.get("eur") or r.get("eur_foil"))
    has_usd = sum(1 for r in rows if r.get("usd"))
    has_any_usd = sum(1 for r in rows if r.get("usd") or r.get("usd_foil"))
    has_any_price = sum(
        1 for r in rows if any(r.get(k) for k in ("eur", "eur_foil", "usd", "usd_foil", "tix"))
    )

    assert has_eur == 1317, f"Expected 1317 regular EUR prices, got {has_eur}"
    assert has_any_eur == 1379, f"Expected 1379 total EUR prices, got {has_any_eur}"
    assert has_usd == 1315, f"Expected 1315 regular USD prices, got {has_usd}"
    assert has_any_usd == 1388, f"Expected 1388 total USD prices, got {has_any_usd}"
    assert has_any_price == 1398, f"Expected 1398 cards with any price, got {has_any_price}"
    assert (len(rows) - has_any_price) == 16, "Expected exactly 16 cards without price"
