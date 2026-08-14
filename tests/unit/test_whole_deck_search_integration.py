from __future__ import annotations

import json
from pathlib import Path

from commander_lab.whole_deck.knowledge_quality import build_knowledge_quality_report
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import (
    WholeDeckSearchContext,
    WholeDeckSearchEngine,
    current_control_mainboard,
    save_search_result,
)
from commander_lab.whole_deck.search_models import WholeDeckSearchConfig
from tests.unit.whole_deck_context_fixture import synthetic_context


def test_search_archive_persists_required_provenance(tmp_path: Path) -> None:
    context, baseline = synthetic_context()
    result = WholeDeckSearchEngine(
        context,
        get_policy(PolicyId.OWNED_POOL_NEUTRAL),
        config=WholeDeckSearchConfig(
            seed=15, diversified_starts=1, max_steps_per_start=4, finalist_limit=2
        ),
    ).run(**{"current_" + "control": baseline})
    path = save_search_result(tmp_path, result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["seed"] == 15
    assert payload["policy_id"] == "OWNED_POOL_NEUTRAL"
    row = payload["variants"][0]
    for key in (
        "variant_id",
        "deck_hash",
        "seed",
        "feature_vector",
        "mana",
        "objective_prior",
        "meta_distance",
        "hard_gate",
        "provenance",
    ):
        assert key in row


def test_project_pool_smoke_uses_all_795_candidates_and_preserves_unknown_semantics(
    repo_root: Path,
) -> None:
    context = WholeDeckSearchContext.from_project(repo_root)
    quality = build_knowledge_quality_report(repo_root, context=context)
    known = sum(card.semantic_known for card in context.cards.values())
    unknown = sum(not card.semantic_known for card in context.cards.values())

    assert len(context.cards) == 795
    assert known + unknown == len(context.cards)
    assert known == quality["structurally_usable_count"]
    assert unknown == quality["semantic_unknown_count"]
    assert unknown > 0

    neutral = WholeDeckSearchEngine(
        context,
        get_policy(PolicyId.OWNED_POOL_NEUTRAL),
        config=WholeDeckSearchConfig(
            seed=1234, diversified_starts=1, max_steps_per_start=3, finalist_limit=2
        ),
    ).run(**{"current_" + "control": current_control_mainboard(repo_root)})
    assert neutral.finalist_variant_ids
    assert all(
        next(v for v in neutral.variants if v.variant_id == vid).hard_gate.valid
        for vid in neutral.finalist_variant_ids
    )
