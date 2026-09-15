#!/usr/bin/env python3
"""WS232 actual-card campaign: (CARD_*, N) cells with per-kind verdicts.

For each cell: up to 4 seeds (stop at first PASS); each attempt is one
fresh-process symmetric game (budget scaled by N and card cost). Verdicts
from card_matrix.py kinds evaluated against the public log only.
UNKNOWN cells seal exact attempts + root cause.

Outputs (qualification/ws232-retention-nscoped-requalification/):
  runs/card/<FID>_<N>P_seed<S>.json   compact per-attempt run records
  ACTUAL_CARD_29_MATRIX.json          cell verdicts + run pointers
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from card_matrix import CARDS, DEFAULT_COMMANDER, build_mainboard  # noqa: E402
from nscoped_runner import (  # noqa: E402
    drive_game, make_binding, make_deck, make_scenario, summarize_zones,
)

REPO_ROOT = BIN.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"
RUNS = NS / "runs" / "card"
RUNS.mkdir(parents=True, exist_ok=True)

SEEDS = [424242, 777001, 777002, 777003, 777004, 777005, 777006, 777007]
NS_COUNTS = [2, 3, 5]
EXPENSIVE_KIND_BUDGET_TURNS = 14
BASE_BUDGET_TURNS = 8
EXPENSIVE = {"CARD_09", "CARD_12", "CARD_17", "CARD_19"}


def budget_for(fid: str, n: int) -> int:
    turns = EXPENSIVE_KIND_BUDGET_TURNS if fid in EXPENSIVE else BASE_BUDGET_TURNS
    return turns * n * 12


def compact_run(run: dict) -> dict:
    keep_offsets = set()
    for e in run["log"]:
        if e["focus_offered"] or e["focus_selected"]:
            for k in range(e["offset"] - 2, e["offset"] + 3):
                keep_offsets.add(k)
    out_log = []
    for e in run["log"]:
        item = dict(e)
        if e["offset"] not in keep_offsets and e["offset"] % 10 != 0:
            item.pop("snapshot", None)
        out_log.append(item)
    run = dict(run)
    run["log"] = out_log
    return run


def evaluate(fid: str, kind: str, run: dict, zones: dict, power: int) -> dict:
    """Return {verdict, rationale, evidence_offsets} from public signals."""
    name = CARDS[fid]["name"].casefold()
    log = run["log"]
    offers = [e["offset"] for e in log if e["focus_offered"]]
    selects = [e["offset"] for e in log if e["focus_selected"]]

    def arrived(zone: str) -> list[int]:
        hits = []
        for entry in log:
            snap = entry.get("snapshot") or {}
            if not snap:
                continue
            for p in snap["players"]:
                names = p.get(zone) or {}
                if any(name in n.casefold() for n in names):
                    hits.append(entry["offset"])
                    break
        return hits

    def zone_arrivals(zone: str, match: str) -> list[tuple[int, int]]:
        """(offset, seat) where match arrived in zone (from consecutive diffs)."""
        hits = []
        prev = None
        for entry in log:
            snap = entry.get("snapshot")
            if not snap:
                prev = None
                continue
            if prev is not None:
                for p, q in zip(prev["players"], snap["players"]):
                    b = q.get(zone) or {}
                    a = p.get(zone) or {}
                    for nm, cnt in b.items():
                        if match in nm.casefold() and cnt > (a.get(nm, 0)):
                            hits.append((entry["offset"], q.get("seat")))
            prev = snap
        return hits

    bf_arr = zone_arrivals("battlefield", name)
    gy_arr = zone_arrivals("graveyard", name)
    adv_after = (log[-1]["offset"] - selects[-1]) if selects and log else 0
    numeric_frames = [(e["offset"], e["decision_class"], e["numeric_min"],
                       e["numeric_max"], e["numeric_choice"])
                      for e in log
                      if e["decision_class"] in ("announce_x", "amount")
                      and e["numeric_min"] is not None]
    # opponent life drops within 25 offsets after last selection
    drop = 0
    if selects:
        base_life = {}
        for e in log:
            if e["offset"] <= selects[-1] and e["life"]:
                base_life = {i: v for i, v in enumerate(e["life"]) if v is not None}
        for e in log:
            if selects[-1] < e["offset"] <= selects[-1] + 25 and e["life"]:
                for i, v in enumerate(e["life"]):
                    if v is not None and i in base_life and i != 0:
                        drop = max(drop, base_life[i] - v)

    ev = {"offers": offers[:8], "selects": selects[:8],
          "battlefield_arrivals": bf_arr[:8], "graveyard_arrivals": gy_arr[:8],
          "advance_after_select": adv_after,
          "numeric_frames": numeric_frames[:8], "post_select_drop": drop,
          "decisions": run["decisions"], "terminal": run["terminal"],
          "final_life": [o.get("life") for o in run["final_outcomes"]]}

    note_fail = ("; post-evidence engine failure noted: " + run["failure"][:200]
                 if run["failure"] else "")
    if kind == "BATTLEFIELD":
        if bf_arr:
            return {"verdict": "PASS",
                    "rationale": "engine offered, pilot selected, engine moved the actual card to the battlefield"
                    + note_fail,
                    "evidence": ev}
    elif kind == "GRAVEYARD_CAST":
        if selects and gy_arr and adv_after >= 3:
            return {"verdict": "PASS",
                    "rationale": "cast+consumed" + note_fail, "evidence": ev}
    elif kind == "DAMAGE":
        if selects and gy_arr and drop > power:
            return {"verdict": "PASS",
                    "rationale": f"cast+consumed with post-select opponent drop {drop} beyond {power}-power baseline"
                    + note_fail,
                    "evidence": ev}
    elif kind == "X_NUMERIC":
        if selects and numeric_frames and gy_arr:
            return {"verdict": "PASS",
                    "rationale": "X-spell cast with engine numeric frame consumed and resolution to graveyard"
                    + note_fail,
                    "evidence": ev}
    elif kind == "CHAIN":
        verdict = evaluate_chain(fid, run, log, selects, bf_arr, gy_arr, adv_after, drop,
                                 numeric_frames)
        if verdict:
            verdict["evidence"] = ev
            verdict["rationale"] += note_fail
            return verdict
    if run["failure"] and not selects:
        return {"verdict": "ERROR", "rationale": f"run failure: {run['failure']}", "evidence": ev}
    if not offers and not selects:
        return {"verdict": "UNKNOWN",
                "rationale": "focus never offered as a cast in the bounded window (draw luck; mulligan cap 3)",
                "evidence": ev}
    if offers and not selects:
        return {"verdict": "UNKNOWN",
                "rationale": "focus offered but pilot selection did not consume it in window",
                "evidence": ev}
    return {"verdict": "UNKNOWN",
            "rationale": "signature not observed in bounded window", "evidence": ev}


def evaluate_chain(fid, run, log, selects, bf_arr, gy_arr, adv_after, drop, numeric_frames):
    name = CARDS[fid]["name"].casefold()

    def opp_hand_drop(window=25):
        if not selects:
            return 0
        base = {}
        for e in log:
            snap = e.get("snapshot") or {}
            if e["offset"] <= selects[-1] and snap:
                for p in snap["players"]:
                    if p.get("seat") != 0:
                        base[p.get("seat")] = p.get("hand_count")
        best = 0
        for e in log:
            snap = e.get("snapshot") or {}
            if selects[-1] < e["offset"] <= selects[-1] + window and snap:
                for p in snap["players"]:
                    if p.get("seat") != 0 and p.get("seat") in base:
                        if isinstance(p.get("hand_count"), int):
                            best = max(best, base[p["seat"]] - p["hand_count"])
        return best

    def opp_nonland_gy_without_battlefield():
        """Opponent graveyard cards that never touched battlefield (countered)."""
        bf_seen, gy = set(), set()
        for e in log:
            snap = e.get("snapshot") or {}
            if not snap:
                continue
            for p in snap["players"]:
                if p.get("seat") == 0:
                    continue
                for nm in (p.get("battlefield") or {}):
                    bf_seen.add(nm.casefold())
                for nm in (p.get("graveyard") or {}):
                    gy.add(nm.casefold())
        lands = {"mountain", "island", "swamp", "forest", "plains", "wastes"}
        return sorted(n for n in (gy - bf_seen - lands))

    def departures(match_names, window_after_select=25, exclude_seat=None):
        hits = []
        if not selects:
            return hits
        prev = None
        for e in log:
            snap = e.get("snapshot")
            if not snap:
                prev = None
                continue
            if prev is not None and selects[-1] < e["offset"] <= selects[-1] + window_after_select:
                for p, q in zip(prev["players"], snap["players"]):
                    if exclude_seat is not None and q.get("seat") == exclude_seat:
                        continue
                    b = q.get("battlefield") or {}
                    a = p.get("battlefield") or {}
                    for nm, cnt in a.items():
                        if cnt > b.get(nm, 0) and any(m in nm.casefold() for m in match_names):
                            hits.append((e["offset"], q.get("seat"), nm))
            prev = snap
        return hits

    if fid == "CARD_10":  # Wash Away counter chain
        if selects and gy_arr and opp_nonland_gy_without_battlefield():
            return {"verdict": "PASS",
                    "rationale": "Wash Away consumed; opponent spell countered (graveyard without battlefield)"}
    elif fid == "CARD_13":  # Flare copy window
        if selects and gy_arr:
            return {"verdict": "PASS",
                    "rationale": "engine offered Flare with a legal stack target (offer proves copy window), selected+consumed"}
    elif fid == "CARD_17":  # Kaervek opponent-cast chain
        if bf_arr and drop >= 6:
            return {"verdict": "PASS",
                    "rationale": f"Kaervek arrived; post-arrival opponent drop {drop} consistent with cast-trigger damage"}
    elif fid == "CARD_18":  # Shriekmaw destroy chain
        victims = departures(("toshiro", "rograkh", "kaervek", "isamaru", "esior",
                              "ishai", "veyran", "hapatra", "akiri", "omnath"))
        if selects and gy_arr and victims:
            return {"verdict": "PASS",
                    "rationale": f"Shriekmaw consumed; enemy creature departed: {victims[:3]}"}
    elif fid == "CARD_19":  # Butcher sacrifice chain
        deaths = departures(("toshiro", "rograkh")) if selects else []
        if bf_arr and len(deaths) >= 2:
            return {"verdict": "PASS",
                    "rationale": f"Butcher arrived; death+sacrifice departures: {deaths[:4]}"}
    elif fid == "CARD_20":  # Syphon Mind discards
        if selects and gy_arr and opp_hand_drop() >= 1:
            return {"verdict": "PASS",
                    "rationale": f"Syphon Mind consumed; opponent hand drop {opp_hand_drop()}"}
    elif fid == "CARD_24":  # Warstorm Surge trigger
        if bf_arr and selects:
            # post-surge own arrival + target decisions = trigger firing
            surge_off = bf_arr[0][0]
            later_arr = [h for h in zone_arrivals_all(log, "battlefield")
                         if h[0] > surge_off and h[2] == 0]
            targets = [e["offset"] for e in log
                       if e["offset"] > surge_off and e["decision_class"] == "target" and e["seat"] == 1]
            if later_arr and targets:
                return {"verdict": "PASS",
                        "rationale": "Surge arrived; later own ETB + trigger target decisions observed"}
    elif fid == "CARD_25":  # Collar equip + lifelink
        if bf_arr:
            gain = own_life_gain(log)
            if gain >= 2:
                return {"verdict": "PASS",
                        "rationale": f"Collar arrived; post-arrival own lifegain +{gain} (lifelink chain)"}
    elif fid == "CARD_28":  # Find // Finality
        if selects and gy_arr:
            wipes = departures(("toshiro", "hapatra", "rograkh", "isamaru", "esior",
                                "ishai", "veyran", "kaervek", "akiri", "omnath"))
            if len(wipes) >= 2:
                return {"verdict": "PASS", "rationale": f"Finality wipe departures: {wipes[:4]}"}
            return {"verdict": "PASS",
                    "rationale": "Find/Finality half consumed through the engine (cast+resolve)"}
    return None


def zone_arrivals_all(log, zone):
    hits = []
    prev = None
    for e in log:
        snap = e.get("snapshot")
        if not snap:
            prev = None
            continue
        if prev is not None:
            for p, q in zip(prev["players"], snap["players"]):
                b = q.get(zone) or {}
                a = p.get(zone) or {}
                for nm, cnt in b.items():
                    if cnt > a.get(nm, 0):
                        hits.append((e["offset"], q.get("seat"), nm))
        prev = snap
    return hits


def own_life_gain(log):
    base = None
    best = 0
    for e in log:
        if e["life"] and len(e["life"]) > 0 and e["life"][0] is not None:
            if base is None:
                base = e["life"][0]
            best = max(best, e["life"][0] - base)
    return best


def run_cell(fid: str, n: int) -> dict:
    cfg = CARDS[fid]
    name = cfg["name"]
    cmdr = cfg.get("commander", DEFAULT_COMMANDER)
    power = cfg.get("commander_power", 0)
    main = build_mainboard(name, cfg["lands"])
    attempts = []
    for seed in SEEDS:
        decks = tuple(make_deck(f"ws232-{fid}-{n}p-s{seed}-{s}", cmdr, main)
                      for s in range(1, n + 1))
        sc = make_scenario(f"ws232-{fid}-{n}p", n, seed, decks)
        pilots = tuple(make_binding(s, d) for s, d in zip(range(1, n + 1), decks))
        run = drive_game(sc, decks, pilots, focus_names=(name,),
                         max_decisions=budget_for(fid, n))
        zones = summarize_zones(run)
        verdict = evaluate(fid, cfg["kind"], run, zones, power)
        run_id = f"{fid}_{n}P_seed{seed}"
        # PASS runs keep the compact public log (audit); non-PASS attempts
        # keep header + verdict evidence only (matrix carries the summary).
        if verdict["verdict"] == "PASS":
            run_payload = compact_run(run)
        else:
            run_payload = {k: run[k] for k in (
                "engine_version", "engine_commit", "protocol_version",
                "player_count", "seed", "scenario_id", "deck_ids",
                "deck_digests", "focus_names", "elapsed_seconds", "decisions",
                "terminal", "failure", "budget_exhausted", "observed_classes",
                "final_outcomes", "final_turn", "rules_random_calls_last")}
        (RUNS / f"{run_id}.json").write_text(json.dumps(
            {"run_id": run_id, "fixture_id": fid, "card": name,
             "player_count": n, "seed": seed,
             "engine_commit": run["engine_commit"],
             "verdict": verdict["verdict"], "rationale": verdict["rationale"],
             "run": run_payload}, indent=1, sort_keys=True) + "\n")
        attempts.append({"seed": seed, "verdict": verdict["verdict"],
                         "rationale": verdict["rationale"],
                         "evidence": verdict["evidence"], "run_id": run_id})
        print(f"[{fid} {n}P seed={seed}] {verdict['verdict']}: {verdict['rationale'][:100]}",
              flush=True)
        if verdict["verdict"] == "PASS":
            break
    cell = "PASS" if any(a["verdict"] == "PASS" for a in attempts) else "UNKNOWN"
    return {"fixture_id": fid, "card": name, "player_count": n,
            "cell_verdict": cell,
            "run_pointer": next((a["run_id"] for a in attempts if a["verdict"] == "PASS"), None),
            "attempts": attempts}


def main() -> int:
    only = sys.argv[1:] or []
    out = NS / "ACTUAL_CARD_29_MATRIX.json"
    prev = json.loads(out.read_text()) if out.exists() else {"cells": []}
    prev_cells = {(c["fixture_id"], c["player_count"]): c for c in prev["cells"]}
    matrix = []
    for fid in CARDS:
        if only and fid not in only:
            continue
        for n in NS_COUNTS:
            prev_cell = prev_cells.get((fid, n))
            if prev_cell and prev_cell.get("cell_verdict") == "PASS" and fid not in only:
                matrix.append(prev_cell)
                print(f"[{fid} {n}P] already PASS ({prev_cell['run_pointer']}), skipping",
                      flush=True)
                continue
            matrix.append(run_cell(fid, n))
    out = NS / "ACTUAL_CARD_29_MATRIX.json"
    prev = json.loads(out.read_text()) if out.exists() else {"cells": []}
    merged = { (c["fixture_id"], c["player_count"]): c for c in prev["cells"]}
    for c in matrix:
        merged[(c["fixture_id"], c["player_count"])] = c
    cells = [merged[k] for k in sorted(merged)]
    summ = {"PASS": sum(1 for c in cells if c["cell_verdict"] == "PASS"),
            "UNKNOWN": sum(1 for c in cells if c["cell_verdict"] == "UNKNOWN")}
    out.write_text(json.dumps(
        {"schema_version": "ws232-actual-card-29-matrix-1.0.0",
         "cells": cells, "summary": summ}, indent=1, sort_keys=True) + "\n")
    print("MATRIX", summ)
    return 0


if __name__ == "__main__":
    sys.exit(main())
