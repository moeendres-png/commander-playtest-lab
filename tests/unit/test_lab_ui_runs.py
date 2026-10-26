"""Tests fuer die Simulations-Warteschlange der Lab UI.

Hermetisch: Der Treiber wird durch ein Stub-Skript ersetzt (keine JVM,
keine echten Spiele). Der echte Treiber wird im Live-Smoke ueber
--plan-only geprueft, nicht hier.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from commander_lab.api.lab_ui import runs as runs_mod


def _spec(**overrides: object) -> runs_mod.RunSpec:
    base: dict[str, object] = {
        "baseline": "data/decks/rogshai_current.json",
        "opponents": ["data/opponents/hosts_of_mordor_precon.json"],
        "swaps": ["Sol Ring=>Mind Stone"],
    }
    base.update(overrides)
    return runs_mod.RunSpec.from_dict(base)


def test_validation_rejects_missing_variant_and_bad_seeds(tmp_path: Path) -> None:
    spec = _spec(swaps=[])
    errors = runs_mod.validate_spec(spec, tmp_path)
    assert any("variant" in e for e in errors)
    errors = runs_mod.validate_spec(_spec(seeds="abc"), tmp_path)
    assert any("Seeds" in e for e in errors)
    errors = runs_mod.validate_spec(_spec(opponents=[]), tmp_path)
    assert any("Gegner" in e for e in errors)
    errors = runs_mod.validate_spec(
        _spec(opponents=["a.json", "b.json", "c.json", "d.json"]), tmp_path
    )
    assert any("Gegner" in e for e in errors)


def test_validation_rejects_paths_outside_data(tmp_path: Path) -> None:
    errors = runs_mod.validate_spec(_spec(baseline="../etc/passwd"), tmp_path)
    assert errors
    errors = runs_mod.validate_spec(_spec(baseline="data/collections/secret.json"), tmp_path)
    assert any("Sammlung" in e for e in errors)
    errors = runs_mod.validate_spec(_spec(workers=17), tmp_path)
    assert any("workers" in e for e in errors)


def test_argv_building_and_planned_games(tmp_path: Path) -> None:
    spec = _spec(
        opponents=[
            "data/opponents/hosts_of_mordor_precon.json",
            "data/opponents/lorehold_spirit_precon.json",
        ],
        seeds="1-2,7",
        workers=2,
        stop_when_decided=True,
        look_every=5,
        comparison_id="c1",
        retry_failed=True,
    )
    argv = runs_mod.build_argv(spec, tmp_path / "driver.py", tmp_path / "out")
    assert argv[0].endswith("python") or "python" in argv[0]
    assert "--baseline" in argv and "--opponent" in argv
    assert argv.count("--opponent") == 2
    assert "--swap" in argv and "--workers" in argv and "2" in argv
    assert "--stop-when-decided" in argv and "--look-every" in argv
    assert "--comparison-id" in argv and "--retry-failed" in argv
    assert runs_mod.expand_seeds("1-2,7") == [1, 2, 7]
    # 3 Seeds x 4 Sitze x 2 Contender (Baseline + Swap) = 24
    assert runs_mod.planned_games(spec) == 24
    assert runs_mod.planned_games(_spec(no_rotate=True, seeds="1")) == 2


def _stub_script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_job_lifecycle_with_stub_driver(tmp_path: Path) -> None:
    stub = _stub_script(
        tmp_path / "stub.py",
        "import sys, pathlib\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])\n"
        "(out / 'games').mkdir(parents=True, exist_ok=True)\n"
        "(out / 'games' / 'g1.json').write_text('{}')\n"
        "(out / 'games' / 'g2.json').write_text('{}')\n"
        "(out / 'COMPARISON_REPORT.json').write_text('{}')\n",
    )
    manager = runs_mod.JobManager(tmp_path, tmp_path / "runs", driver_script=stub)
    job = manager.submit(_spec())
    deadline = time.time() + 10
    while job.status == "running" and time.time() < deadline:
        time.sleep(0.1)
    assert job.status == "completed"
    progress = job.progress()
    assert progress["done"] == 2
    assert progress["report_ready"] is True
    assert manager.get(job.id) is job
    assert len(manager.list_jobs()) == 1


def test_cancel_kills_sleeping_driver(tmp_path: Path) -> None:
    stub = _stub_script(tmp_path / "stub.py", "import time\ntime.sleep(60)\n")
    manager = runs_mod.JobManager(tmp_path, tmp_path / "runs", driver_script=stub)
    job = manager.submit(_spec())
    time.sleep(0.5)
    assert manager.cancel(job.id) is True
    deadline = time.time() + 10
    while job.process is not None and time.time() < deadline:
        time.sleep(0.1)
    assert job.status == "cancelled"
    assert manager.cancel(job.id) is False
    assert manager.cancel("fehlt") is False


def test_plan_only_uses_stub_output(tmp_path: Path) -> None:
    stub = _stub_script(tmp_path / "stub.py", "print('PLAN OK')\n")
    manager = runs_mod.JobManager(tmp_path, tmp_path / "runs", driver_script=stub)
    assert manager.plan_only(_spec()) == "PLAN OK\n"
    with pytest.raises(ValueError):
        manager.plan_only(_spec(swaps=[]))
