#!/usr/bin/env python3
"""WS232 U5 closures + replay/RNG runs (test-only orchestration).

U5-A amount:        Choice of Damnations (Toshiro/Swamp), 2P.
U5-C target_amount: Arc Lightning (Rograkh/Mountain), 2P (+3P/5P option).
U5-B multi_amount:  Travel Preparations (Rhys/Forest+Plains) seed hunt,
                    backups Common Bond (Rhys), Hunger of the Howlpack (Omnath).
U5-D numeric replay + REPLAY_RNG_5: record_tape + dual replay (Lions per N;
                    numeric-bearing Arc tape).
U5-E 5P impact:     5P Lions record + class census through repaired stack.

All games fresh-process; public-only logs; engine owns legality.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
sys.path.insert(0, str(BIN.parent.parent.parent / "src"))

from nscoped_runner import (  # noqa: E402
    drive_game,
    make_binding,
    make_deck,
    make_scenario,
)
from run_card_campaign import compact_run  # noqa: E402

REPO_ROOT = BIN.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"
RUNS_U5 = NS / "runs" / "u5"
TAPES = NS / "tapes"
RUNS_U5.mkdir(parents=True, exist_ok=True)
TAPES.mkdir(parents=True, exist_ok=True)


def sym_deck(tag, commander, main):
    return make_deck(tag, commander, main)


def run_and_store(run_id, card, commander, main, n, seed, budget, focus=None):
    decks = tuple(make_deck(f"{run_id}-{s}", commander, main) for s in range(1, n + 1))
    sc = make_scenario(run_id, n, seed, decks)
    pilots = tuple(make_binding(s, d) for s, d in zip(range(1, n + 1), decks, strict=True))
    run = drive_game(sc, decks, pilots, focus_names=(focus or card,),
                     max_decisions=budget)
    (RUNS_U5 / f"{run_id}.json").write_text(json.dumps(
        {"run_id": run_id, "player_count": n, "seed": seed,
         "engine_commit": run["engine_commit"], "run": compact_run(run)},
        indent=1, sort_keys=True) + "\n")
    return run


def main() -> int:
    which = sys.argv[1:] or ["amount", "target", "multi", "replay"]
    out: dict = {}
    if "amount" in which:
        main_cards = ["Choice of Damnations"] + ["Swamp"] * 98
        run = run_and_store("U5_AMOUNT_DAMNATIONS_2P", "Choice of Damnations",
                            "Toshiro Umezawa", tuple(main_cards), 2, 424242, 600)
        nums = [(e["offset"], e["decision_class"], e["numeric_min"],
                 e["numeric_max"], e["numeric_choice"]) for e in run["log"]
                if e.get("numeric_min") is not None]
        out["amount"] = {
            "run": "U5_AMOUNT_DAMNATIONS_2P",
            "offers": [e["offset"] for e in run["log"] if e["focus_offered"]],
            "selects": [e["offset"] for e in run["log"] if e["focus_selected"]],
            "numeric_frames": nums,
            "final_life": [o.get("life") for o in run["final_outcomes"]],
            "failure": run["failure"],
        }
        print("U5-A amount:", out["amount"], flush=True)
    if "target" in which:
        main_cards = ["Arc Lightning"] + ["Mountain"] * 98
        run = run_and_store("U5_TARGET_ARC_2P", "Arc Lightning",
                            "Rograkh, Son of Rohgahh", tuple(main_cards), 2, 424242, 500)
        tams = [(e["offset"], e["numeric_min"], e["numeric_max"], e["numeric_choice"])
                for e in run["log"] if e["decision_class"] == "target_amount"]
        out["target"] = {
            "run": "U5_TARGET_ARC_2P",
            "selects": [e["offset"] for e in run["log"] if e["focus_selected"]],
            "target_amount_frames": tams,
            "final_life": [o.get("life") for o in run["final_outcomes"]],
            "failure": run["failure"],
        }
        print("U5-C target:", out["target"], flush=True)
    if "multi" in which:
        cands = [
            ("Travel Preparations", "Rhys the Redeemed", ("Forest", "Plains")),
            ("Common Bond", "Rhys the Redeemed", ("Forest", "Plains")),
            ("Hunger of the Howlpack", "Omnath, Locus of Mana", ("Forest",)),
        ]
        hits = []
        for card, cmdr, landtypes in cands:
            nlands: dict = {land: 0 for land in landtypes}
            for i in range(98):
                nlands[landtypes[i % len(landtypes)]] += 1
            main_m = [card]
            for land, count in nlands.items():
                main_m.extend([land] * count)
            for seed in (424242, 777001, 777002, 777003):
                decks = tuple(make_deck(f"ws232-u5multi-{card[:4]}-{seed}-{s}", cmdr, tuple(main_m))
                              for s in (1, 2))
                sc = make_scenario(f"ws232-u5multi-{card[:4]}-{seed}", 2, seed, decks)
                pilots = tuple(make_binding(s, d) for s, d in zip((1, 2), decks, strict=True))
                run = drive_game(sc, decks, pilots, focus_names=(card,), max_decisions=500)
                multis = [(e["offset"], e["decision_class"]) for e in run["log"]
                          if e["decision_class"] == "multi_amount"]
                sels = [e["offset"] for e in run["log"] if e["focus_selected"]]
                print(f"multi {card} seed={seed} sel={sels[:3]} multis={multis[:3]} "
                      f"fail={str(run['failure'])[:60]}", flush=True)
                if multis:
                    run_id = f"U5_MULTI_{card[:4].upper()}_2P_seed{seed}"
                    (RUNS_U5 / f"{run_id}.json").write_text(json.dumps(
                        {"run_id": run_id, "card": card, "seed": seed,
                         "engine_commit": run["engine_commit"],
                         "multi_frames": multis, "run": compact_run(run)},
                        indent=1, sort_keys=True) + "\n")
                    hits.append((card, seed, run_id))
                    break
            if hits:
                break
        out["multi"] = {"hits": hits}
        print("U5-B multi:", hits, flush=True)
    (NS / "U5_RUN_RESULTS.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
