"""Live per-card source coverage over the pinned snapshot (opt-in, env-gated).

Requires ``COMMANDER_LAB_SNAPSHOT_DIR`` (19 canonical originals, out-of-repo)
and ``COMMANDER_LAB_ORACLE_JOIN`` (dated Scryfall join cache from Step B).
Asserts Step B aggregates; engine behavior remains UNKNOWN by construction.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from commander_lab.physical_pool.coverage import build_source_matrix
from commander_lab.physical_pool.snapshot import data_rows, load_snapshot

SNAPSHOT_DIR = os.environ.get("COMMANDER_LAB_SNAPSHOT_DIR", "")
ORACLE_JOIN = os.environ.get("COMMANDER_LAB_ORACLE_JOIN", "")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def matrix():
    if not SNAPSHOT_DIR or not ORACLE_JOIN:
        pytest.skip("COMMANDER_LAB_SNAPSHOT_DIR / COMMANDER_LAB_ORACLE_JOIN not set")
    snapshot = load_snapshot(Path(SNAPSHOT_DIR))
    join = json.loads(Path(ORACLE_JOIN).read_text(encoding="utf-8"))
    verified = _oracle_ids_by_card(snapshot, join["results"])
    knowledge = {
        row.get("card_id"): row
        for row in data_rows(snapshot.rows("FULL_PHYSICAL_CARD_KNOWLEDGE_BASE_CURRENT.jsonl"))
    }
    semantics = {
        row.get("card_id"): row
        for row in data_rows(snapshot.rows("FULL_PHYSICAL_CARD_FUNCTIONAL_SEMANTICS_CURRENT.jsonl"))
    }
    return build_source_matrix(
        snapshot.physical_identities(), knowledge, semantics, verified,
        population="physical-1401-2026-09-19",
        engine_pin="xmage-1.4.61",
    )


def _oracle_ids_by_card(snapshot, results) -> dict[str, str]:
    import re

    def key_of(pr: str | None) -> str | None:
        pr = (pr or "").strip()
        if "#" not in pr:
            return None
        head, *segs = [*pr.split("|"), "", ""][:3]
        match = re.match(r"^([A-Za-z0-9]{2,6})#(\S+)$", head)
        if not match:
            return None
        lang = next((s for s in segs if re.fullmatch(r"[a-z]{2}", s or "")), "en")
        return "|".join([match.group(1).upper(), match.group(2), lang])

    by_card: dict[str, set[str]] = {}
    for row in snapshot.lots():
        entry = results.get(key_of(row.get("printing_ref")) or "")
        if entry and entry.get("oracle_id"):
            by_card.setdefault(row["card_id"], set()).add(entry["oracle_id"])
    return {card: next(iter(oids)) for card, oids in by_card.items() if len(oids) == 1}


def test_live_source_coverage_aggregates(matrix) -> None:
    assert matrix.population_size == 1401
    summary = matrix.source_summary()
    assert summary["oracle_identity"]["PRESENT"] == 1394
    assert summary["oracle_identity"]["UNKNOWN"] == 7
    # 38 textless identities are vanilla creatures (empty Oracle text is correct).
    assert summary["has_oracle_text"]["PRESENT"] == 1363
    assert summary["has_oracle_text"]["ABSENT"] == 38
    assert summary["has_structural_semantics"]["PRESENT"] == 1401
    behavior = matrix.behavior_summary()
    assert behavior["UNKNOWN"] == 1401
    assert sum(v for k, v in behavior.items() if k != "UNKNOWN") == 0
