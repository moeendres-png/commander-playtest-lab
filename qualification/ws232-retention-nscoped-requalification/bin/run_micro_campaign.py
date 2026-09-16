#!/usr/bin/env python3
"""WS232 micro-rules 13 campaign: N-scoped mechanism evidence.

Primary vehicle: symmetric Lions games (published WS215 deck, trigger- and
anthem-bearing but not trigger-rich by S9 standards) at 2P/3P/5P through
the unmodified Rules Core. Each mechanism is evaluated against the public
run log only. Where Lions cannot provoke an engine-owned mechanism with
current fixtures, the cell stays UNKNOWN (no code inspection substitute,
no S9 deck engineering). Two mechanisms cite exact WS232 card runs where
those runs observe the mechanism at the required N (dedup: same exact run,
independently evaluated criterion):

  MICRO_MODES  -> Burn Down the House mode decisions (CARD_26 runs, all N)
  MICRO_TRIGGERS -> trigger_order decisions (card runs, all N) + Lions tokens

MICRO_COPY / MICRO_CONTROL have no sources in any current fixture and stay
UNKNOWN. MICRO_PREVENTION has no source/target pair in symmetric Lions and
stays UNKNOWN.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from nscoped_runner import (  # noqa: E402
    drive_game, make_binding, make_deck, make_scenario,
)

REPO_ROOT = BIN.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"
RUNS = NS / "runs" / "micro"
RUNS.mkdir(parents=True, exist_ok=True)

LIONS_COMMANDER = "Isamaru, Hound of Konda"
SEEDS = [424242, 777001]
BUDGETS = {2: 350, 3: 500, 5: 800}

MICRO_IDS = ["MICRO_COMBAT", "MICRO_CONTINUOUS_EFFECTS", "MICRO_CONTROL",
             "MICRO_COPY", "MICRO_LAYERS", "MICRO_MODES", "MICRO_PREVENTION",
             "MICRO_REPLACEMENT", "MICRO_RULES_RANDOMNESS", "MICRO_STACK",
             "MICRO_STATE_BASED_ACTIONS", "MICRO_TRIGGERS",
             "MICRO_ZONE_CHANGES"]

ANTHEMS = {"Captain of the Watch", "Elesh Norn, Grand Cenobite",
           "Avacyn, Angel of Hope", "Gideon Jura"}


def lions_deck():
    doc = json.loads((REPO_ROOT / "qualification/ws215-xmage-variable-player-multicardinality/decks/ws215_lions.json").read_text())
    main = tuple(c for card in doc["cards"] if card["zone"] == "main"
                 for c in [card["oracle_name"]] * card["quantity"])
    cmdr = next(c["oracle_name"] for c in doc["cards"] if c["zone"] == "commander")
    names = {cmdr} | {c["oracle_name"] for c in doc["cards"] if c["zone"] == "main"}
    return cmdr, main, names


def arrivals(log, zone, match=None, after=0, before=10**9):
    hits = []
    prev = None
    for e in log:
        snap = e.get("snapshot")
        if not snap:
            prev = None
            continue
        if prev is not None and after < e["offset"] <= before:
            for p, q in zip(prev["players"], snap["players"]):
                b = q.get(zone) or {}
                a = p.get(zone) or {}
                for nm, cnt in b.items():
                    if cnt > a.get(nm, 0) and (match is None or match(nm)):
                        hits.append((e["offset"], q.get("seat"), nm))
        prev = snap
    return hits


def departures(log, zone, match=None, after=0, before=10**9):
    hits = []
    prev = None
    for e in log:
        snap = e.get("snapshot")
        if not snap:
            prev = None
            continue
        if prev is not None and after < e["offset"] <= before:
            for p, q in zip(prev["players"], snap["players"]):
                b = q.get(zone) or {}
                a = p.get(zone) or {}
                for nm, cnt in a.items():
                    if cnt > b.get(nm, 0) and (match is None or match(nm)):
                        hits.append((e["offset"], q.get("seat"), nm))
        prev = snap
    return hits


def evaluate_micro(mid: str, runs: list, deck_names: set, commander: str) -> dict:
    """Evaluate one micro-rule across the N's runs (and cited card runs)."""
    ev: dict = {"runs": [r["run_id"] for r in runs]}
    verdict = "UNKNOWN"
    rationale = "mechanism not provoked in bounded window with current fixtures"

    def any_run(pred):
        for r in runs:
            out = pred(r)
            if out:
                return r["run_id"], out
        return None

    if mid == "MICRO_STACK":
        # Non-commander NON-LAND cast resolved to battlefield
        # (hand->stack->field; land plays never touch the stack).
        lands = {"plains", "island", "swamp", "mountain", "forest", "wastes"}
        found = any_run(lambda r: next(
            ((o, s, n) for (o, s, n) in arrivals(
                r["log"], "battlefield",
                lambda nm: nm != commander and nm in deck_names
                and nm.casefold() not in lands)[:1]), None))
        if found:
            verdict, rationale = "PASS", (
                f"non-commander cast resolved via stack in {found[0]}: {found[1]}")
            ev["arrival"] = found[1]
            ev["decisive_run"] = found[0]
    elif mid == "MICRO_ZONE_CHANGES":
        kinds = set()
        for r in runs:
            if arrivals(r["log"], "battlefield"): kinds.add("cast-arrival")
            if arrivals(r["log"], "graveyard"): kinds.add("graveyard")
            if departures(r["log"], "command"): kinds.add("command-exit")
            if arrivals(r["log"], "command"): kinds.add("command-entry")
            # draws: hand_count up + library down across consecutive snapshots
            prev = None
            for e in r["log"]:
                snap = e.get("snapshot")
                if not snap:
                    prev = None
                    continue
                if prev is not None:
                    for p, q in zip(prev["players"], snap["players"]):
                        if (q.get("hand_count") or 0) > (p.get("hand_count") or 0) \
                                and (q.get("library_count") or 0) < (p.get("library_count") or 0):
                            kinds.add("draw")
                prev = snap
        ev["movement_kinds"] = sorted(kinds)
        ev["decisive_run"] = runs[0]["run_id"]
        if len(kinds) >= 3:
            verdict, rationale = "PASS", f"distinct public zone movements: {sorted(kinds)}"
    elif mid == "MICRO_COMBAT":
        for r in runs:
            offs = [e["offset"] for e in r["log"] if e["decision_class"] == "declare_attacker"]
            drops = []
            for e in r["log"]:
                if e["decision_class"] == "priority" and e["life"] and any(
                        v is not None and v < 40 for v in e["life"]):
                    drops.append(e["offset"])
            if offs and drops:
                verdict, rationale = "PASS", (
                    f"attacker declarations {offs[:4]} + combat life drops {drops[:4]} in {r['run_id']}")
                ev.update({"attackers": offs[:6], "drops": drops[:6],
                           "decisive_run": r["run_id"]})
                break
    elif mid == "MICRO_STATE_BASED_ACTIONS":
        for r in runs:
            atk = [e["offset"] for e in r["log"]
                   if e["decision_class"] in ("declare_attacker", "declare_blocker")]
            deps = departures(r["log"], "battlefield")
            gys = arrivals(r["log"], "graveyard")
            linked = [d for d in deps if any(abs(d[0] - a) <= 20 for a in atk)
                      and any(g[0] >= d[0] and g[0] - d[0] <= 6 and g[2] == d[2] for g in gys)]
            if linked:
                verdict, rationale = "PASS", (
                    f"post-combat destroy chain (battlefield->graveyard via SBA) in {r['run_id']}: {linked[:4]}")
                ev["chains"] = linked[:8]
                ev["decisive_run"] = r["run_id"]
                break
    elif mid == "MICRO_TRIGGERS":
        for r in runs:
            tord = [e["offset"] for e in r["log"] if e["decision_class"] == "trigger_order"]
            tokens = arrivals(r["log"], "battlefield",
                              lambda nm: nm not in deck_names and nm != commander)
            post_etb_targets = []
            etbs = arrivals(r["log"], "battlefield")
            for (o, s, n) in etbs[:20]:
                tgts = [e["offset"] for e in r["log"]
                        if o < e["offset"] <= o + 10 and e["decision_class"] == "target"
                        and e["seat"] == (s + 1 if isinstance(s, int) else s)]
                if tgts:
                    post_etb_targets.append((o, n, tgts[:2]))
            if tord or tokens or post_etb_targets:
                verdict, rationale = "PASS", (
                    f"trigger evidence in {r['run_id']}: order={tord[:4]} tokens={tokens[:4]} "
                    f"etb-targets={post_etb_targets[:3]}")
                ev.update({"order": tord[:8], "tokens": tokens[:8],
                           "etb_targets": post_etb_targets[:6],
                           "decisive_run": r["run_id"]})
                break
    elif mid == "MICRO_REPLACEMENT":
        for r in runs:
            cus = [e["offset"] for e in r["log"] if e["decision_class"] == "choose_use"]
            for o in cus:
                cmds = arrivals(r["log"], "command", after=o, before=o + 6)
                if cmds:
                    verdict, rationale = "PASS", (
                        f"command-zone replacement choice + move in {r['run_id']}: use@{o} -> {cmds[:2]}")
                    ev.update({"uses": cus[:6], "moves": cmds[:4],
                               "decisive_run": r["run_id"]})
                    break
            if verdict == "PASS":
                break
    elif mid == "MICRO_RULES_RANDOMNESS":
        growth = [(r["run_id"], r.get("rules_random_calls_first"), r.get("rules_random_calls_last"))
                  for r in runs
                  if isinstance(r.get("rules_random_calls_first"), int)
                  and isinstance(r.get("rules_random_calls_last"), int)
                  and r["rules_random_calls_last"] > r["rules_random_calls_first"]]
        ev["growth"] = growth
        if growth:
            verdict, rationale = "PASS", f"Rules-Core RNG consumption growth: {growth}"
    elif mid == "MICRO_CONTINUOUS_EFFECTS":
        for r in runs:
            anths = arrivals(r["log"], "battlefield", lambda nm: nm in ANTHEMS)
            if not anths:
                # Sovereign path: static ETB-tapped effect.
                sovs = arrivals(r["log"], "battlefield",
                                lambda nm: nm == "Imposing Sovereign")
                tapped_etb = []
                for (o, seat, _nm) in sovs[:4]:
                    after = arrivals(r["log"], "battlefield", after=o, before=o + 60)
                    for (ao, a_seat, anm) in after:
                        if a_seat == seat or anm in ANTHEMS or anm == "Imposing Sovereign":
                            continue
                        lands = {"plains", "island", "swamp", "mountain", "forest", "wastes"}
                        if anm.casefold() in lands:
                            continue
                        # First sighting tapped => entered tapped (no haste in
                        # Lions; summoning sickness bars same-turn attacks).
                        for e in r["log"]:
                            if e["offset"] != ao:
                                continue
                            snap = e.get("snapshot") or {}
                            for p in snap["players"]:
                                if p.get("seat") == a_seat:
                                    for en in (p.get("battlefield_detail") or {}).get(anm, []):
                                        if en.get("tapped") is True:
                                            tapped_etb.append((ao, anm))
                            break
                if tapped_etb:
                    verdict, rationale = "PASS", (
                        f"Imposing Sovereign static ETB-tapped effect in {r['run_id']}: {tapped_etb[:4]}")
                    ev.update({"sovereign": sovs[0] if sovs else None,
                               "tapped_etb": tapped_etb[:8],
                               "decisive_run": r["run_id"]})
                    break
                continue
            # pt elevation of same-controller others after anthem arrival
            o, seat, nm = anths[0]
            elevated = []
            prev = None
            base: dict = {}
            for e in r["log"]:
                snap = e.get("snapshot")
                if not snap:
                    prev = None
                    continue
                if prev is not None and e["offset"] <= o:
                    for p in snap["players"]:
                        if p.get("seat") == seat:
                            for cname, entries in (p.get("battlefield_detail") or {}).items():
                                for en in entries:
                                    base.setdefault(cname, (en.get("power"), en.get("toughness")))
                if prev is not None and e["offset"] > o:
                    for p in snap["players"]:
                        if p.get("seat") == seat:
                            for cname, entries in (p.get("battlefield_detail") or {}).items():
                                for en in entries:
                                    b = base.get(cname)
                                    cur = (en.get("power"), en.get("toughness"))
                                    if b and cur != b and all(
                                            isinstance(v, int) for v in cur + b):
                                        elevated.append((e["offset"], cname, b, cur))
                prev = snap
            if elevated:
                verdict, rationale = "PASS", (
                    f"anthem {nm}@{o} then pt elevation in {r['run_id']}: {elevated[:4]}")
                ev.update({"anthem": anths[0], "elevations": elevated[:8],
                           "decisive_run": r["run_id"]})
                break
        if verdict != "PASS":
            rationale = "no anthem arrival + pt elevation in bounded window"
    elif mid == "MICRO_LAYERS":
        for r in runs:
            anths = arrivals(r["log"], "battlefield",
                             lambda nm: nm == "Elesh Norn, Grand Cenobite")
            if not anths:
                continue
            o = anths[0][0]
            deps = departures(r["log"], "battlefield", after=o, before=o + 15)
            atk = [e["offset"] for e in r["log"]
                   if e["decision_class"] in ("declare_attacker", "declare_blocker")
                   and o - 15 <= e["offset"] <= o + 15]
            noncombat = [d for d in deps if not any(abs(d[0] - a) <= 15 for a in atk)]
            if noncombat:
                verdict, rationale = "PASS", (
                    f"post-Elesh non-combat departures (layers-applied -2/-2) in {r['run_id']}: {noncombat[:4]}")
                ev["departures"] = noncombat[:8]
                ev["decisive_run"] = r["run_id"]
                break
        if verdict != "PASS":
            rationale = "no Elesh-driven non-combat departure in bounded window"
    return {"verdict": verdict, "rationale": rationale, "evidence": ev}


