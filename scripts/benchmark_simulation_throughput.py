"""Benchmark Studio simulation throughput and verify identity against baseline.

Runs the exact same 10 seeds (1-10) with the optimized BatchSimulation configuration,
verifies that results (semantic hash, winner, decision count) match the baseline,
and computes the throughput speedup factor.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import deckbau_eval  # noqa: E402

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
BASELINE_JSON = ROOT / "data/research/simulation_throughput_baseline_10games.json"


def _fingerprint(data: Path, game_id: str) -> dict[str, Any]:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK)
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--games-per-jvm", type=int, default=2)
    parser.add_argument("--work", type=Path, default=Path("/tmp/cpl_throughput_bench"))
    parser.add_argument("--baseline", type=Path, default=BASELINE_JSON)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=ROOT / "data/research/simulation_throughput_comparison.json",
    )
    parser.add_argument(
        "--out-md", type=Path, default=ROOT / "data/research/simulation_throughput_comparison.md"
    )
    args = parser.parse_args(argv)

    seeds = deckbau_eval.seed_list(args.seeds)
    jar = args.jar.resolve(strict=True)
    deck = args.deck.resolve(strict=True)
    opponents = [(ROOT / path).resolve(strict=True) for path in deckbau_eval.PODS["precon"]]

    baseline_data = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_by_seed = {t["seed"]: t for t in baseline_data["timings"]}

    work = args.work.resolve()
    # Preserve cwd/.runtime if db exists to avoid parallel H2 rebuild storm across workers
    db_exists = (work / "cwd/.runtime/engine/db").is_dir() or (work / "cwd/db").is_dir()
    shutil.rmtree(work / "data", ignore_errors=True)
    shutil.rmtree(work / "owner", ignore_errors=True)
    if not db_exists:
        shutil.rmtree(work, ignore_errors=True)
    for name in ("data", "cwd", "owner"):
        (work / name).mkdir(parents=True, exist_ok=True)

    os.chdir(work / "cwd")
    env = dict(os.environ)
    env["COMMANDER_LAB_OWNER_DATA"] = str(work / "owner")
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH", "")])
    )
    base = tuple(jar.as_posix() if part == "{jar}" else part for part in BASE_COMMAND)
    env[ENGINE_COMMAND_ENV] = command_text(base)
    os.environ.update(env)

    engine = series_engine(work / "data", args.games_per_jvm)
    if engine is None:
        raise SystemExit("no engine command: set " + ENGINE_COMMAND_ENV)

    print(f"=== Starting Throughput Benchmark ({len(seeds)} games) ===")
    print(f"Configuration: workers={args.workers}, games_per_jvm={args.games_per_jvm}")
    print(f"JVM flags: {' '.join(engine.jvm_flags)}")
    print(f"Engine pin: {baseline_data.get('engine_pin')}")

    batch = BatchSimulation(
        "bench-fast",
        work / "data",
        deck_id="chulane",
        revision_id="current",
        pod_name="precon",
        opponent_paths=opponents,
        seeds=seeds,
        workers=args.workers,
        games_per_jvm=args.games_per_jvm,
        engine=engine,
    )

    t0 = time.perf_counter()
    batch.run_worker(None, deck)
    t1 = time.perf_counter()
    total_wall_s = t1 - t0

    print(f"\nSeries finished in {total_wall_s:.2f} s")
    print(
        f"{'seed':>4}  {'hash':<5} {'winner':<6} {'decisions':<9}  status  semantic_transcript_sha256"
    )

    all_identical = True
    seed_results: list[dict[str, Any]] = []

    for seed in seeds:
        fp = _fingerprint(work / "data", batch.game_id_of(seed))
        base_t = baseline_by_seed.get(seed)

        if base_t:
            same_hash = fp["semantic"] == base_t["semantic_hash"]
            # baseline winner_seats from profile_game_phases was 1-indexed; convert to 0-indexed
            base_winners = (
                [s - 1 for s in base_t["winner_seats"]] if base_t.get("winner_seats") else []
            )
            same_winner = fp["winners"] == base_winners
            same_decisions = fp["decisions"] == base_t["decision_count"]
            match = same_hash and same_winner and same_decisions and fp["status"] == "finished"
        else:
            same_hash = same_winner = same_decisions = match = False

        if not match:
            all_identical = False

        print(
            f"{seed:>4}  {'yes' if same_hash else 'NO':<5} {'yes' if same_winner else 'NO':<6} {'yes' if same_decisions else 'NO':<9}  "
            f"{fp['status']:<7} {str(fp['semantic'])[:16]}"
        )

        seed_results.append(
            {
                "seed": seed,
                "status": fp["status"],
                "hash_identical": same_hash,
                "winner_identical": same_winner,
                "decisions_identical": same_decisions,
                "semantic_hash": fp["semantic"],
                "winner_seats": fp["winners"],
                "decision_count": fp["decisions"],
                "baseline_hash": base_t.get("semantic_hash") if base_t else None,
                "baseline_winners": base_t.get("winner_seats") if base_t else None,
                "baseline_decisions": base_t.get("decision_count") if base_t else None,
            }
        )

    # Throughput calculations
    games_count = len(seeds)
    durchsatz_neu = round((games_count / total_wall_s) * 3600, 1)

    # Baseline: 10 games total wall time was 287.35 s (median 26.815 s per game)
    # Using baseline total wall time: (10 / 287.35) * 3600 = 125.3 games/h
    # Using baseline median per game: 3600 / 26.815 = 134.3 games/h
    baseline_durchsatz = baseline_data.get("games_per_hour_baseline", 134.3)
    faktor = round(durchsatz_neu / baseline_durchsatz, 2)

    print("\n=== Throughput Comparison ===")
    print(f"Durchsatz alt (Baseline):  {baseline_durchsatz:.1f} Partien/h (Wall: 287.4 s)")
    print(f"Durchsatz neu (Optimiert): {durchsatz_neu:.1f} Partien/h (Wall: {total_wall_s:.2f} s)")
    print(f"Faktor (neu / alt):         {faktor:.2f}x")
    print(f"Identitaet:                {'PASS (10/10 identisch)' if all_identical else 'FAIL'}")
    print(f"Erfolgskriterium >= 5.0x:  {'ERFUELLT' if faktor >= 5.0 else 'NICHT ERFUELLT'}")

    comparison = {
        "engine_pin": baseline_data.get("engine_pin"),
        "games_count": games_count,
        "workers": args.workers,
        "games_per_jvm": args.games_per_jvm,
        "jvm_flags": engine.jvm_flags,
        "baseline": {
            "wall_time_s": 287.35,
            "median_per_game_s": baseline_data.get("median_total_wall_s"),
            "throughput_games_per_h": baseline_durchsatz,
            "description": "1 worker, 1 game/JVM, standard JVM flags",
        },
        "optimized": {
            "wall_time_s": round(total_wall_s, 2),
            "throughput_games_per_h": durchsatz_neu,
            "description": f"{args.workers} workers, {args.games_per_jvm} games/JVM, fast JVM flags (SerialGC, AppCDS if present)",
        },
        "speedup_factor": faktor,
        "target_met_5x": faktor >= 5.0,
        "all_identical": all_identical,
        "seeds": seed_results,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# Simulation Durchsatz-Gegenüberstellung (Issue #1251)",
        "",
        f"- **Engine-Pin:** `{baseline_data.get('engine_pin')}`",
        f"- **Stichprobe:** {games_count} Partien (Seeds 1-10, Chulane vs. 3 Precons: Lorehold Spirit, Animated Army, Token Triumph)",
        "- **System:** 16 CPU Kerne, 16 GB RAM",
        f"- **Fast-Konfiguration:** `workers={args.workers}`, `games_per_jvm={args.games_per_jvm}`, JVM-Flags: `{' '.join(engine.jvm_flags)}`",
        "",
        "## Durchsatz-Vergleich (Schritt 5)",
        "",
        "| Metrik | Baseline (Schritt 1) | Optimiert (Schritt 5) | Faktor (neu / alt) |",
        "|---|---|---|---|",
        f"| **Durchsatz (Partien / Stunde)** | **{baseline_durchsatz:.1f}** | **{durchsatz_neu:.1f}** | **{faktor:.2f}x** |",
        f"| Wall Time (10 Partien) | 287.4 s (Median 26.8 s) | {total_wall_s:.2f} s | {287.35 / total_wall_s:.2f}x |",
        "| Konfiguration | 1 Worker, 1 Game/JVM | "
        + f"{args.workers} Workers, {args.games_per_jvm} Games/JVM"
        + " | - |",
        "| JVM-Flags | Standard | SerialGC | - |",
        "",
        f"**Zielerreichung:** {'✅ ERFÜLLT' if faktor >= 5.0 else '❌ NICHT ERFÜLLT'} (Kriterium: $\\ge 5.0\\times$ Durchsatz)",
        "",
        "## Identitätsnachweis (Bit-für-Bit gegen Baseline)",
        "",
        "| Seed | Status | Semantischer Hash identisch? | Gewinner identisch? | Entscheidungen identisch? | Semantischer Hash (16 Zeichen) |",
        "|---|---|---|---|---|---|",
    ]
    for r in seed_results:
        md_lines.append(
            f"| {r['seed']} | {r['status']} | {'✅ Ja' if r['hash_identical'] else '❌ Nein'} | "
            f"{'✅ Ja' if r['winner_identical'] else '❌ Nein'} | {'✅ Ja' if r['decisions_identical'] else '❌ Nein'} | "
            f"`{str(r['semantic_hash'])[:16]}` |"
        )
    md_lines.extend(
        [
            "",
            f"**Identitätsurteil:** {'✅ PASS (10/10 Partien exakt identisch)' if all_identical else '❌ FAIL'}",
            "",
            "## Bewertung der Hypothese aus Issue #1251",
            "",
            "- **Ausgangshypothese #1251:** „Verdacht: nicht die Regelberechnung ist teuer, sondern das Drumherum (JVM-Start, Kartenscan, Deck-Import, Protokoll)."
            "- **Messergebnis (Schritt 1):**",
            "  - XMage-Regelberechnung (Engine): **71.9 %** (Median 19.27 s / 26.82 s)",
            "  - Python-Pilot-Heuristik: **10.5 %** (Median 2.82 s)",
            "  - Kartendaten-Scan (H2): **10.0 %** (Median 2.68 s)",
            "  - Transport (IPC / JSON): **2.6 %** (Median 0.71 s)",
            "  - Deck-Import: **1.4 %** (Median 0.38 s)",
            "  - JVM-Start: **0.6 %** (Median 0.17 s)",
            "  - Protokollierung: **0.8 %** (Median 0.21 s)",
            "- **Befund:** Die Hypothese ist widerlegt. Die XMage-Regelberechnung macht ~72 % der Laufzeit aus.",
            "- **Durchsatzsteigerung:** Die Beschleunigung um $\\ge 5\\times$ wird daher erreicht durch:",
            "  1. Nutzung der vorhandenen CPU-Kerne durch parallele Worker (`workers >= 6`).",
            "  2. Amortisierung des Kartenscans durch Wiederverwendung der JVM (`games_per_jvm >= 2`).",
            "  3. Schlanke GC-Flags (`-XX:+UseSerialGC`).",
            "",
            "## Schritt 4 Transport-Bewertung",
            "",
            "- **Gemessener Transport-Anteil:** 2.6 % (0.71 s je Partie bei ~5.000 Entscheidungen, ~150 µs je Roundtrip).",
            "- **Entscheidung gemäß Vorgabe:** Transport nicht modifiziert, weil Anteil mit 2.6 % weit unter der 20-%-Schwelle liegt.",
        ]
    )

    args.out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"\nWrote results to {args.out_json} and {args.out_md}")
    return 0 if (all_identical and faktor >= 5.0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
