from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from commander_lab.models import (
    CalibrateInput,
    CardAblationInput,
    CommanderDenialInput,
    CompareDecksInput,
    CreateReportInput,
    GoldfishInput,
    HoldoutInput,
    IngestPlaytestInput,
    InspectDeckInput,
    MatchupBatchInput,
    PackageAblationInput,
    PairedVariantInput,
    RecommendUpgradesInput,
    SearchVariantsInput,
    SensitivityInput,
    SwapMatrixInput,
    ToolResponse,
    ValidateDeckInput,
    ValidateUpgradeInput,
)

from .service import CommanderToolService


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    handler_name: str

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "strict": True,
            "parameters": self.input_model.model_json_schema(),
        }


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition("validate_deck", "Validate Commander legality, size, singleton, color identity and local allocation.", ValidateDeckInput, "validate_deck"),
    ToolDefinition("inspect_deck", "Inspect role counts, structural weaknesses and optional card profiles.", InspectDeckInput, "inspect_deck"),
    ToolDefinition("run_goldfish", "Run a deterministic structural goldfish batch.", GoldfishInput, "run_goldfish"),
    ToolDefinition("run_matchup_batch", "Run a structural multiplayer matchup batch.", MatchupBatchInput, "run_matchup_batch"),
    ToolDefinition("compare_decks", "Compare two complete decks under paired random conditions.", CompareDecksInput, "compare_decks"),
    ToolDefinition("compare_variants_paired", "Compare a baseline and card-swap variant using identical seeds.", PairedVariantInput, "compare_variants_paired"),
    ToolDefinition("run_card_ablation", "Estimate a card contribution with role-neutral paired ablation.", CardAblationInput, "run_card_ablation"),
    ToolDefinition("run_package_ablation", "Estimate a package contribution with paired ablation.", PackageAblationInput, "run_package_ablation"),
    ToolDefinition("run_commander_denial", "Stress-test a deck with added commander tax and optional synergy suppression.", CommanderDenialInput, "run_commander_denial"),
    ToolDefinition("generate_swap_matrix", "Evaluate a matrix of cuts and candidate additions.", SwapMatrixInput, "generate_swap_matrix"),
    ToolDefinition("search_variants", "Search bounded one-card structural variants.", SearchVariantsInput, "search_variants"),
    ToolDefinition("run_holdout", "Evaluate a proposed variant on unused holdout pods.", HoldoutInput, "run_holdout"),
    ToolDefinition("run_sensitivity", "Repeat scenarios across seeds and pilot strengths.", SensitivityInput, "run_sensitivity"),
    ToolDefinition("recommend_upgrades", "Screen role-profile upgrade candidates without claiming confirmation.", RecommendUpgradesInput, "recommend_upgrades"),
    ToolDefinition("validate_upgrade", "Confirm or reject a proposed upgrade using paired and holdout criteria.", ValidateUpgradeInput, "validate_upgrade"),
    ToolDefinition("ingest_playtest", "Import a local real-playtest CSV or XLSX form.", IngestPlaytestInput, "ingest_playtest"),
    ToolDefinition("calibrate", "Build a provisional calibration summary from ingested real games.", CalibrateInput, "calibrate"),
    ToolDefinition("create_report", "Create a local structured Markdown evidence report.", CreateReportInput, "create_report"),
)


class ToolRegistry:
    def __init__(self, service: CommanderToolService) -> None:
        self.service = service
        self._definitions = {definition.name: definition for definition in TOOL_DEFINITIONS}

    def list_schemas(self) -> list[dict[str, Any]]:
        return [definition.schema() for definition in TOOL_DEFINITIONS]

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
