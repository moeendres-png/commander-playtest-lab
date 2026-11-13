"""The deck universe as the browser shows it: per-card counted spread and co-occurrence.

Everything here is a plain count over one stored universe profile (see ``universe.py``),
with its denominator and its origin (profile, snapshot). The spread level (S-D, or U) is
the tier function of ``tiers.py`` applied to the inclusion share. It measures how often a
card is played in the chosen decks, not how strong it is: it does not touch the evidence
model or its unrated policy, and favourites, excludes and notes are never read here.

Name mapping: universe counts are keyed by the raw ``card_name`` of the imported decks.
A Studio card's name keys are its oracle name and its engine name, plus the front face of
a double-faced name unless another Studio card has that exact name (then the card is
flagged ``ambiguous_front_face``). Keys are compared case-insensitively
(``str.casefold``). A card's hits are the number of DISTINCT universe decks that list at
least one of its keys, so a deck listing two spellings counts once and spellings are never
summed; every raw spelling is still listed with its own deck count, and ``matched_name`` is
the spelling with the most decks. When no key occurs in the universe, absence cannot be
told from a spelling mismatch, so the card is reported as unmatched: level ``U``, share
``None``, never a zero.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from .sources import load_spellbook_combo_partners
from .store import StudioStore
from .tiers import MODEL_VERSION, TierParams, TierParamsDict, tier_for_share
from .universe import (
    UniverseDecks,
    UniverseSpec,
    _universe_spec,
    cooccurrence_in_decks,
    excluded_by_card_filter,
    excluded_no_date,
    get_profile,
    inclusion,
    resolve_universe,
    snapshot_id,
    universe_decks,
)

_COMBOS_PATH = Path(__file__).resolve().parents[3] / "data" / "meta" / "spellbook_combos.json"

NAME_NOT_FOUND = "NAME_NOT_FOUND_IN_UNIVERSE"
FILTER_CARD = "FILTER_CARD"
LEVEL_FILTER_CARD = "F"
MEANING = (
    "Verbreitung (gezählt): in wie vielen Decks des gewählten Universums die Karte steht. "
    "Das ist keine Kartenstärke und kein Tier der Bewertung."
)


def subset_note(spec: UniverseSpec, excluded_by_card_filter: int) -> str | None:
    """The text every view shows next to the denominator of a card-filtered universe.

    A universe that requires cards (``must_contain``) counts only the decks that contain
    all of them: its denominator is a subset of the decks the other filters select, not the
    commander's decks. ``None`` for an unfiltered universe."""
    required = spec.get("must_contain", [])
    if not required:
        return None
    return (
        f"Teilmenge: nur Decks mit {', '.join(required)} "
        f"({excluded_by_card_filter} Decks durch den Kartenfilter ausgeschlossen)"
    )


class ProfileSummary(TypedDict):
    profile: str
    spec: UniverseSpec
    version: int
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    excluded_no_date: int
    excluded_by_card_filter: int
    min_universe: int
    below_min_universe: bool
    subset_note: str | None
    snapshot_id: str
    data_class: str


class Spelling(TypedDict):
    name: str
    hits: int


class CardSpread(TypedDict):
    filter_card: bool
    card_id: str
    name: str
    matched: bool
    matched_name: str | None
    hits: int | None
    denominator: int
    share: float | None
    level: str
    reason: str
    spellings: list[Spelling]
    ambiguous_front_face: NotRequired[bool]


class SpreadUniverse(TypedDict):
    profile: str
    version: int
    snapshot_id: str
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    excluded_no_date: int
    excluded_by_card_filter: int
    must_contain: list[str]
    subset_note: str | None
    min_universe: int
    below_min_universe: bool
    data_class: str


class PoolSpread(TypedDict):
    universe: SpreadUniverse
    params: TierParamsDict
    model_version: str
    meaning: str
    cards: list[CardSpread]


class CooccurrencePair(TypedDict):
    card_name: str
    decks_together: int
    lift: float | None
    combo_partner: bool


class CardCooccurrence(TypedDict):
    card_id: str
    matched: bool
    matched_name: str | None
    profile: str | None
    snapshot_id: str
    denominator: int
    denominator_label: str
    decks_with_card: int | None
    decks_with_card_label: str
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    excluded_no_date: int
    excluded_by_card_filter: int
    must_contain: list[str]
    subset_note: str | None
    filter_card: bool
    pairs: list[CooccurrencePair]
    data_class: str


