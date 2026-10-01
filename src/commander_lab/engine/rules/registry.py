from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from commander_lab.models import (
    CardValidationRecord,
    ExternalValidationOutcome,
    GameState,
    GameStatus,
    InteractionSpec,
    InteractionValidation,
    PlayerState,
    RulesEngineAvailability,
    TacticalScenario,
    ValidationLevel,
    ValidationRegistry,
    ZoneState,
)
from commander_lab.storage.atomic import atomic_write_text

from .base import RulesEngineAdapter
from .tactical import TacticalRuleOracle


def load_interaction_catalog(path: str | Path) -> tuple[InteractionSpec, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(InteractionSpec.model_validate(item) for item in payload["interactions"])


def _scenario_for_spec(spec: InteractionSpec) -> TacticalScenario:
    state = GameState(
        game_id=f"interaction-{spec.interaction_id}",
        seed=0,
        status=GameStatus.IN_PROGRESS,
        turn_number=1,
        active_player_id="p1",
        priority_player_id="p1",
        players=(PlayerState(player_id="p1", seat=0, zones=ZoneState()),),
    )
    return TacticalScenario(
        scenario_id=spec.interaction_id,
        description=spec.description,
        state=state,
        rule=spec.rule,
        input_state=spec.input_state,
        expected_normalized=spec.expected_normalized,
        cards=spec.cards,
        tags=(spec.category,),
    )


class ExternalValidationProtocolError(RuntimeError):
    """The adapter cannot produce external-rules-engine evidence for this request."""


def validate_with_external_adapter(
    spec: InteractionSpec,
    adapter: RulesEngineAdapter,
) -> InteractionValidation:
    probe = adapter.probe()
    if probe.availability != RulesEngineAvailability.AVAILABLE:
        raise ExternalValidationProtocolError("external rules engine is not available")
    if probe.capabilities.runtime_kind != "external_rules_engine":
        raise ExternalValidationProtocolError(
            "unverified or legacy bridge cannot produce external_rules_engine evidence"
        )
    session = adapter.create_scenario(_scenario_for_spec(spec))
    result = adapter.get_result(session.session_id)
    if result.validation_level != ValidationLevel.EXTERNAL_RULES_ENGINE:
        raise ExternalValidationProtocolError(
            "external adapter returned a non-rules-engine validation level"
        )
    observed = result.normalized_result
    mismatches = tuple(
        f"{key}: expected {spec.expected_normalized.get(key)!r}, observed {observed.get(key)!r}"
        for key in spec.comparison_keys
        if spec.expected_normalized.get(key) != observed.get(key)
    )
    return InteractionValidation(
        interaction_id=spec.interaction_id,
        level=ValidationLevel.EXTERNAL_RULES_ENGINE,
        passed=not mismatches,
        backend=result.backend,
        expected={key: spec.expected_normalized.get(key) for key in spec.comparison_keys},
        observed={key: observed.get(key) for key in spec.comparison_keys},
        comparison_keys=spec.comparison_keys,
        mismatches=mismatches,
        backend_version=result.backend_version,
    )


def build_validation_registry(
    *,
    all_card_names: Iterable[str],
    interactions: Iterable[InteractionSpec],
    tactical_oracle: TacticalRuleOracle | None = None,
    external_adapters: Iterable[RulesEngineAdapter] = (),
    engine_version: str = "tactical-0.8.1",
) -> ValidationRegistry:
    oracle = tactical_oracle or TacticalRuleOracle()
    specs = tuple(interactions)
    tactical_results = {spec.interaction_id: oracle.validate(spec) for spec in specs}
    # F2: every external attempt is recorded. A failing or disagreeing rules
    # engine is evidence, not something to skip past to the local oracle.
    external_results: dict[str, InteractionValidation] = {}
    external_mismatches: dict[str, InteractionValidation] = {}
    outcomes: list[ExternalValidationOutcome] = []
    external_attempts = 0
    for adapter in external_adapters:
        probe = adapter.probe()
        backend = probe.backend.value
        if probe.availability.value != "available":
            outcomes.append(
                ExternalValidationOutcome(
                    interaction_id="*",
                    backend=backend,
                    status="UNAVAILABLE",
                    detail=f"probe availability {probe.availability.value}",
                )
            )
            continue
        for spec in specs:
            preferred = spec.preferred_backend
            if preferred not in {"either", backend}:
                continue
            external_attempts += 1
            try:
                result = validate_with_external_adapter(spec, adapter)
            except ExternalValidationProtocolError as exc:
                outcomes.append(
                    ExternalValidationOutcome(
                        interaction_id=spec.interaction_id,
                        backend=backend,
                        status="PROTOCOL_FAIL",
                        detail=str(exc),
                    )
                )
                continue
            except Exception as exc:
                outcomes.append(
                    ExternalValidationOutcome(
                        interaction_id=spec.interaction_id,
                        backend=backend,
                        status="ENGINE_FAIL",
                        detail=type(exc).__name__,
                    )
                )
                continue
            if result.passed:
                external_results[spec.interaction_id] = result
                outcomes.append(
                    ExternalValidationOutcome(
                        interaction_id=spec.interaction_id, backend=backend, status="PASS"
                    )
                )
            else:
                external_mismatches[spec.interaction_id] = result
                outcomes.append(
                    ExternalValidationOutcome(
                        interaction_id=spec.interaction_id,
                        backend=backend,
                        status="RESULT_MISMATCH",
                        detail="mismatching keys: "
                        + ", ".join(
                            key
                            for key in spec.comparison_keys
                            if result.expected.get(key) != result.observed.get(key)
                        ),
                    )
                )

    # The external rules engine outranks the local oracle in both directions:
    # its pass is the recorded validation, and so is its disagreement.
    chosen: dict[str, InteractionValidation] = {}
    for spec in specs:
        chosen[spec.interaction_id] = external_results.get(
            spec.interaction_id,
            external_mismatches.get(spec.interaction_id, tactical_results[spec.interaction_id]),
        )

    by_card: dict[str, list[str]] = {name: [] for name in all_card_names}
    for spec in specs:
        for card in spec.cards:
            by_card.setdefault(card, []).append(spec.interaction_id)

    cards: dict[str, CardValidationRecord] = {}
    for card_name, interaction_ids in sorted(by_card.items()):
        tactical = [tactical_results[item] for item in interaction_ids]
        external = [external_results[item] for item in interaction_ids if item in external_results]
        disputed = sorted(item for item in interaction_ids if item in external_mismatches)
        if disputed:
            level = ValidationLevel.STRUCTURAL_ONLY
        elif (
            interaction_ids
            and len(external) == len(interaction_ids)
            and all(item.passed for item in external)
        ):
            level = ValidationLevel.EXTERNAL_RULES_ENGINE
        elif interaction_ids and all(item.passed for item in tactical):
            level = ValidationLevel.TACTICAL_ORACLE
        else:
            level = ValidationLevel.STRUCTURAL_ONLY
        notes: tuple[str, ...] = ()
        if disputed:
            notes = (
                "external rules engine disagrees with the expected result for "
                + ", ".join(disputed)
                + "; the local tactical oracle does not override it",
            )
        elif not interaction_ids:
            notes = ("no project-critical tactical interaction registered",)
        elif level == ValidationLevel.TACTICAL_ORACLE:
            notes = ("local tactical oracle passed; external rules engine not yet recorded",)
        cards[card_name] = CardValidationRecord(
            oracle_name=card_name,
            level=level,
            interaction_ids=tuple(sorted(interaction_ids)),
            tactical_passed=sum(item.passed for item in tactical),
            rules_engine_passed=sum(item.passed for item in external),
            notes=notes,
        )

    registry = ValidationRegistry(
        engine_version=engine_version,
        cards=cards,
        interactions=chosen,
        tactical_cases=len(tactical_results),
        tactical_passed=sum(item.passed for item in tactical_results.values()),
        rules_engine_cases=external_attempts,
        rules_engine_passed=len(external_results),
        external_outcomes=outcomes,
        notes=[
            "tactical_oracle is a bounded local model status, not a complete MTG rules proof",
            "external_rules_engine requires a matching XMage or Forge bridge observation",
        ],
    )
    return registry


def write_validation_registry(registry: ValidationRegistry, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return atomic_write_text(output, registry.model_dump_json(indent=2) + "\n")


__all__ = [
    "ExternalValidationProtocolError",
    "build_validation_registry",
    "load_interaction_catalog",
    "validate_with_external_adapter",
    "write_validation_registry",
]
