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
  (``app.py:470``) -- decides healthy/degraded from its OWN hand-written six-flag tuple. That
  tuple is NOT ``REQUIRED_CAPABILITIES``: it is a strict subset missing five flags.

The third bullet is the finding #691 was opened to establish, not something this module hides.
Converging it is authority-gated ("do not widen or shrink any required set", "no change to what is
credited") and is not even mechanically available today: two of the five unbound flags are not
resolvable through the handshake model at all, so substituting the import would raise rather than
behave identically (see ``test_unbound_flags_are_not_resolvable_by_the_handshake_model``). This
module therefore pins all three consumers exactly. It goes red if any of them changes -- the
property #691 asked for -- and it makes the residual gap machine-checkable instead of prose.
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
from commander_lab.models import RulesEngineCapabilities

REPO_ROOT = Path(__file__).resolve().parents[2]
DERIVE_SCRIPT = REPO_ROOT / "scripts" / "derive_rules_engines_capabilities.py"
H4_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "h4-docker-materialization.yml"
PROCESS_MANAGER = REPO_ROOT / "src" / "commander_lab" / "engine" / "process_manager.py"
MANIFEST = REPO_ROOT / "config" / "rules_engines.json"

H4_STEP_NAME = "engine-verify outcome vs manifest capability truth (recorded, consistency-gated)"

# The five freeze-eligibility flags that decide engine health today without being required by it:
# EngineProcessManager.healthcheck never asks the handshake about them, so an engine missing all
# five still passes its required-capability check. Recorded here as the exact, two-sided delta so
# that any future change on EITHER side turns the test red instead of drifting silently.
KNOWN_UNBOUND_CAPABILITIES = frozenset(
    {
        "engine_shutdown_supported",
        "game_shutdown_supported",
        "headless_supported",
        "replay_supported",
        "seed_supported",
    }
)

# What EngineProcessManager.healthcheck actually requires today, asserted against the shipped
# source rather than restated as a second literal authority.
EXPECTED_ENGINE_HEALTH_REQUIRED_FLAGS = (
    "commander_supported",
    "multiplayer_supported",
    "deck_import_supported",
    "legal_actions_supported",
    "action_submission_supported",
    "event_log_supported",
)


def _load_derive_module(source_path: Path | None = None) -> ModuleType:
    """Load the derivation script. ``source_path`` defaults to the shipped file at call time."""
    spec = importlib.util.spec_from_file_location(
        "derive_rules_engines_capabilities", source_path or DERIVE_SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _engine_health_required_flags(source: str) -> tuple[str, ...]:
    """Extract the literal capability tuple ``EngineProcessManager.healthcheck`` requires.

    Read from the shipped source by AST rather than restated, so this module cannot drift into a
    second copy of the answer it is supposed to police.
    """
    manager = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef) and node.name == "EngineProcessManager"
    )
    healthcheck = next(
        node
        for node in manager.body
        if isinstance(node, ast.FunctionDef) and node.name == "healthcheck"
    )
    tuples = [
        tuple(e.value for e in node.value.elts)
        for node in ast.walk(healthcheck)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "required" for t in node.targets)
        and isinstance(node.value, ast.Tuple)
        and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.value.elts)
    ]
    assert len(tuples) == 1, f"expected one `required` capability tuple, found {len(tuples)}"
    return tuples[0]


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


def test_engine_verify_requires_exactly_the_shipped_process_manager_flags() -> None:
    """Pins what engine-verify credits today, so any change to it is an explicit decision."""
    actual = _engine_health_required_flags(PROCESS_MANAGER.read_text(encoding="utf-8"))
    assert actual == EXPECTED_ENGINE_HEALTH_REQUIRED_FLAGS, (
        f"engine-verify now requires {list(actual)}, "
        f"not {list(EXPECTED_ENGINE_HEALTH_REQUIRED_FLAGS)}"
    )


def test_engine_health_set_is_the_known_strict_subset_of_required_capabilities() -> None:
    """The exact two-sided delta between engine health and the freeze-eligibility set."""
    engine_health = set(_engine_health_required_flags(PROCESS_MANAGER.read_text(encoding="utf-8")))
    assert engine_health < set(REQUIRED_CAPABILITIES), "engine health now requires the whole set"
    assert set(REQUIRED_CAPABILITIES) - engine_health == KNOWN_UNBOUND_CAPABILITIES
    assert engine_health - set(REQUIRED_CAPABILITIES) == set()


def test_unbound_flags_are_not_resolvable_by_the_handshake_model() -> None:
    """Why the gap cannot be closed by a drop-in import, and must stay authority-gated.

    ``RulesEngineCapabilities.supports`` raises KeyError for names the model does not carry, so
    replacing the six-flag tuple with ``REQUIRED_CAPABILITIES`` would crash engine-verify rather
    than preserve its behaviour. Convergence needs a Rules/architecture decision first.
    """
    unresolvable: list[str] = []
    capabilities = RulesEngineCapabilities()
    for name in REQUIRED_CAPABILITIES:
        try:
            capabilities.supports(name)
        except KeyError:
            unresolvable.append(name)
    assert unresolvable == ["engine_shutdown_supported", "game_shutdown_supported"]
    with pytest.raises(KeyError):
        capabilities.supports("engine_shutdown_supported")
    with pytest.raises(KeyError):
        capabilities.supports("game_shutdown_supported")


def test_h4_degraded_expectation_holds_for_the_current_manifest() -> None:
    """H4 keeps expecting engine-verify=degraded while the runtime missing list is non-empty."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = manifest["current_runtime"]["required_missing_capabilities"]
    assert missing, "the derived runtime list is non-empty, so H4 must expect degraded/rc=1"
    assert set(missing) <= set(REQUIRED_CAPABILITIES)
    # ...and the flags it is missing are also ones engine-verify requires, which is why the two
    # currently agree. Recorded explicitly: this agreement is incidental overlap, not binding.
    engine_health = set(_engine_health_required_flags(PROCESS_MANAGER.read_text(encoding="utf-8")))
    assert set(missing) & engine_health, (
        "the manifest/runtime set and the engine-verify set no longer overlap; H4 would demand "
        "degraded while engine-verify reports healthy"
    )
