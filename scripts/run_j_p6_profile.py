from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import resource
import sqlite3
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from commander_lab.models import (
    CardAblationInput,
    CommanderDenialInput,
    CreateReportInput,
    GoldfishInput,
    LocalSearchInput,
    MatchupBatchInput,
    PackageAblationInput,
    PairedVariantInput,
    PilotStrength,
    SensitivityInput,
    VariantSwap,
)
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "j_p6"
PRIMARY = (
    "opponent/morcant-elves",
    "opponent/doom-prevails-precon",
    "opponent/cosmic-spiderman-midbudget",
)
POD = ("korvold/current",) + PRIMARY


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _rss_kib() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def _measure(name: str, fn: Callable[[], Any], repetitions: int = 3) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    signatures: list[str] = []
    for repetition in range(repetitions):
        gc.collect()
        rss_before = _rss_kib()
        cpu_before = time.process_time()
        wall_before = time.perf_counter()
        status = "passed"
        error = None
        value: Any = None
        try:
            value = fn()
        except Exception as exc:  # benchmark records failures instead of hiding them
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
        wall = time.perf_counter() - wall_before
        cpu = time.process_time() - cpu_before
        rss_after = _rss_kib()
        if value is not None:
            if hasattr(value, "model_dump"):
                payload = value.model_dump(mode="json")
            else:
                payload = value
            try:
                signatures.append(
                    __import__("hashlib").sha256(
                        json.dumps(payload, sort_keys=True, default=str).encode()
                    ).hexdigest()
                )
            except TypeError:
                signatures.append(type(value).__name__)
        rows.append(
            {
                "repetition": repetition,
                "status": status,
                "error": error,
                "wall_seconds": wall,
                "cpu_seconds": cpu,
                "rss_before_kib": rss_before,
                "rss_after_kib": rss_after,
            }
        )
    passed = [row for row in rows if row["status"] == "passed"]
    return {
        "name": name,
        "status": "passed" if len(passed) == repetitions else "failed",
        "repetitions": rows,
        "median_wall_seconds": statistics.median(row["wall_seconds"] for row in passed)
        if passed
        else None,
        "median_cpu_seconds": statistics.median(row["cpu_seconds"] for row in passed)
        if passed
        else None,
        "max_rss_kib": max((row["rss_after_kib"] for row in passed), default=None),
        "deterministic_signature_count": len(set(signatures)) if signatures else None,
    }


def _serialization_benchmark(service: CommanderToolService) -> dict[str, int]:
    deck = service._deck("korvold/current")
    payload = deck.model_dump(mode="json")
    total = 0
    for _ in range(1000):
        total += len(json.dumps(payload, sort_keys=True))
    return {"serialized_bytes": total}


def _lookup_benchmark(service: CommanderToolService) -> dict[str, int]:
    deck = service._deck("korvold/current")
    lookup = {card.oracle_name: card for card in deck.cards}
    names = tuple(lookup)
    hits = 0
    for i in range(10000):
        if lookup.get(names[i % len(names)]) is not None:
            hits += 1
    return {"lookups": 10000, "hits": hits}


