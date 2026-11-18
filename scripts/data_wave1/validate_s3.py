"""S3, offline: validate the derived commander rows of one S3 run and write ``derived/validation.json``.

Checks (hard: PASS or FAIL): no duplicate commander id, every row carries its ``playgroup_url``
(credit duty, CC BY 4.0), no forbidden key (salt rating, user and deck-owner fields, top decks).
Reported as dated reference values (the source changes daily, no verdict): row count, whether the
commander Chulane is present, rows with more wins than seats, rows usable under the rule
"seats >= 30 and wins <= seats", the sum check of the win types per row, and (with ``--repo-csv``,
default ``data/research/deckbuilder_1655/playgroup_commander_stats.csv`` of the repo, read only) the
comparison of the list's rated seats with the games of that file for the commanders both contain.
The two figures are DIFFERENT cohorts (rated seats of the list against all games of the single
endpoint, by an undocumented rule): the number of differences is expected to be large and is never
an error; the figures are not combined.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

DEFAULT_CSV = (
    common.REPO_ROOT / "data" / "research" / "deckbuilder_1655" / "playgroup_commander_stats.csv"
)
WIN_TYPE_KEYS = (
    "combat_win_count",
    "combo_win_count",
    "commander_damage_win_count",
    "mill_win_count",
    "non_combat_damage_win_count",
    "poison_win_count",
    "alternative_win_count",
)
FORBIDDEN = (
    frozenset({"average_salt_rating", "average_fun_rating", "top_decks", "scryfall_id"})
    | common.PERSON_KEYS
)


def validate(rows: list[dict[str, Any]], csv_path: Path | None) -> dict[str, Any]:
    ids = [r["id"] for r in rows]
    forbidden: dict[str, int] = {}
    for row in rows:
        common.count_keys(row, FORBIDDEN, forbidden)
    exceed = [r for r in rows if r["wins_exceed_games"]]
    usable = [
        r
        for r in rows
        if (r["rated_seats_played"] or 0) >= 30
        and not r["wins_exceed_games"]
        and not r["placeholder"]
    ]
    sums_equal = sum(
        1 for r in rows if sum(r[k] or 0 for k in WIN_TYPE_KEYS) == (r["rated_seats_won"] or 0)
    )
    chulane = [r for r in rows if "chulane" in str(r["name"]).lower()]
    result: dict[str, Any] = {
        "commanders_out": len(rows),
        "duplicate_ids": len(ids) - len(set(ids)),
        "chulane_present": len(chulane) == 1,
        "chulane_rated_seats_played": chulane[0]["rated_seats_played"]
        if len(chulane) == 1
        else None,
        "chulane_rated_seats_won": chulane[0]["rated_seats_won"] if len(chulane) == 1 else None,
        "wins_exceed_games_rows": len(exceed),
        "wins_exceed_games_rows_with_0_seats": sum(
            1 for r in exceed if r["rated_seats_played"] == 0
        ),
        "max_excess": max(
            (r["rated_seats_won"] - r["rated_seats_played"] for r in exceed), default=0
        ),
        "max_seats_in_violating_rows": max((r["rated_seats_played"] for r in exceed), default=0),
        "placeholder_ids": [r["id"] for r in rows if r["placeholder"]],
        "rows_with_n_ge_30_and_wins_le_games": len(usable),
        "rows_without_playgroup_url": sum(1 for r in rows if not r.get("playgroup_url")),
        "rows_where_win_types_sum_to_rated_seats_won": sums_equal,
        "forbidden_key_counts": {k: forbidden.get(k, 0) for k in sorted(FORBIDDEN)},
    }
    if csv_path is not None and csv_path.is_file():
        by_id = {str(r["id"]): r for r in rows}
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reference = list(csv.DictReader(handle))
        matched = smaller = larger = equal = list_sum = csv_sum = 0
        for line in reference:
            row = by_id.get(line["commander_id"])
            if row is None:
                continue
            matched += 1
            seats, games = row["rated_seats_played"], int(line["games_count"])
            list_sum += seats
            csv_sum += games
            smaller += seats < games
            larger += seats > games
            equal += seats == games
        result["csv_comparison"] = {
            "csv_rows": len(reference),
            "csv_ids_in_list": matched,
            "csv_ids_missing_in_list": len(reference) - matched,
            "list_smaller_than_csv": smaller,
            "list_larger_than_csv": larger,
            "list_equal_csv": equal,
            "sum_rated_seats_list": list_sum,
            "sum_games_csv": csv_sum,
            "note": "two cohorts (list = rated seats; csv = single endpoint, other counting rule): never combine",
        }
    else:
        result["csv_comparison"] = "UNKNOWN: no csv file"
    result["checks"] = {
        "no_duplicate_commander_id": "PASS" if result["duplicate_ids"] == 0 else "FAIL",
        "every_row_has_playgroup_url": "PASS"
        if result["rows_without_playgroup_url"] == 0
        else "FAIL",
        "forbidden_fields_zero": "PASS" if not forbidden else "FAIL",
    }
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--repo-csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args(argv)
    run_dir = common.assert_outside_repository(args.run_dir)
    try:
        rows = list(common.iter_jsonl(run_dir / "derived" / "playgroup_commanders.jsonl"))
        result = validate(rows, args.repo_csv)
    except (common.WaveError, OSError, KeyError, ValueError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    target = run_dir / "derived" / "validation.json"
    common.write_json(target, result)
    common.update_manifest(
        run_dir,
        {"validation_summary": result["checks"]},
        [common.derived_entry(target, run_dir, kind="pruefbericht")],
    )
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if all(v != "FAIL" for v in result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
