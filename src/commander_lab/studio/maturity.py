"""Maturity R0-R3 of a simulated finding in the deck builder (Q1-c, #1666; E15 Q1).

A finding is one stored paired series (base state A against variant state B, same seeds, seats
and table). It gets a maturity level only when every condition of that level is proven; what is
not proven is never assumed, so a missing proof keeps the level lower or gives none at all:

* **R0 Erkundung:** the series counts as a result (``deck_series``) and its verdict can be read.
* **R1 bestätigt:** R0, and the series is an indexed confirmation (``experiments``, purpose
  ``confirmation``) with an intact plan, its seeds (planned range and played seeds) are disjoint
  from every exploration of the same deck (re-checked when read, so a later exploration counts
  too), and its verdict is corrected by Holm.
* **R2:** R1, and a positive control, a negative control and the card competence check passed.
* **R3:** R2, and the pilot audit for this pilot fingerprint passed, and the bridge is covered by
  the seal (``covered_by_sealed_epoch``) or the Owner accepted it "vor Qualifikation".

The Studio records no positive or negative control, no card competence check, no pilot audit
and no Owner acceptance yet; :data:`NO_CHECKS` is what the route passes, so R2 and R3 are not
reachable today and say why (fail-closed). No route parameter can set them.

Verdict in four steps, threshold 0, two-sided, from the stored pairs: ``belegt besser``,
``belegt schlechter``, ``kein nachweisbarer Unterschied ab y pp`` (y = the stored detectable
difference at 80 % power) and ``nicht auswertbar``. The direction of a decided verdict is the
engine lane's (``variant_only`` against ``baseline_only``, the sign test); when the mean
difference leans the other way (fractional credit of a shared win), the series is not
evaluable, never "belegt". Below R1 (exploration, legacy series, control) a decided step is
only a hint ("Hinweis besser/schlechter (Erkundung, unbestätigt)"), never "belegt"; under the
TAM lock no result text is shown. The test statistic is the engine lane's,
reused as-is from ``commander_lab.engine.rules.full_game_comparison`` (sign test over the
discordant pairs, seed-cluster t test, ``effective_p_value``) and the Holm step is its
``_apply_holm`` on the same result model, so the Studio gives the same adjusted p-values. The
level is the stored ``decision_alpha`` of the series (the level its last look spent under the
O'Brien-Fleming plan), never the nominal level. The Holm family is every confirmation of the
same deck with the same base state and the same ``table_hash``, decided by the plan, never
by the result: a member without a usable result enters with p = 1 (a choice of this package; a
later confirmation of the same family can withhold an earlier verdict, the finding says so).
The family level is the smallest ``decision_alpha`` of its members: approximately conservative,
no proven error-rate guarantee over the O'Brien-Fleming looks.

``empfehlungsfähig`` needs R2, a finding about the current state (``main``) or its direct
predecessor, and the pilot fingerprint and bridge JAR of the series equal to the current ones.
TAM gets no simulation badge before the sim readiness per cohort is counted (E15 Q3).

Every number stays ``SIMULATED_RESULT``. Nothing here enters the tier list, a sum or a column
with EDHREC, Playgroup or tournament figures; nothing is added across states or commanders.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from commander_lab.engine.rules.full_game_comparison import (
    PairedVariantResult,
    _apply_holm,
    cluster_t_statistic,
    effective_p_value,
    sign_test_p_value,
)

from .deck_series import plan_intact, plan_record, read_series_file
from .games import games_folder
from .pilot_fingerprint import pilot_fingerprint
from .play import POLICY_VERSION
from .store import StudioStore
from .table_spec import STRENGTH
from .tam_import import TAM_COMMANDER_NAME

SCHEMA = "studio-maturity-1"
DATA_CLASS = "SIMULATED_RESULT"
R0, R1, R2, R3 = "R0", "R1", "R2", "R3"
LEVELS = (R0, R1, R2, R3)
LEVEL_TEXT = {
    R0: "R0 Erkundung",
    R1: "R1 bestätigt (frische Seeds, Holm)",
    R2: "R2 bestätigt mit Kontrollen",
    R3: "R3 bestätigt mit Pilot-Audit und gedeckter Bridge",
}
BETTER = "belegt_besser"
WORSE = "belegt_schlechter"
NO_DIFFERENCE = "kein_nachweisbarer_unterschied"
NOT_EVALUABLE = "nicht_auswertbar"
VERDICTS = (BETTER, WORSE, NO_DIFFERENCE, NOT_EVALUABLE)
CURRENT, PREDECESSOR, OTHER = "aktuell", "vorgaenger", "anderer_stand"
_CENSORING_STOPS = ("CENSORING_LIMIT", "ASYMMETRIC_CENSORING")
TAM_LOCK = (
    "TAM: kein Simulations-Abzeichen vor der Zählung der Sim-Bereitschaft je Kohorte (E15 Q3)"
)
METHOD = (
    "Ergebnis bei Schwelle 0, zweiseitig, aus den gespeicherten Paaren: Vorzeichentest über die "
    "diskordanten Paare und Seed-Cluster-t-Test (full_game_comparison.effective_p_value) auf "
    "dem Niveau decision_alpha der Serie; Holm (full_game_comparison._apply_holm) über alle "
    "indizierten Bestätigungen desselben Decks mit derselben Basis und demselben Tisch-Hash "
    "(nicht auswertbare Mitglieder zählen mit p = 1), Familienniveau = kleinstes decision_alpha. "
    "Näherungsweise konservativ: eine strenge Garantie der Fehlerrate über die "
    "O'Brien-Fleming-Looks ist nicht bewiesen."
)
GAPS = (
    "Positiv-/Negativkontrolle, Karten-Kompetenzprüfung, Pilot-Audit und Owner-Annahme "
    "„vor Qualifikation“ sind im Studio noch nicht erfasst: R2 und R3 sind nicht erreichbar."
)


@dataclass(frozen=True)
class Checks:
    """Proofs for R2/R3 for one finding, three-valued: ``True`` passed, ``False`` failed,
    ``None`` not recorded (UNKNOWN). The Studio records none of them yet."""

    positive_control: bool | None = None
    negative_control: bool | None = None
    card_competence: bool | None = None
    pilot_audit: bool | None = None
    owner_accepts_bridge: bool | None = None


NO_CHECKS = Checks()


@dataclass(frozen=True)
class Current:
    """What is current for the deck: its ``main`` state, the direct predecessor and the bridge
    JAR the next game would use (``None`` = unknown, never current). The current pilot
    fingerprint is per finding (``Finding.pilot_fingerprint_now``), from its plan's pilot."""

    main_revision_id: str | None
    predecessor_revision_id: str | None
    bridge_jar_sha256: str | None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


