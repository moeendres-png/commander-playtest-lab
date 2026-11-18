"""S3, offline: derive the commander rows from the raw pages of one S3 run.

Input: ``raw/list_p*.body`` (and ``raw/turn_damage_chulane_*.body`` when present) written by
``fetch_s3_playgroup.py``. No network. The raw pages still contain ``top_decks``, deck owner names and
ratings, so they are DELETED once the rows are derived (only hash and size stay in the manifest);
``--keep-raw`` keeps them and the manifest then says so (``raw_contains_excluded_fields: true``,
``personal_data`` no longer "none"). Output:

* ``derived/playgroup_commanders.jsonl``: one row per commander with the list fields.
  IMPORTANT, the names are the truth about what is counted: ``rated_seats_played`` and
  ``rated_seats_won`` are RATED SEATS (a seat with a salt rating in a finished game with a win
  condition; two decks of the same commander in one game count twice), not games. Do not mix the
  figures with the single-commander endpoint (a different counting rule, about twice as many).
  ``wins_exceed_games`` flags rows with more wins than seats (a source defect at tiny numbers,
  documented, not corrected); ``placeholder`` flags non-positive ids (id -2 "Guest Commander").
* ``derived/chulane_turn_damage.json`` (when the raw answer exists): mean per single EVENT per
  round, no n, with self damage and undone events, with outliers: NOT reliable, never a damage curve.

Dropped: ``average_salt_rating``, ``average_fun_rating``, ``top_decks`` and image or Scryfall fields.
``pilot_count`` is a count of distinct owners, not a person.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

KEEP_MEAN = [
    "average_turn_time",
    "average_round_amount",
    "average_damage_per_game",
    "average_normal_damage_per_game",
    "average_commander_damage_per_game",
    "average_poison_tokens_per_game",
    "average_healing_per_game",
    "average_mulligans_taken",
]
KEEP_WIN = [
    "combat_win_count",
    "combo_win_count",
    "commander_damage_win_count",
    "mill_win_count",
    "non_combat_damage_win_count",
    "poison_win_count",
    "alternative_win_count",
]
DROPPED = [
    "average_salt_rating",
    "average_fun_rating",
    "top_decks",
    "scryfall_id",
    "art_crop_url",
    "normal_url",
    "card_image",
]
COHORT = "playgroup_bewertete_sitze"
TURN_DAMAGE_WARNING = (
    "NICHT BELASTBAR: Mittelwert je Einzelereignis je Runde, kein Rundenwert und kein Wert je "
    "Spiel/Sitz; ohne n je Runde; enthaelt Selbstschaden und rueckgaengig gemachte Ereignisse; "
    "Ausreisser vorhanden. Nicht als Schadenskurve verwenden; hoechstens 'vorhanden, nicht belastbar' fuehren."
)


def number(value: Any) -> Any:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def commander_row(item: dict[str, Any]) -> dict[str, Any]:
    played, won = item.get("game_played_count"), item.get("game_win_count")
    row: dict[str, Any] = {
        "id": item["id"],
        "name": item["name"],
        "playgroup_url": item.get("playgroup_url"),
        "color_identity": "".join(item.get("color_identity") or []),
        "rated_seats_played": played,
        "rated_seats_won": won,
        "pilot_count": item.get("pilot_count"),
        "global_elo": item.get("global_elo"),
    }
    for key in KEEP_MEAN:
        row[key] = number(item.get(key))
    for key in KEEP_WIN:
        row[key] = item.get(key)
    row["wins_exceed_games"] = bool(won is not None and played is not None and won > played)
    row["placeholder"] = isinstance(item["id"], int) and item["id"] <= 0
    row["cohort"] = COHORT
    row["data_class"] = "beobachtetes_spiel"
    row["source_package"] = "playgroup_public_api_v1"
    row["personal_data"] = "none"
    return row


def _float(value: Any) -> float | None:
    """A number or None: a missing or unreadable value is UNKNOWN, never 0."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result != result else result


