"""RESEARCH ONLY (#1672): isolated 7/8-seat feasibility harness. Never merge, never a gate.

Owner instruction 2026-11-22 (#1672/#1656) under the research clause of
``docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md``: own harness, no admission endpoint, no
Studio surface, results are ``SIMULATED_RESULT`` and never 4P/6P evidence.

Plays ONE recorded game per call (one bridge JVM, ``gamesPerJvm`` not set) with the Studio's
own game setup (``play.prepare_game``) and recorder, but with its own deck loader so the
Studio's 2..6 seat bound (``play.load_decks``) stays untouched. Needs the research branch
(engine-layer bounds raised to 8) and the research bridge JAR via
``COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD``.

Measures wall time, CPU time of this process and its children (the JVM), and the peak RSS of
the bridge JVM (``VmHWM`` polled from ``/proc``), then analyses the written log.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import resource
import sys
import threading
import time
from pathlib import Path

from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.studio.launch import engine_command
from commander_lab.studio.play import _with_hash, close_recorded_game, prepare_game
from commander_lab.studio.play_batch import BatchRecordingRunner

MAX_RESEARCH_SEATS = 8


def _descendants(root: int) -> set[int]:
    children: dict[int, list[int]] = collections.defaultdict(list)
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
            children[int(fields[1])].append(int(entry))
        except (OSError, IndexError, ValueError):
            continue
    found: set[int] = set()
    todo = [root]
    while todo:
        pid = todo.pop()
        for child in children.get(pid, []):
            if child not in found:
                found.add(child)
                todo.append(child)
    return found


class JvmPeakSampler(threading.Thread):
    """Polls VmHWM (peak RSS) of every java descendant; keeps the largest value seen."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.peak_kib = 0
        self.java_pids: set[int] = set()
        self._halt = threading.Event()

    def run(self) -> None:
        me = os.getpid()
        while not self._halt.is_set():
            for pid in _descendants(me):
                try:
                    status = Path(f"/proc/{pid}/status").read_text()
                except OSError:
                    continue
                if "\nName:\tjava" not in "\n" + status:
                    continue
                self.java_pids.add(pid)
                for line in status.splitlines():
                    if line.startswith("VmHWM:"):
                        self.peak_kib = max(self.peak_kib, int(line.split()[1]))
            self._halt.wait(0.5)

    def stop(self) -> None:
        self._halt.set()


def load_research_decks(paths: list[Path]) -> tuple:
    if not 2 <= len(paths) <= MAX_RESEARCH_SEATS:
        raise SystemExit(f"research harness: 2..{MAX_RESEARCH_SEATS} decks, got {len(paths)}")
    decks = tuple(_with_hash(load_rules_deck_snapshot(path)) for path in paths)
    if len({deck.deck_id for deck in decks}) != len(decks):
        raise SystemExit("every seat needs its own deck (distinct deck ids)")
    return decks


