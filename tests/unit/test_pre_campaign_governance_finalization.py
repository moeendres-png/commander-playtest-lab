from __future__ import annotations

from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.lab_context import enriched_context
from commander_lab.whole_deck.search_context import (
    SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE,
    SEMANTIC_STRUCTURALLY_MODELED,
    SEMANTIC_UNKNOWN,
)


def test_enriched_context_preserves_three_state_semantics(repo_root) -> None:
    context, _, _ = enriched_context(repo_root)
    counts = {
        state: sum(card.effective_semantic_state == state for card in context.cards.values())
        for state in (
            SEMANTIC_STRUCTURALLY_MODELED,
            SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE,
            SEMANTIC_UNKNOWN,
        )
    }

    assert counts == {
        SEMANTIC_STRUCTURALLY_MODELED: 774,
        SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE: 21,
        SEMANTIC_UNKNOWN: 0,
    }
    assert sum(counts.values()) == 795


def test_public_enriched_discoverability_reports_true_unknown_partition(repo_root) -> None:
    lab = WholeDeckDesignLab(repo_root)
    payload = lab.prepare(
        policies=("OWNED_POOL_NEUTRAL",),
        seed=2026081505,
        diversified_starts=0,
        steps_per_start=1,
        finalists_per_policy=1,
        max_variants=32,
        output_name="test-governance-three-state.json",
    )
    report = payload["discoverability"]

    assert report["search_eligible_candidate_count"] == 793
    assert report["structurally_modeled_eligible_count"] == 772
    assert report["known_no_functional_eligible_count"] == 21
    assert report["semantic_unknown_eligible_count"] == 0
    assert (
        report["structurally_modeled_eligible_count"]
        + report["known_no_functional_eligible_count"]
        + report["semantic_unknown_eligible_count"]
        == report["search_eligible_candidate_count"]
    )
    assert all("semantic_state" in row for row in report["discovery_review_queue"])
