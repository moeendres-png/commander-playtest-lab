"""Tests: WS50 integration boundary and expected-vs-observed distinction."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.gate import validate_output
from q6_scaffolding.integration import (
    RUNTIME_AUTHORITY,
    SCAFFOLDING_AUTHORITY,
    ExpectedDecisionPretags,
    ObservedRuntimeDecision,
    ScaffoldingScenarioInput,
    WitnessRequirements,
    apply_runtime_observation,
    build_scenario_input,
)

from q6_scaffolding import integration

from .support import by_name, run_pipeline


def _scenario_input_for(tmp_path, name="Lightning Bolt"):
    out = run_pipeline(tmp_path)
    record = by_name(out["skeletons"]["records"], name)
    return build_scenario_input(record["skeleton"], record["skeleton"].get("provenance", {}))


def test_scenario_input_carries_no_legal_options(tmp_path):
    scenario = _scenario_input_for(tmp_path)
    payload = scenario.as_dict()
    validate_output(payload, artifact="scenario-input")
    assert "legal_options" not in payload
    assert "legal_options" not in repr(payload)


def test_pretags_explicitly_non_authoritative():
    pretags = ExpectedDecisionPretags(
        intake_id="i", skeleton_id="s", pretags=({"kind": "TARGET_SELECTION"},)
    )
    assert pretags.authority == SCAFFOLDING_AUTHORITY
    assert pretags.authority != RUNTIME_AUTHORITY


def test_runtime_observation_overwrites_pretags_without_veto(tmp_path):
    scenario = _scenario_input_for(tmp_path)
    observed = [
        ObservedRuntimeDecision(kind="MANA_PAYMENT", options_offered=("pay R",), selection="pay R"),
        ObservedRuntimeDecision(
            kind="NOVEL_RUNTIME_KIND", options_offered=("a", "b"), selection="a"
        ),
    ]
    report = apply_runtime_observation(scenario, observed)
    assert "TARGET_SELECTION" in report["contradicted_pretags"]
    assert "NOVEL_RUNTIME_KIND" in report["novel_runtime_decisions"]
    assert "no veto" in report["precedence"]


def test_empty_runtime_sequence_contradicts_all_pretags(tmp_path):
    scenario = _scenario_input_for(tmp_path)
    report = apply_runtime_observation(scenario, [])
    assert report["novel_runtime_decisions"] == []
    assert set(report["contradicted_pretags"]) == set(report["pretagged_kinds"])


def test_non_runtime_authority_observation_rejected(tmp_path):
    scenario = _scenario_input_for(tmp_path)
    bogus = ObservedRuntimeDecision(
        kind="TARGET_SELECTION",
        options_offered=("x",),
        selection="x",
        authority=SCAFFOLDING_AUTHORITY,
    )
    with pytest.raises(ValueError, match="must carry RUNTIME_AUTHORITATIVE"):
        apply_runtime_observation(scenario, [bogus])


def test_witness_requirements_shape(tmp_path):
    out = run_pipeline(tmp_path)
    record = by_name(out["skeletons"]["records"], "Lightning Bolt")
    witnesses = WitnessRequirements(
        intake_id=record["intake_id"],
        skeleton_id=record["skeleton_id"],
        witnesses=tuple(record["skeleton"]["witness_requirements"]),
    )
    assert witnesses.authority == SCAFFOLDING_AUTHORITY
    assert witnesses.as_dict()["witnesses"]


def test_integration_module_touches_no_ws50_paths():
    source = Path(integration.__file__).read_text(encoding="utf-8")
    # No imports from, and no filesystem references to, WS50-owned surfaces.
    # Prose mentions of the WS50 workstream name are allowed (boundary spec).
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            assert "ws50" not in stripped.lower()
            assert "forge" not in stripped.lower()
    for forbidden in ("qualification/providers/forge", "engine-bridge/"):
        assert forbidden not in source, f"WS50 surface path leaked: {forbidden}"


def test_scenario_input_is_plain_data():
    scenario = ScaffoldingScenarioInput(
        intake_id="i",
        skeleton_id="s",
        card_name_hint="C",
        capability_under_test="TARGET_SELECTION",
    )
    data = scenario.as_dict()
    assert data["capability_under_test"] == "TARGET_SELECTION"
    validate_output(data, artifact="scenario-input-shape")