def analyse(log_path: Path, seats: int) -> dict[str, object]:
    with gzip.open(log_path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    frames = [row for row in rows if row.get("kind") == "frame"]
    result = next((row for row in rows if row.get("kind") == "result"), {})
    classes = collections.Counter(str(f.get("decision_class")) for f in frames)
    deciding = sorted({f.get("seat") for f in frames if isinstance(f.get("seat"), int)})
    in_players = sorted(
        {p.get("seat") for f in frames[:1] for p in f.get("players", []) if "seat" in p}
    )
    lost_order: list[int] = []
    for frame in frames:
        for player in frame.get("players", []):
            if player.get("lost") and player.get("seat") not in lost_order:
                lost_order.append(player["seat"])
    attack = []
    for frame in frames:
        if frame.get("decision_class") != "declare_attacker":
            continue
        alive = [p["seat"] for p in frame.get("players", []) if not p.get("lost") and "seat" in p]
        opponents_alive = len([s for s in alive if s != frame.get("seat")])
        attack.append((frame.get("options"), opponents_alive, frame.get("prompt")))
    events = result.get("event_log") or []
    event_types = collections.Counter(str(e.get("type")) for e in events)
    header = rows[0] if rows and rows[0].get("kind") == "header" else {}
    commanders = {
        name: seat.get("seat")
        for seat in header.get("seats", [])
        for name in seat.get("commanders", [])
    }
    cmd_damage: collections.Counter[tuple[str, str]] = collections.Counter()
    for event in events:
        if (
            event.get("type") == "DAMAGED_PLAYER"
            and event.get("combat")
            and event.get("source_name") in commanders
        ):
            cmd_damage[(event["source_name"], str(event.get("target_player")))] += int(
                event.get("amount") or 0
            )
    losses = [
        (e.get("turn"), e.get("player_player"), e.get("step"))
        for e in events
        if e.get("type") == "LOST"
    ]
    short_attack = sum(1 for options, opp, _ in attack if (options or 0) < opp + 1)
    attacked = sorted(
        {
            a.get("target")
            for f in frames
            if f.get("decision_class") == "declare_attacker"
            for a in (f.get("combat") or {}).get("attacks", [])
        }
        - {None}
    )
    last_players = frames[-1].get("players", []) if frames else []
    return {
        "status": result.get("status"),
        "winner_seats": result.get("winner_seats"),
        "decision_count": result.get("decision_count"),
        "forced_decisions_skipped": result.get("forced_decisions_skipped"),
        "frames": len(frames),
        "last_turn": frames[-1].get("turn") if frames else None,
        "trigger_order": classes.get("trigger_order", 0),
        "declare_attacker": classes.get("declare_attacker", 0),
        "decision_classes": dict(sorted(classes.items())),
        "deciding_seats": deciding,
        "seat_gap": sorted(set(range(seats)) - set(deciding)),
        "players_seats_first_frame": in_players,
        "lost_order": lost_order,
        "final_life": {p.get("seat"): p.get("life") for p in last_players},
        "attack_frames_sample": attack[:3],
        "attack_frames_fewer_options_than_living_opponents_plus_one": short_attack,
        "attack_targets_seen": attacked,
        "commander_combat_damage_max": max(cmd_damage.values(), default=0),
        "commander_combat_damage_pairs_ge21": sorted(
            f"{s}->{t}:{v}" for (s, t), v in cmd_damage.items() if v >= 21
        ),
        "loss_events": losses,
        "event_types": dict(sorted(event_types.items())),
        "failure_class": result.get("failure_class"),
        "failure_message": result.get("failure_message"),
        "bridge_jar_sha256": result.get("bridge_jar_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-decisions", type=int, default=50_000)
    parser.add_argument("--deck", action="append", required=True, type=Path)
    args = parser.parse_args()

    decks = load_research_decks(args.deck)
    command = engine_command(args.data)
    if command is None:
        raise SystemExit("no engine command (set COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD)")
    prepared = prepare_game(
        decks, seed=args.seed, game_id=args.game_id, data_folder=args.data, command=command
    )
    runner = BatchRecordingRunner(
        args.data,
        {prepared.scenario.scenario_id: (prepared.game_id, prepared.header)},
        command=command,
        max_decisions=args.max_decisions,
    )
    load_start = Path("/proc/loadavg").read_text().split()[0]
    sampler = JvmPeakSampler()
    sampler.start()
    started = time.monotonic()
    raw_error = None
    try:
        outcomes = runner.run_batch([(prepared.scenario, prepared.decks, prepared.pilots)])
    except Exception as error:  # harness: record, never hide
        outcomes = [error]
    wall = time.monotonic() - started
    sampler.stop()
    sampler.join(2)
    outcome = outcomes[0]
    if isinstance(outcome, Exception):
        raw_error = f"{type(outcome).__name__}: {outcome}"[:2000]
    summary = close_recorded_game(runner.recorder_of(prepared.scenario.scenario_id), outcome)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    own = resource.getrusage(resource.RUSAGE_SELF)
    log_path = args.data / "games" / f"{args.game_id}.jsonl.gz"
    record: dict[str, object] = {
        "data_class": "SIMULATED_RESULT",
        "research_only": "#1672 isolated 7/8-seat harness; never 4P/6P evidence",
        "game_id": args.game_id,
        "seed": args.seed,
        "seats": len(decks),
        "decks": [deck.deck_id for deck in decks],
        "wall_s": round(wall, 2),
        "cpu_jvm_s": round(children.ru_utime + children.ru_stime, 2),
        "cpu_python_s": round(own.ru_utime + own.ru_stime, 2),
        "jvm_peak_rss_mib": round(sampler.peak_kib / 1024, 1),
        "jvm_pids": len(sampler.java_pids),
        "loadavg_start": load_start,
        "loadavg_end": Path("/proc/loadavg").read_text().split()[0],
        "summary_status": summary.get("status"),
        "raw_error": raw_error,
    }
    if log_path.is_file():
        record.update(analyse(log_path, len(decks)))
    args.out.write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: record.get(k)
                for k in (
                    "game_id",
                    "status",
                    "wall_s",
                    "cpu_jvm_s",
                    "jvm_peak_rss_mib",
                    "decision_count",
                    "trigger_order",
                    "seat_gap",
                    "lost_order",
                    "winner_seats",
                    "raw_error",
                )
            }
        ),
        flush=True,
    )
    return 0 if record.get("status") == "finished" else 1


if __name__ == "__main__":
    sys.exit(main())
