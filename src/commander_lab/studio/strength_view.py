"""The strength index as the tier list page shows it: store access around ``strength.py``.

Reads the stored signals of ONE commander (``card_signal``), the counted deck-list share of
the chosen universe profile (``universe_view``) and hands them to the pure scoring
function. Figures of two commanders are never combined: every query names its commander,
and commander-independent signals are stored under the empty commander name. The
Playgroup atlas signal is one of them: an observed win-rate correlation from multiplayer
games, published per card, not per commander.

The Owner's marks are not read here. Stored simulation rows are never read here: the index
has no simulation component (Q1-b4, #1679, E15 Q1).

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
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TypedDict, cast

from . import (
    chulane_textfit,
    corpus_signals,
    roles,
    signals,
    strength,
    universe,
    universe_choice,
    universe_view,
)
from .builder import commander_identity, pool_cards, pool_members
from .store import StudioStore, now_utc
from .strength import (
    BRACKET_INCLUSION,
    COMBOS,
    COMMANDER_INCLUSION,
    DECK_UNIVERSE,
    EDHREC_THEME_REACH,
    GLOBAL_INCLUSION,
    PLAYGROUP_OBSERVED,
    SYNERGY,
    TOURNAMENT,
    TOURNAMENT_LISTS,
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
    confidence: float | None
    confidence_level: str | None
    borderline: bool
    borderline_cut: str | None
    cut_distance: float | None
    # D4: the count-based ``confidence`` above replaces the denominator-based one; that one stays
    # here, and ``zero_count_thin`` lists the components whose counted zero rests on < 30 decks.
    confidence_by_denominator: float | None
    confidence_by_denominator_level: str | None
    zero_count_thin: list[str]
    # "gezaehlte_null": more than half of the confidence weight rests on counted zeros (0 of N
    # decks: confidence in an absence), else "zaehler"; None without a confidence.
    confidence_basis: str | None
    is_land: bool
    role_ranks: dict[str, dict[str, int]]
    # D3: the number of ranked cards per role (the ``total`` of ``role_ranks``), by role.
    role_totals: dict[str, int]
    # D6: share of weight variants that keep the tier (kept of variants), the other tiers the
    # variants gave (most frequent first), and "unscharf" below ``stability.unsharp_below``. All
    # None / empty / False for a card without a tier (U, N).
    tier_stability: float | None
    tier_stability_kept: int | None
    tier_stability_variants: int | None
    tier_alternatives: list[strength.TierAlternative]
    unscharf: bool
    # Additional view: tier by percentile rank inside the pool (S to F, lands and spells apart),
    # and the rank k of n. None for a card without a tier, and ``relative_tier`` None in a group
    # of fewer than ten ranked cards. Never replaces ``tier``.
    relative_tier: str | None
    relative_rank: strength.RelativeRank | None
    chulane_textfit: chulane_textfit.ChulaneTextfitResult | None


class UnknownBreakdown(TypedDict):
    """Tier U split (#1365): cards whose only evidence is counted zeros (0 of N decks, setting
    ``zero_count_tier`` = U) against cards with missing or too little data. ``denominator`` is the
    deck count of the cards' own ZERO_COUNT deck-universe rows, or None when there is no single one."""

    total: int
    zero_count: int
    missing_data: int
    by_reason: dict[str, int]
    denominator: int | None


class StabilityInfo(TypedDict):
    """How ``tier_stability`` was derived (D6)."""

    variants: int
    single_weight_variants: int
    random_variants: int
    factor: float
    seed: int
    unsharp_below: float
    unscharf_count: int
    evaluated_cards: int
    base: str
    note: str


class RelativeTierPercent(TypedDict):
    tier: str
    up_to_percent: int


class RelativeTiersInfo(TypedDict):
    """The additional relative view (percentile tiers inside the pool)."""

    note: str
    f_note: str
    min_group: int
    percentiles: list[RelativeTierPercent]
    totals: dict[str, int]
    counts: dict[str, dict[str, int]]


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
    tier_counts_by_kind: dict[str, dict[str, int]]
    unknown_breakdown: UnknownBreakdown
    borderline_count: int
    ambiguous_names: list[AmbiguousName]
    # #1364: the rule of the EDHREC weights (E2.a), the weights actually used, the counted corpus
    # and the empirical Bayes priors of the components with small denominators
    weight_rule: strength.WeightRule
    effective_weights: dict[str, float]
    corpus: corpus_signals.CorpusInfo
    shrinkage: dict[str, object]
    # D2: the effective weight per source family (nominal weight and share of the total)
    weight_families: list[strength.WeightFamily]
    # D6: how the stability of the tiers was derived
    stability: StabilityInfo
    # the relative tiers (percentiles inside the pool): the hint, the limits and the counts
    relative_tier_info: RelativeTiersInfo
    # D3: per role the number of ranked cards (the denominator of ``role_ranks``)
    role_totals: dict[str, int]
    chulane_textfit_version: str | None
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
# Signals stored with a published rate and a denominator but no card count (the EDHTop16 play
# rate: the entries of the commander are published, how many of them hold the card is not). The
# reader derives the numerator ``round(rate * denominator)``; the stored row stays as published.
# Other signals with a value and a denominator but no numerator are NOT shares (the Playgroup gap
# is a difference with its sample as denominator): they keep their NULL numerator.
_RATE_ONLY_SIGNALS = frozenset({signals.SIGNAL_EDHTOP16})
# claim key -> [(claim kind, card id)]
_Claims = dict[str, list[tuple[int, str]]]


def _claim_index(store: StudioStore, ids: list[str]) -> _Claims:
    index: _Claims = {}
    for card_id, claims in name_claims(store, ids).items():
        for key, kind in claims:
            index.setdefault(key, []).append((kind, card_id))
    return index


def _claim(
    name: str,
    signal: str,
    claims: _Claims,
    display: Mapping[str, str],
    ambiguous: dict[tuple[str, str], list[str]],
) -> tuple[int, str] | None:
    """``(claim kind, card id)`` of the pool card a stored name belongs to, ``None`` when no
    card claims it or several claim it equally (then it is listed in ``ambiguous``)."""
    found = claims.get(name.casefold())
    if not found:
        return None
    kind = min(item[0] for item in found)
    owners = sorted({card for item_kind, card in found if item_kind == kind})
    if len(owners) > 1:
        ambiguous[(signal, name)] = sorted(display[card] for card in owners)
        return None
    return kind, owners[0]


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
        claim = _claim(name, signal, claims, display, ambiguous)
        if claim is None:
            continue
        kind, card_id = claim
        rank = (kind, name)
        current = best.get(card_id)
        if current is None or rank < (current[0], current[1]):
            numerator = row["numerator"]
            if (
                numerator is None
                and signal in _RATE_ONLY_SIGNALS
                and row["value"] is not None
                and row["denominator"]
            ):
                numerator = round(float(row["value"]) * int(row["denominator"]))
            best[card_id] = (
                kind,
                name,
                Observation(row["value"], numerator, row["denominator"]),
            )
    return {card_id: item[2] for card_id, item in best.items()}, bool(rows)