def _params_for(
    store: StudioStore, profile: str | None, spec: UniverseSpec | None = None
) -> TierParams:
    """Tier parameters of a profile: the model's cuts and fallback, with the
    profile's own ``min_universe`` when its spec sets one. The cuts are model
    constants of ``tiers.py`` (``MODEL_VERSION``) and are never read from a profile."""
    if profile is not None:
        spec = get_profile(store, profile)["spec"]
    spec = spec or {}
    default = TierParams()
    return TierParams(min_universe=spec.get("min_universe", default.min_universe))


def profile_summary(
    store: StudioStore, name: str, *, commander_names: Sequence[str] | None
) -> ProfileSummary:
    """Spec, deck count, breakdowns and snapshot of a stored profile (KeyError if unknown)."""
    profile = get_profile(store, name)
    counted = inclusion(store, profile=name, card_names=[], commander_names=commander_names)
    min_universe = _params_for(store, name).min_universe
    return {
        "profile": name,
        "spec": profile["spec"],
        "version": profile["version"],
        "denominator": counted["denominator"],
        "denominator_by_platform": counted["denominator_by_platform"],
        "denominator_by_bracket": counted["denominator_by_bracket"],
        "excluded_no_date": counted["excluded_no_date"],
        "excluded_by_card_filter": counted["excluded_by_card_filter"],
        "min_universe": min_universe,
        "below_min_universe": counted["denominator"] < min_universe,
        "subset_note": subset_note(profile["spec"], counted["excluded_by_card_filter"]),
        "snapshot_id": snapshot_id(store, profile=name, commander_names=commander_names),
        "data_class": counted["data_class"],
    }


def _front(name: str) -> str:
    return name.split(" // ")[0].strip()


def _name_keys(card: CardRow, taken: Counter[str]) -> tuple[list[str], bool]:
    """Casefolded name keys of a card and whether a front face was withheld as ambiguous.

    Keys are the oracle and engine names. The front face of a double-faced name is added
    only when no other Studio card has that exact name as its oracle or engine name."""
    own = [name.casefold() for name in (card[1], card[2]) if name]
    keys = list(dict.fromkeys(own))
    ambiguous = False
    for name in (card[1], card[2]):
        front = _front(name).casefold()
        if not front or front in keys:
            continue
        if taken[front] > 0:
            ambiguous = True
        else:
            keys.append(front)
    return keys, ambiguous


CardRow = tuple[str, str, str]


def _all_card_rows(store: StudioStore) -> list[CardRow]:
    rows = store.connection.execute(
        "SELECT card_id, oracle_name, engine_name FROM card_fact ORDER BY oracle_name, card_id"
    ).fetchall()
    return [(str(r["card_id"]), str(r["oracle_name"]), str(r["engine_name"])) for r in rows]


def _chosen(rows: list[CardRow], card_ids: Sequence[str] | None) -> list[CardRow]:
    if card_ids is None:
        return rows
    by_id = {row[0]: row for row in rows}
    chosen: list[CardRow] = []
    for card_id in card_ids:
        if card_id not in by_id:
            raise KeyError(card_id)
        chosen.append(by_id[card_id])
    return chosen


