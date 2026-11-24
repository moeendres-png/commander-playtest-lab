"""The card-understanding data set (Kartenverständnis, rubric v2.1): loader and validation.

One JSON line per card of the Chulane pool: seven scores E, F, T, R, K, D, H (0 to 100, higher is
better for the deck), a confidence, the rater's reason and notes, the rules claims the rating
relies on, and where the line came from (``version``, ``rater_tier``, ``rubric``). The file is
compact and derived: ``scripts/import_card_understanding.py`` builds it from the raw rater output.

This module only reads and checks. A broken line makes the whole load fail with the line numbers
(fail closed): a half-read data set would silently rank some cards without their rating. A card
the file does not list is unknown, never 0. A line whose ``version`` or ``rubric`` is not the
data set's is rejected: cohorts of different rubrics are never mixed. The scores are a model rater's judgement of what a
card does in the deck from its rules text, not a measurement; they never carry price, popularity
or any played-game result (the raters are blind to those).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Final, NotRequired, TypedDict

CRITERIA: Final[tuple[str, ...]] = ("E", "F", "T", "R", "K", "D", "H")
CONFIDENCE_LEVELS: Final[tuple[str, ...]] = ("high", "medium", "low")
RATER_TIERS: Final[tuple[str, ...]] = ("small", "large")
DATASET_VERSION: Final = "v2.1"
DATASET_RUBRIC: Final = "chulane-rubric-v2.1"
DATASET_COMMANDER: Final = "Chulane, Teller of Tales"
DATASET_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "card_understanding"
    / "card_understanding_v2_1.jsonl"
)
STEP: Final = 5
MAX_ERRORS: Final = 10

_REQUIRED: Final[tuple[str, ...]] = (
    "oracle_id",
    "card",
    "scores",
    "confidence",
    "reason",
    "notes",
    "rule_claims",
    "version",
    "rater_tier",
    "rubric",
)
_OPTIONAL: Final[tuple[str, ...]] = ("raters", "score_sd", "rounded", "uncertainty")


class UnderstandingRow(TypedDict):
    """One validated line. ``score_sd`` (spread of several raters, per criterion) is None for a
    single rater: an unknown spread is not 0. ``rounded`` marks scores that were rounded to a
    multiple of 5 when the line was built."""

    oracle_id: str
    card: str
    scores: dict[str, float]
    confidence: str
    reason: str
    notes: dict[str, str]
    rule_claims: list[dict[str, object]]
    version: str
    rater_tier: str
    rubric: str
    raters: NotRequired[int]
    score_sd: NotRequired[dict[str, float] | None]
    rounded: NotRequired[bool]
    uncertainty: NotRequired[str]


class UnderstandingDataError(ValueError):
    """The data set (or a line of it) violates the contract or cannot be read."""


class DatasetNotFoundError(UnderstandingDataError):
    """The data file does not exist (a missing file is not an empty data set)."""


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:  # an integer too large for a float
        return None
    return number if math.isfinite(number) else None


def _text(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UnderstandingDataError(f"{key} must be a non-empty string")
    return value


def _criteria_map(value: object, key: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise UnderstandingDataError(f"{key} must be an object")
    unknown = sorted(str(name) for name in value if name not in CRITERIA)
    if unknown:
        raise UnderstandingDataError(f"{key} has unknown criteria {unknown}")
    missing = [name for name in CRITERIA if name not in value]
    if missing:
        raise UnderstandingDataError(f"{key} lacks the criteria {missing}")
    result: dict[str, float] = {}
    for name in CRITERIA:
        number = _number(value[name])
        if number is None:
            raise UnderstandingDataError(f"{key}.{name} must be a finite number")
        if not 0.0 <= number <= 100.0:
            raise UnderstandingDataError(f"{key}.{name} = {number:g} is outside 0..100")
        result[name] = number
    return result


def parse_row(raw: object) -> UnderstandingRow:
    """Validate one decoded line and return it typed; raises ``UnderstandingDataError``."""
    if not isinstance(raw, dict):
        raise UnderstandingDataError("a line must be a JSON object")
    unknown = sorted(str(key) for key in raw if key not in _REQUIRED and key not in _OPTIONAL)
    if unknown:
        raise UnderstandingDataError(f"unknown fields {unknown}")
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise UnderstandingDataError(f"missing required fields {missing}")
    row: UnderstandingRow = {
        "oracle_id": _text(raw, "oracle_id"),
        "card": _text(raw, "card"),
        "scores": _criteria_map(raw["scores"], "scores"),
        "confidence": _text(raw, "confidence"),
        "reason": _text(raw, "reason"),
        "notes": {},
        "rule_claims": [],
        "version": _text(raw, "version"),
        "rater_tier": _text(raw, "rater_tier"),
        "rubric": _text(raw, "rubric"),
    }
    if row["version"] != DATASET_VERSION:
        raise UnderstandingDataError(
            f"version {row['version']!r} is not the data set version {DATASET_VERSION!r}"
        )
    if row["rubric"] != DATASET_RUBRIC:
        raise UnderstandingDataError(
            f"rubric {row['rubric']!r} is not the data set rubric {DATASET_RUBRIC!r}"
        )
    if row["confidence"] not in CONFIDENCE_LEVELS:
        raise UnderstandingDataError(f"confidence must be one of {list(CONFIDENCE_LEVELS)}")
    if row["rater_tier"] not in RATER_TIERS:
        raise UnderstandingDataError(f"rater_tier must be one of {list(RATER_TIERS)}")
    notes = raw["notes"]
    if not isinstance(notes, dict) or any(
        name not in CRITERIA or not isinstance(text, str) for name, text in notes.items()
    ):
        raise UnderstandingDataError("notes must map criteria to strings")
    row["notes"] = {str(name): str(text) for name, text in notes.items()}
    claims = raw["rule_claims"]
    if not isinstance(claims, list) or any(not isinstance(item, dict) for item in claims):
        raise UnderstandingDataError("rule_claims must be a list of objects")
    row["rule_claims"] = [{str(k): v for k, v in item.items()} for item in claims]
    if "raters" in raw:
        raters = raw["raters"]
        if isinstance(raters, bool) or not isinstance(raters, int) or raters < 1:
            raise UnderstandingDataError("raters must be an integer of at least 1")
        row["raters"] = raters
    if raw.get("score_sd") is not None:
        row["score_sd"] = _criteria_map(raw["score_sd"], "score_sd")
    elif "score_sd" in raw:
        row["score_sd"] = None
    if "rounded" in raw:
        if not isinstance(raw["rounded"], bool):
            raise UnderstandingDataError("rounded must be true or false")
        row["rounded"] = raw["rounded"]
    if "uncertainty" in raw:
        if not isinstance(raw["uncertainty"], str):
            raise UnderstandingDataError("uncertainty must be a string")
        row["uncertainty"] = raw["uncertainty"]
    return row


def parse_lines(lines: list[str]) -> dict[str, UnderstandingRow]:
    """All lines of a data set by ``oracle_id``. Blank lines are skipped; a broken line or a
    repeated ``oracle_id`` raises one error that names up to ``MAX_ERRORS`` line numbers."""
    rows: dict[str, UnderstandingRow] = {}
    errors: list[str] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = parse_row(json.loads(line))
        except json.JSONDecodeError as error:
            errors.append(f"line {number}: not valid JSON ({error.msg})")
            continue
        except UnderstandingDataError as error:
            errors.append(f"line {number}: {error}")
            continue
        except (ValueError, OverflowError, RecursionError) as error:
            errors.append(f"line {number}: cannot be decoded ({type(error).__name__})")
            continue
        if row["oracle_id"] in rows:
            errors.append(f"line {number}: oracle_id {row['oracle_id']} appears twice")
            continue
        rows[row["oracle_id"]] = row
    if errors:
        shown = "; ".join(errors[:MAX_ERRORS])
        more = f" (+{len(errors) - MAX_ERRORS} more)" if len(errors) > MAX_ERRORS else ""
        raise UnderstandingDataError(f"{len(errors)} broken line(s): {shown}{more}")
    return rows


def load(path: Path | None = None) -> dict[str, UnderstandingRow]:
    """The data set at ``path`` (default ``DATASET_PATH``). Every failure (file missing,
    unreadable, not UTF-8, a broken line) is an ``UnderstandingDataError``: a missing file is
    ``DatasetNotFoundError`` and never an empty data set."""
    target = DATASET_PATH if path is None else path
    if not target.is_file():
        raise DatasetNotFoundError(f"Datensatz nicht gefunden: {target.name}")
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise UnderstandingDataError(
            f"data file cannot be read ({type(error).__name__})"
        ) from error
    return parse_lines(text.splitlines())


def stamp(path: Path | None = None) -> tuple[str, int, int] | None:
    """Identity of the data file (path, size, modification time) for cache keys; None if absent."""
    target = DATASET_PATH if path is None else path
    try:
        found = os.stat(target)
    except OSError:
        return None
    return (str(target), found.st_size, found.st_mtime_ns)


_LOADED: dict[str, tuple[tuple[str, int, int], dict[str, UnderstandingRow]]] = {}


def load_cached() -> dict[str, UnderstandingRow]:
    """``load()`` of ``DATASET_PATH``, parsed once per file identity (path, size, mtime). The card
    window asks per card; reading 922 lines each time is not needed. Same failures as ``load``."""
    found = stamp()
    if found is None:
        return load()
    cached = _LOADED.get("dataset")
    if cached is not None and cached[0] == found:
        return cached[1]
    rows = load()
    _LOADED["dataset"] = (found, rows)
    return rows


# --- the rating audit of rubric v2.1 (Audit A): cards the reviewer doubts ----------------------
#
# The audit is a separate, blind review of the full run (reviewer of another model family, no usage
# data): 35 lines, one per card whose score H it doubts, with the proposed range. It is research
# evidence, read as it is from the research folder; nothing here changes a score.

AUDIT_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "research"
    / "chulane_rubric_v2_20261118"
    / "audit"
    / "audit_A_flagged.jsonl"
)
AUDIT_SOURCE: Final = (
    "Rating-Audit A der Rubrik v2.1 (blinde Prüfung ohne Nutzungsdaten, Prüfer aus einer "
    "anderen Modellfamilie), data/research/chulane_rubric_v2_20261118/audit/audit_A_flagged.jsonl"
)
AUDIT_KINDS: Final[tuple[str, ...]] = ("H zu hoch", "H zu niedrig", "Begründung faktisch falsch")


class AuditFlag(TypedDict):
    """One doubted card of the audit: the H the reviewer saw, its proposed range and why."""

    card: str
    rater_H: float
    proposed_H_low: float | None
    proposed_H_high: float | None
    kind: str
    reason: str
    sample: str


def parse_audit_row(raw: object) -> AuditFlag:
    """Validate one decoded audit line; raises ``UnderstandingDataError``."""
    if not isinstance(raw, dict):
        raise UnderstandingDataError("an audit line must be a JSON object")
    allowed = {"card", "rater_H", "proposed_H_low", "proposed_H_high", "kind", "reason", "sample"}
    unknown = sorted(str(key) for key in raw if key not in allowed)
    if unknown:
        raise UnderstandingDataError(f"unknown audit fields {unknown}")
    missing = sorted(
        key for key in ("card", "rater_H", "kind", "reason", "sample") if key not in raw
    )
    if missing:
        raise UnderstandingDataError(f"missing audit fields {missing}")
    rater_h = _number(raw["rater_H"])
    if rater_h is None or not 0.0 <= rater_h <= 100.0:
        raise UnderstandingDataError("rater_H must be a number in 0..100")
    bounds: list[float | None] = []
    for key in ("proposed_H_low", "proposed_H_high"):
        value = raw.get(key)
        number = None if value is None else _number(value)
        if value is not None and (number is None or not 0.0 <= number <= 100.0):
            raise UnderstandingDataError(f"{key} must be a number in 0..100 or null")
        bounds.append(number)
    low, high = bounds
    if low is not None and high is not None and low > high:
        raise UnderstandingDataError("proposed_H_low is above proposed_H_high")
    kind = _text(raw, "kind")
    if kind not in AUDIT_KINDS:
        raise UnderstandingDataError(f"kind must be one of {list(AUDIT_KINDS)}")
    return {
        "card": _text(raw, "card"),
        "rater_H": rater_h,
        "proposed_H_low": low,
        "proposed_H_high": high,
        "kind": kind,
        "reason": _text(raw, "reason"),
        "sample": _text(raw, "sample"),
    }


def load_audit(path: Path | None = None) -> list[AuditFlag]:
    """All lines of the audit file (default ``AUDIT_PATH``), in file order. A missing file is
    ``DatasetNotFoundError`` (never "no card doubted"); a broken line fails the whole load."""
    target = AUDIT_PATH if path is None else path
    if not target.is_file():
        raise DatasetNotFoundError(f"Audit-Datei nicht gefunden: {target.name}")
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise UnderstandingDataError(
            f"audit file cannot be read ({type(error).__name__})"
        ) from error
    flags: list[AuditFlag] = []
    errors: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            flags.append(parse_audit_row(json.loads(line)))
        except json.JSONDecodeError as error:
            errors.append(f"line {number}: not valid JSON ({error.msg})")
        except UnderstandingDataError as error:
            errors.append(f"line {number}: {error}")
    if errors:
        raise UnderstandingDataError(f"{len(errors)} broken audit line(s): {'; '.join(errors[:3])}")
    return flags


def audit_stamp(path: Path | None = None) -> tuple[str, int, int] | None:
    """Identity of the audit file for cache keys; None if absent."""
    return stamp(AUDIT_PATH if path is None else path)


class AuditMatch(TypedDict):
    """The audit read against the data set: per ``oracle_id`` the flag that still describes the
    current score, and the counts that say how much of the audit could be placed."""

    flags: dict[str, AuditFlag]
    n_flagged: int
    n_matched: int
    unmatched: list[str]
    outdated: list[str]


def match_audit(rows: dict[str, UnderstandingRow], flags: list[AuditFlag]) -> AuditMatch:
    """Place every audit line on a data-set row by its exact card name. A name the data set does
    not list is counted as unmatched (never dropped silently); a line whose ``rater_H`` is not the
    row's current H is counted as outdated and not shown as a doubt of the current score."""
    by_name: dict[str, str] = {}
    for oracle_id, row in rows.items():
        by_name.setdefault(row["card"], oracle_id)
    placed: dict[str, AuditFlag] = {}
    unmatched: list[str] = []
    outdated: list[str] = []
    for flag in flags:
        placed_id = by_name.get(flag["card"])
        if placed_id is None:
            unmatched.append(flag["card"])
            continue
        if float(rows[placed_id]["scores"]["H"]) != flag["rater_H"]:
            outdated.append(flag["card"])
            continue
        placed[placed_id] = flag
    return {
        "flags": placed,
        "n_flagged": len(flags),
        "n_matched": len(placed),
        "unmatched": unmatched,
        "outdated": outdated,
    }


