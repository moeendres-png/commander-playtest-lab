"""Deck universes: owner-selected sets of source decks, and counts over them.

A *universe* is a stored profile (``universe_profile``) whose spec selects source decks
from the corpus: by platform, by cohort membership (``corpus_cohort`` rows such as
``bracket:3`` or ``source:edhrec``), by deck date range and by a minimum main-deck size.
A spec may also name the commanders its decks must be bound to (exactly this set: a deck
bound to a partner pair belongs to the pair, never to one partner alone) and a ``min_universe``
(the smallest denominator the counted spread of ``tiers.py`` still grades; the tier
cuts themselves stay code constants of the tier model, never profile settings).
Storing a profile validates its platform, cohort and commander values against what
the store actually holds, so a typo is refused instead of silently counting an empty
universe; a dimension whose stock is still empty cannot be checked and is accepted.
A profile carries a version: the first save is version 1, every later save of the same
name keeps ``created_at`` and raises the version by one, stamping ``updated_at``; a
profile can be deleted, and deleting one the store does not hold is an error, never a
silent no-op.

A spec may also require cards: ``must_contain`` names collection cards (oracle names)
and a deck of the universe must contain *every* one of them. Containment is a main-deck
statement: a card counts when a row of the deck's main sections (``main``/``mainboard``,
quantity above zero) names it — under any spelling the collection knows for the card
(oracle name, engine name, or a front face that is no card's exact name; a front face
several cards share is a spelling of each of them, exactly as the counted spread
attributes it, but it names no single card and so cannot state a requirement). A row in the ``commander``
section never counts by itself; the single exception is the deck's own commander: when
a required card *is* the commander the deck is bound to (``commander_binding``), the
deck contains it by definition, even without a main-deck row. Sideboard and maybeboard
rows never satisfy a requirement. Required names are validated against the collection
at save time and stored as the cards' oracle names; a name no collection card carries
is refused, never silently counted as an empty universe. How many decks the card filter
drops is reported next to every denominator (``excluded_by_card_filter``), exactly like
the date filter's ``excluded_no_date``.
Every figure computed over a universe is a plain count with its denominator: inclusion of
a card is the number of distinct universe decks whose counted sections (``main`` and
``mainboard``, the same section under the spelling of the decklist and the corpus importer,
plus ``commander`` and ``companion``) contain it, over the number of decks in the universe. Exact duplicates
never count twice: decks of the universe that share a content fingerprint count once
(the lowest deck id), so the same list stored under two ids is one deck *inside the
selected universe*, whatever its siblings outside it look like. An empty fingerprint
means "content unknown": such a deck is its own key and is never deduplicated. Only cards
with a quantity above zero count, and a deck without any such row in a counted section is
not part of any universe. A deck carrying several bracket cohorts is reported under the
bucket ``multiple`` in the bracket breakdown. Sections ``sideboard`` and ``maybeboard`` are
both excluded here, because both are outside the deck that was played. The minimum deck size
counts each card once per deck and section group: a card listed in both ``main`` and
``mainboard`` contributes its larger quantity, not the sum.

An empty spec selects every stored source deck. A profile whose filters match no deck
yields a universe of size 0; shares over it are ``None`` (unknown), never zero.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import TypedDict, cast

from . import memo
from ._coerce import to_int
from .cache import cached
from .store import COUNTED_SECTIONS, StudioStore, now_utc

# The sections a ``must_contain`` requirement reads: the main deck only. Deliberately
# narrower than COUNTED_SECTIONS — a commander or companion row is not a main-deck card
# (the commander exception is the binding rule in ``resolve_universe``, not a section).
MAIN_SECTIONS = ("main", "mainboard")
_SPEC_KEYS = {
    "platforms",
    "cohorts",
    "commanders",
    "date_from",
    "date_to",
    "min_main_cards",
    "min_universe",
    "must_contain",
}


class UniverseSpec(TypedDict, total=False):
    """A validated universe spec; absent keys mean "no filter"."""

    platforms: list[str]
    cohorts: list[str]
    commanders: list[str]
    date_from: str
    date_to: str
    min_main_cards: int
    min_universe: int
    must_contain: list[str]


class Profile(TypedDict):
    profile_id: str
    name: str
    spec: UniverseSpec
    created_at: str
    version: int
    updated_at: str | None


class SavedProfile(TypedDict):
    profile_id: str
    name: str
    spec: UniverseSpec
    version: int
    created_at: str
    updated_at: str


class InclusionRow(TypedDict):
    card_name: str
    hits: int
    denominator: int
    share: float | None


class InclusionResult(TypedDict):
    profile: str | None
    spec: UniverseSpec
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    excluded_no_date: int
    excluded_by_card_filter: int
    empty: bool
    empty_reason: str | None
    rows: list[InclusionRow]
    data_class: str


class OptionValue(TypedDict):
    value: str
    decks: int


class UniverseOptions(TypedDict):
    platforms: list[OptionValue]
    cohorts: list[OptionValue]
    commanders: list[OptionValue]
    cards: list[OptionValue]


class CooccurrenceRow(TypedDict):
    card_name: str
    decks_together: int


class CooccurrenceResult(TypedDict):
    card_name: str
    profile: str | None
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    decks_with_card: int
    pairs: list[CooccurrenceRow]
    data_class: str


def _string_list(spec: Mapping[str, object], key: str) -> list[str]:
    values = spec.get(key) or []
    if isinstance(values, str) or not isinstance(values, (list, tuple)):
        raise ValueError(f"universe spec {key} must be a list of non-empty strings")
    strings = [value for value in values if isinstance(value, str) and value]
    if len(strings) != len(values):
        raise ValueError(f"universe spec {key} must be a list of non-empty strings")
    return sorted(set(strings))


def _iso_date(spec: Mapping[str, object], key: str) -> str | None:
    if not spec.get(key):
        return None
    try:
        return datetime.date.fromisoformat(str(spec[key])[:10]).isoformat()
    except ValueError:
        raise ValueError(f"universe spec {key} must be an ISO date (YYYY-MM-DD)") from None


def _validate_spec(spec: Mapping[str, object]) -> UniverseSpec:
    unknown = set(spec) - _SPEC_KEYS
    if unknown:
        raise ValueError(f"unknown universe spec keys: {sorted(unknown)}")
    cleaned: UniverseSpec = {}
    platforms = _string_list(spec, "platforms")
    if platforms:
        cleaned["platforms"] = platforms
    cohorts = _string_list(spec, "cohorts")
    if cohorts:
        cleaned["cohorts"] = cohorts
    commanders = _string_list(spec, "commanders")
    if commanders:
        cleaned["commanders"] = commanders
    date_from = _iso_date(spec, "date_from")
    if date_from is not None:
        cleaned["date_from"] = date_from
    date_to = _iso_date(spec, "date_to")
    if date_to is not None:
        cleaned["date_to"] = date_to
    if spec.get("min_main_cards") is not None:
        minimum = to_int(spec["min_main_cards"])
        if minimum < 0:
            raise ValueError("universe spec min_main_cards must not be negative")
        cleaned["min_main_cards"] = minimum
    if spec.get("min_universe") is not None:
        min_universe = to_int(spec["min_universe"])
        if min_universe < 1:
            raise ValueError("universe spec min_universe must be at least 1")
        cleaned["min_universe"] = min_universe
    must_contain = _string_list(spec, "must_contain")
    if must_contain:
        cleaned["must_contain"] = must_contain
    return cleaned


def cohort_family(cohort: str) -> str:
    """The family of a cohort: the text before the first ``:`` (``bracket`` for
    ``bracket:3``); a cohort without a colon is a family of its own."""
    return cohort.split(":", 1)[0]


def cohort_families(cohorts: Sequence[str]) -> dict[str, list[str]]:
    """Cohorts grouped by family, in stable order. Within a family they are OR, across
    families AND (see ``resolve_universe``)."""
    families: dict[str, list[str]] = {}
    for cohort in sorted(set(cohorts)):
        families.setdefault(cohort_family(cohort), []).append(cohort)
    return families


def _known_values(store: StudioStore, sql: str) -> set[str]:
    return {str(row[0]) for row in store.connection.execute(sql)}


def _card_name_index(
    store: StudioStore,
) -> tuple[dict[str, frozenset[str]], dict[str, str]]:
    """Cached form of ``_build_card_name_index`` (read-only result)."""
    return cached(store, ("card_name_index",), lambda: _build_card_name_index(store))


def _build_card_name_index(
    store: StudioStore,
) -> tuple[dict[str, frozenset[str]], dict[str, str]]:
    """The collection's name discipline, shared with the counted spread.

    Returns (oracle name -> its casefolded spellings, unambiguous spelling -> oracle
    name). A card's spellings are its oracle name, its engine name, and the front face
    of either, unless that front face is the exact name of a card (then it names that
    card, never this one). A front face several cards share is a spelling of each of
    them — a deck listing it counts for every one, exactly as the counted spread
    attributes it — but it names no single card, so it is absent from the second map
    and cannot be used to *state* a requirement."""
    cards = [
        (str(row["oracle_name"]), str(row["engine_name"]))
        for row in store.connection.execute("SELECT oracle_name, engine_name FROM card_fact")
    ]
    taken = {spelling.casefold() for pair in cards for spelling in pair}
    by_oracle: dict[str, set[str]] = {}
    for oracle, engine in cards:
        keys = by_oracle.setdefault(oracle, set())
        for spelling in (oracle, engine):
            keys.add(spelling.casefold())
            front = spelling.split(" // ")[0].strip().casefold()
            if front and front not in taken:
                keys.add(front)
    owners: dict[str, str] = {}
    ambiguous: set[str] = set()
    for oracle, keys in by_oracle.items():
        for key in keys:
            if key in owners and owners[key] != oracle:
                ambiguous.add(key)
            owners.setdefault(key, oracle)
    unique = {key: oracle for key, oracle in owners.items() if key not in ambiguous}
    return {oracle: frozenset(keys) for oracle, keys in by_oracle.items()}, unique


class UnknownUniverseCards(ValueError):
    """Card names that name no single collection card; ``names`` carries them as a list, so
    a caller formats them without parsing the message."""

    def __init__(self, names: Sequence[str], *, stock: int | None = None) -> None:
        self.names = sorted(set(names))
        suffix = f"; the store holds {stock} collection cards" if stock is not None else ""
        super().__init__(f"unknown universe card(s): {self.names}{suffix}")


def _required_cards(store: StudioStore, names: Sequence[str]) -> list[tuple[str, frozenset[str]]]:
    """Resolve ``must_contain`` names to (oracle name, its casefolded spellings).

    Raises ValueError naming every name that names no single collection card: an
    unresolvable requirement must fail loudly, never count as an empty universe."""
    by_oracle, unique = _card_name_index(store)
    resolved: list[tuple[str, frozenset[str]]] = []
    unknown: list[str] = []
    for name in names:
        oracle = unique.get(name.casefold())
        if oracle is None:
            unknown.append(name)
        else:
            resolved.append((oracle, by_oracle[oracle]))
    if unknown:
        raise UnknownUniverseCards(unknown)
    return resolved


def _validate_against_stock(store: StudioStore, cleaned: UniverseSpec) -> None:
    """Refuse spec values the store does not hold (a typo must not count as empty).

    A dimension whose stock is empty (no decks imported yet) cannot be checked and is
    accepted as-is; the first import then decides what the profile selects."""
    checks = (
        (
            cleaned.get("platforms"),
            "platform",
            _known_values(store, "SELECT DISTINCT platform FROM corpus_deck"),
        ),
        (
            cleaned.get("cohorts"),
            "cohort",
            _known_values(store, "SELECT DISTINCT cohort FROM corpus_cohort"),
        ),
        (
            cleaned.get("commanders"),
            "commander",
            _known_values(
                store,
                "SELECT DISTINCT commander_name FROM commander_binding WHERE kind = 'corpus_deck'",
            ),
        ),
    )
    for values, label, known in checks:
        if not values or not known:
            continue
        unknown = sorted(set(values) - known)
        if unknown:
            raise ValueError(
                f"unknown universe {label}(s): {unknown}; the store holds: {sorted(known)}"
            )
    required = cleaned.get("must_contain")
    if required:
        by_oracle, unique = _card_name_index(store)
        if by_oracle:
            unknown_cards = sorted({name for name in required if name.casefold() not in unique})
            if unknown_cards:
                raise UnknownUniverseCards(unknown_cards, stock=len(by_oracle))
            # The stored spec names the cards by their oracle name, whatever spelling
            # the caller used, so a profile always reads the same.
            cleaned["must_contain"] = sorted({unique[name.casefold()] for name in required})


def save_profile(store: StudioStore, name: str, spec: Mapping[str, object]) -> SavedProfile:
    """Store (or replace) a named universe profile; returns the stored profile.

    The first save of a name is version 1; replacing a profile keeps its
    ``created_at`` and raises the version by one, so a same-named profile whose
    meaning changed is distinguishable from the one counts were taken with.
    Raises ValueError for a malformed spec and for platform, cohort, commander or
    card values the store does not hold (see ``_validate_against_stock``)."""
    cleaned = _validate_spec(spec)
    _validate_against_stock(store, cleaned)
    profile_id = f"universe:{name}"
    stamp = now_utc()
    with store.connection as db:
        existing = db.execute(
            "SELECT version, created_at FROM universe_profile WHERE name = ?", (name,)
        ).fetchone()
        if existing is None:
            version, created_at = 1, stamp
        else:
            version, created_at = int(existing["version"]) + 1, str(existing["created_at"])
        db.execute(
            "INSERT OR REPLACE INTO universe_profile"
            "(profile_id, name, spec, created_at, version, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (profile_id, name, json.dumps(cleaned, sort_keys=True), created_at, version, stamp),
        )
    return {
        "profile_id": profile_id,
        "name": name,
        "spec": cleaned,
        "version": version,
        "created_at": created_at,
        "updated_at": stamp,
    }


def delete_profile(store: StudioStore, name: str) -> None:
    """Delete a universe profile. Raises KeyError when the store holds no such
    profile — deleting nothing is an explicit error, never a silent no-op."""
    with store.connection as db:
        if db.execute("DELETE FROM universe_profile WHERE name = ?", (name,)).rowcount == 0:
            raise KeyError(name)


def list_profiles(store: StudioStore) -> list[dict[str, object]]:
    rows = store.connection.execute(
        "SELECT profile_id, name, spec, created_at, version, updated_at "
        "FROM universe_profile ORDER BY name"
    ).fetchall()
    return [
        {
            "profile_id": row["profile_id"],
            "name": row["name"],
            "spec": json.loads(row["spec"]),
            "created_at": row["created_at"],
            "version": row["version"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_profile(store: StudioStore, name: str) -> Profile:
    row = store.connection.execute(
        "SELECT profile_id, name, spec, created_at, version, updated_at "
        "FROM universe_profile WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        raise KeyError(name)
    profile: Profile = {
        "profile_id": str(row["profile_id"]),
        "name": str(row["name"]),
        "spec": json.loads(row["spec"]),
        "created_at": str(row["created_at"]),
        "version": int(row["version"]),
        "updated_at": str(row["updated_at"]) if row["updated_at"] is not None else None,
    }
    return profile


def options(store: StudioStore, *, commander_names: Sequence[str] | None = None) -> UniverseOptions:
    """Memoized per data epoch (read-only result); see ``_options`` for the meaning."""
    scope = tuple(sorted(set(commander_names))) if commander_names else None
    return memo.cached(store, "universe_options", scope, lambda: _options(store, commander_names))


def _options(store: StudioStore, commander_names: Sequence[str] | None) -> UniverseOptions:
    """The spec values the store holds, each with the decks a universe would count.

    The count of a value is the size of the universe that selects only decks of that
    value (plus the ``commander_names`` scope when given) under the one counting rule
    of ``resolve_universe`` — duplicates collapsed, decks without a counted card row
    out — so the number next to a value is the denominator it would produce, never a
    raw row count. Values that would count no deck are not offered. The web route always
    passes a commander: without a scope the counts run over every commander's decks, a
    mixed figure no page may show. With a scope, the commander dimension offers the
    scoped commander itself with the size of the scoped universe, never a combination with
    another commander; for a partner-pair scope it offers no commander value at all."""
    scope: UniverseSpec = {}
    if commander_names:
        scope["commanders"] = sorted(set(commander_names))

    def offer(spec: UniverseSpec, value: str) -> OptionValue | None:
        decks = len(resolve_universe(store, spec))
        return {"value": value, "decks": decks} if decks else None

    def collect(specs: list[tuple[UniverseSpec, str]]) -> list[OptionValue]:
        found = [item for spec, value in specs if (item := offer(spec, value))]
        return sorted(found, key=lambda item: item["value"])

    platforms = _known_values(store, "SELECT DISTINCT platform FROM corpus_deck")
    cohorts = _known_values(store, "SELECT DISTINCT cohort FROM corpus_cohort")
    commander_specs: list[tuple[UniverseSpec, str]]
    if commander_names:
        # A partner pair is one scope: a single name would select another universe (the
        # decks of that commander alone), so nothing is offered for a pair.
        commander_specs = [(scope, scope["commanders"][0])] if len(scope["commanders"]) == 1 else []
    else:
        commander_specs = [
            (cast(UniverseSpec, {"commanders": [value]}), value)
            for value in _known_values(
                store,
                "SELECT DISTINCT commander_name FROM commander_binding WHERE kind = 'corpus_deck'",
            )
        ]
    return {
        "platforms": collect(
            [(cast(UniverseSpec, {**scope, "platforms": [value]}), value) for value in platforms]
        ),
        "cohorts": collect(
            [(cast(UniverseSpec, {**scope, "cohorts": [value]}), value) for value in cohorts]
        ),
        "commanders": collect(commander_specs),
        "cards": _with_pool_cards(store, _card_options(store, scope), commander_names),
    }


def _with_pool_cards(
    store: StudioStore, counted: list[OptionValue], commander_names: Sequence[str] | None
) -> list[OptionValue]:
    """The card options of a commander's universe form: the cards its decks contain (with
    their deck counts) plus every other card of the commander's legal pool with 0 decks, so
    a picker always has suggestions. Only names that name exactly one collection card are
    offered (the same names ``must_contain`` accepts). Without a commander nothing is added."""
    if not commander_names:
        return counted
    from .decks import color_set

    identity: frozenset[str] = frozenset()
    for name in commander_names:
        row = store.connection.execute(
            "SELECT color_identity FROM card_fact WHERE oracle_name = ?", (name,)
        ).fetchone()
        if row is None:
            return counted
        identity |= color_set(row["color_identity"])
    _by_oracle, unique = _card_name_index(store)
    have = {item["value"] for item in counted}
    own = set(commander_names)
    extra: list[OptionValue] = []
    for row in store.connection.execute(
        "SELECT c.oracle_name, c.color_identity FROM card_fact c JOIN inventory i USING (card_id) "
        "WHERE c.commander_legal = 1"
    ):
        name = str(row["oracle_name"])
        if name in have or name in own or unique.get(name.casefold()) != name:
            continue
        if color_set(row["color_identity"]) <= identity:
            have.add(name)
            extra.append({"value": name, "decks": 0})
    return sorted([*counted, *extra], key=lambda item: item["value"])


def bound_commander_sets(store: StudioStore) -> list[list[str]]:
    """The commander (or partner pair) sets that have source decks bound to them.

    One entry per distinct set of commander names a stored source deck is bound to, in
    stable order. Reports that must never mix commanders walk this list and count each
    set on its own (see ``resolve_universe``: a deck belongs to exactly one such set)."""
    names: dict[str, set[str]] = {}
    for row in store.connection.execute(
        "SELECT b.key, b.commander_name FROM commander_binding b "
        "JOIN corpus_deck d ON d.deck_id = b.key WHERE b.kind = 'corpus_deck'"
    ):
        names.setdefault(str(row[0]), set()).add(str(row[1]))
    return [list(item) for item in sorted({tuple(sorted(found)) for found in names.values()})]


def _card_options(store: StudioStore, scope: UniverseSpec) -> list[OptionValue]:
    """Collection cards a ``must_contain`` requirement can name, with deck counts.

    The count of a card is the size of the universe the scope plus the single-card
    requirement selects — counted in one pass over the scope's decks under the same
    containment rule ``resolve_universe`` applies (main sections, plus the deck's own
    commander), so the offered number is the denominator the filter would produce.
    Cards no scope deck contains are not offered."""
    deck_ids = resolve_universe(store, scope)
    if not deck_ids:
        return []
    by_oracle, unique = _card_name_index(store)
    if not by_oracle:
        return []
    owners: dict[str, list[str]] = {}
    for oracle, keys in by_oracle.items():
        for key in keys:
            owners.setdefault(key, []).append(oracle)
    bound = {
        str(row[0]): str(row[1])
        for row in store.connection.execute(
            "SELECT key, commander_name FROM commander_binding WHERE kind = 'corpus_deck'"
        )
    }
    counts: dict[str, int] = {}
    main_marks = ", ".join("?" for _ in MAIN_SECTIONS)
    with _universe_table(store, deck_ids) as universe_deck:
        spellings: dict[str, set[str]] = {}
        for deck_id, card_name in store.connection.execute(
            f"SELECT c.deck_id, c.card_name FROM corpus_deck_card c "
            f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
            f"WHERE c.section IN ({main_marks}) AND c.quantity > 0",
            MAIN_SECTIONS,
        ):
            spellings.setdefault(str(deck_id), set()).add(str(card_name).casefold())
    for deck_id in deck_ids:
        found: set[str] = set()
        for name in spellings.get(deck_id, set()):
            found.update(owners.get(name, []))
        commander = bound.get(deck_id)
        if commander is not None and commander.casefold() in unique:
            found.add(unique[commander.casefold()])
        for oracle in found:
            counts[oracle] = counts.get(oracle, 0) + 1
    return [
        {"value": oracle, "decks": decks} for oracle, decks in sorted(counts.items()) if decks > 0
    ]


def excluded_no_date(store: StudioStore, spec: Mapping[str, object]) -> int:
    """Decks a spec's date filter drops only because they carry no deck date.

    Counted exactly: decks the same spec without its date bounds would select, that the
    date bounds remove, and whose stored ``deck_date`` is empty. Decks dated outside the
    range are excluded by their date, not by its absence, and are not counted here.
    Without a date bound the count is 0."""
    cleaned = _validate_spec(spec)
    if not cleaned.get("date_from") and not cleaned.get("date_to"):
        return 0
    undated = dict(cleaned)
    undated.pop("date_from", None)
    undated.pop("date_to", None)
    undated_spec = cast(UniverseSpec, undated)
    dropped = set(resolve_universe(store, undated_spec)) - set(resolve_universe(store, cleaned))
    if not dropped:
        return 0
    with _universe_table(store, sorted(dropped)) as universe_deck:
        row = store.connection.execute(
            f"SELECT COUNT(*) FROM corpus_deck d JOIN {universe_deck} u "
            "ON u.deck_id = d.deck_id WHERE d.deck_date IS NULL OR d.deck_date = ''"
        ).fetchone()
    return int(row[0])


def excluded_by_card_filter(store: StudioStore, spec: Mapping[str, object]) -> int:
    """Decks a spec's ``must_contain`` filter drops.

    Counted exactly, as the set difference the module reports for the date filter:
    decks the same spec without its card requirement would select, minus the decks
    the requirement keeps. Without a card requirement the count is 0."""
    cleaned = _validate_spec(spec)
    if not cleaned.get("must_contain"):
        return 0
    unfiltered = dict(cleaned)
    unfiltered.pop("must_contain", None)
    unfiltered_spec = cast(UniverseSpec, unfiltered)
    return len(
        set(resolve_universe(store, unfiltered_spec)) - set(resolve_universe(store, cleaned))
    )


def resolve_universe(store: StudioStore, spec: Mapping[str, object]) -> list[str]:
    """Deck ids of the universe a spec selects, in stable order.

    Resolved once per store state and spec (see ``cache.py``): one request that needs the
    universe several times (denominator, snapshot, exclusion counts, spread) pays for it once."""
    cleaned = _validate_spec(spec)
    # min_universe is a threshold read by the callers, not a filter: it must not split the cache
    selecting = {name: value for name, value in cleaned.items() if name != "min_universe"}
    key = ("resolve", json.dumps(selecting, sort_keys=True))
    return list(cached(store, key, lambda: tuple(_resolve(store, cleaned))))


def _resolve(store: StudioStore, cleaned: UniverseSpec) -> list[str]:
    where = ["1 = 1"]
    parameters: list[str] = []
    if cleaned.get("platforms"):
        marks = ", ".join("?" for _ in cleaned["platforms"])
        where.append(f"d.platform IN ({marks})")
        parameters.extend(cleaned["platforms"])
    if cleaned.get("date_from"):
        where.append("d.deck_date >= ?")
        parameters.append(cleaned["date_from"])
    if cleaned.get("date_to"):
        where.append("d.deck_date <= ?")
        parameters.append(cleaned["date_to"])
    sql = f"SELECT d.deck_id, d.fingerprint FROM corpus_deck d WHERE {' AND '.join(where)}"
    selected = [(str(row[0]), str(row[1])) for row in store.connection.execute(sql, parameters)]
    deck_ids = [deck_id for deck_id, _ in selected]
    for family_cohorts in cohort_families(cleaned.get("cohorts", [])).values():
        # Cohorts of one family (``bracket:3`` and ``bracket:4``) are alternatives: a deck
        # belongs to the family when it is in ANY of the ticked cohorts. Different families
        # (a bracket and a platform) narrow each other.
        marks = ", ".join("?" for _ in family_cohorts)
        members = {
            str(row[0])
            for row in store.connection.execute(
                f"SELECT deck_id FROM corpus_cohort WHERE cohort IN ({marks})", family_cohorts
            )
        }
        deck_ids = [deck_id for deck_id in deck_ids if deck_id in members]
    wanted_commanders = frozenset(cleaned.get("commanders", []))
    if wanted_commanders:
        # Only decks bound to exactly these commanders count: a deck bound to a partner
        # pair is a deck of the pair, not of either partner alone (the same exact-set rule
        # as ``builder.bound_to``), and a deck without a binding is counted for no
        # commander, so figures of two commanders never share a denominator.
        bound_sets: dict[str, set[str]] = {}
        for row in store.connection.execute(
            "SELECT key, commander_name FROM commander_binding WHERE kind = 'corpus_deck'"
        ):
            bound_sets.setdefault(str(row[0]), set()).add(str(row[1]))
        deck_ids = [
            deck_id for deck_id in deck_ids if bound_sets.get(deck_id, set()) == wanted_commanders
        ]
    # The card-table checks run only over the decks the cheap filters left: a deck is part of
    # a universe only with a counted card row (quantity above zero), and the minimum deck size
    # counts each card once per deck and section group ("main" and "mainboard" are one section:
    # per (deck, card) the larger quantity).
    minimum = cleaned.get("min_main_cards")
    sections = ", ".join("?" for _ in COUNTED_SECTIONS)
    with _universe_table(store, deck_ids, "universe_resolve") as table:
        rows = store.connection.execute(
            f"SELECT c.deck_id, SUM(c.quantity), MAX(c.quantity > 0) FROM corpus_deck_card c "
            f"JOIN {table} u ON u.deck_id = c.deck_id WHERE c.section IN ({sections}) "
            f"GROUP BY c.deck_id",
            COUNTED_SECTIONS,
        ).fetchall()
        sizes = {str(row[0]): int(row[1]) for row in rows if row[2]}
        if minimum:
            # sum(max) = sum(main) + sum(mainboard) - sum(min) over the cards listed in both
            for deck_id, overlap in store.connection.execute(
                f"SELECT a.deck_id, SUM(MIN(a.quantity, b.quantity)) FROM corpus_deck_card a "
                f"JOIN corpus_deck_card b ON b.deck_id = a.deck_id AND b.card_name = a.card_name "
                f"JOIN {table} u ON u.deck_id = a.deck_id "
                f"WHERE a.section = 'main' AND b.section = 'mainboard' GROUP BY a.deck_id"
            ):
                sizes[str(deck_id)] -= int(overlap)
    deck_ids = [deck_id for deck_id in deck_ids if deck_id in sizes]
    if minimum:
        deck_ids = [deck_id for deck_id in deck_ids if sizes[deck_id] >= minimum]
    required_names = cleaned.get("must_contain")
    if required_names:
        # A deck contains a required card when one of its main-section rows names the
        # card under any known spelling, or when the card is the commander the deck is
        # bound to (a commander-section row alone never counts: the binding, not the
        # section, states whose deck this is). All requirements must hold.
        required = _required_cards(store, required_names)
        _by_oracle, unique = _card_name_index(store)
        bound_commanders = {
            str(row[0]): str(row[1])
            for row in store.connection.execute(
                "SELECT key, commander_name FROM commander_binding WHERE kind = 'corpus_deck'"
            )
        }
        main_marks = ", ".join("?" for _ in MAIN_SECTIONS)
        spellings: dict[str, set[str]] = {}
        for deck_id, card_name in store.connection.execute(
            f"SELECT deck_id, card_name FROM corpus_deck_card "
            f"WHERE section IN ({main_marks}) AND quantity > 0",
            MAIN_SECTIONS,
        ):
            spellings.setdefault(str(deck_id), set()).add(str(card_name).casefold())

        def _contains(deck_id: str) -> bool:
            names_in_deck = spellings.get(deck_id, set())
            commander = bound_commanders.get(deck_id)
            commander_oracle = unique.get(commander.casefold()) if commander is not None else None
            return all(
                bool(names_in_deck & spellings_of_card) or commander_oracle == oracle
                for oracle, spellings_of_card in required
            )

        deck_ids = [deck_id for deck_id in deck_ids if _contains(deck_id)]
    # Query-time dedupe inside the selected universe: one deck per content fingerprint,
    # the lowest deck id wins.
    fingerprints = dict(selected)
    first_by_fingerprint: dict[str, str] = {}
    for deck_id in sorted(deck_ids):
        fingerprint = fingerprints[deck_id]
        key = fingerprint if fingerprint else f"\x00unknown:{deck_id}"
        first_by_fingerprint.setdefault(key, deck_id)
    return sorted(first_by_fingerprint.values())


@contextmanager
def _universe_table(
    store: StudioStore, deck_ids: Sequence[str], table: str = "universe_deck"
) -> Iterator[str]:
    """Load the deck ids into a TEMP table so queries never bind one variable per deck.

    SQLite caps bound variables (999 on older builds); a universe can be larger."""
    name = f"temp.{table}"
    db = store.connection
    db.execute(f"DROP TABLE IF EXISTS {name}")
    # CREATE ... AS SELECT is one statement with one bound variable and, unlike an INSERT,
    # opens no implicit transaction: a read-only query must not leave the connection locked.
    db.execute(
        f"CREATE TEMP TABLE {table} AS SELECT DISTINCT value AS deck_id FROM json_each(?)",
        (json.dumps(deck_ids),),
    )
    # An index makes the join with the (large) card table a lookup per row, not a scan.
    db.execute(f"CREATE UNIQUE INDEX temp.{table}_id ON {table}(deck_id)")
    try:
        yield name
    finally:
        db.execute(f"DROP TABLE IF EXISTS {name}")


def _composition(store: StudioStore, deck_ids: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """Denominator split by source platform and by bracket cohort.

    Decks without a bracket cohort count as ``unknown``, decks with several different
    bracket cohorts as ``multiple``; the buckets sum to the denominator."""
    by_platform: dict[str, int] = {}
    by_bracket: dict[str, int] = {}
    if not deck_ids:
        return by_platform, by_bracket
    with _universe_table(store, deck_ids) as universe_deck:
        for platform, count in store.connection.execute(
            f"SELECT d.platform, COUNT(*) FROM corpus_deck d "
            f"JOIN {universe_deck} u ON u.deck_id = d.deck_id "
            f"GROUP BY d.platform ORDER BY d.platform"
        ):
            by_platform[str(platform)] = int(count)
        brackets_of: dict[str, set[str]] = {}
        for deck_id, cohort in store.connection.execute(
            f"SELECT c.deck_id, c.cohort FROM corpus_cohort c "
            f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
            f"WHERE c.cohort LIKE 'bracket:%'"
        ):
            brackets_of.setdefault(str(deck_id), set()).add(str(cohort))
    for deck_id in deck_ids:
        labels = brackets_of.get(deck_id, set())
        label = "unknown" if not labels else "multiple" if len(labels) > 1 else next(iter(labels))
        by_bracket[label] = by_bracket.get(label, 0) + 1
    return by_platform, dict(sorted(by_bracket.items()))


def _universe_spec(
    store: StudioStore,
    profile: str | None,
    spec: Mapping[str, object] | None,
    commander_names: Sequence[str] | None,
) -> UniverseSpec:
    """The spec of a profile or a free spec, narrowed to ``commander_names`` when given.

    A spec that already names other commanders is not silently widened or replaced."""
    if profile is not None:
        resolved = get_profile(store, profile)["spec"]
    else:
        resolved = _validate_spec(spec or {})
    if commander_names:
        wanted = sorted({str(name) for name in commander_names})
        stored = resolved.get("commanders")
        if stored and sorted(stored) != wanted:
            raise ValueError(f"the universe is defined for {sorted(stored)}, not for {wanted}")
        resolved = {**resolved, "commanders": wanted}
    return resolved


def inclusion(
    store: StudioStore,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    card_names: list[str] | None = None,
    commander_names: Sequence[str] | None,
) -> InclusionResult:
    """Per-card deck counts over one universe: hits, denominator, share.

    With ``card_names`` only those cards are returned (missing ones with 0 hits); without
    it, every card that appears in the universe is returned, ordered by hits.
    """
    resolved_spec = _universe_spec(store, profile, spec, commander_names)
    deck_ids = resolve_universe(store, resolved_spec)
    denominator = len(deck_ids)
    by_platform, by_bracket = _composition(store, deck_ids)
    counts: dict[str, int] = {}
    if deck_ids:
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        with _universe_table(store, deck_ids) as universe_deck:
            counts = {
                str(row[0]): int(row[1])
                for row in store.connection.execute(
                    f"SELECT c.card_name, COUNT(DISTINCT c.deck_id) FROM corpus_deck_card c "
                    f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
                    f"WHERE c.section IN ({sections}) AND c.quantity > 0 "
                    f"GROUP BY c.card_name",
                    COUNTED_SECTIONS,
                )
            }
    names = card_names if card_names is not None else sorted(counts, key=lambda n: (-counts[n], n))
    rows: list[InclusionRow] = [
        {
            "card_name": name,
            "hits": counts.get(name, 0),
            "denominator": denominator,
            "share": counts.get(name, 0) / denominator if denominator else None,
        }
        for name in names
    ]
    return {
        "profile": profile,
        "spec": resolved_spec,
        "denominator": denominator,
        "denominator_by_platform": by_platform,
        "denominator_by_bracket": by_bracket,
        "excluded_no_date": excluded_no_date(store, resolved_spec),
        "excluded_by_card_filter": excluded_by_card_filter(store, resolved_spec),
        "empty": not deck_ids,
        "empty_reason": empty_reason(store, resolved_spec, deck_ids),
        "rows": rows,
        "data_class": "DERIVED_DESCRIPTIVE",
    }


def spelling_owners(store: StudioStore) -> dict[str, list[str]]:
    """Cached form of ``_build_spelling_owners`` (read-only result)."""
    return cached(store, ("spelling_owners",), lambda: _build_spelling_owners(store))


def _build_spelling_owners(store: StudioStore) -> dict[str, list[str]]:
    """Casefolded deck-card spelling -> the collection cards (oracle names) it names.

    A spelling is a card's oracle name, its engine name or a front face no card owns as its
    exact name; a front face several cards share names each of them (a deck listing it counts
    for every one). This is the one name discipline of every card-level count."""
    by_oracle, _unique = _card_name_index(store)
    owners: dict[str, list[str]] = {}
    for oracle, keys in by_oracle.items():
        for key in keys:
            owners.setdefault(key, []).append(oracle)
    return owners


def deck_sets(
    store: StudioStore,
    deck_ids: Collection[str],
    group_of: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, set[str]]:
    """The decks (of ``deck_ids``) that list each card, in counted sections (quantity above
    zero): the ONE counting primitive behind inclusion, co-occurrence and lift.

    Without ``group_of`` a card is its raw ``card_name``. With ``group_of`` (casefolded spelling
    -> card names, see ``spelling_owners``) every spelling is merged into the card it names, so
    a deck listing two spellings counts once and spellings are never summed; a spelling that
    names no card keeps its raw name."""
    if not deck_ids:
        return {}
    sets: dict[str, set[str]] = {}
    marks = ", ".join("?" for _ in COUNTED_SECTIONS)
    with _universe_table(store, sorted(deck_ids)) as universe_deck:
        # The aggregation runs inside SQLite: one row per raw card name, with the decks
        # listing it (unit-separator joined; a deck listed twice collapses in the set), instead of one Python step per (deck, card) row.
        for name, joined in store.connection.execute(
            f"SELECT c.card_name, group_concat(c.deck_id, char(31)) FROM corpus_deck_card c "
            f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
            f"WHERE c.section IN ({marks}) AND c.quantity > 0 GROUP BY c.card_name",
            COUNTED_SECTIONS,
        ):
            decks = set(str(joined).split("\x1f"))
            if group_of is None:
                sets.setdefault(str(name), set()).update(decks)
                continue
            # A spelling that names no collection card stays under its own raw name.
            for group in group_of.get(str(name).casefold(), (str(name),)):
                sets.setdefault(group, set()).update(decks)
    return sets


def cooccurrence_pairs(
    sets: Mapping[str, set[str]], target: str, limit: int | None
) -> list[CooccurrenceRow]:
    """Cards listed together with ``target`` in the decks of ``sets`` (from ``deck_sets``),
    most common first, ties by name. ``limit`` caps the list (``None`` = all pairs)."""
    own = sets.get(target, set())
    pairs: list[CooccurrenceRow] = [
        {"card_name": name, "decks_together": len(decks & own)}
        for name, decks in sets.items()
        if name != target and decks & own
    ]
    pairs.sort(key=lambda item: (-item["decks_together"], item["card_name"]))
    return pairs if limit is None else pairs[:limit]


def cooccurrence(
    store: StudioStore,
    card_name: str,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    limit: int | None = 25,
    commander_names: Sequence[str] | None,
) -> CooccurrenceResult:
    """How many universe decks contain ``card_name`` together with each other card.

    Counted raw-name-wise through ``deck_sets`` (the same primitive the card-level views
    use). ``limit`` caps the pair list (``None`` = all pairs); it must be at least 1."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1 (or None for no limit)")
    deck_ids = resolve_universe(store, _universe_spec(store, profile, spec, commander_names))
    by_platform, by_bracket = _composition(store, deck_ids)
    sets = deck_sets(store, deck_ids)
    pairs = cooccurrence_pairs(sets, card_name, limit)
    return {
        "card_name": card_name,
        "profile": profile,
        "denominator": len(deck_ids),
        "denominator_by_platform": by_platform,
        "denominator_by_bracket": by_bracket,
        "decks_with_card": len(sets.get(card_name, set())),
        "pairs": pairs,
        "data_class": "DERIVED_DESCRIPTIVE",
    }


