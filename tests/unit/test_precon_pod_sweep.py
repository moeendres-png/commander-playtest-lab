"""The precon sweep seats four different decks per pod and names each failure's family.

The first sweep (#920) repeated one deck on all four seats; the full-game validator rejects
that before a JVM starts, so it recorded 195 identical failures and played no game.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "precon_pod_sweep", ROOT / "scripts/precon_pod_sweep.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decks(count: int) -> list[str]:
    return [f"deck_{i:03d}" for i in range(count)]


@pytest.mark.parametrize("count", [4, 5, 6, 7, 8, 173, 195])
def test_every_pod_has_distinct_decks_and_every_deck_is_covered(count: int) -> None:
    pods = _module().plan_pods(_decks(count))
    assert all(len(pod) == 4 and len(set(pod)) == 4 for pod in pods)
    assert {deck for pod in pods for deck in pod} == set(_decks(count))
    assert len(pods) == -(-count // 4)


def test_the_plan_is_deterministic_and_the_seed_changes_it() -> None:
    module = _module()
    assert module.plan_pods(_decks(40), seed=3) == module.plan_pods(_decks(40), seed=3)
    assert module.plan_pods(_decks(40), seed=3) != module.plan_pods(_decks(40), seed=4)


def test_too_few_decks_for_distinct_seats_is_refused() -> None:
    with pytest.raises(ValueError):
        _module().plan_pods(_decks(3))


def test_a_failure_is_named_by_the_bridge_error_code() -> None:
    family = _module().failure_family
    assert (
        family("FullGameConformanceError: XMAGE_ACTION_EXECUTION_FAILED: activation")
        == "XMAGE_ACTION_EXECUTION_FAILED"
    )
    assert family("BridgeError: DECISION_ADVANCE_TIMEOUT after 75s") == "DECISION_ADVANCE_TIMEOUT"
    assert family("ValueError: no code in here") == "ValueError"
    assert family(None) == "NONE"


def test_only_decks_that_import_cleanly_are_selected(tmp_path: Path) -> None:
    report = tmp_path / "imports.json"
    rows = [{"deck": "b", "status": "OK"}, {"deck": "a", "status": "FAILED"}]
    report.write_text(json.dumps({"results": rows}), encoding="utf-8")
    assert _module().importable_decks(report) == ["b"]


def test_the_summary_counts_failures_by_family() -> None:
    pods = [
        {"status": "ok"},
        {"status": "failed", "error": "X: COST_FAILED boom"},
        {"status": "failed", "error": "Y: COST_FAILED again"},
    ]
    assert _module().summarize(pods) == {
        "pods": 3,
        "pods_ok": 1,
        "pods_failed": 2,
        "families": {"COST_FAILED": 2},
    }
