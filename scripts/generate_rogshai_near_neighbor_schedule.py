from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations, permutations
from pathlib import Path

CAMPAIGN_ID = "rogshai-postfix-near-neighbor-64x80-2026-08-25-v1"
OPPONENTS = ("kaervek", "blight", "dance", "lorehold", "doom", "wakanda")


def _seed_for(index: int) -> int:
    raw = hashlib.sha256(f"{CAMPAIGN_ID}|scenario|{index}".encode()).digest()
    return int.from_bytes(raw[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def _physical_balanced_templates() -> dict[int, tuple[tuple[str, ...], ...]]:
    symbols = ("A", "B", "C")
    templates: dict[int, tuple[tuple[str, ...], ...]] = {}
    for perms in __import__("itertools").product(list(permutations(symbols)), repeat=4):
        physical = {symbol: Counter() for symbol in symbols}
        relative = {symbol: Counter() for symbol in symbols}
        for replicate, option in enumerate(perms, start=1):
            candidate_seat = replicate
            seats = [seat for seat in range(1, 5) if seat != candidate_seat]
            for seat, symbol in zip(seats, option, strict=True):
                physical[symbol][seat] += 1
                relative[symbol][(seat - candidate_seat) % 4] += 1
        if not all(physical[symbol] == Counter({1: 1, 2: 1, 3: 1, 4: 1}) for symbol in symbols):
            continue
        patterns = [tuple(relative[symbol][pos] for pos in (1, 2, 3)) for symbol in symbols]
        if patterns.count((2, 0, 2)) == 1 and patterns.count((1, 2, 1)) == 2:
            special_index = patterns.index((2, 0, 2))
            templates.setdefault(special_index, perms)
    if set(templates) != {0, 1, 2}:
        raise SystemExit("failed to construct physical-balanced opponent templates")
    return templates


def _build_rows() -> list[dict]:
    triplets = list(combinations(OPPONENTS, 3))
    rows: list[dict] = []
    special_counts = Counter()
    templates = _physical_balanced_templates()
    target_special = {"kaervek": 4, "blight": 4, "dance": 3, "lorehold": 3, "doom": 3, "wakanda": 3}
    special_assignment = (
        "kaervek", "kaervek", "kaervek", "kaervek",
        "dance", "dance", "dance",
        "lorehold", "lorehold", "doom",
        "blight", "blight", "blight", "blight",
        "lorehold", "doom", "doom",
        "wakanda", "wakanda", "wakanda",
    )

    for triplet_index, triplet in enumerate(triplets):
        special = special_assignment[triplet_index]
        if special not in triplet:
            raise SystemExit(f"invalid special assignment for triplet {triplet_index + 1}: {special} not in {triplet}")
        special_counts[special] += 1
        special_index = triplet.index(special)
        template = templates[special_index]
        for replicate in range(4):
            candidate_seat = replicate + 1
            starting_seat = (triplet_index + replicate) % 4 + 1
            available_seats = [seat for seat in range(1, 5) if seat != candidate_seat]
            symbol_to_opponent = {"A": triplet[0], "B": triplet[1], "C": triplet[2]}
            chosen = tuple(symbol_to_opponent[symbol] for symbol in template[replicate])
            opponent_by_seat = {
                str(seat): opponent for seat, opponent in zip(available_seats, chosen, strict=True)
            }
            rows.append(
                {
                    "triplet_index": triplet_index + 1,
                    "triplet_replicate": replicate + 1,
                    "candidate_seat": candidate_seat,
                    "starting_player_seat_0_based": starting_seat - 1,
                    "opponent_triplet": list(triplet),
                    "opponent_by_seat": opponent_by_seat,
                    "relative_balance_special_opponent": special,
                }
            )

    if dict(special_counts) != target_special:
        raise SystemExit(f"special-opponent balancing failed: {dict(special_counts)}")

    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        cells[(int(row["candidate_seat"]), int(row["starting_player_seat_0_based"]) + 1)].append(index)
    if len(cells) != 16 or set(map(len, cells.values())) != {5}:
        raise SystemExit("candidate-seat x starting-seat cells must be exactly 5 each")

    for block in range(1, 6):
        for cell in sorted(cells):
            rows[cells[cell][block - 1]]["block"] = block

    ordered = sorted(
        rows,
        key=lambda row: (
            int(row["block"]),
            int(row["candidate_seat"]),
            int(row["starting_player_seat_0_based"]),
            int(row["triplet_index"]),
        ),
    )
    for index, row in enumerate(ordered, start=1):
        row["scenario_index"] = index
        row["seed_index"] = index
        row["master_seed"] = _seed_for(index)
    return ordered


def _audit(rows: list[dict]) -> dict:
    if len(rows) != 80:
        raise SystemExit(f"expected 80 scenarios, got {len(rows)}")
    seeds = [int(row["master_seed"]) for row in rows]
    if len(set(seeds)) != 80:
        raise SystemExit("master seeds are not unique")

    candidate_seats = Counter(int(row["candidate_seat"]) for row in rows)
    starting_seats = Counter(int(row["starting_player_seat_0_based"]) + 1 for row in rows)
    cells = Counter((int(row["candidate_seat"]), int(row["starting_player_seat_0_based"]) + 1) for row in rows)
    triplet_counts = Counter(tuple(row["opponent_triplet"]) for row in rows)
    opponent_counts: Counter[str] = Counter()
    physical: dict[str, Counter[int]] = {opponent: Counter() for opponent in OPPONENTS}
    relative: dict[str, Counter[int]] = {opponent: Counter() for opponent in OPPONENTS}
    block_sizes = Counter(int(row["block"]) for row in rows)
    block_candidate = defaultdict(Counter)
    block_start = defaultdict(Counter)

    for row in rows:
        candidate = int(row["candidate_seat"])
        block = int(row["block"])
        block_candidate[block][candidate] += 1
        block_start[block][int(row["starting_player_seat_0_based"]) + 1] += 1
        seat_map = {int(seat): str(opponent) for seat, opponent in row["opponent_by_seat"].items()}
        if set(seat_map) != ({1, 2, 3, 4} - {candidate}):
            raise SystemExit("malformed opponent seat map")
        if set(seat_map.values()) != set(row["opponent_triplet"]):
            raise SystemExit("seat map does not match triplet")
        for seat, opponent in seat_map.items():
            opponent_counts[opponent] += 1
            physical[opponent][seat] += 1
            relative[opponent][(seat - candidate) % 4] += 1

    expected20 = Counter({seat: 20 for seat in range(1, 5)})
    if candidate_seats != expected20 or starting_seats != expected20:
        raise SystemExit("global seat/start balance failed")
    if len(cells) != 16 or set(cells.values()) != {5}:
        raise SystemExit("candidate x starting seat matrix is not exactly 5 each")
    if len(triplet_counts) != 20 or set(triplet_counts.values()) != {4}:
        raise SystemExit("triplet multiplicity is not exactly 4")
    if opponent_counts != Counter({opponent: 40 for opponent in OPPONENTS}):
        raise SystemExit(f"opponent appearance balance failed: {dict(opponent_counts)}")
    for opponent in OPPONENTS:
        if physical[opponent] != Counter({seat: 10 for seat in range(1, 5)}):
            raise SystemExit(f"physical seat balance failed for {opponent}: {dict(physical[opponent])}")
        rel_values = [relative[opponent][position] for position in (1, 2, 3)]
        if max(rel_values) - min(rel_values) > 2:
            raise SystemExit(f"relative position balance too wide for {opponent}: {rel_values}")
    if block_sizes != Counter({block: 16 for block in range(1, 6)}):
        raise SystemExit("block sizes must be exactly 16")
    for block in range(1, 6):
        if block_candidate[block] != Counter({seat: 4 for seat in range(1, 5)}):
            raise SystemExit(f"candidate seat block balance failed in block {block}")
        if block_start[block] != Counter({seat: 4 for seat in range(1, 5)}):
            raise SystemExit(f"starting seat block balance failed in block {block}")

    return {
        "schema_version": "rogshai-near-neighbor-balance-audit-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "status": "PASS",
        "scenario_count": 80,
        "block_count": 5,
        "scenarios_per_block": 16,
        "candidate_seat_each": 20,
        "starting_player_seat_each": 20,
        "candidate_by_starting_seat_cell_each": 5,
        "triplet_count": 20,
        "triplet_multiplicity_each": 4,
        "opponent_appearances_each": 40,
        "opponent_physical_seat_each": 10,
        "relative_position_counts": {opponent: dict(relative[opponent]) for opponent in OPPONENTS},
        "morcant_present": False,
        "cosmic_present": False,
        "unique_seed_count": 80,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit-output", required=True)
    args = parser.parse_args()
    rows = _build_rows()
    audit = _audit(rows)
    payload = {
        "schema_version": "rogshai-near-neighbor-schedule-1.0.0",
        "campaign_id": CAMPAIGN_ID,
        "evidence_class": "structural_model_estimates",
        "opponent_information_class": "well_supported_real_current_complete_or_official_precon",
        "scenario_count": 80,
        "candidate_count": 64,
        "target_game_count": 5120,
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
