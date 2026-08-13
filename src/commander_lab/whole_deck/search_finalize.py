from __future__ import annotations

from commander_lab.storage import sha256_value

from .models import PolicyId
from .search_context import SEARCH_ENGINE_VERSION
from .search_models import WholeDeckSearchResult


def finalize(engine, archive, start_ids, current_control):
    ranked = sorted(
        (variant for variant in archive.values() if variant.hard_gate.valid),
        key=lambda variant: (-variant.objective_prior, variant.deck_hash),
    )
    finalists = ranked[: engine.config.finalist_limit]
    control_variant_id = None
    if engine.config.include_current_control_arm and current_control is not None:
        control = engine._evaluate(
            current_control,
            seed=engine.config.seed,
            parent_variant_id=None,
            mutation=None,
            start_type="post_finalist_control_arm",
        )
        archive.setdefault(control.variant_id, control)
        control_variant_id = control.variant_id
    ordered = sorted(
        archive.values(), key=lambda variant: (-variant.objective_prior, variant.deck_hash)
    )
    campaign_id = sha256_value(
        {
            "engine": SEARCH_ENGINE_VERSION,
            "snapshot": engine.context.snapshot_hash,
            "policy": engine.policy.model_dump(mode="json"),
            "config": engine.config.model_dump(mode="json"),
        }
    )
    return WholeDeckSearchResult(
        campaign_id=campaign_id,
        policy_id=engine.policy.policy_id,
        policy_version=engine.policy.policy_version,
        seed=engine.config.seed,
        data_snapshot_hash=engine.context.snapshot_hash,
        candidate_count=len(engine.context.cards),
        start_variant_ids=tuple(start_ids),
        explored_variant_ids=tuple(variant.variant_id for variant in ordered),
        finalist_variant_ids=tuple(variant.variant_id for variant in finalists),
        variants=tuple(ordered),
        control_variant_id=control_variant_id,
        control_used_as_search_prior=(
            engine.policy.policy_id == PolicyId.CURRENT_CONTROL
            and current_control is not None
        ),
    )
