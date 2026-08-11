from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from commander_lab.models import Color, StructuralCardProfile, StructuralDeckProfile


@dataclass(frozen=True)
class ManaSourceClassification:
    oracle_name: str
    colors: tuple[str, ...]
    is_land: bool
    definitely_enters_tapped: bool
    conditionally_enters_tapped: bool


@dataclass(frozen=True)
class DeckManaAnalysis:
    deck_id: str
    deck_hash: str
    land_count: int
    colored_sources: dict[str, int]
    flexible_source_count: int
    definitely_tapped_land_count: int
    conditionally_tapped_land_count: int
    t1_untapped_land_sources: dict[str, int]
    early_color_requirements: dict[int, dict[str, int]]
    commander_color_requirements: dict[str, dict[str, int]]
    evidence_class: str = "derived_structural_mana_analysis"


@dataclass(frozen=True)
class OpeningHandManaAnalysis:
    cards: tuple[str, ...]
    colored_sources: dict[str, int]
    untapped_source_count: int
    definitely_tapped_source_count: int
    conditionally_tapped_source_count: int
    flexible_source_count: int
    commander_color_ready: bool
    missing_commander_colors: tuple[str, ...]
    evidence_class: str = "derived_structural_mana_analysis"


class ManaAnalyzer:
    """Deterministic mana-source analysis using current structural profiles + Oracle text.

    Conditional ETB clauses are intentionally not solved as game rules. They are separated from
    definitely-tapped sources so callers cannot silently treat an approximation as exact rules
    execution.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        path = self.root / "data/canonical_import/2026-08-07/inventory_snapshot.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.inventory = {
            str(row["oracle_name"]): dict(row) for row in payload.get("cards", []) if row.get("oracle_name")
        }

    def classify_source(self, card: StructuralCardProfile) -> ManaSourceClassification:
        colors = tuple(sorted(color.value for color in card.produces_colors))
        row = self.inventory.get(card.oracle_name, {})
        text = str(row.get("oracle_text", "") or "").casefold()
        is_land = card.is_land
        tapped_phrase = "enters the battlefield tapped" in text or "enters tapped" in text
        conditional_markers = (
            "unless",
            "if you don't",
            "if you do not",
            "you may pay",
            "unless you control",
        )
        conditional = bool(tapped_phrase and any(marker in text for marker in conditional_markers))
        definite = bool(tapped_phrase and not conditional)
        return ManaSourceClassification(
            oracle_name=card.oracle_name,
            colors=colors,
            is_land=is_land,
            definitely_enters_tapped=definite,
            conditionally_enters_tapped=conditional,
        )

    @staticmethod
    def _requirements(cards: tuple[StructuralCardProfile, ...]) -> dict[str, int]:
        requirements = {color.value: 0 for color in Color}
        for card in cards:
            for color, count in card.color_requirements.items():
                requirements[color.value] += int(count)
        return {color: value for color, value in requirements.items() if value}

    def analyze_deck(self, deck: StructuralDeckProfile) -> DeckManaAnalysis:
        colors = {color.value: 0 for color in Color}
        t1 = {color.value: 0 for color in Color}
        flexible = 0
        definite_tapped = 0
        conditional_tapped = 0
        for card in deck.cards:
            classification = self.classify_source(card)
            if classification.colors:
                if len(classification.colors) >= 2:
                    flexible += 1
                for color in classification.colors:
                    colors[color] += 1
                    if card.is_land and not classification.definitely_enters_tapped:
                        t1[color] += 1
            if card.is_land and classification.definitely_enters_tapped:
                definite_tapped += 1
            if card.is_land and classification.conditionally_enters_tapped:
                conditional_tapped += 1

        noncommanders = tuple(
            card for card in deck.cards if card.oracle_name not in set(deck.commander_names)
        )
        early: dict[int, dict[str, int]] = {}
        for turn in (1, 2, 3):
            eligible = tuple(
                card
                for card in noncommanders
                if not card.is_land and card.mana_value <= float(turn)
            )
            early[turn] = self._requirements(eligible)
        commanders = {
            name: self._requirements(tuple(card for card in deck.cards if card.oracle_name == name))
            for name in deck.commander_names
        }
        return DeckManaAnalysis(
            deck_id=deck.deck_id,
            deck_hash=deck.deck_hash,
            land_count=sum(card.is_land for card in deck.cards),
            colored_sources={key: value for key, value in colors.items() if value},
            flexible_source_count=flexible,
            definitely_tapped_land_count=definite_tapped,
            conditionally_tapped_land_count=conditional_tapped,
            t1_untapped_land_sources={key: value for key, value in t1.items() if value},
            early_color_requirements=early,
            commander_color_requirements=commanders,
        )

    def analyze_opening_hand(
        self,
        deck: StructuralDeckProfile,
        cards: tuple[StructuralCardProfile, ...],
    ) -> OpeningHandManaAnalysis:
        colors = {color.value: 0 for color in Color}
        definite_tapped = 0
        conditional_tapped = 0
        untapped_sources = 0
        flexible = 0
        for card in cards:
            classification = self.classify_source(card)
            if classification.colors:
                if len(classification.colors) >= 2:
                    flexible += 1
                for color in classification.colors:
                    colors[color] += 1
                if classification.definitely_enters_tapped:
                    definite_tapped += 1
                else:
                    untapped_sources += 1
                if classification.conditionally_enters_tapped:
                    conditional_tapped += 1

        commander_requirements = self._requirements(
            tuple(card for card in deck.cards if card.oracle_name in set(deck.commander_names))
        )
        missing = tuple(
            sorted(color for color in commander_requirements if colors.get(color, 0) <= 0)
        )
        return OpeningHandManaAnalysis(
            cards=tuple(card.oracle_name for card in cards),
            colored_sources={key: value for key, value in colors.items() if value},
            untapped_source_count=untapped_sources,
            definitely_tapped_source_count=definite_tapped,
            conditionally_tapped_source_count=conditional_tapped,
            flexible_source_count=flexible,
            commander_color_ready=not missing,
            missing_commander_colors=missing,
        )
