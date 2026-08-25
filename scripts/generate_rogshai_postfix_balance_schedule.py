from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from itertools import combinations, permutations
from pathlib import Path

CAMPAIGN_ID = "rogshai-postfix-opponent-balance-7680-2026-08-25-v1"
OPPONENTS = ("kaervek", "blight", "dance", "lorehold", "doom", "wakanda")


def _seed_for(index: int) -> int:
    raw = hashlib.sha256(f"{CAMPAIGN_ID}|scenario|{index}".encode()).digest()
    return int.from_bytes(raw[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def _build_rows() -> list[dict]:
    triplets = list(combinations(OPPONENTS, 3))
    rows: list[dict] = []
    physical_counts: dict[str, Counter[int]] = defaultdict(Counter)
    relative_counts: dict[str, Counter[int]] = defaultdict(Counter)
    rng = random.Random(1)

    for triplet_index, triplet in enumerate(triplets):
        for replicate in range(8):
            candidate_seat = replicate % 4 + 1
            starting_seat = (triplet_index + replicate // 4) % 4 + 1
            available_seats = [seat for seat in range(1, 5) if seat != candidate_seat]
            options = list(permutations(triplet))
            rng.shuffle(options)
            scored: list[tuple[float, tuple[str, ...]]] = []
            for option in options:
                score = 0.0
                for seat, opponent in zip(available_seats, option, strict=True):
                    before = physical_counts[opponent][seat]
                    score += float((before + 1) ** 2 - before**2)
                    relative = (seat - candidate_seat) % 4
                    rel_before = relative_counts[opponent][relative]
                    score += 0.4 * float((rel_before + 1) ** 2 - rel_before**2)
                scored.append((score, option))
            _, chosen = min(scored, key=lambda item: item[0])
            opponent_by_seat = {
                str(seat): opponent
                for seat, opponent in zip(available_seats, chosen, strict=True)
            }
            for seat, opponent in zip(available_seats, chosen, strict=True):
                physical_counts[opponent][seat] += 1
                relative_counts[opponent][(seat - candidate_seat) % 4] += 1
            rows.append(
                {
                    "triplet_index": triplet_index + 1,
                    "triplet_replicate": replicate + 1,
                    "candidate_seat": candidate_seat,
                    "starting_player_seat_0_based": starting_seat - 1,
                    "opponent_triplet": list(triplet),
                    "opponent_by_seat": opponent_by_seat,
                }
            )

    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        cells[(int(row["candidate_seat"]), int(row["starting_player_seat_0_based"]) + 1)].append(index)
    if set(map(len, cells.values())) != {10} or len(cells) != 16:
        raise SystemExit("candidate-seat x starting-seat cells are not exactly 10 each")

    for block in range(1, 11):
        for cell in sorted(cells):
            row_index = cells[cell][block - 1]
            rows[row_index]["block"] = block

    ordered = sorted(rows, key=lambda row: (int(row["block"]), int(row["candidate_seat"]), int(row["starting_player_seat_0_based"]), int(row["triplet_index"]), int(row["triplet_replicate"])))
    for index, row in enumerate(ordered, start=1):
        row["scenario_index"] = index
        row["seed_index"] = index
        row["master_seed"] = _seed_for(index)
    return ordered


def _audit(rows: list[dict]) -> dict:
    if len(rows) != 160:
        raise SystemExit(f"expected 160 scenarios, got {len(rows)}")
    seeds = [int(row["master_seed"]) for row in rows]
    if len(set(seeds)) != 160:
        raise SystemExit("master seeds are not unique")

    candidate_seats = Counter(int(row["candidate_seat"]) for row in rows)
    starting_seats = Counter(int(row["starting_player_seat_0_based"]) + 1 for row in rows)
    cells = Counter((int(row["candidate_seat"]), int(row["starting_player_seat_0_based"]) + 1) for row in rows)
    triplet_counts = Counter(tuple(row["opponent_triplet"]) for row in rows)
    opponent_counts: Counter[str] = Counter()
    physical: dict[str, Counter[int]] = {opponent: Counter() for opponent in OPPONENTS}
    relative: dict[str, Counter[int]] = {opponent: Counter() for opponent in OPPONENTS}
    block_sizes = Counter(int(row["block"]) for row in rows)
    block_candidate_seats: dict[int, Counter[int]] = defaultdict(Counter)
    block_starting_seats: dict[int, Counter[int]] = defaultdict(Counter)

    for row in rows:
        candidate = int(row["candidate_seat"])
        block = int(row["block"])
        block_candidate_seats[block][candidate] += 1
        block_starting_seats[block][int(row["starting_player_seat_0_based"]) + 1] += 1
        seat_map = {int(seat): str(opponent) for seat, opponent in row["opponent_by_seat"].items()}
        if set(seat_map) != ({1, 2, 3, 4} - {candidate}):
            raise SystemExit("malformed opponent seat map")
        if set(seat_map.values()) != set(row["opponent_triplet"]):
            raise SystemExit("seat map does not match opponent triplet")
        for seat, opponent in seat_map.items():
            if opponent not in OPPONENTS:
                raise SystemExit(f"unexpected opponent {opponent}")
            opponent_counts[opponent] += 1
            physical[opponent][seat] += 1
            relative[opponent][(seat - candidate) % 4] += 1

    expected_four = Counter({seat: 40 for seat in range(1, 5)})
    if candidate_seats != expected_four or starting_seats != expected_four:
        raise SystemExit("global seat/start balance failed")
    if set(cells.values()) != {10} or len(cells) != 16:
        raise SystemExit("candidate x starting seat matrix is not exactly 10 each")
    if set(triplet_counts.values()) != {8} or len(triplet_counts) != 20:
        raise SystemExit("triplet multiplicity is not exactly 8 for all 20 triplets")
    if opponent_counts != Counter({opponent: 80 for opponent in OPPONENTS}):
        raise SystemExit(f"opponent appearance balance failed: {dict(opponent_counts)}")
    for opponent in OPPONENTS:
        if physical[opponent] != Counter({seat: 20 for seat in range(1, 5)}):
            raise SystemExit(f"physical seat balance failed for {opponent}: {dict(physical[opponent])}")
        values = [relative[opponent][position] for position in (1, 2, 3)]
        if max(values) - min(values) > 2:
            raise SystemExit(f"relative-position balance too wide for {opponent}: {values}")
    if block_sizes != Counter({block: 16 for block in range(1, 11)}):
        raise SystemExit("block sizes are not exactly 16")
    for block in range(1, 11):
        if block_candidate_seats[block] != Counter({seat: 4 for seat in range(1, 5)}):
            raise SystemExit(f"candidate seat balance failed in block {block}")
        if block_starting_seats[block] != Counter({seat: 4 for seat in range(1, 5)}):
            raise SystemExit(f"starting seat balance failed in block {block}")

    return {
        "schema_version": "rogshai-postfix-opponent-balance-audit-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "status": "PASS",
        "scenario_count": 160,
        "block_count": 10,
        "scenarios_per_block": 16,
        "candidate_seat_each": 40,
        "starting_player_seat_each": 40,
        "candidate_by_starting_seat_cell_each": 10,
        "triplet_count": 20,
        "triplet_multiplicity_each": 8,
        "opponent_appearances_each": 80,
        "opponent_physical_seat_each": 20,
        "relative_position_counts": {opponent: dict(relative[opponent]) for opponent in OPPONENTS},
        "morcant_present": False,
        "cosmic_present": False,
        "unique_seed_count": 160,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit-output", required=True)
    args = parser.parse_args()
    rows = _build_rows()
    audit = _audit(rows)
    payload = {
        "schema_version": "rogshai-postfix-opponent-balance-schedule-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "evidence_class": "structural_model_estimates",
        "opponent_information_class": "well_supported_real_current_complete_or_official_precon",
        "scenario_count": 160,
        "candidate_count": 48,
        "target_game_count": 7680,
        "opponents": list(OPPONENTS),
        "morcant_allowed": False,
        "cosmic_allowed": False,
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
