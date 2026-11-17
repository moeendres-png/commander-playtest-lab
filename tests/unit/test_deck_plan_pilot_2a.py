"""Unit tests for PR 2A: memoized Spellbook-aware DeckPlan, O(1) pilot awareness,
actor-scoped library tutor ranking, and simulation plan telemetry (Refs #1167).
"""

from __future__ import annotations

import json
from pathlib import Path

from commander_lab.agents import (
    PLAN_PROVENANCE,
    GenericCommanderPilot,
    derive_deck_plan,
)
from commander_lab.agents.pilots import _norm_plan_name
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
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
from commander_lab.studio import games, strength, strength_view
from commander_lab.studio.simulations import (
    GameSummary,
    aggregate_batch_results,
    extract_game_log_telemetry,
)


def _chulane_deck() -> RulesDeckInput:
    return RulesDeckInput(
        deck_id="custom/chulane_2a",
        name="Chulane Combo 2A",
        commander_names=("Chulane, Teller of Tales",),
        mainboard=tuple(
            [
                "Shrieking Drake",
                "Whitemane Lion",
                "Aluren",
                "Intruder Alarm",
                "Cloudstone Curio",
                "Worldly Tutor",
                "Swords to Plowshares",
                "Heroic Intervention",
            ]
            + [f"Forest {i}" for i in range(1, 92)]
        ),
    )


def _pilot_state(
    *,
    battlefield_names: tuple[str, ...] = (),
    hand_names: tuple[str, ...] = (),
    stack_pressure: float = 0.0,
    max_threat: float = 4.0,
) -> PilotStateView:
    return PilotStateView(
        player_id="p1",
        deck_id="custom/chulane_2a",
        strategy="generic",
        turn=6,
        pod_size=4,
        life=35,
        hand_size=len(hand_names),
        mana_available=6,
        lands=5,
        ramp_mana=1,
        resources=2.0,
        tokens=0.0,
        board_power=3.0,
        engine_value=1.0,
        graveyard_size=1,
        stack_pressure=stack_pressure,
        battlefield_names=battlefield_names,
        hand_names=hand_names,
        role_counts={},
        commanders=(),
        opponents=(
            PilotOpponentView(
                player_id="p2",
                life=35,
                threat=max_threat,
                board_power=4,
                engine_value=1,
                graveyard_size=1,
                hand_size=4,
            ),
        ),
    )


# ---------------------------------------------------------------------------------------------
# 1. Spellbook Combo Derivation & Memoization
# ---------------------------------------------------------------------------------------------


