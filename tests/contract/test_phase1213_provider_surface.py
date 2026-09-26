from __future__ import annotations

from commander_lab.engine.rules.bridge import ExternalRulesAdapter
from commander_lab.models import ENGINE_PROTOCOL_VERSION, EngineMessageType


def test_protocol_2_exposes_required_provider_messages() -> None:
    assert ENGINE_PROTOCOL_VERSION == "2.0.0"
    required = {
        "start_engine",
        "get_capabilities",
        "get_provider_version",
        "import_deck",
        "create_commander_game",
        "add_player",
        "start_game",
        "get_game_state",
        "get_legal_actions",
        "submit_action",
        "pass_priority",
        "select_targets",
        "choose_modes",
        "order_triggers",
        "resolve_mulligan",
        "concede",
        "export_event_log",
        "export_replay",
        "shutdown_game",
        "shutdown_engine",
    }
    assert required <= {kind.value for kind in EngineMessageType}


def test_external_adapter_exposes_required_provider_methods() -> None:
    required = {
        "start_engine",
        "get_capabilities",
        "get_provider_version",
        "import_deck",
        "create_commander_game",
        "add_player",
        "start_game",
        "get_game_state",
        "get_legal_actions",
        "submit_action",
        "pass_priority",
        "select_targets",
        "choose_modes",
        "order_triggers",
        "resolve_mulligan",
        "concede",
        "export_event_log",
        "export_replay",
        "shutdown_game",
        "shutdown_engine",
    }
    assert required <= set(dir(ExternalRulesAdapter))
