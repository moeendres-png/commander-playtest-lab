from __future__ import annotations

from commander_lab.models.whole_deck_tooling import WholeDeckDecisionPrepareInput
from commander_lab.semantic_features import (
    graveyard_hate_semantics,
    produced_self_colors,
    protection_semantics,
    removal_semantics,
    self_mana_semantics,
)
from commander_lab.tools import PUBLIC_TOOL_DEFINITIONS, CommanderToolService


def test_semantic_hardening_examples() -> None:
    offer = "Counter target spell. Its controller creates two Treasure tokens."
    assert self_mana_semantics(offer, "Instant") == (False, False)
    assert produced_self_colors(offer, "Instant") == frozenset()
    own_treasure = "Create two Treasure tokens."
    assert {color.value for color in produced_self_colors(own_treasure, "Sorcery")} == {
        "W",
        "U",
        "R",
    }
    assert not removal_semantics("Target player takes 5 damage.")
    assert not graveyard_hate_semantics("Flashback {2}{U}")
    assert not protection_semantics("This spell can't be countered.")
    assert protection_semantics("Target creature gains indestructible until end of turn.")


def test_public_surface_stays_exactly_four() -> None:
    assert tuple(row.name for row in PUBLIC_TOOL_DEFINITIONS) == (
        "deck_decision_prepare",
        "deck_decision_run",
        "deck_decision_diagnose",
        "deck_decision_bundle",
    )


def test_small_whole_deck_prepare(repo_root) -> None:
    service = CommanderToolService(repo_root)
    request = WholeDeckDecisionPrepareInput(
        design_mode="whole_deck",
        whole_deck_policies=("OWNED_POOL_NEUTRAL",),
        whole_deck_diversified_starts=0,
        whole_deck_steps_per_start=1,
        whole_deck_finalists_per_policy=1,
        whole_deck_max_variants=1,
        design_seed=2026081401,
        whole_deck_output_name="test-whole-deck-design.json",
    )
    response = service.deck_decision_prepare(request)
    assert response.status.value == "completed"
    assert response.result["candidate_count"] == 795
    assert response.result["official_structural_campaign_run"] is False
    assert response.result["automatic_deck_mutation"] is False
    assert response.result["variants"]
    assert response.result["evidence_boundaries"]["old_static_threat_answer_matrix_used"] is False
