#!/usr/bin/env python3
"""WS215 qualification driver: variable-player bounded lifecycles in fresh JVMs.

Mutation surface: qualification/ws215-xmage-variable-player-multicardinality/**
only (plus the committed production cardinality change under test). Drives the
production XmageFullGameSession for 2/3/4/5 players through bounded native
lifecycles (neutral + press), one fresh JVM per run, and adjudicates
fresh-process same-seed twin equality plus distinct-seed controls.

Budgets are bounded lifecycle proofs (150 neutral / 600 press), never full
games to terminal: each run must prove construction, registration, starting
player, mulligan flow, priority progression, authoritative decisions, and
turn advancement with no silently skipped callback.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WS215_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WS215_ROOT.parent.parent

PROBE_SRC = (
    WS215_ROOT / "driver-java/org/commanderlab/xmage/Ws215LifecycleProbe.java"
)
DRIVER_CLASSES = Path("/tmp/opencode/ws215-driver-classes")
CP_FILE = Path("/tmp/opencode/ws205-cp.txt")

NEUTRAL_BUDGET = 150
DEVELOP_BUDGET = 600
LIFECYCLE_SEED = 424242
DISTINCT_SEEDS = {2: 424243, 3: 777001, 4: 424243, 5: 999003}


def base_classpath() -> str:
    deps = CP_FILE.read_text().strip()
    return f"{DRIVER_CLASSES}:engine-bridge/target/classes:{deps}"


def compile_probe() -> None:
    DRIVER_CLASSES.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "javac",
            "-cp",
            base_classpath(),
            "-d",
            str(DRIVER_CLASSES),
            str(PROBE_SRC),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        raise SystemExit(f"probe compilation failed:\n{result.stdout}\n{result.stderr}")


def run_probe(
    players: int,
    seed: int,
    mode: str,
    budget: int,
    tag: str,
    deck: str = "rogshai",
    force_mulligan: bool = False,
) -> dict:
    suffix = f"{mode}-{deck}" + ("-mulligan" if force_mulligan else "")
    run_dir = WS215_ROOT / "runs" / f"{players}p-seed{seed}-{suffix}" / tag
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "summary.json"
    if out_path.exists():
        out_path.unlink()
    cmd = [
        "java",
        "-cp",
        base_classpath(),
        "org.commanderlab.xmage.Ws215LifecycleProbe",
        f"--players={players}",
        f"--seed={seed}",
        f"--budget={budget}",
        f"--mode={mode}",
        f"--deck={deck}",
        f"--force_mulligan={str(force_mulligan).lower()}",
        f"--repoRoot={REPO_ROOT}",
        f"--out={out_path}",
    ]
    print(f"[WS215] {players}P/{mode}/{deck}/{tag}: seed={seed} budget={budget}", flush=True)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=1500, cwd=str(REPO_ROOT)
    )
    (run_dir / "stdout.txt").write_text(result.stdout[-8000:])
    (run_dir / "stderr.txt").write_text(result.stderr[-4000:])
    record: dict = {
        "players": players,
        "seed": seed,
        "mode": mode,
        "tag": tag,
        "returncode": result.returncode,
    }
    if result.returncode != 0 or not out_path.exists():
        record["ok"] = False
        print(f"[WS215] {players}P/{mode}/{tag}: JVM FAILED rc={result.returncode}", flush=True)
        return record
    summary = json.loads(out_path.read_text())
    record["ok"] = True
    record["summary"] = summary
    print(
        f"[WS215] {players}P/{mode}/{tag}: decisions={summary['decisions']} "
        f"turn={summary['max_turn']} hash={summary['transcript_hash'][:12]} "
        f"failed={summary['failed']}",
        flush=True,
    )
    return record


def lifecycle_gates(record: dict) -> list[str]:
    """Return a list of gate failures (empty means PASS) for a neutral run."""
    problems: list[str] = []
    if not record.get("ok"):
        return ["probe JVM failed"]
    summary = record["summary"]
    players = record["players"]
    if summary["player_count"] != players:
        problems.append(f"player_count {summary['player_count']} != {players}")
    if summary["starting_player_seat"] != summary["expected_starting_seat"]:
        problems.append("starting seat is not seed mod N")
    if summary["mulligans_answered"] < players:
        problems.append("mulligan flow incomplete")
    if "priority" not in summary["decision_classes"]:
        problems.append("no priority progression")
    if len(summary["priority_actors"]) < 2:
        problems.append("priority did not rotate across the ring")
    if summary["max_turn"] < 2:
        problems.append("turns did not advance")
    if summary["decisions"] <= 0:
        problems.append("no authoritative decisions executed")
    if summary["hidden_violations"] != 0:
        problems.append("hidden-info structural violation")
    binding = summary["rules_seed_binding"]
    if not (
        binding["rules_seed_matches"]
        and binding["rules_seed_explicit"]
        and binding["seed_supported"]
    ):
        problems.append("seed binding proof failed")
    if binding["rules_random_calls"] <= 0:
        problems.append("no Rules RNG consumption")
    if summary["failed"]:
        problems.append(f"engine failure: {summary['failure_message']}")
    if summary["outcome_count"] != players:
        problems.append("seat/principal map inexact")
    return problems


def run_observations(counts: list[int]) -> None:
    """Single-run observation matrix (no twins): oracle scans, command-zone
    snapshots, hand traces, commander casts, zone choices, stack depths."""
    compile_probe()
    observations: dict = {"runs": []}
    for players in counts:
        neutral = run_probe(players, LIFECYCLE_SEED, "neutral", NEUTRAL_BUDGET, "observe", "rogshai")
        develop = run_probe(
            players, LIFECYCLE_SEED, "develop", DEVELOP_BUDGET, "observe", "lions"
        )
        observations["runs"].extend([neutral, develop])
    for players in (2, 4):
        mulligan = run_probe(
            players,
            LIFECYCLE_SEED,
            "develop",
            DEVELOP_BUDGET,
            "observe",
            "lions",
            True,
        )
        observations["runs"].append(mulligan)
    out_path = WS215_ROOT / "runs" / "WS215_OBSERVATIONS.json"
    out_path.write_text(json.dumps(observations, indent=1, sort_keys=True))
    print(f"[WS215] observations written to {out_path}", flush=True)


def main() -> None:
    only = [arg for arg in sys.argv[1:] if arg != "observe"]
    if "observe" in sys.argv[1:]:
        run_observations([int(arg) for arg in only] or [2, 3, 4, 5])
        return
    compile_probe()
    results: dict = {"runs": [], "twins": {}, "controls": {}}
    for players in (2, 3, 4, 5):
        if only and str(players) not in only:
            continue
        primary = run_probe(players, LIFECYCLE_SEED, "neutral", NEUTRAL_BUDGET, "primary")
        twin = run_probe(players, LIFECYCLE_SEED, "neutral", NEUTRAL_BUDGET, "twin")
        develop_primary = run_probe(
            players, LIFECYCLE_SEED, "develop", DEVELOP_BUDGET, "develop-primary", "lions"
        )
        develop_twin = run_probe(
            players, LIFECYCLE_SEED, "develop", DEVELOP_BUDGET, "develop-twin", "lions"
        )
        control = run_probe(
            players, DISTINCT_SEEDS[players], "neutral", NEUTRAL_BUDGET, "distinct-seed"
        )
        develop_control = run_probe(
            players,
            DISTINCT_SEEDS[players],
            "develop",
            DEVELOP_BUDGET,
            "develop-distinct-seed",
            "lions",
        )
        results["runs"].extend(
            [primary, twin, develop_primary, develop_twin, control, develop_control]
        )
        twin_match = (
            primary.get("ok")
            and twin.get("ok")
            and primary["summary"]["transcript_hash"] == twin["summary"]["transcript_hash"]
        )
        develop_twin_match = (
            develop_primary.get("ok")
            and develop_twin.get("ok")
            and develop_primary["summary"]["transcript_hash"]
            == develop_twin["summary"]["transcript_hash"]
        )
        seed_influence = (
            develop_primary.get("ok")
            and develop_control.get("ok")
            and develop_primary["summary"]["transcript_hash"]
            != develop_control["summary"]["transcript_hash"]
        )
        results["twins"][str(players)] = {
            "neutral_twin_match": twin_match,
            "develop_twin_match": develop_twin_match,
            "neutral_gates_primary": lifecycle_gates(primary),
            "neutral_gates_twin": lifecycle_gates(twin),
            "develop_gates_primary": lifecycle_gates(develop_primary),
            "develop_gates_twin": lifecycle_gates(develop_twin),
        }
        results["controls"][str(players)] = {"distinct_seed_diverges": seed_influence}
        print(
            f"[WS215] {players}P: neutral_twin={twin_match} develop_twin={develop_twin_match} "
            f"seed_influence={seed_influence}",
            flush=True,
        )
    out_path = WS215_ROOT / "runs" / "WS215_MATRIX.json"
    out_path.write_text(json.dumps(results, indent=1, sort_keys=True))
    print(f"[WS215] matrix written to {out_path}", flush=True)


if __name__ == "__main__":
    main()
