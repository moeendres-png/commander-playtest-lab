"""F2: external rules-engine outcomes are persisted, never swallowed.

`build_validation_registry` used to `continue` past any adapter exception and
to drop any external result that did not pass. A card whose external engine
disagreed with the expected result therefore still reached TACTICAL_ORACLE on
the strength of the local model alone. Every attempt is now recorded as
UNAVAILABLE / PROTOCOL_FAIL / ENGINE_FAIL / RESULT_MISMATCH / PASS, and an
external disagreement outranks the local oracle.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from commander_lab.engine.rules import registry as registry_mod
from commander_lab.models import (
    InteractionSpec,
    InteractionValidation,
    RulesBackend,
    ValidationLevel,
)


def _spec(interaction_id: str, card: str) -> InteractionSpec:
    return InteractionSpec(
        interaction_id=interaction_id,
        description=interaction_id,
        category="test",
        cards=(card,),
        rule="r",
        input_state={},
        expected_normalized={"legal": True},
        comparison_keys=("legal",),
    )


class _PassingOracle:
    def validate(self, spec: InteractionSpec) -> InteractionValidation:
        return InteractionValidation(
            interaction_id=spec.interaction_id,
            level=ValidationLevel.TACTICAL_ORACLE,
            passed=True,
            backend=RulesBackend.TACTICAL,
            expected={"legal": True},
            observed={"legal": True},
            comparison_keys=("legal",),
        )


def _adapter(available: bool = True) -> Any:
    probe = SimpleNamespace(
        availability=SimpleNamespace(value="available" if available else "unavailable"),
        backend=SimpleNamespace(value="xmage"),
    )
    return SimpleNamespace(probe=lambda: probe)


def _external(spec: InteractionSpec, passed: bool) -> InteractionValidation:
    return InteractionValidation(
        interaction_id=spec.interaction_id,
        level=ValidationLevel.EXTERNAL_RULES_ENGINE,
        passed=passed,
        backend=RulesBackend.XMAGE,
        expected={"legal": True},
        observed={"legal": passed},
        comparison_keys=("legal",),
        mismatches=() if passed else ("legal: expected True, observed False",),
    )


def _build(monkeypatch: pytest.MonkeyPatch, behaviour: dict[str, Any], adapters: tuple[Any, ...]):  # type: ignore[no-untyped-def]
    specs = tuple(_spec(name, f"Card {name}") for name in behaviour)

    def fake_validate(spec: InteractionSpec, adapter: Any) -> InteractionValidation:
        outcome = behaviour[spec.interaction_id]
        if isinstance(outcome, Exception):
            raise outcome
        return _external(spec, outcome)

    monkeypatch.setattr(registry_mod, "validate_with_external_adapter", fake_validate)
    return registry_mod.build_validation_registry(
        all_card_names=[f"Card {name}" for name in behaviour],
        interactions=specs,
        tactical_oracle=_PassingOracle(),  # type: ignore[arg-type]
        external_adapters=adapters,
    )


def test_every_attempt_outcome_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    behaviour: dict[str, Any] = {
        "pass": True,
        "mismatch": False,
        "protocol": registry_mod.ExternalValidationProtocolError("legacy bridge"),
        "engine": RuntimeError("java.lang.IllegalStateException: hidden card Sol Ring"),
    }
    registry = _build(monkeypatch, behaviour, (_adapter(),))
    status = {o.interaction_id: o.status for o in registry.external_outcomes}
    assert status == {
        "pass": "PASS",
        "mismatch": "RESULT_MISMATCH",
        "protocol": "PROTOCOL_FAIL",
        "engine": "ENGINE_FAIL",
    }
    engine = next(o for o in registry.external_outcomes if o.interaction_id == "engine")
    assert engine.detail == "RuntimeError"
    assert "Sol Ring" not in registry.model_dump_json()
    assert registry.rules_engine_cases == 4
    assert registry.rules_engine_passed == 1


def test_an_external_disagreement_outranks_the_local_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _build(monkeypatch, {"mismatch": False, "pass": True}, (_adapter(),))
    disputed = registry.cards["Card mismatch"]
    assert disputed.level is ValidationLevel.STRUCTURAL_ONLY
    assert "disagrees" in disputed.notes[0]
    assert registry.interactions["mismatch"].level is ValidationLevel.EXTERNAL_RULES_ENGINE
    assert registry.interactions["mismatch"].passed is False
    assert registry.cards["Card pass"].level is ValidationLevel.EXTERNAL_RULES_ENGINE


def test_an_engine_failure_leaves_the_oracle_level_but_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _build(monkeypatch, {"engine": RuntimeError("boom")}, (_adapter(),))
    assert registry.cards["Card engine"].level is ValidationLevel.TACTICAL_ORACLE
    assert [o.status for o in registry.external_outcomes] == ["ENGINE_FAIL"]


def test_an_unavailable_adapter_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _build(monkeypatch, {"pass": True}, (_adapter(available=False),))
    assert [(o.interaction_id, o.status) for o in registry.external_outcomes] == [
        ("*", "UNAVAILABLE")
    ]
    assert registry.rules_engine_cases == 0