class UniverseDecks(TypedDict):
    """One resolved universe with the deck ids behind every raw card name."""

    spec: UniverseSpec
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    snapshot_id: str
    data_class: str
    empty: bool
    empty_reason: str | None
    deck_ids: list[str]
    decks_by_name: dict[str, set[str]]


NO_COMMANDER_DECKS = "NO_SOURCE_DECKS_FOR_COMMANDER"
FILTERS_EXCLUDE_ALL = "FILTERS_EXCLUDE_ALL_DECKS"
EMPTY_REASONS: dict[str, str] = {
    NO_COMMANDER_DECKS: "Für diesen Commander sind keine Quelldecks importiert.",
    FILTERS_EXCLUDE_ALL: "Die Filter des Universums lassen kein Deck übrig.",
}


def empty_reason(store: StudioStore, spec: UniverseSpec, deck_ids: Sequence[str]) -> str | None:
    """Why a universe is empty (``None`` when it holds a deck): an empty universe is an
    explicit state, never a silent zero. Tells "no decks of the commander at all" from
    "the filters (e.g. two cohorts of different families) exclude every deck"."""
    if deck_ids:
        return None
    scope: UniverseSpec = {}
    if spec.get("commanders"):
        scope["commanders"] = spec["commanders"]
    if scope and not resolve_universe(store, scope):
        return NO_COMMANDER_DECKS
    if not scope and not resolve_universe(store, {}):
        return NO_COMMANDER_DECKS
    return FILTERS_EXCLUDE_ALL