def test_spellbook_combo_extraction_any_of_and_dfc_normalization(tmp_path: Path) -> None:
    sb_path = tmp_path / "spellbook.json"
    sb_path.write_text(
        json.dumps(
            {
                "combos": [
                    {
                        "combo_id": "sb-win-1",
                        "cards": ["Chulane, Teller of Tales", "Shrieking Drake"],
                        "any_of": [["Aluren", "Earthcraft"]],
                        "result": "Infinite casts, Win the game",
                        "tier": "cEDH",
                    },
                    {
                        "combo_id": "sb-dfc-1",
                        "cards": ["Bala Ged Recovery", "Intruder Alarm"],
                        "result": "Value loop",
                        "tier": "High",
                    },
                    {
                        "combo_id": "sb-missing",
                        "cards": ["Thassa's Oracle", "Demonic Consultation"],
                        "result": "Win the game",
                        "tier": "cEDH",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    deck = RulesDeckInput(
        deck_id="custom/dfc_test",
        name="DFC Combo Deck",
        commander_names=("Chulane, Teller of Tales",),
        mainboard=tuple(
            [
                "Shrieking Drake",
                "Aluren",
                "Intruder Alarm",
                "Bala Ged Recovery // Bala Ged Sanctuary",
                "Heroic Intervention",
            ]
            + [f"Island {i}" for i in range(1, 95)]
        ),
    )

    plan = derive_deck_plan(deck, guides_dir=tmp_path / "no_guides", spellbook_path=sb_path)
    assert plan.provenance == PLAN_PROVENANCE
    combo_ids = [c["combo_id"] for c in plan.combos]
    assert combo_ids == ["sb-win-1", "sb-dfc-1"]
    assert "sb-missing" not in combo_ids
    assert "Aluren" in plan.combo_cards
    assert "Bala Ged Recovery // Bala Ged Sanctuary" in plan.combo_cards
    assert any(axis.startswith("combo (2") for axis in plan.win_axes)
    assert "Shrieking Drake" in plan.protection_targets
    assert "Shrieking Drake" in plan.tutor_priorities

    # Memoization cache hit returns identical frozen instance, while as_dict() returns fresh copies
    plan2 = derive_deck_plan(deck, guides_dir=tmp_path / "no_guides", spellbook_path=sb_path)
    assert plan2 is plan
    d1 = plan.as_dict()
    d1["engines"].append("Mutated Card")  # type: ignore[union-attr]
    d1["combos"][0]["cards"].append("Mutated")  # type: ignore[index]
    d2 = plan.as_dict()
    assert "Mutated Card" not in d2["engines"]  # type: ignore[operator]
    assert "Mutated" not in d2["combos"][0]["cards"]  # type: ignore[index]


def test_real_spellbook_matches_chulane_combos() -> None:
    plan = derive_deck_plan(_chulane_deck())
    assert len(plan.combos) >= 1
    assert "Shrieking Drake" in plan.combo_cards
    assert "Chulane, Teller of Tales" in plan.combo_cards
    partners = dict(plan.combo_partners)
    assert "Shrieking Drake" in partners and len(partners["Shrieking Drake"]) >= 1


# ---------------------------------------------------------------------------------------------
# 2. Pre-Indexed BasePilot Awareness & Baseline Identity
# ---------------------------------------------------------------------------------------------


def test_base_pilot_baseline_identical_when_deck_plan_is_none() -> None:
    baseline = GenericCommanderPilot(
        PilotConfig(pilot_name="auto", strength=PilotStrength.STRONG, deck_plan=None)
    )
    empty_plan = GenericCommanderPilot(
        PilotConfig(pilot_name="auto", strength=PilotStrength.STRONG, deck_plan={})
    )
    state = _pilot_state(battlefield_names=("Sol Ring",), hand_names=("Shrieking Drake",))
    action = PilotActionView(
        action_id="cast:drake",
        card_name="Shrieking Drake",
        action_kind="card",
        mana_cost=1.0,
        roles=frozenset({CardRole.ENGINE}),
    )
    b1 = baseline.evaluate_action(state, action)
    b2 = empty_plan.evaluate_action(state, action)
    assert b1.components() == b2.components()
    assert b1.total_utility == b2.total_utility


def test_base_pilot_rewards_completing_combo_and_protecting_own_target() -> None:
    plan_dict: dict[str, object] = {
        "deck_id": "custom/chulane_2a",
        "focus": "combo",
        "win_condition": "Chulane + Shrieking Drake",
        "engines": ["Chulane, Teller of Tales"],
        "answers": ["Counterspell"],
        "key_cards": ["Chulane, Teller of Tales", "Shrieking Drake"],
        "combos": [
            {
                "combo_id": "c1",
                "cards": ["Chulane, Teller of Tales", "Shrieking Drake"],
                "result": "Win",
            }
        ],
        "combo_cards": ["Chulane, Teller of Tales", "Shrieking Drake"],
        "combo_partners": {"Shrieking Drake": ["Chulane, Teller of Tales"]},
        "protection_targets": ["Chulane, Teller of Tales", "Shrieking Drake"],
        "tutor_priorities": ["Shrieking Drake"],
    }
    no_plan = GenericCommanderPilot(
        PilotConfig(pilot_name="auto", strength=PilotStrength.STRONG, deck_plan=None)
    )
    planned = GenericCommanderPilot(
        PilotConfig(pilot_name="auto", strength=PilotStrength.STRONG, deck_plan=plan_dict)
    )

    # Partner Chulane already on battlefield -> casting Shrieking Drake gets strong win_progress boost
    state_board = _pilot_state(battlefield_names=("Chulane, Teller of Tales",))
    cast_drake = PilotActionView(
        action_id="cast:drake",
        card_name="Shrieking Drake",
        action_kind="card",
        mana_cost=1.0,
    )
    u_none = no_plan.evaluate_action(state_board, cast_drake)
    u_plan = planned.evaluate_action(state_board, cast_drake)
    assert u_plan.win_progress > u_none.win_progress + 2.5
    assert u_plan.total_utility > u_none.total_utility

    # Protecting actor-owned Chulane boosts survival; opponent Chulane does NOT
    prot_own = PilotActionView(
        action_id="prot:own",
        card_name="Chulane, Teller of Tales",
        action_kind="protection",
        metadata={"target_is_actor_controlled": True},
    )
    prot_opp = PilotActionView(
        action_id="prot:opp",
        card_name="Chulane, Teller of Tales",
        action_kind="protection",
        metadata={"target_is_actor_controlled": False},
    )
    assert planned.evaluate_action(state_board, prot_own).survival > (
        no_plan.evaluate_action(state_board, prot_own).survival + 0.5
    )
    assert (
        planned.evaluate_action(state_board, prot_opp).survival
        == no_plan.evaluate_action(state_board, prot_opp).survival
    )


def test_opening_hand_pair_bonus_requires_two_lands_and_bottoming_spares_combo_card() -> None:
    plan_dict: dict[str, object] = {
        "combos": [
            {"combo_id": "c1", "cards": ["Chulane, Teller of Tales", "Shrieking Drake"]},
        ],
        "combo_cards": ["Chulane, Teller of Tales", "Shrieking Drake"],
        "combo_partners": {
            "Shrieking Drake": ["Chulane, Teller of Tales"],
            "Chulane, Teller of Tales": ["Shrieking Drake"],
        },
        "key_cards": ["Chulane, Teller of Tales"],
        "engines": [],
    }
    pilot = GenericCommanderPilot(
        PilotConfig(pilot_name="auto", strength=PilotStrength.STRONG, deck_plan=plan_dict)
    )
    no_plan = GenericCommanderPilot(
        PilotConfig(pilot_name="auto", strength=PilotStrength.STRONG, deck_plan=None)
    )
    combo_a = PilotActionView(
        action_id="c1", card_name="Chulane, Teller of Tales", action_kind="card"
    )
    combo_b = PilotActionView(action_id="c2", card_name="Shrieking Drake", action_kind="card")
    filler = PilotActionView(action_id="f1", card_name="Grizzly Bears", action_kind="card")
    land = PilotActionView(
        action_id="l1", card_name="Forest", action_kind="card", metadata={"is_land": True}
    )

    one_land = [land, combo_a, combo_b, filler]
    two_lands = [land, land, combo_a, combo_b]
    cmd = ("Chulane, Teller of Tales",)
    diff_one_land = pilot.opening_hand_specialist_bonus(
        one_land, cmd
    ) - no_plan.opening_hand_specialist_bonus(one_land, cmd)
    diff_two_lands = pilot.opening_hand_specialist_bonus(
        two_lands, cmd
    ) - no_plan.opening_hand_specialist_bonus(two_lands, cmd)
    # Two-land hand additionally qualifies for the complete combo-pair bonus (+0.75)
    assert diff_two_lands > diff_one_land + 0.5

    # Bottoming discards filler rather than combo partner
    bottomed = pilot.choose_bottom_cards(
        (filler, combo_b),
        1,
        commander_names=cmd,
        extra_lands=2,
    )
    assert bottomed == ("f1",)


# ---------------------------------------------------------------------------------------------
# 3. Actor-Scoped Library Tutor Search Ranking (choices.py)
# ---------------------------------------------------------------------------------------------


def _tutor_request(
    *,
    actor_bf: list[str],
    actor_hand: list[str],
    opp_hand: list[str],
    library_options: list[tuple[str, str]],
) -> dict[str, object]:
    return {
        "decision_id": "opaque-tutor-1",
        "decision_offset": 1,
        "actor_id": "p0",
        "decision_class": "target",
        "seat": 0,
        "prompt": "Search your library for a card",
        "context": {"outcome": "neutral"},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "source_object": {"source_name": "Worldly Tutor", "ability_type": "spell"},
        "pilot_state": {
            "game_id": "g-tutor",
            "actor_id": "p0",
            "seat": 0,
            "turn_number": 4,
            "active_player_id": "p0",
            "priority_player_id": "p0",
            "phase": "precombat_main",
            "step": "precombat_main",
            "stack": [],
            "players": [
                {
                    "player_id": "p0",
                    "seat": 0,
                    "life": 40,
                    "hand_count": len(actor_hand),
                    "library_count": 70,
                    "graveyard_count": 0,
                    "battlefield": [
                        {"object_id": f"b{i}", "name": name, "tapped": False}
                        for i, name in enumerate(actor_bf)
                    ],
                    "hand": [
                        {"object_id": f"h{i}", "name": name} for i, name in enumerate(actor_hand)
                    ],
                    "command": [],
                    "graveyard": [],
                    "mana_pool": {},
                },
                {
                    "player_id": "p1",
                    "seat": 1,
                    "life": 40,
                    "hand_count": len(opp_hand),
                    "library_count": 70,
                    "graveyard_count": 0,
                    "battlefield": [],
                    "hand": [
                        {"object_id": f"oh{i}", "name": name} for i, name in enumerate(opp_hand)
                    ],
                    "command": [],
                    "graveyard": [],
                },
            ],
        },
        "legal_options": [
            {
                "option_id": oid,
                "label": name,
                "option_type": "target_card",
                "metadata": {"zone": "library", "zone_index": idx, "name": name},
            }
            for idx, (oid, name) in enumerate(library_options)
        ],
    }


def test_library_tutor_ranks_completing_combo_over_generic_and_ignores_opponent_zones() -> None:
    plan_dict: dict[str, object] = {
        "combos": [
            {"combo_id": "c-win", "cards": ["Aluren", "Shrieking Drake"], "result": "Win"},
            {
                "combo_id": "c-alt",
                "cards": ["Intruder Alarm", "Cloudstone Curio"],
                "result": "Loop",
            },
        ],
        "combo_cards": ["Aluren", "Shrieking Drake", "Intruder Alarm", "Cloudstone Curio"],
        "combo_partners": {
            "Shrieking Drake": ["Aluren"],
            "Aluren": ["Shrieking Drake"],
            "Intruder Alarm": ["Cloudstone Curio"],
            "Cloudstone Curio": ["Intruder Alarm"],
        },
        "tutor_priorities": ["Intruder Alarm", "Shrieking Drake", "Sol Ring"],
    }
    config = PilotConfig(
        pilot_name="auto",
        strength=PilotStrength.STRONG,
        mode=PilotDecisionMode.DETERMINISTIC,
        deck_plan=plan_dict,
    )
    binding = FullGamePilotBinding(
        seat=1,
        deck_id="custom/chulane_2a",
        strategy="generic",
        commander_names=("Chulane, Teller of Tales",),
        config=config,
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    opp_config = PilotConfig(
        pilot_name="auto",
        strength=PilotStrength.STRONG,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    opp_binding = FullGamePilotBinding(
        seat=2,
        deck_id="opp",
        strategy="generic",
        commander_names=("Osgir",),
        config=opp_config,
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    policy = ExternalPilotDecisionPolicy(
        (
            _RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)),
            _RuntimePilot(binding=opp_binding, pilot=GenericCommanderPilot(opp_config)),
        ),
        42,
    )  # type: ignore[arg-type]

    # Actor controls Aluren on board -> Shrieking Drake completes c-win (Tier 3) and beats Intruder Alarm (Tier 2)
    req_completes = _tutor_request(
        actor_bf=["Aluren"],
        actor_hand=[],
        opp_hand=[],
        library_options=[
            ("opt-bears", "Grizzly Bears"),
            ("opt-alarm", "Intruder Alarm"),
            ("opt-drake", "Shrieking Drake"),
        ],
    )
    resp = policy.decide(req_completes)
    assert resp["selected_option_ids"] == ["opt-drake"]

    # Negative hidden-info control: opponent has Cloudstone Curio in their hand dict; actor has neither
    # Aluren nor Cloudstone Curio -> actor MUST NOT treat Cloudstone Curio as visible to complete c-alt.
    # Instead, rank falls back to tutor_priorities (Intruder Alarm outranks Cloudstone Curio).
    req_hidden = _tutor_request(
        actor_bf=[],
        actor_hand=[],
        opp_hand=["Cloudstone Curio"],
        library_options=[
            ("opt-bears", "Grizzly Bears"),
            ("opt-curio", "Cloudstone Curio"),
            ("opt-alarm", "Intruder Alarm"),
        ],
    )
    resp_hidden = policy.decide(req_hidden)
    assert resp_hidden["selected_option_ids"] == ["opt-alarm"]
    assert _norm_plan_name("Bala Ged Recovery [a1b2c]") == "bala ged recovery"


# ---------------------------------------------------------------------------------------------
# 4. Simulation Plan Telemetry & Tierliste Weight 0 Invariant
# ---------------------------------------------------------------------------------------------


def test_simulation_plan_telemetry_and_batch_aggregation(tmp_path: Path) -> None:
    plan_dict = {
        "provenance": PLAN_PROVENANCE,
        "combos": [
            {"combo_id": "c1", "cards": ["Chulane, Teller of Tales", "Shrieking Drake"]},
        ],
        "combo_cards": ["Chulane, Teller of Tales", "Shrieking Drake"],
        "key_cards": ["Chulane, Teller of Tales", "Shrieking Drake"],
        "engines": ["Shrieking Drake"],
        "answers": ["Counterspell"],
    }
    header: dict[str, object] = {
        "engine_commit": "f4d12f6e80",
        "pilot": "GenericCommanderPilot 1.0.0",
        "decision_policy": "xmage-full-game-policy-1.0.0",
        "strategy": "generic",
        "seats": [
            {
                "seat": 0,
                "deck_id": "chulane",
                "commanders": ["Chulane, Teller of Tales"],
                "deck_plan": plan_dict,
            },
            {"seat": 1, "deck_id": "opp1", "commanders": ["Osgir"]},
        ],
    }
    rec = games.GameRecorder(tmp_path, "g-plan-1", {**header, "seed": 7})
    # Frame 1: Chulane on battlefield, Shrieking Drake in hand -> combo assembled (hand + board), not deployed
    rec.record(
        {
            "seat": 0,
            "decision_class": "cast_spell",
            "pilot_state": {
                "turn_number": 4,
                "phase": "precombat_main",
                "active_player_id": "p0",
                "players": [
                    {
                        "seat": 0,
                        "player_id": "p0",
                        "life": 40,
                        "hand": [{"name": "Shrieking Drake"}, {"name": "Counterspell"}],
                        "battlefield": [{"name": "Chulane, Teller of Tales", "tapped": False}],
                        "command": [],
                    },
                    {"seat": 1, "player_id": "p1", "life": 40, "hand_count": 7},
                ],
                "stack": [],
            },
            "legal_options": [{"option_id": "o1", "label": "Shrieking Drake"}],
        },
        {"selected_option_ids": ["o1"]},
    )
    # Frame 2: Shrieking Drake resolved onto battlefield -> combo deployed on board on turn 5
    rec.record(
        {
            "seat": 0,
            "decision_class": "priority",
            "pilot_state": {
                "turn_number": 5,
                "phase": "precombat_main",
                "active_player_id": "p0",
                "players": [
                    {
                        "seat": 0,
                        "player_id": "p0",
                        "life": 40,
                        "hand": [{"name": "Counterspell"}],
                        "battlefield": [
                            {"name": "Chulane, Teller of Tales", "tapped": False},
                            {"name": "Shrieking Drake", "tapped": False},
                        ],
                        "command": [],
                    },
                    {"seat": 1, "player_id": "p1", "life": 40, "hand_count": 7},
                ],
                "stack": [],
            },
            "legal_options": [{"option_id": "pass", "label": "Pass priority"}],
        },
        {"selected_option_ids": ["pass"]},
    )
    rec.close({"status": "finished", "winner_seats": [0], "decision_count": 2})

    g1 = extract_game_log_telemetry(tmp_path, "g-plan-1", candidate_seat=0)
    assert g1.plan_telemetry["has_plan"] is True
    assert g1.plan_telemetry["combo_assembled"] is True
    assert g1.plan_telemetry["combo_deployed"] is True
    assert g1.plan_telemetry["combos_assembled"] == ["c1"]
    assert g1.plan_telemetry["combos_deployed"] == ["c1"]
    assert g1.plan_telemetry["first_combo_assembled_round"] == 4
    assert g1.plan_telemetry["first_combo_deployed_round"] == 5

    g2 = GameSummary(
        game_id="g-plan-2",
        seed=8,
        status="finished",
        winner_seats=[1],
        rounds=9,
        plan_telemetry={
            "has_plan": True,
            "combo_assembled": False,
            "combo_deployed": False,
            "roles": {
                "combo_card": {"in_plan": 2, "offered": 1, "cast": 0},
                "key_card": {"in_plan": 2, "offered": 1, "cast": 0},
                "engine": {"in_plan": 1, "offered": 1, "cast": 0},
                "answer": {"in_plan": 1, "offered": 1, "cast": 1},
            },
        },
    )
    batch_summary = aggregate_batch_results([g1, g2])
    ps = batch_summary["plan_summary"]
    assert isinstance(ps, dict)
    assert ps["data_class"] == "SIMULATED_RESULT"
    assert ps["games_with_plan"] == 2
    assert ps["combo_assembled_games"] == 1
    assert ps["combo_deployed_games"] == 1
    assert ps["combo_assembly_rate"] == 0.5
    assert ps["combo_deployment_rate"] == 0.5

    # Tierliste simulation weight must stay 0 in default and all presets
    assert strength.DEFAULT_WEIGHTS[strength.SIMULATION] == 0.0
    for preset in strength.PRESETS.values():
        assert preset.weights[strength.SIMULATION] == 0.0
    assert strength_view.presets()["recommended"]["weights"][strength.SIMULATION] == 0.0  # type: ignore[index]
