from __future__ import annotations

import json
from pathlib import Path

ALLOWED_EVIDENCE_KINDS = {
    "verified_full_deck",
    "official_precon",
    "directly_observed",
    "reported",
    "partially_observed",
    "inferred",
    "synthetic_completion",
    "unknown",
}


def test_j_p2_opponent_profiles_use_explicit_evidence_taxonomy(repo_root: Path) -> None:
    payload = json.loads(
        (repo_root / "data/opponents/current_structural_profiles.json").read_text(encoding="utf-8")
    )
    profiles = {row["deck_id"]: row for row in payload["profiles"]}
    for row in profiles.values():
        kinds = set(row["evidence_kinds"])
        assert kinds
        assert kinds <= ALLOWED_EVIDENCE_KINDS

    assert set(profiles["kaervek/current"]["evidence_kinds"]) == {"verified_full_deck"}
    assert set(profiles["opponent/cosmic-spiderman-midbudget"]["evidence_kinds"]) == {
        "partially_observed",
        "synthetic_completion",
        "unknown",
    }
    assert set(profiles["opponent/morcant-elves"]["evidence_kinds"]) == {
        "partially_observed",
        "synthetic_completion",
    }
    assert set(profiles["opponent/doom-prevails-precon"]["evidence_kinds"]) == {
        "official_precon",
    }
    assert set(profiles["opponent/blight-curse-precon"]["evidence_kinds"]) == {
        "official_precon",
        "directly_observed",
    }


def test_j_p2_current_deck_source_and_protected_metadata_are_clean(repo_root: Path) -> None:
    canonical = json.loads(
        (repo_root / "data/canonical_import/2026-08-11/rogshai_current_provisional.json").read_text(
            encoding="utf-8"
        )
    )
    protected = json.loads((repo_root / "config/protected_cards.json").read_text(encoding="utf-8"))
    assert protected == {}
    assert canonical["status"] == "current_provisional_final_for_simulator_optimization"
    assert canonical["deck"]["deck_id"] == "rogshai/current"
    assert set(canonical["deck_hashes"]) == {"rogshai/current"}
    assert canonical["deck_hashes"]["rogshai/current"] == canonical["deck"]["deck_hash"]


def test_j_p2_current_opponents_route_to_non_generic_archetype_pilots(repo_root: Path) -> None:
    from commander_lab.agents.live_routing import auto_pilot_name as live_auto_pilot_name
    from commander_lab.agents.live_routing import build_pilot
    from commander_lab.agents.pilots import auto_pilot_name as legacy_auto_pilot_name
    from commander_lab.engine.structural.fixtures import build_current_opponent_profiles
    from commander_lab.models import PilotConfig

    profiles = build_current_opponent_profiles(
        repo_root / "data/opponents/current_structural_profiles.json",
        data_snapshot_hash="0" * 64,
    )
    expected = {
        "opponent/morcant-elves": "AggroPilot",
        "opponent/cosmic-spiderman-midbudget": "AggroPilot",
        "opponent/blight-curse-precon": "GraveyardPilot",
        "opponent/doom-prevails-precon": "ArtifactPilot",
        "opponent/dance-elements-precon": "GraveyardPilot",
        "opponent/wakanda-forever-precon": "ArtifactPilot",
        "kaervek/current": "KaervekOpponentPilot",
    }
    checked = list(expected.items())
    assert checked, "nothing was checked: expected.items() is empty"
    for deck_id, pilot_name in checked:
        strategy = profiles[deck_id].commander_strategy
        assert legacy_auto_pilot_name(strategy) == pilot_name
        assert live_auto_pilot_name(strategy) == pilot_name
        built = build_pilot(PilotConfig(pilot_name="auto"), strategy=strategy)
        assert type(built).__name__ == pilot_name


def test_j_p2_pilot_state_exposes_explicit_seat_position() -> None:
    import pytest
    from pydantic import ValidationError

    from commander_lab.models import PilotStateView

    state = PilotStateView(
        player_id="p3",
        deck_id="korvold/current",
        strategy="korvold",
        turn=3,
        pod_size=5,
        seat_position=3,
        life=40,
        hand_size=7,
        mana_available=3,
        lands=3,
        ramp_mana=0,
        resources=0,
        tokens=0,
        board_power=0,
        engine_value=0,
        graveyard_size=0,
    )
    assert state.seat_position == 3
    with pytest.raises(ValidationError, match="seat_position"):
        state.model_copy(update={"seat_position": 6}).__class__.model_validate(
            {**state.model_dump(mode="json"), "seat_position": 6}
        )
