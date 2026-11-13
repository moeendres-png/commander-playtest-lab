"""One reading of "how often is this card played in this commander's decks" (EDHREC inclusion).

Two stores hold that figure. ``card_signal`` is filled by ``import-signals`` (per commander and
card: decks with the card over decks of the commander, with its source file); the older
``observation`` rows are filled by the EDHREC page importers. Every view that shows the figure
(the tier list column and drawer, the builder table and the builder sort) reads it through
``commander_inclusion`` so none of them can say "no observation" while another shows a value.

A figure always names its origin: ``source`` is ``card_signal`` or ``observation``, with the
registered source id and the capture date (when the source file was imported) for a signal row.
A card without any row is absent from the result: unknown, never 0. A signal row whose value
could not be read (no numerator or denominator) is unknown too and falls back to the
observation rows.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from .builder import SMALL_DENOMINATOR, bound_to
from .store import StudioStore

SIGNAL = "edhrec_commander_inclusion"
FROM_SIGNAL = "card_signal"
FROM_OBSERVATION = "observation"


class InclusionFigure(TypedDict):
    pct: float
    numerator: int | None
    denominator: int | None
    small_denominator: bool
    source: str
    source_id: str | None
    captured_at: str | None
    page: str


def _front(name: str) -> str:
    return name.split(" // ")[0].strip()


def card_name_map(store: StudioStore) -> dict[str, str]:
    """Casefolded card name -> card id over the whole collection; a name that two cards
    claim (a shared front face) is dropped, so a figure is never attached to a guess."""
    claims: dict[str, set[str]] = {}
    for row in store.connection.execute("SELECT card_id, oracle_name, engine_name FROM card_fact"):
        for name in (row["oracle_name"], row["engine_name"]):
            if not name:
                continue
            for key in (str(name), _front(str(name))):
                if key:
                    claims.setdefault(key.casefold(), set()).add(str(row["card_id"]))
    return {key: next(iter(ids)) for key, ids in claims.items() if len(ids) == 1}


def _from_signal(store: StudioStore, commander: str) -> dict[str, InclusionFigure]:
    by_name = card_name_map(store)
    found: dict[str, InclusionFigure] = {}
    for row in store.connection.execute(
        "SELECT s.card_name, s.value, s.numerator, s.denominator, s.source_id, "
        "r.imported_at FROM card_signal s LEFT JOIN source r ON r.source_id = s.source_id "
        "WHERE s.commander_name = ? AND s.signal = ?",
        (commander, SIGNAL),
    ):
        card_id = by_name.get(str(row["card_name"]).casefold())
        if card_id is None or card_id in found or row["value"] is None:
            continue
        denominator = row["denominator"]
        found[card_id] = {
            "pct": 100.0 * float(row["value"]),
            "numerator": row["numerator"],
            "denominator": denominator,
            "small_denominator": denominator is not None and denominator < SMALL_DENOMINATOR,
            "source": FROM_SIGNAL,
            "source_id": str(row["source_id"]),
            "captured_at": None if row["imported_at"] is None else str(row["imported_at"]),
            "page": "commander",
        }
    return found


def _from_observations(
    store: StudioStore, commander_names: Sequence[str]
) -> dict[str, InclusionFigure]:
    cohort_bound, cohort_args = bound_to("observation_cohort", "o.cohort", commander_names)
    found: dict[str, InclusionFigure] = {}
    for row in store.connection.execute(
        "SELECT o.card_id, o.cohort, o.value, o.numerator, o.denominator, o.snapshot, "
        "o.source_id FROM observation o "
        f"WHERE o.metric = 'inclusion_pct' AND o.card_id IS NOT NULL{cohort_bound} "
        "ORDER BY o.denominator DESC",
        cohort_args,
    ):
        card_id = str(row["card_id"])
        if card_id in found or row["value"] is None:
            continue
        denominator = row["denominator"]
        found[card_id] = {
            "pct": float(row["value"]),
            "numerator": row["numerator"],
            "denominator": denominator,
            "small_denominator": denominator is not None and denominator < SMALL_DENOMINATOR,
            "source": FROM_OBSERVATION,
            "source_id": None if row["source_id"] is None else str(row["source_id"]),
            "captured_at": row["snapshot"] or None,
            "page": str(row["cohort"]).removeprefix("edhrec:"),
        }
    return found


def commander_inclusion(
    store: StudioStore, commander_names: Sequence[str]
) -> dict[str, InclusionFigure]:
    """EDHREC inclusion per card id for the named commander(s).

    ``card_signal`` wins where it has a readable value (it carries the exact decks counts of
    the imported commander page); other cards fall back to the observation rows bound to the
    commander (the widest denominator first). Signals are stored per single commander name, so
    a pair of commanders reads observations only. No commander: nothing."""
    if not commander_names:
        return {}
    figures = _from_observations(store, commander_names)
    if len(commander_names) == 1:
        figures.update(_from_signal(store, commander_names[0]))
    return figures


__all__ = [
    "FROM_OBSERVATION",
    "FROM_SIGNAL",
    "InclusionFigure",
    "card_name_map",
    "commander_inclusion",
]
