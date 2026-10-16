"""Shared deck-profile resolution for CLI scripts (#852).

``structural_profile`` used to live in ``scripts/mana_castability_report.py``;
it moved here unchanged (same behaviour, same return value) so other scripts
(such as the deck-variant prefilter) can reuse it without duplicating the
resolution logic. The script now imports it from here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.engine.structural.card_facts import load_card_facts
from commander_lab.engine.structural.project import load_project_structural_decks
from commander_lab.engine.structural.xmage_calibration import (
    fact_deck_profile,
    known_card_profiles,
)
from commander_lab.models import RulesDeckInput, StructuralDeckProfile
from commander_lab.storage import sha256_value

ROOT = Path(__file__).resolve().parents[2]


def load_deck(path: Path) -> RulesDeckInput:
    deck = load_rules_deck_snapshot(path)
    if deck.deck_hash is None:
        deck = deck.model_copy(
            update={
                "deck_hash": sha256_value(
                    {
                        "deck_id": deck.deck_id,
                        "commander_names": list(deck.commander_names),
                        "mainboard": list(deck.mainboard),
                        "sideboard": list(deck.sideboard),
                    }
                )
            }
        )
    return deck


def structural_profile(deck: RulesDeckInput) -> tuple[StructuralDeckProfile, str]:
    """Resolve a structural profile: project manifest first, card facts otherwise."""
    project_decks = load_project_structural_decks(ROOT)
    if deck.deck_id in project_decks:
        return project_decks[deck.deck_id], "project manifest"
    facts = load_card_facts(ROOT)
    if facts is None:
        print("data/cards/xmage_card_facts.json is missing", file=sys.stderr)
        raise SystemExit(2)
    manifest = json.loads((ROOT / "data/decks/manifest.json").read_text(encoding="utf-8"))
    profile, report = fact_deck_profile(
        deck,
        known=known_card_profiles(project_decks.values()),
        facts=facts,
        snapshot_hash=str(manifest["data_snapshot_hash"]),
    )
    source = (
        "XMage card facts "
        f"({report.curated} curated, {report.inferred_from_facts} inferred"
        + (f", {len(report.without_facts)} without facts" if report.without_facts else "")
        + ")"
    )
    return profile, source
