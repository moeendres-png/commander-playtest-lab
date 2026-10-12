from __future__ import annotations

import pytest

from commander_lab.engine.rules import TacticalRuleOracle, load_interaction_catalog
from commander_lab.engine.rules.tactical import TacticalRuleError
from commander_lab.models import ValidationLevel


def test_phase8_catalog_contains_at_least_fifty_project_critical_interactions(repo_root) -> None:
    cases = load_interaction_catalog(repo_root / "data/rules/project_critical_interactions.json")
    assert len(cases) >= 50
    assert len({case.interaction_id for case in cases}) == len(cases)
    assert all(case.cards is not None for case in cases)


def test_all_registered_tactical_interactions_match_expected_results(repo_root) -> None:
    oracle = TacticalRuleOracle()
    cases = load_interaction_catalog(repo_root / "data/rules/project_critical_interactions.json")
    results = [oracle.validate(case) for case in cases]
    assert all(result.passed for result in results)
    assert all(result.level == ValidationLevel.TACTICAL_ORACLE for result in results)


def test_unknown_tactical_rule_is_rejected() -> None:
    oracle = TacticalRuleOracle()
    try:
        oracle.evaluate("not-a-rule", {})
    except Exception as exc:
        assert "unsupported tactical rule primitive" in str(exc)
    else:
        raise AssertionError("unknown tactical primitive must not be silently accepted")


def test_countered_commander_still_counts_toward_commander_tax() -> None:
    # CR 903.8: the tax counts every previous cast from the command zone; a
    # countered commander was cast, so its next cast costs {2} more (#734).
    observed = TacticalRuleOracle().evaluate("counter_commander", {"move_to_command_zone": True})
    assert observed["commander_tax_increments"] is True
    assert observed["final_zone"] == "command"


def test_tactical_input_with_unmodelled_key_fails_closed() -> None:
    # A typo must not silently fall back to a default and pass (#734).
    oracle = TacticalRuleOracle()
    with pytest.raises(TacticalRuleError, match="not modelled by commander_tax: prior_casts"):
        oracle.evaluate("commander_tax", {"printed_mana_value": 5, "prior_casts": 2})


def test_tactical_flag_must_be_a_boolean() -> None:
    oracle = TacticalRuleOracle()
    with pytest.raises(TacticalRuleError, match="must be a boolean"):
        oracle.evaluate("counter_commander", {"move_to_command_zone": "false"})


def test_tactical_missing_required_key_fails_closed() -> None:
    oracle = TacticalRuleOracle()
    with pytest.raises(TacticalRuleError, match="missing required key: toughness"):
        oracle.evaluate("zero_toughness", {})


def test_tactical_conditional_inputs_are_still_consulted() -> None:
    # Unselected Farewell modes and a non-lifelink hit keep their inputs modelled.
    oracle = TacticalRuleOracle()
    farewell = oracle.evaluate(
        "farewell", {"modes": ["graveyards"], "creatures": 3, "artifacts": 2, "graveyard_cards": 9}
    )
    assert farewell["creatures_exiled"] == 0 and farewell["graveyards_exiled"] == 9
    with pytest.raises(TacticalRuleError, match="unknown Farewell modes"):
        oracle.evaluate("farewell", {"modes": ["lands"]})


def test_short_circuited_inputs_are_modelled_on_every_branch(repo_root) -> None:
    # A key the primitive reads only on some branches is still modelled: turning
    # any boolean flag of a catalog case to False must never make another key
    # "unmodelled" (silence_restriction with silence_resolved=False used to).
    oracle = TacticalRuleOracle()
    cases = load_interaction_catalog(repo_root / "data/rules/project_critical_interactions.json")
    for case in cases:
        for key, value in case.input_state.items():
            if not isinstance(value, bool):
                continue
            for flipped in (False, True):
                try:
                    oracle.evaluate(case.rule, {**case.input_state, key: flipped})
                except TacticalRuleError as exc:
                    assert "not modelled" not in str(exc), (case.interaction_id, key, exc)
    assert oracle.evaluate("silence_restriction", {"silence_resolved": False, "same_turn": True})


@pytest.mark.parametrize(
    ("rule", "payload"),
    [
        ("soul_guide_lantern", {"mode": "etb", "target_available": "false"}),
        ("titania", {"land_in_graveyard": "no"}),
        ("fire_covenant", {"damage_assignments": [3], "toughnesses": [2], "indestructible": [1]}),
    ],
)
def test_every_branch_flag_read_must_be_a_boolean(rule: str, payload: dict[str, object]) -> None:
    with pytest.raises(TacticalRuleError, match="must be a boolean"):
        TacticalRuleOracle().evaluate(rule, payload)
