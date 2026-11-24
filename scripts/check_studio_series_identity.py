"""Check that a game played inside a Studio series is THE SAME GAME as played alone.

Plays the same seeds of one deck (``--mode batch``) or a base/variant pair (``--mode paired``)
against the ``precon`` pod of ``deckbau_eval.py`` twice on the real rules engine:

  (a) one game per bridge JVM, default JVM options, one ``commander_lab.studio play`` process
      per game (how a Studio series played before), and
  (b) as a Studio series (``BatchSimulation`` in ``batch`` mode, or
      ``paired_comparison.parallel_window_player`` in ``paired`` mode) with ``--workers`` workers,
      ``--games-per-jvm`` games per JVM and the fast JVM options (serial GC, AppCDS archive if the
      jar has one).

Then it compares, per game, the semantic transcript SHA-256 (the field
``benchmark_xmage_full_games.py`` records as ``semantic``: ``semantic_transcript_sha256`` of the
full-game result), the winner seats and the decision count, as every game log of the Studio
records them. Exit 0 only if every game is identical and every game of both runs finished.

    python scripts/check_studio_series_identity.py --jar bridge.jar --work /tmp/x/fast-check
    python scripts/check_studio_series_identity.py --mode paired --variant-deck variant.json --jar bridge.jar --work /tmp/x/paired-check

Wall and CPU times are printed as a measurement only; the verdict rests on identity alone.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:
    resource = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import deckbau_eval  # noqa: E402

from commander_lab.engine.rules.project import load_rules_deck_snapshot  # noqa: E402
from commander_lab.studio import paired_comparison  # noqa: E402
from commander_lab.studio.games import read_game  # noqa: E402
from commander_lab.studio.launch import (  # noqa: E402
    ENGINE_COMMAND_ENV,
    command_text,
    series_engine,
)
from commander_lab.studio.simulations import BatchSimulation  # noqa: E402

DEFAULT_DECK = ROOT / "data/decks/deckbau/chulane_current.json"
DEFAULT_JAR = ROOT / "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
BASE_COMMAND = ("java", "-Xmx3g", "-jar", "{jar}", "full-game")


def _cpu_seconds() -> float | None:
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return float(usage.ru_utime + usage.ru_stime)


def _cpu_delta(start: float | None, end: float | None) -> float | None:
    if start is None or end is None:
        return None
    return round(end - start, 1)


def _format_cpu(delta: float | None) -> str:
    return f"{delta:.1f} s" if delta is not None else "nicht verfügbar"


def _fingerprint(data: Path, game_id: str) -> dict[str, Any]:
    """Hash, winners, decisions and status of a recorded game, as its log closes it."""
    result = read_game(data, game_id, start=0, count=0).get("result")
    result = result if isinstance(result, dict) else {}
    return {
        "game_id": game_id,
        "status": result.get("status", "missing"),
        "semantic": result.get("semantic_transcript_sha256"),
        "winners": result.get("winner_seats"),
        "decisions": result.get("decision_count"),
        "failure": result.get("failure_message"),
    }


def play_alone(
    data: Path, deck: Path, opponents: list[Path], seeds: list[int], env: dict[str, str]
) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for seed in seeds:
        game_id = f"identity-a-s{seed}"
        command = [
            sys.executable,
            "-m",
            "commander_lab.studio",
            "--data",
            str(data),
            "play",
            "--seed",
            str(seed),
            "--game-id",
            game_id,
            "--deck",
            str(deck),
        ]
        for opponent in opponents:
            command += ["--deck", str(opponent)]
        subprocess.run(command, env=env, check=False, stdout=subprocess.DEVNULL)
        rows[seed] = _fingerprint(data, game_id)
    return rows


def play_series(
    data: Path,
    deck: Path,
    opponents: list[Path],
    seeds: list[int],
    workers: int,
    games_per_jvm: int,
) -> tuple[dict[int, dict[str, Any]], BatchSimulation]:
    engine = series_engine(data, games_per_jvm)
    if engine is None:
        raise SystemExit("no engine command: set " + ENGINE_COMMAND_ENV)
    batch = BatchSimulation(
        "identity-b",
        data,
        deck_id="chulane",
        revision_id="check",
        pod_name="precon",
        opponent_paths=opponents,
        seeds=seeds,
        workers=workers,
        games_per_jvm=games_per_jvm,
        engine=engine,
    )
    batch.run_worker(None, deck)
    return {seed: _fingerprint(data, batch.game_id_of(seed)) for seed in seeds}, batch


def play_paired_series(
    data: Path,
    base_deck_path: Path,
    variant_deck_path: Path,
    opponents: list[Path],
    seeds: list[int],
    workers: int,
    games_per_jvm: int,
) -> tuple[dict[tuple[str, int], dict[str, object]], dict[str, object]]:
    engine = series_engine(data, games_per_jvm)
    if engine is None:
        raise SystemExit("no engine command: set " + ENGINE_COMMAND_ENV)
    base_deck = load_rules_deck_snapshot(base_deck_path)
    variant_deck = load_rules_deck_snapshot(variant_deck_path)
    if variant_deck.deck_id == base_deck.deck_id:
        variant_deck = variant_deck.model_copy(
            update={"deck_id": f"{variant_deck.deck_id}__variant"}
        )
    opponent_decks = [load_rules_deck_snapshot(path) for path in opponents]
    paths_by_deck_id: dict[str, Path] = {
        base_deck.deck_id: base_deck_path,
        variant_deck.deck_id: variant_deck_path,
    }
    for deck_obj, deck_path in zip(opponent_decks, opponents, strict=True):
        paths_by_deck_id[deck_obj.deck_id] = deck_path

    series_id = "identity-paired"
    rows: dict[tuple[str, int], dict[str, object]] = {}
    pool_summary: dict[str, object] | None = None
    if seeds:
        player = paired_comparison.parallel_window_player(
            data,
            series_id=series_id,
            base_deck=base_deck,
            variant_deck=variant_deck,
            opponents=opponent_decks,
            paths_by_deck_id=paths_by_deck_id,
            seeds=seeds,
            tested_seats=[0],
            budget_pairs=len(seeds),
            look_every_pairs=len(seeds),
            workers=workers,
            games_per_jvm=engine.games_per_jvm,
            command=engine.command,
        )
        try:
            for seed in seeds:
                for arm in paired_comparison.ARMS:
                    player(arm, seed, 0)
            pool_summary = player.pool_summary() if hasattr(player, "pool_summary") else None
        finally:
            if hasattr(player, "close"):
                player.close()
        for seed in seeds:
            for arm in paired_comparison.ARMS:
                game_id = f"{series_id}-{arm}-s{seed}-t0"
                rows[(arm, seed)] = _fingerprint(data, game_id)
    execution: dict[str, object] = {
        "series_id": series_id,
        "workers": workers,
        "games_per_jvm": engine.games_per_jvm,
        "pool": pool_summary,
    }
    return rows, execution


def _row_semantic(row: Mapping[str, object] | None) -> object:
    if row is None:
        return None
    if "semantic" in row:
        return row.get("semantic")
    return row.get("semantic_hash")


def _row_winners(row: Mapping[str, object] | None) -> object:
    if row is None:
        return None
    if "winners" in row:
        return row.get("winners")
    if "winner_seat" in row:
        return row.get("winner_seat")
    return row.get("winner_seats")


def _row_decisions(row: Mapping[str, object] | None) -> object:
    if row is None:
        return None
    if "decisions" in row:
        return row.get("decisions")
    return row.get("decision_count")


def compare_paired_identity(
    seeds: Sequence[int],
    alone: Mapping[tuple[str, int], Mapping[str, object]],
    paired: Mapping[tuple[str, int], Mapping[str, object]],
) -> dict[str, object]:
    """Compare every ``(arm, seed)`` game between single-game and parallel paired runs.

    Fail-closed: empty seeds, any missing game on either side, any non-finished status, or any
    difference in semantic hash, winner seat(s) or decision count yields ``passed = False`` and
    ``status = "FAIL"``.
    """
    table: list[dict[str, object]] = []
    for seed in seeds:
        for arm in paired_comparison.ARMS:
            a = alone.get((arm, seed))
            b = paired.get((arm, seed))
            missing_a = a is None
            missing_b = b is None
            status_a = str(a.get("status", "missing")) if a is not None else "missing"
            status_b = str(b.get("status", "missing")) if b is not None else "missing"
            played = (
                not missing_a
                and not missing_b
                and status_a == "finished"
                and status_b == "finished"
            )
            a_sem = _row_semantic(a)
            b_sem = _row_semantic(b)
            a_win = _row_winners(a)
            b_win = _row_winners(b)
            a_dec = _row_decisions(a)
            b_dec = _row_decisions(b)

            same_hash = played and a_sem is not None and a_sem == b_sem
            same_winner = played and a_win is not None and a_win == b_win
            same_decisions = played and a_dec is not None and a_dec == b_dec
            row_identical = same_hash and same_winner and same_decisions

            reasons: list[str] = []
            if missing_a:
                reasons.append("missing_alone")
            elif status_a != "finished":
                reasons.append(f"alone_status={status_a}")
            if missing_b:
                reasons.append("missing_paired")
            elif status_b != "finished":
                reasons.append(f"paired_status={status_b}")
            if played:
                if not same_hash:
                    reasons.append("semantic_hash_mismatch")
                if not same_winner:
                    reasons.append("winner_seat_mismatch")
                if not same_decisions:
                    reasons.append("decision_count_mismatch")

            table.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "identical": row_identical,
                    "hash_equal": same_hash,
                    "winner_equal": same_winner,
                    "decisions_equal": same_decisions,
                    "reasons": reasons,
                    "a": dict(a) if a is not None else None,
                    "b": dict(b) if b is not None else None,
                }
            )

    total = len(table)
    identical = sum(1 for row in table if bool(row["identical"]))
    passed = total > 0 and identical == total and all(bool(row["identical"]) for row in table)
    status = "PASS" if passed else "FAIL"
    mismatches = [row for row in table if not bool(row["identical"])]
    return {
        "status": status,
        "passed": passed,
        "identical": identical,
        "total": total,
        "summary": f"{identical} identisch von {total}",
        "table": table,
        "mismatches": mismatches,
    }


def _write_json(path: Path | None, payload: Mapping[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("batch", "paired"), default="batch")
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK)
    parser.add_argument(
        "--variant-deck",
        type=Path,
        default=None,
        help="variant deck JSON (required for --mode paired)",
    )
    parser.add_argument("--seeds", default="1-6")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--games-per-jvm", type=int, default=3)
    parser.add_argument("--work", type=Path, required=True, help="scratch folder (emptied)")
    parser.add_argument("--out", type=Path, default=None, help="write the comparison as JSON")
    args = parser.parse_args(argv)

    out_path = args.out.resolve() if args.out is not None else None

    if args.mode == "paired":
        if args.variant_deck is None:
            print("ERROR: --variant-deck is required when --mode paired", file=sys.stderr)
            return 2
        if not args.variant_deck.is_file():
            print(f"ERROR: variant deck not found: {args.variant_deck}", file=sys.stderr)
            return 2

    if not args.deck.is_file():
        print(f"ERROR: deck not found: {args.deck}", file=sys.stderr)
        return 2

    seeds = deckbau_eval.seed_list(args.seeds)

    if not args.jar.is_file():
        reason = f"engine jar not found: {args.jar}"
        print(f"IDENTITY NOT_RUN ({reason})")
        _write_json(
            out_path,
            {
                "mode": args.mode,
                "status": "NOT_RUN",
                "passed": False,
                "reason": reason,
                "jar": str(args.jar),
                "seeds": seeds,
            },
        )
        return 2

    jar = args.jar.resolve(strict=True)
    deck = args.deck.resolve(strict=True)
    variant_deck = args.variant_deck.resolve(strict=True) if args.mode == "paired" else None
    opponents = [(ROOT / path).resolve(strict=True) for path in deckbau_eval.PODS["precon"]]

    work = args.work.resolve()
    shutil.rmtree(work, ignore_errors=True)
    subdirs = (
        ("a/base", "a/variant", "b", "cwd", "owner")
        if args.mode == "paired"
        else ("a", "b", "cwd", "owner")
    )
    for name in subdirs:
        (work / name).mkdir(parents=True, exist_ok=True)
    # the bridge keeps its card database under ./db of the working directory
    previous_cwd = Path.cwd()
    os.chdir(work / "cwd")
    try:
        env = dict(os.environ)
        env["COMMANDER_LAB_OWNER_DATA"] = str(work / "owner")
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH", "")])
        )
        base = tuple(jar.as_posix() if part == "{jar}" else part for part in BASE_COMMAND)
        env[ENGINE_COMMAND_ENV] = command_text(base)
        os.environ.update(env)

        if args.mode == "paired":
            if variant_deck is None:
                print("ERROR: --variant-deck is required when --mode paired", file=sys.stderr)
                return 2
            cpu0, wall0 = _cpu_seconds(), time.monotonic()
            alone_base = play_alone(work / "a" / "base", deck, opponents, seeds, env)
            alone_variant = play_alone(work / "a" / "variant", variant_deck, opponents, seeds, env)
            alone_paired: dict[tuple[str, int], dict[str, object]] = {}
            for seed, row in alone_base.items():
                alone_paired[("base", seed)] = row
            for seed, row in alone_variant.items():
                alone_paired[("variant", seed)] = row
            cpu1, wall1 = _cpu_seconds(), time.monotonic()
            paired_rows, execution = play_paired_series(
                work / "b",
                deck,
                variant_deck,
                opponents,
                seeds,
                args.workers,
                args.games_per_jvm,
            )
            cpu2, wall2 = _cpu_seconds(), time.monotonic()

            comparison = compare_paired_identity(seeds, alone_paired, paired_rows)
            ok = bool(comparison["passed"])
            status = str(comparison["status"])
            identical = int(comparison["identical"])
            total = int(comparison["total"])
            summary_text = str(comparison["summary"])
            paired_table = comparison["table"]
            if not isinstance(paired_table, list):
                paired_table = []

            print(
                f"{'arm':<7} {'seed':>4}  {'hash':<5} {'winner':<6} {'decisions':<9}  "
                "semantic transcript (a | b)"
            )
            flag = lambda value: "yes" if value else "NO"  # noqa: E731
            for row in paired_table:
                a_row = row.get("a") if isinstance(row.get("a"), Mapping) else None
                b_row = row.get("b") if isinstance(row.get("b"), Mapping) else None
                a_sem = str(_row_semantic(a_row))[:16]
                b_sem = str(_row_semantic(b_row))[:16]
                reasons = row.get("reasons")
                suffix = (
                    f"  ({', '.join(reasons)})" if isinstance(reasons, list) and reasons else ""
                )
                print(
                    f"{row['arm']!s:<7} {int(row['seed']):>4}  "
                    f"{flag(bool(row['hash_equal'])):<5} "
                    f"{flag(bool(row['winner_equal'])):<6} "
                    f"{flag(bool(row['decisions_equal'])):<9}  "
                    f"{a_sem} | {b_sem}{suffix}"
                )
            print(summary_text)
            print("paired execution:", json.dumps(execution))
            cpu_a = _cpu_delta(cpu0, cpu1)
            cpu_b = _cpu_delta(cpu1, cpu2)
            print(f"(a) one game per JVM: wall {wall1 - wall0:.1f} s, cpu {_format_cpu(cpu_a)}")
            print(
                f"(b) paired series workers={args.workers} games_per_jvm={args.games_per_jvm}: "
                f"wall {wall2 - wall1:.1f} s, cpu {_format_cpu(cpu_b)} "
                "(a measurement, not evidence)"
            )
            print("IDENTITY", status)
            _write_json(
                out_path,
                {
                    "mode": "paired",
                    "status": status,
                    "passed": ok,
                    "summary": summary_text,
                    "seeds": seeds,
                    "identical": identical,
                    "total": total,
                    "table": paired_table,
                    "mismatches": comparison["mismatches"],
                    "execution": execution,
                    "wall_s": {"a": round(wall1 - wall0, 1), "b": round(wall2 - wall1, 1)},
                    "cpu_s": {"a": cpu_a, "b": cpu_b},
                },
            )
            return 0 if ok else 1

        cpu0, wall0 = _cpu_seconds(), time.monotonic()
        alone = play_alone(work / "a", deck, opponents, seeds, env)
        cpu1, wall1 = _cpu_seconds(), time.monotonic()
        series, batch = play_series(
            work / "b", deck, opponents, seeds, args.workers, args.games_per_jvm
        )
        cpu2, wall2 = _cpu_seconds(), time.monotonic()

        print(
            f"{'seed':>4}  {'hash':<5} {'winner':<6} {'decisions':<9}  semantic transcript (a | b)"
        )
        ok = True
        table: list[dict[str, Any]] = []
        for seed in seeds:
            a, b = alone[seed], series[seed]
            played = a["status"] == "finished" and b["status"] == "finished"
            same_hash = played and a["semantic"] is not None and a["semantic"] == b["semantic"]
            same_winner = played and a["winners"] == b["winners"]
            same_decisions = played and a["decisions"] == b["decisions"]
            ok = ok and same_hash and same_winner and same_decisions
            table.append(
                {
                    "seed": seed,
                    "hash_equal": same_hash,
                    "winner_equal": same_winner,
                    "decisions_equal": same_decisions,
                    "a": a,
                    "b": b,
                }
            )
            flag = lambda value: "yes" if value else "NO"  # noqa: E731
            print(
                f"{seed:>4}  {flag(same_hash):<5} {flag(same_winner):<6} {flag(same_decisions):<9}  "
                f"{str(a['semantic'])[:16]} | {str(b['semantic'])[:16]}"
                + ("" if played else f"  (a: {a['status']}, b: {b['status']})")
            )
        identical = sum(1 for row in table if row["hash_equal"])
        print(f"identical {identical}/{len(seeds)}")
        execution = batch.execution()
        print(
            "series execution:", json.dumps({k: v for k, v in execution.items() if k != "chunks"})
        )
        cpu_a = _cpu_delta(cpu0, cpu1)
        cpu_b = _cpu_delta(cpu1, cpu2)
        print(f"(a) one game per JVM: wall {wall1 - wall0:.1f} s, cpu {_format_cpu(cpu_a)}")
        print(
            f"(b) series workers={args.workers} games_per_jvm={args.games_per_jvm}: "
            f"wall {wall2 - wall1:.1f} s, cpu {_format_cpu(cpu_b)} (a measurement, not evidence)"
        )
        print("IDENTITY", "PASS" if ok else "FAIL")
        _write_json(
            out_path,
            {
                "seeds": seeds,
                "table": table,
                "execution": execution,
                "wall_s": {"a": round(wall1 - wall0, 1), "b": round(wall2 - wall1, 1)},
                "cpu_s": {"a": cpu_a, "b": cpu_b},
                "identical": identical,
            },
        )
        return 0 if ok else 1
    finally:
        os.chdir(previous_cwd)


if __name__ == "__main__":
    raise SystemExit(main())
