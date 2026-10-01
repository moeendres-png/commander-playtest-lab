"""F1: the product's real process-pool path is exercised, not only the pytest thread path.

`run_structural_batch` switches to a ThreadPoolExecutor whenever
PYTEST_CURRENT_TEST is set, because a spawned pool can block on pytest's
captured pipes. So in-suite tests never reach the ProcessPoolExecutor that
normal product runs use. This test runs the batch in a fresh interpreter
without PYTEST_CURRENT_TEST and with output to files instead of pipes, proves
that the process pool was actually used, and requires its results to match
the serial run exactly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_SCRIPT = textwrap.dedent(
    """
    import json, sys
    from pathlib import Path
    import concurrent.futures
    import commander_lab.engine.structural.batch as batch
    from commander_lab.engine.structural import load_project_structural_decks
    from commander_lab.models import StructuralAbortLimits, StructuralBatchConfig

    created = []

    class CountingPool(concurrent.futures.ProcessPoolExecutor):
        def __init__(self, *args, **kwargs):
            created.append(kwargs.get("mp_context").get_start_method())
            super().__init__(*args, **kwargs)

    batch.ProcessPoolExecutor = CountingPool

    def main():
        root = Path(sys.argv[1])
        decks = load_project_structural_decks(
            root, include_synthetic_fixtures=True, include_current_opponents=True
        )
        common = dict(
            run_id="process-pool",
            seed=20260930,
            iterations=24,
            deck_ids=("rogshai/current", "kaervek/current", "synthetic/aggro"),
            limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
        )
        def key(result):
            return [
                [m.seed, list(m.placements), list(m.winner_ids), m.turns, m.log_sha256, m.end_reason]
                for m in result.match_results
            ]
        serial = batch.run_structural_batch(StructuralBatchConfig(**common, workers=1), decks)
        pooled = batch.run_structural_batch(StructuralBatchConfig(**common, workers=2), decks)
        Path(sys.argv[2]).write_text(json.dumps({
            "pools": created,
            "serial": key(serial),
            "pooled": key(pooled),
            "aggregate_equal": serial.aggregate == pooled.aggregate,
        }))

    if __name__ == "__main__":
        main()
    """
)


@pytest.mark.integration
def test_the_process_pool_path_matches_the_serial_run(repo_root: Path, tmp_path: Path) -> None:
    script = tmp_path / "process_pool_probe.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    out = tmp_path / "result.json"
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "src"), env.get("PYTHONPATH", "")]).rstrip(
        os.pathsep
    )
    with (tmp_path / "stdout.log").open("w") as stdout, (tmp_path / "stderr.log").open("w") as err:
        completed = subprocess.run(
            [sys.executable, str(script), str(repo_root), str(out)],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=err,
            timeout=600,
            check=False,
        )
    assert completed.returncode == 0, (tmp_path / "stderr.log").read_text()[-4000:]
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["pools"] == ["spawn"], "the product process pool (spawn) was not used"
    assert result["serial"] == result["pooled"]
    assert len(result["serial"]) == 24
    assert result["aggregate_equal"] is True
