from __future__ import annotations

from commander_lab.engine.structural.strategy import commander_strategy
from commander_lab.models import CardRole, StructuralCardProfile, StructuralDeckProfile
from commander_lab.models.mulligan import (
    MulliganContext,
    MulliganGamePlan,
    MulliganPolicyName,
    MulliganPolicySummary,
)
from commander_lab.mulligan import MulliganLab


def _generic_profile() -> StructuralDeckProfile:
    return StructuralDeckProfile(
        deck_id="fixture/future-own-deck",
        deck_hash="a" * 64,
        commander_names=("Fixture Commander",),
        cards=(
            StructuralCardProfile(
                oracle_name="Fixture Commander",
                roles=frozenset({CardRole.PAYOFF}),
            ),
        ),
        commander_base_costs={"Fixture Commander": 3.0},
        commander_base_power={"Fixture Commander": 2.0},
        commander_strategy="generic",
        data_snapshot_hash="b" * 64,
    )


class _FixtureMulliganLab(MulliganLab):
    def __init__(self, deck: StructuralDeckProfile) -> None:
        self._fixture_deck = deck

    def deck(self, deck_id: str) -> StructuralDeckProfile:
        assert deck_id == self._fixture_deck.deck_id
        return self._fixture_deck


def _context(deck: StructuralDeckProfile) -> MulliganContext:
    return MulliganContext(
        deck_id=deck.deck_id,
        deck_hash=deck.deck_hash,
        seat_position=1,
        starting_player=False,
        pod_size=4,
        pilot_profile_id="future-deck-pilot",
        pilot_version="fixture",
        game_plan=MulliganGamePlan.BALANCED,
        seed=17,
    )


def _summary() -> MulliganPolicySummary:
    return MulliganPolicySummary(
        policy=MulliganPolicyName.CONSERVATIVE,
        samples=10,
        keep_rate_first_seven=0.7,
        final_keep_rate=1.0,
        mulligan_rate=0.3,
        average_mulligans=0.4,
        color_problem_rate=0.1,
        average_dead_cards=0.5,
        median_hand_score=3.5,
        structural_placement_mean=2.4,
        uncertainty_half_width_95=0.1,
    )


def test_commander_strategy_only_selects_explicit_known_families() -> None:
    assert commander_strategy(("Korvold, Fae-Cursed King",)) == "korvold"
    assert (
        commander_strategy(("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh")) == "rogshai"
    )
    assert commander_strategy(("Fixture Commander",)) == "generic"
    assert commander_strategy(("Ishai, Ojutai Dragonspeaker",)) == "generic"


def test_unknown_deck_uses_generic_mulligan_pilot_not_rogshai() -> None:
    deck = _generic_profile()
    lab = _FixtureMulliganLab(deck)
    context = _context(deck)

    assert (
        lab._pilot_name_for_policy(
            deck.deck_id, MulliganPolicyName.CURRENT_PILOT, "RogShaiControlPilot"
        )
        == "GenericCommanderPilot"
    )
    config = lab._pilot_config(deck, MulliganPolicyName.CURRENT_PILOT, context)
    assert config.pilot_name == "GenericCommanderPilot"


def test_generic_keep_rule_contains_no_rogshai_ishai_or_jeskai_assumptions() -> None:
    deck = _generic_profile()
    lab = _FixtureMulliganLab(deck)
    rule = lab.generate_keep_rules(_context(deck), (_summary(),), "c" * 64)[0]

    text = " ".join(
        [
            *(clause.feature for clause in rule.clauses),
            *(clause.rationale for clause in rule.clauses),
            *rule.exceptions,
        ]
    ).casefold()
    assert rule.deck_id == deck.deck_id
    assert rule.absolute_rule is False
    assert "early_blue_source_count" not in {clause.feature for clause in rule.clauses}
    assert all(term not in text for term in ("rogshai", "ishai", "jeskai"))
