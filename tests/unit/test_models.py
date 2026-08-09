from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.models import (
    ActionProposal,
    ActionType,
    CommanderConfiguration,
    GameState,
    PlayerState,
    SimulationConfig,
    ZoneState,
)


def test_partner_configuration_requires_two_commanders() -> None:
    with pytest.raises(ValidationError):
        CommanderConfiguration(commanders=("Ishai, Ojutai Dragonspeaker",), uses_partner=True)


def test_non_partner_configuration_requires_one_commander() -> None:
    with pytest.raises(ValidationError):
        CommanderConfiguration(
            commanders=("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"),
            uses_partner=False,
        )


def test_game_state_rejects_unknown_active_player() -> None:
    with pytest.raises(ValidationError):
        GameState(
            game_id="game-1",
            seed=1,
            players=(PlayerState(player_id="p1", seat=0, zones=ZoneState()),),
            active_player_id="p2",
        )


def test_action_proposal_is_structured_and_immutable() -> None:
    proposal = ActionProposal(
        proposal_id="proposal-1",
        actor_id="p1",
        action_type=ActionType.CAST_SPELL,
        source_object_id="card-1",
        target_ids=("permanent-2",),
        decision_tier=2,
        policy_name="KorvoldPilot",
    )
    assert proposal.target_ids == ("permanent-2",)
    with pytest.raises(ValidationError):
        proposal.decision_tier = 3  # type: ignore[misc]


def test_simulation_config_requires_one_deck_per_seat() -> None:
    with pytest.raises(ValidationError):
        SimulationConfig(
            seed=1,
            pod_size=4,
            deck_ids=("a", "b", "c"),
            card_data_hash="0" * 64,
        )


def test_requested_phase2_models_are_publicly_importable() -> None:
    from commander_lab.models import (
        ActionProposal,
        CardContribution,
        CardIdentity,
        Collection,
        CommanderConfiguration,
        Deck,
        GameEvent,
        GameState,
        LegalAction,
        MatchResult,
        OpponentProfile,
        PhysicalCard,
        PlayerState,
        SimulationConfig,
        SimulationRun,
        UncertaintyModel,
        UpgradeProposal,
        ZoneState,
    )

    assert all(
        model is not None
        for model in (
            CardIdentity,
            PhysicalCard,
            Collection,
            Deck,
            CommanderConfiguration,
            OpponentProfile,
            UncertaintyModel,
            GameState,
            PlayerState,
            ZoneState,
            LegalAction,
            ActionProposal,
            GameEvent,
            SimulationConfig,
            SimulationRun,
            MatchResult,
            CardContribution,
            UpgradeProposal,
        )
    )


def test_pilot_config_count_must_match_pod_size() -> None:
    from commander_lab.models import PilotConfig, StructuralMatchConfig

    with pytest.raises(ValidationError):
        StructuralMatchConfig(
            match_id="pilot-count",
            seed=1,
            deck_ids=("a", "b"),
            pilot_configs=(PilotConfig(),),
        )


def test_phase4_pilot_models_are_publicly_importable() -> None:
    from commander_lab.models import (
        PilotActionView,
        PilotCommanderView,
        PilotConfig,
        PilotDecision,
        PilotDecisionMode,
        PilotOpponentView,
        PilotStateView,
        PilotStrength,
        PilotUtilityBreakdown,
        PilotUtilityWeights,
    )

    assert all(
        item is not None
        for item in (
            PilotActionView,
            PilotCommanderView,
            PilotConfig,
            PilotDecision,
            PilotDecisionMode,
            PilotOpponentView,
            PilotStateView,
            PilotStrength,
            PilotUtilityBreakdown,
            PilotUtilityWeights,
        )
    )
