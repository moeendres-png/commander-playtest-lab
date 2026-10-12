from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.engine.structural.card_facts import (
    CardFacts,
    CardFactsCatalog,
    apply_card_facts,
    load_card_facts,
    profile_from_facts,
)
from commander_lab.engine.structural.simulator import DEFAULT_TUNING, StructuralTuning
from commander_lab.engine.structural.simulator_fidelity import StructuralSimulator
from commander_lab.engine.structural.xmage_calibration import (
    XmagePod,
    calibration_metrics,
    fact_deck_profile,
    pod_from_record,
    spearman,
    split_pods,
    structural_win_probabilities,
)
from commander_lab.models import CardRole, RulesDeckInput, StructuralCardProfile

ROOT = Path(__file__).resolve().parents[2]


def _facts(name: str, **values: Any) -> CardFacts:
    return CardFacts(
        name=name,
        mana_value=values.get("mana_value", 3.0),
        types=tuple(values.get("types", ("CREATURE",))),
        subtypes=(),
        supertypes=tuple(values.get("supertypes", ())),
        power=values.get("power"),
        toughness=values.get("toughness"),
        rules=tuple(values.get("rules", ())),
    )


def _record(seat: int, winner: int | None, *, status: str = "completed") -> dict[str, Any]:
    return {
        "status": status,
        "run_key": f"k{seat}{winner}",
        "result": {
            "scenario": {
                "seat": seat,
                "seed": 7,
                "candidate_id": "me",
                "opponent_deck_ids": ["a", "b", "c"],
            },
            "result_payload": {
                "terminal": True,
                "turn_number": 40,
                "outcomes": [{"seat": index, "won": index == winner} for index in range(4)],
            },
        },
    }


def test_pod_from_record_puts_the_candidate_in_its_seat() -> None:
    pod = pod_from_record(_record(seat=3, winner=2))
    assert pod is not None
    assert pod.deck_ids == ("a", "b", "me", "c")
    assert pod.winner_seat == 2
    assert pod_from_record(_record(seat=1, winner=None)).winner_seat is None  # type: ignore[union-attr]
    assert pod_from_record(_record(seat=1, winner=0, status="failed")) is None


def test_facts_give_uncurated_creatures_their_power_and_keep_curated_values() -> None:
    bear = _facts("Grizzly Bears", power=2.0, rules=())
    profile = profile_from_facts("Grizzly Bears", bear)
    assert profile.is_creature and profile.base_power == 2.0
    flier = _facts("Serra Angel", power=4.0, rules=("Flying, vigilance",))
    assert profile_from_facts("Serra Angel", flier).base_power == pytest.approx(5.0)
    curated = StructuralCardProfile(
        oracle_name="Ishai", roles=frozenset({CardRole.ENABLER}), is_creature=True, base_power=3.5
    )
    assert apply_card_facts(curated, _facts("Ishai", power=1.0)).base_power == 3.5


def test_facts_mark_finishers_from_their_text() -> None:
    drain = _facts("Test Drain Spell", types=("SORCERY",), rules=("Each opponent loses X life.",))
    profile = profile_from_facts("Test Drain Spell", drain)
    assert CardRole.FINISHER in profile.roles
    assert profile.role_strengths[CardRole.FINISHER] == 1.0


def test_fact_lookup_ignores_case_accents_and_back_faces() -> None:
    catalog = CardFactsCatalog(
        {"Troll of Khazad-dum": _facts("Troll of Khazad-dum", power=6.0), "Wear": _facts("Wear")}
    )
    assert catalog.get("Troll of Khazad-dûm") is not None
    assert catalog.get("Wear // Tear") is not None
    assert catalog.get("Nothing Here") is None


def test_metrics_reward_the_model_that_ranks_like_xmage() -> None:
    pods = [
        XmagePod(f"g{index}", index, ("strong", "weak", "x", "y"), 0, 48) for index in range(6)
    ]
    right = [[0.7, 0.1, 0.1, 0.1]] * 6
    wrong = [[0.1, 0.7, 0.1, 0.1]] * 6
    good = calibration_metrics(pods, right, [12.0] * 6, min_games=1)
    bad = calibration_metrics(pods, wrong, [12.0] * 6, min_games=1)
    assert good["log_loss"] == pytest.approx(-math.log(0.7))
    assert good["log_loss"] < good["log_loss_uniform"] < bad["log_loss"]
    assert good["xmage_mean_rounds"] == 12.0
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    first, second = split_pods(pods)
    assert len(first) == len(second) == 3
    assert {pod.game_key for pod in first}.isdisjoint(pod.game_key for pod in second)


def test_default_tuning_is_the_long_standing_model() -> None:
    assert DEFAULT_TUNING == StructuralTuning()
    assert DEFAULT_TUNING.creature_attack == 0.62
    assert set(DEFAULT_TUNING.as_dict()) >= {"creature_attack", "finisher_damage"}


@pytest.mark.skipif(load_card_facts(ROOT) is None, reason="card facts not exported")
def test_a_collection_deck_replays_in_the_structural_model() -> None:
    facts = load_card_facts(ROOT)
    assert facts is not None
    deck: RulesDeckInput = load_rules_deck_snapshot(
        ROOT / "data/coverage_decks/collection/agrus.json"
    )
    profile, report = fact_deck_profile(deck, known={}, facts=facts, snapshot_hash="test")
    assert report.without_facts == []
    assert report.inferred_from_facts == 100
    assert sum(card.base_power for card in profile.cards if card.is_creature) > 20
    pod = XmagePod("g", 1, (deck.deck_id,) * 4, 0, 40)
    probabilities, abort_rate, turns = structural_win_probabilities(
        pod,
        {deck.deck_id: profile},
        seeds=range(1, 3),
        simulator_factory=StructuralSimulator,
    )
    assert sum(probabilities) == pytest.approx(1.0) or abort_rate > 0
    assert turns > 0
