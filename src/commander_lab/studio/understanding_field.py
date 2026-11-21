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

WP-6 (#1404, builder audit T1 to T5) adds, all additively and without touching the index:

* ``streuung``: the measured spread of one rating (one run per card), with its sources and n;
  the figures keep ``intervall: null`` (a typical spread is no measured per-card interval).
* ``abdeckung``: n of N pool cards with a value, per criterion E, F, T, R, K, D, H.
* ``pruefer_zweifel``: the cards the blind rating audit doubts (Audit A), with n placed of n
  flagged; a missing audit file is "nicht verfügbar", never "no card doubted".
* ``laender_skala``: lands were rated against land anchors, on a scale of their own; their ids
  and how many of them have T = 0, counted in this answer.

``card_detail`` gives one card's single ratings (all seven criteria, reason, notes, rules claims)
for the card window; for any commander but the data set's it gives nothing to show.

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
CLAIMS_HEADING: Final = (
    "Regelclaims des Raters (Modellurteil, keine Regelaussage; Regelautorität XMage/CR)"
)
CLAIMS_NOTE: Final = (
    "Zitate nicht einzeln geprüft (Audit A: 11 von 1708 Zitaten, 0,6 %, nicht wörtlich; Audit D: "
    "100 von 100 Stichproben-Claims richtig, in einer gezielten Sichtung ein Sachfehler beim "
    "Evoke-Opferfenster)"
)
NOT_STRENGTH: Final = (
    "Modellurteil aus dem Regeltext, keine Spielstärke; keine Stufe, kein Rang, nicht Teil des "
    "Stärke-Index"
)
CRITERIA_NAMES: Final[dict[str, str]] = {
    "E": "Effizienz",
    "F": "Passung zu Chulane",
    "T": "Wirkung am Tisch (drei Gegner)",
    "R": "Verlässlichkeit",
    "K": "Motor- und Kombo-Potenzial",
    "D": "Deck-Kosten und Risiko (100 = kein Risiko)",
    "H": "Gesamtwert",
}
RESEARCH: Final = "data/research/chulane_rubric_v2_20261118"
# The spread of ONE rating of H (one run per card), from the reports of the research folder. The
# figures are checked against the raw files by tests (drift: RMS of the 49 differences / sqrt 2;
# other model family: RMS of the 70 differences / sqrt 2; the audit's combined estimate is text).
SPREAD: Final[dict[str, object]] = {
    "kriterium": "H",
    "text": "typisch ± rund 5 bis 8 Punkte (1\u03c3), ein Lauf je Karte; je nach H-Bereich anders",
    "kurz": "±5\u20138",
    "unten": 5,
    "oben": 8,
    "einheit": "Punkte",
    "laeufe_je_karte": 1,
    "art": "typische Streuung eines Einzelwerts, kein gemessenes Intervall je Karte",
    # The spread grows with H. The bands are the audit's estimate (text of AUDIT_A §4, not
    # computable from paired ratings); a value outside every band shows the typical spread.
    "baender": [
        {
            "ab": 0,
            "bis": 10,
            "kurz": "±5",
            "text": "etwa ±5 bei H bis 10",
            "quelle": f"Schätzung Rating-Audit A §4 ({RESEARCH}/audit/AUDIT_A_ratings.md)",
        },
        {
            "ab": 40,
            "bis": 55,
            "kurz": "±10",
            "text": "etwa ±10 bei H 40 bis 55",
            "quelle": f"Schätzung Rating-Audit A §4 ({RESEARCH}/audit/AUDIT_A_ratings.md)",
        },
        {
            "ab": 60,
            "bis": 100,
            "kurz": "\u221215/+5",
            "text": "asymmetrisch etwa \u221215 bis +5 ab H 60 (hohe Werte eher zu hoch)",
            "quelle": f"Schätzung Rating-Audit A §4 ({RESEARCH}/audit/AUDIT_A_ratings.md)",
        },
    ],
    "quellen": [
        {
            "name": "Drift-Test: zweiter Lauf derselben Rater-Stufe",
            "kurzname": "Drift",
            "gemessen": True,
            "n": 49,
            "N": 922,
            "bezug": "Karten (zweimal bewertet / Datensatz)",
            "kennzahl": "mittlere |ΔH| 5,10; Wiederholstreuung etwa 5 (RMS 7,1 / √2)",
            "datei": f"{RESEARCH}/PILOT_REPORT.md §10; audit/AUDIT_A_ratings.md §4",
        },
        {
            "name": "Unabhängiger Rater aus einer anderen Modellfamilie",
            "kurzname": "anderer Rater",
            "gemessen": True,
            "n": 70,
            "N": 922,
            "bezug": "Karten (geschichtete Stichprobe / Datensatz)",
            "kennzahl": "mittlere |ΔH| 7,9; 13 von 70 mit |ΔH| ≥ 15; etwa 7,3 (RMS 10,4 / √2)",
            "datei": f"{RESEARCH}/PILOT_REPORT.md §11; audit/independent_rater_ratings.jsonl",
        },
        {
            "name": "Rating-Audit A (Schätzung aus der Prüfung, kein gepaartes \u03c3)",
            "kurzname": "Audit A",
            "gemessen": False,
            "n": 230,
            "N": 922,
            "bezug": "Karten (geprüft / Datensatz)",
            "kennzahl": (
                "Schätzung: 1\u03c3 etwa 7 bis 8 Punkte inklusive Fehler; Unterschiede unter 10 "
                "Punkten nicht belastbar"
            ),
            "datei": f"{RESEARCH}/audit/AUDIT_A_ratings.md §0, §4",
        },
    ],
}
LAND_SCALE_SOURCE: Final = f"Gutachten C §4 ({RESEARCH}/audit/GUTACHTEN_C_gesamtrating.md)"
LAND_SCALE_TEXT: Final = (
    "Länder-Skala: Länder sind gegen eigene Länder-Anker bewertet, auf einer eigenen Skala; ihr H "
    "ist nicht mit dem H von Zaubern vergleichbar"
)


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


# What the audit looked at: without a mark a card was either not checked or checked without
# finding. Counts from AUDIT_A_ratings.md §0/§1 (a test reads them there).
AUDIT_BASIS: Final[dict[str, object]] = {
    "n": 230,
    "N": 922,
    "ausserhalb": 6,
    "bezug": "Karten in den Stichproben des Audits (Spitze 100, Boden 60, Grenzbereich 70) / Datensatz",
    "text": (
        "Prüfbasis: 230 von 922 Karten geprüft (plus 6 Funde außerhalb der Stichproben); ohne "
        "Kennzeichen heißt nicht geprüft (692 von 922) oder geprüft ohne Befund"
    ),
}


def _claim_findings(
    rows: Mapping[str, UnderstandingRow],
) -> dict[str, list[dict[str, object]]]:
    """Audit D findings by ``oracle_id``; a finding whose card or claim the data set lacks is left
    out (it cannot be placed)."""
    by_name = {row["card"]: oracle_id for oracle_id, row in rows.items()}
    found: dict[str, list[dict[str, object]]] = {}
    for item in card_understanding.RULE_CLAIM_FINDINGS:
        oracle_id = by_name.get(item["card"])
        if oracle_id is None or item["index"] >= len(rows[oracle_id]["rule_claims"]):
            continue
        found.setdefault(oracle_id, []).append(
            {
                "index": item["index"],
                "urteil": item["verdict"],
                "kurz": f"Regelclaim laut Audit D {item['verdict']}",
                "korrektur": item["correction"],
                "quelle": card_understanding.AUDIT_D_SOURCE,
            }
        )
    return found


def _doubt_short(flag: card_understanding.AuditFlag) -> str:
    """The visible label: the reviewer is a model, and a wrong reason is no doubt about H."""
    if flag["kind"] == "Begründung faktisch falsch":
        return "Prüfer-Modell: Begründung faktisch falsch"
    return f"Prüfer-Modell bezweifelt H: {flag['kind'].removeprefix('H ')}"


def _doubt_text(flag: card_understanding.AuditFlag) -> str:
    low, high = flag["proposed_H_low"], flag["proposed_H_high"]
    span = (
        f"; Spanne des Prüfers für H {low:g} bis {high:g}"
        if low is not None and high is not None
        else ""
    )
    return (
        f"{_doubt_short(flag)}{span} (Rating-Audit A; der Prüfer ist ein Modell einer anderen "
        "Modellfamilie, kein Mensch)"
    )


def card_figure(
    card_id: str,
    row: UnderstandingRow,
    criterion: str = CRITERION,
    *,
    extra_notes: Sequence[str] = (),
) -> dict[str, object]:
    """The contract object (class URTEIL) of one rated card for one criterion (default H)."""
    raters = int(row.get("raters", 1))
    rater_text = "1 Bewerter" if raters == 1 else f"{raters} Bewerter"
    figure_id = (
        f"{ID_PREFIX}{card_id}" if criterion == CRITERION else f"{ID_PREFIX}{card_id}:{criterion}"
    )
    return number_contract.zahl(
        figure_id,
        f"{criterion} {CRITERIA_NAMES[criterion]} (0 bis 100)",
        float(row["scores"][criterion]),
        klasse=number_contract.URTEIL,
        einheit="Punkte",
        quelle=(
            f"Rubrik {row['version']} ({row['rubric']}), Modell-Rater Stufe "
            f"{row['rater_tier']}, {rater_text}"
        ),
        kohorte=cohort(),
        hinweise=[
            f"Rater-Vertrauen {row['confidence']} (Selbstauskunft)",
            NOT_VALIDATED,
            *extra_notes,
        ],
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


def _audit(
    rows: Mapping[str, UnderstandingRow], audit: Sequence[card_understanding.AuditFlag] | None
) -> tuple[card_understanding.AuditMatch | None, str | None]:
    """The audit placed on the data set, or (None, reason) when the file is missing or broken."""
    try:
        flags = card_understanding.load_audit() if audit is None else list(audit)
    except card_understanding.UnderstandingDataError as error:
        return None, f"Rating-Audit nicht lesbar: {error}"
    return card_understanding.match_audit(dict(rows), flags), None


def _doubt_entry(flag: card_understanding.AuditFlag) -> dict[str, object]:
    low, high = flag["proposed_H_low"], flag["proposed_H_high"]
    return {
        "art": flag["kind"],
        "spanne": [low, high] if low is not None and high is not None else None,
        "h_gesehen": flag["rater_H"],
        "grund": flag["reason"],
        "kurz": _doubt_short(flag),
        "text": _doubt_text(flag),
    }


def _doubt_field(
    match: card_understanding.AuditMatch | None,
    reason: str | None,
    in_pool: Mapping[str, card_understanding.AuditFlag],
) -> dict[str, object]:
    if match is None:
        return {
            "verfuegbar": False,
            "grund": reason,
            "quelle": card_understanding.AUDIT_SOURCE,
            "n_markiert": None,
            "n_zugeordnet": None,
            "n_im_pool": None,
            "nicht_zugeordnet": [],
            "veraltet": [],
            "pruefbasis": AUDIT_BASIS,
            "karten": {},
        }
    return {
        "verfuegbar": True,
        "grund": None,
        "quelle": card_understanding.AUDIT_SOURCE,
        "n_markiert": match["n_flagged"],
        "n_zugeordnet": match["n_matched"],
        "n_im_pool": len(in_pool),
        "nicht_zugeordnet": list(match["unmatched"]),
        "veraltet": list(match["outdated"]),
        "pruefbasis": AUDIT_BASIS,
        "karten": {card_id: _doubt_entry(flag) for card_id, flag in in_pool.items()},
    }


def with_understanding(
    store: StudioStore,
    answer: Mapping[str, object],
    *,
    dataset: Mapping[str, UnderstandingRow] | None = None,
    audit: Sequence[card_understanding.AuditFlag] | None = None,
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
    match, audit_reason = _audit(rows, audit)
    doubts = match["flags"] if match is not None else {}
    findings = _claim_findings(rows)
    pool_findings: dict[str, list[dict[str, object]]] = {}
    ids = [str(card["card_id"]) for card in cards]
    lands = {str(card["card_id"]) for card in cards if card.get("is_land") is True}
    oracle = _oracle_ids(store, ids)
    figures: list[dict[str, object]] = []
    in_pool: dict[str, card_understanding.AuditFlag] = {}
    rated_lands: list[str] = []
    lands_t_zero = 0
    for card_id in ids:
        oracle_id = oracle.get(card_id)
        row = rows.get(oracle_id) if oracle_id else None
        if row is None:
            continue
        notes: list[str] = []
        flag = doubts.get(oracle_id) if oracle_id else None
        if flag is not None:
            in_pool[card_id] = flag
            notes.append(_doubt_text(flag))
        claim_found = findings.get(oracle_id) if oracle_id else None
        if claim_found:
            pool_findings[card_id] = claim_found
            notes.extend(
                f"{item['kurz']} (Claim {int(str(item['index'])) + 1})" for item in claim_found
            )
        if card_id in lands:
            rated_lands.append(card_id)
            lands_t_zero += 1 if float(row["scores"]["T"]) == 0.0 else 0
            notes.append(LAND_SCALE_TEXT)
        figures.append(card_figure(card_id, row, extra_notes=notes))
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
        "streuung": SPREAD,
        "abdeckung": {
            name: {
                "n": len(figures),
                "N": n_total,
                "bezug": "Karten des Pools (mit Wert / gesamt)",
            }
            for name in card_understanding.CRITERIA
        },
        "pruefer_zweifel": _doubt_field(match, audit_reason, in_pool),
        "regelclaim_befunde": {
            "quelle": card_understanding.AUDIT_D_SOURCE,
            "karten": pool_findings,
        },
        "laender_skala": {
            "text": LAND_SCALE_TEXT,
            "quelle": LAND_SCALE_SOURCE,
            "n_laender": len(rated_lands),
            "n_t_null": lands_t_zero,
            "bezug": "bewertete Länder dieser Antwort (T = 0 / gesamt)",
            "karten": rated_lands,
        },
        "hinweis": NOT_STRENGTH,
    }
    return out


# --- one card's single ratings for the card window (WP-6, T2) -----------------------------------


def _nothing_to_show(commander: str) -> dict[str, object]:
    return {
        "verfuegbar": False,
        "anzeigen": False,
        "grund": (
            f"Kartenverständnis gibt es nur für {card_understanding.DATASET_COMMANDER}, "
            f"nicht für {commander}"
        ),
        "name": NAME,
    }


def card_detail(
    store: StudioStore,
    card_id: str,
    commander: str,
    *,
    dataset: Mapping[str, UnderstandingRow] | None = None,
    audit: Sequence[card_understanding.AuditFlag] | None = None,
) -> dict[str, object]:
    """One card's single ratings: the seven criteria as URTEIL figures with the rater's note, the
    reason, the rules claims, the audit doubt, the land scale, the spread and the coverage n of N
    per criterion over the data set. ``anzeigen`` is False for every commander but the data set's
    (the page then shows nothing); a card the data set does not list has all seven values None
    ("unbekannt", never 0). ``KeyError`` for a card the store does not know."""
    found = store.connection.execute(
        "SELECT oracle_id, oracle_name, type_line FROM card WHERE card_id = ?", (card_id,)
    ).fetchone()
    if found is None:  # an unknown card is unknown for every commander (404 at the route)
        raise KeyError(card_id)
    if commander.strip().casefold() != card_understanding.DATASET_COMMANDER.casefold():
        return _nothing_to_show(commander)
    oracle_id, name, type_line = (str(found[0]) if found[0] else None), str(found[1]), found[2]
    base: dict[str, object] = {
        "verfuegbar": True,
        "anzeigen": True,
        "grund": None,
        "name": NAME,
        "card_id": card_id,
        "karte": name,
        "kohorte": cohort(),
        "hinweis": f"{NOT_STRENGTH}; {NOT_VALIDATED}",
        "streuung": SPREAD,
    }
    try:
        rows = card_understanding.load_cached() if dataset is None else dataset
    except card_understanding.UnderstandingDataError as error:
        return base | {
            "verfuegbar": False,
            "grund": f"Datensatz Kartenverständnis nicht lesbar: {error}",
        }
    row = rows.get(oracle_id) if oracle_id else None
    coverage = {
        name_: {
            "n": sum(1 for item in rows.values() if name_ in item["scores"]),
            "N": len(rows),
            "bezug": "Zeilen des Datensatzes (mit Wert / gesamt)",
        }
        for name_ in card_understanding.CRITERIA
    }
    is_land = "Land" in str(type_line or "").split("—")[0]
    match, audit_reason = _audit(rows, audit)
    flag = match["flags"].get(oracle_id) if match is not None and oracle_id else None
    extra = [
        *([_doubt_text(flag)] if flag is not None else []),
        *([LAND_SCALE_TEXT] if is_land and row is not None else []),
    ]
    criteria = [
        {
            "kriterium": name_,
            "name": CRITERIA_NAMES[name_],
            "zahl": card_figure(
                card_id, row, name_, extra_notes=extra if name_ == CRITERION else ()
            )
            if row is not None
            else None,
            "notiz": (row["notes"].get(name_) or None) if row is not None else None,
        }
        for name_ in card_understanding.CRITERIA
    ]
    return base | {
        "bewertet": row is not None,
        "herkunft": {
            "version": card_understanding.DATASET_VERSION,
            "rubric": card_understanding.DATASET_RUBRIC,
            "rater_tier": row["rater_tier"] if row is not None else None,
            "raters": int(row.get("raters", 1)) if row is not None else None,
        },
        "kriterien": criteria,
        "begruendung": row["reason"] if row is not None else None,
        "vertrauen": row["confidence"] if row is not None else None,
        "regelclaims": list(row["rule_claims"]) if row is not None else [],
        "regelclaims_titel": CLAIMS_HEADING,
        "regelclaims_hinweis": CLAIMS_NOTE,
        "pruefer_zweifel": _doubt_entry(flag) if flag is not None else None,
        "pruefer_audit": {
            "verfuegbar": match is not None,
            "grund": audit_reason,
            "quelle": card_understanding.AUDIT_SOURCE,
            "pruefbasis": AUDIT_BASIS,
        },
        "regelclaim_befunde": _claim_findings(rows).get(oracle_id, []) if oracle_id else [],
        "laender_skala": (
            {"text": LAND_SCALE_TEXT, "quelle": LAND_SCALE_SOURCE}
            if is_land and row is not None
            else None
        ),
        "abdeckung": coverage,
    }
