from __future__ import annotations

import json
from pathlib import Path

from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import (
    WholeDeckSearchEngine,
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
