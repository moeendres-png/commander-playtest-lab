from __future__ import annotations

import json
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from commander_lab.models import CardRole, Color, StructuralCardProfile, StructuralDeckProfile

_CASTABILITY_TURNS: tuple[int, ...] = tuple(range(2, 11))
_CASTABILITY_MODES: tuple[str, str] = ("play", "draw")
DEFAULT_CASTABILITY_TRIALS = 20_000
DEFAULT_CASTABILITY_SEED = 20261016
_COMMANDER_LIBRARY_SIZES = (98, 99)  # 100-card deck minus one or two commanders
_OPENING_HAND_SIZE = 7


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
    commander_cast_probability: dict[str, dict[str, dict[int, float]]]
    expected_commander_turn: dict[str, dict[str, float | None]]
    evidence_class: str = "derived_structural_mana_analysis"
    approximation_note: str = (
        "Castability support is a structural source-coverage signal, not a rules-exact or "
        "probabilistic opening-hand result. Commander cast probabilities come from a seeded "
        "Monte Carlo over the library (7-card hand, one land per turn, no mulligans); lands "
        "that definitely enter tapped give mana from the next turn, and mana rocks/dorks "
        "with mana value <= 2 count from the turn after they could first be cast without "
        "modeling the mana spent casting them."
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


@dataclass(frozen=True)
class CastabilityLibraryCard:
    """One library card for the commander-cast Monte Carlo.

    ``is_mana_accelerant`` marks nonland cards with mana value <= 2 that produce mana
    (mana rocks and mana dorks). The simulation counts them as mana sources from the
    turn after they could first be cast; the mana spent casting them is not modeled.
    """

    oracle_name: str
    produces_colors: frozenset[str]
    is_land: bool
    definitely_tapped: bool
    mana_value: float
    is_mana_accelerant: bool


@dataclass(frozen=True)
class CommanderCastCost:
    name: str
    mana_value: float
    color_pips: dict[str, int]


@dataclass(frozen=True)
class CommanderCastability:
    """Seeded Monte Carlo result: is the commander castable by turn N?

    ``probability[commander]["play"|"draw"][turn]`` is the share of trials where the
    commander was castable on or before ``turn`` (turns 2..10, 3 decimals).
    ``expected_turn[commander]["play"|"draw"]`` is the mean earliest castable turn
    across trials that cast the commander by turn 10 (2 decimals), or None when no
    trial did.
    """

    probability: dict[str, dict[str, dict[int, float]]]
    expected_turn: dict[str, dict[str, float | None]]


def _choose_land_index(
    hand: list[CastabilityLibraryCard],
    wanted_colors: frozenset[str],
) -> int | None:
    """Index of the land to play: untapped first, then most wanted colors, then name."""
    best: int | None = None
    best_key: tuple[bool, int, str] | None = None
    for index, card in enumerate(hand):
        if not card.is_land:
            continue
        key = (
            card.definitely_tapped,
            -len(card.produces_colors & wanted_colors),
            card.oracle_name,
        )
        if best_key is None or key < best_key:
            best_key = key
            best = index
    return best


def simulate_commander_cast_probability(
    library: Sequence[CastabilityLibraryCard],
    commanders: Sequence[CommanderCastCost],
    *,
    trials: int = DEFAULT_CASTABILITY_TRIALS,
    seed: int = DEFAULT_CASTABILITY_SEED,
) -> CommanderCastability:
    """Seeded Monte Carlo over the library: P(commander castable by turn N).

    Pure and deterministic: the same ``(library, commanders, trials, seed)`` always
    yields identical numbers. Each trial shuffles the library with ``random.Random``,
    draws a 7-card hand, then simulates turns 1..10 on the play and on the draw from
    the same shuffle (on the play there is no turn-1 draw). Each turn draws one card
    (except turn 1 on the play), plays one land from hand when possible, and counts a
    mana rock/dork as a source from the turn after it could first be cast. A land
    that definitely enters tapped gives mana from the turn after it entered. The
    commander is castable on turn N when available mana covers its mana value and
    every colored pip is covered by a mana-active colored source in play. There are
    no mulligans.
    """
    if len(library) not in _COMMANDER_LIBRARY_SIZES:
        raise ValueError(
            "castability library must hold 98 or 99 cards "
            f"(100-card deck minus commanders); got {len(library)}"
        )
    if not commanders:
        raise ValueError("at least one commander is required")
    if trials < 1:
        raise ValueError("trials must be positive")
    names = [commander.name for commander in commanders]
    if len(set(names)) != len(names):
        raise ValueError("commander names must be unique")
    mana_thresholds = {commander.name: math.ceil(commander.mana_value) for commander in commanders}
    pips: Mapping[str, Mapping[str, int]] = {
        commander.name: dict(commander.color_pips) for commander in commanders
    }
    wanted: Mapping[str, frozenset[str]] = {
        commander.name: frozenset(commander.color_pips) for commander in commanders
    }

    earliest: dict[str, dict[str, list[int | None]]] = {
        name: {mode: [] for mode in _CASTABILITY_MODES} for name in names
    }
    rng = random.Random(seed)
    for _ in range(trials):
        order = list(library)
        rng.shuffle(order)
        for mode in _CASTABILITY_MODES:
            hand = list(order[:_OPENING_HAND_SIZE])
            stock = order[_OPENING_HAND_SIZE:]
            stock_index = 0
            lands_in_play: list[tuple[CastabilityLibraryCard, int]] = []
            accelerant_ready_turns: list[int] = []
            accelerant_colors: list[frozenset[str]] = []
            first_castable: dict[str, int | None] = dict.fromkeys(names)
            for turn in range(1, _CASTABILITY_TURNS[-1] + 1):
                if turn > 1 or mode == "draw":
                    hand.append(stock[stock_index])
                    stock_index += 1
                land_index = _choose_land_index(hand, frozenset().union(*wanted.values()))
                if land_index is not None:
                    lands_in_play.append((hand.pop(land_index), turn))
                available_mana = 0
                active_colors: dict[str, int] = {}
                for card, entry_turn in lands_in_play:
                    if entry_turn < turn or not card.definitely_tapped:
                        available_mana += 1
                        for color in card.produces_colors:
                            active_colors[color] = active_colors.get(color, 0) + 1
                for ready_turn, colors in zip(
                    accelerant_ready_turns, accelerant_colors, strict=True
                ):
                    if ready_turn <= turn:
                        available_mana += 1
                        for color in colors:
                            active_colors[color] = active_colors.get(color, 0) + 1
                for card in sorted(
                    (card for card in hand if card.is_mana_accelerant),
                    key=lambda card: (card.mana_value, card.oracle_name),
                ):
                    if card.mana_value <= available_mana:
                        hand.remove(card)
                        accelerant_ready_turns.append(turn + 1)
                        accelerant_colors.append(card.produces_colors)
                for name in names:
                    if (
                        first_castable[name] is None
                        and available_mana >= mana_thresholds[name]
                        and all(
                            active_colors.get(color, 0) >= count
                            for color, count in pips[name].items()
                        )
                    ):
                        first_castable[name] = turn
            for name in names:
                earliest[name][mode].append(first_castable[name])

    probability: dict[str, dict[str, dict[int, float]]] = {}
    expected_turn: dict[str, dict[str, float | None]] = {}
    for name in names:
        probability[name] = {}
        expected_turn[name] = {}
        for mode in _CASTABILITY_MODES:
            turns = earliest[name][mode]
            probability[name][mode] = {
                turn: round(
                    sum(1 for first in turns if first is not None and first <= turn) / trials,
                    3,
                )
                for turn in _CASTABILITY_TURNS
            }
            cast_turns = [first for first in turns if first is not None]
            expected_turn[name][mode] = (
                round(sum(cast_turns) / len(cast_turns), 2) if cast_turns else None
            )
    return CommanderCastability(probability=probability, expected_turn=expected_turn)


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

    def commander_castability(
        self,
        deck: StructuralDeckProfile,
        *,
        trials: int = DEFAULT_CASTABILITY_TRIALS,
        seed: int = DEFAULT_CASTABILITY_SEED,
    ) -> CommanderCastability:
        commander_names = set(deck.commander_names)
        library: list[CastabilityLibraryCard] = []
        for card in deck.cards:
            if card.oracle_name in commander_names:
                continue
            classification = self.classify_source(card)
            library.append(
                CastabilityLibraryCard(
                    oracle_name=card.oracle_name,
                    produces_colors=frozenset(classification.colors),
                    is_land=card.is_land,
                    definitely_tapped=classification.definitely_enters_tapped,
                    mana_value=card.mana_value,
                    is_mana_accelerant=(
                        not card.is_land and card.mana_value <= 2.0 and bool(classification.colors)
                    ),
                )
            )
        costs = [
            CommanderCastCost(
                name=name,
                mana_value=next(card.mana_value for card in deck.cards if card.oracle_name == name),
                color_pips={
                    color.value: int(count)
                    for card in deck.cards
                    if card.oracle_name == name
                    for color, count in card.color_requirements.items()
                },
            )
            for name in deck.commander_names
        ]
        return simulate_commander_cast_probability(
            tuple(library), tuple(costs), trials=trials, seed=seed
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
                card
                for card in noncommanders
                if not card.is_land and card.mana_value <= float(turn)
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
        castability = self.commander_castability(deck)
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
            commander_cast_probability=castability.probability,
            expected_commander_turn=castability.expected_turn,
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
                if variant.colored_sources.get(color, 0) != baseline.colored_sources.get(color, 0)
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