# --- the pooled H of two ratings (Owner decision of 2026-11-22, register E19, #1404) -----------
#
# The second rating of all 922 cards (wave 1, #1758; wave 2, #1764) gives every card two ratings
# of H: F1 (the full run, the scores of the data set above) and R2. The evaluation script of the
# pre-registered plan wrote the mean of both, unrounded, to ``pooled.jsonl`` in the research
# folder. The Studio only reads that file; it never writes or rounds it, and it never reads the
# correction proposal K1 of the file (the Owner chose the plain mean, no correction). A broken file
# fails as a whole (a half-read file would mix pooled and single values silently).

POOLED_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "research"
    / "chulane_rubric_v2_20261118"
    / "second_run_full_20261122"
    / "pooled.jsonl"
)
POOLED_SOURCE: Final = (
    "data/research/chulane_rubric_v2_20261118/second_run_full_20261122/pooled.jsonl "
    "(Bericht docs/analysis-reports/rating_full_second_run_20261122.md)"
)
# |H_R2 - H_F1| from which the two ratings count as far apart (plan §4, marks of the file).
DEVIATION_MARK: Final = 15.0
DEVIATION_STRONG: Final = 30.0
POOLED_MARKS: Final[tuple[str, ...]] = (
    "abweichung_ge15",
    "abweichung_ge30",
    "nur_erstbewertung",
    "charge_auffaellig",
)
_POOLED_REQUIRED: Final[tuple[str, ...]] = (
    "oracle_id",
    "card",
    "H_F1",
    "H_R2",
    "H_pooled",
    "n_bewertungen",
    "marken",
    "grund_nur_erstbewertung",
    "quelle_R2",
)
# present in the file, never read by the Studio (K1 is not applied; only H was decided)
_POOLED_IGNORED: Final[tuple[str, ...]] = ("H_pooled_K1_vorschlag", "teilkriterien_gepoolt")


