#!/usr/bin/env python3
"""Throwaway continuation (M1): the p1g1 sweep process was killed by a runtime
restart after pod-027. This driver plays the remaining pods with the sweep's
own machinery (plan_pods, bench._setup, bench._play, same seeds, workers=1
sequential) and merges the rows into the sweep report, recomputing the summary
with the sweep module's own summarize(). The partial report is backed up first.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/github/wt-m1-sweep/src")
sys.path.insert(0, "/home/hatch/workspace/github/wt-m1-sweep/scripts")

import benchmark_xmage_full_games as bench  # noqa: E402
import precon_pod_sweep as sweep  # noqa: E402

ROOT = Path("/home/hatch/workspace/github/wt-m1-sweep")
JAR = Path("/home/hatch/workspace/tmp/m1/bridge.jar")
OUT = Path("/home/hatch/workspace/tmp/m1/sweep_p1g1.json")
FROM_INDEX = 28


def main() -> int:
    partial = json.loads(OUT.read_text(encoding="utf-8"))
    done = {r["pod"]: r for r in partial["rows"]}
    print(f"partial rows: {len(done)} (jar={partial['jar']})", flush=True)
    shutil.copy(OUT, OUT.with_name("sweep_p1g1_partial28.json"))

    names = sweep.importable_decks(Path("/home/hatch/workspace/tmp/m1/imports.json"))
    pods = sweep.plan_pods(names, sweep.POD_SIZE, 1)
    assert len(pods) == 46, len(pods)
    for index in range(FROM_INDEX):
        label = f"pod-{index:03d}"
        assert done[label]["decks"] == list(pods[index]), f"plan drift at {label}"
    print("plan consistency for pods 000-027 verified against partial rows", flush=True)
    command = bench.bridge_command(JAR, [])
    deck_dir = ROOT / "data/decks/precons"
    rows = list(partial["rows"])
    for index in range(FROM_INDEX, len(pods)):
        label = f"pod-{index:03d}"
        assert label not in done, label
        setup = bench._setup(tuple((deck_dir / f"{n}.json").relative_to(ROOT) for n in pods[index]))
        row = bench._play(command, label, setup, 1, True)
        row["decks"] = list(pods[index])
        rows.append(row)
        report = {"jar": partial["jar"], "game_seed": 1, "plan_seed": 1}
        report |= sweep.summarize(rows) | {"rows": sorted(rows, key=lambda r: r["pod"])}
        OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(f"{label} merged -> pods={report['pods']} ok={report['pods_ok']} failed={report['pods_failed']}", flush=True)
    print("CONTINUATION-DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
