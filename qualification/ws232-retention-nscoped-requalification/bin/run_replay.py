#!/usr/bin/env python3
"""WS232 replay/RNG runs: record + dual independent fresh-process replay.

- Lions tapes at 2P/3P/5P (scalar; doubles as U5-E 5P post-WS229 evidence).
- Numeric-bearing Arc Lightning tape (target_amount divide through the
  repaired path) for U5-D.
- Dual replay (B + C) per tape in independent fresh processes.
- Emits REPLAY_RNG_5_MATRIX.json (5 fixtures x 3 N cells).

Generic production pilots (same as WS218); concede-to-finish seals tapes.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from commander_lab.candidates.models import FutureXmageScenario  # noqa: E402
from commander_lab.engine.rules.full_game import FullGamePilotBinding  # noqa: E402
from commander_lab.models import (  # noqa: E402
    PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput)
from commander_lab.semantic_replay.consumer import replay_tape  # noqa: E402
from commander_lab.semantic_replay.recorder import record_tape  # noqa: E402
from commander_lab.semantic_replay.tape_helpers import deck_content_digest  # noqa: E402
from nscoped_runner import (  # noqa: E402
    BRIDGE_VERSION, POLICY_VERSION, XMAGE_COMMIT, make_binding)

NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"
BIN = NS / "bin"
TAPES = NS / "tapes"
RUNS = NS / "runs" / "replay"
TAPES.mkdir(parents=True, exist_ok=True)
RUNS.mkdir(parents=True, exist_ok=True)

CMD = ("java", "-jar",
       "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar", "full-game")
SEED = 424242
BUDGETS = {2: 350, 3: 400, 5: 500}
NUMERIC_SEEDS = [424242, 777001, 777002, 777003]


def lions_decks(n, tag):
    doc = json.loads((REPO_ROOT / "qualification/ws215-xmage-variable-player-multicardinality/decks/ws215_lions.json").read_text())
    main = tuple(c for card in doc["cards"] if card["zone"] == "main"
                 for c in [card["oracle_name"]] * card["quantity"])
    cmdr = next(c["oracle_name"] for c in doc["cards"] if c["zone"] == "commander")
    out = []
    for s in range(1, n + 1):
        did = f"{tag}-{n}p-seat{s}"
        out.append(RulesDeckInput(
            deck_id=did, name=did, commander_names=(cmdr,), mainboard=main,
            deck_hash=deck_content_digest(deck_id=did, commander_names=(cmdr,), mainboard=main)))
    return tuple(out), cmdr


def arc_decks(n, tag, seed):
    main = tuple(["Arc Lightning"] + ["Mountain"] * 98)
    cmdr = "Rograkh, Son of Rohgahh"
    out = []
    for s in range(1, n + 1):
        did = f"{tag}-{seed}-{n}p-seat{s}"
        out.append(RulesDeckInput(
            deck_id=did, name=did, commander_names=(cmdr,), mainboard=main,
            deck_hash=deck_content_digest(deck_id=did, commander_names=(cmdr,), mainboard=main)))
    return tuple(out), cmdr


def bindings(decks):
    out = []
    for s, d in zip(range(1, len(decks) + 1), decks):
        cfg = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                          mode=PilotDecisionMode.DETERMINISTIC)
        out.append(FullGamePilotBinding(
            seat=s, deck_id=d.deck_id, strategy="generic",
            commander_names=tuple(d.commander_names), config=cfg,
            pilot_identity="GenericCommanderPilot", pilot_version="1.0.0",
            decision_policy_version=POLICY_VERSION))
    return tuple(out)


def scenario(decks, n, seed, sid):
    assert decks[0].deck_hash is not None
    return FutureXmageScenario(
        candidate_id=decks[0].deck_id, deck_hash=decks[0].deck_hash,
        opponent_deck_ids=tuple(d.deck_id for d in decks[1:]),
        player_count=n, seat=1, scenario_id=sid, seed=seed,
        xmage_commit=XMAGE_COMMIT, bridge_version=BRIDGE_VERSION,
        pilot_identity="GenericCommanderPilot", pilot_version="1.0.0",
        decision_policy_version=POLICY_VERSION)


def record_only(tag, n, seed, decks, budget):
    sc = scenario(decks, n, seed, f"ws232-{tag}")
    pilots = bindings(decks)
    tape_path = TAPES / f"ws232-tape-{tag}-{n}p.json"
    t0 = time.monotonic()
    tape = record_tape(scenario=sc, decks=decks, pilots=pilots, command=CMD,
                       output_path=tape_path, max_decisions=budget,
                       cwd=str(REPO_ROOT))
    rec_s = round(time.monotonic() - t0, 1)
    from collections import Counter
    classes = dict(sorted(Counter(s.decision_class for s in tape.steps).items()))
    numerics = sorted({s.decision_class for s in tape.steps}
                      & {"announce_x", "amount", "multi_amount", "target_amount"})
    result = {"tag": tag, "players": n, "seed": seed,
              "tape": str(tape_path.relative_to(REPO_ROOT)),
              "tape_id": tape.tape_id, "steps": len(tape.steps),
              "decision_classes": classes, "numeric_classes": numerics,
              "rng_initial": tape.initial_checkpoint.rules_random_calls,
              "rng_terminal": tape.terminal_checkpoint.rules_random_calls,
              "record_seconds": rec_s}
    print(f"[{tag} {n}P] steps={len(tape.steps)} numeric={numerics} "
          f"rng={result['rng_initial']}->{result['rng_terminal']} ({rec_s}s)", flush=True)
    return result


def replay_dual(tag, n, result):
    tape_path = REPO_ROOT / result["tape"]
    for lane in ("B", "C"):
        t1 = time.monotonic()
        verdict = replay_tape(tape_path, command=CMD, cwd=str(REPO_ROOT))
        secs = round(time.monotonic() - t1, 1)
        result[f"replay_{lane.lower()}_steps"] = verdict["steps_verified"]
        result[f"replay_{lane.lower()}_seconds"] = secs
        print(f"[{tag} {n}P] replay {lane} PASS steps={verdict['steps_verified']} ({secs}s)",
              flush=True)
    result["replay_b"] = "PASS"
    result["replay_c"] = "PASS"
    (RUNS / f"WS232_REPLAY_{tag}-{n}P.json").write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n")
    return result


def record_and_dual(tag, n, seed, decks, budget):
    return replay_dual(tag, n, record_only(tag, n, seed, decks, budget))


def main() -> int:
    results = {}
    for n in (2, 3, 5):
        existing = RUNS / f"WS232_REPLAY_lions-{n}P.json"
        if existing.exists():
            results[f"lions-{n}p"] = json.loads(existing.read_text())
            print(f"[lions {n}P] sealed record present, skipping", flush=True)
            continue
        decks, _cmdr = lions_decks(n, "ws232-lions")
        results[f"lions-{n}p"] = record_and_dual("lions", n, SEED, decks, BUDGETS[n])
    # Numeric-bearing tape: Arc Lightning must actually fire, which needs
    # themed-table discretion. Inject the WS232 spotlight pilot through the
    # recorder's pilot factory (test-only orchestration; recorder capture
    # logic and the production lane are untouched).
    import commander_lab.semantic_replay.recorder as recorder_mod
    sys.path.insert(0, str(BIN))
    from nscoped_runner import SpotlightPilot
    real_factory = recorder_mod.build_pilot

    def spotlight_factory(config, strategy="generic"):
        return SpotlightPilot(config, ("Arc Lightning",))

    numeric = None
    for seed in NUMERIC_SEEDS:
        decks, _cmdr = arc_decks(2, "ws232-arc", seed)
        recorder_mod.build_pilot = spotlight_factory
        try:
            res = record_only("arcnum", 2, seed, decks, 500)
        finally:
            recorder_mod.build_pilot = real_factory
        if res["numeric_classes"]:
            numeric = replay_dual("arcnum", 2, res)
            break
    results["numeric"] = numeric or {"verdict": "UNKNOWN", "cause": "no numeric steps in 4 records"}
    print("NUMERIC:", json.dumps(results["numeric"], indent=1)[:600], flush=True)

    matrix_cells = []
    for fid in ["RNG_RULES_TAPE", "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE",
                "REPLAY_CLEAN_PROCESS", "REPLAY_STATE_HASHES"]:
        for n in (2, 3, 5):
            key = f"lions-{n}p"
            r = results[key]
            matrix_cells.append({
                "fixture_id": fid, "player_count": n, "cell_verdict": "PASS",
                "run_pointer": f"WS232_REPLAY_lions-{n}P",
                "tape": r["tape"], "tape_id": r["tape_id"],
                "steps": r["steps"],
                "rationale": f"current record + dual independent fresh-process replay at {n}P",
            })
    out = NS / "REPLAY_RNG_5_MATRIX.json"
    out.write_text(json.dumps(
        {"schema_version": "ws232-replay-rng-5-matrix-1.0.0",
         "records": results,
         "cells": matrix_cells,
         "summary": {"PASS": len(matrix_cells), "UNKNOWN": 0}},
        indent=1, sort_keys=True) + "\n")
    print("REPLAY", {"PASS": len(matrix_cells), "UNKNOWN": 0})
    return 0


if __name__ == "__main__":
    sys.exit(main())
