"""#662 SLOT-06: every freeze proof class is executed by the PB-03 XMage native suite.

The freeze-record assembler credits a capability or a lane-surface gate only from an
executed in-epoch native receipt. A proof class that PB-03 never runs can never be
credited, so the epoch would silently miss it. This keeps the two lists in step.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary.freeze_record import (
    AF01_PROOF,
    CAPABILITY_PROOF,
    LANE_SURFACE_COMPONENTS,
    TEST_SOURCE_ROOT,
)

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"
PROOF_CLASSES = sorted(
    {
        name
        for proofs in (*CAPABILITY_PROOF.values(), *LANE_SURFACE_COMPONENTS.values())
        for name in proofs
        if name != AF01_PROOF
    }
)


def _runner_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("FORGE_WORKSPACE", str(REPO))
    monkeypatch.delenv("CURRENT_BOUNDARY_EVIDENCE_EPOCH", raising=False)
    spec = importlib.util.spec_from_file_location("pb03_freeze_proof_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", PROOF_CLASSES)
def test_proof_class_is_in_the_pb03_xmage_native_suite(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    module = _runner_module(monkeypatch)
    native = {
        cls for group in module.NATIVE_SUITE_BINDING["xmage"]["classes"].values() for cls in group
    }
    assert name in native, f"{name} is a freeze proof but PB-03 never executes it"
    assert (REPO / f"{TEST_SOURCE_ROOT}{name}.java").is_file(), name