PASSED, FAILED, UNRECORDED = "bestanden", "durchgefallen", "nicht erfasst (UNKNOWN)"


UNKNOWN_STATE = "unbekannt (UNKNOWN)"


def _condition(
    level: str, name: str, met: bool | None, reason: str, unknown_reason: str = ""
) -> dict[str, object]:
    """A condition met, not met, or ``None`` unknown (UNKNOWN is never met)."""
    if met is None:
        return {
            "stufe": level,
            "name": name,
            "erfuellt": False,
            "zustand": UNKNOWN_STATE,
            "grund": unknown_reason or reason,
        }
    return {
        "stufe": level,
        "name": name,
        "erfuellt": met,
        "zustand": PASSED if met else "nicht erfüllt",
        "grund": "" if met else reason,
    }


def _proof(level: str, name: str, value: bool | None) -> dict[str, object]:
    """A recorded proof (passed or failed) or one that is not recorded: UNKNOWN, never failed."""
    state = UNRECORDED if value is None else PASSED if value else FAILED
    reason = {PASSED: "", FAILED: "Nachweis durchgefallen", UNRECORDED: "Nachweis nicht erfasst"}
    return {
        "stufe": level,
        "name": name,
        "erfuellt": value is True,
        "zustand": state,
        "grund": reason[state],
    }


