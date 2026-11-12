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
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from commander_lab.models import (
    CardIdentity,
    CardRole,
    Color,
    StructuralCardProfile,
    StructuralDeckProfile,
)

from .profiles import ALL_COLORS, build_default_profile

CARD_FACTS_PATH = "data/cards/xmage_card_facts.json"
CARD_FACTS_SCHEMA_VERSION = "xmage-card-facts-1.0.0"

_FINISHER_TEXT = (
    "each opponent loses",
    "damage to each opponent",
    "additional combat phase",
    "you win the game",
    "double the damage",
)
_TAP_MANA_ABILITY = re.compile(r"\{T\}[^.:]*:\s*add\b([^.]*)", re.IGNORECASE)
_MANA_SYMBOL = re.compile(r"\{([WUBRG])\}")
_ANY_COLOR_TEXT = ("any color", "any one color", "any combination of colors", "any type")
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
    mana_cost: str = ""

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


def fact_name_index(names: set[str], aliases: object) -> dict[str, str]:
    """Index exact names, then unambiguous front faces and validated explicit aliases."""
    index = {engine_lookup_key(name): name for name in sorted(names)}
    fronts: dict[str, set[str]] = {}
    for name in names:
        if " // " in name:
            fronts.setdefault(engine_lookup_key(name.split(" // ")[0]), set()).add(name)
    for key, targets in fronts.items():
        if len(targets) == 1:
            index.setdefault(key, next(iter(targets)))
    if not isinstance(aliases, dict):
        raise ValueError("card facts aliases must be a mapping")
    seen_aliases: dict[str, str] = {}
    for alias, target in aliases.items():
        if not isinstance(alias, str) or not isinstance(target, str) or target not in names:
            raise ValueError("card facts alias has an invalid target")
        key = engine_lookup_key(alias)
        if key in seen_aliases and seen_aliases[key] != target:
            raise ValueError("card facts alias maps to conflicting targets")
        seen_aliases[key] = target
        index.setdefault(key, target)
    return index


def apply_retained_lookup(
    index: dict[str, str], cards: dict[str, object], retained: object
) -> None:
    """Restore prior canonical keys only where any competing fresh fact is identical."""
    if not isinstance(retained, dict):
        raise ValueError("retained lookup must be a mapping")
    for key, target in retained.items():
        if (
            not isinstance(key, str)
            or engine_lookup_key(key) != key
            or not isinstance(target, str)
            or target not in cards
        ):
            raise ValueError("retained lookup has an invalid target")
        existing = index.get(key)
        if existing is not None and cards[existing] != cards[target]:
            raise ValueError("retained lookup conflicts with a fresh engine fact")
        index[key] = target


class CardFactsCatalog:
    def __init__(
        self,
        facts: dict[str, CardFacts],
        aliases: dict[str, str] | None = None,
        ambiguous: tuple[str, ...] = (),
        retained_index: dict[str, str] | None = None,
    ) -> None:
        index = fact_name_index(set(facts), aliases if aliases is not None else {})
        if retained_index is not None:
            index.update(retained_index)
        unknown_keys = {engine_lookup_key(name) for name in ambiguous}
        self._by_key = {key: facts[name] for key, name in index.items() if key not in unknown_keys}
        self._facts = tuple(dict.fromkeys(self._by_key.values()))
        self._profiles: tuple[StructuralCardProfile, ...] | None = None

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
                mana_cost=str(row.get("mana_cost") or ""),
            )
            for name, row in payload["cards"].items()
        }
        ambiguous = payload.get("ambiguous", [])
        if not isinstance(ambiguous, list) or not all(isinstance(name, str) for name in ambiguous):
            raise ValueError("card facts ambiguous names must be a list of strings")
        index = fact_name_index(set(facts), payload.get("aliases", {}))
        apply_retained_lookup(index, payload["cards"], payload.get("retained_lookup", {}))
        return cls(facts, payload.get("aliases", {}), tuple(ambiguous), index)

    def get(self, name: str) -> CardFacts | None:
        return self._by_key.get(engine_lookup_key(name))

    def facts(self) -> tuple[CardFacts, ...]:
        return self._facts

    def __len__(self) -> int:
        return len(self._facts)


