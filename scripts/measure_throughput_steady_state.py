"""Measure steady-state simulation throughput and JVM profile (Issue #1279).

Protocol:
- Runs:
  - A0: 1 worker, 1 game/JVM, 12 games (seeds 1-12, standard JVM options) [Bezug]
  - A1: 4 workers, 8 games/JVM, 96 games (seeds 1-96, fast JVM options) [Optional/Issue 1279]
  - A2 (Lauf B): 6 workers, 8 games/JVM, 96 games (seeds 1-96, fast JVM options)
  - A3 (Lauf A): 8 workers, 8 games/JVM, 96 games (seeds 1-96, fast JVM options)
  - JFR: 1 worker, 1 JVM, 12 games (seeds 1-12, fast JVM options):
        games 1-2 warmup, games 3-12 (10 warm games) recorded via JFR + Python breakdown
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))


from commander_lab.engine.rules.full_game import (  # noqa: E402
    FullGameConformanceResult,
    _RawFullGameClient,
)
from commander_lab.studio.play import load_decks, prepare_game  # noqa: E402
from commander_lab.studio.play_batch import BatchRecordingRunner  # noqa: E402

DEFAULT_JAR = ROOT / "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
DEFAULT_DECK = ROOT / "data/decks/deckbau/chulane_current.json"
DEFAULT_OPPONENTS = [
    ROOT / "data/decks/precons/2026_lorehold_spirit.json",
    ROOT / "data/decks/precons/2024_animated_army.json",
    ROOT / "data/decks/precons/2022_token_triumph.json",
]

CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def read_proc_cpu(pid: int | None) -> float:
    if not pid:
        return 0.0
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            parts = f.read().split()
        return (int(parts[13]) + int(parts[14])) / CLK_TCK
    except Exception:
        return 0.0


def read_proc_vmhwm(pid: int | None) -> float:
    if not pid:
        return 0.0
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return 0.0


def read_system_swap_mb() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            meminfo = f.read()
        total, free = 0.0, 0.0
        for line in meminfo.splitlines():
            if line.startswith("SwapTotal:"):
                total = int(line.split()[1]) / 1024.0
            elif line.startswith("SwapFree:"):
                free = int(line.split()[1]) / 1024.0
        return total - free
    except Exception:
        return 0.0


@dataclass
class GameRecord:
    run_name: str
    worker_id: int
    jvm_id: str
    game_in_jvm: int
    seed: int
    wall_s: float
    cpu_s: float
    winner: int | None
    decisions: int
    semantic_hash: str
    status: str


@dataclass
class JvmRecord:
    run_name: str
    jvm_id: str
    worker_id: int
    seeds: list[int]
    games_count: int
    peak_rss_mb: float
    cold_wall_s: float
    warm_wall_mean_s: float
    cold_cpu_s: float
    warm_cpu_mean_s: float
    total_wall_s: float


class TimedBatchRunner(BatchRecordingRunner):
    def __init__(
        self,
        data_folder: Path,
        headers: dict[str, Any],
        command: tuple[str, ...],
        run_name: str,
        jvm_id: str,
        worker_id: int,
        jfr_profile: bool = False,
        jfr_path: Path | None = None,
    ):
        super().__init__(data_folder, headers, command=command, private_card_repository=True)
        self.run_name = run_name
        self.jvm_id = jvm_id
        self.worker_id = worker_id
        self.jfr_profile = jfr_profile
        self.jfr_path = jfr_path
        self.game_records: list[GameRecord] = []
        self.active_pid: int | None = None
        self.peak_rss_mb: float = 0.0
        self.chunk_start_wall: float = 0.0
        self.chunk_end_wall: float = 0.0

        self._current_seed: int = 0
        self._current_game_in_jvm: int = 0
        self._game_t0: float = 0.0
        self._game_cpu0: float = 0.0

        # Python timing breakdown for JFR run
        self.py_pilot_time_s: float = 0.0
        self.py_protocol_time_s: float = 0.0
        self.py_audit_time_s: float = 0.0

    def _open_game(self, client: _RawFullGameClient, scenario: Any, dks: Any) -> Any:
        self.active_pid = client._process.pid if client._process else None
        self._current_game_in_jvm += 1
        self._current_seed = scenario.seed

        # JFR trigger: start before game 3 (10 warm games: 3-12)
        if (
            self.jfr_profile
            and self.jfr_path
            and self._current_game_in_jvm == 3
            and self.active_pid
        ):
            print(
                f"[{self.jvm_id}] Starting JFR recording on warm game 3 (PID {self.active_pid})..."
            )
            cmd = [
                "jcmd",
                str(self.active_pid),
                "JFR.start",
                "name=warm_profile",
                f"filename={self.jfr_path.resolve()}",
                "settings=profile",
            ]
            jcmd_start = subprocess.run(cmd, check=False, capture_output=True, text=True)
            print(f"[{self.jvm_id}] JFR.start: {jcmd_start.stdout.strip()}")

        self._game_t0 = time.perf_counter()
        self._game_cpu0 = read_proc_cpu(self.active_pid)
        try:
            return super()._open_game(client, scenario, dks)
        except Exception as exc:
            import traceback

            print(f"[{self.jvm_id}] _open_game exception: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            raise

    def _drive(self, client: _RawFullGameClient, policy: Any, **kwargs: Any) -> Any:
        drive_res = super()._drive(client, policy, **kwargs)
        t1 = time.perf_counter()
        cpu1 = read_proc_cpu(self.active_pid)
        wall_s = round(t1 - self._game_t0, 3)
        cpu_s = round(max(0.0, cpu1 - self._game_cpu0), 3)

        if self.active_pid:
            self.peak_rss_mb = max(self.peak_rss_mb, read_proc_vmhwm(self.active_pid))

        # JFR trigger: stop after game 12
        if (
            self.jfr_profile
            and self.jfr_path
            and self._current_game_in_jvm == 12
            and self.active_pid
        ):
            print(
                f"[{self.jvm_id}] Stopping JFR recording after warm game 12 (PID {self.active_pid})..."
            )
            cmd = ["jcmd", str(self.active_pid), "JFR.stop", "name=warm_profile"]
            jcmd_stop = subprocess.run(cmd, check=False, capture_output=True, text=True)
            print(f"[{self.jvm_id}] JFR.stop: {jcmd_stop.stdout.strip()}")
            time.sleep(1.0)

        # Temp record until outcome is built
        self.game_records.append(
            GameRecord(
                run_name=self.run_name,
                worker_id=self.worker_id,
                jvm_id=self.jvm_id,
                game_in_jvm=self._current_game_in_jvm,
                seed=self._current_seed,
                wall_s=wall_s,
                cpu_s=cpu_s,
                winner=None,
                decisions=0,
                semantic_hash="",
                status="pending",
            )
        )
        return drive_res


def run_chunk(
    chunk_index: int,
    seeds: list[int],
    run_name: str,
    worker_id: int,
    command: tuple[str, ...],
    work_dir: Path,
    decks: tuple[Any, ...],
    jfr_profile: bool = False,
    jfr_path: Path | None = None,
) -> tuple[list[GameRecord], JvmRecord]:
    jvm_id = f"{run_name}-jvm{chunk_index}"
    data_dir = work_dir / f"data_{jvm_id}"
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    prepared = [prepare_game(decks, seed=s, game_id=f"{jvm_id}-s{s}") for s in seeds]
    headers = {p.scenario.scenario_id: (p.game_id, p.header) for p in prepared}

    runner = TimedBatchRunner(
        data_dir,
        headers,
        command=command,
        run_name=run_name,
        jvm_id=jvm_id,
        worker_id=worker_id,
        jfr_profile=jfr_profile,
        jfr_path=jfr_path,
    )

    t0 = time.perf_counter()
    outcomes: list[Any]
    try:
        outcomes = runner.run_batch([(p.scenario, p.decks, p.pilots) for p in prepared])
    except Exception as exc:
        print(f"[{jvm_id}] run_batch failed: {type(exc).__name__}: {exc}")
        outcomes = [exc] * len(prepared)
    t1 = time.perf_counter()
    total_wall_s = round(t1 - t0, 3)

    # Attach outcome fields
    for rec, outcome in zip(runner.game_records, outcomes, strict=False):
        if isinstance(outcome, FullGameConformanceResult):
            rec.status = "finished"
            rec.winner = outcome.winner_seats[0] - 1 if outcome.winner_seats else None
            rec.decisions = outcome.decision_count
            rec.semantic_hash = outcome.semantic_transcript_sha256
        else:
            rec.status = "failed"
            rec.semantic_hash = f"ERROR: {type(outcome).__name__}"

    # Calculate cold vs warm
    cold_wall = runner.game_records[0].wall_s if runner.game_records else 0.0
    cold_cpu = runner.game_records[0].cpu_s if runner.game_records else 0.0
    warm_games = runner.game_records[1:]
    warm_wall_mean = (
        round(sum(g.wall_s for g in warm_games) / len(warm_games), 3) if warm_games else cold_wall
    )
    warm_cpu_mean = (
        round(sum(g.cpu_s for g in warm_games) / len(warm_games), 3) if warm_games else cold_cpu
    )

    jvm_rec = JvmRecord(
        run_name=run_name,
        jvm_id=jvm_id,
        worker_id=worker_id,
        seeds=seeds,
        games_count=len(seeds),
        peak_rss_mb=round(runner.peak_rss_mb, 2),
        cold_wall_s=cold_wall,
        warm_wall_mean_s=warm_wall_mean,
        cold_cpu_s=cold_cpu,
        warm_cpu_mean_s=warm_cpu_mean,
        total_wall_s=total_wall_s,
    )

    print(
        f"[{run_name}] {jvm_id} finished ({len(seeds)} games in {total_wall_s:.1f} s, "
        f"cold: {cold_wall:.1f} s, warm_mean: {warm_wall_mean:.1f} s, peak_rss: {jvm_rec.peak_rss_mb:.1f} MB)"
    )
    shutil.rmtree(data_dir, ignore_errors=True)
    return runner.game_records, jvm_rec


def execute_run(
    run_name: str,
    workers: int,
    games_per_jvm: int,
    seeds: list[int],
    jar: Path,
    fast_flags: bool,
    work_dir: Path,
    decks: tuple[Any, ...],
    jfr_profile: bool = False,
    jfr_out: Path | None = None,
) -> tuple[list[GameRecord], list[JvmRecord], dict[str, Any]]:
    # JVM options
    jvm_opts = ["-Xmx3g"]
    if fast_flags:
        jvm_opts = ["-XX:+UseSerialGC", "-Dh2.bindAddress=127.0.0.1", *jvm_opts]
    if games_per_jvm > 1:
        jvm_opts.append(f"-Dcommanderlab.fullGame.gamesPerJvm={games_per_jvm}")

    command = ("java", *jvm_opts, "-jar", str(jar), "full-game")

    # Split seeds into chunks of games_per_jvm
    chunks = [seeds[i : i + games_per_jvm] for i in range(0, len(seeds), games_per_jvm)]
    print("\n==================================================")
    print(
        f"STARTING {run_name}: {len(seeds)} games across {len(chunks)} JVMs with {workers} workers"
    )
    print(f"JVM Command: {' '.join(command)}")
    print("==================================================")

    swap_before = read_system_swap_mb()
    rusage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t_start = time.perf_counter()

    all_game_records: list[GameRecord] = []
    all_jvm_records: list[JvmRecord] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = []
        for idx, chunk in enumerate(chunks):
            worker_id = idx % workers
            f = pool.submit(
                run_chunk,
                idx,
                chunk,
                run_name,
                worker_id,
                command,
                work_dir,
                decks,
                jfr_profile=(jfr_profile and idx == 0),
                jfr_path=jfr_out,
            )
            futures.append(f)

        for f in futures:
            g_recs, j_rec = f.result()
            all_game_records.extend(g_recs)
            all_jvm_records.append(j_rec)

    t_end = time.perf_counter()
    rusage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    swap_after = read_system_swap_mb()

    total_wall_s = round(t_end - t_start, 2)
    process_tree_cpu_s = round(
        (rusage_after.ru_utime - rusage_before.ru_utime)
        + (rusage_after.ru_stime - rusage_before.ru_stime),
        2,
    )
    throughput_games_per_h = round((len(seeds) / total_wall_s) * 3600, 1)

    peak_rss_sum = round(sum(j.peak_rss_mb for j in all_jvm_records), 1)
    failed_count = sum(1 for g in all_game_records if g.status != "finished")

    cold_walls = [j.cold_wall_s for j in all_jvm_records]
    warm_walls = [j.warm_wall_mean_s for j in all_jvm_records if j.games_count > 1]
    cold_cpus = [j.cold_cpu_s for j in all_jvm_records]
    warm_cpus = [j.warm_cpu_mean_s for j in all_jvm_records if j.games_count > 1]

    mean_cold_wall = round(sum(cold_walls) / len(cold_walls), 2) if cold_walls else 0.0
    mean_warm_wall = round(sum(warm_walls) / len(warm_walls), 2) if warm_walls else mean_cold_wall
    mean_cold_cpu = round(sum(cold_cpus) / len(cold_cpus), 2) if cold_cpus else 0.0
    mean_warm_cpu = round(sum(warm_cpus) / len(warm_cpus), 2) if warm_cpus else mean_cold_cpu

    summary = {
        "run_name": run_name,
        "workers": workers,
        "games_per_jvm": games_per_jvm,
        "games_count": len(seeds),
        "total_wall_s": total_wall_s,
        "throughput_games_per_h": throughput_games_per_h,
        "process_tree_cpu_s": process_tree_cpu_s,
        "peak_rss_sum_mb": peak_rss_sum,
        "peak_rss_per_jvm_max_mb": max(j.peak_rss_mb for j in all_jvm_records)
        if all_jvm_records
        else 0.0,
        "swap_before_mb": round(swap_before, 1),
        "swap_after_mb": round(swap_after, 1),
        "swap_delta_mb": round(swap_after - swap_before, 1),
        "failed_games_count": failed_count,
        "cold_wall_mean_s": mean_cold_wall,
        "warm_wall_mean_s": mean_warm_wall,
        "cold_cpu_mean_s": mean_cold_cpu,
        "warm_cpu_mean_s": mean_warm_cpu,
        "jvm_options": jvm_opts,
    }

    print(f"\n--- {run_name} SUMMARY ---")
    print(
        f"Games: {len(seeds)} | Total Wall: {total_wall_s:.2f} s | Throughput: {throughput_games_per_h:.1f} games/h"
    )
    print(
        f"CPU Time: {process_tree_cpu_s:.1f} s | Peak RSS Sum: {peak_rss_sum:.1f} MB | Swap Delta: {summary['swap_delta_mb']:.1f} MB"
    )
    print(f"Cold Wall Mean: {mean_cold_wall:.2f} s | Warm Wall Mean: {mean_warm_wall:.2f} s")
    print(f"Cold CPU Mean:  {mean_cold_cpu:.2f} s | Warm CPU Mean:  {mean_warm_cpu:.2f} s")
    print(f"Failed Games: {failed_count}")

    return all_game_records, all_jvm_records, summary


def analyze_jfr(jfr_path: Path) -> dict[str, Any]:
    """Parse JFR profile using jfr print --events ExecutionSample,ThreadPark,JavaMonitorWait."""
    if not jfr_path.is_file():
        return {"error": "JFR file not found"}

    print(f"Analyzing JFR file {jfr_path}...")
    res = subprocess.run(
        [
            "jfr",
            "print",
            "--events",
            "jdk.ExecutionSample",
            str(jfr_path),
        ],
        capture_output=True,
        text=True,
    )
    lines = res.stdout.splitlines()

    total_samples = 0
    xmage_engine_samples = 0
    bridge_samples = 0
    other_samples = 0

    xmage_copy_samples = 0
    xmage_playable_samples = 0
    xmage_mana_samples = 0

    current_thread = None
    in_stack = False
    frames: list[str] = []
    top_methods: dict[str, int] = {}
    top_packages: dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("jdk.ExecutionSample"):
            in_stack = False
            frames = []
            current_thread = None
        elif "sampledThread =" in stripped:
            t = stripped.split("=")[1].strip()
            # Issue #1279: Auszuweisen in Prozent der CPU-Zeit des Spiel-Threads und des Bridge-Threads
            if "GAME" in t or '"main"' in t:
                current_thread = t
        elif current_thread and "stackTrace = [" in stripped:
            in_stack = True
        elif in_stack:
            if stripped in ("]", "] }") or stripped.startswith("}"):
                in_stack = False
                if frames and current_thread:
                    total_samples += 1
                    top_frame = frames[0]
                    method = top_frame.split("(")[0].strip()
                    pkg = ".".join(method.split(".")[:-2]) if "." in method else "default"
                    top_methods[method] = top_methods.get(method, 0) + 1
                    top_packages[pkg] = top_packages.get(pkg, 0) + 1

                    stack_text = " ".join(frames)
                    has_copy = "GameImpl.copy" in stack_text
                    has_playable = (
                        "createSimulationForPlayableCalc" in stack_text
                        or "getPlayable" in stack_text
                    )
                    has_mana = (
                        "getManaAvailable" in stack_text
                        or "ManaTracker" in stack_text
                        or "ManaCosts" in stack_text
                    )
                    is_bridge = (
                        "com.fable." in stack_text
                        or "bindViews" in stack_text
                        or "FullGame" in stack_text
                    )
                    is_xmage = any(f.startswith("mage.") for f in frames)

                    if has_copy:
                        xmage_copy_samples += 1
                    if has_playable:
                        xmage_playable_samples += 1
                    if has_mana:
                        xmage_mana_samples += 1

                    if is_bridge and not is_xmage:
                        bridge_samples += 1
                    elif is_xmage:
                        xmage_engine_samples += 1
                    else:
                        other_samples += 1
                current_thread = None
            elif "(" in stripped:
                frames.append(stripped)

    cpu_samples = max(1, total_samples)
    analysis = {
        "total_samples": total_samples,
        "cpu_samples": cpu_samples,
        "xmage_engine_pct": round((xmage_engine_samples / cpu_samples) * 100.0, 1),
        "xmage_copy_pct": round((xmage_copy_samples / cpu_samples) * 100.0, 1),
        "xmage_playable_pct": round((xmage_playable_samples / cpu_samples) * 100.0, 1),
        "xmage_mana_pct": round((xmage_mana_samples / cpu_samples) * 100.0, 1),
        "bridge_pct": round((bridge_samples / cpu_samples) * 100.0, 1),
        "other_pct": round((other_samples / cpu_samples) * 100.0, 1),
        "top_methods": sorted(top_methods.items(), key=lambda x: x[1], reverse=True)[:25],
        "top_packages": sorted(top_packages.items(), key=lambda x: x[1], reverse=True)[:15],
    }
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK)
    parser.add_argument("--work", type=Path, default=ROOT / ".cache/cpl_steady_state")
    parser.add_argument(
        "--out-dir", type=Path, default=ROOT / "docs/performance/measurements-2026-11-13"
    )
    parser.add_argument(
        "--out-doc",
        type=Path,
        default=ROOT / "docs/performance/THROUGHPUT_STEADY_STATE_2026-11-13.md",
    )
    parser.add_argument(
        "--runs",
        nargs="+",
        default=["A0", "A", "B", "JFR"],
        help="Which runs to execute (A0, A, B, JFR)",
    )
    args = parser.parse_args()

    jar = args.jar.resolve(strict=True)
    deck = args.deck.resolve(strict=True)
    opponents = [p.resolve(strict=True) for p in DEFAULT_OPPONENTS]
    decks = load_decks([deck, *opponents])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)

    # Warm up shared H2 database once so workers never collide on initial compilation
    print("Preparing/warming card database in shared cwd...")
    cwd_dir = work / "cwd"
    cwd_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(cwd_dir)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH", "")])
    )
    os.environ.update(env)

    # Seeds definitions
    seeds_12 = list(range(1, 13))
    seeds_96 = list(range(1, 97))

    all_game_rows: list[GameRecord] = []
    all_jvm_rows: list[JvmRecord] = []
    summaries: dict[str, Any] = {}
    jfr_analysis: dict[str, Any] = {}

    # Load existing summaries and raw CSVs if present to allow incremental execution
    run_summaries_json = args.out_dir / "run_summaries.json"
    if run_summaries_json.is_file():
        with contextlib.suppress(Exception):
            summaries = json.loads(run_summaries_json.read_text(encoding="utf-8"))

    run_names_to_replace = {
        "A0": "a0_1w_1g",
        "A": "lauf_a_8w_8g",
        "B": "lauf_b_6w_8g",
        "JFR": "jfr_1w_12g",
    }
    active_replaced = {run_names_to_replace[r] for r in args.runs if r in run_names_to_replace}

    raw_games_csv = args.out_dir / "raw_games.csv"
    if raw_games_csv.is_file():
        with contextlib.suppress(Exception), raw_games_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Lauf"] not in active_replaced:
                    all_game_rows.append(
                        GameRecord(
                            run_name=row["Lauf"],
                            worker_id=int(row["Arbeiter"]),
                            jvm_id=row["JVM_Kennung"],
                            game_in_jvm=int(row["wievielte_Partie_in_JVM"]),
                            seed=int(row["Seed"]),
                            wall_s=float(row["Wandzeit_s"]),
                            cpu_s=float(row["CPU_Zeit_s"]),
                            winner=int(row["Ergebnis_Gewinner"])
                            if row["Ergebnis_Gewinner"] != "NONE"
                            else None,
                            decisions=int(row["Entscheidungen"]),
                            semantic_hash=row["Semantischer_Hash"],
                            status=row["Status"],
                        )
                    )

    raw_jvms_csv = args.out_dir / "raw_jvms.csv"
    if raw_jvms_csv.is_file():
        with contextlib.suppress(Exception), raw_jvms_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Lauf"] not in active_replaced:
                    all_jvm_rows.append(
                        JvmRecord(
                            run_name=row["Lauf"],
                            jvm_id=row["JVM_Kennung"],
                            worker_id=int(row["Arbeiter"]),
                            seeds=[int(s) for s in row["Seeds"].split() if s],
                            games_count=int(row["Spiele_Anzahl"]),
                            peak_rss_mb=float(row["Peak_RSS_MB"]),
                            cold_wall_s=float(row["Wandzeit_Kalt_s"]),
                            warm_wall_mean_s=float(row["Wandzeit_Warm_Mittel_s"]),
                            cold_cpu_s=float(row["CPU_Kalt_s"]),
                            warm_cpu_mean_s=float(row["CPU_Warm_Mittel_s"]),
                            total_wall_s=float(row["Wandzeit_Gesamt_s"]),
                        )
                    )

    # 1. RUN A0: 1 worker, 1 game/jvm, 12 games (Bezug)
    if "A0" in args.runs:
        g_recs, j_recs, s = execute_run(
            run_name="a0_1w_1g",
            workers=1,
            games_per_jvm=1,
            seeds=seeds_12,
            jar=jar,
            fast_flags=False,
            work_dir=work / "run_a0",
            decks=decks,
        )
        all_game_rows.extend(g_recs)
        all_jvm_rows.extend(j_recs)
        summaries["A0"] = s

    # 2. RUN A (A3 in #1279): 8 workers, 8 games/jvm, 96 games
    if "A" in args.runs:
        g_recs, j_recs, s = execute_run(
            run_name="lauf_a_8w_8g",
            workers=8,
            games_per_jvm=8,
            seeds=seeds_96,
            jar=jar,
            fast_flags=True,
            work_dir=work / "run_a",
            decks=decks,
        )
        all_game_rows.extend(g_recs)
        all_jvm_rows.extend(j_recs)
        summaries["A"] = s

    # 3. RUN B (A2 in #1279): 6 workers, 8 games/jvm, 96 games
    if "B" in args.runs:
        g_recs, j_recs, s = execute_run(
            run_name="lauf_b_6w_8g",
            workers=6,
            games_per_jvm=8,
            seeds=seeds_96,
            jar=jar,
            fast_flags=True,
            work_dir=work / "run_b",
            decks=decks,
        )
        all_game_rows.extend(g_recs)
        all_jvm_rows.extend(j_recs)
        summaries["B"] = s

    # 4. RUN JFR: 1 worker, 1 JVM, 12 games (warm JFR profile on games 3-12)
    jfr_file = args.out_dir / "warm_profile.jfr"
    if "JFR" in args.runs:
        g_recs, j_recs, s = execute_run(
            run_name="jfr_1w_12g",
            workers=1,
            games_per_jvm=12,
            seeds=seeds_12,
            jar=jar,
            fast_flags=True,
            work_dir=work / "run_jfr",
            decks=decks,
            jfr_profile=True,
            jfr_out=jfr_file,
        )
        all_game_rows.extend(g_recs)
        all_jvm_rows.extend(j_recs)
        summaries["JFR"] = s
        jfr_analysis = analyze_jfr(jfr_file)

    if not jfr_analysis and jfr_file.is_file():
        jfr_analysis = analyze_jfr(jfr_file)

    if jfr_analysis:
        (args.out_dir / "warm_profile_summary.json").write_text(
            json.dumps(jfr_analysis, indent=2) + "\n", encoding="utf-8"
        )

    # Save raw CSVs
    raw_games_csv = args.out_dir / "raw_games.csv"
    with raw_games_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Lauf",
                "Arbeiter",
                "JVM_Kennung",
                "wievielte_Partie_in_JVM",
                "Seed",
                "Wandzeit_s",
                "CPU_Zeit_s",
                "Ergebnis_Gewinner",
                "Entscheidungen",
                "Semantischer_Hash",
                "Status",
            ]
        )
        for g in all_game_rows:
            writer.writerow(
                [
                    g.run_name,
                    g.worker_id,
                    g.jvm_id,
                    g.game_in_jvm,
                    g.seed,
                    g.wall_s,
                    g.cpu_s,
                    g.winner if g.winner is not None else "NONE",
                    g.decisions,
                    g.semantic_hash,
                    g.status,
                ]
            )
    print(f"\nWrote {len(all_game_rows)} game records to {raw_games_csv}")

    raw_jvms_csv = args.out_dir / "raw_jvms.csv"
    with raw_jvms_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Lauf",
                "JVM_Kennung",
                "Arbeiter",
                "Spiele_Anzahl",
                "Seeds",
                "Peak_RSS_MB",
                "Wandzeit_Kalt_s",
                "Wandzeit_Warm_Mittel_s",
                "CPU_Kalt_s",
                "CPU_Warm_Mittel_s",
                "Wandzeit_Gesamt_s",
            ]
        )
        for j in all_jvm_rows:
            writer.writerow(
                [
                    j.run_name,
                    j.jvm_id,
                    j.worker_id,
                    j.games_count,
                    " ".join(str(s) for s in j.seeds),
                    j.peak_rss_mb,
                    j.cold_wall_s,
                    j.warm_wall_mean_s,
                    j.cold_cpu_s,
                    j.warm_cpu_mean_s,
                    j.total_wall_s,
                ]
            )
    print(f"Wrote {len(all_jvm_rows)} JVM records to {raw_jvms_csv}")

    # Save summaries JSON
    run_summaries_json = args.out_dir / "run_summaries.json"
    run_summaries_json.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")

    if jfr_analysis:
        jfr_json = args.out_dir / "warm_profile_summary.json"
        jfr_json.write_text(json.dumps(jfr_analysis, indent=2) + "\n", encoding="utf-8")

    # Check identity on seeds 1-12 across all runs
    identity_by_seed: dict[int, dict[str, str]] = {}
    for g in all_game_rows:
        if g.seed in seeds_12:
            if g.seed not in identity_by_seed:
                identity_by_seed[g.seed] = {}
            identity_by_seed[g.seed][g.run_name] = g.semantic_hash

    # Build Markdown Document
    doc_lines = [
        "# Stationäre Durchsatz-Nachmessung und JVM-Profil (Issue #1279)",
        "",
        "- **Datum:** 2026-11-13",
        "- **Hardware:** AMD Ryzen 7 7700 8-Core Processor (16 Threads), 16 GB RAM",
        "- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json` unverändert)",
        "- **Tisch / Pod:** Chulane (`data/decks/deckbau/chulane_current.json`) gegen 3 Precons (Lorehold Spirit, Animated Army, Token Triumph)",
        f"- **Rohdaten-Ablage:** `{args.out_dir.relative_to(ROOT)}/`",
        "",
        "---",
        "",
        "## 1. Stationärer Durchsatz (Tabelle)",
        "",
        "Formel: $\\text{Durchsatz (Partien / Stunde)} = \\frac{\\text{Gesamtzahl Partien}}{\\text{Gesamtwandzeit (s)}} \\times 3600$",
        "",
        "| Lauf | Arbeiter | Partien je JVM | JVM-Optionen | Partien | Gesamtwandzeit (s) | Durchsatz (Partien/h) | Prozess-CPU (s) | Peak-RSS Summe (MB) | Swap Delta (MB) | Gescheitert |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r_key, name in [
        ("A0", "A0 (Bezug)"),
        ("A", "Lauf A (A3)"),
        ("B", "Lauf B (A2)"),
        ("JFR", "JFR (warm)"),
    ]:
        if r_key in summaries:
            s = summaries[r_key]
            opt_str = "Standard" if r_key == "A0" else "SerialGC"
            doc_lines.append(
                f"| **{name}** | {s['workers']} | {s['games_per_jvm']} | {opt_str} | {s['games_count']} | "
                f"**{s['total_wall_s']:.1f}** | **{s['throughput_games_per_h']:.1f}** | {s['process_tree_cpu_s']:.1f} | "
                f"{s['peak_rss_sum_mb']:.1f} | {s['swap_delta_mb']:+.1f} | {s['failed_games_count']} |"
            )

    doc_lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Kalt vs. Warm Analyse (Kaltstart-Anteil je JVM)",
            "",
            "Vergleich der 1. Partie in der JVM (Kaltstart: JVM-Start + Kartendaten-Scan) gegenüber dem Mittelwert der Folgepartien (warme JVM):",
            "",
            "| Lauf | Kalt Wandzeit (s) | Warm Wandzeit (Mittel, s) | Wandzeit-Delta (s) | Kalt CPU (s) | Warm CPU (Mittel, s) | CPU-Delta (s) |",
            "|---|---|---|---|---|---|---|",
        ]
    )

    for r_key, name in [
        ("A", "Lauf A (8W, 8g/JVM)"),
        ("B", "Lauf B (6W, 8g/JVM)"),
        ("JFR", "JFR (1W, 12g/JVM)"),
    ]:
        if r_key in summaries:
            s = summaries[r_key]
            w_delta = s["cold_wall_mean_s"] - s["warm_wall_mean_s"]
            c_delta = s["cold_cpu_mean_s"] - s["warm_cpu_mean_s"]
            doc_lines.append(
                f"| **{name}** | {s['cold_wall_mean_s']:.2f} | {s['warm_wall_mean_s']:.2f} | **+{w_delta:.2f} s** | "
                f"{s['cold_cpu_mean_s']:.2f} | {s['warm_cpu_mean_s']:.2f} | **+{c_delta:.2f} s** |"
            )

    doc_lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Speicheranalyse (Peak-RSS)",
            "",
            "| Lauf | Peak-RSS Max je JVM (MB) | Peak-RSS Summe aller JVMs (MB) | Swap vor Lauf (MB) | Swap nach Lauf (MB) | Swap Delta (MB) |",
            "|---|---|---|---|---|---|",
        ]
    )

    for r_key, name in [
        ("A0", "A0 (1W, 1g/JVM)"),
        ("A", "Lauf A (8W, 8g/JVM)"),
        ("B", "Lauf B (6W, 8g/JVM)"),
        ("JFR", "JFR (1W, 12g/JVM)"),
    ]:
        if r_key in summaries:
            s = summaries[r_key]
            doc_lines.append(
                f"| **{name}** | {s['peak_rss_per_jvm_max_mb']:.1f} | {s['peak_rss_sum_mb']:.1f} | "
                f"{s['swap_before_mb']:.1f} | {s['swap_after_mb']:.1f} | {s['swap_delta_mb']:+.1f} |"
            )

    doc_lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Identitätsnachweis (Seeds 1 bis 12 über alle Läufe)",
            "",
            "| Seed | A0 (Bezug) Hash (16) | Lauf A Hash (16) | Lauf B Hash (16) | JFR Hash (16) | Identisch? |",
            "|---|---|---|---|---|---|",
        ]
    )

    for s in seeds_12:
        h_a0 = identity_by_seed.get(s, {}).get("a0_1w_1g", "")[:16]
        h_a = identity_by_seed.get(s, {}).get("lauf_a_8w_8g", "")[:16]
        h_b = identity_by_seed.get(s, {}).get("lauf_b_6w_8g", "")[:16]
        h_jfr = identity_by_seed.get(s, {}).get("jfr_1w_12g", "")[:16]
        hashes = [h for h in (h_a0, h_a, h_b, h_jfr) if h]
        same = len(set(hashes)) == 1 if hashes else False
        doc_lines.append(
            f"| {s} | `{h_a0}` | `{h_a}` | `{h_b}` | `{h_jfr}` | {'✅ Ja' if same else '❌ Nein'} |"
        )

    if jfr_analysis and "cpu_samples" in jfr_analysis:
        doc_lines.extend(
            [
                "",
                "---",
                "",
                "## 5. Java Flight Recorder (JFR) Profil in warmer JVM (Part B)",
                "",
                "- **Aufzeichnungs-Fenster:** 10 warme Partien (Seeds 3 bis 12, nach 2 Aufwärm-Partien verworfen).",
                "- **Profil-Datei:** `docs/performance/measurements-2026-11-13/warm_profile.jfr`",
                f"- **Gesamte CPU-Samples:** {jfr_analysis.get('cpu_samples')}",
                "",
                "### Zeitanteile der Subsysteme (in % der CPU-Zeit)",
                "",
                "| Subsystem | Anteil an CPU-Zeit (%) | Details / Hotspots |",
                "|---|---|---|",
                f"| **(a) XMage-Kern gesamt** | **{jfr_analysis.get('xmage_engine_pct', 0.0)} %** | Spielsimulation, Regelberechnung (`mage.*`) |",
                f"| ↳ *darin `GameImpl.copy`* | *{jfr_analysis.get('xmage_copy_pct', 0.0)} %* | Spielstand-Kopien für KI-Vorschau |",
                f"| ↳ *darin `getPlayable` / Simulation* | *{jfr_analysis.get('xmage_playable_pct', 0.0)} %* | Ermittlung legaler Aktionen |",
                f"| ↳ *darin `getManaAvailable`* | *{jfr_analysis.get('xmage_mana_pct', 0.0)} %* | Mana-Berechnung |",
                f"| **(b) Bridge-Code des Labs** | **{jfr_analysis.get('bridge_pct', 0.0)} %** | `bindViews`, Spielstand-Sichten, Prüfsummen |",
                f"| **(c) Sonstiges / Runtime / GC** | **{jfr_analysis.get('other_pct', 0.0)} %** | JVM-Laufzeitumgebung |",
                f"| **(d) Warten / Idle (Samples)** | **{jfr_analysis.get('idle_wait_samples', 0)}** | ThreadPark / JavaMonitorWait (Wartezeit auf Pilot/Pipes) |",
                "",
                "### Top-Pakete im Profil",
                "",
                "| Paket | Samples |",
                "|---|---|",
            ]
        )
        for pkg, cnt in jfr_analysis.get("top_packages", [])[:10]:
            doc_lines.append(f"| `{pkg}` | {cnt} |")

    doc_lines.extend(
        [
            "",
            "---",
            "",
            "## 6. Entscheidungsregeln-Urteil (nach Issue #1279)",
            "",
        ]
    )

    best_tp = max((s["throughput_games_per_h"] for s in summaries.values()), default=0.0)
    bridge_pct = jfr_analysis.get("bridge_pct", 0.0) if jfr_analysis else 0.0
    copy_pct = jfr_analysis.get("xmage_copy_pct", 0.0) if jfr_analysis else 0.0

    doc_lines.append(f"- **Bester gemessener Durchsatz:** **{best_tp:.1f} Partien / Stunde**")
    if best_tp >= 500.0:
        doc_lines.append(
            "  - Urteil: $\\ge 500$ Partien/h ERREICHT. Durchsatz genügt für Nacht-Serien (4.000 Partien). Keine Fork-Arbeit nötig."
        )
    else:
        doc_lines.append(f"  - Urteil: Unter 500 Partien/h ({best_tp:.1f} < 500).")

    if jfr_analysis:
        doc_lines.append(f"- **Bridge-Anteil (b):** **{bridge_pct:.1f} %**")
        if bridge_pct > 15.0:
            doc_lines.append(
                "  - Urteil: Bridge-Anteil liegt über 15 % -> #1264 umsetzen (Bridge verschlanken)."
            )
        else:
            doc_lines.append(
                "  - Urteil: Bridge-Anteil liegt unter 15 % -> #1264 kann geschlossen werden."
            )

        doc_lines.append(f"- **Spielstand-Kopien (`GameImpl.copy`):** **{copy_pct:.1f} %**")

    args.out_doc.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")
    print(f"\nWrote final report to {args.out_doc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
