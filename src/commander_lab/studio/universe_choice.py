"""Which deck universe the strength index (and the builder) counts with.

Counted prevalence must not become a tier by default: the recommended ``universe_source`` is
``profile`` (a selected stored profile, else no universe); ``auto`` and the counted universes
are explicit options.

Three sources can give the deck-universe component its counts, never two at once:

- a stored universe profile over the deck lists imported into the store (``universe.py``),
- all local deck lists of the commander (an unfiltered profile, made on the fly),
- a counted deck-list universe imported as a signal (``decklist_universe:<source>:<bracket>``,
  see ``signals.py``): complete deck lists that were counted elsewhere and delivered as counts.

``choose`` is the one place that decides, from the ``universe_source`` setting:

- ``auto``: a selected stored profile; else the local deck lists of the commander when there
  are at least ``min_universe`` of them; else the counted universe whose bracket matches the
  bracket setting (core 2, upgraded 3, optimized 4, cedh 5), the larger denominator first;
  else, without a matching bracket (setting ``none`` or no such universe), the counted universe
  with the largest denominator; else none.
- ``profile``: the selected stored profile (none when no profile is selected).
- ``counted:<source>:<bracket>``: exactly that counted universe (none when it is not stored).
- ``none``: no universe.

Counted universes are read for ONE commander only. The builder asks the same function.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from . import signals, strength, universe_view
from .store import StudioStore
from .tiers import TierParams
from .universe import UniverseSpec, resolve_universe
from .universe_view import ProfileSummary, filtered_spec

KIND_PROFILE = "profile"
KIND_LOCAL = "local"
KIND_COUNTED = "counted"
KIND_NONE = "none"

BRACKET_NUMBER = {"core": "2", "upgraded": "3", "optimized": "4", "cedh": "5"}
_BRACKET_NAMES = {
    "core": "Core",
    "upgraded": "Upgraded",
    "optimized": "Optimized",
    "cedh": "cEDH",
}
_SOURCE_NAMES = {"edhrec": "EDHREC", "archidekt": "Archidekt", "moxfield": "Moxfield"}


class CountedUniverse(TypedDict):
    signal: str
    value: str  # the ``universe_source`` value that selects it
    source: str
    bracket: str
    denominator: int
    snapshot_id: str
    rows: int
    label: str


class UniverseChoice(TypedDict):
    """The universe a calculation used and why. Counts and names only."""

    kind: str  # profile | local | counted | none
    requested: str  # the universe_source setting
    automatic: bool
    label: str
    reason: str
    denominator: int
    snapshot_id: str
    profile: str | None
    counted: str  # the ``counted:<source>:<bracket>`` value, else ""
    source: str
    bracket: str


def source_name(source: str) -> str:
    return _SOURCE_NAMES.get(source, source)


def counted_label(source: str, bracket: str, denominator: int) -> str:
    return (
        f"Gezählte Decklisten (Repo): {source_name(source)}, Bracket {bracket}, {denominator} Decks"
    )


def counted_universes(store: StudioStore, commander: str) -> list[CountedUniverse]:
    """The counted universes stored for ``commander`` (and only for it), by source and bracket.

    The denominator is the one the import verified for the universe; the snapshot id is the
    one of the file, kept in the title of the universe's source row."""
    rows = store.connection.execute(
        "SELECT c.signal AS signal, COUNT(*) AS rows, MAX(c.denominator) AS denominator, "
        "MIN(s.title) AS title FROM card_signal c JOIN source s USING (source_id) "
        "WHERE c.commander_name = ? AND c.signal LIKE ? GROUP BY c.signal ORDER BY c.signal",
        (commander, f"{signals.SIGNAL_DECKLIST}:%"),
    ).fetchall()
    found: list[CountedUniverse] = []
    for row in rows:
        parts = str(row["signal"]).split(":")
        if len(parts) != 3 or row["denominator"] is None or int(row["denominator"]) <= 0:
            continue
        source, bracket, total = parts[1], parts[2], int(row["denominator"])
        snapshot = str(row["title"]).rpartition("#")[2] if "#" in str(row["title"]) else ""
        found.append(
            {
                "signal": str(row["signal"]),
                "value": f"{strength.UNIVERSE_COUNTED}:{source}:{bracket}",
                "source": source,
                "bracket": bracket,
                "denominator": total,
                "snapshot_id": snapshot or f"counted:{source}:{bracket}:{total}",
                "rows": int(row["rows"]),
                "label": counted_label(source, bracket, total),
            }
        )
    found.sort(key=lambda item: (item["source"], item["bracket"]))
    return found


def _largest(universes: Sequence[CountedUniverse]) -> CountedUniverse:
    return max(universes, key=lambda item: (item["denominator"], item["source"], item["bracket"]))


def pick_counted(
    universes: Sequence[CountedUniverse], bracket_setting: str
) -> tuple[CountedUniverse, bool] | None:
    """The counted universe the automatic choice takes, and whether its bracket matched the
    bracket setting. ``None`` without any counted universe."""
    if not universes:
        return None
    number = BRACKET_NUMBER.get(bracket_setting)
    matching = [item for item in universes if item["bracket"] == number]
    if matching:
        return _largest(matching), True
    return _largest(universes), False


