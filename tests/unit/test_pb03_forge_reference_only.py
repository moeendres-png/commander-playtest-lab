"""M15: Forge is a bounded reference on the PB-03 path (ADR
docs/engine_strategy_20261009, Owner decision 2).

* a pull_request run never executes Forge: every Forge step is gated on
  ``FORGE_REFERENCE``, which only a workflow_dispatch input can set;
* the runner executes XMage alone unless the reference run was requested;
* without the reference run the Forge column must be the marked carry-forward,
  never a column presented as fresh.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/pb03-runtime-qualification.yml"
FORGE_STEPS = (
    "Checkout admitted Forge bridge/materialization source",
    "Verify immutable Forge dual-source binding",
    "Build and warm admitted Forge exact source",
)


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps() -> dict[str, dict]:
    return {step.get("name", ""): step for step in _workflow()["jobs"]["pb03-runtime"]["steps"]}


def test_the_reference_flag_is_dispatch_only_and_off_by_default() -> None:
    workflow = _workflow()
    triggers = workflow.get("on") or workflow.get(True)
    forge_input = triggers["workflow_dispatch"]["inputs"]["forge_reference"]
    assert forge_input["type"] == "boolean"
    assert forge_input["default"] is False
    expression = workflow["env"]["FORGE_REFERENCE"]
    assert "github.event_name == 'workflow_dispatch'" in expression
    assert "inputs.forge_reference" in expression


def test_every_forge_step_is_gated_on_the_reference_flag() -> None:
    steps = _steps()
    for name in FORGE_STEPS:
        assert steps[name]["if"] == "env.FORGE_REFERENCE == 'true'", name
    ungated = [
        name
        for name, step in steps.items()
        if "forge" in name.lower() and name not in FORGE_STEPS and "if" not in step
    ]
    # Only the identity resolution (a config read) and the runner, which picks
    # its candidates from the flag, stay unconditional; the workspace binding
    # exports FORGE_WORKSPACE only on a reference run.
    assert ungated == [
        "Resolve current XMage and Forge dual identities",
        "Execute authoritative current-boundary runner (XMage; Forge on demand)",
    ], ungated
    binding = steps["Bind external candidate workspaces without polluting Lab identity"]["run"]
    assert 'if test "$FORGE_REFERENCE" = true; then' in binding


def test_the_runner_executes_xmage_alone_without_the_reference_run() -> None:
    run = _steps()["Execute authoritative current-boundary runner (XMage; Forge on demand)"]["run"]
    assert "--candidate xmage" in run
    assert run.index('if test "$FORGE_REFERENCE" = true; then') < run.index("--candidate all")


def test_an_unrun_forge_column_must_be_the_marked_carry_forward() -> None:
    run = _steps()["Assert R-3/R-4 current-boundary invariants"]["run"]
    assert 'expected = {"xmage": os.environ["XMAGE_COMMIT"]}' in run
    assert 'assert forge_full107.get("carried_forward")' in run
    assert 'forge_full107["evidence_class"] == "CARRIED_FORWARD_NOT_REEXECUTED"' in run
    assert '!= "FRESH_CURRENT_BOUNDARY_EXECUTION"' in run