def _clustered(result: Mapping[str, object]) -> list[tuple[int, float]] | None:
    """(seed, difference) of every stored pair; None when a pair lacks either (not evaluable)."""
    raw = result.get("pairs")
    if not isinstance(raw, list) or not raw:
        return None
    out: list[tuple[int, float]] = []
    for pair in raw:
        if not isinstance(pair, dict):
            return None
        seed, diff = _int(pair.get("seed")), _float(pair.get("difference"))
        if seed is None or diff is None:
            return None
        out.append((seed, diff))
    return out


def _directions_conflict(clustered: Sequence[tuple[int, float]]) -> bool:
    """True when the sign test leans one way and the mean difference does not lean the same way
    (fractional credit of a shared win, ``card_outcomes._credit``): no verdict direction."""
    variant_only = sum(1 for _, diff in clustered if diff > 0)
    baseline_only = sum(1 for _, diff in clustered if diff < 0)
    if variant_only == baseline_only:
        return False
    mean = sum(diff for _, diff in clustered) / len(clustered)
    return mean * (variant_only - baseline_only) <= 0


def directions_conflict(result: Mapping[str, object]) -> bool:
    """Whether the stored pairs give a sign test and a mean difference of opposite direction."""
    clustered = _clustered(result)
    return clustered is not None and _directions_conflict(clustered)


def verdict_basis(series_id: str, result: Mapping[str, object]) -> PairedVariantResult | None:
    """The engine lane's result model over the stored pairs, with the effective p-value its Holm
    step reads; None when the series gives no verdict basis, also when the mean difference and
    the sign test lean different ways (the direction is the engine lane's sign-test direction)."""
    clustered = _clustered(result)
    if clustered is None or result.get("stop_reason") in _CENSORING_STOPS:
        return None
    if _directions_conflict(clustered):
        return None
    variant_only = sum(1 for _, diff in clustered if diff > 0)
    baseline_only = sum(1 for _, diff in clustered if diff < 0)
    sign_p = sign_test_p_value(variant_only, baseline_only)
    cluster_t, cluster_df = cluster_t_statistic(clustered)
    difference = sum(diff for _, diff in clustered) / len(clustered)
    effective = effective_p_value(
        sign_p=sign_p,
        variant_only=variant_only,
        baseline_only=baseline_only,
        pairs=len(clustered),
        seed_clusters=len({seed for seed, _ in clustered}),
        cluster_t=cluster_t,
        cluster_df=cluster_df,
        difference=difference,
    )
    detectable = _float(result.get("detectable_difference_pp"))
    return PairedVariantResult(
        variant_deck_id=f"{series_id}:variant",
        baseline_deck_id=f"{series_id}:base",
        pairs_completed=len(clustered),
        pairs_censored=max(0, _int(result.get("pairs_censored")) or 0),
        variant_win_share=None,
        baseline_win_share=None,
        win_share_difference=difference,
        variant_only_wins=variant_only,
        baseline_only_wins=baseline_only,
        sign_test_p_value=sign_p,
        verdict=(
            "NO_CLEAR_DIFFERENCE"
            if effective >= 1.0
            else _direction(float(variant_only - baseline_only))
        ),
        cluster_t_statistic=cluster_t,
        cluster_t_df=cluster_df,
        effective_p_value=effective,
        detectable_difference_80pct_power=None if detectable is None else detectable / 100.0,
    )


def _direction(difference: float) -> Literal["VARIANT_BETTER", "BASELINE_BETTER"]:
    return "VARIANT_BETTER" if difference > 0 else "BASELINE_BETTER"


def decide(basis: PairedVariantResult, level: float) -> PairedVariantResult:
    """The verdict at ``level``: decided exactly when the effective p-value lies below it (the
    engine lane's sign test plus cluster confirmation in one number)."""
    p = basis.effective_p_value
    decided = p is not None and p < level and basis.verdict != "NO_CLEAR_DIFFERENCE"
    verdict = basis.verdict if decided else "NO_CLEAR_DIFFERENCE"
    result: PairedVariantResult = basis.model_copy(update={"verdict": verdict})
    return result


