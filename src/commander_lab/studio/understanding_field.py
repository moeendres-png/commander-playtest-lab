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

* ``streuung``: the spread of one rating (one run per card) as a floor of ±8 (Owner decision
  option B, E17), with its sources and n of N; the figures keep ``intervall: null`` (a spread is no
  measured per-card interval). ``rauschgate``: differences of H below that floor are no difference
  in rank; an H doubt of the audit closer to the score than the gate gets no warning mark.
* ``abdeckung``: n of N pool cards with a value, per criterion E, F, T, R, K, D, H.
* ``pruefer_zweifel``: the cards the blind rating audit doubts (Audit A), with n placed of n
  flagged; a missing audit file is "nicht verfügbar", never "no card doubted".
* ``laender_skala``: lands were rated against land anchors, on a scale of their own; their ids
  and how many of them have T = 0, counted in this answer.

``card_detail`` gives one card's single ratings (all seven criteria, reason, notes, rules claims)
for the card window; for any commander but the data set's it gives nothing to show.

Owner decision of 2026-11-22 (#1404, comment 7085569723, register E19): the shown H is the mean of
the two ratings of the card, H_pooled = (H_F1 + H_R2) / 2, read unrounded from ``pooled.jsonl`` of
the research folder (``card_understanding.load_pooled``), never with the correction K1. The field
``bewertungen`` names per card the number of ratings, both raw values with their run ("Lauf 1
(F1)", "Lauf 2 (R2)") and the mark "Bewertungen weichen stark ab" at |H_R2 - H_F1| >= 15. Without
a usable pooled value (file missing or broken, card missing, or its H_F1 not the data set's H) the
card shows H_F1 marked "nur Lauf 1". Everything else stays on the first run: the six other
criteria, reason, notes, claims, the confidence, the placement of the audit doubts (the auditor
saw H_F1) and the land counts. The spread floor ±8 and the noise gate are unchanged.

No weights, no rank: the scores are a model rater's reading of the rules text, not a
measurement, never carry price, popularity or a played-game result, and are not validated
against game results. The only mean is the Owner-chosen mean of the two ratings of H of one card.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from . import card_understanding, number_contract
from .card_understanding import PooledRow, UnderstandingRow
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
    "100 von 100 Stichproben-Claims richtig, davon 5 unscharf formuliert; in einer gezielten "
    "Sichtung ein Sachfehler beim Evoke-Opferfenster)"
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
SECOND_RUN_REPORT: Final = "docs/analysis-reports/rating_second_run_20261122.md"
FULL_RUN_REPORT: Final = "docs/analysis-reports/rating_full_second_run_20261122.md"
POOLED_FILE: Final = f"{RESEARCH}/second_run_full_20261122/pooled.jsonl"
# Owner decision of 2026-11-22, option B (#1404, comment 7081544721; register E17): the spread of
# ONE rating of H is shown as a floor of 8 points. The second rater run (265 of 300 cards, the 35
# reviewer-flagged cards left out) measured 8.1 [7.3; 8.9] (RMS of the differences / sqrt 2), above
# the old display "5 to 8". No shown spread, band or mark goes below this floor; a test recomputes
# 8.1 from the raw files and binds the floor and the noise gate to it.
SPREAD_FLOOR: Final = 8
# The noise gate of H: a difference below it is no difference in rank. It is the spread floor (one
# constant, so the gate can never be finer than the shown spread). Display and thresholds only: the
# raw scores stay as rated.
NOISE_GATE: Final = SPREAD_FLOOR
SECOND_RUN_LABEL: Final = (
    "zweiter Rater-Lauf (Familie ungeprüft, A3): 8,1; n/N = 265/300, Herkunft Bericht "
    "rating_second_run_20261122"
)
NOISE_GATE_FIELD: Final[dict[str, object]] = {
    "punkte": NOISE_GATE,
    "einheit": "Punkte",
    "text": (
        f"Unterschiede von H unter {NOISE_GATE} Punkten sind kein Rangunterschied (Rauschgate = "
        f"Mindeststreuung ±{SPREAD_FLOOR})"
    ),
    "quelle": f"{SECOND_RUN_REPORT} §0, §2 (Owner-Entscheid Option B, Register E17)",
}
# The spread of ONE rating of H (one run per card), from the reports of the research folder and the
# second rater run. The measured figures are checked against the raw files by tests (drift: RMS of
# the 49 differences / sqrt 2; other model family: RMS of the 70 differences / sqrt 2; second run:
# RMS of the 265 differences / sqrt 2; the audit's combined estimate is text).
SPREAD: Final[dict[str, object]] = {
    "kriterium": "H",
    "text": (
        f"mindestens ±{SPREAD_FLOOR} Punkte (1\u03c3, ein Lauf je Karte; {SECOND_RUN_LABEL}); "
        "je nach H-Bereich auch mehr"
    ),
    "kurz": f"±{SPREAD_FLOOR}",
    "mindestens": SPREAD_FLOOR,
    "einheit": "Punkte",
    "laeufe_je_karte": 1,
    "art": "Mindestwert der Streuung eines Einzelwerts, kein gemessenes Intervall je Karte",
    # The spread grows with H. The bands are the audit's estimate (text of AUDIT_A §4, not
    # computable from paired ratings), never shown below the floor: where the audit's estimate is
    # smaller (H up to 10, upwards from H 60), the floor is shown and the estimate is named in words.
    # A value outside every band shows the floor.
    "baender": [
        {
            "ab": 0,
            "bis": 10,
            "kurz": f"±{SPREAD_FLOOR}",
            "geschaetzt": False,
            "text": (
                f"mindestens ±{SPREAD_FLOOR} bei H bis 10 (Audit-A-Schätzung 5 Punkte, unter dem "
                "Mindestwert)"
            ),
            "quelle": f"Schätzung Rating-Audit A §4 ({RESEARCH}/audit/AUDIT_A_ratings.md)",
        },
        {
            "ab": 40,
            "bis": 55,
            "kurz": "±10",
            "geschaetzt": True,
            "text": "etwa ±10 bei H 40 bis 55 (Schätzung Audit A)",
            "quelle": f"Schätzung Rating-Audit A §4 ({RESEARCH}/audit/AUDIT_A_ratings.md)",
        },
        {
            "ab": 60,
            "bis": 100,
            "kurz": f"\u221215/+{SPREAD_FLOOR}",
            "geschaetzt": True,
            "text": (
                f"asymmetrisch ab H 60: nach unten etwa 15 (Schätzung Audit A, hohe Werte eher zu "
                f"hoch), nach oben mindestens {SPREAD_FLOOR} (Audit-A-Schätzung 5 Punkte, unter dem "
                "Mindestwert)"
            ),
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
        {
            "name": "Zweiter Rater-Lauf (Familie ungeprüft, A3)",
            "kurzname": "zweiter Lauf",
            "gemessen": True,
            "n": 265,
            "N": 300,
            "bezug": "Karten (nicht markierte Karten / Stichprobe)",
            "kennzahl": (
                "mittlere |ΔH| 8,38; Einzelstreuung 8,1 [7,3; 8,9] (RMS 11,45 / √2); Spearman "
                "0,881; Spells im Mittel rund \u22125,6, Länder +2,3; „teilweise bestätigt“ (G1)"
            ),
            "datei": f"{SECOND_RUN_REPORT} §0, §2; {RESEARCH}/second_run_20261122/",
        },
        {
            "name": "Zweite Bewertung aller Karten (Welle 1 und 2, Familie ungeprüft, A3)",
            "kurzname": "zweite Bewertung",
            "gemessen": True,
            "n": 922,
            "N": 922,
            "bezug": "Karten (zwei Bewertungen / Datensatz)",
            "kennzahl": (
                "Einzelwert SD(d)/√2 7,77 [7,38; 8,16], RMS/√2 8,46; mittleres Gefälle R2 \u2212 F1 "
                "\u22124,73; gepoolter Standardfehler SD(d)/2 5,50 nur bei unabhängigen Fehlern "
                "(nicht belegt, A3), daher Anzeige weiter mindestens ±8"
            ),
            "datei": f"{FULL_RUN_REPORT} §0, §3; {POOLED_FILE}",
        },
    ],
}
LAND_SCALE_SOURCE: Final = f"Gutachten C §4 ({RESEARCH}/audit/GUTACHTEN_C_gesamtrating.md)"
LAND_SCALE_TEXT: Final = (
    "Länder-Skala: Länder sind gegen eigene Länder-Anker bewertet, auf einer eigenen Skala; ihr H "
    "ist nicht mit dem H von Zaubern vergleichbar"
)


# --- the shown H: mean of the two ratings (Owner decision 2026-11-22, register E19) --------------

RUN_1: Final = "Lauf 1 (F1)"
RUN_2: Final = "Lauf 2 (R2)"
POOLED_SHORT: Final = "Mittel aus 2 Bewertungen"
SINGLE_SHORT: Final = "1 Bewertung, nur erste"
FALLBACK_SHORT: Final = "nur Lauf 1"
DEVIATION_LABEL: Final = "Bewertungen weichen stark ab"
RATINGS_TEXT: Final = (
    f"H = Mittel der zwei Bewertungen ({RUN_1}, {RUN_2}; zwei Bewertungen, Unabhängigkeit "
    "ungeprüft, A3), ungerundet; keine Zusatzkorrektur (K1 nicht angewendet); Owner-Entscheid "
    "2026-11-22, Register E19"
)
# The pooled standard error is shown only together with its condition (report §0, §7).
STANDARD_ERROR_NOTE: Final = (
    "Gepoolter Standardfehler SD(d)/2 = 5,50 Punkte (n/N = 922/922) gilt nur, wenn die Fehler "
    "beider Bewertungen unabhängig sind; das ist nicht belegt (A3). Deshalb bleibt die angezeigte "
    f"Streuung mindestens ±{SPREAD_FLOOR} (E17)"
)
OTHER_CRITERIA_NOTE: Final = (
    f"E, F, T, R, K, D, Notizen, Begründung, Regelclaims und Rater-Vertrauen stammen aus {RUN_1}; "
    "gemittelt wird nur H (Owner-Entscheid E19)"
)


def _de(value: float) -> str:
    """A score as German text without rounding: 42.5 -> "42,5", 40.0 -> "40"."""
    return f"{value:g}".replace(".", ",")


def _pooled(
    pooled: Mapping[str, PooledRow] | None, *, cached: bool
) -> tuple[Mapping[str, PooledRow] | None, str | None]:
    """The pooled values, or (None, reason) when the file is missing or broken: then every card
    shows H_F1 marked "nur Lauf 1" (never 0, never a partial mean)."""
    if pooled is not None:
        return pooled, None
    try:
        return (
            card_understanding.load_pooled_cached() if cached else card_understanding.load_pooled()
        ), None
    except card_understanding.DatasetNotFoundError as error:
        return None, str(error)
    except card_understanding.UnderstandingDataError as error:
        return None, f"Gepoolte Werte nicht lesbar: {error}"


def card_rating(
    row: UnderstandingRow, pooled_row: PooledRow | None, unavailable: str | None = None
) -> dict[str, object]:
    """How the shown H of one rated card comes about: the mean of two ratings, the first rating
    only (the file says so), or H_F1 because no pooled value fits ("nur Lauf 1")."""
    h_f1 = float(row["scores"]["H"])
    if pooled_row is None or pooled_row["h_f1"] != h_f1:
        reason = unavailable or (
            "kein gepoolter Wert für diese Karte"
            if pooled_row is None
            else f"gepoolter Wert passt nicht zum Datensatz (H_F1 {_de(pooled_row['h_f1'])} statt "
            f"{_de(h_f1)})"
        )
        return {
            "art": "nur_lauf_1",
            "n_bewertungen": 1,
            "wert": h_f1,
            "h_f1": h_f1,
            "h_r2": None,
            "delta": None,
            "abweichung": False,
            "kurz": FALLBACK_SHORT,
            "text": f"{FALLBACK_SHORT}: H {_de(h_f1)} aus {RUN_1}; Mittel nicht verfügbar ({reason})",
            "grund": reason,
            "marke": None,
            "quelle_r2": None,
        }
    h_r2 = pooled_row["h_r2"]
    if pooled_row["n_bewertungen"] != 2 or h_r2 is None:
        reason = pooled_row["grund"] or "keine gültige zweite Bewertung"
        return {
            "art": "nur_erstbewertung",
            "n_bewertungen": 1,
            "wert": pooled_row["h_pooled"],
            "h_f1": h_f1,
            "h_r2": None,
            "delta": None,
            "abweichung": False,
            "kurz": SINGLE_SHORT,
            "text": f"{SINGLE_SHORT}: H {_de(h_f1)} aus {RUN_1}; {RUN_2} fehlt ({reason})",
            "grund": reason,
            "marke": None,
            "quelle_r2": None,
        }
    delta = h_r2 - h_f1
    far = abs(delta) >= card_understanding.DEVIATION_MARK
    mark = (
        f"{DEVIATION_LABEL} (Δ {_de(abs(delta))}: {RUN_1} {_de(h_f1)}, {RUN_2} {_de(h_r2)})"
        if far
        else None
    )
    return {
        "art": "mittel",
        "n_bewertungen": 2,
        "wert": pooled_row["h_pooled"],
        "h_f1": h_f1,
        "h_r2": h_r2,
        "delta": delta,
        "abweichung": far,
        "kurz": POOLED_SHORT,
        "text": (
            f"{POOLED_SHORT}: H {_de(pooled_row['h_pooled'])} = Mittel aus {RUN_1} {_de(h_f1)} "
            f"und {RUN_2} {_de(h_r2)}"
        ),
        "grund": None,
        "marke": mark,
        "quelle_r2": pooled_row["quelle_r2"],
    }


def _runs(
    rows: Mapping[str, UnderstandingRow], pooled: Mapping[str, PooledRow] | None
) -> list[dict[str, object]]:
    """n of N per run over the data set: how many cards have a valid H of that run. Without the
    pooled file the second run is "unbekannt" (n None), never 0."""
    second = (
        sum(
            1
            for oracle_id, row in rows.items()
            if (found := pooled.get(oracle_id)) is not None
            and found["h_r2"] is not None
            and found["h_f1"] == float(row["scores"]["H"])
        )
        if pooled is not None
        else None
    )
    bezug = "Karten des Datensatzes mit gültigem H dieses Laufs / gesamt"
    return [
        {"lauf": RUN_1, "n": len(rows), "N": len(rows), "bezug": bezug},
        {"lauf": RUN_2, "n": second, "N": len(rows), "bezug": bezug},
    ]


def _h_source(row: UnderstandingRow, rating: Mapping[str, object]) -> str:
    """The origin of the shown H, the same text for all cards of one kind (the head line of the
    tier list lists the distinct origins once)."""
    base = f"Rubrik {row['version']} ({row['rubric']})"
    if rating["art"] == "mittel":
        return (
            f"{base}, {POOLED_SHORT}: {RUN_1} Modell-Rater Stufe {row['rater_tier']}, {RUN_2} "
            "Modell-Rater Stufe unbekannt (Unabhängigkeit ungeprüft, A3)"
        )
    raters = int(row.get("raters", 1))
    rater_text = "1 Bewerter" if raters == 1 else f"{raters} Bewerter"
    return f"{base}, Modell-Rater Stufe {row['rater_tier']}, {rater_text}, {RUN_1}"


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
                "teil": item["part"],
                "begruendung_hinweis": item["reason_note"],
                "quelle": f"{card_understanding.AUDIT_D_SOURCE} ({item['part']})",
            }
        )
    return found


def doubt_distance(flag: card_understanding.AuditFlag) -> float | None:
    """How far the score lies outside the reviewer's span for H (0 inside it); None when the
    flag is no doubt about H (a wrong reason) or names no span."""
    low, high = flag["proposed_H_low"], flag["proposed_H_high"]
    if not flag["kind"].startswith("H ") or low is None or high is None:
        return None
    score = flag["rater_H"]
    return max(low - score, score - high, 0.0)


def doubt_below_gate(flag: card_understanding.AuditFlag) -> bool:
    """An H doubt whose span lies closer to the score than the noise gate: a difference under the
    spread, so it is shown without a warning mark (no difference in rank)."""
    distance = doubt_distance(flag)
    return distance is not None and distance < NOISE_GATE


def _doubt_short(flag: card_understanding.AuditFlag) -> str:
    """The visible label: the reviewer is a model, and a wrong reason is no doubt about H."""
    if flag["kind"] == "Begründung faktisch falsch":
        return "Prüfer-Modell: Begründung faktisch falsch"
    if doubt_below_gate(flag):
        return f"Prüfer-Spanne innerhalb der Streuung (unter {NOISE_GATE} Punkten)"
    return f"Prüfer-Modell bezweifelt H: {flag['kind'].removeprefix('H ')}"


def _doubt_text(flag: card_understanding.AuditFlag) -> str:
    low, high = flag["proposed_H_low"], flag["proposed_H_high"]
    span = (
        f"; Spanne des Prüfers für H {low:g} bis {high:g}"
        if low is not None and high is not None
        else ""
    )
    return (
        f"{_doubt_short(flag)}{span}; bezieht sich auf H {_de(flag['rater_H'])} aus {RUN_1} "
        "(Rating-Audit A; der Prüfer ist ein Modell einer anderen Modellfamilie, kein Mensch)"
    )


def card_figure(
    card_id: str,
    row: UnderstandingRow,
    criterion: str = CRITERION,
    *,
    extra_notes: Sequence[str] = (),
    rating: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """The contract object (class URTEIL) of one rated card for one criterion (default H). With
    ``rating`` (``card_rating``) the figure of H shows the rating's value (the mean of the two
    ratings, or H_F1 for a single rating) with its origin; the other criteria never take it."""
    raters = int(row.get("raters", 1))
    rater_text = "1 Bewerter" if raters == 1 else f"{raters} Bewerter"
    figure_id = (
        f"{ID_PREFIX}{card_id}" if criterion == CRITERION else f"{ID_PREFIX}{card_id}:{criterion}"
    )
    value = float(row["scores"][criterion])
    source = (
        f"Rubrik {row['version']} ({row['rubric']}), Modell-Rater Stufe "
        f"{row['rater_tier']}, {rater_text}"
    )
    rating_notes: list[str] = []
    if rating is not None and criterion == CRITERION:
        value = float(str(rating["wert"]))
        source = _h_source(row, rating)
        rating_notes = [str(rating["text"]), *([str(rating["marke"])] if rating["marke"] else [])]
    return number_contract.zahl(
        figure_id,
        f"{criterion} {CRITERIA_NAMES[criterion]} (0 bis 100)",
        value,
        klasse=number_contract.URTEIL,
        einheit="Punkte",
        quelle=source,
        kohorte=cohort(),
        hinweise=[
            f"Rater-Vertrauen {row['confidence']} (Selbstauskunft)",
            NOT_VALIDATED,
            *rating_notes,
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
        "abstand": doubt_distance(flag),
        "unter_rauschgate": doubt_below_gate(flag),
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
            "rauschgate": NOISE_GATE,
            "n_unter_rauschgate": None,
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
        "rauschgate": NOISE_GATE,
        "n_unter_rauschgate": sum(1 for flag in in_pool.values() if doubt_below_gate(flag)),
        "karten": {card_id: _doubt_entry(flag) for card_id, flag in in_pool.items()},
    }


def with_understanding(
    store: StudioStore,
    answer: Mapping[str, object],
    *,
    dataset: Mapping[str, UnderstandingRow] | None = None,
    audit: Sequence[card_understanding.AuditFlag] | None = None,
    pooled: Mapping[str, PooledRow] | None = None,
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
    pooled_rows, pooled_reason = _pooled(pooled, cached=False)
    ratings: dict[str, dict[str, object]] = {}
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
        rating = card_rating(
            row,
            pooled_rows.get(oracle_id) if pooled_rows is not None and oracle_id else None,
            pooled_reason,
        )
        ratings[card_id] = rating
        figures.append(card_figure(card_id, row, extra_notes=notes, rating=rating))
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
        "rauschgate": NOISE_GATE_FIELD,
        "bewertungen": _ratings_field(rows, pooled_rows, pooled_reason, ratings),
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


def _ratings_field(
    rows: Mapping[str, UnderstandingRow],
    pooled: Mapping[str, PooledRow] | None,
    reason: str | None,
    ratings: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    """Per pool card how its shown H comes about, and the counts beside it (n of N)."""
    kinds = [str(rating["art"]) for rating in ratings.values()]
    far_in_set = (
        sum(
            1
            for oracle_id, row in rows.items()
            if (found := pooled.get(oracle_id)) is not None
            and found["h_r2"] is not None
            and found["h_f1"] == float(row["scores"]["H"])
            and abs(found["h_r2"] - found["h_f1"]) >= card_understanding.DEVIATION_MARK
        )
        if pooled is not None
        else None
    )
    return {
        "verfuegbar": pooled is not None,
        "grund": reason,
        "quelle": card_understanding.POOLED_SOURCE,
        "text": RATINGS_TEXT
        if pooled is not None
        else f"{FALLBACK_SHORT}: H aus {RUN_1} ({reason})",
        "laeufe": _runs(rows, pooled),
        "n_mittel": kinds.count("mittel"),
        "n_nur_erstbewertung": kinds.count("nur_erstbewertung"),
        "n_nur_lauf_1": kinds.count("nur_lauf_1"),
        "N": len(ratings),
        "bezug": "bewertete Karten dieser Antwort",
        "schwelle_abweichung": card_understanding.DEVIATION_MARK,
        "n_abweichung": sum(1 for rating in ratings.values() if rating["abweichung"] is True),
        "abweichung_datensatz": {
            "n": far_in_set,
            "N": len(rows),
            "bezug": "Karten des Datensatzes",
        },
        "standardfehler_hinweis": STANDARD_ERROR_NOTE,
        "karten": dict(ratings),
    }


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
    pooled: Mapping[str, PooledRow] | None = None,
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
        "rauschgate": NOISE_GATE_FIELD,
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
    pooled_rows, pooled_reason = _pooled(pooled, cached=True)
    rating = (
        card_rating(
            row,
            pooled_rows.get(oracle_id) if pooled_rows is not None and oracle_id else None,
            pooled_reason,
        )
        if row is not None
        else None
    )
    criteria = [
        {
            "kriterium": name_,
            "name": CRITERIA_NAMES[name_],
            "zahl": card_figure(
                card_id,
                row,
                name_,
                extra_notes=extra if name_ == CRITERION else (),
                rating=rating,
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
        "bewertungen": {
            "verfuegbar": pooled_rows is not None,
            "grund": pooled_reason,
            "quelle": card_understanding.POOLED_SOURCE,
            "text": RATINGS_TEXT,
            "laeufe": _runs(rows, pooled_rows),
            "karte": rating,
            "schwelle_abweichung": card_understanding.DEVIATION_MARK,
            "standardfehler_hinweis": STANDARD_ERROR_NOTE,
            "andere_kriterien": OTHER_CRITERIA_NOTE,
        },
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
