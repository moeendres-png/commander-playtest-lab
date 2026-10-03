#!/usr/bin/env python3
"""B7 (#488): kill every real-tape replay mutation through the live consumer.

1. Record one fresh semantic replay tape on the pinned engine, in a fresh
   process (``semantic_replay.recorder.record_tape``), with the same 4P setup the
   full-game conformance gate uses. A committed tape is not used: it is bound to
   the engine commit it was recorded on and would diverge at the source lock.
2. Replay the unmutated tape with ``semantic_replay.consumer.replay_tape`` in a
   fresh process; it must pass.
3. Replay each mutated tape the same way; the consumer must raise exactly the
   mutation's expected divergence class (``LIVE_CONSUMER_DETECTORS``).

Exit 0 only when the baseline passes and every mutation is killed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from commander_lab.engine.rules.full_game import XMAGE_FULL_GAME_COMMAND_ENV, XmageFullGameRunner
from commander_lab.meta_qualification import run_live_consumer_mutations
from commander_lab.semantic_replay import consumer, recorder

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("artifacts/meta-verification/LIVE_CONSUMER_MUTATIONS.json")
DEFAULT_WORKDIR = Path("artifacts/meta-verification/live-consumer-tapes")


def _conformance_setup(player_count: int):  # type: ignore[no-untyped-def]
    path = ROOT / "scripts" / "run_external_full_game_conformance.py"
    spec = importlib.util.spec_from_file_location("full_game_conformance_setup", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_setup(player_count)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    parser.add_argument("--player-count", type=int, default=4)
    args = parser.parse_args()

    runner = XmageFullGameRunner(request_timeout_seconds=120.0)
    command = runner.command
    if command is None:
        print(f"{XMAGE_FULL_GAME_COMMAND_ENV} is required", file=sys.stderr)
        return 2
    output = args.output if args.output.is_absolute() else ROOT / args.output
    workdir = args.workdir if args.workdir.is_absolute() else ROOT / args.workdir
    workdir.mkdir(parents=True, exist_ok=True)

    scenario, decks, pilots = _conformance_setup(args.player_count)
    fresh = workdir / "fresh.tape.json"
    recorder.record_tape(
        scenario=scenario,
        decks=decks,
        pilots=pilots,
        command=command,
        output_path=fresh,
        cwd=runner.cwd,
    )
    tape = json.loads(fresh.read_text(encoding="utf-8"))
    report = run_live_consumer_mutations(
        tape,
        replay=lambda path: consumer.replay_tape(path, command=command, cwd=runner.cwd),
        workdir=workdir,
        source_tape=str(fresh.relative_to(ROOT)) if fresh.is_relative_to(ROOT) else str(fresh),
    )
    report["fresh_tape_id"] = tape["tape_id"]
    report["fresh_tape_steps"] = len(tape["steps"])
    report["engine_commit"] = tape["source_lock"].get("engine_commit")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("attempted", "killed", "survived", "not_run")}))
    for row in report["results"]:
        print(f"{row['mutation_id']}: {row['status']} ({row['observed_divergence']})")
    return 0 if report["complete"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