def _placeholder(series_id: str) -> PairedVariantResult:
    """A family member without a usable result: p = 1, no verdict (it counts, it never helps)."""
    return PairedVariantResult(
        variant_deck_id=f"{series_id}:variant",
        baseline_deck_id=f"{series_id}:base",
        pairs_completed=0,
        pairs_censored=0,
        variant_win_share=None,
        baseline_win_share=None,
        win_share_difference=None,
        variant_only_wins=0,
        baseline_only_wins=0,
        sign_test_p_value=1.0,
        verdict="NO_CLEAR_DIFFERENCE",
        effective_p_value=1.0,
    )


def _redecide(basis: PairedVariantResult | None, level: float) -> PairedVariantResult:
    """The member's verdict at the family level. That level is the smallest of the family, so a
    verdict not decided at the member's own level stays undecided; one decided may fall back."""
    if basis is None:
        raise ValueError("no basis")
    return decide(basis, level)


def holm(family: Sequence[PairedVariantResult], level: float) -> list[PairedVariantResult]:
    """Holm over ``family`` exactly as the engine lane applies it to the variants of a run."""
    return _apply_holm(list(family), [entry.effective_p_value for entry in family], level)


def verdict_of(
    entry: PairedVariantResult | None, stored_difference_pp: float | None, y_pp: float | None
) -> tuple[str, str]:
    """The four-step verdict and its text; a decided verdict against the stored sign, or an
    unknown detectable difference, is not evaluable (never "ab 0 pp")."""
    if entry is None:
        return NOT_EVALUABLE, "nicht auswertbar (keine Auswertungsbasis)"
    if entry.verdict in ("VARIANT_BETTER", "BASELINE_BETTER"):
        sign = 1.0 if entry.verdict == "VARIANT_BETTER" else -1.0
        if stored_difference_pp is None or stored_difference_pp * sign <= 0:
            return (
                NOT_EVALUABLE,
                "nicht auswertbar (Ergebnis widerspricht der gespeicherten Differenz)",
            )
        if sign > 0:
            return BETTER, "belegt besser (B gegenüber A)"
        return WORSE, "belegt schlechter (B gegenüber A)"
    if y_pp is None or y_pp <= 0:
        return NOT_EVALUABLE, "nicht auswertbar (nachweisbare Differenz unbekannt)"
    return (
        NO_DIFFERENCE,
        f"kein nachweisbarer Unterschied ab {y_pp:.1f} pp (y = nachweisbar mit 80 % Power)",
    )


def _stand(
    base: str, variant: str, hashes: Mapping[str, str], current: Current
) -> dict[str, object]:
    """Which state the finding is about, relative to the current ``main`` state."""
    main, previous = current.main_revision_id, current.predecessor_revision_id
    if main is not None and main in (base, variant):
        relation, revision, text = CURRENT, main, "Befund zum aktuellen Stand"
    elif previous is not None and previous in (base, variant):
        relation, revision, text = PREDECESSOR, previous, "Befund zum direkten Vorgänger"
    else:
        relation, revision = OTHER, base
        text = "Befund zu einem anderen Stand (nicht der aktuelle)"
    return {
        "bezug": relation,
        "text": text,
        "revision_id": revision,
        "deck_hash": hashes.get(revision),
    }


def _fresh_seeds(
    seeds: Sequence[int], first: object, last: object, explorations: Sequence[tuple[int, int]]
) -> bool:
    lo, hi = _int(first), _int(last)
    if lo is None or hi is None or not seeds:
        return False
    for start, end in explorations:
        if start <= hi and end >= lo:
            return False
        if any(start <= seed <= end for seed in seeds):
            return False
    return True


def _played_seeds(finding: Finding) -> list[int]:
    """Every seed the series names (stored result and history entry), counted or not."""
    found: set[int] = set()
    for raw in (finding.result.get("seeds"), finding.entry.get("seeds")):
        if isinstance(raw, list):
            found.update(seed for seed in raw if _int(seed) is not None)
    return sorted(found)


