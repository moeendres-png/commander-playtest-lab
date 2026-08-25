from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean

CANDIDATES = tuple(f"C{i:03d}" for i in range(1, 49))
OPPONENTS = ("kaervek", "blight", "dance", "lorehold", "doom", "wakanda")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _paired(by_candidate: dict[str, list[dict]], a: str, b: str) -> dict:
    amap = {int(row["scenario_index"]): row for row in by_candidate[a]}
    bmap = {int(row["scenario_index"]): row for row in by_candidate[b]}
    keys = sorted(set(amap) & set(bmap))
    if len(keys) != 160:
        raise SystemExit(f"paired comparison {a}/{b} has {len(keys)} rows, expected 160")
    return {
        "candidate_a": a,
        "candidate_b": b,
        "paired_games": len(keys),
        "a_minus_b_first_place": fmean(
            float(amap[key]["candidate_first_place"] - bmap[key]["candidate_first_place"])
            for key in keys
        ),
        "a_minus_b_placement": fmean(
            float(amap[key]["candidate_placement"] - bmap[key]["candidate_placement"])
            for key in keys
        ),
        "a_minus_b_damage": fmean(
            float(amap[key]["candidate_damage"] - bmap[key]["candidate_damage"])
            for key in keys
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    result_paths = sorted(input_root.rglob("GAME_RESULTS.jsonl"))
    if len(result_paths) != 10:
        raise SystemExit(f"expected 10 block result files, got {len(result_paths)}")

    rows: list[dict] = []
    for path in result_paths:
        rows.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    if len(rows) != 7680:
        raise SystemExit(f"expected 7680 game rows, got {len(rows)}")
    if not all(row["completed"] and not row["aborted"] for row in rows):
        raise SystemExit("aggregate contains incomplete/aborted rows")
    if any("morcant" in row["opponent_triplet"] or "cosmic" in row["opponent_triplet"] for row in rows):
        raise SystemExit("Morcant/Cosmic appeared in the equalization lane")

    by_candidate: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_candidate[str(row["candidate_id"])].append(row)
    if set(by_candidate) != set(CANDIDATES):
        raise SystemExit("aggregate candidate population is not exactly C001..C048")

    summaries: list[dict] = []
    robustness: list[dict] = []
    conditioned: list[dict] = []
    seat_conditioned: list[dict] = []

    for candidate in CANDIDATES:
        candidate_rows = by_candidate[candidate]
        if len(candidate_rows) != 160:
            raise SystemExit(f"{candidate} has {len(candidate_rows)} rows, expected 160")
        if len({int(row["master_seed"]) for row in candidate_rows}) != 160:
            raise SystemExit(f"{candidate} does not have 160 unique seeds")
        seat_counts = Counter(int(row["candidate_seat"]) for row in candidate_rows)
        if seat_counts != Counter({1: 40, 2: 40, 3: 40, 4: 40}):
            raise SystemExit(f"{candidate} seat balance failed: {dict(seat_counts)}")
        opponent_presence = Counter(
            opponent for row in candidate_rows for opponent in row["opponent_triplet"]
        )
        if opponent_presence != Counter({opponent: 80 for opponent in OPPONENTS}):
            raise SystemExit(f"{candidate} opponent balance failed: {dict(opponent_presence)}")

        first_place = fmean(float(row["candidate_first_place"]) for row in candidate_rows)
        mean_placement = fmean(float(row["candidate_placement"]) for row in candidate_rows)
        mean_damage = fmean(float(row["candidate_damage"]) for row in candidate_rows)
        mean_cards = fmean(float(row["candidate_cards_drawn"]) for row in candidate_rows)
        mean_turns = fmean(float(row["turns"]) for row in candidate_rows)

        seat_fp: dict[int, float] = {}
        for seat in range(1, 5):
            cell = [row for row in candidate_rows if int(row["candidate_seat"]) == seat]
            seat_fp[seat] = fmean(float(row["candidate_first_place"]) for row in cell)
            seat_conditioned.append(
                {
                    "candidate_id": candidate,
                    "seat": seat,
                    "games": len(cell),
                    "first_place_fraction": seat_fp[seat],
                    "mean_placement": fmean(float(row["candidate_placement"]) for row in cell),
                }
            )

        opponent_fp: dict[str, float] = {}
        opponent_place: dict[str, float] = {}
        for opponent in OPPONENTS:
            cell = [row for row in candidate_rows if opponent in row["opponent_triplet"]]
            if len(cell) != 80:
                raise SystemExit(f"{candidate}/{opponent} cell has {len(cell)} rows")
            opponent_fp[opponent] = fmean(float(row["candidate_first_place"]) for row in cell)
            opponent_place[opponent] = fmean(float(row["candidate_placement"]) for row in cell)
            conditioned.append(
                {
                    "candidate_id": candidate,
                    "opponent": opponent,
                    "games_with_opponent": len(cell),
                    "first_place_fraction": opponent_fp[opponent],
                    "mean_placement": opponent_place[opponent],
                }
            )

        triplets: dict[tuple[str, ...], list[dict]] = defaultdict(list)
        for row in candidate_rows:
            triplets[tuple(sorted(row["opponent_triplet"]))].append(row)
        if len(triplets) != 20 or set(map(len, triplets.values())) != {8}:
            raise SystemExit(f"{candidate} triplet replication structure failed")
        triplet_fp = {
            "+".join(key): fmean(float(row["candidate_first_place"]) for row in value)
            for key, value in triplets.items()
        }

        summaries.append(
            {
                "candidate_id": candidate,
                "games": 160,
                "first_place_fraction": first_place,
                "mean_placement": mean_placement,
                "mean_damage": mean_damage,
                "mean_cards_drawn": mean_cards,
                "mean_turns": mean_turns,
            }
        )
        robustness.append(
            {
                "candidate_id": candidate,
                "seat_fp_min": min(seat_fp.values()),
                "seat_fp_max": max(seat_fp.values()),
                "seat_fp_range": max(seat_fp.values()) - min(seat_fp.values()),
                "opponent_fp_min": min(opponent_fp.values()),
                "opponent_fp_max": max(opponent_fp.values()),
                "opponent_fp_range": max(opponent_fp.values()) - min(opponent_fp.values()),
                "triplet_fp_min": min(triplet_fp.values()),
                "triplet_fp_max": max(triplet_fp.values()),
                "triplet_fp_range": max(triplet_fp.values()) - min(triplet_fp.values()),
                "worst_opponent": min(opponent_fp, key=opponent_fp.get),
                "worst_opponent_fp": min(opponent_fp.values()),
                "best_opponent": max(opponent_fp, key=opponent_fp.get),
                "best_opponent_fp": max(opponent_fp.values()),
                "seat_values": json.dumps(seat_fp, sort_keys=True),
                "opponent_values": json.dumps(opponent_fp, sort_keys=True),
                "opponent_mean_placements": json.dumps(opponent_place, sort_keys=True),
            }
        )

    summaries.sort(
        key=lambda row: (
            -float(row["first_place_fraction"]),
            float(row["mean_placement"]),
            -float(row["mean_damage"]),
            str(row["candidate_id"]),
        )
    )
    ranked = []
    for rank, row in enumerate(summaries, start=1):
        ranked.append({"rank": rank, **row})

    _write_csv(output / "RANKING_ALL_48.csv", ranked, list(ranked[0]))
    _write_csv(output / "ROBUSTNESS_ALL_48.csv", robustness, list(robustness[0]))
    _write_csv(output / "OPPONENT_CONDITIONED_ALL_48.csv", conditioned, list(conditioned[0]))
    _write_csv(output / "SEAT_CONDITIONED_ALL_48.csv", seat_conditioned, list(seat_conditioned[0]))

    focus_pairs = (
        ("C029", "C030"),
        ("C029", "C043"),
        ("C030", "C043"),
        ("C011", "C029"),
        ("C011", "C030"),
        ("C020", "C029"),
        ("C020", "C030"),
        ("C043", "C048"),
    )
    focus = [_paired(by_candidate, a, b) for a, b in focus_pairs]
    (output / "FOCUS_PAIRED_COMPARISONS.json").write_text(
        json.dumps(focus, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with (output / "GAME_RESULTS.jsonl").open("w", encoding="utf-8") as handle:
        for row in sorted(rows, key=lambda item: (item["candidate_id"], int(item["scenario_index"]))):
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    report = {
        "schema_version": "rogshai-postfix-opponent-balance-aggregate-1.0.0",
        "status": "PASS",
        "evidence_class": "structural_model_estimates",
        "engine_version": "structural-0.6.2",
        "fidelity_engine_version": "structural-fidelity-overlay-2026-08-25-v2",
        "total_games": 7680,
        "candidate_count": 48,
        "games_per_candidate": 160,
        "opponents": list(OPPONENTS),
        "opponent_appearances_per_candidate_each": 80,
        "cumulative_after": {
            "morcant": 192,
            "kaervek": 192,
            "blight": 192,
            "dance": 192,
            "lorehold": 192,
            "doom": 192,
            "wakanda": 192,
        },
        "cosmic_new_games": 0,
        "morcant_new_games": 0,
        "pre_gameplay_candidate_elimination": 0,
        "ranking_basis": "post-fix Structural model sample only; not empirical Commander win rate",
        "ranking": [row["candidate_id"] for row in ranked],
    }
    (output / "AGGREGATE_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
