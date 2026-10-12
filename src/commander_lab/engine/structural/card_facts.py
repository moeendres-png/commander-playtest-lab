"""Card facts from the pinned XMage card repository for Structural profiles.

Structural card profiles used to take creature power, finishers and commander stats only
from hand-curated tables. Every other creature was a 0-power body and every other card an
inert filler, so decks whose cards nobody curated (opponent precons, collection decks,
optimizer candidates) could not win through combat at all. These facts come from the
engine that decides full games (``scripts/export_xmage_card_facts.py``); a profile keeps
its curated values and only gains what the facts know and the profile does not.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from commander_lab.models import CardIdentity, CardRole, StructuralCardProfile

from .profiles import build_default_profile

CARD_FACTS_PATH = "data/cards/xmage_card_facts.json"
CARD_FACTS_SCHEMA_VERSION = "xmage-card-facts-1.0.0"

_FINISHER_TEXT = (
    "each opponent loses",
    "damage to each opponent",
    "additional combat phase",
    "you win the game",
    "double the damage",
)
_EVASION_TEXT = ("flying", "trample", "menace", "can't be blocked", "double strike")


def engine_lookup_key(name: str) -> str:
    """Casefolded, accent-free name: XMage spells card names in ASCII."""
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class CardFacts:
    name: str
    mana_value: float
    types: tuple[str, ...]
    subtypes: tuple[str, ...]
    supertypes: tuple[str, ...]
    power: float | None
    toughness: float | None
    rules: tuple[str, ...]

    @property
    def is_creature(self) -> bool:
        return "CREATURE" in self.types

    @property
    def is_land(self) -> bool:
        return "LAND" in self.types

    @property
    def text(self) -> str:
        return "\n".join(self.rules).replace("{this}", self.name)

    @property
    def type_line(self) -> str:
        words = [*self.supertypes, *self.types]
        line = " ".join(word.capitalize() for word in words)
        if self.subtypes:
            line += " — " + " ".join(self.subtypes)
        return line or "Unknown"

    def combat_power(self) -> float:
        """Power as the Structural combat model counts it (evasion adds a little)."""
        if self.power is None:
            return 0.0
        power = max(0.0, self.power)
        text = self.text.casefold()
        if any(word in text for word in _EVASION_TEXT):
            power *= 1.25
        return min(power, 30.0)


class CardFactsCatalog:
    def __init__(self, facts: dict[str, CardFacts]) -> None:
        self._by_key = {engine_lookup_key(name): fact for name, fact in facts.items()}

    @classmethod
    def from_json(cls, path: str | Path) -> CardFactsCatalog:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != CARD_FACTS_SCHEMA_VERSION:
            raise ValueError(f"unsupported card facts schema: {payload.get('schema_version')}")
        facts = {
            name: CardFacts(
                name=name,
                mana_value=float(row.get("mana_value") or 0.0),
                types=tuple(row.get("types", ())),
                subtypes=tuple(row.get("subtypes", ())),
                supertypes=tuple(row.get("supertypes", ())),
                power=row.get("power"),
                toughness=row.get("toughness"),
                rules=tuple(row.get("rules", ())),
            )
            for name, row in payload["cards"].items()
        }
        return cls(facts)

    def get(self, name: str) -> CardFacts | None:
        fact = self._by_key.get(engine_lookup_key(name))
        if fact is None and " // " in name:
            fact = self._by_key.get(engine_lookup_key(name.split(" // ")[0]))
        return fact

    def __len__(self) -> int:
        return len(self._by_key)


@lru_cache(maxsize=4)
def load_card_facts(root: str | Path) -> CardFactsCatalog | None:
    """The project's card facts, or None when they have not been exported."""
    path = Path(root) / CARD_FACTS_PATH
    return CardFactsCatalog.from_json(path) if path.is_file() else None


def apply_card_facts(profile: StructuralCardProfile, facts: CardFacts) -> StructuralCardProfile:
    """Fill in what the facts know and the profile leaves at its uncurated default."""
    update: dict[str, object] = {}
    if facts.is_creature and not profile.is_land:
        update["is_creature"] = True
        if profile.base_power <= 0.0:
            update["base_power"] = facts.combat_power()
    text = facts.text.casefold()
    if CardRole.FINISHER not in profile.roles and any(cue in text for cue in _FINISHER_TEXT):
        update["roles"] = profile.roles | {CardRole.FINISHER}
        update["role_strengths"] = {**profile.role_strengths, CardRole.FINISHER: 1.0}
        if profile.roles == frozenset({CardRole.ENABLER}):
            update["roles"] = frozenset({CardRole.FINISHER})
            update["role_strengths"] = {CardRole.FINISHER: 1.0}
    return profile.model_copy(update=update) if update else profile


def profile_from_facts(name: str, facts: CardFacts) -> StructuralCardProfile:
    """A Structural profile for a card nobody curated, inferred from its facts."""
    identity = CardIdentity(
        oracle_name=name,
        mana_value=facts.mana_value,
        type_line=facts.type_line,
        oracle_text=facts.text,
        is_basic_land=facts.is_land and "BASIC" in facts.supertypes,
    )
    return apply_card_facts(build_default_profile(identity), facts)


def commander_stats(name: str, catalog: CardFactsCatalog | None) -> tuple[float, float] | None:
    """(mana value, combat power) of a commander, when the facts know it."""
    facts = catalog.get(name) if catalog is not None else None
    if facts is None:
        return None
    return facts.mana_value, facts.combat_power()


__all__ = [
    "CARD_FACTS_PATH",
    "CARD_FACTS_SCHEMA_VERSION",
    "CardFacts",
    "CardFactsCatalog",
    "apply_card_facts",
    "commander_stats",
    "engine_lookup_key",
    "load_card_facts",
    "profile_from_facts",
]