def _sqlite_benchmark() -> dict[str, int]:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "profile.sqlite"
    target.unlink(missing_ok=True)
    con = sqlite3.connect(target)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE measurements(id INTEGER PRIMARY KEY, value REAL NOT NULL)")
        con.executemany(
            "INSERT INTO measurements(value) VALUES (?)", [(float(i),) for i in range(1000)]
        )
        con.commit()
        count = int(con.execute("SELECT COUNT(*) FROM measurements").fetchone()[0])
        total = int(con.execute("SELECT SUM(value) FROM measurements").fetchone()[0])
        return {"rows": count, "sum": total}
    finally:
        con.close()
        for suffix in ("", "-wal", "-shm"):
            (Path(str(target) + suffix)).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--output", default="J_P6_PERFORMANCE_PROFILE.json")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    measurements: list[dict[str, Any]] = []
    measurements.append(_measure("service_initialization", lambda: CommanderToolService(ROOT), 5))
    service = CommanderToolService(ROOT)

    measurements.append(
        _measure(
            "goldfish_50_workers_1",
            lambda: service.run_goldfish(
                GoldfishInput(deck_id="korvold/current", iterations=50, workers=1, seed=20260811)
            ),
        )
    )
    for iterations, workers in ((32, 1), (32, 2), (64, 1), (64, 2)):
        measurements.append(
            _measure(
                f"matchup_{iterations}_workers_{workers}",
                lambda iterations=iterations, workers=workers: service.run_matchup_batch(
                    MatchupBatchInput(
                        deck_ids=POD,
                        iterations=iterations,
                        workers=workers,
                        seed=20260811,
                    )
                ),
            )
        )

    measurements.append(
        _measure(
            "paired_comparison_8",
            lambda: service.compare_variants_paired(
                PairedVariantInput(
                    deck_id="korvold/current",
                    swaps=(
                        VariantSwap(
                            remove="Goblin Bombardment",
                            add_candidate_id="korvold/god-eternal-bontu",
                        ),
                    ),
                    opponent_deck_ids=PRIMARY,
                    iterations=8,
                    workers=1,
                    seed=20260811,
                )
            ),
        )
    )
    measurements.append(
        _measure(
            "card_ablation_4",
            lambda: service.run_card_ablation(
                CardAblationInput(
                    deck_id="korvold/current",
                    card_name="Mirkwood Bats",
                    opponent_deck_ids=PRIMARY,
                    iterations=4,
                    seed=20260811,
                )
            ),
        )
    )
    measurements.append(
        _measure(
            "package_ablation_4",
            lambda: service.run_package_ablation(
                PackageAblationInput(
                    deck_id="korvold/current",
                    card_names=("Mayhem Devil", "Mirkwood Bats"),
                    opponent_deck_ids=PRIMARY,
                    iterations=4,
                    seed=20260812,
                )
            ),
        )
    )
    measurements.append(
        _measure(
            "commander_denial_4",
            lambda: service.run_commander_denial(
                CommanderDenialInput(
                    deck_id="korvold/current",
                    opponent_deck_ids=PRIMARY,
                    iterations=4,
                    seed=20260813,
                )
            ),
        )
    )
    measurements.append(
        _measure(
            "sensitivity_2_decks_1_seed_1_strength",
            lambda: service.run_sensitivity(
                SensitivityInput(
                    deck_ids=POD,
                    seeds=(20260811,),
                    pilot_strengths=(PilotStrength.STRONG,),
                    iterations=2,
                    workers=1,
                )
            ),
        )
    )
    measurements.append(
        _measure(
            "local_search_bounded",
            lambda: service.run_local_search(
                LocalSearchInput(
                    deck_id="korvold/current",
                    candidate_ids=("korvold/god-eternal-bontu",),
                    max_steps=1,
                    cuts_per_step=2,
                    opponent_deck_ids=PRIMARY,
                    iterations=1,
                    seed=20260814,
                )
            ),
        )
    )

    paired = service.compare_variants_paired(
        PairedVariantInput(
            deck_id="korvold/current",
            swaps=(
                VariantSwap(
                    remove="Goblin Bombardment",
                    add_candidate_id="korvold/god-eternal-bontu",
                ),
            ),
            opponent_deck_ids=PRIMARY,
            iterations=1,
            workers=1,
            seed=20260815,
        )
    )
    measurements.append(
        _measure(
            "report_generation",
            lambda: service.create_report(
                CreateReportInput(
                    title="J-P6 benchmark report",
                    tool_responses=(paired.model_dump(mode="json"),),
                    output_name="j_p6_benchmark_report.md",
                )
            ),
        )
    )
    measurements.append(_measure("serialization_1000", lambda: _serialization_benchmark(service)))
    measurements.append(_measure("card_lookup_10000", lambda: _lookup_benchmark(service)))
    measurements.append(_measure("sqlite_write_read_1000", _sqlite_benchmark))

    payload = {
        "schema_version": "1.0.0",
        "label": args.label,
        "software_commit": _git("rev-parse", "HEAD"),
        "software_tree": _git("rev-parse", "HEAD^{tree}"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "runner_name": os.environ.get("RUNNER_NAME"),
        "runner_os": os.environ.get("RUNNER_OS"),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
        "truth_boundary": "technical timings only; simulation outputs are structural_model_estimates",
        "cache_status": "no production result cache identified; cache_hit_rate not_applicable",
        "measurements": measurements,
    }
    target = OUT / args.output
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
