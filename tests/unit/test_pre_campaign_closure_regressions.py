from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.structural import StructuralSimulator
from commander_lab.models import (
    CardRole,
    Color,
    DataQuality,
    StructuralAbortLimits,
    StructuralCardProfile,
    StructuralDeckProfile,
    StructuralMatchConfig,
)
from commander_lab.storage import sha256_value


def _card(
    name: str,
    *,
    mana_value: float,
    roles: frozenset[CardRole] = frozenset(),
    is_land: bool = False,
    is_creature: bool = False,
    base_power: float = 0.0,
    multiplayer_scaling: float = 0.0,
) -> StructuralCardProfile:
    colors = frozenset({Color.BLUE}) if is_land else frozenset()
    return StructuralCardProfile(
        oracle_name=name,
        mana_value=mana_value,
        roles=roles,
        role_strengths={role: 1.0 for role in roles},
        color_identity=colors,
        produces_colors=colors,
        is_land=is_land,
        is_permanent=is_land or is_creature,
        is_creature=is_creature,
        base_power=base_power,
        commander_synergy=0.0,
        floor_value=1.0 if name == "Fixture Lever" else 0.2,
        immediate_impact=1.0 if name == "Fixture Lever" else 0.1,
        turn_cycle_risk=0.0 if name == "Fixture Lever" else 0.5,
        multiplayer_scaling=multiplayer_scaling,
        source_quality=DataQuality.SYNTHETIC_ASSUMPTION,
        notes="Controlled pre-campaign closure regression fixture.",
    )


def _fixture_deck(deck_id: str, *, multiplayer_scaling: float) -> StructuralDeckProfile:
    commander = "Fixture Commander"
    cards: list[StructuralCardProfile] = [
        _card(commander, mana_value=10.0, is_creature=True, base_power=1.0),
        _card(
            "Fixture Lever",
            mana_value=0.0,
            roles=frozenset({CardRole.FINISHER}),
            multiplayer_scaling=multiplayer_scaling,
        ),
    ]
    for index in range(36):
        cards.append(
            _card(
                f"Fixture Island {index:02d}",
                mana_value=0.0,
                roles=frozenset({CardRole.MANA_SOURCE}),
                is_land=True,
            )
        )
    while len(cards) < 100:
        cards.append(_card(f"Fixture Filler {len(cards):02d}", mana_value=10.0))
    return StructuralDeckProfile(
        deck_id=deck_id,
        deck_hash=sha256_value(
            {
                "deck_id": deck_id,
                "multiplayer_scaling": multiplayer_scaling,
                "cards": [card.oracle_name for card in cards],
            }
        ),
        commander_names=(commander,),
        cards=tuple(cards),
        commander_base_costs={commander: 10.0},
        commander_base_power={commander: 1.0},
        commander_strategy="generic",
        data_snapshot_hash=sha256_value("pre-campaign-closure-fixture"),
    )


def _selected_fixture_utility(
    tmp_path: Path, *, pod_size: int, multiplayer_scaling: float, label: str
) -> float:
    actor = _fixture_deck(
        f"synthetic/closure/{label}/actor/{pod_size}p",
        multiplayer_scaling=multiplayer_scaling,
    )
    opponents = [
        _fixture_deck(
            f"synthetic/closure/{label}/opponent-{index}/{pod_size}p",
            multiplayer_scaling=0.0,
        )
        for index in range(1, pod_size)
    ]
    decks = {deck.deck_id: deck for deck in (actor, *opponents)}
    deck_ids = tuple(decks)
    opening_hand = (
        "Fixture Lever",
        "Fixture Island 00",
        "Fixture Island 01",
        "Fixture Island 02",
        "Fixture Island 03",
        "Fixture Island 04",
        "Fixture Island 05",
    )
    overrides = (opening_hand, *tuple(None for _ in opponents))
    log_path = tmp_path / f"{label}-{pod_size}p.jsonl"
    result = StructuralSimulator(decks).simulate(
        StructuralMatchConfig(
            match_id=f"closure-{label}-{pod_size}p",
            seed=2026081501,
            deck_ids=deck_ids,
            starting_player_seat=0,
            opening_hand_overrides=overrides,
            limits=StructuralAbortLimits(
                max_turns=1,
                max_events=20_000,
                max_no_progress_turns=2,
                max_spells_per_turn=2,
            ),
        ),
        run_id="pre-campaign-closure",
        event_log_path=log_path,
    )
    assert result.estimate_type == "structural_model_estimates"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    decisions = [
        event
        for event in events
        if event["event_type"] == "pilot_decision"
        and event["actor_id"] == "p1"
        and "Fixture Lever" in str(event["payload"].get("selected_action_id", ""))
    ]
    assert decisions, "fixture lever must be evaluated and selected through the real pilot path"
    return float(decisions[0]["payload"]["selected_utility"])


def test_structural_engine_4p_to_5p_scaling_is_causal_and_not_global(
    repo_root: Path, tmp_path: Path
) -> None:
    control_4p = _selected_fixture_utility(
        tmp_path, pod_size=4, multiplayer_scaling=0.0, label="control"
    )
    control_5p = _selected_fixture_utility(
        tmp_path, pod_size=5, multiplayer_scaling=0.0, label="control"
    )
    scaling_4p = _selected_fixture_utility(
        tmp_path, pod_size=4, multiplayer_scaling=1.0, label="scaling"
    )
    scaling_5p = _selected_fixture_utility(
        tmp_path, pod_size=5, multiplayer_scaling=1.0, label="scaling"
    )

    control_pod_delta = control_5p - control_4p
    scaling_pod_delta = scaling_5p - scaling_4p
    uplift_4p = scaling_4p - control_4p
    uplift_5p = scaling_5p - control_5p

    assert scaling_pod_delta > control_pod_delta + 0.1
    assert uplift_5p > uplift_4p

    report = {
        "schema_version": "1.0.0",
        "fixture": "controlled_structural_multiplayer_scaling",
        "evidence_class": "structural_model_estimates",
        "synthetic_assumption": True,
        "primary_4p": {
            "control_selected_utility": control_4p,
            "scaling_selected_utility": scaling_4p,
            "candidate_vs_control_effect": uplift_4p,
        },
        "five_player_sensitivity": {
            "primary_evidence": False,
            "control_selected_utility": control_5p,
            "scaling_selected_utility": scaling_5p,
            "candidate_vs_control_effect": uplift_5p,
        },
        "pod_size_response": scaling_pod_delta - control_pod_delta,
        "card_ablation": {
            "lever": "multiplayer_scaling",
            "candidate_value": 1.0,
            "ablated_value": 0.0,
            "specific_uplift_4p": uplift_4p,
            "specific_uplift_5p": uplift_5p,
        },
        "package_ablation": "NOT_APPLICABLE_NO_PACKAGE_IN_CONTROLLED_FIXTURE",
        "commander_denial": "NOT_APPLICABLE_NONCOMMANDER_CAUSAL_LEVER",
        "counterfactual_replay": {
            "same_seed": True,
            "same_opening_hand": True,
            "same_actor_shell": True,
            "changed_dimension": "multiplayer_scaling_only",
        },
        "acceptance": {
            "scaling_fixture_responds_more_in_5p": True,
            "non_scaling_control_has_no_corresponding_artificial_uplift": True,
            "four_player_is_primary": True,
            "five_player_is_sensitivity_only": True,
        },
    }
    output = repo_root / "artifacts" / "quality" / "pre_campaign_attribution_ablation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