def _spread_of(
    card: CardRow,
    keys: list[str],
    ambiguous: bool,
    universe: UniverseDecks,
    by_key: dict[str, list[str]],
    params: TierParams,
    required: frozenset[str],
) -> tuple[CardSpread, set[str]]:
    card_id, oracle_name, _ = card
    denominator = universe["denominator"]
    decks_by_name = universe["decks_by_name"]
    raw_names = sorted({raw for key in keys for raw in by_key.get(key, [])})
    union: set[str] = set()
    for raw in raw_names:
        union |= decks_by_name[raw]
    spellings: list[Spelling] = sorted(
        ({"name": raw, "hits": len(decks_by_name[raw])} for raw in raw_names),
        key=lambda item: (-item["hits"], item["name"]),
    )
    result: CardSpread = {
        "filter_card": oracle_name in required,
        "card_id": card_id,
        "name": oracle_name,
        "matched": bool(union),
        "matched_name": spellings[0]["name"] if union else None,
        "hits": len(union) if union else None,
        "denominator": denominator,
        "share": None,
        "level": "U",
        "reason": NAME_NOT_FOUND,
        "spellings": spellings if union else [],
    }
    if ambiguous:
        result["ambiguous_front_face"] = True
    if union:
        share = len(union) / denominator if denominator else None
        result["share"] = share
        result["level"], result["reason"] = tier_for_share(share, denominator, params)
    if result["filter_card"]:
        # A card the universe requires is in every deck of the subset by definition
        # (share 2/2): that is the filter speaking, not the decks, so it gets no share and
        # no level. The deck count stays visible; the page labels it as a filter card.
        result["share"] = None
        result["level"], result["reason"] = LEVEL_FILTER_CARD, FILTER_CARD
    return result, union


def _taken_names(rows: list[CardRow]) -> Counter[str]:
    taken: Counter[str] = Counter()
    for _, oracle_name, engine_name in rows:
        for name in {oracle_name.casefold(), engine_name.casefold()}:
            taken[name] += 1
    return taken


NAME_CLASS_ORACLE = 0
NAME_CLASS_ENGINE = 1
NAME_CLASS_FRONT_FACE = 2


def name_claims(store: StudioStore, card_ids: Sequence[str]) -> dict[str, list[tuple[str, int]]]:
    """The casefolded name keys each given Studio card claims, with the kind of claim.

    The keys are exactly those of the counted spread (``_name_keys``): oracle name, engine
    name, and the front face of a double-faced name unless another Studio card has that
    exact name. The kind orders the claims (``NAME_CLASS_ORACLE`` before
    ``NAME_CLASS_ENGINE`` before ``NAME_CLASS_FRONT_FACE``) for a caller that must give one
    name to one card. Raises KeyError for an unknown card id."""
    rows = _all_card_rows(store)
    taken = _taken_names(rows)
    claims: dict[str, list[tuple[str, int]]] = {}
    for card in _chosen(rows, card_ids):
        keys, _ambiguous = _name_keys(card, taken)
        oracle, engine = card[1].casefold(), card[2].casefold()
        claims[card[0]] = [
            (
                key,
                NAME_CLASS_ORACLE
                if key == oracle
                else NAME_CLASS_ENGINE
                if key == engine
                else NAME_CLASS_FRONT_FACE,
            )
            for key in keys
        ]
    return claims


def _spread_all(
    store: StudioStore,
    profile: str | None,
    card_ids: Sequence[str] | None,
    commander_names: Sequence[str] | None,
    spec: UniverseSpec | None = None,
) -> tuple[UniverseDecks, list[tuple[CardSpread, set[str], list[str]]], TierParams]:
    universe = universe_decks(store, profile=profile, commander_names=commander_names, spec=spec)
    rows = _all_card_rows(store)
    taken = _taken_names(rows)
    by_key: dict[str, list[str]] = {}
    for raw in universe["decks_by_name"]:
        by_key.setdefault(raw.casefold(), []).append(raw)
    params = _params_for(store, profile, universe["spec"])
    required = frozenset(universe["spec"].get("must_contain", []))
    entries: list[tuple[CardSpread, set[str], list[str]]] = []
    for card in _chosen(rows, card_ids):
        keys, ambiguous = _name_keys(card, taken)
        spread, decks = _spread_of(card, keys, ambiguous, universe, by_key, params, required)
        entries.append((spread, decks, keys))
    return universe, entries, params


