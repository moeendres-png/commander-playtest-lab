"""Deck readiness: which cards of a deck the simulator cannot play well yet (#834).

A deck variant often adds cards outside the current card data. A card missing
from the XMage card facts is unknown to the structural tools; a card missing
from the pilot card knowledge is played by the pilots without strategic roles.
Checking readiness *before* anyone spends hours of full games on a deck keeps
a variant comparison from silently measuring "unknown card" instead of the card.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from commander_lab.agents.card_knowledge import card_facts as pilot_card_facts
from commander_lab.engine.structural.card_facts import (
    CARD_FACTS_SCHEMA_VERSION,
    engine_lookup_key,
)
from commander_lab.models import RulesDeckInput

_ROOT = Path(__file__).resolve().parents[2]
_CARD_FACTS_PATH = _ROOT / "data/cards/xmage_card_facts.json"
_PILOT_KNOWLEDGE_PATH = _ROOT / "data/cards/pilot_card_knowledge.json"


class CardReadinessStatus(StrEnum):
    """What the simulator knows about one card of a deck."""

    OK = "OK"
    NO_CARD_FACTS = "NO_CARD_FACTS"
    KNOWN_MISSING_IN_XMAGE = "KNOWN_MISSING_IN_XMAGE"
    NO_PILOT_KNOWLEDGE = "NO_PILOT_KNOWLEDGE"


@dataclass(frozen=True)
class CardReadiness:
    """The readiness of one unique card name of a deck."""

    name: str
    status: CardReadinessStatus


@dataclass(frozen=True)
class DeckReadiness:
    """The readiness of a whole deck: ready only when every card is OK."""

    deck_id: str
    cards: tuple[CardReadiness, ...]
    counts: dict[CardReadinessStatus, int]
    ready: bool


#: How to fix a card that is not ready, named for the human CLI output.
FIX_HINTS: dict[CardReadinessStatus, str] = {
    CardReadinessStatus.NO_CARD_FACTS: (
        "re-export the XMage card facts: python scripts/export_xmage_card_facts.py"
    ),
    CardReadinessStatus.KNOWN_MISSING_IN_XMAGE: (
        "the pinned XMage engine has no facts for this card; "
        "re-export with scripts/export_xmage_card_facts.py after an engine update"
    ),
    CardReadinessStatus.NO_PILOT_KNOWLEDGE: (
        "teach the pilots this card: python scripts/build_pilot_card_knowledge.py"
    ),
}


class _CardData:
    """The two card-data files, indexed the way the exporters key them."""

    def __init__(self, facts_path: Path, pilot_knowledge_path: Path) -> None:
        facts_payload = json.loads(facts_path.read_text(encoding="utf-8"))
        if facts_payload.get("schema_version") != CARD_FACTS_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported card facts schema in {facts_path}: "
                f"{facts_payload.get('schema_version')}"
            )
        self._facts_keys = {engine_lookup_key(name) for name in facts_payload.get("cards", {})}
        self._missing_keys = {engine_lookup_key(name) for name in facts_payload.get("missing", [])}
        if not pilot_knowledge_path.is_file():
            raise FileNotFoundError(f"pilot card knowledge not found: {pilot_knowledge_path}")
        self._pilot_knowledge_path = pilot_knowledge_path

    def status_of(self, name: str) -> CardReadinessStatus:
        key = engine_lookup_key(name)
        front = engine_lookup_key(name.split(" // ")[0]) if " // " in name else None
        if key in self._facts_keys or (front is not None and front in self._facts_keys):
            if pilot_card_facts(name, self._pilot_knowledge_path) is None:
                return CardReadinessStatus.NO_PILOT_KNOWLEDGE
            return CardReadinessStatus.OK
        if key in self._missing_keys or (front is not None and front in self._missing_keys):
            return CardReadinessStatus.KNOWN_MISSING_IN_XMAGE
        return CardReadinessStatus.NO_CARD_FACTS


def check_deck(
    deck: RulesDeckInput,
    *,
    facts_path: Path | None = None,
    pilot_knowledge_path: Path | None = None,
) -> DeckReadiness:
    """Readiness of every card of *deck* against the card data files.

    Each unique card name (commanders, mainboard, sideboard) gets one of OK,
    NO_CARD_FACTS, KNOWN_MISSING_IN_XMAGE or NO_PILOT_KNOWLEDGE. The deck is
    ready only when every card is OK. Name lookup mirrors the exporters:
    ``engine_lookup_key``, with double-faced names resolved by their front face.
    """
    data = _CardData(facts_path or _CARD_FACTS_PATH, pilot_knowledge_path or _PILOT_KNOWLEDGE_PATH)
    cards = tuple(
        CardReadiness(name=name, status=data.status_of(name))
        for name in dict.fromkeys([*deck.commander_names, *deck.mainboard, *deck.sideboard])
    )
    counts = {status: 0 for status in CardReadinessStatus}
    for card in cards:
        counts[card.status] += 1
    return DeckReadiness(
        deck_id=deck.deck_id,
        cards=cards,
        counts=counts,
        ready=all(card.status is CardReadinessStatus.OK for card in cards),
    )


def format_deck_report(label: str, report: DeckReadiness) -> str:
    """Human-readable readiness report for one deck, with fix hints."""
    state = "READY" if report.ready else "NOT READY"
    lines = [f"{label}: {report.deck_id} is {state}"]
    for status in CardReadinessStatus:
        if status is CardReadinessStatus.OK:
            continue
        names = [card.name for card in report.cards if card.status is status]
        if names:
            lines.append(f"  {status.value} ({len(names)}): {', '.join(names)}")
            lines.append(f"    fix: {FIX_HINTS[status]}")
    return "\n".join(lines)


__all__ = [
    "FIX_HINTS",
    "CardReadiness",
    "CardReadinessStatus",
    "DeckReadiness",
    "check_deck",
    "format_deck_report",
]
