"""Deck Plan: Derives a concise, structured game plan for each deck before a game.

Format and provenance are marked as 'abgeleitet, nicht gemessen'.
Derives how the deck operates, how it wins, which cards are engines, and which cards are answers,
using existing deck guides (data/deck_guides/guides/*.json) and repository card roles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from commander_lab.agents.card_knowledge import card_facts, card_roles
from commander_lab.models import CardRole, RulesDeckInput

PLAN_PROVENANCE: Final[str] = "abgeleitet, nicht gemessen"

_DEFAULT_GUIDES_DIR: Final[Path] = (
    Path(__file__).resolve().parents[3] / "data" / "deck_guides" / "guides"
)


@dataclass(frozen=True)
class DeckPlan:
    deck_id: str
    focus: str
    win_condition: str
    engines: tuple[str, ...]
    answers: tuple[str, ...]
    key_cards: tuple[str, ...]
    provenance: str = PLAN_PROVENANCE

    def as_dict(self) -> dict[str, object]:
        return {
            "deck_id": self.deck_id,
            "focus": self.focus,
            "win_condition": self.win_condition,
            "engines": list(self.engines),
            "answers": list(self.answers),
            "key_cards": list(self.key_cards),
            "provenance": self.provenance,
        }


def _find_guide(deck_id: str, guides_dir: Path) -> dict[str, object] | None:
    if not guides_dir.is_dir():
        return None

    # 1. Exact slug match or normalized deck_id
    normalized = deck_id.replace("/", "_").replace("-", "_")
    candidates = [
        guides_dir / f"{deck_id}.json",
        guides_dir / f"{normalized}.json",
        guides_dir / f"{deck_id.split('/')[-1]}.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                pass

    # 2. Iterate and match deck_id inside guide
    for guide_file in guides_dir.glob("*.json"):
        try:
            data = json.loads(guide_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("deck_id") == deck_id:
                return data
        except (OSError, ValueError):
            continue
    return None


def derive_deck_plan(
    deck: RulesDeckInput,
    guides_dir: Path | None = None,
) -> DeckPlan:
    """Derive a concise DeckPlan from a guide or from card roles in the deck."""
    directory = guides_dir or _DEFAULT_GUIDES_DIR
    guide = _find_guide(deck.deck_id, directory)

    # Classify all cards in the deck
    all_cards = list(deck.mainboard) + list(deck.commander_names)
    role_map: dict[str, set[CardRole]] = {}
    for card in all_cards:
        facts = card_facts(card)
        role_map[card] = set(card_roles(facts).keys()) if facts is not None else set()

    engines: list[str] = [card for card, roles in role_map.items() if CardRole.ENGINE in roles]
    answers: list[str] = [
        card
        for card, roles in role_map.items()
        if roles & {CardRole.REMOVAL, CardRole.COUNTER, CardRole.WIPE, CardRole.PROTECTION}
    ]
    finishers: list[str] = [
        card
        for card, roles in role_map.items()
        if roles & {CardRole.FINISHER, CardRole.COMBAT_PAYOFF}
    ]

    if guide is not None:
        win_condition = str(guide.get("win_plan") or "")
        if not win_condition:
            angriffs_fokus = str(guide.get("angriffs_fokus") or "")
            if angriffs_fokus:
                win_condition = f"Angriffs-Fokus: {angriffs_fokus}"
            else:
                win_condition = (
                    f"Synergie- und Kampflinie über {', '.join(deck.commander_names)} "
                    f"({len(finishers)} Finisher/Payoffs)"
                )

        archetypes = guide.get("archetypen")
        if isinstance(archetypes, list) and archetypes:
            focus = str(archetypes[0])
        elif guide.get("angriffs_fokus"):
            focus = str(guide.get("angriffs_fokus"))
        else:
            focus = "value_engine"

        schluesselkarten = guide.get("schluesselkarten")
        if isinstance(schluesselkarten, list) and schluesselkarten:
            key_cards = tuple(str(c) for c in schluesselkarten)
        else:
            key_cards = tuple(engines[:3] + finishers[:3])[:6]
    else:
        # Fallback without guide (e.g. arbitrary custom deck revision)
        focus = "kreaturen_und_synergie" if finishers else "kontrolle_und_value"
        win_condition = (
            f"Kampflinie über {', '.join(deck.commander_names)} "
            f"({len(finishers)} Finisher, {len(engines)} Motoren)"
        )
        key_cards = tuple(list(deck.commander_names) + engines[:2] + finishers[:2])[:6]

    return DeckPlan(
        deck_id=deck.deck_id,
        focus=focus,
        win_condition=win_condition,
        engines=tuple(sorted(set(engines))),
        answers=tuple(sorted(set(answers))),
        key_cards=key_cards,
        provenance=PLAN_PROVENANCE,
    )
