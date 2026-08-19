from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from commander_lab.project_context import load_project_context
from commander_lab.workflow_identity import (
    WorkflowIdentityError,
    build_priority_comparison_identity,
)

ROOT = Path(__file__).resolve().parents[2]


def _replace_hash(
    rows: tuple[tuple[str, str], ...], key: str, value: str
) -> tuple[tuple[str, str], ...]:
    payload = dict(rows)
    payload[key] = value
    return tuple(sorted(payload.items()))


def test_priority_identity_ignores_declared_irrelevant_governance_changes() -> None:
    context = load_project_context(ROOT)
    before = build_priority_comparison_identity(context).identity_hash

    changed_rules = replace(
        context,
        policy_config_hashes=_replace_hash(
            context.policy_config_hashes,
            "config/rules_engines.json",
            "f" * 64,
        ),
    )
    changed_historical = replace(
        context,
        source_hashes=_replace_hash(
            context.source_hashes,
            "inactive_deck_releases",
            "e" * 64,
        ),
    )

    assert build_priority_comparison_identity(changed_rules).identity_hash == before
    assert build_priority_comparison_identity(changed_historical).identity_hash == before


def test_priority_identity_invalidates_relevant_semantic_dependencies() -> None:
    context = load_project_context(ROOT)
    before = build_priority_comparison_identity(context).identity_hash

    changed_policy = replace(
        context,
        policy_config_hashes=_replace_hash(
            context.policy_config_hashes,
            "config/phase7_optimization.json",
            "a" * 64,
        ),
    )
    changed_scenario = replace(
        context,
        source_hashes=_replace_hash(
            context.source_hashes,
            "pod_scenarios",
            "b" * 64,
        ),
    )
    feature_key = next(
        key for key, _value in context.source_hashes if key.startswith("drive_feature:")
    )
    changed_feature = replace(
        context,
        source_hashes=_replace_hash(context.source_hashes, feature_key, "c" * 64),
    )

    assert build_priority_comparison_identity(changed_policy).identity_hash != before
    assert build_priority_comparison_identity(changed_scenario).identity_hash != before
    assert build_priority_comparison_identity(changed_feature).identity_hash != before


def test_priority_identity_fails_closed_if_declared_dependency_is_missing() -> None:
    context = load_project_context(ROOT)
    sources = tuple((key, value) for key, value in context.source_hashes if key != "pod_scenarios")
    with pytest.raises(WorkflowIdentityError, match="pod_scenarios"):
        build_priority_comparison_identity(replace(context, source_hashes=sources))


def test_priority_identity_is_deck_scoped_for_multi_deck_fixture() -> None:
    current = load_project_context(ROOT)
    sources = dict(current.source_hashes)
    sources.pop("active_deck:rogshai/current")
    sources["active_deck:fixture/alpha"] = "1" * 64
    sources["active_deck:fixture/beta"] = "2" * 64
    fixture = replace(
        current,
        active_own_deck_ids=("fixture/alpha", "fixture/beta"),
        primary_deckbuilding_focus="fixture/alpha",
        active_deck_hashes=(
            ("fixture/alpha", "1" * 64),
            ("fixture/beta", "2" * 64),
        ),
        source_hashes=tuple(sorted(sources.items())),
    )

    alpha = build_priority_comparison_identity(fixture, "fixture/alpha")
    beta = build_priority_comparison_identity(fixture, "fixture/beta")

    assert alpha.identity_hash != beta.identity_hash
    assert alpha.workflow_name.endswith(":fixture/alpha")
    assert beta.workflow_name.endswith(":fixture/beta")
    assert "active_deck:fixture/alpha" in dict(alpha.source_dependencies)
    assert "active_deck:fixture/beta" not in dict(alpha.source_dependencies)
    assert "active_deck:fixture/beta" in dict(beta.source_dependencies)
    assert "active_deck:fixture/alpha" not in dict(beta.source_dependencies)

    with pytest.raises(WorkflowIdentityError, match="not active"):
        build_priority_comparison_identity(fixture, "fixture/unknown")
