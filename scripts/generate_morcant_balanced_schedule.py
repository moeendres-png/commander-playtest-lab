from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

CAMPAIGN_ID = "rogshai-morcant-balanced-post-seatfix-2026-08-25-v1"
NAMES = ("scions", "counter", "turtle", "silverquill", "fantastic", "avengers")
# (candidate seat, Morcant seat, opp-A index, opp-A seat, opp-B index, opp-B seat, start seat 0-based)
CONFIGS = [
(2,4,0,1,2,3,2),(2,1,0,4,3,3,3),(4,1,0,2,4,3,2),(4,1,0,3,5,2,1),(3,2,1,4,2,1,3),(3,2,1,1,3,4,2),(1,2,1,3,4,4,1),(3,4,1,2,5,1,0),(1,3,2,4,4,2,0),(1,3,2,2,5,4,0),(4,3,3,2,4,1,1),(2,4,3,1,5,3,3),
(2,1,0,4,2,3,0),(1,3,0,2,3,4,0),(4,2,0,3,4,1,3),(4,2,0,1,5,3,0),(1,4,1,3,2,2,1),(3,4,1,2,3,1,3),(3,4,1,1,4,2,1),(3,2,1,4,5,1,3),(2,3,2,1,4,4,1),(1,3,2,4,5,2,2),(4,1,3,2,4,3,2),(2,1,3,3,5,4,2),
(1,3,0,2,2,4,2),(2,1,0,4,3,3,2),(4,3,0,1,4,2,0),(1,2,0,3,5,4,1),(4,2,1,1,2,3,3),(3,1,1,2,3,4,2),(2,1,1,3,4,4,3),(1,2,1,4,5,3,1),(3,4,2,1,3,2,0),(3,4,2,2,4,1,0),(4,3,3,1,5,2,1),(2,4,4,3,5,1,3),
(2,3,0,4,1,1,2),(1,2,0,3,3,4,0),(1,4,0,2,4,3,2),(3,4,0,1,5,2,1),(3,1,1,4,2,2,2),(4,2,1,3,3,1,1),(1,4,1,2,5,3,0),(2,1,2,4,3,3,3),(4,2,2,3,4,1,0),(2,3,2,1,5,4,3),(3,1,3,2,4,4,3),(4,3,4,2,5,1,1),
(3,1,0,2,1,4,0),(1,2,0,4,3,3,2),(2,4,0,3,4,1,0),(3,4,0,1,5,2,1),(2,1,1,3,2,4,1),(4,3,1,2,3,1,0),(4,2,1,1,4,3,3),(4,3,2,1,3,2,2),(3,1,2,2,4,4,1),(1,2,2,3,5,4,3),(2,3,3,4,5,1,2),(1,4,4,2,5,3,3),
(3,4,0,2,1,1,1),(2,1,0,3,3,4,0),(1,3,0,4,4,2,1),(3,4,0,1,5,2,2),(1,3,1,4,2,2,3),(1,4,1,3,3,2,3),(4,1,1,2,4,3,1),(3,2,2,4,3,1,3),(2,1,2,3,4,4,0),(4,2,2,1,5,3,2),(4,2,3,3,5,1,2),(2,3,4,1,5,4,0),
(4,1,0,3,1,2,1),(1,3,0,4,2,2,3),(3,1,0,2,4,4,1),(4,3,0,1,5,2,3),(2,4,1,3,3,1,0),(2,3,1,4,4,1,1),(4,2,1,1,5,3,3),(3,4,2,1,3,2,2),(1,4,2,3,4,2,2),(3,2,2,4,5,1,0),(2,1,3,4,4,3,0),(1,2,3,3,5,4,2),
(3,1,0,4,1,2,3),(2,3,0,1,2,4,2),(4,1,0,3,4,2,2),(4,3,0,2,5,1,3),(1,2,1,4,2,3,0),(2,4,1,1,3,3,2),(1,4,1,3,5,2,1),(3,2,2,1,3,4,0),(4,3,2,2,4,1,3),(2,4,3,1,4,3,1),(3,1,3,2,5,4,0),(1,2,4,4,5,3,1),
(2,4,0,3,1,1,1),(2,1,0,4,2,3,1),(3,1,0,2,3,4,3),(2,3,0,1,5,4,3),(3,2,1,4,3,1,2),(1,3,1,2,4,4,2),(4,2,1,3,5,1,0),(1,4,2,2,3,3,3),(1,2,2,4,4,3,1),(3,4,2,1,5,2,2),(4,3,3,2,4,1,0),(4,1,4,2,5,3,0),
(1,4,0,3,1,2,3),(4,2,0,1,2,3,0),(2,3,0,4,3,1,1),(3,4,0,2,5,1,0),(4,3,1,1,3,2,2),(3,1,1,4,4,2,3),(1,2,1,3,5,4,0),(1,3,2,2,3,4,2),(3,2,2,4,4,1,2),(2,4,2,1,5,3,3),(2,1,3,3,4,4,1),(4,1,4,3,5,2,1),
(4,3,0,1,1,2,1),(4,3,0,2,2,1,0),(2,4,0,3,3,1,3),(1,2,0,4,4,3,1),(4,1,1,3,2,2,3),(3,4,1,1,4,2,0),(1,3,1,4,5,2,3),(1,2,2,3,3,4,2),(2,1,2,4,5,3,0),(3,1,3,2,4,4,2),(2,4,3,3,5,1,2),(3,2,4,1,5,4,1),
(1,2,0,3,1,4,3),(1,4,0,2,2,3,0),(3,2,0,4,3,1,1),(4,2,0,1,4,3,2),(3,4,1,1,2,2,1),(4,1,1,3,4,2,2),(4,3,1,2,5,1,3),(2,4,2,1,3,3,2),(1,3,2,4,5,2,0),(2,3,3,4,4,1,1),(3,1,3,2,5,4,3),(2,1,4,4,5,3,0)
]