class PooledRow(TypedDict):
    """One validated line of ``pooled.jsonl``: both ratings of H, their mean and the marks.
    ``h_r2`` is None when the card has only the first rating (``n_bewertungen`` 1); ``h_pooled``
    is then ``h_f1``."""

    oracle_id: str
    card: str
    h_f1: float
    h_r2: float | None
    h_pooled: float
    n_bewertungen: int
    marken: list[str]
    grund: str | None
    quelle_r2: str | None


def _score(raw: dict[str, object], key: str, *, half_step: int = 10) -> float:
    number = _number(raw.get(key))
    if number is None or not 0.0 <= number <= 100.0:
        raise UnderstandingDataError(f"{key} must be a number in 0..100")
    doubled = number * 2.0
    if not math.isclose(doubled, round(doubled), abs_tol=1e-9) or round(doubled) % half_step:
        step = half_step / 2.0
        raise UnderstandingDataError(f"{key} must lie on the {step:g}-point grid")
    return number


def parse_pooled_row(raw: object) -> PooledRow:
    """Validate one decoded line of the pooled file; raises ``UnderstandingDataError``. The mean,
    the number of ratings and the marks must agree with the two raw values."""
    if not isinstance(raw, dict):
        raise UnderstandingDataError("a pooled line must be a JSON object")
    unknown = sorted(
        str(key) for key in raw if key not in _POOLED_REQUIRED and key not in _POOLED_IGNORED
    )
    if unknown:
        raise UnderstandingDataError(f"unknown pooled fields {unknown}")
    missing = [key for key in _POOLED_REQUIRED if key not in raw]
    if missing:
        raise UnderstandingDataError(f"missing pooled fields {missing}")
    h_f1 = _score(raw, "H_F1", half_step=10)
    h_pooled = _score(raw, "H_pooled", half_step=5)
    count = raw["n_bewertungen"]
    if isinstance(count, bool) or count not in (1, 2):
        raise UnderstandingDataError("n_bewertungen must be 1 or 2")
    marks = raw["marken"]
    if not isinstance(marks, list) or any(mark not in POOLED_MARKS for mark in marks):
        raise UnderstandingDataError(f"marken must be a list of {list(POOLED_MARKS)}")
    reason = raw["grund_nur_erstbewertung"]
    source = raw["quelle_R2"]
    if count == 2:
        second = _score(raw, "H_R2", half_step=10)
        h_r2: float | None = second
        if not isinstance(source, str) or not source.strip():
            raise UnderstandingDataError("quelle_R2 must name the second rating")
        if source.strip() == "welle2:8":
            raise UnderstandingDataError("retest batch welle2:8 must not enter pooled ratings")
        if reason is not None or "nur_erstbewertung" in marks:
            raise UnderstandingDataError("two ratings carry no reason for a single rating")
        if not math.isclose(h_pooled, (h_f1 + second) / 2.0, abs_tol=1e-9):
            raise UnderstandingDataError("H_pooled is not the mean of H_F1 and H_R2")
        gap = abs(second - h_f1)
    else:
        if raw["H_R2"] is not None:
            raise UnderstandingDataError("a single rating has no H_R2")
        if not math.isclose(h_pooled, h_f1, abs_tol=1e-9):
            raise UnderstandingDataError("a single rating keeps H_pooled = H_F1")
        if not isinstance(reason, str) or not reason.strip() or "nur_erstbewertung" not in marks:
            raise UnderstandingDataError("a single rating needs the mark and its reason")
        h_r2, source, gap = None, None, 0.0
    if ("abweichung_ge15" in marks) != (gap >= DEVIATION_MARK):
        raise UnderstandingDataError("abweichung_ge15 does not match |H_R2 - H_F1|")
    if ("abweichung_ge30" in marks) != (gap >= DEVIATION_STRONG):
        raise UnderstandingDataError("abweichung_ge30 does not match |H_R2 - H_F1|")
    return {
        "oracle_id": _text(raw, "oracle_id"),
        "card": _text(raw, "card"),
        "h_f1": h_f1,
        "h_r2": h_r2,
        "h_pooled": h_pooled,
        "n_bewertungen": int(count),
        "marken": [str(mark) for mark in marks],
        "grund": str(reason) if reason is not None else None,
        "quelle_r2": str(source) if source is not None else None,
    }


