#!/usr/bin/env python3
"""Build the compact card-understanding data set from raw rater output (rubric v2.1).

Input: JSON lines of rater ratings (``rater``, ``batch``, ``version``, ``card``, ``oracle_id``,
``scores``, ``notes``, ``reason``, ``confidence``, ...), for example the ``fullrun_ratings
.jsonl`` of the rubric research folder. A ``model`` field in the input is ignored; the tier of the
rater is the optional ``rater_tier`` field of a line, else ``--rater-tier``.

Output: one line per ``oracle_id`` in ``data/card_understanding/card_understanding_v2_1.jsonl``,
sorted by card name, with the rules of the Studio loader (``studio/card_understanding.py``):

* Versions: only the versions of ``--versions`` are read, first named = highest priority. A card
  takes its rating from the best version that has one; ratings of a lower version are used only
  for a card without a better one. Default: ``v2.1`` only.
* One rating per card. Several raters of the chosen version: the score is the mean per
  criterion, ``score_sd`` the standard deviation of the raters (sample, None for one rater: an
  unknown spread is not 0), ``raters`` their number, ``confidence`` the lowest of them, and the
  text fields (reason, notes, rule claims) come from the rater whose H is closest to the mean H
  (ties: rater, batch).
* Scores are rounded to multiples of 5 (half up); ``rounded`` is true when any value changed.
* ``rater_tier``: ``small`` when any of the raters is small, else ``large``.

Every output line is checked with the loader's own validation; a broken input line stops the run
with exit code 2 and writes nothing. ``--check`` compares the result with the existing file.

    python scripts/import_card_understanding.py RATINGS.jsonl [RATINGS2.jsonl ...]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if (REPO_ROOT / "src").is_dir():
    sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.studio import card_understanding as cu  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "data" / "card_understanding" / "card_understanding_v2_1.jsonl"
_COPIED = ("oracle_id", "card", "scores", "notes", "reason", "confidence")


def round5(value: float) -> int:
    """Nearest multiple of 5, halves up."""
    return int((value + cu.STEP / 2) // cu.STEP) * cu.STEP


def read_ratings(
    paths: list[Path], versions: list[str], default_tier: str
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """The accepted rater lines, each with its resolved ``rater_tier``, plus counts of what was
    skipped. Raises ``cu.UnderstandingDataError`` for lines that are not usable."""
    accepted: list[dict[str, object]] = []
    skipped: dict[str, int] = defaultdict(int)
    errors: list[str] = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            where = f"{path.name}:{number}"
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                errors.append(f"{where}: not valid JSON ({error.msg})")
                continue
            if not isinstance(raw, dict):
                errors.append(f"{where}: not a JSON object")
                continue
            version = raw.get("version")
            if version not in versions:
                skipped[f"version {version}"] += 1
                continue
            tier = raw.get("rater_tier", default_tier)
            probe = {key: raw[key] for key in _COPIED if key in raw}
            probe.update(
                {
                    "rule_claims": raw.get("rule_claims", []),
                    "version": version,
                    "rater_tier": tier,
                    "rubric": cu.DATASET_RUBRIC,
                }
            )
            try:
                # scores may be off the 5-grid in raw input (rounded below), so check the range
                # and structure here with the loader and the grid when building the line
                cu.parse_row(probe)
            except cu.UnderstandingDataError as error:
                errors.append(f"{where}: {error}")
                continue
            raw["rater_tier"] = tier
            accepted.append(raw)
    if errors:
        shown = "; ".join(errors[:10])
        more = f" (+{len(errors) - 10} more)" if len(errors) > 10 else ""
        raise cu.UnderstandingDataError(f"{len(errors)} unusable input line(s): {shown}{more}")
    return accepted, dict(skipped)


def _lowest_confidence(rows: list[dict[str, object]]) -> str:
    order = {level: index for index, level in enumerate(reversed(cu.CONFIDENCE_LEVELS))}
    return min((str(row["confidence"]) for row in rows), key=lambda level: order[level])


def combine(rows: list[dict[str, object]], version: str) -> cu.UnderstandingRow:
    """One data set line from the ratings (one version) of one card."""
    scores_by_rater = [dict(row["scores"]) for row in rows]  # type: ignore[call-overload]
    means = {
        name: sum(float(item[name]) for item in scores_by_rater) / len(rows) for name in cu.CRITERIA
    }
    scores: dict[str, float] = {name: round5(value) for name, value in means.items()}
    rounded = any(
        scores[name] != float(item[name]) for item in scores_by_rater for name in cu.CRITERIA
    )
    spread: dict[str, float] | None = None
    if len(rows) > 1:
        spread = {
            name: round(statistics.stdev(float(item[name]) for item in scores_by_rater), 2)
            for name in cu.CRITERIA
        }
    source = min(
        rows,
        key=lambda row: (
            abs(float(row["scores"]["H"]) - means["H"]),  # type: ignore[index]
            str(row.get("rater", "")),
            str(row.get("batch", "")),
        ),
    )
    tier = "small" if any(row["rater_tier"] == "small" for row in rows) else "large"
    line: cu.UnderstandingRow = {
        "oracle_id": str(source["oracle_id"]),
        "card": str(source["card"]),
        "scores": scores,
        "confidence": _lowest_confidence(rows),
        "reason": str(source["reason"]),
        "notes": dict(source["notes"]),  # type: ignore[call-overload]
        "rule_claims": list(source.get("rule_claims") or []),  # type: ignore[call-overload]
        "version": version,
        "rater_tier": tier,
        "rubric": cu.DATASET_RUBRIC,
        "raters": len(rows),
        "score_sd": spread,
        "rounded": rounded,
    }
    uncertainty = source.get("uncertainty")
    if isinstance(uncertainty, str) and uncertainty.strip():
        line["uncertainty"] = uncertainty
    return line


def build(
    ratings: list[dict[str, object]], versions: list[str]
) -> tuple[list[cu.UnderstandingRow], dict[str, int]]:
    """The data set lines (sorted by card name) and how many cards each version supplied."""
    by_card: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(lambda: defaultdict(list))
    for row in ratings:
        by_card[str(row["oracle_id"])][str(row["version"])].append(row)
    lines: list[cu.UnderstandingRow] = []
    used: dict[str, int] = defaultdict(int)
    for per_version in by_card.values():
        version = next(name for name in versions if name in per_version)
        used[version] += 1
        lines.append(combine(per_version[version], version))
    lines.sort(key=lambda line: (line["card"].casefold(), line["oracle_id"]))
    cu.parse_lines([json.dumps(line) for line in lines])  # same checks as the loader (and dupes)
    return lines, dict(used)


def render(lines: list[cu.UnderstandingRow]) -> str:
    return "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="rater ratings, JSON lines")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="data set file to write")
    parser.add_argument(
        "--versions",
        default=cu.DATASET_VERSION,
        help="comma-separated rater versions to read, best first (default: %(default)s)",
    )
    parser.add_argument(
        "--rater-tier",
        choices=cu.RATER_TIERS,
        default="large",
        help="tier of lines that carry no rater_tier (default: %(default)s)",
    )
    parser.add_argument(
        "--check", action="store_true", help="do not write; exit 1 if --out differs"
    )
    args = parser.parse_args(argv)
    versions = [name.strip() for name in args.versions.split(",") if name.strip()]
    try:
        ratings, skipped = read_ratings(args.inputs, versions, args.rater_tier)
        lines, used = build(ratings, versions)
    except cu.UnderstandingDataError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    text = render(lines)
    summary = (
        f"{len(lines)} cards from {len(ratings)} ratings; by version {used}; "
        f"skipped {skipped or 'none'}; "
        f"rounded {sum(1 for line in lines if line.get('rounded'))}; "
        f"several raters {sum(1 for line in lines if line.get('raters', 1) > 1)}"
    )
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.is_file() else None
        print(summary)
        if current != text:
            print(f"{args.out} is out of date", file=sys.stderr)
            return 1
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