@dataclass(frozen=True)
class Finding:
    """One series as maturity reads it (built by :func:`deck_maturity` or by tests)."""

    series_id: str
    entry: Mapping[str, object]
    result: Mapping[str, object]
    plan_ok: bool
    pilot_fingerprint_now: str | None


def assess(
    findings: Sequence[Finding],
    *,
    explorations: Sequence[tuple[int, int]],
    hashes: Mapping[str, str],
    current: Current,
    tam: bool = False,
    checks: Mapping[str, Checks] | None = None,
    seeds_incomplete: str | None = None,
) -> dict[str, object]:
    """Maturity, verdict, state relation and ``empfehlungsfähig`` of every finding (pure).

    ``seeds_incomplete`` names why the history answer did not read every series (bounded folder
    scan, newest series only): the played seeds of the unread ones are unknown, so "frische
    Seeds" is UNKNOWN then and no confirmation reaches R1 (fail-closed)."""
    proofs = checks or {}
    bases: dict[str, PairedVariantResult | None] = {}
    levels: dict[str, float | None] = {}
    for finding in findings:
        counted = bool(finding.entry.get("counts_as_result"))
        basis = verdict_basis(finding.series_id, finding.result) if counted else None
        level = _float(finding.result.get("decision_alpha"))
        level = level if level is not None and 0.0 < level < 1.0 else None
        bases[finding.series_id] = None if basis is None or level is None else decide(basis, level)
        levels[finding.series_id] = level
    # The family hangs on the plan, never on the result: every indexed confirmation with the same
    # base and table is a member; one without a usable result (cancelled, censored, broken plan,
    # no verdict basis) enters as a placeholder with p = 1 and never gives the others credit.
    families: dict[tuple[str, str], list[Finding]] = {}
    for finding in findings:
        exp = finding.entry.get("experiment")
        if not isinstance(exp, dict) or exp.get("purpose") != "confirmation":
            continue
        if not exp.get("table_hash"):
            continue
        key = (str(finding.entry.get("base_ref")), str(exp.get("table_hash")))
        families.setdefault(key, []).append(finding)
    corrected: dict[str, tuple[PairedVariantResult, int, float]] = {}
    for members in families.values():
        known = [lv for lv in (levels[f.series_id] for f in members) if lv is not None]
        if not known:
            continue  # no member has a level: nothing to decide, nothing to correct
        family_level = min(known)
        entries = [
            _placeholder(f.series_id)
            if bases[f.series_id] is None or not f.plan_ok
            else _redecide(bases[f.series_id], family_level)
            for f in members
        ]
        adjusted = holm(entries, family_level)
        for member, entry in zip(members, adjusted, strict=True):
            if bases[member.series_id] is None or not member.plan_ok:
                continue  # a placeholder shows nothing of its own
            if len(members) == 1:  # Holm over one test is the test itself (adjusted p = p)
                entry = entry.model_copy(update={"holm_adjusted_p_value": entry.effective_p_value})
            corrected[member.series_id] = (entry, len(members), family_level)
    # Seeds a confirmation must avoid: the indexed explorations plus the played seeds of every
    # other series that is not an indexed confirmation (legacy series, explorations, controls).
    used = list(explorations)
    for finding in findings:
        exp = finding.entry.get("experiment")
        if isinstance(exp, dict) and exp.get("purpose") == "confirmation":
            continue
        used.extend((seed, seed) for seed in _played_seeds(finding))
    out: dict[str, object] = {}
    for finding in findings:
        out[finding.series_id] = _one(
            finding, bases, levels, corrected, used, hashes, current, tam, proofs, seeds_incomplete
        )
    return {
        "schema": SCHEMA,
        "data_class": DATA_CLASS,
        "methode": METHOD,
        "luecken": [GAPS],
        "tam_sperre": TAM_LOCK if tam else None,
        "befunde": out,
    }


