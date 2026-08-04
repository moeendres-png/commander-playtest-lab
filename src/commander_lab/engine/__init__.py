"""Simulation engines and action-validation boundaries."""

from .process_manager import EngineProcessManager, load_engine_runtime_config

from .action_validation import IllegalActionProposal, validate_action_proposal

__all__ = ["IllegalActionProposal", "validate_action_proposal", "EngineProcessManager", "load_engine_runtime_config"]

from .rules import (
    ForgeRulesAdapter,
    RulesEngineAdapter,
    RulesEngineError,
    RulesEngineProtocolError,
    RulesEngineUnavailable,
    RulesEngineManager,
    PHASE8_ENGINE_VERSION,
    TacticalRuleOracle,
    TacticalRulesAdapter,
    XMageRulesAdapter,
    build_validation_registry,
    load_interaction_catalog,
    write_validation_registry,
    load_project_rules_decks,
    load_rules_deck_snapshot,
    run_phase8_validation,
)

__all__ += [
    "ForgeRulesAdapter",
    "RulesEngineAdapter",
    "RulesEngineError",
    "RulesEngineProtocolError",
    "RulesEngineUnavailable",
    "RulesEngineManager",
    "PHASE8_ENGINE_VERSION",
    "TacticalRuleOracle",
    "TacticalRulesAdapter",
    "XMageRulesAdapter",
    "build_validation_registry",
    "load_interaction_catalog",
    "write_validation_registry",
    "load_project_rules_decks",
    "load_rules_deck_snapshot",
    "run_phase8_validation",
]
