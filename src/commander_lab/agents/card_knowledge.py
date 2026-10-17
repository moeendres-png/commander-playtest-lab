"""Public printed card knowledge for the full-game pilots (#732).

A human Commander player knows what the cards on the table and in their hand
do. The XMage pilot view mostly names cards, so this module reads the printed
facts (types, mana value, power/toughness, keywords, text) from
``data/cards/pilot_card_knowledge.json`` (built by
``scripts/build_pilot_card_knowledge.py``) and derives the strategic roles the
pilot evaluator already understands.

This is ranking knowledge, never rules authority: nothing here decides what is
legal or what happens. An unknown card simply yields no facts, and every caller
falls back to the name-only behaviour it had before.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path

from commander_lab.models import CardRole

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data/cards/pilot_card_knowledge.json"
_BASIC_LANDS = frozenset(
    {"plains", "island", "swamp", "mountain", "forest", "wastes"}
    | {f"snow-covered {name}" for name in ("plains", "island", "swamp", "mountain", "forest")}
)
COLOR_WORDS = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
_PIP = re.compile(r"\{([WUBRGC])(?:/[WUBRGP])?\}")


@dataclass(frozen=True)
class CardFacts:
    name: str
    mana_value: float
    mana_cost: str
    type_line: str
    oracle_text: str
    power: int | None
    toughness: int | None
    keywords: frozenset[str]
    colors: frozenset[str]
    color_identity: frozenset[str]
    produced_mana: frozenset[str]

    # Pilots ask these for every permanent on every decision; the facts are
    # immutable, so each is computed once per card.
    @cached_property
    def types(self) -> str:
        return self.type_line.split("—", 1)[0].casefold()

    @property
    def subtypes(self) -> tuple[str, ...]:
        if "—" not in self.type_line:
            return ()
        return tuple(self.type_line.split("—", 1)[1].split("//")[0].split())

    @cached_property
    def is_land(self) -> bool:
        return "land" in self.types and "//" not in self.type_line.split("—", 1)[0]

    @cached_property
    def is_creature(self) -> bool:
        return "creature" in self.types

    @cached_property
    def is_planeswalker(self) -> bool:
        return "planeswalker" in self.types

    @property
    def is_instant_speed(self) -> bool:
        return "instant" in self.types or "flash" in {word.casefold() for word in self.keywords}

    def has_keyword(self, keyword: str) -> bool:
        wanted = keyword.casefold()
        return any(word.casefold() == wanted for word in self.keywords)

    def pips(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for symbol in _PIP.findall(self.mana_cost):
            counts[symbol] = counts.get(symbol, 0) + 1
        return counts


def is_basic_land_name(name: str) -> bool:
    return name.strip().casefold() in _BASIC_LANDS


@lru_cache(maxsize=4)
def _catalog(path: str) -> dict[str, CardFacts]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8")).get("cards", {})
    except (OSError, ValueError):
        return {}
    catalog: dict[str, CardFacts] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            continue
        facts = CardFacts(
            name=str(item.get("name", name)),
            mana_value=float(item.get("mana_value") or 0.0),
            mana_cost=str(item.get("mana_cost") or ""),
            type_line=str(item.get("type_line") or ""),
            oracle_text=str(item.get("oracle_text") or ""),
            power=item.get("power") if isinstance(item.get("power"), int) else None,
            toughness=item.get("toughness") if isinstance(item.get("toughness"), int) else None,
            keywords=frozenset(str(word) for word in item.get("keywords") or ()),
            colors=frozenset(str(color) for color in item.get("colors") or ()),
            color_identity=frozenset(str(color) for color in item.get("color_identity") or ()),
            produced_mana=frozenset(str(color) for color in item.get("produced_mana") or ()),
        )
        catalog[name.casefold()] = facts
        front = name.split(" // ")[0].casefold()
        catalog.setdefault(front, facts)
    return catalog


def card_facts(name: str | None, path: Path | None = None) -> CardFacts | None:
    """Printed facts for a card name, or None when the catalog does not know it."""
    if not name:
        return None
    return _lookup(name, str(path or _DEFAULT_PATH))


@lru_cache(maxsize=8192)
def _lookup(name: str, path: str) -> CardFacts | None:
    catalog = _catalog(path)
    key = name.strip().casefold()
    return catalog.get(key) or catalog.get(key.split(" // ")[0])


@lru_cache(maxsize=4)
def _split_card_names(path: str) -> dict[str, str]:
    """Casefolded half name -> catalog name of the split card it belongs to."""
    halves: dict[str, str] = {}
    for facts in _catalog(path).values():
        if " // " in facts.name:
            for half in facts.name.split(" // "):
                halves[half.strip().casefold()] = facts.name
    return halves


def canonical_card_name(name: str | None, path: Path | None = None) -> str:
    """The catalog name of the physical card a (half) name stands for.

    XMage names each half of a split, adventure or flip card on its own ("Wear",
    "Tear") next to the combined name ("Wear // Tear"). Anything that counts cards,
    not spell halves, must count them under one name. A name that is no known half
    is returned unchanged.
    """
    text = (name or "").strip()
    return _split_card_names(str(path or _DEFAULT_PATH)).get(text.casefold(), text)


_REMOVAL = re.compile(
    r"(destroy|exile) (up to (one|two|three) )?(another )?target"
    r"|(destroy|exile) (two|three|x) target"
    r"|deals? (\d+|x) damage to (any target|target creature|target (creature or )?planeswalker)"
    r"|deals? damage equal to [^.]* to (any target|target creature)"
    r"|target creature (an opponent controls )?gets -(\d+|x)/-(\d+|x)"
    r"|return target (nonland )?(creature|permanent|artifact|enchantment)[^.]* to its owner's hand"
    r"|put target (nonland )?(creature|permanent)[^.]* on (the )?(top|bottom) of its owner's library"
    r"|gain control of target"
    r"|fights? (target|another target|up to one target) creature"
    r"|enchanted creature can't attack or block|enchanted creature doesn't untap"
    r"|enchanted creature gets -"
    r"|target (player|opponent) sacrifices"
)
_WIPE = re.compile(
    r"(destroy|exile) (all|each) (other )?(nonland )?(creatures?|permanents?|artifacts?|nontoken)"
    r"|deals? (\d+|x) damage to each creature"
    r"|all creatures get -"
    r"|each player sacrifices"
)
_DRAW = re.compile(
    r"draws? (a|an additional|two|three|four|five|seven|x|that many) cards?|draw cards equal"
)
_SELECTION = re.compile(
    r"\bscry\b|\bsurveil\b|look at the top|discard a card, then draw|then discard"
)
_RAMP = re.compile(
    r"search your library for (up to (one|two) )?(a |an )?(basic )?(land|plains|island|swamp|mountain|forest)"
    r"|put (a|up to one) land card from your hand onto the battlefield|create (a|two|x) treasure"
)
_COUNTER = re.compile(r"counter target")
_PROTECTION = re.compile(
    r"(gains?|have|has) (hexproof|indestructible|shroud|protection)"
    r"|equipped creature has (hexproof|shroud)|phase out"
)
_RECURSION = re.compile(r"return [^.]* from your graveyard|from your graveyard (to|onto)")
_GRAVE_HATE = re.compile(r"exile (all cards from )?(target player's|each opponent's|all) graveyard")
_TOKENS = re.compile(
    r"create (a|an|one|two|three|four|five|six|seven|eight|nine|ten|x|that many|\d+) "
)
_ANTHEM = re.compile(r"(enchanted|equipped) creature gets \+|creatures you control get \+")
_TABLE = re.compile(r"each opponent (loses|deals?|sacrifices)|deals? \d+ damage to each opponent")


_PROFILES_PATH = _DEFAULT_PATH.parent / "structural_role_profiles.json"


@lru_cache(maxsize=2)
def _curated_profiles(path: str) -> dict[str, dict[str, object]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8")).get("profiles", [])
    except (OSError, ValueError):
        return {}
    return {
        str(item["oracle_name"]).casefold(): item
        for item in raw
        if isinstance(item, dict) and item.get("oracle_name")
    }


def curated_profile(name: str | None) -> dict[str, object] | None:
    """The project's curated structural profile of a card, when it has one.

    ``data/cards/structural_role_profiles.json`` holds hand-reviewed roles,
    floor value and immediate impact for the project's own cards; it is the
    better source wherever it exists, and printed-text roles fill the gaps.
    """
    if not name:
        return None
    return _curated_profiles(str(_PROFILES_PATH)).get(name.strip().casefold())


def _curated_roles(name: str) -> dict[CardRole, float] | None:
    profile = curated_profile(name)
    if profile is None:
        return None
    strengths = profile.get("role_strengths")
    listed = profile.get("roles")
    roles: dict[CardRole, float] = {}
    for role in listed if isinstance(listed, list) else ():
        try:
            card_role = CardRole(str(role))
        except ValueError:
            continue
        value = strengths.get(role, 1.0) if isinstance(strengths, dict) else 1.0
        roles[card_role] = float(value)
    return roles


def card_roles(facts: CardFacts) -> dict[CardRole, float]:
    """Strategic roles: curated profile first, else printed text and types."""
    return dict(_card_roles(facts))


@lru_cache(maxsize=8192)
def _card_roles(facts: CardFacts) -> dict[CardRole, float]:
    curated = _curated_roles(facts.name)
    if curated is not None:
        return curated
    text = facts.oracle_text.casefold()
    roles: dict[CardRole, float] = {}

    def add(role: CardRole, strength: float) -> None:
        roles[role] = max(roles.get(role, 0.0), strength)

    if facts.is_land:
        add(CardRole.MANA_SOURCE, 1.0)
        return roles
    if facts.produced_mana or "add {" in text or "add one mana" in text:
        add(CardRole.MANA_SOURCE, 1.0)
        add(CardRole.RAMP, 1.0 if facts.mana_value <= 3 else 0.6)
    if _RAMP.search(text):
        add(CardRole.RAMP, 1.0)
    if _WIPE.search(text):
        add(CardRole.WIPE, 1.2)
    if _REMOVAL.search(text):
        add(CardRole.REMOVAL, 1.0)
    if _COUNTER.search(text):
        add(CardRole.COUNTER, 1.0)
    if _DRAW.search(text):
        add(CardRole.DRAW, 1.0)
    if _SELECTION.search(text):
        add(CardRole.SELECTION, 0.7)
    if _PROTECTION.search(text):
        add(CardRole.PROTECTION, 0.9)
    if _RECURSION.search(text):
        add(CardRole.RECURSION, 0.8)
    if _GRAVE_HATE.search(text):
        add(CardRole.GRAVEYARD_HATE, 0.9)
    if _TOKENS.search(text):
        add(CardRole.TOKEN_SOURCE, 0.7)
    if _TABLE.search(text):
        add(CardRole.PAYOFF, 0.8)
    if _ANTHEM.search(text):
        add(CardRole.COMBAT_PAYOFF, 0.5)
    if "whenever" in text or "at the beginning of" in text:
        add(CardRole.ENGINE, 0.7)
    power = facts.power or 0
    if facts.is_creature and power >= 5:
        add(CardRole.FINISHER, min(1.5, power / 6.0))
    elif facts.is_creature and power >= 3:
        add(CardRole.COMBAT_PAYOFF, 0.6)
    if facts.is_planeswalker:
        add(CardRole.ENGINE, 1.0)
    return roles


def permanent_value(
    facts: CardFacts | None,
    *,
    power: int | None = None,
    toughness: int | None = None,
    is_commander: bool = False,
) -> float:
    """How much an opponent's (or one's own) permanent matters, roughly in mana.

    Board power/toughness (which include counters and pumps) win over printed
    values. Basic and utility lands are worth little as a target; a commander
    is worth a lot because it keeps coming back and carries the deck's plan.
    """
    if facts is None:
        base = 1.5 + max(0, power or 0) * 0.5
        return base + (6.0 if is_commander else 0.0)
    if facts.is_land:
        return 0.3 if not facts.oracle_text or len(facts.oracle_text) < 60 else 0.8
    value = max(1.0, facts.mana_value)
    effective_power = power if power is not None else facts.power
    effective_toughness = toughness if toughness is not None else facts.toughness
    if facts.is_creature:
        value += max(0, effective_power or 0) * 0.6 + max(0, effective_toughness or 0) * 0.15
        for keyword in ("Flying", "Trample", "Double strike", "Deathtouch", "Lifelink", "Menace"):
            if facts.has_keyword(keyword):
                value += 0.5
    roles = card_roles(facts)
    if CardRole.ENGINE in roles:
        value += 1.5
    if CardRole.MANA_SOURCE in roles and not facts.is_creature:
        value += 0.5
    if facts.is_planeswalker:
        value += 2.0
    if is_commander:
        value += 6.0
    return value


def evasion(facts: CardFacts | None, abilities: list[str] | tuple[str, ...] = ()) -> set[str]:
    """Evasion and combat keywords, from printed facts and live ability text."""
    found: set[str] = set()
    words = {word.casefold() for word in (facts.keywords if facts else ())}
    text = " ".join(str(rule).casefold() for rule in abilities)
    for keyword in (
        "flying",
        "reach",
        "menace",
        "trample",
        "first strike",
        "double strike",
        "deathtouch",
        "indestructible",
        "vigilance",
        "lifelink",
    ):
        if keyword in words or keyword in text:
            found.add(keyword)
    if "can't be blocked" in text or "can't be blocked" in (
        facts.oracle_text.casefold() if facts else ""
    ):
        found.add("unblockable")
    if "defender" in words or text.startswith("defender"):
        found.add("defender")
    return found


__all__ = [
    "COLOR_WORDS",
    "CardFacts",
    "card_facts",
    "card_roles",
    "curated_profile",
    "evasion",
    "is_basic_land_name",
    "permanent_value",
]