def _one(
    finding: Finding,
    bases: Mapping[str, PairedVariantResult | None],
    levels: Mapping[str, float | None],
    corrected: Mapping[str, tuple[PairedVariantResult, int, float]],
    explorations: Sequence[tuple[int, int]],
    hashes: Mapping[str, str],
    current: Current,
    tam: bool,
    proofs: Mapping[str, Checks],
    seeds_incomplete: str | None,
) -> dict[str, object]:
    sid, entry, res = finding.series_id, finding.entry, finding.result
    exp = entry.get("experiment")
    exp_view: Mapping[str, object] = exp if isinstance(exp, dict) else {}
    holm_entry = corrected.get(sid)
    shown = holm_entry[0] if holm_entry else bases.get(sid)
    y_pp = _float(res.get("detectable_difference_pp"))
    verdict, verdict_text = verdict_of(shown, _float(entry.get("difference_pp")), y_pp)
    counted = bool(entry.get("counts_as_result"))
    if shown is None and counted and directions_conflict(res):
        verdict_text = (
            "nicht auswertbar (Mittelwert und Vorzeichentest zeigen in verschiedene Richtungen)"
        )
    withheld = holm_entry is not None and holm_entry[0].holm_withheld_verdict is not None
    if withheld and verdict == NO_DIFFERENCE:
        # y belongs to the uncorrected single test; after Holm the sensitivity is not known
        verdict_text = (
            "kein nachweisbarer Unterschied nach Holm (Empfindlichkeit nach Korrektur unbekannt)"
        )
        y_pp = None
    own_level = levels.get(sid)
    family_lower = (
        holm_entry is not None and own_level is not None and holm_entry[2] < own_level
    )
    own = bases.get(sid)
    # decided at the member's own level, taken back only by the smaller family level
    family_withheld = (
        family_lower
        and not withheld
        and own is not None
        and own.verdict != "NO_CLEAR_DIFFERENCE"
        and verdict == NO_DIFFERENCE
    )
    if family_lower and not withheld and verdict == NO_DIFFERENCE:
        # y belongs to the member's own decision_alpha; at the smaller family level the
        # sensitivity is not known, so no "ab y pp"
        verdict_text = (
            "kein nachweisbarer Unterschied auf Familienniveau "
            "(Empfindlichkeit auf diesem Niveau unbekannt)"
        )
        y_pp = None
    raw_seeds = res.get("seeds") if counted else None
    seeds = [s for s in raw_seeds if _int(s) is not None] if isinstance(raw_seeds, list) else []
    plan_seeds = exp_view.get("seeds")
    first, last = plan_seeds if isinstance(plan_seeds, list) and len(plan_seeds) == 2 else (0, -1)
    check = proofs.get(sid, NO_CHECKS)
    shas = entry.get("bridge_jar_sha256s")
    jar_list = [s for s in shas if isinstance(s, str)] if isinstance(shas, list) else []
    conditions = [
        _condition(R0, "Serie zählt als Ergebnis", counted, "Serie zählt nicht als Ergebnis"),
        _condition(R0, "Ergebnis auswertbar", verdict != NOT_EVALUABLE, verdict_text),
        _condition(
            R1,
            "Bestätigung mit intaktem Plan",
            exp_view.get("purpose") == "confirmation" and finding.plan_ok,
            "keine Bestätigung aus dem Experiment-Index (Erkundung, Kontrolle oder Alt-Serie)",
        ),
        _condition(
            R1,
            "frische Seeds (disjunkt von jeder Erkundung des Decks)",
            None if seeds_incomplete else _fresh_seeds(seeds, first, last, explorations),
            "Seeds überschneiden eine Erkundung oder sind unbekannt",
            f"{seeds_incomplete}: deren Seeds sind unbekannt" if seeds_incomplete else "",
        ),
        _condition(
            R1,
            "Holm angewandt",
            holm_entry is not None and holm_entry[0].holm_adjusted_p_value is not None,
            "kein Holm-Schritt für diesen Befund",
        ),
        _proof(R2, "Positivkontrolle bestanden", check.positive_control),
        _proof(R2, "Negativkontrolle bestanden", check.negative_control),
        _proof(R2, "Karten-Kompetenzprüfung bestanden", check.card_competence),
        _proof(R3, "Pilot-Audit für diesen Fingerabdruck", check.pilot_audit),
        _proof(
            R3,
            "Bridge durch Siegel gedeckt oder vom Owner angenommen",
            True if entry.get("covered_by_sealed_epoch") is True else check.owner_accepts_bridge,
        ),
    ]
    level: str | None = None
    for candidate in LEVELS:
        if all(c["erfuellt"] for c in conditions if c["stufe"] == candidate):
            level = candidate
        else:
            break
    if tam:
        level = None
    proven = level in (R1, R2, R3)
    if verdict in (BETTER, WORSE) and not proven:
        # below R1 a decided step is a hint, never "belegt" (no confirmation, no Holm)
        word = "besser" if verdict == BETTER else "schlechter"
        verdict_text = f"Hinweis {word} (Erkundung, unbestätigt; B gegenüber A)"
    stand = _stand(str(entry.get("base_ref")), str(entry.get("variant_ref")), hashes, current)
    reasons: list[str] = []
    if level not in (R2, R3):
        reasons.append("Reifegrad unter R2")
    if stand["bezug"] == OTHER:
        reasons.append("Befund gehört nicht zum aktuellen Stand oder direkten Vorgänger")
    stored_fp = exp_view.get("pilot_fingerprint")
    if stored_fp is None or stored_fp != finding.pilot_fingerprint_now:
        reasons.append("Pilot-Fingerabdruck nicht aktuell oder unbekannt")
    if (
        not jar_list
        or current.bridge_jar_sha256 is None
        or set(jar_list) != {current.bridge_jar_sha256}
    ):
        reasons.append("Bridge-JAR nicht aktuell oder unbekannt")
    if tam:
        reasons.append(TAM_LOCK)
    notes = []
    if holm_entry is not None:
        notes.append(
            f"Holm-Familie: {holm_entry[1]} Bestätigung(en) mit derselben Basis und demselben "
            "Tisch; eine spätere Bestätigung derselben Familie kann dieses Ergebnis zurückhalten"
        )
        if holm_entry[0].holm_withheld_verdict is not None:
            notes.append("Ergebnis durch Holm zurückgehalten")
        if family_withheld:
            notes.append(
                "Ergebnis auf dem kleineren Familienniveau zurückgehalten "
                "(auf dem eigenen Niveau der Serie entschieden)"
            )
    if entry.get("experiment") is None:
        notes.append("Alt-Serie ohne Plan: höchstens R0")
    effective_p = None if shown is None else shown.effective_p_value
    holm_p = None if holm_entry is None else holm_entry[0].holm_adjusted_p_value
    if tam:
        # E15 Q3: no simulation badge and no result text for TAM, only the lock
        verdict, verdict_text, y_pp, effective_p, holm_p = (
            NOT_EVALUABLE,
            f"kein Ergebnis gezeigt ({TAM_LOCK})",
            None,
            None,
            None,
        )
    return {
        "stufe": level,
        "stufe_text": _level_text(level, exp_view.get("purpose")),
        "bedingungen": conditions,
        "urteil": verdict,
        "urteil_text": verdict_text,
        "belegt": verdict in (BETTER, WORSE) and proven,
        "y_pp": y_pp,
        "niveau": holm_entry[2] if holm_entry else levels.get(sid),
        "effektives_p": effective_p,
        "holm_p": holm_p,
        "n": _int(entry.get("pairs_completed")),
        "N": _int(entry.get("pairs_planned")),
        "bezug": "Paare (abgeschlossen / geplant)",
        "stand": stand,
        "empfehlungsfaehig": not reasons,
        "empfehlungsfaehig_gruende": reasons,
        "hinweise": notes,
        "data_class": DATA_CLASS,
    }


