from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path

from commander_lab.mcp.server import CommanderMcpServer
from commander_lab.models import (
    CompareMulliganPoliciesInput,
    CreateReportInput,
    GoldfishInput,
    MatchupBatchInput,
    PairedVariantInput,
    RunEnsembleMatchupsInput,
    VariantSwap,
)
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase12_19"
OUT.mkdir(parents=True, exist_ok=True)


def timed(name: str, fn):
    start = time.perf_counter()
    try:
        value = fn()
        status = "passed"
        error = None
    except Exception as exc:  # benchmark must record, not hide, a failed operation
        value = None
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - start
    return {
        "name": name,
        "execution_status": status,
        "seconds": round(elapsed, 6),
        "error": error,
    }, value


rows: list[dict[str, object]] = []

row, service = timed("deck_import_and_service_initialization", lambda: CommanderToolService(ROOT))
rows.append(row)
if service is None:
    raise SystemExit("service initialization failed")

pod = ("korvold/current", "synthetic/aggro", "synthetic/control", "synthetic/engine")
# High-volume throughput is measured with one-seat structural runs to avoid making
# event-log serialization dominate the benchmark. Four-player worker scaling is
# measured separately below.
for iterations in (1, 100, 1000):
    row, _ = timed(
        f"structural_goldfish_{iterations}_games_workers_1",
        lambda iterations=iterations: service.run_goldfish(
            GoldfishInput(
                deck_id="korvold/current", iterations=iterations, workers=1, seed=20260807
            )
        ),
    )
    rows.append(row)
for workers in (1, 2):
    row, _ = timed(
        f"four_player_50_games_workers_{workers}",
        lambda workers=workers: service.run_matchup_batch(
            MatchupBatchInput(deck_ids=pod, iterations=50, workers=workers, seed=20260807)
        ),
    )
    rows.append(row)

row, _ = timed(
    "mulligan_sampling_500x2",
    lambda: service.compare_mulligan_policies(
        CompareMulliganPoliciesInput(
            deck_id="korvold/current",
            policies=("conservative", "commander_oriented"),
            samples=500,
            followup_samples=0,
            seed=20260807,
        )
    ),
)
rows.append(row)

row, _ = timed(
    "opponent_ensemble_evaluation",
    lambda: service.run_ensemble_matchups(
        RunEnsembleMatchupsInput(
            deck_id="korvold/current",
            ensemble_id="cosmic-spiderman-ensemble-v1",
            seed=20260807,
        )
    ),
)
rows.append(row)

row, paired = timed(
    "paired_variant_comparison_50",
    lambda: service.compare_variants_paired(
        PairedVariantInput(
            deck_id="korvold/current",
            swaps=(
                VariantSwap(remove="Scouring Swarm", add_candidate_id="korvold/idol-of-oblivion"),
            ),
            iterations=50,
            workers=1,
            seed=20260807,
        )
    ),
)
rows.append(row)

row, _ = timed(
    "report_generation",
    lambda: service.create_report(
        CreateReportInput(
            title="Phase 12.19 benchmark report",
            tool_responses=(paired.model_dump(mode="json") if paired else {"status": "failed"},),
            output_name="phase12_19_benchmark_report.md",
        )
    ),
)
rows.append(row)


def sqlite_benchmark() -> dict[str, int]:
    target = OUT / "benchmark.sqlite"
    if target.exists():
        target.unlink()
    con = sqlite3.connect(target)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE measurements(id INTEGER PRIMARY KEY, value REAL NOT NULL)")
        con.executemany(
            "INSERT INTO measurements(value) VALUES (?)", [(float(i),) for i in range(1000)]
        )
        con.commit()
        count = con.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        total = con.execute("SELECT SUM(value) FROM measurements").fetchone()[0]
        return {"rows": int(count), "sum": int(total)}
    finally:
        con.close()


row, _ = timed("sqlite_write_read_1000", sqlite_benchmark)
rows.append(row)

server = CommanderMcpServer(ROOT)
row, _ = timed(
    "mcp_initialize_in_process",
    lambda: server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "phase12.19", "version": "1"},
            },
        }
    ),
)
rows.append(row)
row, _ = timed(
    "mcp_tools_list_in_process",
    lambda: server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
)
rows.append(row)

# External providers were really probed in phase 12.13 and are unavailable in this runtime.
rows.extend(
    [
        {
            "name": "xmage_run",
            "execution_status": "blocked",
            "seconds": None,
            "error": "No verified source/binary; GitHub DNS and build dependencies unavailable.",
        },
        {
            "name": "forge_run",
            "execution_status": "blocked",
            "seconds": None,
            "error": "No verified source/binary; GitHub DNS and build dependencies unavailable.",
        },
        {
            "name": "parquet_roundtrip",
            "execution_status": "not_run",
            "seconds": None,
            "error": "Parquet is not an active project feature; pyarrow/fastparquet not required.",
        },
        {
            "name": "counterfactual_replay",
            "execution_status": "not_run",
            "seconds": None,
            "error": "No canonical replay fixture selected for this performance run; functionality remains covered by tests.",
        },
        {
            "name": "decision_diagnostics",
            "execution_status": "not_run",
            "seconds": None,
            "error": "No canonical diagnostic dataset selected for this performance run; functionality remains covered by tests.",
        },
    ]
)

payload = {
    "schema_version": "1.0.0",
    "generated_at": "2026-08-07",
    "environment_note": "Single-container measurements; not transferable performance guarantees.",
    "semantic_change_allowed": False,
    "measurements": rows,
}
(OUT / "PHASE12_19_PERFORMANCE.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)

lines = [
    "# Phase 12.19 Performance Report",
    "",
    "Measurements are local technical timings, not cross-machine guarantees.",
    "",
    "| Operation | Status | Seconds | Note |",
    "|---|---|---:|---|",
]
for item in rows:
    seconds = "—" if item["seconds"] is None else f"{item['seconds']:.6f}"
    note = str(item["error"] or "")
    lines.append(f"| `{item['name']}` | `{item['execution_status']}` | {seconds} | {note} |")
(OUT / "PHASE12_19_PERFORMANCE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Remove benchmark run artifacts; the summarized benchmark evidence remains.
for child in (ROOT / "data/runs/tool_runs").glob("*"):
    if child.is_dir():
        shutil.rmtree(child)
    else:
        child.unlink()
