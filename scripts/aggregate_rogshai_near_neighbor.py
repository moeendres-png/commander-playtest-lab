from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, stdev

EXISTING = tuple(f"C{i:03d}" for i in range(1, 49))
NEW = tuple(f"N{i:03d}" for i in range(1, 17))
CANDIDATES = EXISTING + NEW
OPPONENTS = ("kaervek", "blight", "dance", "lorehold", "doom", "wakanda")

METRICS = {
    "first_place": ("candidate_first_place", 1),
    "placement": ("candidate_placement", -1),
    "damage": ("candidate_damage", 1),
    "commander_damage": ("candidate_commander_damage", 1),
    "cards_drawn": ("candidate_cards_drawn", 1),
    "mulligans": ("candidate_mulligans", -1),
    "lands_played": ("candidate_lands_played", 1),
    "ramp_resolved": ("candidate_ramp_resolved", 1),
    "first_commander_cast_turn": ("candidate_first_commander_cast_turn", -1),
    "ishai_peak_power": ("candidate_ishai_peak_power", 1),
    "protections_resolved": ("candidate_protections_resolved", 1),
    "turns": ("turns", -1),
}


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: list[float]) -> float | None:
    return fmean(values) if values else None


def _paired_values(amap: dict[int, dict], bmap: dict[int, dict], field: str) -> list[float]:
    values = []
    for key in sorted(set(amap) & set(bmap)):
        av = amap[key].get(field)
        bv = bmap[key].get(field)
        if av is None or bv is None:
            continue
        values.append(float(av) - float(bv))
    return values