def universe_decks(
    store: StudioStore,
    *,
    profile: str | None,
    commander_names: Sequence[str] | None,
    spec: Mapping[str, object] | None = None,
) -> UniverseDecks:
    """Resolve a profile (or a free ``spec``) once: its figures and, per raw card name, the
    universe decks that list it in a counted section with a quantity above zero. Memoized per
    data epoch (the result is read-only)."""
    resolved = _universe_spec(store, profile, spec, commander_names)
    return memo.cached(
        store,
        "universe_decks",
        json.dumps(resolved, sort_keys=True, default=str),
        lambda: _universe_decks_of(store, resolved),
    )


def _universe_decks_of(store: StudioStore, spec: UniverseSpec) -> UniverseDecks:
    deck_ids = resolve_universe(store, spec)
    by_platform, by_bracket = _composition(store, deck_ids)
    reason = empty_reason(store, spec, deck_ids)
    return {
        "spec": spec,
        "denominator": len(deck_ids),
        "denominator_by_platform": by_platform,
        "denominator_by_bracket": by_bracket,
        "snapshot_id": _snapshot_of(store, spec, deck_ids),
        "data_class": "DERIVED_DESCRIPTIVE",
        "empty": reason is not None,
        "empty_reason": reason,
        "deck_ids": deck_ids,
        "decks_by_name": deck_sets(store, deck_ids),
    }


