"""The card-understanding data set (Kartenverständnis, rubric v2.1): loader and validation.

One JSON line per card of the Chulane pool: seven scores E, F, T, R, K, D, H (0 to 100, higher is
better for the deck), a confidence, the rater's reason and notes, the rules claims the rating
relies on, and where the line came from (``version``, ``rater_tier``, ``rubric``). The file is
compact and derived: ``scripts/import_card_understanding.py`` builds it from the raw rater output.

This module only reads and checks. A broken line makes the whole load fail with the line numbers
(fail closed): a half-read data set would silently rank some cards without their rating. A card
the file does not list is unknown, never 0. The scores are a model rater's judgement of what a
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
    """The data set (or a line of it) violates the contract."""


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
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
    """The data set at ``path`` (default ``DATASET_PATH``). A missing file is an empty data set:
    no card is rated, none is 0."""
    target = DATASET_PATH if path is None else path
    if not target.is_file():
        return {}
    return parse_lines(target.read_text(encoding="utf-8").splitlines())


def stamp(path: Path | None = None) -> tuple[str, int, int] | None:
    """Identity of the data file (path, size, modification time) for cache keys; None if absent."""
    target = DATASET_PATH if path is None else path
    try:
        found = os.stat(target)
    except OSError:
        return None
    return (str(target), found.st_size, found.st_mtime_ns)