def _level_text(level: str | None, purpose: object) -> str:
    if level is None:
        return "kein Reifegrad (Beleg fehlt)"
    if level == R0 and purpose == "control":
        return "R0 (Kontrolle, keine Bestätigung)"
    return LEVEL_TEXT[level]


def _current_main(store: StudioStore, deck_id: str) -> tuple[str | None, str | None]:
    row = store.connection.execute(
        "SELECT b.revision_id, r.parent_revision_id FROM deck_branch b JOIN deck_revision r "
        "ON r.revision_id = b.revision_id WHERE b.deck_id = ? AND b.branch = 'main'",
        (deck_id,),
    ).fetchone()
    if row is None:
        return None, None
    parent = row["parent_revision_id"]
    return str(row["revision_id"]), None if parent is None else str(parent)


def _is_tam(store: StudioStore, revision_id: str | None) -> bool:
    if revision_id is None:
        return False
    row = store.connection.execute(
        "SELECT 1 FROM deck_revision_card d JOIN card c ON c.card_id = d.card_id "
        "WHERE d.revision_id = ? AND d.zone = 'commander' AND c.oracle_name = ?",
        (revision_id, TAM_COMMANDER_NAME),
    ).fetchone()
    return row is not None


def _explorations(db: sqlite3.Connection, deck_id: str) -> list[tuple[int, int]]:
    return [
        (int(r[0]), int(r[1]))
        for r in db.execute(
            "SELECT first_seed, last_seed FROM experiment WHERE deck_id = ? AND purpose = "
            "'exploration' AND first_seed IS NOT NULL AND last_seed IS NOT NULL",
            (deck_id,),
        )
    ]