def load_pooled(path: Path | None = None) -> dict[str, PooledRow]:
    """The pooled file (default ``POOLED_PATH``) by ``oracle_id``. A missing file is
    ``DatasetNotFoundError``; a broken line or a repeated ``oracle_id`` fails the whole load."""
    target = POOLED_PATH if path is None else path
    if not target.is_file():
        raise DatasetNotFoundError(f"Datei der gepoolten Werte nicht gefunden: {target.name}")
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise UnderstandingDataError(
            f"pooled file cannot be read ({type(error).__name__})"
        ) from error
    rows: dict[str, PooledRow] = {}
    errors: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = parse_pooled_row(json.loads(line))
        except json.JSONDecodeError as error:
            errors.append(f"line {number}: not valid JSON ({error.msg})")
            continue
        except UnderstandingDataError as error:
            errors.append(f"line {number}: {error}")
            continue
        except (ValueError, OverflowError, RecursionError) as error:
            errors.append(f"line {number}: cannot be decoded ({type(error).__name__})")
            continue
        if row["oracle_id"] in rows:
            errors.append(f"line {number}: oracle_id {row['oracle_id']} appears twice")
            continue
        rows[row["oracle_id"]] = row
    if errors:
        shown = "; ".join(errors[:MAX_ERRORS])
        raise UnderstandingDataError(f"{len(errors)} broken pooled line(s): {shown}")
    return rows