def _theme_reach_observations(
    store: StudioStore,
    commander: str,
    claims: _Claims,
    display: Mapping[str, str],
    ambiguous: dict[tuple[str, str], list[str]],
    minimum_denominator: int,
) -> tuple[dict[str, Observation], bool]:
    """``edhrec_theme_reach``: per pool card the highest share over the EDHREC themes of the
    commander (observation cohorts ``edhrec:<commander>/<theme>``). The commander page itself and
    the bracket and price pages are no themes; a theme row counts only when its own denominator
    reaches ``minimum_denominator`` (a card in 1 of 1 decks of a tiny theme is no reach). The
    observation carries the numerator and denominator of the winning theme and names it; the
    maximum over many themes leans upward, which is why it only has a small weight. Whether the
    source exists is decided by any theme row of the commander."""
    rows = store.connection.execute(
        "SELECT o.card_name, o.cohort, o.numerator, o.denominator FROM observation o "
        "JOIN commander_binding b ON b.kind = 'observation_cohort' AND b.key = o.cohort "
        "AND b.commander_name = ? "
        "WHERE o.metric = 'inclusion_pct' AND o.numerator IS NOT NULL AND o.denominator > 0 "
        "AND o.numerator <= o.denominator ORDER BY o.cohort, o.card_name",
        (commander,),
    ).fetchall()
    candidates: dict[str, list[tuple[float, int, str, int]]] = {}
    exists = False
    for row in rows:
        cohort = str(row["cohort"])
        _page, _slash, theme = cohort.partition("/")
        if not theme or theme in corpus_signals.VARIANT_PAGES:
            continue
        exists = True
        denominator, numerator = int(row["denominator"]), int(row["numerator"])
        if denominator < minimum_denominator:
            continue
        claim = _claim(str(row["card_name"]), "edhrec_theme_inclusion", claims, display, ambiguous)
        if claim is None:
            continue
        candidates.setdefault(claim[1], []).append(
            (numerator / denominator, denominator, theme, numerator)
        )
    # Each theme share is shrunk on its own, then the highest posterior mean wins: shrinking
    # the raw maximum would let a 1 of 3 theme beat a 50 of 400 one (the maximum of noisy
    # shares leans upward, the more the smaller the theme).
    pairs = [(item[3], item[1]) for found in candidates.values() for item in found]
    prior = strength.beta_binomial_prior(
        [pair for pair in pairs if pair[1] < strength.EB_MAX_DENOMINATOR]
    )
    result: dict[str, Observation] = {}
    for card_id, found in candidates.items():
        scored = [
            (
                strength.shrunk_share(item[3], item[1], prior)
                if prior is not None and item[1] < strength.EB_MAX_DENOMINATOR
                else item[0],
                item,
            )
            for item in found
        ]
        best, (share, denominator, theme, numerator) = sorted(
            scored, key=lambda entry: (-entry[0], -entry[1][1], entry[1][2])
        )[0]
        result[card_id] = Observation(
            share,
            numerator,
            denominator,
            note=(
                f"Maximum über {len(found)} EDHREC-Themen nach Schrumpfung je Thema: {theme} "
                f"({numerator} von {denominator} Decks)"
            ),
            shrunk=best if prior is not None else None,
            prior=prior,
        )
    return result, exists


def _valid_shell_count(value: float | None, *, maximum: float | None = None) -> bool:
    if value is None or not math.isfinite(value) or value < 0:
        return False
    return maximum is None or value <= maximum


def shell_note(shells: float, two_card: float | None, commander: float | None) -> str:
    """The row text of a shell count (#1366): the total and its breakdown by card
    count and commander involvement, the figures the detail modal shows."""
    if not _valid_shell_count(shells):
        return "Combo-Shells (ungültige Gesamtzahl)"
    cards_ok = _valid_shell_count(two_card, maximum=shells)
    cmd_ok = _valid_shell_count(commander, maximum=shells)
    if not cards_ok and not cmd_ok:
        return f"{_number_text(shells)} Combo-Shells (Aufschlüsselung unbekannt)"
    if cards_ok and two_card is not None:
        three_plus = shells - two_card
        card_part = (
            f"davon {_number_text(two_card)} mit 2 Karten, {_number_text(three_plus)} mit 3+ Karten"
        )
    else:
        card_part = "2/3+-Karten-Aufschlüsselung unbekannt"
    if cmd_ok and commander is not None:
        cmd_part = f"{_number_text(commander)} mit Commander-Beteiligung"
    else:
        cmd_part = "Commander-Beteiligung unbekannt"
    return f"{_number_text(shells)} Combo-Shells ({card_part}, {cmd_part})"


def _combo_observations(
    store: StudioStore,
    commander: str,
    claims: _Claims,
    display: Mapping[str, str],
    ambiguous: dict[tuple[str, str], list[str]],
) -> tuple[dict[str, Observation], bool, bool]:
    """The combos observations: one per pool card the spellbook source lists, valued
    by the combo quality mixture (``strength.combo_quality``). Returns ``(observations,
    exists, used_shells)``. Whether the source exists is decided by the primary signal
    alone; the other parts only refine the value of the listed cards.

    When the store holds the shell signals (#1366) for this commander, the mixture reads
    the shell parts and the shell count is the primary part — distinct combos instead of
    raw variants — and the note carries the shell breakdown. The variant count is then a
    stored display value only. Without the commander's shell signals, the variant mixture
    ranks exactly as before."""
    shell_raw: dict[str, dict[str, Observation]] = {}
    shell_parts: dict[str, dict[str, float]] = {}
    shell_exists = False
    for signal in strength.COMBO_SHELL_PARTS:
        observed, found = _signal_observations(store, commander, signal, claims, display, ambiguous)
        if signal == strength.COMBO_PART_SHELLS:
            shell_exists = found
        shell_raw[signal] = observed
        shell_parts[signal] = {
            card_id: item.value for card_id, item in observed.items() if item.value is not None
        }
    if shell_exists:
        quality = strength.combo_quality(shell_parts, primary=strength.COMBO_PART_SHELLS)
        result: dict[str, Observation] = {}
        for card_id, value in quality.items():
            shell_count = shell_parts[strength.COMBO_PART_SHELLS][card_id]
            two_item = shell_raw[strength.COMBO_PART_TWO_CARD_SHELLS].get(card_id)
            cmd_item = shell_raw[strength.COMBO_PART_COMMANDER_SHELLS].get(card_id)
            result[card_id] = Observation(
                value,
                note=shell_note(
                    shell_count,
                    two_item.value if two_item is not None else None,
                    cmd_item.value if cmd_item is not None else None,
                ),
            )
        return result, True, True
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
        False,
    )


def _number_text(value: float) -> str:
    """A number the way the Owner reads it: 3 not 3.0, 0,4 with a decimal comma."""
    return (f"{value:g}").replace(".", ",")


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


