#!/usr/bin/env python3
import argparse, base64, gzip, json
from pathlib import Path

ENSEMBLE_ID = "rogshai-12-complete-opponents-no-cosmic-no-morcant-2026-08-25"
PATTERN_B64 = """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"""

def load_patterns():
    return json.loads(gzip.decompress(base64.b64decode(PATTERN_B64)).decode())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--block", type=int, required=True)
    ap.add_argument("--output", required=True)
    args=ap.parse_args()
    b=args.block
    if b == 2:
        src=2
        day=3
        contract="EXT12-B02R"
    elif 9 <= b <= 16:
        src=b-8
        day=10+(b-9)
        contract=f"EXT12-R2-B{b:02d}"
    else:
        raise SystemExit("supported blocks: 2, 9..16")
    patterns=load_patterns()
    games=patterns[str(src)]
    seeds=[int(f"202609{day:02d}{i:02d}") for i in range(1,17)]
    schedule=[]
    for i,(g,seed) in enumerate(zip(games,seeds),1):
        x=dict(g)
        x["master_seed"]=seed
        x["seed_index"]=i
        x["triplet_contract"]=contract
        schedule.append(x)
    candidate_counts={str(s):sum(g["candidate_seat"]==s for g in schedule) for s in [1,2,3,4]}
    start_counts={str(s):sum(g["xmage_starting_player_seat_0_based"]==s for g in schedule) for s in [0,1,2,3]}
    obj={
        "balance": {
            "candidate_seat_counts": candidate_counts,
            "opponent_appearance_count_per_deck": 4,
            "opponent_seat_count_per_deck_per_seat": 1,
            "starting_player_seat_counts_0_based": start_counts,
        },
        "block": b,
        "ensemble_id": ENSEMBLE_ID,
        "game_count_per_candidate": 16,
        "master_seeds": seeds,
        "schedule": schedule,
    }
    Path(args.output).write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n")

if __name__=="__main__":
    main()
