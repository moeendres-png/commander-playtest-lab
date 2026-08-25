#!/usr/bin/env python3
import argparse, hashlib, itertools, json
from collections import Counter
from pathlib import Path

CAMPAIGN_ID = "rogshai-real-current-8-opponents-2026-08-25"
ENSEMBLE_ID = CAMPAIGN_ID
OPPONENTS = ["morcant","cosmic","blight","dance","wakanda","kaervek","lorehold","doom"]
# Compact frozen design tuple format:
# (triplet opponent indices a,b,c, candidate_seat, opponents on ascending non-candidate seats x,y,z, starting_player_seat_0_based)
PATTERNS = {
1:[(0,1,4,3,4,1,0,3),(0,2,3,1,0,2,3,1),(0,2,5,3,0,5,2,0),(0,2,6,4,0,2,6,0),(0,3,5,1,3,0,5,2),(0,4,7,3,7,0,4,1),(1,2,4,4,2,4,1,1),(1,3,4,2,3,4,1,2),(1,3,6,1,1,6,3,3),(1,3,7,4,3,7,1,2),(1,5,6,2,1,5,6,3),(2,4,6,2,4,2,6,0),(2,5,7,3,7,5,2,2),(3,6,7,1,6,3,7,0),(4,5,7,4,5,4,7,3),(5,6,7,2,6,5,7,1)],
2:[(0,1,5,4,1,0,5,1),(0,1,6,1,1,0,6,2),(0,2,3,2,0,3,2,3),(0,3,4,3,3,4,0,0),(0,3,6,4,6,3,0,2),(0,6,7,3,7,0,6,1),(1,2,4,1,4,1,2,3),(1,2,6,2,6,2,1,0),(1,3,5,3,5,3,1,2),(1,5,7,1,7,1,5,0),(2,4,5,1,2,4,5,1),(2,4,7,4,2,7,4,3),(2,6,7,4,2,6,7,0),(3,4,6,2,3,6,4,1),(3,5,7,2,7,5,3,2),(4,5,7,3,4,5,7,3)],
3:[(0,1,3,3,1,3,0,1),(0,1,4,3,1,0,4,2),(0,2,5,4,2,5,0,2),(0,2,7,4,0,2,7,3),(0,4,7,1,4,7,0,3),(0,6,7,4,7,6,0,0),(1,2,5,3,2,1,5,3),(1,3,7,1,7,3,1,0),(1,5,6,1,6,5,1,1),(1,5,7,2,5,1,7,0),(2,3,4,1,2,4,3,2),(2,3,6,2,6,3,2,1),(2,4,5,2,4,2,5,2),(3,4,6,2,3,6,4,3),(3,5,6,3,5,3,6,0),(4,6,7,4,6,7,4,1)],
4:[(0,1,3,1,0,3,1,0),(0,2,4,3,4,2,0,2),(0,3,5,3,0,3,5,3),(0,5,6,4,0,5,6,3),(0,5,7,3,5,7,0,0),(0,6,7,4,7,6,0,0),(1,2,3,1,1,2,3,1),(1,2,6,3,1,2,6,1),(1,2,7,1,1,7,2,2),(1,4,5,2,1,5,4,1),(1,6,7,2,6,1,7,2),(2,3,4,2,3,2,4,3),(2,5,6,4,2,5,6,1),(3,4,5,4,5,4,3,2),(3,4,7,2,4,7,3,0),(4,6,7,1,6,4,7,3)],
5:[(0,1,7,3,1,0,7,3),(0,2,4,3,2,4,0,0),(0,2,7,4,0,7,2,0),(0,3,6,3,6,0,3,1),(0,4,5,3,0,4,5,2),(0,4,6,2,4,0,6,2),(1,2,3,1,2,3,1,1),(1,3,5,1,5,1,3,2),(1,3,6,2,3,1,6,3),(1,4,7,4,7,1,4,1),(1,6,7,4,7,1,6,2),(2,3,5,4,5,3,2,3),(2,4,6,2,4,6,2,0),(2,5,7,1,5,7,2,3),(3,5,7,2,3,5,7,1),(4,5,6,1,6,5,4,0)],
6:[(0,1,2,4,2,0,1,1),(0,1,4,1,0,1,4,2),(0,1,5,1,1,0,5,3),(0,3,4,4,0,3,4,2),(0,3,7,2,7,3,0,3),(0,5,6,2,6,0,5,0),(1,2,3,3,3,2,1,0),(1,4,5,2,5,4,1,1),(1,4,6,4,1,4,6,3),(2,3,7,1,7,2,3,0),(2,4,7,1,4,7,2,1),(2,5,6,3,2,5,6,1),(2,6,7,3,6,7,2,2),(3,4,7,3,4,3,7,3),(3,5,6,2,3,5,6,2),(5,6,7,4,7,6,5,0)],
7:[(0,2,5,4,2,5,0,2),(0,2,6,4,2,6,0,3),(0,3,6,1,6,3,0,3),(0,3,7,1,0,3,7,0),(0,4,5,3,0,4,5,1),(0,5,7,1,7,5,0,1),(1,2,6,2,6,1,2,0),(1,2,7,1,2,7,1,2),(1,3,4,4,1,3,4,0),(1,3,7,3,7,3,1,2),(1,4,6,2,1,6,4,1),(1,5,7,4,5,1,7,1),(2,4,5,2,4,2,5,2),(2,4,6,3,6,2,4,3),(3,4,5,2,5,4,3,3),(3,6,7,3,3,7,6,0)],
8:[(0,1,2,1,1,2,0,0),(0,1,6,4,0,6,1,3),(0,1,7,3,1,0,7,2),(0,2,7,2,2,7,0,1),(0,3,4,1,3,0,4,1),(0,4,6,4,0,4,6,0),(1,2,5,4,1,5,2,1),(1,4,5,1,5,4,1,2),(1,4,7,3,4,1,7,3),(2,3,5,1,2,5,3,3),(2,3,6,2,6,3,2,2),(2,3,7,3,7,2,3,0),(3,5,6,2,5,3,6,3),(3,5,7,2,3,7,5,0),(4,5,6,3,5,6,4,1),(4,6,7,4,4,7,6,2)]}

