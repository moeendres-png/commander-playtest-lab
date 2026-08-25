#!/usr/bin/env python3
import argparse, base64, gzip, hashlib, itertools, json
from collections import Counter
from pathlib import Path

CAMPAIGN_ID = "rogshai-real-current-8-opponents-2026-08-25"
ENSEMBLE_ID = "rogshai-real-current-8-opponents-2026-08-25"
OPPONENTS = ["morcant","cosmic","blight","dance","wakanda","kaervek","lorehold","doom"]
PATTERN_B64 = """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"""

def load_patterns():
    return json.loads(gzip.decompress(base64.b64decode(PATTERN_B64)).decode())

def master_seed(global_index: int) -> int:
    raw = hashlib.sha256(f"{CAMPAIGN_ID}|{global_index}".encode()).digest()
    value = int.from_bytes(raw[:4], "big") & 0x7fffffff
    return value or 1

def build_all():
    patterns = load_patterns()
    all_blocks = {}
    global_index = 0
    for b in range(1,9):
        schedule=[]
        for i,pat in enumerate(patterns[str(b)],1):
            global_index += 1
            x=dict(pat)
            x["seed_index"]=i
            x["global_seed_index"]=global_index
            x["master_seed"]=master_seed(global_index)
            x["triplet_contract"]=f"REAL8-B{b:02d}"
            schedule.append(x)
        all_blocks[b]=schedule
    return all_blocks

def audit(all_blocks):
    all_rows=[r for b in range(1,9) for r in all_blocks[b]]
    assert len(all_rows)==128
    seeds=[int(r["master_seed"]) for r in all_rows]
    assert len(set(seeds))==128
    assert Counter(int(r["candidate_seat"]) for r in all_rows)==Counter({1:32,2:32,3:32,4:32})
    assert Counter(int(r["xmage_starting_player_seat_0_based"]) for r in all_rows)==Counter({0:32,1:32,2:32,3:32})
    opp=Counter(); opp_seat=Counter(); triplets=Counter(); pairs=Counter()
    for r in all_rows:
        t=tuple(sorted(str(x) for x in r["opponent_triplet"]))
        assert len(t)==3 and len(set(t))==3
        triplets[t]+=1
        for o in t: opp[o]+=1
        by={int(k):str(v) for k,v in r["opponent_by_seat"].items()}
        assert set(by)==({1,2,3,4}-{int(r["candidate_seat"])})
        assert sorted(by.values())==sorted(t)
        for s,o in by.items(): opp_seat[(o,s)]+=1
        for p in itertools.combinations(t,2): pairs[p]+=1
    assert opp==Counter({o:48 for o in OPPONENTS})
    assert all(opp_seat[(o,s)]==12 for o in OPPONENTS for s in [1,2,3,4])
    assert len(triplets)==56 and Counter(triplets.values())==Counter({2:40,3:16})
    assert len(pairs)==28 and Counter(pairs.values())==Counter({13:8,14:20})
    for b,rows in all_blocks.items():
        assert len(rows)==16
        assert Counter(int(r["candidate_seat"]) for r in rows)==Counter({1:4,2:4,3:4,4:4})
        assert Counter(int(r["xmage_starting_player_seat_0_based"]) for r in rows)==Counter({0:4,1:4,2:4,3:4})
        bc=Counter(o for r in rows for o in r["opponent_triplet"])
        assert bc==Counter({o:6 for o in OPPONENTS})
        bs=Counter((o,int(s)) for r in rows for s,o in r["opponent_by_seat"].items())
        for o in OPPONENTS:
            vals=[bs[(o,s)] for s in [1,2,3,4]]
            assert sum(vals)==6 and all(v in (1,2) for v in vals)
    return {
        "game_count":128,
        "opponent_appearances_each":48,
        "opponent_seat_appearances_each":12,
        "triplet_multiplicity_distribution":dict(sorted(Counter(triplets.values()).items())),
        "pair_multiplicity_distribution":dict(sorted(Counter(pairs.values()).items())),
        "seed_min":min(seeds),
        "seed_max":max(seeds),
        "seed_count":len(seeds),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--block",type=int)
    ap.add_argument("--output")
    ap.add_argument("--audit-output")
    args=ap.parse_args()
    blocks=build_all()
    summary=audit(blocks)
    if args.audit_output:
        Path(args.audit_output).write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    if args.block is not None:
        if args.block not in blocks: raise SystemExit("block must be 1..8")
        rows=blocks[args.block]
        obj={
            "schema_version":"rogshai-real-current-8-seed-schedule-1.0.0",
            "ensemble_id":ENSEMBLE_ID,
            "campaign_id":CAMPAIGN_ID,
            "block":args.block,
            "game_count_per_candidate":16,
            "master_seeds":[int(r["master_seed"]) for r in rows],
            "balance":{
                "candidate_seat_counts":dict(Counter(str(r["candidate_seat"]) for r in rows)),
                "starting_player_seat_counts_0_based":dict(Counter(str(r["xmage_starting_player_seat_0_based"]) for r in rows)),
                "opponent_appearance_count_per_deck":6,
                "opponent_per_seat_counts_each_block":"1_or_2; global total exactly 12 per opponent per seat across 8 blocks"
            },
            "schedule":rows
        }
        if not args.output: raise SystemExit("--output required with --block")
        Path(args.output).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")

if __name__=="__main__":
    main()
