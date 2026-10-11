"""#691: one authority for the capability set that judges engine health.

``commander_lab.freeze_readiness.REQUIRED_CAPABILITIES`` (11 flags) is the freeze-eligibility
capability set. Three consumers decide or gate on "required/missing capabilities" for engine
health, and each is bound to that one authority by a different mechanism:

* ``scripts/derive_rules_engines_capabilities.py`` imports the list directly and derives BOTH
  lists in ``config/rules_engines.json`` from it. The manifest's missing lists therefore cannot
  name a capability the freeze set does not name (ruling SLOT-06 §(b)2; the manifest is never
  hand-edited).
* the H4 workflow step "engine-verify outcome vs manifest capability truth" gates on the derived
  ``current_runtime.required_missing_capabilities`` field and hard-codes no capability name of its
  own, so its required set IS the derived set by construction. H4 keeps expecting
  ``engine-verify=degraded`` while that runtime list is non-empty.
* ``EngineProcessManager.healthcheck`` -- the code behind ``commander_lab.cli.app engine-verify``
  -- requires ``tuple(REQUIRED_CAPABILITIES)`` from the handshake (``EngineCapabilityHandshake``,
  which carries every one of the 11 flags). Until #691 was closed it used its own six-flag tuple,
  a strict subset missing five flags; that tuple is gone, and this module goes red if any literal
  capability tuple returns.

All three consumers therefore judge engine health by the same 11 flags.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from commander_lab.freeze_readiness import REQUIRED_CAPABILITIES
from commander_lab.models import EngineCapabilityHandshake

REPO_ROOT = Path(__file__).resolve().parents[2]
DERIVE_SCRIPT = REPO_ROOT / "scripts" / "derive_rules_engines_capabilities.py"
H4_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "h4-docker-materialization.yml"
PROCESS_MANAGER = REPO_ROOT / "src" / "commander_lab" / "engine" / "process_manager.py"
MANIFEST = REPO_ROOT / "config" / "rules_engines.json"

H4_STEP_NAME = "engine-verify outcome vs manifest capability truth (recorded, consistency-gated)"


def _load_derive_module(source_path: Path | None = None) -> ModuleType:
    """Load the derivation script. ``source_path`` defaults to the shipped file at call time."""
    spec = importlib.util.spec_from_file_location(
        "derive_rules_engines_capabilities", source_path or DERIVE_SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _healthcheck_node(source: str) -> ast.FunctionDef:
    manager = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef) and node.name == "EngineProcessManager"
    )
    return next(
        node
        for node in manager.body
        if isinstance(node, ast.FunctionDef) and node.name == "healthcheck"
    )


def _required_assignments(healthcheck: ast.FunctionDef) -> list[ast.expr]:
    return [
        node.value
        for node in ast.walk(healthcheck)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "required" for t in node.targets)
    ]


def _h4_engine_verify_step() -> str:
    workflow = yaml.safe_load(H4_WORKFLOW.read_text(encoding="utf-8"))
    steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if step.get("name") == H4_STEP_NAME
    ]
    assert len(steps) == 1, f"expected one H4 {H4_STEP_NAME!r} step, found {len(steps)}"
    return str(steps[0]["run"])


def test_derivation_script_takes_the_required_capability_set_from_freeze_readiness() -> None:
    """The manifest's two derived lists are reachable only through REQUIRED_CAPABILITIES."""
    actual = list(_load_derive_module().REQUIRED_CAPABILITIES)
    expected = list(REQUIRED_CAPABILITIES)
    assert actual == expected, (
        f"derivation script required set diverges: "
        f"only-in-script={sorted(set(actual) - set(expected))} "
        f"only-in-freeze-readiness={sorted(set(expected) - set(actual))}"
    )


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("primary_engine", "missing_required_capabilities"),
        ("current_runtime", "required_missing_capabilities"),
    ],
)
def test_manifest_missing_lists_name_only_required_capabilities(section: str, field: str) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = manifest[section][field]
    assert set(missing) <= set(REQUIRED_CAPABILITIES)
    assert len(missing) == len(set(missing))