def card_run_citations():
    """Exact WS232 card runs observing MODES / TRIGGER_ORDER per N."""
    matrix = json.loads((NS / "ACTUAL_CARD_29_MATRIX.json").read_text())
    runs_dir = NS / "runs" / "card"
    cites: dict = {}
    for cell in matrix["cells"]:
        if cell["cell_verdict"] != "PASS" or not cell["run_pointer"]:
            continue
        rec = json.loads((runs_dir / (cell["run_pointer"] + ".json")).read_text())
        classes = (rec.get("run") or {}).get("observed_classes") or {}
        for cls in ("mode", "trigger_order"):
            if cls in classes:
                cites.setdefault(cls, {}).setdefault(cell["player_count"], []).append(
                    cell["run_pointer"])
    return cites


def store_run(run_id, n, seed, run):
    (RUNS / f"{run_id}.json").write_text(json.dumps(
        {"run_id": run_id, "player_count": n, "seed": seed,
         "engine_commit": run["engine_commit"],
         "decisions": run["decisions"], "terminal": run["terminal"],
         "failure": run["failure"],
         "observed_classes": run["observed_classes"],
         "rules_random_calls_first": run.get("rules_random_calls_first"),
         "rules_random_calls_last": run.get("rules_random_calls_last"),
         "final_outcomes": run["final_outcomes"],
         "run": run}, indent=1, sort_keys=True) + "\n")