def pool_spread(
    store: StudioStore,
    profile: str,
    card_ids: Sequence[str] | None = None,
    *,
    commander_names: Sequence[str] | None,
) -> PoolSpread:
    """Counted spread of Studio cards (all, or the given ids) in one profile's universe.

    A card's hits are the distinct universe decks listing at least one of its name keys
    (casefolded) in a counted section. Raises KeyError for an unknown profile or card id."""
    universe, entries, params = _spread_all(store, profile, card_ids, commander_names)
    excluded_cards = excluded_by_card_filter(store, universe["spec"])
    return {
        "universe": {
            "profile": profile,
            "version": get_profile(store, profile)["version"],
            "snapshot_id": universe["snapshot_id"],
            "denominator": universe["denominator"],
            "denominator_by_platform": universe["denominator_by_platform"],
            "denominator_by_bracket": universe["denominator_by_bracket"],
            "excluded_no_date": excluded_no_date(store, universe["spec"]),
            "excluded_by_card_filter": excluded_cards,
            "must_contain": list(universe["spec"].get("must_contain", [])),
            "subset_note": subset_note(universe["spec"], excluded_cards),
            "min_universe": params.min_universe,
            "below_min_universe": universe["denominator"] < params.min_universe,
            "data_class": universe["data_class"],
        },
        "params": params.to_dict(),
        "model_version": MODEL_VERSION,
        "meaning": MEANING,
        "cards": [spread for spread, _, _ in entries],
    }


def spread_for_spec(
    store: StudioStore,
    spec: UniverseSpec,
    card_ids: Sequence[str] | None,
    *,
    commander_names: Sequence[str],
) -> tuple[int, str, list[CardSpread]]:
    """(denominator, snapshot id, counted spread) of Studio cards over a free spec, e.g. all
    local decks of the commander. The same machinery as a stored profile's ``pool_spread``."""
    universe, entries, _params = _spread_all(store, None, card_ids, commander_names, spec)
    return universe["denominator"], universe["snapshot_id"], [entry[0] for entry in entries]


class DeckFilterCard(TypedDict):
    card_id: str
    name: str
    filter_card: bool
    matched: bool
    hits: int | None
    denominator: int
    share: float | None


class DeckFilter(TypedDict):
    commander: list[str]
    profile: str | None
    must_contain: list[str]
    decks: int
    of: int
    label: str
    snapshot_id: str
    data_class: str
    cards: list[DeckFilterCard]


def filtered_spec(
    store: StudioStore,
    must_contain: Sequence[str],
    *,
    commander_names: Sequence[str],
    profile: str | None = None,
) -> UniverseSpec:
    """The spec of the commander's decks (or of ``profile`` narrowed to the commander) that
    additionally must contain every card of ``must_contain``. Raises ValueError for a name
    that names no single collection card."""
    base = _universe_spec(store, profile, None, commander_names)
    wanted = sorted({*base.get("must_contain", []), *(name for name in must_contain if name)})
    spec = {key: value for key, value in base.items() if key != "must_contain"}
    if wanted:
        spec["must_contain"] = wanted
    return cast(UniverseSpec, spec)


def deck_filter(
    store: StudioStore,
    must_contain: Sequence[str],
    *,
    commander_names: Sequence[str],
    profile: str | None = None,
    card_ids: Sequence[str] | None = None,
) -> DeckFilter:
    """Source-deck figures of the commander over only the decks that contain ALL chosen
    cards, each with its denominator ("Teilmenge: N von M Decks").

    ``of`` (M) is the number of decks the same scope counts without the card filter, ``decks``
    (N) the decks that contain every chosen card. It is the one universe machinery (a free
    spec instead of a stored profile): a chosen card is a filter card, in every deck of the
    subset by definition, so it gets no hits and no share. No deck in the subset means an
    unknown share, never 0. Raises ValueError for a name that is no collection card."""
    spec = filtered_spec(store, must_contain, commander_names=commander_names, profile=profile)
    base_spec = cast(UniverseSpec, {k: v for k, v in spec.items() if k != "must_contain"})
    if profile is not None:
        stored_required = get_profile(store, profile)["spec"].get("must_contain", [])
        if stored_required:
            base_spec["must_contain"] = list(stored_required)
    of = len(resolve_universe(store, base_spec))
    universe, entries, _params = _spread_all(store, None, card_ids, commander_names, spec)
    cards: list[DeckFilterCard] = [
        {
            "card_id": spread["card_id"],
            "name": spread["name"],
            "filter_card": spread["filter_card"],
            "matched": spread["matched"],
            "hits": None if spread["filter_card"] else spread["hits"],
            "denominator": spread["denominator"],
            "share": None if spread["filter_card"] else spread["share"],
        }
        for spread, _decks, _keys in entries
    ]
    decks = universe["denominator"]
    return {
        "commander": list(commander_names),
        "profile": profile,
        "must_contain": list(universe["spec"].get("must_contain", [])),
        "decks": decks,
        "of": of,
        "label": f"Teilmenge: {decks} von {of} Decks",
        "snapshot_id": universe["snapshot_id"],
        "data_class": universe["data_class"],
        "cards": cards,
    }


