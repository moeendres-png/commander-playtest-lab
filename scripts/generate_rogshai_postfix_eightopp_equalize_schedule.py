from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from itertools import combinations, permutations
from pathlib import Path

CAMPAIGN_ID = "rogshai-postfix-eightopp-equalize-15360-2026-08-26-v1"
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
NON_COSMIC = tuple(opponent for opponent in OPPONENTS if opponent != "cosmic")
SCENARIO_COUNT = 320
CANDIDATE_COUNT = 48
TARGET_GAME_COUNT = SCENARIO_COUNT * CANDIDATE_COUNT
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
TARGET_AFTER = 318
NEW_APPEARANCE_TARGETS = {
    opponent: TARGET_AFTER - CUMULATIVE_BEFORE[opponent] for opponent in OPPONENTS
}
SEATING_SEARCH_SEED = 268


def _seed_for(index: int) -> int:
    raw = hashlib.sha256(f"{CAMPAIGN_ID}|scenario|{index}".encode()).digest()
    return int.from_bytes(raw[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def _build_triplets() -> list[tuple[str, str, str]]:
    # Cosmic has the full post-fix evidence deficit. Exact cumulative equalization therefore
    # requires it in 318/320 scenarios. Two no-Cosmic scenarios are retained so the non-Cosmic
    # degree sequence remains realizable without duplicate opponents inside a pod.
    no_cosmic = [
        ("morcant", "kaervek", "blight"),
        ("morcant", "dance", "lorehold"),
    ]

    # After the two no-Cosmic triplets, each remaining appearance target becomes a vertex degree
    # in a deterministic multigraph. Every multigraph edge becomes Cosmic + two opponents.
    remaining = dict(NEW_APPEARANCE_TARGETS)
    remaining["cosmic"] = 0
    for triplet in no_cosmic:
        for opponent in triplet:
            remaining[opponent] -= 1

    pair_counts: Counter[tuple[str, str]] = Counter()
    edges: list[tuple[str, str]] = []
    while sum(remaining[opponent] for opponent in NON_COSMIC) > 0:
        first = max(NON_COSMIC, key=lambda opponent: (remaining[opponent], opponent))
        if remaining[first] <= 0:
            break
        choices = [
            opponent
            for opponent in NON_COSMIC
            if opponent != first and remaining[opponent] > 0
        ]
        if not choices:
            raise SystemExit("non-Cosmic degree sequence became unrealizable")
        second = min(
            choices,
            key=lambda opponent: (
                pair_counts[tuple(sorted((first, opponent)))],
                -remaining[opponent],
                opponent,
            ),
        )
        key = tuple(sorted((first, second)))
        pair_counts[key] += 1
        edges.append((first, second))
        remaining[first] -= 1
        remaining[second] -= 1

    if any(remaining[opponent] != 0 for opponent in OPPONENTS):
        raise SystemExit(f"triplet construction left residual appearances: {remaining}")
    if len(edges) != 318:
        raise SystemExit(f"expected 318 Cosmic triplets, got {len(edges)}")

    triplets = [("cosmic", first, second) for first, second in edges] + no_cosmic
    if len(triplets) != SCENARIO_COUNT:
        raise SystemExit(f"expected {SCENARIO_COUNT} triplets, got {len(triplets)}")
    return triplets


def _build_rows() -> list[dict]:
    rng = random.Random(SEATING_SEARCH_SEED)
    triplets = _build_triplets()
    rng.shuffle(triplets)

    # 16 candidate-seat x starting-seat cells, exactly 20 scenarios per cell.
    cells = [
        (candidate_seat, starting_seat)
        for candidate_seat in range(1, 5)
        for starting_seat in range(1, 5)
    ] * 20
    rng.shuffle(cells)

    physical_counts: dict[str, Counter[int]] = defaultdict(Counter)
    relative_counts: dict[str, Counter[int]] = defaultdict(Counter)
    rows: list[dict] = []

    for triplet, (candidate_seat, starting_seat) in zip(triplets, cells, strict=True):
        available_seats = [seat for seat in range(1, 5) if seat != candidate_seat]
        options = list(permutations(triplet))
        rng.shuffle(options)

        def option_score(option: tuple[str, str, str]) -> float:
            score = 0.0
            for seat, opponent in zip(available_seats, option, strict=True):
                before = physical_counts[opponent][seat]
                score += 2.0 * float((before + 1) ** 2 - before**2)
                relative = (seat - candidate_seat) % 4
                rel_before = relative_counts[opponent][relative]
                score += 1.5 * float((rel_before + 1) ** 2 - rel_before**2)
            return score

        chosen = min(options, key=option_score)
        opponent_by_seat = {
            str(seat): opponent
            for seat, opponent in zip(available_seats, chosen, strict=True)
        }
        for seat, opponent in zip(available_seats, chosen, strict=True):
            physical_counts[opponent][seat] += 1
            relative_counts[opponent][(seat - candidate_seat) % 4] += 1

        rows.append(
            {
                "candidate_seat": candidate_seat,
                "starting_player_seat_0_based": starting_seat - 1,
                "opponent_triplet": list(triplet),
                "opponent_by_seat": opponent_by_seat,
            }
        )

    # Twenty blocks x sixteen scenarios. Each block contains one copy of every seat/start cell.
    cell_indices: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        cell = (
            int(row["candidate_seat"]),
            int(row["starting_player_seat_0_based"]) + 1,
        )
        cell_indices[cell].append(index)
    if len(cell_indices) != 16 or set(map(len, cell_indices.values())) != {20}:
        raise SystemExit("candidate-seat x starting-seat cells are not exactly 20 each")

    for block in range(1, 21):
        for cell in sorted(cell_indices):
            row_index = cell_indices[cell][block - 1]
            rows[row_index]["block"] = block

    ordered = sorted(
        rows,
        key=lambda row: (
            int(row["block"]),
            int(row["candidate_seat"]),
            int(row["starting_player_seat_0_based"]),
            tuple(sorted(str(value) for value in row["opponent_triplet"])),
        ),
    )
    for index, row in enumerate(ordered, start=1):
        row["scenario_index"] = index
        row["seed_index"] = index
        row["master_seed"] = _seed_for(index)
    return ordered


def _audit(rows: list[dict]) -> dict:
    if len(rows) != SCENARIO_COUNT:
        raise SystemExit(f"expected {SCENARIO_COUNT} scenarios, got {len(rows)}")

    seeds = [int(row["master_seed"]) for row in rows]
    if len(set(seeds)) != SCENARIO_COUNT:
        raise SystemExit("master seeds are not unique")

    candidate_seats = Counter(int(row["candidate_seat"]) for row in rows)
    starting_seats = Counter(int(row["starting_player_seat_0_based"]) + 1 for row in rows)
    cells = Counter(
        (int(row["candidate_seat"]), int(row["starting_player_seat_0_based"]) + 1)
        for row in rows
    )
    block_sizes = Counter(int(row["block"]) for row in rows)
    triplet_counts = Counter(tuple(sorted(row["opponent_triplet"])) for row in rows)
    pair_counts: Counter[tuple[str, str]] = Counter()
    appearances: Counter[str] = Counter()
    physical: dict[str, Counter[int]] = {opponent: Counter() for opponent in OPPONENTS}
    relative: dict[str, Counter[int]] = {opponent: Counter() for opponent in OPPONENTS}

    for row in rows:
        candidate_seat = int(row["candidate_seat"])
        triplet = tuple(str(value) for value in row["opponent_triplet"])
        if len(triplet) != 3 or len(set(triplet)) != 3:
            raise SystemExit("opponent triplet must contain three distinct opponents")
        if any(opponent not in OPPONENTS for opponent in triplet):
            raise SystemExit(f"unexpected opponent triplet {triplet}")
        appearances.update(triplet)
        for pair in combinations(sorted(triplet), 2):
            pair_counts[pair] += 1

        seat_map = {
            int(seat): str(opponent) for seat, opponent in row["opponent_by_seat"].items()
        }
        if set(seat_map) != ({1, 2, 3, 4} - {candidate_seat}):
            raise SystemExit("malformed opponent seat map")
        if set(seat_map.values()) != set(triplet):
            raise SystemExit("seat map does not match opponent triplet")
        for seat, opponent in seat_map.items():
            physical[opponent][seat] += 1
            relative[opponent][(seat - candidate_seat) % 4] += 1

    expected_seats = Counter({seat: 80 for seat in range(1, 5)})
    if candidate_seats != expected_seats or starting_seats != expected_seats:
        raise SystemExit("candidate/start seat balance failed")
    if len(cells) != 16 or set(cells.values()) != {20}:
        raise SystemExit("candidate x starting seat matrix is not exactly 20 each")
    if block_sizes != Counter({block: 16 for block in range(1, 21)}):
        raise SystemExit("block sizes are not exactly sixteen")
    if appearances != Counter(NEW_APPEARANCE_TARGETS):
        raise SystemExit(f"new appearance targets failed: {dict(appearances)}")

    cumulative_after = {
        opponent: CUMULATIVE_BEFORE[opponent] + appearances[opponent]
        for opponent in OPPONENTS
    }
    if set(cumulative_after.values()) != {TARGET_AFTER}:
        raise SystemExit(f"cumulative opponent equalization failed: {cumulative_after}")

    for opponent in OPPONENTS:
        physical_values = [physical[opponent][seat] for seat in range(1, 5)]
        relative_values = [relative[opponent][position] for position in (1, 2, 3)]
        if max(physical_values) - min(physical_values) > 1:
            raise SystemExit(f"physical seat imbalance too wide for {opponent}: {physical_values}")
        if max(relative_values) - min(relative_values) > 1:
            raise SystemExit(f"relative position imbalance too wide for {opponent}: {relative_values}")

    return {
        "schema_version": "rogshai-postfix-eightopp-equalization-audit-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "status": "PASS",
        "scenario_count": SCENARIO_COUNT,
        "candidate_count": CANDIDATE_COUNT,
        "target_game_count": TARGET_GAME_COUNT,
        "block_count": 20,
        "scenarios_per_block": 16,
        "candidate_seat_each": 80,
        "starting_player_seat_each": 80,
        "candidate_by_starting_seat_cell_each": 20,
        "opponent_appearances_before_per_candidate": CUMULATIVE_BEFORE,
        "new_opponent_appearances_per_candidate": dict(appearances),
        "opponent_appearances_after_per_candidate": cumulative_after,
        "equalized_after_each": TARGET_AFTER,
        "cosmic_new_appearances_per_candidate": appearances["cosmic"],
        "morcant_new_appearances_per_candidate": appearances["morcant"],
        "triplet_type_count": len(triplet_counts),
        "triplet_multiplicity_min": min(triplet_counts.values()),
        "triplet_multiplicity_max": max(triplet_counts.values()),
        "pair_type_count": len(pair_counts),
        "pair_multiplicity_min": min(pair_counts.values()),
        "pair_multiplicity_max": max(pair_counts.values()),
        "physical_seat_counts": {
            opponent: {str(seat): physical[opponent][seat] for seat in range(1, 5)}
            for opponent in OPPONENTS
        },
        "relative_position_counts": {
            opponent: {str(position): relative[opponent][position] for position in (1, 2, 3)}
            for opponent in OPPONENTS
        },
        "cosmic_information_class": "partially_observed_synthetic_completion_public_deck_proxy",
        "morcant_information_class": "partially_observed_synthetic_completion_pool_constrained",
        "unique_seed_count": SCENARIO_COUNT,
        "replacement_seeds_allowed": False,
        "balance_note": (
            "Triplet/pair frequencies are intentionally nonuniform because exact cumulative opponent "
            "appearance equalization is the primary constraint; seat and relative-position balance "
            "are exact or mathematically minimal within one appearance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit-output", required=True)
    args = parser.parse_args()

    rows = _build_rows()
    audit = _audit(rows)
    payload = {
        "schema_version": "rogshai-postfix-eightopp-equalization-schedule-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "evidence_class": "structural_model_estimates",
        "opponent_information_class": "mixed_real_official_and_synthetic_proxy_equalization",
        "scenario_count": SCENARIO_COUNT,
        "candidate_count": CANDIDATE_COUNT,
        "target_game_count": TARGET_GAME_COUNT,
        "opponents": list(OPPONENTS),
        "cumulative_before_per_candidate": CUMULATIVE_BEFORE,
        "new_appearance_targets_per_candidate": NEW_APPEARANCE_TARGETS,
        "target_after_each_per_candidate": TARGET_AFTER,
        "schedule": rows,
    }
    output = Path(args.output)
    audit_output = Path(args.audit_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
