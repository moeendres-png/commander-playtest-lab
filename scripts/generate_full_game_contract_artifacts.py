from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    ExternalPilotDecisionPolicy,
    FullGameConformanceResult,
    FullGamePilotBinding,
    FullGameReplayGate,
)
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    FullGameBatchRecord,
    FullGameBatchReport,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/xmage-full-game"


def _write(name: str, payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    schemas = {
        "FULL_GAME_PILOT_BINDING_SCHEMA.json": FullGamePilotBinding.model_json_schema(),
        "FULL_GAME_CONFORMANCE_RESULT_SCHEMA.json": FullGameConformanceResult.model_json_schema(),
        "FULL_GAME_REPLAY_GATE_SCHEMA.json": FullGameReplayGate.model_json_schema(),
        "FULL_GAME_BATCH_CASE_SCHEMA.json": FullGameBatchCase.model_json_schema(),
        "FULL_GAME_BATCH_RECORD_SCHEMA.json": FullGameBatchRecord.model_json_schema(),
        "FULL_GAME_BATCH_REPORT_SCHEMA.json": FullGameBatchReport.model_json_schema(),
    }
    for name, schema in schemas.items():
        _write(name, schema)

    invariant = {
        "schema_version": "xmage-full-game-architecture-invariant-report-1.0.0",
        "lane": FULL_GAME_LANE,
        "decision_protocol_version": FULL_GAME_DECISION_PROTOCOL_VERSION,
        "operational_pod_size": 4,
        "rules_authority": "xmage",
        "decision_authority": "commander_lab_external_pilots",
        "supported_decision_classes": sorted(ExternalPilotDecisionPolicy._SUPPORTED_CLASSES),
        "unknown_decision_class_behavior": "fail_closed",
        "structural_decision_authority": False,
        "tactical_decision_authority": False,
        "xmage_ai_decision_authority": False,
        "random_or_default_discretionary_fallback": False,
        "actor_scoped_hidden_information": True,
        "opponent_hand_visibility_to_actor": False,
        "library_order_visibility": False,
        "state_injection_supported": False,
        "scenario_injection_supported": False,
        "one_isolated_jvm_per_game": True,
        "rules_randomness_seeded_in_xmage": True,
        "bit_exact_replay_preclaimed": False,
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "official_gameplay_evidence_consumed": False,
        "holdout_consumed": False,
        "canonical_data_mutated": False,
    }
    _write("ARCHITECTURE_INVARIANT_REPORT.json", invariant)


if __name__ == "__main__":
    main()
