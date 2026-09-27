from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from commander_lab.models import ToolResponse
from commander_lab.models.tooling_v120 import (
    ComparePilotsInput,
    RunPilotBenchmarkInput,
    RunPilotEnsembleInput,
    TestVariantAcrossPilotsInput,
)
from commander_lab.models.whole_deck_tooling import (
    WholeDeckDecisionPrepareInput,
    WholeDeckDecisionRunInput,
)

from .registry import (
    PUBLIC_TOOL_DEFINITIONS as LEGACY_PUBLIC_TOOL_DEFINITIONS,
)
from .registry import (
    TOOL_DEFINITIONS,
    ToolDefinition,
)
from .service_v120 import CommanderToolService

_MODEL_OVERRIDES: dict[str, type[BaseModel]] = {
    "run_pilot_benchmark": RunPilotBenchmarkInput,
    "compare_pilots": ComparePilotsInput,
    "run_pilot_ensemble": RunPilotEnsembleInput,
    "test_variant_across_pilots": TestVariantAcrossPilotsInput,
}

EXPERT_TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = tuple(
    ToolDefinition(
        definition.name,
        definition.description,
        _MODEL_OVERRIDES.get(definition.name, definition.input_model),
        definition.handler_name,
    )
    for definition in TOOL_DEFINITIONS
)

PUBLIC_TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        "deck_decision_prepare",
        "Validate current truth and prepare either a swap decision or bounded Whole-Deck designs without applying them.",
        WholeDeckDecisionPrepareInput,
        "deck_decision_prepare",
    ),
    ToolDefinition(
        "deck_decision_run",
        "Run one paired structural swap or Whole-Deck comparison without applying it.",
        WholeDeckDecisionRunInput,
        "deck_decision_run",
    ),
    next(
        definition
        for definition in LEGACY_PUBLIC_TOOL_DEFINITIONS
        if definition.name == "deck_decision_diagnose"
    ),
    next(
        definition
        for definition in LEGACY_PUBLIC_TOOL_DEFINITIONS
        if definition.name == "deck_decision_bundle"
    ),
)


class ToolRegistry:
    def __init__(self, service: CommanderToolService, *, surface: str = "public") -> None:
        self.service = service
        if surface == "public":
            definitions = PUBLIC_TOOL_DEFINITIONS
        elif surface == "expert":
            definitions = EXPERT_TOOL_DEFINITIONS
        elif surface == "all":
            definitions = (*PUBLIC_TOOL_DEFINITIONS, *EXPERT_TOOL_DEFINITIONS)
        else:
            raise ValueError("tool surface must be public, expert, or all")
        self.surface = surface
        self.definitions = tuple(definitions)
        self._definitions = {definition.name: definition for definition in self.definitions}

    def list_schemas(self) -> list[dict[str, Any]]:
        return [definition.schema() for definition in self.definitions]

    def input_model(self, name: str) -> type[BaseModel]:
        try:
            return self._definitions[name].input_model
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def invoke(self, name: str, payload: dict[str, Any]) -> ToolResponse:
        try:
            definition = self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc
        request = definition.input_model.model_validate(payload)
        handler: Callable[[Any], ToolResponse] = getattr(self.service, definition.handler_name)
        return handler(request)