def _extreme(series: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    valid = [(v, t) for t in series if (v := _float(t.get(key))) is not None]
    if not valid:
        return None
    value, turn = max(valid, key=lambda pair: pair[0])
    return {"turn": turn.get("turn"), "value": value}


def turn_damage_document(raw: dict[str, Any]) -> dict[str, Any]:
    series = raw.get("average_turn_data", [])
    damage = [v for t in series if (v := _float(t.get("normal_damage"))) is not None]
    return {
        "id": raw["id"],
        "name": raw["name"],
        "playgroup_url": raw.get("playgroup_url"),
        "data_class": "beobachtetes_spiel",
        "cohort": COHORT,
        "warning": TURN_DAMAGE_WARNING,
        "outliers": {
            "max_normal_damage": _extreme(series, "normal_damage"),
            "max_healing": _extreme(series, "healing"),
            "median_normal_damage_over_turns": statistics.median(damage) if damage else None,
        },
        "average_turn_data": series,
    }


def derive(run_dir: Path) -> dict[str, Any]:
    raw = run_dir / "raw"
    derived = run_dir / "derived"
    rows: list[dict[str, Any]] = []
    rows_in = 0
    dropped_seen: set[str] = set()
    for name in sorted(raw.glob("list_p*.body")):
        items = json.loads(common.read_limited_text(name, common.MAX_LINE_BYTES))
        rows_in += len(items)
        for item in items:
            dropped_seen.update(key for key in item if key in DROPPED)
            rows.append(commander_row(item))
    with common.open_text_out(derived / "playgroup_commanders.jsonl") as writer:
        for row in rows:
            writer.write(json.dumps(row, ensure_ascii=False) + "\n")
    turn_damage_files = sorted(raw.glob("turn_damage_chulane_*.body"))
    if turn_damage_files:
        document = turn_damage_document(
            json.loads(common.read_limited_text(turn_damage_files[0], common.MAX_LINE_BYTES))
        )
        common.write_json(derived / "chulane_turn_damage.json", document)
    return {
        "rows_in": rows_in,
        "rows_out": len(rows),
        "turn_damage_derived": bool(turn_damage_files),
        "dropped_source_fields_seen": sorted(dropped_seen),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True, help="S3 run folder")
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="keep raw/ (the pages contain top_decks, owner names and ratings the derived rows "
        "drop); default: delete it after deriving",
    )
    args = parser.parse_args(argv)
    run_dir = common.assert_outside_repository(args.run_dir)
    try:
        counts = derive(run_dir)
    except (common.WaveError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    derived = run_dir / "derived"
    entries = [
        common.derived_entry(
            derived / "playgroup_commanders.jsonl",
            run_dir,
            rows_in=counts["rows_in"],
            dropped_fields=DROPPED,
            cohort_scope=COHORT,
            data_class="beobachtetes_spiel",
        )
    ]
    if counts["turn_damage_derived"]:
        entries.append(
            common.derived_entry(
                derived / "chulane_turn_damage.json", run_dir, warning="not reliable"
            )
        )
    common.update_manifest(
        run_dir,
        {
            "rows_in": counts["rows_in"],
            "rows_out": counts["rows_out"],
            "dropped_fields": DROPPED,
            "field_mapping_source_to_derived": {
                "game_played_count": "rated_seats_played (rated seats, NOT games)",
                "game_win_count": "rated_seats_won (rated seats won)",
                "pilot_count": "pilot_count (count of distinct owners, no person)",
                "(new)": "wins_exceed_games, placeholder (id <= 0), cohort",
            },
            "usage_rules": [
                "Use only rows with rated_seats_played >= 30 and wins_exceed_games == false; never placeholder rows.",
                "Never combine with the single-commander endpoint figures (a different counting rule).",
                "Name the selection bias: only rated seats; the win rate is higher than in the single endpoint.",
                "turn_damage is not reliable (mean per event per round, no n); at most 'present, not reliable'.",
                "Credit (CC BY 4.0): show the playgroup_url link of the row in every display.",
            ],
        },
        entries,
    )
    common.settle_raw(run_dir, keep=args.keep_raw)
    print(json.dumps(counts, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
