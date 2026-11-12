"""Unit tests verifying integrity and validity of Scryfall rulings research artifact."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

RULINGS_PATH = Path("data/research/scryfall_rulings_1414.jsonl")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_scryfall_rulings_artifact_integrity_and_ranges() -> None:
    assert RULINGS_PATH.is_file(), "Rulings artifact must exist"

    total_rulings = 0
    oracle_ids: set[str] = set()
    with RULINGS_PATH.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            ruling = json.loads(line_str)
            assert "oracle_id" in ruling, f"Row {idx} missing oracle_id"
            assert "source" in ruling, f"Row {idx} missing source"
            assert "published_at" in ruling, f"Row {idx} missing published_at"
            assert "comment" in ruling, f"Row {idx} missing comment"

            # Value range and format validation
            oracle_id = ruling["oracle_id"]
            assert UUID_RE.match(oracle_id), f"Invalid oracle_id format at row {idx}: {oracle_id}"

            source = ruling["source"]
            assert source in ("wotc", "scryfall"), f"Unexpected source at row {idx}: {source}"

            pub_date = ruling["published_at"]
            assert DATE_RE.match(pub_date), f"Invalid published_at format at row {idx}: {pub_date}"
            parsed_date = date.fromisoformat(pub_date)
            assert 1993 <= parsed_date.year <= 2026, (
                f"Published date out of reasonable range at row {idx}: {pub_date}"
            )

            comment = ruling["comment"]
            assert isinstance(comment, str) and len(comment.strip()) >= 5, (
                f"Comment too short or invalid type at row {idx}: {comment[:30]}"
            )

            oracle_ids.add(oracle_id)
            total_rulings += 1

    assert total_rulings == 2669, f"Expected 2669 rulings, got {total_rulings}"
    assert len(oracle_ids) == 822, f"Expected 822 cards with rulings, got {len(oracle_ids)}"