def to_eval_entry(run_id, run):
    return {"run_id": run_id, **{k: run[k] for k in (
        "decisions", "terminal", "failure", "observed_classes",
        "final_outcomes")},
        "rules_random_calls_first": run.get("rules_random_calls_first"),
        "rules_random_calls_last": run.get("rules_random_calls_last"),
        "log": run["log"]}


ANTHEM_FOCUS = ("Captain of the Watch", "Elesh Norn, Grand Cenobite",
                "Imposing Sovereign")
ANTHEM_BUDGETS = {2: 400, 3: 600, 5: 900}
ANTHEM_SEEDS = [424242, 777001, 777002, 777003, 777004, 777005,
                777006, 777007, 777008, 777009]


def main() -> int:
    cmdr, main, deck_names = lions_deck()
    runs_by_n: dict[int, list] = {}
    # Base Lions runs: load stored full logs when present, else drive.
    for n in (2, 3, 5):
        for seed in SEEDS:
            run_id = f"MICRO_LIONS_{n}P_seed{seed}"
            stored = RUNS / f"{run_id}.json"
            if stored.exists():
                run = json.loads(stored.read_text())["run"]
                print(f"[lions {n}P seed={seed}] loaded stored ({run['decisions']} decisions)",
                      flush=True)
            else:
                decks = tuple(make_deck(f"ws232-micro-lions-{n}p-s{seed}-{s}", cmdr, main)
                              for s in range(1, n + 1))
                sc = make_scenario(f"ws232-micro-lions-{n}p", n, seed, decks)
                pilots = tuple(make_binding(s, d) for s, d in zip(range(1, n + 1), decks))
                run = drive_game(sc, decks, pilots, max_decisions=BUDGETS[n])
                store_run(run_id, n, seed, run)
                print(f"[lions {n}P seed={seed}] dec={run['decisions']} fail={str(run['failure'])[:80]} "
                      f"classes={sorted(run['observed_classes'])}", flush=True)
            runs_by_n.setdefault(n, []).append(to_eval_entry(run_id, run))
    # Anthem-spotlight Lions runs (continuous/layers provocation).
    for n in (2, 3, 5):
        for seed in ANTHEM_SEEDS:
            run_id = f"MICRO_LIONS_ANTHEM_{n}P_seed{seed}"
            stored = RUNS / f"{run_id}.json"
            if stored.exists():
                run = json.loads(stored.read_text())["run"]
                print(f"[anthem {n}P seed={seed}] loaded stored ({run['decisions']} decisions)",
                      flush=True)
            else:
                decks = tuple(make_deck(f"ws232-micro-anthem-{n}p-s{seed}-{s}", cmdr, main)
                              for s in range(1, n + 1))
                sc = make_scenario(f"ws232-micro-anthem-{n}p", n, seed, decks)
                pilots = tuple(make_binding(s, d) for s, d in zip(range(1, n + 1), decks))
                run = drive_game(sc, decks, pilots, focus_names=ANTHEM_FOCUS,
                                 max_decisions=ANTHEM_BUDGETS[n])
                store_run(run_id, n, seed, run)
                print(f"[anthem {n}P seed={seed}] dec={run['decisions']} fail={str(run['failure'])[:80]} "
                      f"classes={sorted(run['observed_classes'])}", flush=True)
            runs_by_n.setdefault(n, []).append(to_eval_entry(run_id, run))

    # Static-wave Lions runs (tapped-visibility snapshots for the
    # Imposing Sovereign path + further Elesh kill-windows).
    for n in (2, 3, 5):
        for seed in (424242, 777001, 777002):
            run_id = f"MICRO_LIONS_STATIC_{n}P_seed{seed}"
            stored = RUNS / f"{run_id}.json"
            if stored.exists():
                run = json.loads(stored.read_text())["run"]
                print(f"[static {n}P seed={seed}] loaded stored ({run['decisions']} decisions)",
                      flush=True)
            else:
                decks = tuple(make_deck(f"ws232-micro-static-{n}p-s{seed}-{s}", cmdr, main)
                              for s in range(1, n + 1))
                sc = make_scenario(f"ws232-micro-static-{n}p", n, seed, decks)
                pilots = tuple(make_binding(s, d) for s, d in zip(range(1, n + 1), decks))
                run = drive_game(sc, decks, pilots, focus_names=ANTHEM_FOCUS,
                                 max_decisions=ANTHEM_BUDGETS[n])
                store_run(run_id, n, seed, run)
                print(f"[static {n}P seed={seed}] dec={run['decisions']} fail={str(run['failure'])[:80]} "
                      f"classes={sorted(run['observed_classes'])}", flush=True)
            runs_by_n.setdefault(n, []).append(to_eval_entry(run_id, run))
    cites = card_run_citations()
    cells = []
    for mid in MICRO_IDS:
        for n in (2, 3, 5):
            if mid == "MICRO_MODES":
                ptrs = (cites.get("mode", {}).get(n) or [])
                if ptrs:
                    cells.append({"fixture_id": mid, "player_count": n,
                                  "cell_verdict": "PASS",
                                  "run_pointer": ptrs[0],
                                  "rationale": "engine-offered modal choice answered (Burn Down the House mode)",
                                  "attempts": []})
                else:
                    cells.append({"fixture_id": mid, "player_count": n,
                                  "cell_verdict": "UNKNOWN", "run_pointer": None,
                                  "rationale": "no mode decision in Lions or cited runs at this N",
                                  "attempts": []})
                continue
            if mid in ("MICRO_COPY", "MICRO_CONTROL", "MICRO_PREVENTION"):
                reason = {"MICRO_COPY": "no copy source in Lions or card fixtures; S9 decks not built",
                          "MICRO_CONTROL": "no control-change source in Lions or card fixtures",
                          "MICRO_PREVENTION": "no prevention source/target pair in symmetric Lions"}[mid]
                cells.append({"fixture_id": mid, "player_count": n,
                              "cell_verdict": "UNKNOWN", "run_pointer": None,
                              "rationale": reason, "attempts": []})
                continue
            verdict = evaluate_micro(mid, runs_by_n[n], deck_names, cmdr)
            # MICRO_TRIGGERS may cite card runs as supplement at Ns where
            # Lions shows no trigger evidence.
            if mid == "MICRO_TRIGGERS" and verdict["verdict"] != "PASS":
                ptrs = (cites.get("trigger_order", {}).get(n) or [])
                if ptrs:
                    verdict = {"verdict": "PASS",
                               "rationale": "trigger_order decisions in cited card run",
                               "evidence": {"runs": [r["run_id"] for r in runs_by_n[n]],
                                            "citation": ptrs[0]}}
            run_pointer = None
            if verdict["verdict"] == "PASS":
                if verdict["evidence"].get("citation"):
                    run_pointer = verdict["evidence"]["citation"]
                else:
                    run_pointer = verdict["evidence"].get("decisive_run")
                    if not run_pointer:
                        ev_runs = (verdict["evidence"].get("runs") or [])
                        run_pointer = ev_runs[0] if ev_runs else None
            cells.append({"fixture_id": mid, "player_count": n,
                          "cell_verdict": verdict["verdict"],
                          "run_pointer": run_pointer,
                          "rationale": verdict["rationale"],
                          "attempts": [{"note": "evaluated over runs",
                                        "runs": verdict["evidence"].get("runs")}]})
    out = NS / "MICRO_RULE_13_MATRIX.json"
    out.write_text(json.dumps(
        {"schema_version": "ws232-micro-rule-13-matrix-1.0.0",
         "cells": cells,
         "summary": {"PASS": sum(1 for c in cells if c["cell_verdict"] == "PASS"),
                     "UNKNOWN": sum(1 for c in cells if c["cell_verdict"] == "UNKNOWN")}},
        indent=1, sort_keys=True) + "\n")
    print("MICRO", {"PASS": sum(1 for c in cells if c["cell_verdict"] == "PASS"),
                    "UNKNOWN": sum(1 for c in cells if c["cell_verdict"] == "UNKNOWN")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
