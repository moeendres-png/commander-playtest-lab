from .base import (
    RulesEngineAdapter,
    RulesEngineError,
    RulesEngineProtocolError,
    RulesEngineUnavailable,
)
from .bridge import ExternalRulesAdapter, ForgeRulesAdapter, JsonLineBridgeClient, XMageRulesAdapter
from .full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    ExternalPilotDecisionPolicy,
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGamePilotBinding,
    FullGameProtocolError,
    FullGameReplayGate,
    XmageFullGameRunner,
)
from .full_game_batch import (
    FullGameBatchCase,
    FullGameBatchRecord,
    FullGameBatchReport,
    FullGameFailureClass,
    XmageFullGameBatchRunner,
)
from .manager import RulesEngineManager
from .phase85 import PHASE85_VERSION, run_phase85_validation
from .project import load_project_rules_decks, load_rules_deck_snapshot
from .protocol import build_protocol_schema, write_protocol_schema
from .registry import (
    build_validation_registry,
    load_interaction_catalog,
    validate_with_external_adapter,
    write_validation_registry,
)
from .replay import ReplayValidationError, ReplayValidationResult, replay_into_internal_model
from .tactical import TacticalRuleError, TacticalRuleOracle, TacticalRulesAdapter
from .validation import PHASE8_ENGINE_VERSION, run_phase8_validation

__all__ = [
    "FULL_GAME_DECISION_PROTOCOL_VERSION",
    "FULL_GAME_EVIDENCE_CLASS",
    "FULL_GAME_LANE",
    "PHASE8_ENGINE_VERSION",
    "PHASE85_VERSION",
    "ExternalPilotDecisionPolicy",
    "ExternalRulesAdapter",
    "ForgeRulesAdapter",
    "FullGameBatchCase",
    "FullGameBatchRecord",
    "FullGameBatchReport",
    "FullGameConformanceError",
    "FullGameConformanceResult",
    "FullGameFailureClass",
    "FullGamePilotBinding",
    "FullGameProtocolError",
    "FullGameReplayGate",
    "JsonLineBridgeClient",
    "ReplayValidationError",
    "ReplayValidationResult",
    "RulesEngineAdapter",
    "RulesEngineError",
    "RulesEngineManager",
    "RulesEngineProtocolError",
    "RulesEngineUnavailable",
    "TacticalRuleError",
    "TacticalRuleOracle",
    "TacticalRulesAdapter",
    "XMageRulesAdapter",
    "XmageFullGameBatchRunner",
    "XmageFullGameRunner",
    "build_protocol_schema",
    "build_validation_registry",
    "load_interaction_catalog",
    "load_project_rules_decks",
    "load_rules_deck_snapshot",
    "replay_into_internal_model",
    "run_phase8_validation",
    "run_phase85_validation",
    "validate_with_external_adapter",
    "write_protocol_schema",
    "write_validation_registry",
]
