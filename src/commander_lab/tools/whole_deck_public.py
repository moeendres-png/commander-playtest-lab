from __future__ import annotations

from typing import Any

from commander_lab.models.whole_deck_tooling import (
    WholeDeckDecisionPrepareInput,
    WholeDeckDecisionRunInput,
)

from .whole_deck_prepare import prepare_whole_deck
from .whole_deck_run import run_whole_deck


def install_whole_deck_public_integration() -> None:
    from commander_lab.tools import registry as registry_module
    from commander_lab.tools.registry import ToolDefinition
    from commander_lab.tools.service import CommanderToolService

    if getattr(CommanderToolService, "_whole_deck_public_installed", False):
        return
    original_prepare = CommanderToolService.deck_decision_prepare
    original_run = CommanderToolService.deck_decision_run

    def prepare(self: Any, request: Any):
        if getattr(request, "design_mode", "swap") != "whole_deck":
            return original_prepare(self, request)
        return self._invoke(
            "deck_decision_prepare",
            request,
            lambda: prepare_whole_deck(self, request),
            deck_ids=(request.deck_id,),
        )

    def run(self: Any, request: Any):
        if getattr(request, "comparison_mode", "swap") != "whole_deck":
            return original_run(self, request)
        return self._invoke(
            "deck_decision_run",
            request,
            lambda: run_whole_deck(self, request),
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.iterations,
        )

    CommanderToolService.deck_decision_prepare = prepare
    CommanderToolService.deck_decision_run = run
    CommanderToolService._whole_deck_public_installed = True

    definitions: list[ToolDefinition] = []
    for definition in registry_module.PUBLIC_TOOL_DEFINITIONS:
        if definition.name == "deck_decision_prepare":
            definitions.append(
                ToolDefinition(
                    "deck_decision_prepare",
                    "Validate current truth and prepare a legacy swap decision or bounded "
                    "Whole-Deck designs without applying them.",
                    WholeDeckDecisionPrepareInput,
                    "deck_decision_prepare",
                )
            )
        elif definition.name == "deck_decision_run":
            definitions.append(
                ToolDefinition(
                    "deck_decision_run",
                    "Run one paired structural comparison for a legacy swap or prepared "
                    "Whole-Deck finalist without applying it.",
                    WholeDeckDecisionRunInput,
                    "deck_decision_run",
                )
            )
        else:
            definitions.append(definition)
    registry_module.PUBLIC_TOOL_DEFINITIONS = tuple(definitions)