def snapshot_id(
    store: StudioStore,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    commander_names: Sequence[str] | None,
) -> str:
    """A short fingerprint of a universe: its spec plus what it currently selects.

    The digest covers the spec, the selected deck ids and each deck's stored card
    fingerprint, so a snapshot id changes when the selection changes *or* when a
    selected deck's cards are replaced by a later import. Two equal snapshot ids mean
    the same spec over the same deck contents; figures can cite the exact universe
    they were counted over.
    """
    cleaned = _universe_spec(store, profile, spec, commander_names)
    return _snapshot_of(store, cleaned, resolve_universe(store, cleaned))


def _snapshot_of(store: StudioStore, cleaned: UniverseSpec, deck_ids: list[str]) -> str:
    import hashlib

    fingerprints = {
        str(row[0]): str(row[1])
        for row in store.connection.execute("SELECT deck_id, fingerprint FROM corpus_deck")
    }
    digest = hashlib.sha256()
    digest.update(json.dumps(cleaned, sort_keys=True).encode())
    for deck_id in deck_ids:
        digest.update(f"\n{deck_id}:{fingerprints.get(deck_id, '')}".encode())
    return f"universe:{digest.hexdigest()[:16]}:{len(deck_ids)}"


__all__ = [
    "COUNTED_SECTIONS",
    "EMPTY_REASONS",
    "CooccurrenceResult",
    "InclusionResult",
    "OptionValue",
    "Profile",
    "SavedProfile",
    "UniverseDecks",
    "UniverseOptions",
    "UniverseSpec",
    "bound_commander_sets",
    "cohort_families",
    "cohort_family",
    "cooccurrence",
    "cooccurrence_pairs",
    "deck_sets",
    "empty_reason",
    "excluded_no_date",
    "get_profile",
    "inclusion",
    "list_profiles",
    "options",
    "resolve_universe",
    "save_profile",
    "snapshot_id",
    "spelling_owners",
    "universe_decks",
]
