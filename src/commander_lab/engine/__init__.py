"""Simulation engines and action-validation boundaries."""

from .action_validation import IllegalActionProposal, validate_action_proposal
from .process_manager import EngineProcessManager, load_engine_runtime_config

__all__ = [
    "EngineProcessManager",
    "IllegalActionProposal",
    "load_engine_runtime_config",
    "validate_action_proposal",
]

from .rules import (
    RulesEngineAdapter,
    RulesEngineError,
    RulesEngineManager,
    RulesEngineProtocolError,
    RulesEngineUnavailable,
    TacticalRuleOracle,
    TacticalRulesAdapter,
    XMageRulesAdapter,
    build_validation_registry,
    load_interaction_catalog,
    load_project_rules_decks,
    load_rules_deck_snapshot,
    write_validation_registry,
)

__all__ += [
    "RulesEngineAdapter",
    "RulesEngineError",
    "RulesEngineManager",
    "RulesEngineProtocolError",
    "RulesEngineUnavailable",
    "TacticalRuleOracle",
    "TacticalRulesAdapter",
    "XMageRulesAdapter",
    "build_validation_registry",
    "load_interaction_catalog",
    "load_project_rules_decks",
    "load_rules_deck_snapshot",
    "write_validation_registry",
]