def pooled_stamp(path: Path | None = None) -> tuple[str, int, int] | None:
    """Identity of the pooled file for cache keys; None if absent."""
    return stamp(POOLED_PATH if path is None else path)


def load_pooled_cached() -> dict[str, PooledRow]:
    """``load_pooled()`` of ``POOLED_PATH``, parsed once per file identity. Same failures."""
    found = pooled_stamp()
    if found is None:
        return load_pooled()
    cached = _POOLED.get("pooled")
    if cached is not None and cached[0] == found:
        return cached[1]
    rows = load_pooled()
    _POOLED["pooled"] = (found, rows)
    return rows


_POOLED: dict[str, tuple[tuple[str, int, int], dict[str, PooledRow]]] = {}


# --- the rules-claim review of rubric v2.1 (Audit D) ------------------------------------------
#
# Audit D checked 100 random rules claims (100 right, 5 of them right but unsharply worded) and
# then looked at about 280 risky claims on purpose; that look found one claim wrong and one
# unsharp. Copied from the tables "Richtig, aber unscharf formuliert" and "Zusatzprobe" of
# AUDIT_D_rule_claims.md and the sample file audit_D_rule_claims.jsonl (tests compare them);
# ``index`` is the claim's position in the card's ``rule_claims``.

AUDIT_D_SOURCE: Final = (
    "Audit D der Regelclaims, data/research/chulane_rubric_v2_20261118/audit/AUDIT_D_rule_claims.md"
)
AUDIT_D_SAMPLE: Final = "Zufallsstichprobe (100 Claims): richtig, aber unscharf formuliert"
AUDIT_D_EXTRA: Final = "Zusatzprobe außerhalb der Zufallsstichprobe"