def test_h4_step_gates_on_the_derived_runtime_missing_field() -> None:
    """H4 inherits the required set from the derived field and hard-codes no capability name."""
    run = _h4_engine_verify_step()
    assert 'manifest["current_runtime"].get("required_missing_capabilities", [])' in run
    # degraded iff the derived runtime list is non-empty; exit code follows the same conditional.
    assert 'expected = "degraded" if missing else "healthy"' in run
    assert 'rc == (0 if expected == "healthy" else 1)' in run
    leaked = sorted(name for name in REQUIRED_CAPABILITIES if name in run)
    assert leaked == [], f"H4 hard-codes capability names {leaked}; it must read the derived field"


def test_engine_verify_requires_exactly_the_freeze_readiness_set() -> None:
    """engine-verify reads the one authority; no literal capability tuple may come back."""
    source = PROCESS_MANAGER.read_text(encoding="utf-8")
    assert "from commander_lab.freeze_readiness import REQUIRED_CAPABILITIES" in source
    assignments = _required_assignments(_healthcheck_node(source))
    assert len(assignments) == 1, f"expected one `required` assignment, found {len(assignments)}"
    assert ast.unparse(assignments[0]) == "tuple(REQUIRED_CAPABILITIES)"
    literals = [
        node
        for node in ast.walk(_healthcheck_node(source))
        if isinstance(node, ast.Constant) and node.value in REQUIRED_CAPABILITIES
    ]
    assert literals == [], "healthcheck restates capability names instead of the authority"


def test_every_required_capability_resolves_on_the_handshake_model() -> None:
    """The model engine-verify reads carries all 11 flags, so none can raise or be skipped."""
    capabilities = EngineCapabilityHandshake()
    assert [name for name in REQUIRED_CAPABILITIES if capabilities.supports(name)] == []
    full = EngineCapabilityHandshake.model_validate(
        {name: True for name in REQUIRED_CAPABILITIES} | {"runtime_kind": "external_rules_engine"}
    )
    assert all(full.supports(name) for name in REQUIRED_CAPABILITIES)


@pytest.mark.parametrize("missing", [None, *sorted(REQUIRED_CAPABILITIES)])
def test_engine_verify_degrades_when_any_required_capability_is_missing(
    tmp_path: Path, missing: str | None
) -> None:
    """Each of the 11 flags is load-bearing: one false flag makes engine-verify degraded.

    ``missing=None`` is the positive control: the same harness with all 11 true is healthy.
    """
    from commander_lab.engine.process_manager import (
        EngineProcessManager,
        load_engine_runtime_config,
    )
    from commander_lab.models import EngineProcessStatus

    caps: dict[str, object] = {name: True for name in REQUIRED_CAPABILITIES} | {
        "runtime_kind": "external_rules_engine"
    }
    if missing is not None:
        caps[missing] = False

    class _Client:
        running = True
        pid = 4242

        def handshake(self):
            return (
                {"engine": "xmage", "engine_version": "test"},
                EngineCapabilityHandshake.model_validate(caps),
            )

    config = load_engine_runtime_config(
        {"ENGINE_PROVIDER": "xmage", "ENGINE_START_COMMAND": "true"}
    )
    manager = EngineProcessManager(config, root=tmp_path)
    manager._client = _Client()  # type: ignore[assignment]
    state = manager.healthcheck()
    if missing is None:
        assert state.status == EngineProcessStatus.HEALTHY
        return
    assert state.status == EngineProcessStatus.DEGRADED
    assert missing in " ".join(state.details)


def test_h4_healthy_expectation_holds_for_the_current_manifest() -> None:
    """D5: the launched full-game lane derives no missing capability, so H4 expects healthy.

    The healthy expectation is bound to evidence, not to overlap: the sealed epoch's AF01 for
    the launched lane reports every flag engine-verify requires as literally true. If either
    stops holding, H4 and engine-verify could disagree, so this goes red.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = manifest["current_runtime"]["required_missing_capabilities"]
    assert missing == [], "the derived runtime list is empty, so H4 must expect healthy/rc=0"
    assert manifest["production_bridge"] == "xmage_full_game_lane_bridge"
    epoch = MANIFEST.parents[1] / manifest["architecture_freeze"]["evidence_epoch"]
    af01 = json.loads((epoch / "AF01_XMAGE.json").read_text(encoding="utf-8"))
    assert af01["verdict"] == "PASS" and af01["lane"] == "full-game"
    reported = af01["capabilities_provider_reported"]
    assert {flag for flag in REQUIRED_CAPABILITIES if reported.get(flag) is not True} == set()