def expected_signals(commander: str = "") -> list[str]:
    """The usage signals the importers can store, a fixed list from the code (not from what
    happens to be stored): a signal without rows is then shown as missing, never left out."""
    names = [
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
    return names


def signal_coverage(
    store: StudioStore, commander: str, *, include_commanders: bool = True
) -> dict[str, SignalCoverage]:
    """Per stored signal: its rows and how many of the commander's pool cards it gives a
    value (the same name matching as the index). Counts only. A signal without rows for
    this commander is listed with 0 rows: missing, not a weak signal. Raises KeyError when
    the commander is not in the collection."""
    # Only the pool's card ids and names are read here: the light pool (the same cards in the
    # same order as ``pool_cards``) skips the builder's per-card figures, which cost a quarter
    # second per commander in the data report's sweep over every commander.
    _identity, commander_list = commander_identity(store, [commander])
    raw_cards = pool_members(store, [commander])
    commander_ids = set(commander_list)
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["oracle_name"]) for card in raw_cards}
    non_cmd_cards = [card for card in raw_cards if str(card["card_id"]) not in commander_ids]
    display_non_cmd = {str(card["card_id"]): str(card["oracle_name"]) for card in non_cmd_cards}
    claims = _claim_index(store, ids)
    db = store.connection
    result: dict[str, SignalCoverage] = {}
    stored = [str(row[0]) for row in db.execute("SELECT DISTINCT signal FROM card_signal")]
    own_stored = {
        str(row[0])
        for row in db.execute(
            "SELECT DISTINCT signal FROM card_signal WHERE commander_name = ?",
            (commander,),
        )
    }
    counted_signals = {
        item["signal"]: item for item in universe_choice.counted_universes(store, commander)
    }
    names = expected_signals(commander)
    if counted_signals:
        names.remove(signals.SIGNAL_DECKLIST)
    for signal in sorted(set(stored) - set(names) - signals.RETIRED_SIGNALS):
        if signal.startswith(f"{signals.SIGNAL_DECKLIST}:") and signal not in counted_signals:
            continue  # a counted universe of another commander
        if signal in strength.COMBO_SHELL_PARTS and signal not in own_stored:
            continue  # commander-scoped combo shells of another commander
        names.append(signal)
    for signal in names:
        independent = signal in _INDEPENDENT
        owner = "" if independent else commander
        scoped_display = display if (include_commanders or independent) else display_non_cmd
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
            valued = sum(1 for cid in scoped_display if cid in full)
        else:
            observed, _exists = _signal_observations(store, commander, signal, claims, display, {})
            valued = sum(
                1
                for cid in scoped_display
                if (item := observed.get(cid)) is not None and item.value is not None
            )
        result[signal] = {
            "scope": "independent" if independent else "commander",
            "rows": int(counted[0]),
            "rows_with_value": int(counted[1]),
            "pool_cards_with_value": valued,
            "pool_size": len(scoped_display),
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
    store: StudioStore,
    commander: str,
    card_ids: list[str],
    display: Mapping[str, str],
    *,
    extra: Mapping[str, str] | None = None,
) -> dict[str, dict[str, SignalValue]]:
    """Stored usage signals of ONE commander per pool card, for the builder columns.

    Keys per card: ``inclusion`` (decks with the card over the commander's decks),
    ``synergy`` and ``global_inclusion`` (independent of the commander). A card without a
    row for a signal has no entry for it: unknown, never 0. Same name matching as the index.
    ``extra`` names more stored signals to read the same way (``{key: stored signal name}``)."""
    claims = _claim_index(store, card_ids)
    wanted = {
        "inclusion": strength.signal_for(COMMANDER_INCLUSION, strength.BRACKET_NONE),
        "synergy": strength.signal_for(SYNERGY, strength.BRACKET_NONE),
        "global_inclusion": strength.signal_for(GLOBAL_INCLUSION, strength.BRACKET_NONE),
        **(extra or {}),
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


def _unranked_cards(
    raw_cards: Sequence[Mapping[str, object]], commander_ids: set[str]
) -> dict[str, str]:
    """The cards that get no tier: the commander and basic lands."""
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


_ROLE_ORDER = {role: index for index, role in enumerate(roles.ROLES)}


def _function_groups(
    store: StudioStore, raw_cards: Sequence[Mapping[str, object]]
) -> dict[str, tuple[str, ...]]:
    """The functional roles of every pool card (``card_role`` by oracle id), in the
    canonical order of ``roles.ROLES``. A card without a sourced role is absent: the
    function comparison group then falls back to the pool for it, said openly."""
    by_oracle: dict[str, list[str]] = {}
    with store.connection as db:
        for oracle_id, role in db.execute("SELECT oracle_id, role FROM card_role"):
            by_oracle.setdefault(str(oracle_id), []).append(str(role))
    result: dict[str, tuple[str, ...]] = {}
    for card in raw_cards:
        found = by_oracle.get(_optional_text(card["oracle_id"]) or "")
        if found:
            result[str(card["card_id"])] = tuple(
                sorted(found, key=lambda role: (_ROLE_ORDER.get(role, len(_ROLE_ORDER)), role))
            )
    return result


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


def _other_commander_names(store: StudioStore, commander: str) -> set[str]:
    """Casefolded names of the commanders the store knows besides ``commander``: the ones
    source decks are bound to and the ones signals were imported for. Such a card is a
    commander in its own right and, like the chosen one, not ranked in this commander's pool
    unless the Owner switches that on."""
    found: set[str] = set()
    target = commander.casefold()
    for (name,) in store.connection.execute(
        "SELECT commander_name FROM commander_binding WHERE kind IN ('corpus_deck', "
        "'neutral_source') UNION SELECT commander_name FROM card_signal "
        "WHERE commander_name != ''"
    ):
        folded = str(name).casefold()
        if folded != target:
            found.add(folded)
    return found


@dataclass
class Prepared:
    """Everything the scoring needs, read from the store once: the one place that builds the
    observations for the tier list (``compute``) and for the ranking check."""

    commander: str
    settings: StrengthSettings  # as requested (a dangling universe profile already dropped)
    effective: StrengthSettings  # with the E2.a rule applied: what the scoring uses
    weight_rule: strength.WeightRule
    ids: list[str]
    display: dict[str, str]
    raw_cards: list[Mapping[str, object]]
    per_card: dict[str, dict[str, Observation]]
    collected: set[str]
    context: PoolContext
    choice: UniverseChoice
    summary: ProfileSummary | None
    universe_missing: str | None
    notices: list[str]
    ambiguous: dict[tuple[str, str], list[str]]
    corpus: corpus_signals.CorpusInfo
    corpus_counts: corpus_signals.CorpusCounts | None
    edhtop16: dict[str, Observation]


def prepare(
    store: StudioStore,
    commander: str,
    settings: StrengthSettings,
    *,
    dangling_universe_ok: bool = False,
    notices: Sequence[str] = (),
) -> Prepared:
    """Read the observations of ``commander``'s legal pool and the rule-adjusted settings.

    Raises KeyError when the commander is not in the collection or the universe profile of the
    settings is unknown; with ``dangling_universe_ok`` a deleted profile gives a notice and the
    automatic choice instead."""
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
    spellbook_shells_used = False
    for component in (
        COMMANDER_INCLUSION,
        BRACKET_INCLUSION,
        SYNERGY,
        TOURNAMENT_LISTS,
        GLOBAL_INCLUSION,
        COMBOS,
        PLAYGROUP_OBSERVED,
    ):
        signal = strength.signal_for(
            component, settings.bracket, combo_source=settings.combo_source
        )
        if not signal:
            continue
        if component == COMBOS and settings.combo_source == strength.COMBO_SPELLBOOK:
            observed, exists, spellbook_shells_used = _combo_observations(
                store, commander, claims, display, ambiguous
            )
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

    # Corpus components (#1364): the counted local corpus of the commander, its cohorts, EDHTop16
    # and the EDHREC themes. A source that does not exist for the commander is not collected
    # (``NOT_COLLECTED``, no coverage penalty).
    corpus_minimum = TierParams().min_universe
    local_decks = universe_choice.local_deck_count(store, commander)
    counts = corpus_signals.count_corpus(store, commander, ids, corpus_minimum)
    corpus = (
        counts.info(corpus_minimum)
        if counts is not None
        else corpus_signals.no_corpus(local_decks, corpus_minimum)
    )
    global_inclusion = {
        card_id: per[GLOBAL_INCLUSION]
        for card_id, per in per_card.items()
        if GLOBAL_INCLUSION in per
    }
    if counts is not None:
        for component, found in corpus_signals.corpus_observations(
            counts, global_inclusion
        ).items():
            if not found:
                continue  # no card has a value (e.g. no global share for the lift): not collected
            collected.add(component)
            for card_id, observation in found.items():
                per_card[card_id][component] = observation
    top16, top16_exists = _signal_observations(
        store, commander, signals.SIGNAL_EDHTOP16, claims, display, ambiguous
    )
    tournament = corpus_signals.tournament_observations(counts, top16)
    if tournament or top16_exists:
        collected.add(TOURNAMENT)
    for card_id, observation in tournament.items():
        per_card[card_id][TOURNAMENT] = observation
    themes, themes_exist = _theme_reach_observations(
        store, commander, claims, display, ambiguous, settings.min_denominators[strength.MIN_EDHREC]
    )
    if themes_exist:
        collected.add(EDHREC_THEME_REACH)
    for card_id, observation in themes.items():
        per_card[card_id][EDHREC_THEME_REACH] = observation

    type_group: dict[str, str] = {}
    bands: dict[str, str] = {}
    unranked = _unranked_cards(raw_cards, commander_ids)
    for card in raw_cards:
        card_id = str(card["card_id"])
        group = str(card["group"])
        type_group[card_id] = group
        bands[card_id] = strength.mana_band(_float(card["mana_value"]), is_land=group == "Land")
    # Other commanders known to the store are not ranked in this commander's pool (tier N).
    others = _other_commander_names(store, commander)
    tier_unranked = dict(unranked)
    for card in raw_cards:
        card_id = str(card["card_id"])
        if card_id not in tier_unranked and str(card["name"]).casefold() in others:
            tier_unranked[card_id] = strength.NOT_RANKED_OTHER_COMMANDER
    context = PoolContext(
        type_group,
        bands,
        tier_unranked,
        filter_cards,
        universe_minimum,
        function_group=_function_groups(store, raw_cards),
        spellbook_shells=spellbook_shells_used,
    )
    # E2.a: while a counted local corpus exists the EDHREC inclusion weights are 0 (the rule is
    # explicit and reported); without one they are the fallback.
    effective, weight_rule = strength.apply_corpus_rule(
        settings, corpus_decks=local_decks, min_universe=corpus_minimum
    )
    return Prepared(
        commander,
        settings,
        effective,
        weight_rule,
        ids,
        display,
        raw_cards,
        per_card,
        collected,
        context,
        choice,
        summary,
        universe_missing,
        notices,
        ambiguous,
        corpus,
        counts,
        top16,
    )


def compute(
    store: StudioStore,
    commander: str,
    settings: StrengthSettings,
    *,
    dangling_universe_ok: bool = False,
    notices: Sequence[str] = (),
    saved_weights: Mapping[str, float] | None = None,
) -> StrengthResult:
    """Index and tier for every legal pool card of ``commander``.

    ``saved_weights`` are the weights a loaded profile stored (``profile_saved_weights``): the
    result then says when the E2.a rule zeroes a stored EDHREC weight.

    Raises KeyError when the commander is not in the collection or the universe profile of
    the settings is unknown. With ``dangling_universe_ok`` (settings read from a saved
    profile) a universe profile that was deleted meanwhile is not an error: the index runs
    with "kein Universum" and the result carries a notice and ``universe_missing``."""
    prepared = prepare(
        store, commander, settings, dangling_universe_ok=dangling_universe_ok, notices=notices
    )
    settings = prepared.settings
    diagnostics: dict[str, object] = {}
    scored = strength.score_pool(
        prepared.effective,
        prepared.per_card,
        prepared.collected,
        context=prepared.context,
        diagnostics=diagnostics,
    )
    notices_out = prepared.notices
    notices_out.extend(_weight_notices(settings, prepared.weight_rule, saved_weights or {}))
    roles_by_id: dict[str, list[str]] = {
        str(card["card_id"]): [str(r) for r in card["roles"]]  # type: ignore[attr-defined]
        for card in prepared.raw_cards
        if isinstance(card.get("roles"), list)
    }
    scored_by_role: dict[str, list[tuple[float, str, str]]] = {}
    for card_id in prepared.ids:
        result = scored[card_id]
        idx_val = result["index"]
        if result["tier"] in ("U", "N") or idx_val is None:
            continue
        for role in roles_by_id.get(card_id, ()):
            scored_by_role.setdefault(role, []).append(
                (float(idx_val), prepared.display[card_id], card_id)
            )
    ranks_for_card: dict[str, dict[str, dict[str, int]]] = {}
    for role, bucket in scored_by_role.items():
        bucket.sort(key=lambda item: (-item[0], item[1], item[2]))
        total = len(bucket)
        prev_idx: float | None = None
        current_rank = 0
        for pos, (idx_val, _name, card_id) in enumerate(bucket, start=1):
            if prev_idx is None or abs(idx_val - prev_idx) > 1e-12:
                current_rank = pos
                prev_idx = idx_val
            ranks_for_card.setdefault(card_id, {})[role] = {
                "rank": current_rank,
                "total": total,
            }

    raw_inputs = diagnostics.get("tier_inputs")
    tier_inputs = cast("dict[str, strength.TierInputs]", raw_inputs) if raw_inputs else {}
    stability = strength.tier_stability(
        prepared.effective,
        tier_inputs,
        {card_id: scored[card_id]["tier"] for card_id in tier_inputs},
    )
    relative = strength.relative_tiers(
        {
            card_id: (float(scored[card_id]["index"] or 0.0), is_land)
            for card_id in prepared.ids
            if scored[card_id]["tier"] in strength.TIERS and scored[card_id]["index"] is not None
            for is_land in (prepared.context.type_group.get(card_id) == "Land",)
        }
    )

    raw_by_id = {str(card["card_id"]): card for card in prepared.raw_cards}
    show_chulane_textfit = chulane_textfit.is_chulane_commander(commander)
    cards: list[StrengthCard] = []
    for card_id in prepared.ids:
        result = scored[card_id]
        found = stability.get(card_id)
        rel = relative.get(card_id)
        raw_card = raw_by_id.get(card_id)
        textfit_val: chulane_textfit.ChulaneTextfitResult | None = None
        if show_chulane_textfit and raw_card is not None:
            mv_raw = raw_card.get("mana_value")
            mv_val = float(mv_raw) if isinstance(mv_raw, int | float) else None
            textfit_val = chulane_textfit.evaluate_chulane_textfit(
                type_line=str(raw_card.get("type_line") or ""),
                oracle_text=str(raw_card.get("text") or ""),
                mana_value=mv_val,
                produced_mana=str(raw_card.get("produced_mana") or ""),
            )
        cards.append(
            {
                "card_id": card_id,
                "name": prepared.display[card_id],
                **result,
                "is_land": prepared.context.type_group.get(card_id) == "Land",
                "role_ranks": ranks_for_card.get(card_id, {}),
                "role_totals": {
                    role: info["total"] for role, info in ranks_for_card.get(card_id, {}).items()
                },
                "tier_stability": found["stability"] if found else None,
                "tier_stability_kept": found["kept"] if found else None,
                "tier_stability_variants": found["variants"] if found else None,
                "tier_alternatives": found["alternatives"] if found else [],
                "unscharf": bool(found and found["stability"] < strength.STABILITY_UNSHARP_BELOW),
                "relative_tier": rel[0] if rel else None,
                "relative_rank": rel[1] if rel else None,
                "chulane_textfit": textfit_val,
            }
        )
    tiers = Counter(card["tier"] for card in cards)
    tier_order = (*strength.TIERS, "U", "N")
    by_kind = {
        kind: {tier: sum(1 for c in group if c["tier"] == tier) for tier in tier_order}
        for kind, group in (
            ("spells", [c for c in cards if not c["is_land"]]),
            ("lands", [c for c in cards if c["is_land"]]),
        )
    }
    unknown = [card for card in cards if card["tier"] == "U"]
    unknown_reasons = Counter(card["reason"] for card in unknown)
    zero_only = unknown_reasons.get(strength.ZERO_COUNT_ONLY, 0)
    # the deck count the zeros refer to, taken from the cards' own ZERO_COUNT rows; None when
    # the rows name more than one denominator (then the header names no single N)
    zero_denominators = {
        row["denominator"]
        for card in unknown
        if card["reason"] == strength.ZERO_COUNT_ONLY
        for row in card["components"]
        if row["status"] == strength.ZERO_COUNT
        and row["component"] == strength.DECK_UNIVERSE
        and row["denominator"]
    }
    breakdown: UnknownBreakdown = {
        "total": len(unknown),
        "zero_count": zero_only,
        "missing_data": len(unknown) - zero_only,
        "by_reason": dict(sorted(unknown_reasons.items())),
        "denominator": next(iter(zero_denominators)) if len(zero_denominators) == 1 else None,
    }
    shrinkage = diagnostics["shrinkage"]
    relative_counts: dict[str, dict[str, int]] = {
        group: {name: 0 for name in strength.RELATIVE_TIERS}
        for group in (strength.RELATIVE_GROUP_SPELLS, strength.RELATIVE_GROUP_LANDS)
    }
    for tier_name, rank_info in relative.values():
        if tier_name is not None:
            relative_counts[rank_info["group"]][tier_name] += 1
    variants = next(iter(stability.values()))["variants"] if stability else 0
    return {
        "schema": strength.SCHEMA,
        "data_class": strength.DATA_CLASS,
        "meaning": strength.MEANING,
        "commander": commander,
        "settings": settings.to_dict(),
        "universe": prepared.summary
        if prepared.choice["kind"] == universe_choice.KIND_PROFILE
        else None,
        "universe_choice": prepared.choice,
        "universe_missing": prepared.universe_missing,
        "notices": notices_out,
        "collected": sorted(prepared.collected),
        "tier_counts": {tier: tiers.get(tier, 0) for tier in tier_order},
        "tier_counts_by_kind": by_kind,
        "unknown_breakdown": breakdown,
        "borderline_count": sum(1 for card in cards if card["borderline"]),
        "ambiguous_names": [
            {"signal": signal, "name": name, "candidates": candidates}
            for (signal, name), candidates in sorted(prepared.ambiguous.items())
        ],
        "weight_rule": prepared.weight_rule,
        "effective_weights": dict(prepared.effective.weights),
        "corpus": prepared.corpus,
        "shrinkage": dict(shrinkage) if isinstance(shrinkage, dict) else {},
        "weight_families": strength.weight_families(prepared.effective),
        "stability": {
            "variants": variants,
            "single_weight_variants": variants - strength.STABILITY_RANDOM_VARIANTS
            if variants
            else 0,
            "random_variants": strength.STABILITY_RANDOM_VARIANTS if variants else 0,
            "factor": strength.STABILITY_FACTOR,
            "seed": strength.STABILITY_SEED,
            "unsharp_below": strength.STABILITY_UNSHARP_BELOW,
            "unscharf_count": sum(1 for card in cards if card["unscharf"]),
            "evaluated_cards": len(stability),
            "base": "wirksame Gewichte der Anfrage (im Standard das Preset Ausgewogen)",
            "note": (
                "Anteil der Gewichtsvarianten, in denen die Karte ihre Stufe behält: jedes "
                "Gewicht über 0 einzeln ±20 %, dazu alle zugleich zufällig ±20 % (fester Seed); "
                "unscharf: weniger als 80 % der Varianten"
            ),
        },
        "role_totals": {role: len(bucket) for role, bucket in sorted(scored_by_role.items())},
        "chulane_textfit_version": (
            chulane_textfit.CHULANE_TEXTFIT_RULES_VERSION if show_chulane_textfit else None
        ),
        "relative_tier_info": {
            "note": strength.RELATIVE_TIER_NOTE,
            "f_note": strength.RELATIVE_TIER_F_NOTE,
            "min_group": strength.RELATIVE_MIN_GROUP,
            "percentiles": [
                {"tier": name, "up_to_percent": percent}
                for name, percent in (*strength.RELATIVE_TIER_PERCENTILES, ("F", 100))
            ],
            "totals": {
                group: sum(1 for _tier, info in relative.values() if info["group"] == group)
                for group in relative_counts
            },
            "counts": relative_counts,
        },
        "cards": cards,
    }


def compute_with_snapshot(
    store: StudioStore,
    commander: str,
    settings: StrengthSettings,
    *,
    profile_name: str | None = None,
    dangling_universe_ok: bool = False,
    notices: Sequence[str] = (),
    saved_weights: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Read a persisted tier snapshot on HIT, or compute live with snapshot status metadata."""
    from . import tier_snapshot

    return tier_snapshot.read_snapshot(
        store,
        commander,
        settings,
        profile_name=profile_name,
        dangling_universe_ok=dangling_universe_ok,
        notices=notices,
        saved_weights=saved_weights,
    )


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


def _weight_notices(
    settings: StrengthSettings, rule: strength.WeightRule, saved: Mapping[str, float]
) -> list[str]:
    """Notices on weights that do not act as the person may expect: stored EDHREC weights the
    E2.a rule sets to 0."""
    found: list[str] = []
    if rule["rule"] == strength.RULE_CORPUS_ZERO:
        zeroed = [
            f"{strength.LABELS[name]} (gespeichert {saved[name]:g}, wirksam 0)"
            for name in strength.EDHREC_RULE_COMPONENTS
            if saved.get(name, 0.0) > 0
        ]
        if zeroed:
            found.append(
                "Gespeicherte EDHREC-Gewichte werden vom gezählten Korpus auf 0 gesetzt "
                f"(Regel {strength.RULE_CORPUS_ZERO}): "
                + "; ".join(zeroed)
                + ". Einstellung „EDHREC-Gewichte mit Korpus behalten“ (an) hebt das auf."
            )
    return found


def profile_saved_weights(store: StudioStore, name: str) -> dict[str, float]:
    """The weights the stored profile ``name`` holds for its own (known) keys."""
    entry = get_profile(store, name)
    stored = entry["settings"]
    weights = stored.get("weights") if stored is not None else None
    if not isinstance(weights, Mapping):
        return {}
    return {
        str(key): float(value) for key, value in weights.items() if isinstance(value, (int, float))
    }


# Q1-b2 (#1677), Q1-b4 (#1679): the German names of the retired settings a profile notice may
# name.
_RETIRED_NAMES = {
    "layer_weights": "Gewichte der Bewertungsebenen",
    "pod_size": "Pod-Größe",
    "weights.rubric": "Gewicht Raster-Bewertung (Rubrik v1)",
    "weights.simulation": "Gewicht Simulation",
    "weights.tournament_conversion": "Gewicht Turnier-Conversion (TopDeck)",
    "min_denominators.conversion": "Mindest-Nenner Turnier-Conversion",
}


def _retired_notice(store: StudioStore, name: str) -> list[str]:
    """One calm notice when the stored profile ``name`` holds a value of a retired setting that
    differed from its default (``strength.retired_deviations``); none otherwise."""
    row = store.connection.execute(
        "SELECT spec FROM strength_profile WHERE name = ?", (name,)
    ).fetchone()
    try:
        raw = _as_mapping(json.loads(str(row["spec"]))) if row is not None else {}
    except (ValueError, TypeError):
        return []
    deviating = strength.retired_deviations(raw)
    if not deviating:
        return []
    return [
        f"Hinweis: Die Einstellung „{name}“ enthält einen Wert für "
        + " und ".join(_RETIRED_NAMES.get(key, key) for key in deviating)
        + ". Diese Einstellung gibt es nicht mehr; der Wert wird nicht verwendet, alles andere "
        "gilt wie gespeichert."
    ]


def profile_notices(store: StudioStore, name: str) -> list[str]:
    """Notices for computing with a stored profile: keys of the profile this version does not
    know are ignored, not an error; a retired setting whose stored value differed from its
    default is named once (Q1-b2, Q1-b4)."""
    ignored = get_profile(store, name)["ignored_keys"]
    found = (
        [
            f"Die Einstellung „{name}“ enthält unbekannte Schlüssel, sie werden ignoriert: "
            + ", ".join(ignored)
        ]
        if ignored
        else []
    )
    return found + _retired_notice(store, name)


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


_GROUP_CHOICES = {
    strength.GROUP_POOL: "ganzer Pool",
    strength.GROUP_TYPE: "gleicher Kartentyp",
    strength.GROUP_MANA_BAND: "gleiches Manawert-Band",
    strength.GROUP_FUNCTION: "gleiche Funktion (Rolle)",
}
_MEASURE_CHOICES = {
    strength.MEASURE_WILSON: "Wilson-Untergrenze",
    strength.MEASURE_RAW: "roher Anteil",
}
_SCALE_CHOICES = {
    strength.SCALE_LOG: "Anteil (Logarithmus relativ zum Maximum)",
    strength.SCALE_SHARE: "Anteil (Wurzel relativ zum Maximum)",
    strength.SCALE_RANK: "Rang (Perzentil)",
}
_ZERO_TIER_CHOICES = {
    strength.ZERO_TIER_D: "Stufe D (gezählte Null zählt voll)",
    strength.ZERO_TIER_U: "zu wenig Daten (U)",
}
_EDHREC_WITH_CORPUS_CHOICES = {
    False: "aus: der Korpus ersetzt die EDHREC-Gewichte",
    True: "an: EDHREC-Gewichte auch mit Korpus",
}
_MISSING_CHOICES = {
    strength.MISSING_SKIP: "auslassen",
    strength.MISSING_LOWEST: "als niedrigster Rang zählen",
}
_BRACKET_CHOICES = {
    "core": "Core (Bracket 2)",
    "upgraded": "Upgraded (Bracket 3)",
    "optimized": "Optimized (Bracket 4)",
    "cedh": "cEDH (Bracket 5)",
    "none": "kein Bracket",
}
_COMBO_SOURCE_CHOICES = {
    strength.COMBO_COMMANDER: "EDHREC-Kombos des Commanders",
    strength.COMBO_SPELLBOOK: "Commander Spellbook (Shells beim Commander, sonst Varianten)",
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
    helps[f"weights.{strength.SYNERGY}"] = (
        "EDHREC-Synergie beim Commander („hier häufiger als anderswo“). Standardmäßig "
        "aus dem Index genommen (Gewicht 0) und als Spalte „Passt zum Commander“ gezeigt. "
        "Bei positivem Gewicht wirkt negative Synergie (< 0) neutral (kein Abzug)."
    )
    helps[f"weights.{strength.PLAYGROUP_OBSERVED}"] = (
        "Beobachteter Unterschied der Siegrate, wenn die Karte gewirkt wurde (Playgroup-Live-"
        f"Partien, alle Commander). Zählt erst ab {rec.min_denominators['playgroup']} Partien "
        f"(Import-Minimum {strength.OBSERVED_MIN_SAMPLE}) mit der Karte und wird über "
        f"n / (n + {strength.OBSERVED_SHRINKAGE}) zur Null hin gedämpft. Standardmäßig nur "
        "als Spalte „Sieg-Abstand“ gezeigt (Gewicht 0). Gilt für jeden Commander und reicht "
        "für eine Stufe allein nicht. 0 schaltet das Signal ab."
    )
    helps[f"weights.{strength.DECK_UNIVERSE}"] = (
        "Wie stark die Verbreitung in gezählten Decklisten zählt. 0 schaltet sie ab."
    )
    for key in strength.EDHREC_RULE_COMPONENTS:
        helps[f"weights.{key}"] = (
            "Rückfall-Gewicht der EDHREC-Aufnahme (Regel E2.a): Es gilt nur, solange für den "
            f"Commander kein gezählter lokaler Korpus mit mindestens {universe_minimum} Decks "
            "vorliegt. Mit Korpus ist das wirksame Gewicht 0, außer die Einstellung "
            "„EDHREC-Gewichte mit Korpus behalten“ ist an. Das Ergebnis nennt die angewandte Regel."
        )
    helps[f"weights.{strength.CORPUS_TUNED}"] = (
        "Anteil der Karte in den gezählten Decks der Brackets 4 und 5 (Zähler / Nenner steht in "
        "der Signalzeile). Bei kleinem Nenner zum Prior gezogen (empirisches Bayes). Nur für "
        "Commander mit lokalem Korpus."
    )
    helps[f"weights.{strength.CORPUS_LOG_LIFT}"] = (
        "Wie viel häufiger die Karte im Korpus dieses Commanders steht als in allen Decks "
        "(EDHREC „Aufnahme überhaupt“): log10 des Verhältnisses, mit n / (n + "
        f"{strength.LOG_RATIO_DAMPING}) gedämpft (n = Decks mit der Karte), auf ±"
        f"{_number_text(strength.LOG_RATIO_CAP)} begrenzt (Faktor 100) und als (Wert + 2) / 4 auf "
        "0 bis 1 gelegt (0,5 = neutral); der Index zählt nur den Teil über neutral, max(0, 2·Wert - 1). "
        "Nur für Karten mit mindestens einem Treffer."
    )
    helps[f"weights.{strength.CORPUS_BRACKET_SLOPE}"] = (
        "Gefälle des Anteils zwischen den Brackets 4+5 und Bracket 2 im Korpus: log10 des "
        "Verhältnisses, wie beim Lift gedämpft und begrenzt; der Index zählt nur den Teil über "
        f"neutral. Nur ab {strength.SLOPE_MIN_HITS} Treffern insgesamt."
    )
    helps[f"weights.{strength.TOURNAMENT}"] = (
        "EDHTop16-Spielrate (Turnierzeitraum, Nenner = Einträge des Commanders) und Anteil im "
        "Korpus-Bracket 5 als ein Signal: die Zähler und Nenner beider Quellen werden "
        "zusammengelegt (Anteil = Summe Zähler / Summe Nenner), danach wie jeder kleine Nenner "
        "zum Prior gezogen. Eine Karte ohne EDHTop16-Zeile zählt nur mit dem Korpus-Bracket 5."
    )
    helps[f"weights.{strength.TOURNAMENT_LISTS}"] = (
        "TopDeck-Turnierlisten des Commanders: derzeit nur wenige Listen (Mindest-Nenner nicht "
        "erreicht). Standardmäßig 0, die Spalte bleibt."
    )
    helps[f"weights.{strength.EDHREC_THEME_REACH}"] = (
        "Höchster Anteil der Karte über die EDHREC-Themen des Commanders (nur Themen mit "
        "mindestens dem Mindest-Nenner EDHREC an Decks), mit dem Thema und seinem Zähler und "
        "Nenner in der Signalzeile. Ein Maximum über viele Themen ist nach oben verzerrt; "
        "deshalb nur ein kleines Gewicht."
    )
    helps[f"weights.{strength.GLOBAL_INCLUSION}"] = (
        "Anteil der Karte in allen EDHREC-Decks, unabhängig vom Commander. 0 schaltet ab."
    )
    helps[f"weights.{strength.COMBOS}"] = (
        "Je nach „Combo-Quelle“ zählt EDHREC-Kombos des Commanders (Standard: wie viele Decks "
        "dieses Commanders die Karte in Kombinationen spielen) oder Commander Spellbook "
        "(Qualitäts-Mix aus distinkten Combo-Shells beim Commander, falls importiert, sonst aus "
        "globalen Varianten über alle Commander). 0 schaltet das Signal ab."
    )
    labels["bracket"] = (
        "Bracket-Signal (empfohlen: upgraded, passend zum Bracket 3; bei Turnierausrichtung cedh)"
    )
    helps["bracket"] = "Welche Bracket-Seite von EDHREC als Bracket-Signal zählt."
    labels["combo_source"] = f"Combo-Quelle (empfohlen: {_COMBO_SOURCE_CHOICES[rec.combo_source]})"
    helps["combo_source"] = (
        "„EDHREC-Kombos des Commanders“ nutzt die beim Commander gezählten Combo-Decks "
        "(commander-spezifisch). „Commander Spellbook“ nutzt für diesen Commander importierte "
        "Combo-Shells (distinkte Combos in Farbidentität und Pool); fehlen Shells für diesen "
        "Commander, greift es auf den globalen Mix aus Varianten, 2-Karten-Varianten und "
        "vorhandenen Partnern zurück. Allein ohne eigenes Commander-Signal genügt Spellbook "
        "weiterhin nicht."
    )
    labels["rank_group"] = (
        f"Vergleichsgruppe für den Rang (empfohlen: {_GROUP_CHOICES[rec.rank_group]})"
    )
    helps["rank_group"] = (
        "Gegen welche Karten der Rang berechnet wird. Eine Gruppe mit weniger als "
        f"{strength.MIN_GROUP} Karten mit Wert fällt auf den ganzen Pool zurück "
        "(steht dann in der Signalzeile). „Gleiche Funktion“ vergleicht innerhalb der "
        "belegten Rollen der Karte (card_role): eine Karte mit mehreren Rollen zählt in "
        "jeder ihrer Rollengruppen, ihr Rang ist der Mittelwert daraus. Gruppen unter "
        "der Mindestgröße zählen beim Mittelwert nicht mit. Eine Karte ohne "
        "belegte Rolle fällt auf den ganzen Pool zurück und sagt das in der Signalzeile."
    )
    labels["separate_lands"] = (
        f"Länder getrennt von Zaubern ranken (empfohlen: {'an' if rec.separate_lands else 'aus'})"
    )
    helps["separate_lands"] = (
        "an: Länder werden nur mit Ländern und Zauber nur mit Zaubern verglichen. Der "
        "Anteil relativ zum Maximum (und jeder Rang) wird in den beiden Gruppen „Länder“ "
        "und „Zauber“ getrennt berechnet; die Stufen-Grenzen sind für beide gleich. So legt "
        "Command Tower den Maßstab nicht für die Zauber fest und umgekehrt. aus: ein "
        "gemeinsamer Vergleich über den ganzen Pool. Eine Gruppe mit weniger als "
        f"{strength.MIN_GROUP} Karten mit Wert bleibt im gemeinsamen Vergleich (steht in der "
        "Signalzeile). Standardländer und der Commander bekommen weiterhin keine Stufe."
    )
    labels["share_measure"] = (
        f"Anteil messen als (empfohlen: {_MEASURE_CHOICES[rec.share_measure]})"
    )
    helps["share_measure"] = (
        "Die Wilson-Untergrenze ordnet Karten mit verschieden großen Nennern vorsichtiger; "
        "bei gleichem Nenner ändert sie die Reihenfolge nicht. Anteile mit einem Nenner unter "
        f"{strength.EB_MAX_DENOMINATOR} werden stattdessen zum Prior der Komponente gezogen "
        "(empirisches Bayes: Beta-Binomial-Mittel, Prior-Mittel und -Stärke aus dem Pool nach "
        f"der Momentenmethode, Stärke begrenzt auf {strength.EB_STRENGTH_MIN:g} bis "
        f"{strength.EB_STRENGTH_MAX:g}); das Ergebnis nennt beide. Gegen kleine Stichproben "
        "schützt zusätzlich der Mindest-Nenner. Bei „roher Anteil“ gibt es keine Schrumpfung."
    )
    labels["share_scale"] = f"Anteil skalieren als (empfohlen: {_SCALE_CHOICES[rec.share_scale]})"
    helps["share_scale"] = (
        "Wie Anteils-Signale in einen Wert von 0 bis 1 umgerechnet werden. „Anteil (Logarithmus "
        f"relativ zum Maximum)“ (Standard) rechnet ln(1 + k·Anteil) / ln(1 + k·Maximalanteil) "
        f"mit k = {strength.LOG_SHARE_K:g} in der Vergleichsgruppe: seltene Karten bleiben "
        "sichtbar über null, die Spitze wird abgeflacht. „Anteil (Wurzel relativ zum Maximum)“ "
        "nimmt √(Anteil / Maximalanteil). „Rang (Perzentil)“ nutzt nur die Reihenfolge und drückt "
        "lange Null-Schwänze nach oben. Synergie, Kombos und Playgroup bleiben immer auf "
        "Perzentil-Rängen."
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
    labels["min_denominators.playgroup"] = (
        f"Mindest-Nenner Playgroup (empfohlen: {rec.min_denominators['playgroup']} Partien)"
    )
    helps["min_denominators.playgroup"] = (
        "Liegt die Stichprobe (Partien, in denen die Karte gewirkt wurde) unter dem Minimum, "
        "zählt das Playgroup-Signal im Index für diese Karte nicht. 0 = nur Import-Minimum "
        f"({strength.OBSERVED_MIN_SAMPLE} Partien)."
    )
    for key in strength.MISSING_CAPABLE:
        labels[f"missing_value.{key}"] = (
            f"Fehlender Wert bei „{strength.LABELS[key]}“ "
            f"(empfohlen: {_MISSING_CHOICES[rec.missing_value[key]]})"
        )
        helps[f"missing_value.{key}"] = (
            "auslassen (empfohlen, Owner-Entscheidung E4.b): eine nicht gelistete Karte ist eine "
            "fehlende Beobachtung („nicht gelistet“), nie eine Null; ihr Gewicht entfällt und der "
            "Index mittelt über die übrigen Signale. Eine GEZÄHLTE Null (0 von N Decks im "
            "vollständig gezählten Korpus) ist dagegen ein Befund und zählt immer voll. "
            "als niedrigster Rang: eine nicht gelistete Karte zählt mit dem Wert 0, also bei "
            "oder unter der kleinsten gelisteten Karte, nie darüber. Nur sinnvoll, wenn die Quelle "
            "alle Karten über ihrer Listenschwelle nennt (EDHREC): nicht gelistet heißt darunter."
        )
    labels["rank_commander_and_basics"] = (
        "Commander und Standardländer bewerten "
        f"(empfohlen: {'an' if rec.rank_commander_and_basics else 'aus'})"
    )
    helps["rank_commander_and_basics"] = (
        "aus: der Commander und die Standardländer bekommen keine Stufe "
        "(„nicht bewertet“) und nehmen keinen Rang weg."
    )
    labels["rank_other_commanders"] = (
        "Andere Commander-Karten im Pool ranken "
        f"(empfohlen: {'ja' if rec.rank_other_commanders else 'nein'})"
    )
    helps["rank_other_commanders"] = (
        "ja: eine Karte, die im Studio selbst ein Commander ist, aber für diesen Commander "
        "ein legales Deckmitglied, wird wie jede andere Karte bewertet. nein: sie bekommt "
        "keine Stufe („nicht bewertet, anderer Commander“) und nimmt keinen Rang weg."
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
        "Universum, Synergie, Turnierlisten oder EDHREC-Kombos). „Aufnahme überhaupt“, "
        "Spellbook-Kombos und die Playgroup-Beobachtung gelten für jeden Commander und "
        "reichen allein nicht: die Karte bleibt „zu wenig Daten“."
    )
    labels["zero_count_tier"] = (
        f"Stufe bei nur gezählten Nullen (empfohlen: {_ZERO_TIER_CHOICES[rec.zero_count_tier]})"
    )
    helps["zero_count_tier"] = (
        "Eine Karte, deren einziger Beleg zu diesem Commander gezählte Nullen sind (0 von N Decks "
        "im vollständig gezählten Korpus) und die sonst nur ein commanderunabhängiges Signal hat. "
        "Stufe D (E4.b, empfohlen): die Null ist ein Befund und zählt voll. U (E4.a): zu wenig "
        "Daten, Grund ZERO_COUNT_ONLY."
    )
    labels["edhrec_with_corpus"] = (
        "EDHREC-Gewichte mit Korpus behalten "
        f"(empfohlen: {_EDHREC_WITH_CORPUS_CHOICES[rec.edhrec_with_corpus]})"
    )
    helps["edhrec_with_corpus"] = (
        "Regel E2.a: Gibt es für den Commander einen gezählten lokalen Korpus mit mindestens "
        f"{universe_minimum} Decks, sind die Gewichte „Aufnahme beim Commander“ und „Aufnahme im "
        "Bracket“ wirksam 0 (aus). Ohne Korpus gelten sie wie eingestellt (Rückfall). An: sie "
        "gelten auch mit Korpus."
    )
    labels["min_coverage"] = (
        f"Mindest-Datenlage in % (empfohlen: {_number_text(round(rec.min_coverage * 100, 1))})"
    )
    helps["min_coverage"] = (
        "Anteil des Gewichts der Signale, die zu dieser Karte einen Wert haben. Darunter steht "
        "„zu wenig Daten“. Das ist keine Schwelle für den Anteil in Decks."
    )
    labels["borderline_distance"] = (
        f"Grenzwertig-Abstand in Punkten (empfohlen: {_number_text(rec.borderline_distance)})"
    )
    helps["borderline_distance"] = (
        "Liegt der Index einer Karte näher als dieser Abstand an einer Tier-Grenze, trägt sie die "
        "Markierung „grenzwertig“: eine kleine Änderung der Gewichte kann ihre Stufe ändern. 0 "
        "schaltet die Markierung aus."
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
        {"title": "Bracket", "keys": ["bracket", "combo_source"]},
        {"title": "Vergleichsgruppe für den Rang", "keys": ["rank_group", "separate_lands"]},
        {"title": "Anteil messen als", "keys": ["share_measure", "share_scale"]},
        {
            "title": "Mindest-Nenner je Signal",
            "keys": [
                "min_denominators.edhrec",
                "min_denominators.deck_universe",
                "min_denominators.tournament",
                "min_denominators.playgroup",
            ],
        },
        {
            "title": "Fehlender Wert",
            "keys": [f"missing_value.{key}" for key in strength.MISSING_CAPABLE],
        },
        {"title": "Decklisten-Universum", "keys": ["universe_source", "edhrec_with_corpus"]},
        {"title": "Commander und Standardländer", "keys": ["rank_commander_and_basics"]},
        {"title": "Andere Commander im Pool", "keys": ["rank_other_commanders"]},
        {
            "title": "Mindestdaten für eine Stufe",
            "keys": [
                "min_coverage",
                "min_components",
                "require_commander_signal",
                "zero_count_tier",
            ],
        },
        {
            "title": (
                "Tier-Grenzen (empfohlen: "
                + " / ".join(_number_text(cuts[tier]) for tier in ("S", "A", "B", "C"))
                + ")"
            ),
            "keys": [
                *(f"tier_cuts.{tier}" for tier in ("S", "A", "B", "C")),
                "borderline_distance",
            ],
        },
    ]
    return {
        "labels": labels,
        "help": helps,
        "groups": groups,
        "choices": {
            "bracket": _choices(_BRACKET_CHOICES, rec.bracket),
            "combo_source": _choices(_COMBO_SOURCE_CHOICES, rec.combo_source),
            "rank_group": _choices(_GROUP_CHOICES, rec.rank_group),
            "share_measure": _choices(_MEASURE_CHOICES, rec.share_measure),
            "share_scale": _choices(_SCALE_CHOICES, rec.share_scale),
            **{
                f"missing_value.{key}": _choices(_MISSING_CHOICES, rec.missing_value[key])
                for key in strength.MISSING_CAPABLE
            },
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
            "zero_count_tier": _choices(_ZERO_TIER_CHOICES, rec.zero_count_tier),
            "edhrec_with_corpus": [
                {
                    "value": value,
                    "label": f"{label} (empfohlen)" if value == rec.edhrec_with_corpus else label,
                    "recommended": value == rec.edhrec_with_corpus,
                }
                for value, label in _EDHREC_WITH_CORPUS_CHOICES.items()
            ],
            "separate_lands": [
                {"value": True, "label": "an (empfohlen)", "recommended": True},
                {"value": False, "label": "aus", "recommended": False},
            ],
            "rank_commander_and_basics": [
                {"value": False, "label": "aus (empfohlen)", "recommended": True},
                {"value": True, "label": "an", "recommended": False},
            ],
            "rank_other_commanders": [
                {"value": True, "label": "ja (empfohlen)", "recommended": True},
                {"value": False, "label": "nein", "recommended": False},
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
            {
                "key": key,
                "label": strength.LABELS[key],
                "default_weight": weight,
                "data_class": strength.COMPONENT_DATA_CLASS[key],
                "commander_only": key in strength.COMMANDER_ONLY_SOURCES,
            }
            for key, weight in strength.DEFAULT_WEIGHTS.items()
        ],
        "brackets": [*strength.BRACKETS, strength.BRACKET_NONE],
        "defaults": recommended,
        "recommended": recommended,
        "missing_capable": list(strength.MISSING_CAPABLE),
        "edhrec_rule_components": list(strength.EDHREC_RULE_COMPONENTS),
        "log_share_k": strength.LOG_SHARE_K,
        "empirical_bayes": {
            "max_denominator": strength.EB_MAX_DENOMINATOR,
            "strength_range": [strength.EB_STRENGTH_MIN, strength.EB_STRENGTH_MAX],
            "min_cards": strength.EB_MIN_CARDS,
        },
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
    "compute_with_snapshot",
    "delete_profile",
    "get_profile",
    "list_profiles",
    "presets",
    "profile_notices",
    "resolve_settings",
    "save_profile",
    "signal_coverage",
]