def local_spec(store: StudioStore, commander: str) -> UniverseSpec:
    """The unfiltered universe of the commander's own decks."""
    return filtered_spec(store, [], commander_names=[commander])


def local_deck_count(store: StudioStore, commander: str) -> int:
    """Decks of the commander the unfiltered local universe counts (deduplicated)."""
    return len(resolve_universe(store, local_spec(store, commander)))


def _choice(
    kind: str,
    requested: str,
    *,
    label: str,
    reason: str,
    denominator: int = 0,
    snapshot: str = "",
    profile: str | None = None,
    counted: CountedUniverse | None = None,
) -> UniverseChoice:
    return {
        "kind": kind,
        "requested": requested,
        "automatic": requested == strength.UNIVERSE_AUTO,
        "label": label,
        "reason": reason,
        "denominator": denominator,
        "snapshot_id": snapshot,
        "profile": profile,
        "counted": counted["value"] if counted else "",
        "source": counted["source"] if counted else "",
        "bracket": counted["bracket"] if counted else "",
    }


def _from_counted(requested: str, item: CountedUniverse, reason: str) -> UniverseChoice:
    return _choice(
        KIND_COUNTED,
        requested,
        label=item["label"],
        reason=reason,
        denominator=item["denominator"],
        snapshot=item["snapshot_id"],
        counted=item,
    )


def _from_profile(requested: str, summary: ProfileSummary, reason: str) -> UniverseChoice:
    return _choice(
        KIND_PROFILE,
        requested,
        label=f"Universum {summary['profile']}",
        reason=reason,
        denominator=summary["denominator"],
        snapshot=summary["snapshot_id"],
        profile=summary["profile"],
    )


def choose(
    store: StudioStore,
    commander: str,
    settings: strength.StrengthSettings,
    summary: ProfileSummary | None,
) -> UniverseChoice:
    """The universe for ``settings``. ``summary`` is the summary of the selected stored profile
    (``None`` when none is selected or it no longer exists)."""
    requested = settings.universe_source
    kind, source, bracket = strength.parse_universe_source(requested) or ("", "", "")
    counted = counted_universes(store, commander)
    if kind == strength.UNIVERSE_NONE:
        return _choice(
            KIND_NONE, requested, label="kein Decklisten-Universum", reason="abgeschaltet"
        )
    if kind == strength.UNIVERSE_PROFILE:
        if summary is None:
            return _choice(
                KIND_NONE,
                requested,
                label="kein Decklisten-Universum",
                reason="kein gespeichertes Universum gewählt",
            )
        return _from_profile(requested, summary, "von dir gewählt")
    if kind == strength.UNIVERSE_COUNTED:
        for item in counted:
            if item["source"] == source and item["bracket"] == bracket:
                return _from_counted(requested, item, "von dir gewählt")
        return _choice(
            KIND_NONE,
            requested,
            label="kein Decklisten-Universum",
            reason=f"gezählte Decklisten {source}, Bracket {bracket} sind nicht gespeichert",
        )
    if summary is not None:
        return _from_profile(requested, summary, "automatisch gewählt: gespeichertes Universum")
    minimum = TierParams().min_universe
    local = local_deck_count(store, commander)
    if local >= minimum:
        return _choice(
            KIND_LOCAL,
            requested,
            label=f"Alle {local} lokalen Decklisten dieses Commanders",
            reason=(f"automatisch gewählt: {local} lokale Decklisten (mindestens {minimum} nötig)"),
            denominator=local,
            snapshot=universe_view.spread_for_spec(
                store, local_spec(store, commander), [], commander_names=[commander]
            )[1],
        )
    picked = pick_counted(counted, settings.bracket)
    if picked is None:
        why = (
            f"nur {local} lokale Decklisten (mindestens {minimum} nötig) "
            "und keine gezählten Decklisten importiert"
        )
        return _choice(KIND_NONE, requested, label="kein Decklisten-Universum", reason=why)
    item, matched = picked
    if matched:
        reason = (
            "automatisch gewählt: gezählte Decklisten passend zum Bracket-Signal "
            f"({_BRACKET_NAMES.get(settings.bracket, settings.bracket)}), "
            "größter Nenner"
        )
    else:
        reason = (
            "automatisch gewählt: gezählte Decklisten mit dem größten Nenner "
            "(kein Universum zum Bracket-Signal)"
        )
    return _from_counted(requested, item, reason)


__all__ = [
    "BRACKET_NUMBER",
    "KIND_COUNTED",
    "KIND_LOCAL",
    "KIND_NONE",
    "KIND_PROFILE",
    "CountedUniverse",
    "UniverseChoice",
    "choose",
    "counted_label",
    "counted_universes",
    "local_deck_count",
    "local_spec",
    "pick_counted",
    "source_name",
]
