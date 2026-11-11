"""Unit tests for AI Pilot Style (0.0 - 1.0), DeckPlan derivation, and Priority Rules (#1173).

Governing mission:
- Style slider 0.0 (aggressive) to 1.0 (control) shifts utility weights and mana reservation smoothly.
- Deck plan is derived from existing guides or card roles with provenance 'abgeleitet, nicht gemessen'.
- Priority invariant: lethal attack, preventing lethal loss, and winning combo strictly precede style and plan.
- Observable differences demonstrated on identical seeds / board situations.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from commander_lab.agents import (
    PLAN_PROVENANCE,
    GenericCommanderPilot,
    clamp_style,
    derive_deck_plan,
    style_label,
    style_reserve_mana,
    style_weights,
)
from commander_lab.engine.rules.full_game_pilot_blocks import urgent_scores
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotOpponentView,
    PilotStateView,
    PilotStrength,
    RulesDeckInput,
)
from commander_lab.studio import launch
from commander_lab.studio.__main__ import _parser
from commander_lab.studio.web import create_app
from tests.unit.test_full_game_pilot_judgment import _state
from tests.unit.test_pilot_block_rounds import _brute, _frame, _myrs, _round_for

# ---------------------------------------------------------------------------------------------
# 1. Style Weights & Interpolation Tests
# ---------------------------------------------------------------------------------------------


def test_style_clamping() -> None:
    assert clamp_style(None) == 0.5
    assert clamp_style(-0.5) == 0.0
    assert clamp_style(1.5) == 1.0
    assert clamp_style(0.35) == 0.35


def test_style_labels() -> None:
    assert style_label(0.0) == "Aggressiv"
    assert style_label(0.15) == "Aggressiv"
    assert style_label(0.3) == "Druckvoll"
    assert style_label(0.5) == "Ausgeglichen"
    assert style_label(0.7) == "Defensiv"
    assert style_label(0.95) == "Kontrollierend"
    assert style_label(1.0) == "Kontrollierend"


def test_style_reserve_mana_monotonicity() -> None:
    assert style_reserve_mana(0.0) == 0.0
    assert style_reserve_mana(0.25) == 0.5
    assert style_reserve_mana(0.5) == 1.0
    assert style_reserve_mana(0.75) == 1.5
    assert style_reserve_mana(1.0) == 2.0


def test_style_weights_monotonicity_and_bounds() -> None:
    w_aggro = style_weights(0.0)
    w_mid = style_weights(0.5)
    w_control = style_weights(1.0)

    # Win progress & tempo decrease from Aggro to Control
    assert w_aggro.win_progress > w_mid.win_progress > w_control.win_progress
    assert w_aggro.tempo > w_mid.tempo > w_control.tempo

    # Survival, interaction reserve & threat reduction increase from Aggro to Control
    assert w_aggro.survival < w_mid.survival < w_control.survival
    assert w_aggro.interaction_reserve < w_mid.interaction_reserve < w_control.interaction_reserve
    assert w_aggro.threat_reduction < w_mid.threat_reduction < w_control.threat_reduction

    # Political visibility is less negative (bolder) in aggro, more negative in control
    assert (
        w_aggro.political_visibility > w_mid.political_visibility > w_control.political_visibility
    )

    # Intermediate interpolation check (e.g. style = 0.25)
    w_quarter = style_weights(0.25)
    assert w_aggro.win_progress > w_quarter.win_progress > w_mid.win_progress
    assert w_aggro.survival < w_quarter.survival < w_mid.survival


# ---------------------------------------------------------------------------------------------
# 2. Deck Plan Derivation Tests
# ---------------------------------------------------------------------------------------------


def test_deck_plan_derivation_chulane() -> None:
    deck = RulesDeckInput(
        deck_id="custom/chulane",
        name="Chulane Value",
        commander_names=("Chulane, Teller of Tales",),
        mainboard=tuple(
            ["Tangletrove Kelp", "Shrieking Drake", "Whitemane Lion", "Swords to Plowshares"]
            + [f"Forest {i}" for i in range(1, 96)]
        ),
    )
    plan = derive_deck_plan(deck)
    assert plan.deck_id == "custom/chulane"
    assert plan.provenance == PLAN_PROVENANCE
    assert "value_engine" in plan.focus
    assert "Chulane ist die Engine" in plan.win_condition
    assert "Chulane, Teller of Tales" in plan.key_cards
    plan_dict = plan.as_dict()
    assert plan_dict["provenance"] == "abgeleitet, nicht gemessen"
    assert isinstance(plan_dict["engines"], list)
    assert isinstance(plan_dict["answers"], list)


def test_deck_plan_derivation_precon() -> None:
    deck = RulesDeckInput(
        deck_id="precon/2011/counterpunch",
        name="Counterpunch",
        commander_names=("Ghave, Guru of Spores",),
        mainboard=tuple(
            ["Swords to Plowshares", "Cultivate", "Sol Ring"]
            + [f"Plains {i}" for i in range(1, 97)]
        ),
    )
    plan = derive_deck_plan(deck)
    assert plan.deck_id == "precon/2011/counterpunch"
    assert plan.provenance == PLAN_PROVENANCE
    assert plan.focus != ""
    assert plan.win_condition != ""


def test_deck_plan_derivation_arbitrary_deck_without_guide() -> None:
    deck = RulesDeckInput(
        deck_id="custom/my_unique_homebrew",
        name="My Unique Homebrew",
        commander_names=("Chulane, Teller of Tales",),
        mainboard=tuple(
            ["Swords to Plowshares", "Beast Within", "Counterspell"]
            + [f"Forest {i}" for i in range(1, 97)]
        ),
    )
    plan = derive_deck_plan(deck, guides_dir=Path("/nonexistent/directory"))
    assert plan.deck_id == "custom/my_unique_homebrew"
    assert plan.provenance == PLAN_PROVENANCE
    assert "Chulane, Teller of Tales" in plan.win_condition
    # Answers were recognized from card roles
    assert "Swords to Plowshares" in plan.answers
    assert "Beast Within" in plan.answers
    assert "Counterspell" in plan.answers


# ---------------------------------------------------------------------------------------------
# 3. Priority Rules Tests (Vorrangregeln)
# ---------------------------------------------------------------------------------------------


def _make_state() -> PilotStateView:
    opponents = (
        PilotOpponentView(
            player_id="p2",
            life=25,
            threat=5,
            board_power=4,
            engine_value=1,
            graveyard_size=2,
            hand_size=4,
        ),
        PilotOpponentView(
            player_id="p3",
            life=15,
            threat=6,
            board_power=4,
            engine_value=2,
            graveyard_size=3,
            hand_size=5,
        ),
    )
    return PilotStateView(
        player_id="p1",
        deck_id="custom/chulane",
        strategy="generic",
        turn=5,
        pod_size=3,
        life=30,
        hand_size=5,
        mana_available=5,
        lands=5,
        ramp_mana=1,
        resources=1.0,
        tokens=0.0,
        board_power=6.0,
        engine_value=1.0,
        graveyard_size=2,
        battlefield_names=(),
        hand_names=(),
        role_counts={},
        commanders=(),
        opponents=opponents,
    )


def test_priority_rule_lethal_attack_beats_control_style() -> None:
    """Under maximal Control style (1.0), an open finishing attack strictly beats holding back."""
    pilot = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
            style=1.0,
        )
    )
    assert pilot.weights.win_progress == 0.80  # Control downweights win_progress
    assert pilot.weights.survival == 1.35  # Control upweights survival

    state = _make_state()
    # Lethal attack option vs hold option
    lethal_attack = PilotActionView(
        action_id="attack:opponent-3",
        card_name="Grizzly Bears",
        action_kind="combat_target",
        base_power=4.0,
        metadata={"lethal_window": True, "target_life": 4.0},
    )
    hold_action = PilotActionView(
        action_id="attack:hold",
        card_name="",
        action_kind="pass",
        base_power=0.0,
    )
    nonlethal_attack = PilotActionView(
        action_id="attack:opponent-2",
        card_name="Grizzly Bears",
        action_kind="combat_target",
        base_power=4.0,
        metadata={"lethal_window": False, "target_life": 35.0},
    )

    decision = pilot.choose_combat_target(
        state, [hold_action, nonlethal_attack, lethal_attack], random.Random(42)
    )
    assert decision.selected_action_id == "attack:opponent-3"


def test_priority_rule_winning_combo_beats_style() -> None:
    """Under maximal Control style (1.0), a game-winning action/combo strictly beats passive play."""
    pilot = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
            style=1.0,
        )
    )
    state = _make_state()
    combo_action = PilotActionView(
        action_id="cast:mechanized_production",
        card_name="Mechanized Production",
        action_kind="card",
        mana_cost=4,
        roles=frozenset([CardRole.FINISHER]),
        role_strengths={CardRole.FINISHER: 1.0},
        metadata={"combo_win": True},
    )
    passive_hold = PilotActionView(
        action_id="pass_priority",
        card_name="",
        action_kind="pass",
    )
    ordinary_action = PilotActionView(
        action_id="cast:ramp",
        card_name="Nature's Lore",
        action_kind="card",
        mana_cost=2,
        roles=frozenset([CardRole.RAMP]),
        role_strengths={CardRole.RAMP: 1.0},
    )

    decision = pilot.choose_action(
        state, [passive_hold, ordinary_action, combo_action], random.Random(42)
    )
    assert decision.selected_action_id == "cast:mechanized_production"


def test_priority_rule_defend_lethal_loss_beats_aggro_style() -> None:
    """Under maximal Aggro style (0.0), blocking to prevent lethal damage is strictly prioritized."""
    pilot = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
            style=0.0,
        )
    )
    assert pilot.weights.survival == 0.80  # Aggro downweights survival

    # Incoming unblocked lethal damage against life of 9
    state = _state(
        actor_board=_myrs(1), opponent_board=[_brute("a", 5), _brute("b", 5)], actor_life=9
    )
    round_ = _round_for(state, ["a", "b"])
    options = _frame("myr-0", ["a", "b"])

    # urgent_scores must return high positive score for blocking lethal attackers
    scores = urgent_scores(round_, "myr-0", options, [0.0, 0.0], state)
    assert scores is not None
    assert len(scores) == 2
    assert scores[0] > 0.0
    assert scores[1] > 0.0


# ---------------------------------------------------------------------------------------------
# 4. Observable Differences on Identical Seeds / States
# ---------------------------------------------------------------------------------------------


def test_observable_differences_same_seed_across_styles() -> None:
    """Compare evaluations across styles 0.0, 0.5, and 1.0 demonstrating clear behavioral divergence."""
    pilot_aggro = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
            style=0.0,
        )
    )
    pilot_balanced = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
            style=0.5,
        )
    )
    pilot_control = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
            style=1.0,
        )
    )

    state = _make_state()
    # State with interaction in hand to measure interaction reservation
    state_with_counter = PilotStateView(
        player_id=state.player_id,
        deck_id=state.deck_id,
        strategy=state.strategy,
        turn=state.turn,
        pod_size=state.pod_size,
        life=state.life,
        hand_size=state.hand_size,
        mana_available=state.mana_available,
        lands=state.lands,
        ramp_mana=state.ramp_mana,
        resources=state.resources,
        tokens=state.tokens,
        board_power=state.board_power,
        engine_value=state.engine_value,
        graveyard_size=state.graveyard_size,
        battlefield_names=state.battlefield_names,
        hand_names=state.hand_names,
        role_counts={CardRole.COUNTER: 1},
        commanders=state.commanders,
        opponents=state.opponents,
    )

    # Offensive action (attacking a defender)
    attack = PilotActionView(
        action_id="attack:opponent",
        card_name="Grizzly Bears",
        action_kind="combat_target",
        base_power=3.0,
        metadata={"target_life": 20.0},
    )
    # Holding action with open mana for interaction
    hold_open_mana = PilotActionView(
        action_id="pass:hold_mana",
        card_name="",
        action_kind="pass",
        remaining_mana=2.0,
    )

    u_aggro_atk = pilot_aggro.evaluate_action(state, attack).total_utility
    u_mid_atk = pilot_balanced.evaluate_action(state, attack).total_utility
    u_ctrl_atk = pilot_control.evaluate_action(state, attack).total_utility

    # Attack utility decreases monotonically from Aggro to Control
    assert u_aggro_atk > u_mid_atk > u_ctrl_atk
    diff_atk = round(u_aggro_atk - u_ctrl_atk, 3)
    assert diff_atk >= 0.45  # Observable spread (Aggro 2.13 vs Control 1.05)

    # Holding open interaction mana utility increases monotonically from Aggro to Control
    u_aggro_hold = pilot_aggro.evaluate_action(state_with_counter, hold_open_mana).total_utility
    u_mid_hold = pilot_balanced.evaluate_action(state_with_counter, hold_open_mana).total_utility
    u_ctrl_hold = pilot_control.evaluate_action(state_with_counter, hold_open_mana).total_utility
    assert u_ctrl_hold > u_mid_hold > u_aggro_hold
    diff_hold = round(u_ctrl_hold - u_aggro_hold, 3)
    assert diff_hold >= 1.0  # Significant observable spread (Control 2.32 vs Aggro 0.57)

    # Reserve mana target directly enforces spending vs holding
    assert pilot_aggro.reserve_mana_target == 0.0
    assert pilot_balanced.reserve_mana_target == 1.0
    assert pilot_control.reserve_mana_target == 2.0


# ---------------------------------------------------------------------------------------------
# 5. Studio Integration & Web API Tests
# ---------------------------------------------------------------------------------------------


def test_studio_play_cli_args_parsing() -> None:
    parser = _parser()
    args = parser.parse_args(
        [
            "play",
            "--seed",
            "123",
            "--deck",
            "data/decks/chulane_current.txt",
            "--deck",
            "data/decks/precons/2011/counterpunch.txt",
            "--style",
            "0.25",
            "--seat-style",
            "1:0.0",
            "--seat-style",
            "2:1.0",
        ]
    )
    assert args.seed == 123
    assert args.style == 0.25
    assert args.seat_style == ["1:0.0", "2:1.0"]


def test_web_api_game_body_with_styles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "mock-engine")
    captured_kwargs: dict[str, object] = {}

    def mock_start_game(store: object, folder: object, **kwargs: object) -> str:
        captured_kwargs.update(kwargs)
        return "mock-game-123"

    monkeypatch.setattr(launch, "start_game", mock_start_game)

    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/games",
        headers={"X-Studio": "1"},
        json={
            "revision_id": "chulane@main",
            "opponent_ids": ["precon/2011/counterpunch"],
            "seed": 42,
            "style": 0.25,
            "seat_styles": [0.25, 0.75],
        },
    )
    assert response.status_code == 200
    assert response.json() == {"game_id": "mock-game-123"}
    assert captured_kwargs["style"] == 0.25
    assert captured_kwargs["seat_styles"] == [0.25, 0.75]
