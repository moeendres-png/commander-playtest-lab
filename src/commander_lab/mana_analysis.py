from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from commander_lab.models import CardRole, Color, StructuralCardProfile, StructuralDeckProfile


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
    ishai_wu_source_counts: dict[str, int]
    early_interaction_hold_up_requirements: dict[str, int]
    turn_castability_support: dict[int, dict[str, object]]
    evidence_class: str = "derived_structural_mana_analysis"
    approximation_note: str = (
        "Castability support is a structural source-coverage signal, not a rules-exact or "
        "probabilistic opening-hand result."
    )


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
    approximate_castable_card_count_by_turn: dict[int, int]
    ishai_wu_color_ready: bool
    t2_interaction_hold_up_ready: bool
    evidence_class: str = "derived_structural_mana_analysis"
    approximation_note: str = (
        "Opening-hand castability assumes one land play per turn from lands already in hand and "
        "does not solve conditional ETB clauses, future draws, sequencing, or game rules."
    )


@dataclass(frozen=True)
class ManaDeltaAnalysis:
    colored_source_delta: dict[str, int]
    flexible_source_delta: int
    definitely_tapped_land_delta: int
    conditionally_tapped_land_delta: int
    t1_untapped_source_delta: dict[str, int]
    ishai_wu_source_delta: dict[str, int]
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
            str(row["oracle_name"]): dict(row)
            for row in payload.get("cards", [])
            if row.get("oracle_name")
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

    @staticmethod
    def _max_requirements(cards: tuple[StructuralCardProfile, ...]) -> dict[str, int]:
        requirements = {color.value: 0 for color in Color}
        for card in cards:
            for color, count in card.color_requirements.items():
                requirements[color.value] = max(requirements[color.value], int(count))
        return {color: value for color, value in requirements.items() if value}

    @staticmethod
    def _requirements_supported(
        card: StructuralCardProfile,
        *,
        available_colors: set[str],
        available_mana: int,
    ) -> bool:
        if math.ceil(card.mana_value) > available_mana:
            return False
        return all(
            count <= available_mana and color.value in available_colors
            for color, count in card.color_requirements.items()
        )

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
        turn_support: dict[int, dict[str, object]] = {}
        t1_colors = {color for color, count in t1.items() if count > 0}
        for turn in (1, 2, 3):
            eligible = tuple(
                card for card in noncommanders if not card.is_land and card.mana_value <= float(turn)
            )
            early[turn] = self._requirements(eligible)
            supported = sum(
                self._requirements_supported(
                    card,
                    available_colors=t1_colors,
                    available_mana=turn,
                )
                for card in eligible
            )
            turn_support[turn] = {
                "eligible_spell_count": len(eligible),
                "source_supported_spell_count": supported,
                "source_supported_share": supported / len(eligible) if eligible else 1.0,
            }
        commanders = {
            name: self._requirements(tuple(card for card in deck.cards if card.oracle_name == name))
            for name in deck.commander_names
        }
        early_interaction = tuple(
            card
            for card in noncommanders
            if not card.is_land
            and card.mana_value <= 2.0
            and ({CardRole.COUNTER, CardRole.PROTECTION} & set(card.roles))
        )
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
            ishai_wu_source_counts={"W": colors.get("W", 0), "U": colors.get("U", 0)},
            early_interaction_hold_up_requirements=self._max_requirements(early_interaction),
            turn_castability_support=turn_support,
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
        land_colors: set[str] = set()
        land_count = 0
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
                if classification.is_land:
                    land_count += 1
                    land_colors.update(classification.colors)

        commander_requirements = self._requirements(
            tuple(card for card in deck.cards if card.oracle_name in set(deck.commander_names))
        )
        missing = tuple(
            sorted(color for color in commander_requirements if colors.get(color, 0) <= 0)
        )
        nonlands = tuple(card for card in cards if not card.is_land)
        castable: dict[int, int] = {}
        for turn in (1, 2, 3):
            available_mana = min(turn, land_count)
            castable[turn] = sum(
                self._requirements_supported(
                    card,
                    available_colors=land_colors,
                    available_mana=available_mana,
                )
                for card in nonlands
                if card.mana_value <= float(turn)
            )
        interaction = tuple(
            card
            for card in nonlands
            if card.mana_value <= 2.0
            and ({CardRole.COUNTER, CardRole.PROTECTION} & set(card.roles))
        )
        t2_hold_up = any(
            self._requirements_supported(
                card,
                available_colors=land_colors,
                available_mana=min(2, land_count),
            )
            for card in interaction
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
            approximate_castable_card_count_by_turn=castable,
            ishai_wu_color_ready=colors.get("W", 0) > 0 and colors.get("U", 0) > 0,
            t2_interaction_hold_up_ready=t2_hold_up,
        )

    def compare_decks(
        self,
        before: StructuralDeckProfile,
        after: StructuralDeckProfile,
    ) -> ManaDeltaAnalysis:
        baseline = self.analyze_deck(before)
        variant = self.analyze_deck(after)
        colors = {color.value for color in Color}
        return ManaDeltaAnalysis(
            colored_source_delta={
                color: variant.colored_sources.get(color, 0)
                - baseline.colored_sources.get(color, 0)
                for color in sorted(colors)
                if variant.colored_sources.get(color, 0)
                != baseline.colored_sources.get(color, 0)
            },
            flexible_source_delta=variant.flexible_source_count - baseline.flexible_source_count,
            definitely_tapped_land_delta=(
                variant.definitely_tapped_land_count - baseline.definitely_tapped_land_count
            ),
            conditionally_tapped_land_delta=(
                variant.conditionally_tapped_land_count - baseline.conditionally_tapped_land_count
            ),
            t1_untapped_source_delta={
                color: variant.t1_untapped_land_sources.get(color, 0)
                - baseline.t1_untapped_land_sources.get(color, 0)
                for color in sorted(colors)
                if variant.t1_untapped_land_sources.get(color, 0)
                != baseline.t1_untapped_land_sources.get(color, 0)
            },
            ishai_wu_source_delta={
                color: variant.ishai_wu_source_counts.get(color, 0)
                - baseline.ishai_wu_source_counts.get(color, 0)
                for color in ("W", "U")
            },
        )
