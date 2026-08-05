from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from commander_lab.storage.atomic import atomic_write_text

from commander_lab.models import (
    GameState,
    GameStatus,
    InteractionSpec,
    InteractionValidation,
    PlayerState,
    RulesBackend,
    RulesEngineAvailability,
    TacticalScenario,
    ValidationLevel,
    ValidationRegistry,
    CardValidationRecord,
    ZoneState,
)

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


def validate_with_external_adapter(
    spec: InteractionSpec,
    adapter: RulesEngineAdapter,
) -> InteractionValidation:
    probe = adapter.probe()
    if probe.availability != RulesEngineAvailability.AVAILABLE:
        raise RuntimeError("external rules engine is not available")
    if probe.capabilities.runtime_kind != "external_rules_engine":
        raise RuntimeError("unverified or legacy bridge cannot produce rules_engine_validated evidence")
    session = adapter.create_scenario(_scenario_for_spec(spec))
    result = adapter.get_result(session.session_id)
    if result.validation_level != ValidationLevel.RULES_ENGINE_VALIDATED:
        raise RuntimeError("external adapter returned a non-rules-engine validation level")
    observed = result.normalized_result
    mismatches = tuple(
        f"{key}: expected {spec.expected_normalized.get(key)!r}, observed {observed.get(key)!r}"
        for key in spec.comparison_keys
        if spec.expected_normalized.get(key) != observed.get(key)
    )
    return InteractionValidation(
        interaction_id=spec.interaction_id,
        level=ValidationLevel.RULES_ENGINE_VALIDATED,
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
    engine_version: str = "tactical-0.8.0",
) -> ValidationRegistry:
    oracle = tactical_oracle or TacticalRuleOracle()
    specs = tuple(interactions)
    tactical_results = {spec.interaction_id: oracle.validate(spec) for spec in specs}
    external_results: dict[str, InteractionValidation] = {}
    external_attempts = 0
    for adapter in external_adapters:
        probe = adapter.probe()
        if probe.availability.value != "available":
            continue
        for spec in specs:
            preferred = spec.preferred_backend
            if preferred not in {"either", adapter.probe().backend.value}:
                continue
            external_attempts += 1
            try:
                result = validate_with_external_adapter(spec, adapter)
            except Exception:
                continue
            if result.passed:
                external_results[spec.interaction_id] = result

    chosen: dict[str, InteractionValidation] = {}
    for spec in specs:
        chosen[spec.interaction_id] = external_results.get(
            spec.interaction_id, tactical_results[spec.interaction_id]
        )

    by_card: dict[str, list[str]] = {name: [] for name in all_card_names}
    for spec in specs:
        for card in spec.cards:
            by_card.setdefault(card, []).append(spec.interaction_id)

    cards: dict[str, CardValidationRecord] = {}
    for card_name, interaction_ids in sorted(by_card.items()):
        tactical = [tactical_results[item] for item in interaction_ids]
        external = [external_results[item] for item in interaction_ids if item in external_results]
        if interaction_ids and len(external) == len(interaction_ids) and all(item.passed for item in external):
            level = ValidationLevel.RULES_ENGINE_VALIDATED
        elif interaction_ids and all(item.passed for item in tactical):
            level = ValidationLevel.TACTICAL_VALIDATED
        else:
            level = ValidationLevel.STRUCTURAL_ONLY
        notes: tuple[str, ...] = ()
        if not interaction_ids:
            notes = ("no project-critical tactical interaction registered",)
        elif level == ValidationLevel.TACTICAL_VALIDATED:
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
        notes=[
            "tactical_validated is a bounded local model status, not a complete MTG rules proof",
            "rules_engine_validated requires a matching XMage or Forge bridge observation",
        ],
    )
    return registry


def write_validation_registry(registry: ValidationRegistry, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return atomic_write_text(output, registry.model_dump_json(indent=2) + "\n")


__all__ = [
    "build_validation_registry",
    "load_interaction_catalog",
    "validate_with_external_adapter",
    "write_validation_registry",
]
