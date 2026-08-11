from __future__ import annotations

from commander_lab.engine.rules import TacticalRulesAdapter, load_project_rules_decks
from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameState,
    GameStatus,
    LegalAction,
    PlayerState,
    RulesGameRequest,
    TacticalScenario,
    TurnPhase,
    ZoneState,
)


def test_tactical_adapter_loads_decks_and_reproduces_starting_state(repo_root) -> None:
    adapter = TacticalRulesAdapter()
    decks = load_project_rules_decks(repo_root)
    rogshai = adapter.load_deck(decks["rogshai/current"])
    request = RulesGameRequest(
        game_id="a",
        deck_handles=(rogshai.handle_id,) * 4,
        seed=12345,
    )
    a = adapter.start_commander_game(request)
    b = adapter.start_commander_game(request.model_copy(update={"game_id": "b"}))
    assert [player.zones for player in a.state.players] == [
        player.zones for player in b.state.players
    ]
    assert all(len(player.zones.hand) == 7 for player in a.state.players)
    assert len(a.state.players) == 4


def test_tactical_adapter_exposes_and_accepts_only_legal_actions() -> None:
    adapter = TacticalRulesAdapter()
    action = LegalAction(
        action_id="pass",
        actor_id="p1",
        action_type=ActionType.PASS_PRIORITY,
    )
    state = GameState(
        game_id="scenario",
        seed=1,
        status=GameStatus.IN_PROGRESS,
        turn_number=1,
        active_player_id="p1",
        priority_player_id="p1",
        phase=TurnPhase.PRECOMBAT_MAIN,
        players=(
            PlayerState(player_id="p1", seat=0, zones=ZoneState()),
            PlayerState(player_id="p2", seat=1, zones=ZoneState()),
        ),
        legal_actions=(action,),
    )
    session = adapter.create_scenario(
        TacticalScenario(scenario_id="pass", description="pass", state=state)
    )
    assert adapter.get_legal_actions(session.session_id) == (action,)
    next_state = adapter.submit_action(
        session.session_id,
        ActionProposal(
            proposal_id="p",
            actor_id="p1",
            legal_action_id="pass",
            action_type=ActionType.PASS_PRIORITY,
        ),
    )
    assert next_state.priority_player_id == "p2"
    assert len(adapter.get_logs(session.session_id).events) == 2
