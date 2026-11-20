"""The rubric v2 field of the strength answer: "Kartenverständnis (Modellurteil)" (Q1-b3, #1678).

Owner decision E15 Q1 removed the overall rating v1; rubric v2 stays as a model judgement for
Chulane only (Co-Lead decision E5, #1665). This module adds ONE top-level field,
``kartenverstaendnis``, to an answer of ``POST /api/strength`` (live or from a snapshot). Every
other field of the answer is returned unchanged and the given answer is not modified.

* Only for the commander the data set belongs to (``card_understanding.DATASET_COMMANDER``). For
  any other commander the field is absent: nothing was rated there, so nothing is shown.
* Only for the cohort the raters judged for: Bracket 3, the setting "upgraded". For another
  bracket, and when the data file is missing or broken, the field says ``verfuegbar: false``
  with the reason; the route never fails over it.
* Per rated card one contract object of the number contract (B3, ``number_contract``) with the
  class ``URTEIL``: the rater's score H (overall value of the card, 0 to 100). A card the data set
  does not list gets no object: it is "unbekannt", never 0. The object carries its origin
  (rubric, version, rater tier and number of raters) and the rater's self-reported confidence.
* The coverage (rated cards of the pool, n of N) is a plain count beside the figures, never a
  figure of the judgement column; judgement and counted figures are never mixed.

No weights, no mean, no rank: the scores are a model rater's reading of the rules text, not a
measurement, never carry price, popularity or a played-game result, and are not validated
against game results.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from . import card_understanding, number_contract
from .card_understanding import UnderstandingRow
from .store import StudioStore

FIELD: Final = "kartenverstaendnis"
NAME: Final = "Kartenverständnis (Modellurteil)"
CRITERION: Final = "H"
CRITERION_NAME: Final = "Gesamtwert"
RATER_BRACKET: Final = "upgraded"  # Bracket 3, the cohort the raters judged for
ID_PREFIX: Final = "kartenverstaendnis:"
NOT_VALIDATED: Final = "nicht gegen Spielergebnisse validiert"


def cohort() -> str:
    """The cohort the raters judged for (the data set's commander, read at call time)."""
    return f"{card_understanding.DATASET_COMMANDER} · Bracket 3 (Annahme der Rater)"


def _origin(rows: Mapping[str, UnderstandingRow], matched: int) -> dict[str, object]:
    tiers: dict[str, int] = {}
    for row in rows.values():
        tiers[row["rater_tier"]] = tiers.get(row["rater_tier"], 0) + 1
    return {
        "version": card_understanding.DATASET_VERSION,
        "rubric": card_understanding.DATASET_RUBRIC,
        "commander": card_understanding.DATASET_COMMANDER,
        "rows": len(rows),
        "matched": matched,
        "rater_tiers": dict(sorted(tiers.items())),
    }


def _unavailable(reason: str, n_total: int) -> dict[str, object]:
    return {
        "verfuegbar": False,
        "grund": reason,
        "name": NAME,
        "kriterium": CRITERION,
        "n_bewertet": 0,
        "n_gesamt": n_total,
        "herkunft": None,
        "zahlen": [],
    }


def card_figure(card_id: str, row: UnderstandingRow) -> dict[str, object]:
    """The contract object (class URTEIL) of one rated card."""
    raters = int(row.get("raters", 1))
    rater_text = "1 Bewerter" if raters == 1 else f"{raters} Bewerter"
    return number_contract.zahl(
        f"{ID_PREFIX}{card_id}",
        f"{CRITERION} {CRITERION_NAME} (0 bis 100)",
        float(row["scores"][CRITERION]),
        klasse=number_contract.URTEIL,
        einheit="Punkte",
        quelle=(
            f"Rubrik {row['version']} ({row['rubric']}), Modell-Rater Stufe "
            f"{row['rater_tier']}, {rater_text}"
        ),
        kohorte=cohort(),
        hinweise=[f"Rater-Vertrauen {row['confidence']} (Selbstauskunft)", NOT_VALIDATED],
    )


def _oracle_ids(store: StudioStore, card_ids: Sequence[str]) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for start in range(0, len(card_ids), 500):
        chunk = list(card_ids[start : start + 500])
        marks = ",".join("?" for _ in chunk)
        for card_id, oracle_id in store.connection.execute(
            f"SELECT card_id, oracle_id FROM card WHERE card_id IN ({marks})",
            chunk,
        ):
            found[str(card_id)] = str(oracle_id) if oracle_id else None
    return found


def with_understanding(
    store: StudioStore,
    answer: Mapping[str, object],
    *,
    dataset: Mapping[str, UnderstandingRow] | None = None,
) -> dict[str, object]:
    """``answer`` plus the field ``kartenverstaendnis`` (only for the data set's commander)."""
    out: dict[str, object] = dict(answer)
    commander = card_understanding.DATASET_COMMANDER
    if str(answer.get("commander", "")).strip().casefold() != commander.casefold():
        return out
    raw_cards = answer.get("cards")
    cards = (
        [card for card in raw_cards if isinstance(card, dict)]
        if isinstance(raw_cards, list)
        else []
    )
    n_total = len(cards)
    settings = answer.get("settings")
    bracket = settings.get("bracket") if isinstance(settings, dict) else None
    if bracket != RATER_BRACKET:
        out[FIELD] = _unavailable(
            "Kartenverständnis gilt für Bracket 3 (Einstellung „upgraded“), "
            f"die Anfrage nutzt {bracket!r}",
            n_total,
        )
        return out
    try:
        rows = card_understanding.load() if dataset is None else dataset
    except card_understanding.UnderstandingDataError as error:
        out[FIELD] = _unavailable(
            str(error)
            if isinstance(error, card_understanding.DatasetNotFoundError)
            else f"Datensatz Kartenverständnis nicht lesbar: {error}",
            n_total,
        )
        return out
    ids = [str(card["card_id"]) for card in cards]
    oracle = _oracle_ids(store, ids)
    figures: list[dict[str, object]] = []
    for card_id in ids:
        oracle_id = oracle.get(card_id)
        row = rows.get(oracle_id) if oracle_id else None
        if row is not None:
            figures.append(card_figure(card_id, row))
    matched = len({oid for oid in oracle.values() if oid in rows})
    out[FIELD] = {
        "verfuegbar": True,
        "grund": None,
        "name": NAME,
        "kriterium": CRITERION,
        "n_bewertet": len(figures),
        "n_gesamt": n_total,
        "herkunft": _origin(rows, matched),
        "zahlen": figures,
    }
    return out