@lru_cache(maxsize=4)
def load_card_facts(root: str | Path) -> CardFactsCatalog | None:
    """The project's card facts, or None when they have not been exported."""
    path = Path(root) / CARD_FACTS_PATH
    return CardFactsCatalog.from_json(path) if path.is_file() else None


def produced_colors_from_rules(rules: tuple[str, ...]) -> frozenset[Color]:
    """Colours added by the card's tap mana abilities (spells and triggers do not count)."""
    produced: set[Color] = set()
    for line in rules:
        for clause in _TAP_MANA_ABILITY.findall(line):
            produced.update(Color(symbol) for symbol in _MANA_SYMBOL.findall(clause.upper()))
            if any(phrase in clause.casefold() for phrase in _ANY_COLOR_TEXT):
                produced.update(ALL_COLORS)
    return frozenset(produced)


def apply_card_facts(
    profile: StructuralCardProfile, facts: CardFacts, *, infer_roles: bool = True
) -> StructuralCardProfile:
    """Fill in what the facts know and the profile leaves at its uncurated default.

    Power is a fact. A finisher role read from rules text is an inference, so callers that
    keep a card's semantics deliberately unknown pass ``infer_roles=False``.
    """
    update: dict[str, object] = {}
    if facts.is_creature and not profile.is_land:
        update["is_creature"] = True
        if profile.base_power <= 0.0:
            update["base_power"] = facts.combat_power()
    text = facts.text.casefold()
    if (
        infer_roles
        and CardRole.FINISHER not in profile.roles
        and any(cue in text for cue in _FINISHER_TEXT)
    ):
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
    profile = build_default_profile(identity)
    if not profile.produces_colors:
        # An uncurated land or mana rock would otherwise count as a colourless source.
        produced = produced_colors_from_rules(facts.rules)
        if produced:
            profile = profile.model_copy(update={"produces_colors": produced})
    return apply_card_facts(profile, facts)


def apply_facts_to_deck(
    deck: StructuralDeckProfile, catalog: CardFactsCatalog | None
) -> StructuralDeckProfile:
    """Card power, text finishers and commander cost/power from the facts, where known.

    Placeholder role cards of partially known opponent lists stay as they are.
    """
    if catalog is None:
        return deck
    cards = []
    for card in deck.cards:
        facts = catalog.get(card.oracle_name)
        cards.append(card if facts is None else apply_card_facts(card, facts))
    costs = dict(deck.commander_base_costs)
    powers = dict(deck.commander_base_power)
    for name in deck.commander_names:
        stats = commander_stats(name, catalog)
        if stats is not None:
            costs[name], powers[name] = stats
    return deck.model_copy(
        update={
            "cards": tuple(cards),
            "commander_base_costs": costs,
            "commander_base_power": powers,
        }
    )


def fact_profiles(catalog: CardFactsCatalog | None) -> tuple[StructuralCardProfile, ...]:
    """Inferred profiles for every card with facts (curated profiles take precedence)."""
    if catalog is None:
        return ()
    if catalog._profiles is None:
        catalog._profiles = tuple(profile_from_facts(fact.name, fact) for fact in catalog.facts())
    return catalog._profiles


def commander_stats(name: str, catalog: CardFactsCatalog | None) -> tuple[float, float] | None:
    """(mana value, base power) of a commander, when the facts know it.

    The base power is the card's own power. ``StructuralDeckProfile.commander_base_power``
    is the card fact the deck profile asserts (and the integration tests pin against the
    real card), and the simulator derives commander damage from it, so the evasion bump
    of ``combat_power`` — the combat-model power of an uncurated body — would restate a
    printed 9-power card as 11.25 and count its evasion twice. A commander the facts
    cannot give a power for (for example a planeswalker commander) stays unknown so the
    deck's own value survives.
    """
    facts = catalog.get(name) if catalog is not None else None
    if facts is None or facts.power is None:
        return None
    return facts.mana_value, max(0.0, facts.power)


__all__ = [
    "CARD_FACTS_PATH",
    "CARD_FACTS_SCHEMA_VERSION",
    "CardFacts",
    "CardFactsCatalog",
    "apply_card_facts",
    "apply_facts_to_deck",
    "commander_stats",
    "engine_lookup_key",
    "fact_profiles",
    "load_card_facts",
    "profile_from_facts",
]