def _normal_ci(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    mean = fmean(values)
    if len(values) < 2:
        return mean, mean, mean
    se = stdev(values) / math.sqrt(len(values))
    return mean, mean - 1.96 * se, mean + 1.96 * se


def _bootstrap_ci(values: list[float], key: str, iterations: int = 5000) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    raw = hashlib.sha256(key.encode()).digest()
    rng = random.Random(int.from_bytes(raw[:8], "big"))
    n = len(values)
    means = []
    for _ in range(iterations):
        means.append(fmean(values[rng.randrange(n)] for _ in range(n)))
    means.sort()
    low = means[int(0.025 * (iterations - 1))]
    high = means[int(0.975 * (iterations - 1))]
    return low, high


def _direction_from_ci(mean: float | None, low: float | None, high: float | None, favorable_sign: int) -> str:
    if mean is None or low is None or high is None:
        return "UNMEASURED"
    if low > 0:
        return "A" if favorable_sign > 0 else "B"
    if high < 0:
        return "B" if favorable_sign > 0 else "A"
    return "UNRESOLVED"


def _classify(primary: dict[str, dict]) -> tuple[str, str]:
    fp = primary["first_place"]["direction"]
    placement = primary["placement"]["direction"]
    supported = {value for value in (fp, placement) if value in {"A", "B"}}
    if len(supported) == 2:
        return "MIXED", "Primary matched outcomes significantly disagree in direction."
    if len(supported) == 1:
        direction = next(iter(supported))
        other = placement if fp in {"A", "B"} else fp
        if other in {"A", "B"} and other != direction:
            return "MIXED", "Primary matched outcomes disagree."
        return (
            "SUPPORTED_DIRECTION",
            f"At least one paired primary outcome has a 95% CI excluding zero in favor of {direction}, with no significant opposing primary outcome.",
        )
    fp_mean = primary["first_place"]["mean_diff"]
    pl_mean = primary["placement"]["mean_diff"]
    if fp_mean is None or pl_mean is None:
        return "INSUFFICIENT_MATCHED_EVIDENCE", "Primary paired metrics unavailable."
    fp_point = "A" if fp_mean > 0 else "B" if fp_mean < 0 else "TIE"
    pl_point = "A" if pl_mean < 0 else "B" if pl_mean > 0 else "TIE"
    if fp_point in {"A", "B"} and pl_point in {"A", "B"} and fp_point != pl_point:
        return (
            "MIXED",
            "Point estimates for first-place and placement move in opposite directions; neither direction is sufficiently resolved.",
        )
    return (
        "INSUFFICIENT_MATCHED_EVIDENCE",
        "Matched comparison is directionally unresolved at the 95% interval level.",
    )


def _cell_pair(amap: dict[int, dict], bmap: dict[int, dict], keys: list[int]) -> dict:
    if not keys:
        return {"n": 0}
    fp = [float(amap[k]["candidate_first_place"] - bmap[k]["candidate_first_place"]) for k in keys]
    pl = [float(amap[k]["candidate_placement"] - bmap[k]["candidate_placement"]) for k in keys]
    return {
        "n": len(keys),
        "a_minus_b_first_place": fmean(fp),
        "a_minus_b_placement": fmean(pl),
    }


def _paired_result(by_candidate: dict[str, list[dict]], pair: dict) -> dict:
    a, b = pair["a"], pair["b"]
    amap = {int(row["scenario_index"]): row for row in by_candidate[a]}
    bmap = {int(row["scenario_index"]): row for row in by_candidate[b]}
    keys = sorted(set(amap) & set(bmap))
    if len(keys) != 80:
        raise SystemExit(f"paired comparison {a}/{b} has {len(keys)} rows, expected 80")

    metric_results: dict[str, dict] = {}
    for metric, (field, favorable_sign) in METRICS.items():
        values = _paired_values(amap, bmap, field)
        mean, normal_low, normal_high = _normal_ci(values)
        boot_low, boot_high = _bootstrap_ci(values, f"{pair['question']}|{metric}")
        direction = _direction_from_ci(mean, boot_low, boot_high, favorable_sign)
        metric_results[metric] = {
            "n": len(values),
            "mean_diff": mean,
            "normal_95_low": normal_low,
            "normal_95_high": normal_high,
            "bootstrap_95_low": boot_low,
            "bootstrap_95_high": boot_high,
            "favorable_direction": "higher" if favorable_sign > 0 else "lower",
            "direction": direction,
        }

    classification, reason = _classify(metric_results)

    seat = {}
    for seat_num in range(1, 5):
        cell_keys = [k for k in keys if int(amap[k]["candidate_seat"]) == seat_num]
        seat[str(seat_num)] = _cell_pair(amap, bmap, cell_keys)

    opponent = {}
    for opp in OPPONENTS:
        cell_keys = [k for k in keys if opp in amap[k]["opponent_triplet"]]
        opponent[opp] = _cell_pair(amap, bmap, cell_keys)

    block = {}
    for block_num in range(1, 6):
        cell_keys = [k for k in keys if int(amap[k]["block"]) == block_num]
        block[str(block_num)] = _cell_pair(amap, bmap, cell_keys)

    fp_mean = metric_results["first_place"]["mean_diff"] or 0.0
    overall_direction = "A" if fp_mean > 0 else "B" if fp_mean < 0 else "TIE"
    block_directions = []
    for cell in block.values():
        value = float(cell["a_minus_b_first_place"])
        block_directions.append("A" if value > 0 else "B" if value < 0 else "TIE")
    sign_agree = sum(value == overall_direction for value in block_directions if value != "TIE")
    non_tie = sum(value != "TIE" for value in block_directions)

    worst_opponent_for_a = min(
        opponent,
        key=lambda name: (
            float(opponent[name]["a_minus_b_first_place"]),
            -float(opponent[name]["a_minus_b_placement"]),
        ),
    )
    worst_seat_for_a = min(
        seat,
        key=lambda name: (
            float(seat[name]["a_minus_b_first_place"]),
            -float(seat[name]["a_minus_b_placement"]),
        ),
    )

    return {
        **pair,
        "paired_games": len(keys),
        "classification": classification,
        "classification_reason": reason,
        "metric_results": metric_results,
        "seat_stratification": seat,
        "opponent_stratification": opponent,
        "block_seed_consistency": {
            "block_results": block,
            "overall_first_place_point_direction": overall_direction,
            "non_tie_blocks": non_tie,
            "blocks_agreeing_with_overall_first_place_direction": sign_agree,
            "note": "Five deterministic balanced blocks are consistency strata, not independent replications.",
        },
        "worst_case_for_candidate_a": {
            "opponent": worst_opponent_for_a,
            "opponent_result": opponent[worst_opponent_for_a],
            "seat": worst_seat_for_a,
            "seat_result": seat[worst_seat_for_a],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_root = Path(args.input_root)
    candidate_payload = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    result_paths = sorted(input_root.rglob("GAME_RESULTS.jsonl"))
    if len(result_paths) != 5:
        raise SystemExit(f"expected 5 block result files, got {len(result_paths)}")

    rows = []
    for path in result_paths:
        rows.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    if len(rows) != 5120:
        raise SystemExit(f"expected 5120 game rows, got {len(rows)}")
    if not all(row["completed"] and not row["aborted"] for row in rows):
        raise SystemExit("aggregate contains incomplete/aborted rows")
    if any("morcant" in row["opponent_triplet"] or "cosmic" in row["opponent_triplet"] for row in rows):
        raise SystemExit("Morcant/Cosmic appeared in primary lane")

    candidate_rows = candidate_payload.get("candidates")
    if not isinstance(candidate_rows, list) or len(candidate_rows) != 64:
        raise SystemExit("candidate payload malformed")
    if tuple(row["candidate_id"] for row in candidate_rows) != CANDIDATES:
        raise SystemExit("candidate payload IDs are not exact expected population")
    source = {str(row["candidate_id"]): row for row in candidate_rows}

    by_candidate: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_candidate[str(row["candidate_id"])].append(row)
    if set(by_candidate) != set(CANDIDATES):
        raise SystemExit("aggregate candidate population mismatch")

    summaries = []
    conditioned = []
    seat_conditioned = []
    robustness = []
    for candidate in CANDIDATES:
        cr = by_candidate[candidate]
        if len(cr) != 80 or len({int(row["master_seed"]) for row in cr}) != 80:
            raise SystemExit(f"{candidate} row/seed count mismatch")
        if Counter(int(row["candidate_seat"]) for row in cr) != Counter({1: 20, 2: 20, 3: 20, 4: 20}):
            raise SystemExit(f"{candidate} seat balance failed")
        presence = Counter(opp for row in cr for opp in row["opponent_triplet"])
        if presence != Counter({opp: 40 for opp in OPPONENTS}):
            raise SystemExit(f"{candidate} opponent balance failed")

        summary = {
            "candidate_id": candidate,
            "candidate_label": source[candidate].get("candidate_label"),
            "axis": source[candidate].get("near_neighbor_axis"),
            "parent_candidate_id": source[candidate].get("parent_candidate_id"),
            "land_count": source[candidate].get("land_count"),
            "games": 80,
            "first_place_fraction": fmean(float(r["candidate_first_place"]) for r in cr),
            "mean_placement": fmean(float(r["candidate_placement"]) for r in cr),
            "mean_damage": fmean(float(r["candidate_damage"]) for r in cr),
            "mean_commander_damage": fmean(float(r["candidate_commander_damage"]) for r in cr),
            "mean_cards_drawn": fmean(float(r["candidate_cards_drawn"]) for r in cr),
            "mean_mulligans": fmean(float(r["candidate_mulligans"]) for r in cr),
            "mean_lands_played": fmean(float(r["candidate_lands_played"]) for r in cr),
            "mean_ramp_resolved": fmean(float(r["candidate_ramp_resolved"]) for r in cr),
            "mean_first_commander_cast_turn": _mean(
                [float(r["candidate_first_commander_cast_turn"]) for r in cr if r["candidate_first_commander_cast_turn"] is not None]
            ),
            "commander_cast_observed_fraction": sum(r["candidate_first_commander_cast_turn"] is not None for r in cr) / len(cr),
            "mean_ishai_peak_power": fmean(float(r["candidate_ishai_peak_power"]) for r in cr),
            "mean_protections_resolved": fmean(float(r["candidate_protections_resolved"]) for r in cr),
            "mean_turns": fmean(float(r["turns"]) for r in cr),
        }
        summaries.append(summary)

        seat_fp = {}
        for seat_num in range(1, 5):
            cell = [r for r in cr if int(r["candidate_seat"]) == seat_num]
            seat_fp[seat_num] = fmean(float(r["candidate_first_place"]) for r in cell)
            seat_conditioned.append({
                "candidate_id": candidate,
                "seat": seat_num,
                "games": len(cell),
                "first_place_fraction": seat_fp[seat_num],
                "mean_placement": fmean(float(r["candidate_placement"]) for r in cell),
            })

        opp_fp = {}
        for opp in OPPONENTS:
            cell = [r for r in cr if opp in r["opponent_triplet"]]
            opp_fp[opp] = fmean(float(r["candidate_first_place"]) for r in cell)
            conditioned.append({
                "candidate_id": candidate,
                "opponent": opp,
                "games": len(cell),
                "first_place_fraction": opp_fp[opp],
                "mean_placement": fmean(float(r["candidate_placement"]) for r in cell),
            })

        robustness.append({
            "candidate_id": candidate,
            "seat_fp_min": min(seat_fp.values()),
            "seat_fp_max": max(seat_fp.values()),
            "seat_fp_range": max(seat_fp.values()) - min(seat_fp.values()),
            "opponent_fp_min": min(opp_fp.values()),
            "opponent_fp_max": max(opp_fp.values()),
            "opponent_fp_range": max(opp_fp.values()) - min(opp_fp.values()),
            "worst_opponent": min(opp_fp, key=opp_fp.get),
            "worst_opponent_fp": min(opp_fp.values()),
        })

    ranked = sorted(
        summaries,
        key=lambda r: (
            -float(r["first_place_fraction"]),
            float(r["mean_placement"]),
            -float(r["mean_damage"]),
            str(r["candidate_id"]),
        ),
    )
    ranked = [{"rank": i, **row} for i, row in enumerate(ranked, start=1)]
    _write_csv(output / "RANKING_ALL_64.csv", ranked, list(ranked[0]))
    _write_csv(output / "ROBUSTNESS_ALL_64.csv", robustness, list(robustness[0]))
    _write_csv(output / "OPPONENT_CONDITIONED_ALL_64.csv", conditioned, list(conditioned[0]))
    _write_csv(output / "SEAT_CONDITIONED_ALL_64.csv", seat_conditioned, list(seat_conditioned[0]))

    focus_pairs = candidate_payload.get("focus_comparisons")
    if not isinstance(focus_pairs, list) or len(focus_pairs) != 17:
        raise SystemExit("expected exactly 17 focus comparisons")
    focus = [_paired_result(by_candidate, pair) for pair in focus_pairs]
    (output / "FOCUS_PAIR_RESULTS.json").write_text(
        json.dumps(focus, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    focus_flat = []
    for result in focus:
        fp = result["metric_results"]["first_place"]
        pl = result["metric_results"]["placement"]
        dmg = result["metric_results"]["damage"]
        draw = result["metric_results"]["cards_drawn"]
        mull = result["metric_results"]["mulligans"]
        cmd = result["metric_results"]["first_commander_cast_turn"]
        focus_flat.append({
            "question": result["question"],
            "candidate_a": result["a"],
            "candidate_b": result["b"],
            "a_slot": result["a_slot"],
            "b_slot": result["b_slot"],
            "classification": result["classification"],
            "fp_diff": fp["mean_diff"],
            "fp_boot_low": fp["bootstrap_95_low"],
            "fp_boot_high": fp["bootstrap_95_high"],
            "placement_diff": pl["mean_diff"],
            "placement_boot_low": pl["bootstrap_95_low"],
            "placement_boot_high": pl["bootstrap_95_high"],
            "damage_diff": dmg["mean_diff"],
            "cards_drawn_diff": draw["mean_diff"],
            "mulligans_diff": mull["mean_diff"],
            "first_commander_cast_turn_diff": cmd["mean_diff"],
            "worst_opponent_for_a": result["worst_case_for_candidate_a"]["opponent"],
            "block_first_place_sign_agreement": (
                f"{result['block_seed_consistency']['blocks_agreeing_with_overall_first_place_direction']}/"
                f"{result['block_seed_consistency']['non_tie_blocks']}"
            ),
        })
    _write_csv(output / "FOCUS_PAIR_RESULTS.csv", focus_flat, list(focus_flat[0]))

    with (output / "GAME_RESULTS.jsonl").open("w", encoding="utf-8") as handle:
        for row in sorted(rows, key=lambda item: (item["candidate_id"], int(item["scenario_index"]))):
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    report = {
        "schema_version": "rogshai-near-neighbor-aggregate-1.0.0",
        "status": "PASS",
        "evidence_class": "structural_model_estimates",
        "engine_version": "structural-0.6.2",
        "fidelity_engine_version": "structural-fidelity-overlay-2026-08-25-v2",
        "total_games": 5120,
        "candidate_count": 64,
        "existing_candidates_admitted": 48,
        "new_theorycraft_candidates_admitted": 16,
        "pre_gameplay_candidate_elimination": 0,
        "games_per_candidate": 80,
        "opponents": list(OPPONENTS),
        "opponent_appearances_per_candidate_each": 40,
        "cosmic_games": 0,
        "morcant_games": 0,
        "focus_pair_count": 17,
        "all_focus_pairs_exactly_one_replacement_slot": True,
        "focus_classification_counts": dict(Counter(result["classification"] for result in focus)),
        "ranking_basis": "post-fix Structural model sample only; not empirical Commander win rate",
        "ranking": [row["candidate_id"] for row in ranked],
        "not_measured": [
            "literal spell-throughput count in StructuralPlayerMetrics",
            "colored_mana_failures",
            "stranded_spells",
            "unused_mana",
        ],
    }
    (output / "AGGREGATE_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