class ClaimFinding(TypedDict):
    card: str
    index: int
    verdict: str
    correction: str
    part: str
    reason_note: str | None


RULE_CLAIM_FINDINGS: Final[tuple[ClaimFinding, ...]] = (
    {
        "card": "Wavesifter",
        "index": 0,
        "verdict": "falsch",
        "correction": (
            "Das Opfern bei Evoke ist eine ausgelöste Fähigkeit (CR 702.74a). Mit ihr auf dem "
            "Stapel kann Chulane für {3},{T} Wavesifter auf die Hand zurückholen."
        ),
        "part": AUDIT_D_EXTRA,
        "reason_note": (
            "Die Begründung des Raters wiederholt den falschen Regelclaim („cannot be bounced“, "
            "Audit D)"
        ),
    },
    {
        "card": "Appeal to Eirdu",
        "index": 0,
        "verdict": "unscharf",
        "correction": "{W} zahlt nur eine weiße Kreatur; sonst {1} (CR 702.51).",
        "part": AUDIT_D_EXTRA,
        "reason_note": None,
    },
    {
        "card": "Hada Freeblade",
        "index": 0,
        "verdict": "unscharf formuliert",
        "correction": (
            "Chulanes Effekt ist kein Landspiel (CR 305.4); inhaltlich korrekt, an anderer Stelle "
            "(Augur of Autumn, Explore) trennt der Rater das sauber."
        ),
        "part": AUDIT_D_SAMPLE,
        "reason_note": None,
    },
    {
        "card": "Molder Beast",
        "index": 0,
        "verdict": "unscharf formuliert",
        "correction": "Das Land ist optional („may“) und braucht eine Landkarte auf der Hand.",
        "part": AUDIT_D_SAMPLE,
        "reason_note": None,
    },
    {
        "card": "Tam, Observant Sequencer // Deep Sight",
        "index": 0,
        "verdict": "unscharf formuliert",
        "correction": "Ist Tam schon vorbereitet, entsteht keine zweite Kopie (Ruling).",
        "part": AUDIT_D_SAMPLE,
        "reason_note": None,
    },
    {
        "card": "Mindseeker Oculus",
        "index": 2,
        "verdict": "unscharf formuliert",
        "correction": (
            "Nur eine Loyalitätsfähigkeit je Zug (CR 606.3); der Wert verteilt sich auf zwei Züge."
        ),
        "part": AUDIT_D_SAMPLE,
        "reason_note": None,
    },
    {
        "card": "Strixhaven Skycoach",
        "index": 2,
        "verdict": "unscharf formuliert",
        "correction": (
            "Stimmt für die Karte allein; Chulane selbst kann nicht bemannen und danach noch {T} "
            "zahlen."
        ),
        "part": AUDIT_D_SAMPLE,
        "reason_note": None,
    },
)
