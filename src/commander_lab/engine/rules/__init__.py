from .base import (
    RulesEngineAdapter,
    RulesEngineError,
    RulesEngineProtocolError,
    RulesEngineUnavailable,
)
from .bridge import ExternalRulesAdapter, ForgeRulesAdapter, JsonLineBridgeClient, XMageRulesAdapter
from .manager import RulesEngineManager
from .protocol import build_protocol_schema, write_protocol_schema
from .replay import ReplayValidationError, ReplayValidationResult, replay_into_internal_model
from .project import load_project_rules_decks, load_rules_deck_snapshot
from .registry import (
    build_validation_registry,
    load_interaction_catalog,
    validate_with_external_adapter,
    write_validation_registry,
)
from .tactical import TacticalRuleError, TacticalRuleOracle, TacticalRulesAdapter
from .validation import PHASE8_ENGINE_VERSION, run_phase8_validation
from .phase85 import PHASE85_VERSION, run_phase85_validation

__all__ = [
    "ExternalRulesAdapter",
    "ForgeRulesAdapter",
    "JsonLineBridgeClient",
    "RulesEngineAdapter",
    "RulesEngineError",
    "RulesEngineProtocolError",
    "RulesEngineManager",
    "ReplayValidationError",
    "ReplayValidationResult",
    "RulesEngineUnavailable",
    "TacticalRuleError",
    "TacticalRuleOracle",
    "TacticalRulesAdapter",
    "PHASE8_ENGINE_VERSION",
    "PHASE85_VERSION",
    "run_phase8_validation",
    "run_phase85_validation",
    "XMageRulesAdapter",
    "build_validation_registry",
    "load_interaction_catalog",
    "load_project_rules_decks",
    "load_rules_deck_snapshot",
    "validate_with_external_adapter",
    "write_validation_registry",
    "build_protocol_schema",
    "write_protocol_schema",
    "replay_into_internal_model",
]