def master_seed(global_index: int) -> int:
    raw = hashlib.sha256(f"{CAMPAIGN_ID}|{global_index}".encode()).digest()
    value = int.from_bytes(raw[:4], "big") & 0x7FFFFFFF
    return value or 1


def build_rows() -> list[dict]:
    if len(CONFIGS) != 144:
        raise RuntimeError(f"expected 144 configs, found {len(CONFIGS)}")
    rows = []
    for offset, (candidate_seat, morcant_seat, a, a_seat, b, b_seat, start) in enumerate(CONFIGS):
        block = offset // 12 + 1
        seed_index = offset % 12 + 1
        occupied = {candidate_seat, morcant_seat, a_seat, b_seat}
        if occupied != {1, 2, 3, 4}:
            raise RuntimeError(f"malformed seat assignment at {offset + 1}: {occupied}")
        by_seat = {
            str(morcant_seat): "morcant",
            str(a_seat): NAMES[a],
            str(b_seat): NAMES[b],
        }
        rows.append(
            {
                "block": block,
                "seed_index": seed_index,
                "global_seed_index": offset + 1,
                "master_seed": master_seed(offset + 1),
                "candidate_seat": candidate_seat,
                "xmage_starting_player_seat_0_based": start,
                "opponent_triplet": ["morcant", NAMES[a], NAMES[b]],
                "opponent_by_seat": dict(sorted(by_seat.items(), key=lambda item: int(item[0]))),
            }
        )
    return rows


def audit(rows: list[dict]) -> dict:
    if len(rows) != 144 or len({row["master_seed"] for row in rows}) != 144:
        raise RuntimeError("scenario or seed uniqueness failure")
    candidate_seats = Counter(row["candidate_seat"] for row in rows)
    starting_seats = Counter(row["xmage_starting_player_seat_0_based"] + 1 for row in rows)
    appearances: Counter[str] = Counter()
    physical: Counter[tuple[str, int]] = Counter()
    relative: Counter[tuple[str, int]] = Counter()
    co_pairs: Counter[tuple[str, str]] = Counter()
    candidate_start: Counter[tuple[int, int]] = Counter()
    for row in rows:
        c = row["candidate_seat"]
        candidate_start[(c, row["xmage_starting_player_seat_0_based"] + 1)] += 1
        non_morcant = []
        for seat_text, key in row["opponent_by_seat"].items():
            seat = int(seat_text)
            appearances[key] += 1
            physical[(key, seat)] += 1
            if key != "morcant":
                relative[(key, (seat - c) % 4)] += 1
                non_morcant.append(key)
        co_pairs[tuple(sorted(non_morcant))] += 1
    assert candidate_seats == Counter({1: 36, 2: 36, 3: 36, 4: 36})
    assert starting_seats == Counter({1: 36, 2: 36, 3: 36, 4: 36})
    assert appearances["morcant"] == 144
    assert all(appearances[key] == 48 for key in NAMES)
    assert all(physical[("morcant", seat)] == 36 for seat in range(1, 5))
    assert all(physical[(key, seat)] == 12 for key in NAMES for seat in range(1, 5))
    assert all(relative[(key, distance)] == 16 for key in NAMES for distance in (1, 2, 3))
    assert Counter(co_pairs.values()) == Counter({10: 9, 9: 6})
    assert set(candidate_start.values()) == {9}
    for block in range(1, 13):
        block_rows = [row for row in rows if row["block"] == block]
        assert len(block_rows) == 12
        assert Counter(row["candidate_seat"] for row in block_rows) == Counter({1: 3, 2: 3, 3: 3, 4: 3})
        assert Counter(row["xmage_starting_player_seat_0_based"] + 1 for row in block_rows) == Counter({1: 3, 2: 3, 3: 3, 4: 3})
        block_app = Counter(key for row in block_rows for key in row["opponent_by_seat"].values())
        assert block_app == Counter({"morcant": 12, **{key: 4 for key in NAMES}})
        block_phys = Counter((key, int(seat)) for row in block_rows for seat, key in row["opponent_by_seat"].items())
        assert all(block_phys[("morcant", seat)] == 3 for seat in range(1, 5))
        assert all(block_phys[(key, seat)] == 1 for key in NAMES for seat in range(1, 5))
    return {
        "schema_version": "rogshai-morcant-balance-audit-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "scenario_count": 144,
        "unique_seed_count": 144,
        "candidate_seat_each": 36,
        "starting_player_seat_each": 36,
        "morcant_appearances": 144,
        "morcant_physical_seat_each": 36,
        "rotating_opponent_appearances_each": 48,
        "rotating_opponent_physical_seat_each": 12,
        "rotating_opponent_relative_position_each": 16,
        "co_opponent_pair_multiplicity_distribution": {"9": 6, "10": 9},
        "candidate_by_starting_seat_cell_each": 9,
        "blocks": 12,
        "scenarios_per_block": 12,
        "cosmic_present": False,
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--block", type=int)
    parser.add_argument("--audit-output")
    args = parser.parse_args()
    rows = build_rows()
    report = audit(rows)
    selected = rows
    if args.block is not None:
        if args.block not in range(1, 13):
            raise SystemExit("block must be 1..12")
        selected = [row for row in rows if row["block"] == args.block]
    payload = {
        "schema_version": "rogshai-morcant-balanced-seed-schedule-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "scenario_count": len(selected),
        "full_campaign_scenario_count": 144,
        "block": args.block,
        "seed_policy": "SHA-256(campaign_id|global_seed_index), positive 31-bit; no replacement seeds",
        "schedule": selected,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.audit_output:
        Path(args.audit_output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
