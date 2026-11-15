from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.models import (
    CounterfactualAction,
    CounterfactualBranchpoint,
    CounterfactualEngineMode,
)


def test_counterfactual_branchpoint_validation_level_must_match_engine() -> None:
    with pytest.raises(ValidationError, match="requires validation_level=tactical_oracle"):
        CounterfactualBranchpoint(
            branchpoint_id="b1",
            source_run_id="run",
            source_path="events.jsonl",
            game_id="g1",
            event_offset=0,
            actor_id="p1",
            state_hash="1" * 64,
            replay_prefix_hash="2" * 64,
            available_actions=(CounterfactualAction(action_id="pass"),),
            chosen_action="pass",
            engine_mode=CounterfactualEngineMode.TACTICAL_ORACLE,
            validation_level="structural_model_estimates",
        )
