from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean

CANDIDATES = tuple(f"C{i:03d}" for i in range(1, 49))
OPPONENTS = (
    "cosmic",
    "morcant",
    "kaervek",
    "blight",
    "dance",
    "lorehold",
    "doom",
    "wakanda",
)
WELL_SUPPORTED = ("kaervek", "blight", "dance", "lorehold", "doom", "wakanda")
OPPONENT_EVIDENCE_CLASSES = {
    "cosmic": "partially_observed_synthetic_completion_public_deck_proxy",
    "morcant": "partially_observed_synthetic_completion_pool_constrained",
    "kaervek": "verified_full_deck_frozen_opponent_only",
    "blight": "official_precon_baseline_commander_preference_observed",
    "dance": "official_precon_baseline",
    "lorehold": "official_precon_exact_100_real_unchanged_confirmed",
    "doom": "official_precon_baseline",
    "wakanda": "official_precon_baseline",
}
CUMULATIVE_BEFORE = {
    "cosmic": 0,
    "morcant": 192,
    "kaervek": 232,
    "blight": 232,
    "dance": 232,
    "lorehold": 232,
    "doom": 232,
    "wakanda": 232,
}
NEW_TARGETS = {
    "cosmic": 318,
    "morcant": 126,
    "kaervek": 86,
    "blight": 86,
    "dance": 86,
    "lorehold": 86,
    "doom": 86,
    "wakanda": 86,
}
TARGET_AFTER = 318


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean(rows: list[dict], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return fmean(values) if values else None


def _candidate_summary(candidate: str, rows: list[dict]) -> dict:
    return {
        "candidate_id": candidate,
        "games": len(rows),
        "first_place_fraction": _mean(rows, "candidate_first_place"),
        "mean_placement": _mean(rows, "candidate_placement"),
        "mean_damage": _mean(rows, "candidate_damage"),
        "mean_commander_damage": _mean(rows, "candidate_commander_damage"),
        "mean_cards_drawn": _mean(rows, "candidate_cards_drawn"),
        "mean_mulligans": _mean(rows, "candidate_mulligans"),
        "mean_lands_played": _mean(rows, "candidate_lands_played"),
        "mean_ramp_resolved": _mean(rows, "candidate_ramp_resolved"),
        "mean_first_commander_cast_turn": _mean(rows, "candidate_first_commander_cast_turn"),
        "mean_ishai_peak_power": _mean(rows, "candidate_ishai_peak_power"),
        "mean_protections_resolved": _mean(rows, "candidate_protections_resolved"),
        "mean_turns": _mean(rows, "turns"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--balance-audit", required=True)
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    balance = json.loads(Path(args.balance_audit).read_text(encoding="utf-8"))
    if balance.get("status") != "PASS":
        raise SystemExit("balance audit is not PASS")
    if balance.get("target_game_count") != 15360:
        raise SystemExit("unexpected balance target game count")
    if balance.get("opponent_appearances_after_per_candidate") != {
        opponent: TARGET_AFTER for opponent in OPPONENTS
    }:
        raise SystemExit("balance audit does not prove exact cumulative equalization")

    result_paths = sorted(input_root.rglob("GAME_RESULTS.jsonl"))
    if len(result_paths) != 20:
        raise SystemExit(f"expected 20 block result files, got {len(result_paths)}")

    rows: list[dict] = []
    for path in result_paths:
        rows.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    if len(rows) != 15360:
        raise SystemExit(f"expected 15360 game rows, got {len(rows)}")
    if not all(row["completed"] and not row["aborted"] for row in rows):
        raise SystemExit("aggregate contains incomplete/aborted rows")
    if any(row["evidence_class"] != "structural_model_estimates" for row in rows):
        raise SystemExit("unexpected evidence class")
    if any(row["engine_version"] != "structural-0.6.2" for row in rows):
        raise SystemExit("unexpected structural engine version")

    by_candidate: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_candidate[str(row["candidate_id"])].append(row)
    if set(by_candidate) != set(CANDIDATES):
        raise SystemExit("aggregate candidate population is not exactly C001..C048")

    summaries: list[dict] = []
    robustness: list[dict] = []
    conditioned: list[dict] = []
    evidence_conditioned: list[dict] = []
    seat_conditioned: list[dict] = []

    for candidate in CANDIDATES:
        candidate_rows = by_candidate[candidate]
        if len(candidate_rows) != 320:
            raise SystemExit(f"{candidate} has {len(candidate_rows)} rows, expected 320")
        if len({int(row["master_seed"]) for row in candidate_rows}) != 320:
            raise SystemExit(f"{candidate} does not have 320 unique seeds")
        if Counter(int(row["candidate_seat"]) for row in candidate_rows) != Counter(
            {1: 80, 2: 80, 3: 80, 4: 80}
        ):
            raise SystemExit(f"{candidate} candidate seat balance failed")
        if Counter(int(row["starting_player_seat_0_based"]) + 1 for row in candidate_rows) != Counter(
            {1: 80, 2: 80, 3: 80, 4: 80}
        ):
            raise SystemExit(f"{candidate} starting seat balance failed")

        opponent_presence = Counter(
            opponent for row in candidate_rows for opponent in row["opponent_triplet"]
        )
        if opponent_presence != Counter(NEW_TARGETS):
            raise SystemExit(
                f"{candidate} new opponent appearance targets failed: {dict(opponent_presence)}"
            )
        cumulative = {
            opponent: CUMULATIVE_BEFORE[opponent] + opponent_presence[opponent]
            for opponent in OPPONENTS
        }
        if set(cumulative.values()) != {TARGET_AFTER}:
            raise SystemExit(f"{candidate} cumulative equalization failed: {cumulative}")

        summary = _candidate_summary(candidate, candidate_rows)
        summaries.append(summary)

        seat_fp = {}
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

        opponent_fp = {}
        opponent_place = {}
        for opponent in OPPONENTS:
            cell = [row for row in candidate_rows if opponent in row["opponent_triplet"]]
            expected = NEW_TARGETS[opponent]
            if len(cell) != expected:
                raise SystemExit(f"{candidate}/{opponent} has {len(cell)} rows, expected {expected}")
            opponent_fp[opponent] = fmean(float(row["candidate_first_place"]) for row in cell)
            opponent_place[opponent] = fmean(float(row["candidate_placement"]) for row in cell)
            conditioned.append(
                {
                    "candidate_id": candidate,
                    "opponent": opponent,
                    "opponent_evidence_class": OPPONENT_EVIDENCE_CLASSES[opponent],
                    "games_with_opponent": len(cell),
                    "cumulative_after_per_candidate": TARGET_AFTER,
                    "first_place_fraction": opponent_fp[opponent],
                    "mean_placement": opponent_place[opponent],
                    "mean_damage": _mean(cell, "candidate_damage"),
                    "mean_commander_damage": _mean(cell, "candidate_commander_damage"),
                    "mean_cards_drawn": _mean(cell, "candidate_cards_drawn"),
                }
            )

        evidence_groups = {
            "contains_cosmic_public_deck_proxy": [
                row for row in candidate_rows if "cosmic" in row["opponent_triplet"]
            ],
            "contains_morcant_synthetic_completion": [
                row for row in candidate_rows if "morcant" in row["opponent_triplet"]
            ],
            "without_cosmic_proxy": [
                row for row in candidate_rows if "cosmic" not in row["opponent_triplet"]
            ],
            "without_morcant_synthetic_completion": [
                row for row in candidate_rows if "morcant" not in row["opponent_triplet"]
            ],
        }
        for group, cell in evidence_groups.items():
            evidence_conditioned.append(
                {
                    "candidate_id": candidate,
                    "evidence_group": group,
                    "games": len(cell),
                    "first_place_fraction": _mean(cell, "candidate_first_place"),
                    "mean_placement": _mean(cell, "candidate_placement"),
                    "mean_damage": _mean(cell, "candidate_damage"),
                    "mean_commander_damage": _mean(cell, "candidate_commander_damage"),
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
                "worst_opponent": min(opponent_fp, key=opponent_fp.get),
                "worst_opponent_fp": min(opponent_fp.values()),
                "best_opponent": max(opponent_fp, key=opponent_fp.get),
                "best_opponent_fp": max(opponent_fp.values()),
                "cosmic_proxy_fp": opponent_fp["cosmic"],
                "morcant_synthetic_fp": opponent_fp["morcant"],
                "well_supported_min_fp": min(opponent_fp[opponent] for opponent in WELL_SUPPORTED),
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
    ranked = [{"rank": rank, **row} for rank, row in enumerate(summaries, start=1)]

    _write_csv(output / "RANKING_ALL_48_MIXED_EVIDENCE.csv", ranked, list(ranked[0]))
    _write_csv(output / "ROBUSTNESS_ALL_48.csv", robustness, list(robustness[0]))
    _write_csv(output / "OPPONENT_CONDITIONED_ALL_48.csv", conditioned, list(conditioned[0]))
    _write_csv(
        output / "EVIDENCE_CLASS_CONDITIONED_ALL_48.csv",
        evidence_conditioned,
        list(evidence_conditioned[0]),
    )
    _write_csv(output / "SEAT_CONDITIONED_ALL_48.csv", seat_conditioned, list(seat_conditioned[0]))

    with (output / "GAME_RESULTS.jsonl").open("w", encoding="utf-8") as handle:
        for row in sorted(
            rows, key=lambda item: (item["candidate_id"], int(item["scenario_index"]))
        ):
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    report = {
        "schema_version": "rogshai-postfix-eightopp-equalization-aggregate-1.0.0",
        "status": "PASS",
        "evidence_class": "structural_model_estimates",
        "opponent_information_class": "mixed_real_official_and_synthetic_proxy_equalization",
        "engine_version": "structural-0.6.2",
        "fidelity_engine_version": "structural-fidelity-overlay-2026-08-25-v2",
        "total_games": 15360,
        "candidate_count": 48,
        "games_per_candidate": 320,
        "opponents": list(OPPONENTS),
        "opponent_evidence_classes": OPPONENT_EVIDENCE_CLASSES,
        "cumulative_before_per_candidate": CUMULATIVE_BEFORE,
        "new_appearances_per_candidate": NEW_TARGETS,
        "cumulative_after_per_candidate": {
            opponent: TARGET_AFTER for opponent in OPPONENTS
        },
        "equalized_after_each": TARGET_AFTER,
        "cosmic_proxy_new_games_per_candidate": NEW_TARGETS["cosmic"],
        "morcant_synthetic_new_games_per_candidate": NEW_TARGETS["morcant"],
        "pre_gameplay_candidate_elimination": 0,
        "ranking_basis": (
            "mixed-evidence post-fix Structural sample only; Cosmic is a public-deck synthetic "
            "proxy and Morcant is a pool-constrained synthetic completion. Overall rank is "
            "descriptive and must be read with opponent-conditioned outputs."
        ),
        "ranking": [row["candidate_id"] for row in ranked],
        "truth_boundaries": [
            "Structural model evidence is not empirical Commander win rate or rules authority.",
            "Exact cumulative appearance equality is a test-design property, not a real-meta prior.",
            "Cosmic proxy exposure does not become observed Cosmic evidence.",
            "Morcant synthetic completion exposure does not become verified Morcant evidence.",
            "No canonical deck, inventory, allocation, purchase, or opponent truth is mutated.",
        ],
    }
    (output / "AGGREGATE_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "BALANCE_AUDIT.json").write_text(
        json.dumps(balance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
