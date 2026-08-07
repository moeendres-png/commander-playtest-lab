from __future__ import annotations

from commander_lab.engine.rules import TacticalRuleOracle, load_interaction_catalog
from commander_lab.models import ValidationLevel


def test_phase8_catalog_contains_at_least_fifty_project_critical_interactions(repo_root) -> None:
    cases = load_interaction_catalog(
        repo_root / "data/rules/project_critical_interactions.json"
    )
    assert len(cases) >= 50
    assert len({case.interaction_id for case in cases}) == len(cases)
    assert all(case.cards is not None for case in cases)


def test_all_registered_tactical_interactions_match_expected_results(repo_root) -> None:
    oracle = TacticalRuleOracle()
    cases = load_interaction_catalog(
        repo_root / "data/rules/project_critical_interactions.json"
    )
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