def _plan_fingerprint(record: Mapping[str, object] | None) -> str | None:
    """The table-level fingerprint the plan's pilot would have now (same arguments as
    ``experiments.resolve_plan``); None when the plan names no strength."""
    plan = record.get("plan") if record else None
    table = plan.get("table") if isinstance(plan, dict) else None
    pilot = table.get("pilot") if isinstance(table, dict) else None
    strength = pilot.get("strength") if isinstance(pilot, dict) else None
    if strength is None and isinstance(table, dict):
        strength = STRENGTH  # a plan without a pilot block ran the default pilot
    if not isinstance(strength, str):
        return None
    return pilot_fingerprint(policy_version=POLICY_VERSION, strength=strength)


def deck_maturity(
    store: StudioStore,
    data_folder: str | Path,
    deck_id: str,
    series_payload: Mapping[str, object],
    hashes: Mapping[str, str],
    *,
    bridge_jar_sha256: str | None,
) -> dict[str, object]:
    """Maturity of every series of ``/api/decks/{id}/series`` (read-only; writes nothing)."""
    main, previous = _current_main(store, deck_id)
    folder = games_folder(Path(data_folder).resolve())
    findings: list[Finding] = []
    skipped_files = _int(series_payload.get("scan_truncated")) or 0
    incomplete: list[str] = []
    if skipped_files > 0:
        incomplete.append(f"{skipped_files} ältere Ergebnisdateien nicht geprüft")
    if series_payload.get("truncated") is True:
        incomplete.append("nur die neuesten Serien gelesen")
    raw_series = series_payload.get("series")
    for item in raw_series if isinstance(raw_series, list) else []:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("series_id"))
        raw = read_series_file(folder / f"{sid}.paired.json")
        result = raw.get("result") if raw else None
        exp = item.get("experiment")
        record = (
            plan_record(data_folder, str(exp["experiment_id"])) if isinstance(exp, dict) else None
        )
        findings.append(
            Finding(
                series_id=sid,
                entry=item,
                result=result if isinstance(result, dict) else {},
                plan_ok=raw is not None and record is not None and plan_intact(record, raw),
                pilot_fingerprint_now=_plan_fingerprint(record),
            )
        )
    return assess(
        findings,
        explorations=_explorations(store.connection, deck_id),
        hashes=hashes,
        current=Current(main, previous, bridge_jar_sha256),
        tam=_is_tam(store, main),
        seeds_incomplete="; ".join(incomplete) or None,
    )