def _combo_partners(commander_names: Sequence[str] | None) -> dict[str, set[str]]:
    """Spellbook combo partners per card for the named commanders, merged.

    The commander key of the curated combo file is the name's first fragment, the
    same matching ``sources.load_spellbook_combo_cards`` applies for evidence."""
    merged: dict[str, set[str]] = {}
    for name in commander_names or []:
        found = load_spellbook_combo_partners(_COMBOS_PATH, commander=name.split(",")[0].strip())
        for card, others in found.items():
            merged.setdefault(card, set()).update(others)
    return merged


def card_cooccurrence(
    store: StudioStore,
    profile: str | None,
    card_id: str,
    limit: int = 25,
    *,
    commander_names: Sequence[str] | None,
    spec: UniverseSpec | None = None,
) -> CardCooccurrence:
    """Cards played together with one card in the universe, over the card's counted decks.

    Each pair also carries its ``lift`` — P(partner | this card) over P(partner in the
    universe), ``None`` when a denominator is 0 — and ``combo_partner``, whether the
    pair shares a verified Spellbook combo listed for the commander. Raises KeyError
    for an unknown profile or card, ValueError when ``limit`` < 1."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    universe, entries, _params = _spread_all(store, profile, [card_id], commander_names, spec)
    card, decks, keys = entries[0]
    excluded_cards = excluded_by_card_filter(store, universe["spec"])
    base: CardCooccurrence = {
        "card_id": card_id,
        "matched": card["matched"],
        "matched_name": card["matched_name"],
        "profile": profile,
        "snapshot_id": universe["snapshot_id"],
        "denominator": universe["denominator"],
        "denominator_label": "Decks im Universum",
        "decks_with_card": None,
        "decks_with_card_label": "Decks mit dieser Karte",
        "denominator_by_platform": universe["denominator_by_platform"],
        "denominator_by_bracket": universe["denominator_by_bracket"],
        "excluded_no_date": excluded_no_date(store, universe["spec"]),
        "excluded_by_card_filter": excluded_cards,
        "must_contain": list(universe["spec"].get("must_contain", [])),
        "subset_note": subset_note(universe["spec"], excluded_cards),
        "filter_card": card["filter_card"],
        "pairs": [],
        "data_class": universe["data_class"],
    }
    if not card["matched"]:
        return base
    decks_with_card = len(decks)
    base["decks_with_card"] = decks_with_card
    partners = _combo_partners(commander_names)
    own_partners: set[str] = set()
    for key in keys:
        own_partners |= partners.get(key, set())
    denominator = universe["denominator"]
    decks_by_name = universe["decks_by_name"]
    pairs: list[CooccurrencePair] = []
    for pair in cooccurrence_in_decks(store, decks, set(keys), limit):
        partner_decks = len(decks_by_name.get(pair["card_name"], set()))
        lift = None
        if denominator and decks_with_card and partner_decks:
            lift = (pair["decks_together"] / decks_with_card) / (partner_decks / denominator)
        pairs.append(
            {
                "card_name": pair["card_name"],
                "decks_together": pair["decks_together"],
                "lift": lift,
                "combo_partner": pair["card_name"].casefold() in own_partners,
            }
        )
    base["pairs"] = pairs
    return base


__all__ = [
    "FILTER_CARD",
    "LEVEL_FILTER_CARD",
    "NAME_CLASS_ENGINE",
    "NAME_CLASS_FRONT_FACE",
    "NAME_CLASS_ORACLE",
    "NAME_NOT_FOUND",
    "CardCooccurrence",
    "CardSpread",
    "CooccurrencePair",
    "DeckFilter",
    "DeckFilterCard",
    "PoolSpread",
    "ProfileSummary",
    "card_cooccurrence",
    "deck_filter",
    "filtered_spec",
    "name_claims",
    "pool_spread",
    "profile_summary",
    "spread_for_spec",
    "subset_note",
]
