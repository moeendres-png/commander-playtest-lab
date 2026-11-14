"""The strength index as the tier list page shows it: store access around ``strength.py``.

Reads the stored signals of ONE commander (``card_signal``), the counted deck-list share of
the chosen universe profile (``universe_view``) and hands them to the pure scoring
function. Figures of two commanders are never combined: every query names its commander,
and commander-independent signals are stored under the empty commander name. The
Playgroup atlas signal is one of them: an observed win-rate correlation from multiplayer
games, published per card, not per commander.

The Owner's marks are not read here. The simulation component is ``NOT_COLLECTED``: the
stored simulation rows are per deck and per card cast statistics, not an outcome model.

Matching a stored card name to a pool card is deterministic and follows the counted
spread's name discipline (``universe_view.name_claims``): a name belongs to the card whose
**exact oracle name** it is; failing that, to the card whose **engine name** it is; failing
that, to the card whose **front face** it is (a front face is a spelling only when no other
Studio card has it as an exact name). Comparison is case-insensitive. A name that several
cards claim at the best level is ambiguous: it is given to none and listed in the result
(``ambiguous_names``), never dropped silently. When several stored rows resolve to one
card, the row with the better claim wins, then the smaller stored name.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TypedDict

from . import layers, layers_view, signals, strength, universe, universe_choice, universe_view
from .builder import pool_cards
from .store import StudioStore, now_utc
from .strength import (
    BRACKET_INCLUSION,
    COMBOS,
    COMMANDER_INCLUSION,
    DECK_UNIVERSE,
    GLOBAL_INCLUSION,
    PLAYGROUP_OBSERVED,
    SYNERGY,
    TOURNAMENT_LISTS,
    CardStrength,
    Observation,
    PoolContext,
    StrengthSettings,
)
from .tiers import TierParams
from .universe_choice import UniverseChoice
from .universe_view import ProfileSummary, name_claims, pool_spread, profile_summary

MAX_NAME = 80


class StrengthCard(TypedDict):
    card_id: str
    name: str
    index: float | None
    coverage: float | None
    tier: str
    reason: str
    note: str
    present: int
    components: list[strength.ComponentResult]
    layers: dict[str, layers.LayerValue]


class LayerSummaryBlock(TypedDict):
    schema: str
    pod_size: int
    pod_note: str
    measured_note: str
    weighted: list[str]
    layers: list[layers.LayerSummary]


class AmbiguousName(TypedDict):
    signal: str
    name: str
    candidates: list[str]


class StrengthResult(TypedDict):
    schema: str
    data_class: str
    meaning: str
    commander: str
    settings: dict[str, object]
    universe: ProfileSummary | None
    universe_choice: UniverseChoice
    universe_missing: str | None
    notices: list[str]
    collected: list[str]
    tier_counts: dict[str, int]
    ambiguous_names: list[AmbiguousName]
    layer_summary: LayerSummaryBlock
    cards: list[StrengthCard]


_INDEPENDENT = frozenset(
    {
        "edhrec_global_inclusion",
        "spellbook_variants",
        signals.SIGNAL_TWO_CARD,
        signals.SIGNAL_PARTNERS,
        "playgroup_observed_winrate_gap",
        # A marker layer only (no rated component): the salt list does not depend on a commander.
        signals.SIGNAL_SALT,
    }
)
# claim key -> [(claim kind, card id)]
_Claims = dict[str, list[tuple[int, str]]]


def _claim_index(store: StudioStore, ids: list[str]) -> _Claims:
    index: _Claims = {}
    for card_id, claims in name_claims(store, ids).items():
        for key, kind in claims:
            index.setdefault(key, []).append((kind, card_id))
    return index


def _signal_observations(
    store: StudioStore,
    commander: str,
    signal: str,
    claims: _Claims,
    display: Mapping[str, str],
    ambiguous: dict[tuple[str, str], list[str]],
) -> tuple[dict[str, Observation], bool]:
    """Observations of the pool cards for one stored signal, and whether the source has
    any row for it. Commander-independent signals sit under the empty commander name."""
    owner = "" if signal in _INDEPENDENT else commander
    best: dict[str, tuple[int, str, Observation]] = {}
    rows = store.connection.execute(
        "SELECT card_name, value, numerator, denominator FROM card_signal "
        "WHERE commander_name = ? AND signal = ? ORDER BY card_name",
        (owner, signal),
    ).fetchall()
    for row in rows:
        name = str(row["card_name"])
        found = claims.get(name.casefold())
        if not found:
            continue
        kind = min(item[0] for item in found)
        owners = sorted({card for item_kind, card in found if item_kind == kind})
        if len(owners) > 1:
            ambiguous[(signal, name)] = sorted(display[card] for card in owners)
            continue
        card_id = owners[0]
        rank = (kind, name)
        current = best.get(card_id)
        if current is None or rank < (current[0], current[1]):
            best[card_id] = (
                kind,
                name,
                Observation(row["value"], row["numerator"], row["denominator"]),
            )
    return {card_id: item[2] for card_id, item in best.items()}, bool(rows)


def _combo_observations(
    store: StudioStore,
    commander: str,
    claims: _Claims,
    display: Mapping[str, str],
    ambiguous: dict[tuple[str, str], list[str]],
) -> tuple[dict[str, Observation], bool]:
    """The combos observations: one per pool card the spellbook file lists, valued by
    the combo quality mixture (``strength.combo_quality``) of the three spellbook
    signals. Whether the source exists is decided by the primary signal alone, as
    before; the two quality signals only refine the value of the listed cards."""
    parts: dict[str, dict[str, float]] = {}
    exists = False
    for signal in strength.COMBO_PARTS:
        observed, found = _signal_observations(store, commander, signal, claims, display, ambiguous)
        if signal == strength.COMBO_PART_VARIANTS:
            exists = found
        parts[signal] = {
            card_id: item.value for card_id, item in observed.items() if item.value is not None
        }
    return (
        {card_id: Observation(value) for card_id, value in strength.combo_quality(parts).items()},
        exists,
    )


def _strings(value: object) -> set[str]:
    if not isinstance(value, list):
        raise TypeError("pool_cards returned an unexpected shape")
    return {str(item) for item in value}


class SignalCoverage(TypedDict):
    scope: str
    rows: int
    rows_with_value: int
    pool_cards_with_value: int
    pool_size: int


def expected_signals() -> list[str]:
    """The usage signals the importers can store, a fixed list from the code (not from what
    happens to be stored): a signal without rows is then shown as missing, never left out."""
    return [
        strength.signal_for(COMMANDER_INCLUSION, strength.BRACKET_NONE),
        *(f"{signals.SIGNAL_BRACKET}:{variant}" for variant in signals.BRACKET_VARIANTS),
        strength.signal_for(SYNERGY, strength.BRACKET_NONE),
        strength.signal_for(GLOBAL_INCLUSION, strength.BRACKET_NONE),
        strength.signal_for(COMBOS, strength.BRACKET_NONE),
        signals.SIGNAL_TWO_CARD,
        signals.SIGNAL_PARTNERS,
        strength.signal_for(TOURNAMENT_LISTS, strength.BRACKET_NONE),
        signals.SIGNAL_EDHTOP16,
        # One generic row: the counted universes are named by the file (source, bracket); the
        # stored ones are listed under their own names, this row stays while none exists.
        signals.SIGNAL_DECKLIST,
        signals.SIGNAL_PLAYGROUP,
        signals.SIGNAL_SALT,
        signals.SIGNAL_COMBO_DECKS,
    ]


def signal_coverage(store: StudioStore, commander: str) -> dict[str, SignalCoverage]:
    """Per stored signal: its rows and how many of the commander's pool cards it gives a
    value (the same name matching as the index). Counts only. A signal without rows for
    this commander is listed with 0 rows: missing, not a weak signal. Raises KeyError when
    the commander is not in the collection."""
    pool = pool_cards(store, [commander], with_signals=False)
    raw_cards = pool["cards"]
    if not isinstance(raw_cards, list):
        raise TypeError("pool_cards returned an unexpected shape")
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["name"]) for card in raw_cards}
    claims = _claim_index(store, ids)
    db = store.connection
    result: dict[str, SignalCoverage] = {}
    stored = [str(row[0]) for row in db.execute("SELECT DISTINCT signal FROM card_signal")]
    counted_signals = {
        item["signal"]: item for item in universe_choice.counted_universes(store, commander)
    }
    names = expected_signals()
    if counted_signals:
        names.remove(signals.SIGNAL_DECKLIST)
    for signal in sorted(set(stored) - set(names)):
        if signal.startswith(f"{signals.SIGNAL_DECKLIST}:") and signal not in counted_signals:
            continue  # a counted universe of another commander
        names.append(signal)
    for signal in names:
        owner = "" if signal in _INDEPENDENT else commander
        counted = db.execute(
            "SELECT COUNT(*), COUNT(value) FROM card_signal "
            "WHERE commander_name = ? AND signal = ?",
            (owner, signal),
        ).fetchone()
        if signal in counted_signals:
            # A complete count: a pool card without a row is a counted zero, so every pool card
            # (but the ones whose name is ambiguous) has a value.
            full = counted_observations(
                store, commander, counted_signals[signal], claims, display, {}
            )
            valued = len(full)
        else:
            observed, _exists = _signal_observations(store, commander, signal, claims, display, {})
            valued = sum(1 for item in observed.values() if item.value is not None)
        result[signal] = {
            "scope": "independent" if signal in _INDEPENDENT else "commander",
            "rows": int(counted[0]),
            "rows_with_value": int(counted[1]),
            "pool_cards_with_value": valued,
            "pool_size": len(ids),
        }
    return result


def counted_observations(
    store: StudioStore,
    commander: str,
    universe: universe_choice.CountedUniverse,
    claims: _Claims,
    display: Mapping[str, str],
    ambiguous: dict[tuple[str, str], list[str]],
) -> dict[str, Observation]:
    """One observation per pool card from a counted deck-list universe of ``commander``.

    The universe holds complete deck lists that were counted, so a pool card without a row is
    in none of its decks: a counted zero (0 of N), not an unknown. Names are matched like every
    signal (exact oracle name, engine name, then the FRONT face only; the back half of a
    two-part name is never a spelling of the card). A card that an ambiguous name could belong
    to, or whose front face is withheld because another card has that name, stays unknown: the
    row may be its own."""
    taken: dict[tuple[str, str], list[str]] = {}
    observed, _exists = _signal_observations(
        store, commander, universe["signal"], claims, display, taken
    )
    ambiguous.update(taken)
    by_name = {name: card_id for card_id, name in display.items()}
    unsure = {by_name[name] for names in taken.values() for name in names if name in by_name}
    unsure |= universe_view.front_face_withheld(store, list(display))  # same as the local path
    total = universe["denominator"]
    result: dict[str, Observation] = {}
    for card_id in display:
        item = observed.get(card_id)
        if item is not None and item.numerator is not None:
            result[card_id] = Observation(item.value, item.numerator, item.denominator)
        elif card_id not in unsure:
            result[card_id] = Observation(0.0, 0, total)
    return result


def _unmatched_universe_notices(
    store: StudioStore, commander: str, choice: UniverseChoice
) -> list[str]:
    """A notice when the counted universe the calculation used holds rows that match no card
    of the store: those cards cannot take part in the index."""
    if choice["kind"] != universe_choice.KIND_COUNTED:
        return []
    for item in universe_choice.counted_universes(store, commander):
        if item["value"] != choice["counted"]:
            continue
        missing = signals.unmatched_universe_names(store, commander, item["signal"])
        if not missing:
            return []
        examples = missing[: signals.UNMATCHED_EXAMPLES]
        return [
            f"Im Decklisten-Universum „{item['short_label']}“ passen {len(missing)} Zeilen zu keiner "
            f"Karte im Store (z. B. {'; '.join(examples)}): diese Karten fehlen in der "
            "Rechnung, das Universum ist unvollständig abgeglichen."
        ]
    return []


def builder_counted_universe(
    store: StudioStore,
    commander: str,
    card_ids: list[str],
    display: Mapping[str, str],
    settings: StrengthSettings | None = None,
) -> tuple[UniverseChoice, dict[str, Observation]] | None:
    """For the builder: the counted universe the tier list takes for the same ``settings``
    (the same ``universe_choice.choose`` as the index; default settings when none are given)
    and the counts of the given cards in it. ``None`` when the choice is not a counted
    universe (a saved universe profile in the settings is none either)."""
    settings = settings or StrengthSettings()
    kind = (strength.parse_universe_source(settings.universe_source) or ("",) * 3)[0]
    if settings.universe_profile and kind in (strength.UNIVERSE_AUTO, strength.UNIVERSE_PROFILE):
        return None  # the tier list takes the stored profile, not a counted universe
    choice = universe_choice.choose(store, commander, settings, None)
    if choice["kind"] != universe_choice.KIND_COUNTED:
        return None
    for item in universe_choice.counted_universes(store, commander):
        if item["value"] == choice["counted"]:
            claims = _claim_index(store, card_ids)
            return choice, counted_observations(store, commander, item, claims, display, {})
    return None


class SignalValue(TypedDict):
    value: float | None
    numerator: int | None
    denominator: int | None


def card_signal_values(
    store: StudioStore, commander: str, card_ids: list[str], display: Mapping[str, str]
) -> dict[str, dict[str, SignalValue]]:
    """Stored usage signals of ONE commander per pool card, for the builder columns.

    Keys per card: ``inclusion`` (decks with the card over the commander's decks),
    ``synergy`` and ``global_inclusion`` (independent of the commander). A card without a
    row for a signal has no entry for it: unknown, never 0. Same name matching as the index."""
    claims = _claim_index(store, card_ids)
    wanted = {
        "inclusion": strength.signal_for(COMMANDER_INCLUSION, strength.BRACKET_NONE),
        "synergy": strength.signal_for(SYNERGY, strength.BRACKET_NONE),
        "global_inclusion": strength.signal_for(GLOBAL_INCLUSION, strength.BRACKET_NONE),
    }
    result: dict[str, dict[str, SignalValue]] = {}
    for key, signal in wanted.items():
        if not signal:
            continue
        observed, _exists = _signal_observations(store, commander, signal, claims, display, {})
        for card_id, item in observed.items():
            if item.value is None:
                continue
            result.setdefault(card_id, {})[key] = {
                "value": float(item.value),
                "numerator": item.numerator,
                "denominator": item.denominator,
            }
    return result


def _layer_result(
    store: StudioStore,
    raw_cards: Sequence[Mapping[str, object]],
    display: Mapping[str, str],
    claims: _Claims,
    unranked: Mapping[str, str],
    per_card: Mapping[str, Mapping[str, Observation]],
    pod_size: int,
) -> layers.LayerResult:
    """The rating layers of the pool cards. ``per_card`` carries the Playgroup gap
    observations the index reads (the layer "Sieg-Abstand" reuses them)."""
    return layers.compute_layers(
        layers_view.layer_cards(
            store,
            display,
            {str(card["card_id"]): str(card["type_line"]) for card in raw_cards},
            unranked,
        ),
        layers_view.atlas_records(
            store,
            {str(card["card_id"]): _optional_text(card["oracle_id"]) for card in raw_cards},
            claims,
        ),
        {
            card_id: observation
            for card_id, per in per_card.items()
            if (observation := per.get(PLAYGROUP_OBSERVED)) is not None
        },
        pod_size,
    )


def rating_layers(store: StudioStore, commander: str, pod_size: int) -> layers.LayerResult:
    """The rating layers of ``commander``'s legal pool without the strength index (the card
    window of the builder). Raises KeyError when the commander is not in the collection."""
    pool = pool_cards(store, [commander], with_signals=False)
    raw_cards = pool["cards"]
    if not isinstance(raw_cards, list):
        raise TypeError("pool_cards returned an unexpected shape")
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["name"]) for card in raw_cards}
    commander_ids = _strings(pool["commander_ids"])
    claims = _claim_index(store, ids)
    gap: dict[str, dict[str, Observation]] = {card_id: {} for card_id in ids}
    observed, _exists = _signal_observations(
        store,
        commander,
        strength.signal_for(PLAYGROUP_OBSERVED, strength.BRACKET_NONE),
        claims,
        display,
        {},
    )
    for card_id, observation in observed.items():
        gap[card_id][PLAYGROUP_OBSERVED] = observation
    return _layer_result(
        store, raw_cards, display, claims, _unranked_cards(raw_cards, commander_ids), gap, pod_size
    )


def _unranked_cards(
    raw_cards: Sequence[Mapping[str, object]], commander_ids: set[str]
) -> dict[str, str]:
    """The cards that get no tier and no layer value: the commander and basic lands."""
    unranked: dict[str, str] = {}
    for card in raw_cards:
        card_id = str(card["card_id"])
        if card_id in commander_ids:
            unranked[card_id] = strength.NOT_RANKED_COMMANDER
        elif card["basic"]:
            unranked[card_id] = strength.NOT_RANKED_BASIC_LAND
    return unranked


def _optional_text(value: object) -> str | None:
    return str(value) if value else None


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _fill_spread(
    per_card: dict[str, dict[str, Observation]],
    filter_cards: set[str],
    cards: Sequence[universe_view.CardSpread],
) -> None:
    """Deck-universe observations from the counted spread of local decks. Every deck list is
    complete, so a card that no deck names is a counted zero (0 of N) like in a counted
    universe, except when its name is ambiguous (a withheld front face): that stays unknown."""
    for item in cards:
        card_id = item["card_id"]
        if item["filter_card"]:
            filter_cards.add(card_id)
        elif item["hits"] is not None:
            per_card[card_id][DECK_UNIVERSE] = Observation(
                item["hits"] / item["denominator"], item["hits"], item["denominator"]
            )
        elif item["denominator"] > 0 and not item.get("ambiguous_front_face"):
            per_card[card_id][DECK_UNIVERSE] = Observation(0.0, 0, item["denominator"])


def compute(
    store: StudioStore,
    commander: str,
    settings: StrengthSettings,
    *,
    dangling_universe_ok: bool = False,
    notices: Sequence[str] = (),
) -> StrengthResult:
    """Index and tier for every legal pool card of ``commander``.

    Raises KeyError when the commander is not in the collection or the universe profile of
    the settings is unknown. With ``dangling_universe_ok`` (settings read from a saved
    profile) a universe profile that was deleted meanwhile is not an error: the index runs
    with "kein Universum" and the result carries a notice and ``universe_missing``."""
    pool = pool_cards(store, [commander], with_signals=False)
    raw_cards = pool["cards"]
    if not isinstance(raw_cards, list):
        raise TypeError("pool_cards returned an unexpected shape")
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["name"]) for card in raw_cards}
    commander_ids = _strings(pool["commander_ids"])
    claims = _claim_index(store, ids)
    ambiguous: dict[tuple[str, str], list[str]] = {}

    notices = list(notices)
    universe_missing: str | None = None
    summary: ProfileSummary | None = None
    kind, _source, _bracket = strength.parse_universe_source(settings.universe_source) or ("",) * 3
    if settings.universe_profile and kind in (strength.UNIVERSE_AUTO, strength.UNIVERSE_PROFILE):
        try:
            summary = profile_summary(store, settings.universe_profile, commander_names=[commander])
        except KeyError:
            if not dangling_universe_ok:
                raise
            universe_missing = settings.universe_profile
            settings = replace(settings, universe_profile=None)
            notices.append(
                f"Das Universum „{universe_missing}“ dieser Einstellung gibt es nicht mehr: "
                "die Rechnung läuft ohne dieses Universum (kein Universum, oder bei "
                "„automatisch“ die automatische Wahl)."
            )
    choice = universe_choice.choose(store, commander, settings, summary)
    if choice["kind"] == universe_choice.KIND_NONE and kind == strength.UNIVERSE_COUNTED:
        notices.append(f"Kein Decklisten-Universum: {choice['reason']}.")
    notices.extend(_unmatched_universe_notices(store, commander, choice))

    per_card: dict[str, dict[str, Observation]] = {card_id: {} for card_id in ids}
    collected: set[str] = set()
    for component in (
        COMMANDER_INCLUSION,
        BRACKET_INCLUSION,
        SYNERGY,
        TOURNAMENT_LISTS,
        GLOBAL_INCLUSION,
        COMBOS,
        PLAYGROUP_OBSERVED,
    ):
        signal = strength.signal_for(component, settings.bracket)
        if not signal:
            continue
        if component == COMBOS:
            observed, exists = _combo_observations(store, commander, claims, display, ambiguous)
        else:
            observed, exists = _signal_observations(
                store, commander, signal, claims, display, ambiguous
            )
        if exists:
            collected.add(component)
        for card_id, observation in observed.items():
            per_card[card_id][component] = observation

    filter_cards: set[str] = set()
    universe_minimum = TierParams().min_universe
    if choice["kind"] == universe_choice.KIND_PROFILE and summary is not None:
        universe_minimum = summary["min_universe"]
        if summary["denominator"] > 0:
            collected.add(DECK_UNIVERSE)
            spread = pool_spread(store, summary["profile"], ids, commander_names=[commander])
            _fill_spread(per_card, filter_cards, spread["cards"])
    elif choice["kind"] == universe_choice.KIND_LOCAL:
        local_total, _snapshot, local_cards = universe_view.spread_for_spec(
            store, universe_choice.local_spec(store, commander), ids, commander_names=[commander]
        )
        if local_total > 0:
            collected.add(DECK_UNIVERSE)
            _fill_spread(per_card, filter_cards, local_cards)
    elif choice["kind"] == universe_choice.KIND_COUNTED:
        for item in universe_choice.counted_universes(store, commander):
            if item["value"] == choice["counted"]:
                collected.add(DECK_UNIVERSE)
                for card_id, observation in counted_observations(
                    store, commander, item, claims, display, ambiguous
                ).items():
                    per_card[card_id][DECK_UNIVERSE] = observation

    type_group: dict[str, str] = {}
    bands: dict[str, str] = {}
    unranked = _unranked_cards(raw_cards, commander_ids)
    for card in raw_cards:
        card_id = str(card["card_id"])
        group = str(card["group"])
        type_group[card_id] = group
        bands[card_id] = strength.mana_band(_float(card["mana_value"]), is_land=group == "Land")
    context = PoolContext(type_group, bands, unranked, filter_cards, universe_minimum)

    # Rating layers (Bewertungsebenen): always computed for the page; they join the index only
    # with a positive weight (default 0), as one more rank-based component each.
    layer_result = _layer_result(
        store, raw_cards, display, claims, unranked, per_card, settings.pod_size
    )
    weighted = [key for key in strength.LAYER_KEYS if settings.layer_weights[key] > 0]
    for card_id, found in layers.index_observations(layer_result, weighted).items():
        per_card[card_id].update(found)
    for key in weighted:
        if any(item[key]["status"] == layers.OK for item in layer_result["cards"].values()):
            collected.add(strength.layer_component(key))
        else:
            notices.append(f"{strength.LAYER_LABELS[key]}: keine Daten, Gewicht ohne Wirkung")

    scored = strength.score_pool(settings, per_card, collected, context=context)
    notices.extend(strength.weights_without_effect(settings, collected))
    cards: list[StrengthCard] = []
    for card_id in ids:
        result: CardStrength = scored[card_id]
        cards.append(
            {
                "card_id": card_id,
                "name": display[card_id],
                **result,
                "layers": layer_result["cards"][card_id],
            }
        )
    tiers = Counter(card["tier"] for card in cards)
    return {
        "schema": strength.SCHEMA,
        "data_class": strength.DATA_CLASS,
        "meaning": strength.MEANING,
        "commander": commander,
        "settings": settings.to_dict(),
        "universe": summary if choice["kind"] == universe_choice.KIND_PROFILE else None,
        "universe_choice": choice,
        "universe_missing": universe_missing,
        "notices": notices,
        # the index sources; a weighted layer is listed in ``layer_summary.weighted`` instead
        "collected": sorted(
            name for name in collected if not name.startswith(strength.LAYER_PREFIX)
        ),
        "tier_counts": {tier: tiers.get(tier, 0) for tier in (*strength.TIERS, "U", "N")},
        "ambiguous_names": [
            {"signal": signal, "name": name, "candidates": candidates}
            for (signal, name), candidates in sorted(ambiguous.items())
        ],
        "layer_summary": {
            "schema": layer_result["schema"],
            "pod_size": layer_result["pod_size"],
            "pod_note": layer_result["pod_note"],
            "measured_note": layer_result["measured_note"],
            "weighted": weighted,
            "layers": layer_result["layers"],
        },
        "cards": cards,
    }


# ---------- saved settings of the Owner ----------


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > MAX_NAME:
        raise ValueError(f"a profile name needs 1 to {MAX_NAME} characters")
    return cleaned


def save_profile(store: StudioStore, name: str, settings: StrengthSettings) -> ProfileEntry:
    cleaned = _clean_name(name)
    with store.connection as db:
        db.execute(
            "INSERT OR REPLACE INTO strength_profile(name, spec, created_at) VALUES (?, ?, ?)",
            (cleaned, json.dumps(settings.to_dict(), sort_keys=True), now_utc()),
        )
    return get_profile(store, cleaned)


class ProfileEntry(TypedDict):
    name: str
    settings: dict[str, object] | None
    created_at: str
    valid: bool
    reason: str | None
    universe_missing: str | None
    ignored_keys: list[str]


def _entry(store: StudioStore, row: Mapping[str, object]) -> ProfileEntry:
    """A stored profile as the page lists it. A spec that no longer validates (settings
    that were valid when saved and are not any more) is listed with ``valid`` false and the
    reason, never an error that hides the other profiles. ``universe_missing`` names the
    universe profile a valid entry still points to although it was deleted."""
    name, created = str(row["name"]), str(row["created_at"])
    try:
        settings, ignored = StrengthSettings.from_stored(_as_mapping(json.loads(str(row["spec"]))))
    except (ValueError, TypeError) as error:  # json.JSONDecodeError is a ValueError
        return {
            "name": name,
            "settings": None,
            "created_at": created,
            "valid": False,
            "reason": str(error),
            "universe_missing": None,
            "ignored_keys": [],
        }
    missing: str | None = None
    if settings.universe_profile:
        try:
            universe.get_profile(store, settings.universe_profile)
        except KeyError:
            missing = settings.universe_profile
    return {
        "name": name,
        "settings": settings.to_dict(),
        "created_at": created,
        "valid": True,
        "reason": None,
        "universe_missing": missing,
        "ignored_keys": ignored,
    }


def profile_notices(store: StudioStore, name: str) -> list[str]:
    """Notices for computing with a stored profile: keys of the profile this version does not
    know are ignored, not an error."""
    ignored = get_profile(store, name)["ignored_keys"]
    if not ignored:
        return []
    return [
        f"Die Einstellung „{name}“ enthält unbekannte Schlüssel, sie werden ignoriert: "
        + ", ".join(ignored)
    ]


def get_profile(store: StudioStore, name: str) -> ProfileEntry:
    row = store.connection.execute(
        "SELECT name, spec, created_at FROM strength_profile WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise KeyError(name)
    return _entry(store, row)


def list_profiles(store: StudioStore) -> list[ProfileEntry]:
    rows = store.connection.execute(
        "SELECT name, spec, created_at FROM strength_profile ORDER BY name"
    ).fetchall()
    return [_entry(store, row) for row in rows]


def delete_profile(store: StudioStore, name: str) -> None:
    with store.connection as db:
        if db.execute("DELETE FROM strength_profile WHERE name = ?", (name,)).rowcount == 0:
            raise KeyError(name)


def _number_text(value: float) -> str:
    """A number the way the Owner reads it: 3 not 3.0, 0,4 with a decimal comma."""
    return (f"{value:g}").replace(".", ",")


_GROUP_CHOICES = {
    strength.GROUP_POOL: "ganzer Pool",
    strength.GROUP_TYPE: "gleicher Kartentyp",
    strength.GROUP_MANA_BAND: "gleiches Manawert-Band",
}
_MEASURE_CHOICES = {
    strength.MEASURE_WILSON: "Wilson-Untergrenze",
    strength.MEASURE_RAW: "roher Anteil",
}
_MISSING_CHOICES = {
    strength.MISSING_SKIP: "auslassen",
    strength.MISSING_LOWEST: "als niedrigster Rang zählen",
}
_BRACKET_CHOICES = {
    "core": "Core (Bracket 1-2)",
    "upgraded": "Upgraded (Bracket 3)",
    "optimized": "Optimized (Bracket 4)",
    "cedh": "cEDH (Bracket 5)",
    "none": "kein Bracket",
}


def _choices(names: Mapping[str, str], recommended: str) -> list[dict[str, object]]:
    return [
        {
            "value": value,
            "label": f"{label} (empfohlen)" if value == recommended else label,
            "recommended": value == recommended,
        }
        for value, label in names.items()
    ]


def _panel_texts() -> dict[str, object]:
    """Labels, help texts and choices of the settings panel, every label with the
    recommendation in parentheses. The recommended values are those of the defaults of
    ``StrengthSettings``: the page draws these texts and hard-codes no value."""
    rec = StrengthSettings()
    universe_minimum = TierParams().min_universe
    cuts = rec.tier_cuts
    labels: dict[str, str] = {}
    helps: dict[str, str] = {}
    for key, weight in rec.weights.items():
        labels[f"weights.{key}"] = f"{strength.LABELS[key]} (empfohlen: {_number_text(weight)})"
        helps[f"weights.{key}"] = (
            "Gewicht des Signals im Mittel der Ränge. 0 schaltet das Signal ab; "
            "ein leeres Feld nimmt den empfohlenen Wert."
        )
    labels[f"weights.{strength.SIMULATION}"] = (
        f"{strength.LABELS[strength.SIMULATION]} (empfohlen: "
        f"{_number_text(rec.weights[strength.SIMULATION])}, derzeit ohne Daten)"
    )
    helps[f"weights.{strength.SIMULATION}"] = (
        "Simulationsergebnisse zählen nicht in die Tierliste und werden dafür vorerst weder "
        "eingeholt noch verarbeitet. Das Gewicht bleibt als Option bestehen und steht auf 0."
    )
    helps[f"weights.{strength.PLAYGROUP_OBSERVED}"] = (
        "Beobachteter Unterschied der Siegrate, wenn die Karte gewirkt wurde (Playgroup-Live-"
        f"Partien, alle Commander). Zählt erst ab {strength.OBSERVED_MIN_SAMPLE} Partien mit "
        "der Karte und wird bei kleinen Stichproben zur Null hin gedämpft. Gilt für jeden "
        "Commander und reicht für eine Stufe allein nicht. 0 schaltet das Signal ab."
    )
    helps[f"weights.{strength.DECK_UNIVERSE}"] = (
        "Wie stark die Verbreitung in gezählten Decklisten zählt. 0 schaltet sie ab."
    )
    helps[f"weights.{strength.COMBOS}"] = (
        "Combo-Qualität statt reiner Anzahl (Commander Spellbook): der Rang mischt zu "
        "gleichen Teilen, in wie vielen Combo-Varianten eine Karte steht, in wie vielen "
        "ihrer Varianten mit genau zwei Karten und wie viele ihrer Combo-Partner in der "
        "Sammlung sind. Eine 2-Karten-Kombo mit vorhandenem Partner zählt so mehr als "
        "viele Varianten ohne Partner. Was eine Kombo erzeugt und welche Partner eine "
        "einzelne Variante hat, veröffentlicht die Datei nicht: das bleibt unbekannt "
        "und zählt nicht mit. 0 schaltet das Signal ab."
    )
    for key in strength.LAYER_KEYS:
        labels[f"layer_weights.{key}"] = (
            f"{strength.LAYER_LABELS[key]} (empfohlen: {_number_text(rec.layer_weights[key])})"
        )
        helps[f"layer_weights.{key}"] = (
            f"{layers.DESCRIPTIONS[key]} Gewicht im Mittel der Ränge; 0 (empfohlen) lässt die "
            "Ebene aus dem Index heraus, sie bleibt eine Spalte. Ein leeres Feld nimmt den "
            "empfohlenen Wert."
        )
    helps[f"layer_weights.{strength.LAYER_KEYS[0]}"] += (
        " Aus dem Regeltext abgeleitet, keine Messung."
    )
    labels["pod_size"] = f"Pod-Größe (empfohlen: {rec.pod_size})"
    helps["pod_size"] = (
        f"Anzahl der Spieler von {strength.POD_SIZE_MIN} bis {strength.POD_SIZE_MAX}. Ändert nur "
        "die angezeigte Zahl („wirkt auf N-1 Gegner“) bei „Großpod-Wirkung“, keinen Rang und "
        "keinen Index."
    )
    labels["bracket"] = (
        "Bracket-Signal (empfohlen: upgraded, passend zum Bracket 3; bei Turnierausrichtung cedh)"
    )
    helps["bracket"] = "Welche Bracket-Seite von EDHREC als Bracket-Signal zählt."
    labels["rank_group"] = (
        f"Vergleichsgruppe für den Rang (empfohlen: {_GROUP_CHOICES[rec.rank_group]})"
    )
    helps["rank_group"] = (
        "Gegen welche Karten der Rang berechnet wird. Eine Gruppe mit weniger als "
        f"{strength.MIN_GROUP} Karten mit Wert fällt auf den ganzen Pool zurück "
        "(steht dann in der Signalzeile)."
    )
    labels["share_measure"] = (
        f"Anteil messen als (empfohlen: {_MEASURE_CHOICES[rec.share_measure]})"
    )
    helps["share_measure"] = (
        "Die Wilson-Untergrenze ordnet Karten mit verschieden großen Nennern vorsichtiger; "
        "bei gleichem Nenner ändert sie die Reihenfolge nicht. Gegen kleine Stichproben "
        "schützt der Mindest-Nenner."
    )
    labels["min_denominators.edhrec"] = (
        f"Mindest-Nenner EDHREC-Signale (empfohlen: {rec.min_denominators['edhrec']} Decks)"
    )
    helps["min_denominators.edhrec"] = (
        "Liegt der Referenz-Nenner der Quelle (der größte Nenner des Signals) unter dem Minimum, "
        "wird das Signal für alle Karten nicht verwendet; liegt nur der eigene Nenner einer "
        "einzelnen Karte darunter, entfällt das Signal nur für diese Karte. 0 = kein Minimum."
    )
    labels["min_denominators.deck_universe"] = (
        "Mindest-Nenner Decklisten-Universum (empfohlen: das Mindest-Universum des "
        f"Universums, Standard {universe_minimum} Decks; hier nur lesbar)"
    )
    helps["min_denominators.deck_universe"] = (
        "Wird beim Universum eingestellt (Mindest-Universum) und gilt hier unverändert."
    )
    labels["min_denominators.tournament"] = (
        f"Mindest-Nenner Turnierlisten (empfohlen: {rec.min_denominators['tournament']} Listen)"
    )
    helps["min_denominators.tournament"] = (
        "Gibt es weniger Turnierlisten des Commanders, wird das Signal nicht verwendet. "
        "0 = kein Minimum."
    )
    for key in strength.MISSING_CAPABLE:
        labels[f"missing_value.{key}"] = (
            f"Fehlender Wert bei „{strength.LABELS[key]}“ "
            f"(empfohlen: {_MISSING_CHOICES[rec.missing_value[key]]})"
        )
        helps[f"missing_value.{key}"] = (
            "auslassen: eine nicht gelistete Karte ist eine fehlende Beobachtung (Owner-"
            "Entscheidung B5). als niedrigster Rang: nur sinnvoll, wenn die Quelle die "
            "Karten des Commanders fast vollständig nennt."
        )
    labels["rank_commander_and_basics"] = (
        "Commander und Standardländer bewerten "
        f"(empfohlen: {'an' if rec.rank_commander_and_basics else 'aus'})"
    )
    helps["rank_commander_and_basics"] = (
        "aus: der Commander und die Standardländer bekommen keine Stufe "
        "(„nicht bewertet“) und nehmen keinen Rang weg."
    )
    labels["universe_source"] = "Decklisten-Universum (empfohlen: automatisch)"
    helps["universe_source"] = (
        "Woher die Zählung „Decklisten-Universum“ kommt. Automatisch: ein oben gewähltes "
        "gespeichertes Universum, sonst alle lokalen Decklisten des Commanders ab dem "
        "Mindest-Universum, sonst gezählte Decklisten aus dem Repo passend zum Bracket-Signal "
        "(bei keinem passenden das größte), sonst keines. Gezählte Decklisten sind "
        "vollständige Listen, die dieser Commander in jedem Deck hat; eine Karte ohne Zeile "
        "steht in keinem Deck und zählt als gezählte Null (0 von N), nicht als unbekannt. Es "
        "wird nie ein zweites Universum dazugerechnet."
    )
    labels["require_commander_signal"] = (
        f"Stufe nur mit Signal speziell für diesen Commander "
        f"(empfohlen: {'an' if rec.require_commander_signal else 'aus'})"
    )
    helps["require_commander_signal"] = (
        "an: eine Karte bekommt nur dann eine Stufe, wenn mindestens ein Signal speziell für "
        "diesen Commander einen Rang hat (Aufnahme beim Commander, im Bracket, Decklisten-"
        "Universum, Synergie, Turnierlisten). „Aufnahme überhaupt“, Kombos und die Playgroup-"
        "Beobachtung gelten für jeden Commander und reichen allein nicht: die Karte bleibt "
        "„zu wenig Daten“."
    )
    labels["min_coverage"] = (
        f"Mindest-Datenlage in % (empfohlen: {_number_text(round(rec.min_coverage * 100, 1))})"
    )
    helps["min_coverage"] = (
        "Anteil des Gewichts der Signale, die zu dieser Karte einen Wert haben. Darunter steht "
        "„zu wenig Daten“. Das ist keine Schwelle für den Anteil in Decks."
    )
    labels["min_components"] = f"Mindestzahl Signale (empfohlen: {rec.min_components})"
    helps["min_components"] = "Wie viele gewichtete Signale mindestens vorhanden sein müssen."
    for tier in ("S", "A", "B", "C"):
        labels[f"tier_cuts.{tier}"] = f"Grenze {tier} (empfohlen: {_number_text(cuts[tier])})"
        helps[f"tier_cuts.{tier}"] = (
            "Ab diesem Index beginnt die Stufe. Die Grenzen müssen von S bis C streng fallen."
        )
    groups = [
        {"title": "Gewichte je Signal", "keys": [f"weights.{key}" for key in rec.weights]},
        {
            "title": "Zusätzliche Ebenen",
            "keys": [*(f"layer_weights.{key}" for key in strength.LAYER_KEYS), "pod_size"],
        },
        {"title": "Bracket", "keys": ["bracket"]},
        {"title": "Vergleichsgruppe für den Rang", "keys": ["rank_group"]},
        {"title": "Anteil messen als", "keys": ["share_measure"]},
        {
            "title": "Mindest-Nenner je Signal",
            "keys": [
                "min_denominators.edhrec",
                "min_denominators.deck_universe",
                "min_denominators.tournament",
            ],
        },
        {
            "title": "Fehlender Wert",
            "keys": [f"missing_value.{key}" for key in strength.MISSING_CAPABLE],
        },
        {"title": "Decklisten-Universum", "keys": ["universe_source"]},
        {"title": "Commander und Standardländer", "keys": ["rank_commander_and_basics"]},
        {
            "title": "Mindestdaten für eine Stufe",
            "keys": ["min_coverage", "min_components", "require_commander_signal"],
        },
        {
            "title": (
                "Tier-Grenzen (empfohlen: "
                + " / ".join(_number_text(cuts[tier]) for tier in ("S", "A", "B", "C"))
                + ")"
            ),
            "keys": [f"tier_cuts.{tier}" for tier in ("S", "A", "B", "C")],
        },
    ]
    return {
        "labels": labels,
        "help": helps,
        "groups": groups,
        "choices": {
            "bracket": _choices(_BRACKET_CHOICES, rec.bracket),
            "rank_group": _choices(_GROUP_CHOICES, rec.rank_group),
            "share_measure": _choices(_MEASURE_CHOICES, rec.share_measure),
            "missing_value": _choices(_MISSING_CHOICES, strength.MISSING_SKIP),
            "universe_source": [
                {
                    "value": strength.UNIVERSE_AUTO,
                    "label": "Automatisch (empfohlen)",
                    "recommended": True,
                },
                {
                    "value": strength.UNIVERSE_PROFILE,
                    "label": "Nur das oben gewählte Universum, sonst keines",
                    "recommended": False,
                },
                {"value": strength.UNIVERSE_NONE, "label": "keines", "recommended": False},
            ],
            "rank_commander_and_basics": [
                {"value": False, "label": "aus (empfohlen)", "recommended": True},
                {"value": True, "label": "an", "recommended": False},
            ],
            "require_commander_signal": [
                {"value": True, "label": "an (empfohlen)", "recommended": True},
                {"value": False, "label": "aus", "recommended": False},
            ],
        },
        "universe_minimum": universe_minimum,
    }


def presets() -> dict[str, object]:
    """Built-in presets, the recommended values and what the settings panel needs to draw
    itself. ``recommended`` is the one place the recommendations come from."""
    recommended = StrengthSettings().to_dict()
    return {
        "presets": [
            {"name": name, "settings": item.to_dict()} for name, item in strength.PRESETS.items()
        ],
        "components": [
            {"key": key, "label": strength.LABELS[key], "default_weight": weight}
            for key, weight in strength.DEFAULT_WEIGHTS.items()
        ],
        "layers": [
            {
                "key": key,
                "label": layers.LABELS[key],
                "kind": layers.KINDS[key],
                "source": layers.SOURCES[key],
                "denominator": layers.DENOMINATORS[key],
                "description": layers.DESCRIPTIONS[key],
                "weight_allowed": key in strength.LAYER_KEYS,
                "default_weight": strength.DEFAULT_LAYER_WEIGHTS.get(key),
            }
            for key in layers.ALL_LAYER_KEYS
        ],
        "pod_classes": [
            {
                "key": key,
                "label": layers.POD_CLASS_LABELS[key],
                "help": layers.POD_CLASS_HELP[key],
                "rank": layers.POD_CLASS_RANK[key],
            }
            for key in layers.POD_CLASSES
        ],
        "pod_derived_note": layers.POD_DERIVED_NOTE,
        "brackets": [*strength.BRACKETS, strength.BRACKET_NONE],
        "defaults": recommended,
        "recommended": recommended,
        "missing_capable": list(strength.MISSING_CAPABLE),
        "min_group": strength.MIN_GROUP,
        "panel": _panel_texts(),
        "meaning": strength.MEANING,
    }


def resolve_settings(
    store: StudioStore,
    *,
    preset: str | None,
    profile: str | None,
    settings: Mapping[str, object] | None,
) -> StrengthSettings:
    """Settings from at most one source: explicit settings, a saved profile or a preset.

    Raises ValueError for several sources or invalid settings, KeyError for an unknown
    preset or profile; none given means the default settings."""
    if sum(item is not None for item in (preset, profile, settings)) > 1:
        raise ValueError("give at most one of preset, profile and settings")
    if settings is not None:
        return StrengthSettings.from_dict(settings)
    if profile is not None:
        entry = get_profile(store, profile)
        if entry["settings"] is None:
            raise ValueError(
                f"strength profile {profile!r} is not valid any more: {entry['reason']}"
            )
        return StrengthSettings.from_dict(entry["settings"])
    if preset is not None:
        return strength.PRESETS[preset]
    return StrengthSettings()


def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("settings must be a mapping")
    return value


__all__ = [
    "ProfileEntry",
    "SignalCoverage",
    "SignalValue",
    "StrengthResult",
    "card_signal_values",
    "compute",
    "delete_profile",
    "get_profile",
    "list_profiles",
    "presets",
    "profile_notices",
    "rating_layers",
    "resolve_settings",
    "save_profile",
    "signal_coverage",
]
