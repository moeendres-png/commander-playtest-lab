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
    XmageFullGameRunner,
)
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    FullGameBatchRecord,
    FullGameBatchReport,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/xmage-full-game"

# The primary decision mode (one own deck, three opponents). It is a decision
# policy, not the lane's range: the range comes from the runner below.
PRIMARY_DECISION_POD_SIZE = 4


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

    _write("ARCHITECTURE_INVARIANT_REPORT.json", invariant_report())


def invariant_report() -> dict[str, Any]:
    """The lane's invariant report; the player range is the runner's own."""
    minimum, maximum = XmageFullGameRunner.MIN_PLAYERS, XmageFullGameRunner.MAX_PLAYERS
    return {
        "schema_version": "xmage-full-game-architecture-invariant-report-1.2.0",
        # C3: every flag below is the lane's design contract, not a runtime
        # observation; per-run evidence lives in XMAGE_FULL_GAME_CONFORMANCE.json
        # ("claim_basis") and HIDDEN_INFORMATION_BOUNDARY_REPORT.json ("observed").
        "evidence_status": "DECLARED_CONTRACT",
        "lane": FULL_GAME_LANE,
        "decision_protocol_version": FULL_GAME_DECISION_PROTOCOL_VERSION,
        "min_players": minimum,
        "max_players": maximum,
        "operational_pod_sizes": list(range(minimum, maximum + 1)),
        "player_range_source": "XmageFullGameRunner.MIN_PLAYERS..MAX_PLAYERS",
        "primary_decision_pod_size": PRIMARY_DECISION_POD_SIZE,
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


if __name__ == "__main__":
    main()