def master_seed(global_index: int) -> int:
    raw = hashlib.sha256(f"{CAMPAIGN_ID}|{global_index}".encode()).digest()
    value = int.from_bytes(raw[:4], "big") & 0x7fffffff
    return value or 1

def build_all():
    out = {}
    global_index = 0
    for block in range(1, 9):
        rows = []
        for seed_index, pattern in enumerate(PATTERNS[block], 1):
            a,b,c,candidate_seat,x,y,z,start = pattern
            triplet = [OPPONENTS[i] for i in (a,b,c)]
            free_seats = [s for s in (1,2,3,4) if s != candidate_seat]
            opponent_by_seat = {str(s): OPPONENTS[o] for s,o in zip(free_seats,(x,y,z))}
            global_index += 1
            rows.append({
                "seed_index": seed_index,
                "global_seed_index": global_index,
                "master_seed": master_seed(global_index),
                "candidate_seat": candidate_seat,
                "xmage_starting_player_seat_0_based": start,
                "opponent_triplet": triplet,
                "opponent_by_seat": opponent_by_seat,
                "triplet_contract": f"REAL8-B{block:02d}",
            })
        out[block] = rows
    return out

def audit(blocks):
    rows = [r for block in range(1,9) for r in blocks[block]]
    assert len(rows) == 128
    seeds = [int(r["master_seed"]) for r in rows]
    assert len(set(seeds)) == 128
    assert Counter(int(r["candidate_seat"]) for r in rows) == Counter({1:32,2:32,3:32,4:32})
    assert Counter(int(r["xmage_starting_player_seat_0_based"]) for r in rows) == Counter({0:32,1:32,2:32,3:32})
    opponent_counts = Counter()
    opponent_seats = Counter()
    triplets = Counter()
    pairs = Counter()
    for r in rows:
        candidate_seat = int(r["candidate_seat"])
        t = tuple(sorted(str(x) for x in r["opponent_triplet"]))
        assert len(t) == 3 and len(set(t)) == 3
        triplets[t] += 1
        for o in t:
            opponent_counts[o] += 1
        by = {int(k):str(v) for k,v in r["opponent_by_seat"].items()}
        assert set(by) == ({1,2,3,4} - {candidate_seat})
        assert sorted(by.values()) == sorted(t)
        for seat,o in by.items():
            opponent_seats[(o,seat)] += 1
        for pair in itertools.combinations(t,2):
            pairs[pair] += 1
    assert opponent_counts == Counter({o:48 for o in OPPONENTS})
    assert all(opponent_seats[(o,s)] == 12 for o in OPPONENTS for s in (1,2,3,4))
    assert len(triplets) == 56 and Counter(triplets.values()) == Counter({2:40,3:16})
    assert len(pairs) == 28 and Counter(pairs.values()) == Counter({13:8,14:20})
    for block in range(1,9):
        br = blocks[block]
        assert len(br) == 16
        assert Counter(int(r["candidate_seat"]) for r in br) == Counter({1:4,2:4,3:4,4:4})
        assert Counter(int(r["xmage_starting_player_seat_0_based"]) for r in br) == Counter({0:4,1:4,2:4,3:4})
        assert Counter(o for r in br for o in r["opponent_triplet"]) == Counter({o:6 for o in OPPONENTS})
        per_seat = Counter((o,int(s)) for r in br for s,o in r["opponent_by_seat"].items())
        for o in OPPONENTS:
            values = [per_seat[(o,s)] for s in (1,2,3,4)]
            assert sum(values) == 6 and all(v in (1,2) for v in values)
    return {
        "game_count": 128,
        "seed_count": 128,
        "seed_min": min(seeds),
        "seed_max": max(seeds),
        "opponent_appearances_each": 48,
        "opponent_seat_appearances_each": 12,
        "candidate_seat_appearances_each": 32,
        "starting_player_seat_appearances_each": 32,
        "triplet_multiplicity_distribution": dict(sorted(Counter(triplets.values()).items())),
        "pair_multiplicity_distribution": dict(sorted(Counter(pairs.values()).items())),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", type=int)
    ap.add_argument("--output")
    ap.add_argument("--audit-output")
    args = ap.parse_args()
    blocks = build_all()
    summary = audit(blocks)
    if args.audit_output:
        Path(args.audit_output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if args.block is not None:
        if args.block not in blocks:
            raise SystemExit("block must be 1..8")
        if not args.output:
            raise SystemExit("--output required with --block")
        rows = blocks[args.block]
        obj = {
            "schema_version": "rogshai-real-current-8-seed-schedule-1.0.0",
            "ensemble_id": ENSEMBLE_ID,
            "campaign_id": CAMPAIGN_ID,
            "block": args.block,
            "game_count_per_candidate": 16,
            "master_seeds": [int(r["master_seed"]) for r in rows],
            "balance": {
                "candidate_seat_counts": dict(Counter(str(r["candidate_seat"]) for r in rows)),
                "starting_player_seat_counts_0_based": dict(Counter(str(r["xmage_starting_player_seat_0_based"]) for r in rows)),
                "opponent_appearance_count_per_deck": 6,
                "opponent_per_seat_counts_each_block": "1_or_2; global total exactly 12 per opponent per seat across 8 blocks"
            },
            "schedule": rows,
        }
        Path(args.output).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
