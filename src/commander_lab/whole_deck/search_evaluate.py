from __future__ import annotations

from .mana import whole_deck_mana_summary
from .models import PolicyId
from .search_context import SEARCH_ENGINE_VERSION, stable_variant_hash
from .search_models import WholeDeckVariant


def evaluate_variant(engine, mainboard, seed, parent_variant_id, mutation, start_type=None):
    deck_hash = stable_variant_hash(mainboard, engine.context.snapshot_hash, engine.context.commander_names)
    gate = engine._hard_gate(mainboard)
    features = engine._feature_summary(mainboard)
    if gate.valid:
        deck = engine.context.materialize(mainboard, label=deck_hash[:12])
        if engine.context.mana_analyzer is not None:
            mana = whole_deck_mana_summary(deck, engine.context.mana_analyzer.analyze_deck(deck))
        else:
            mana = engine._synthetic_mana_summary(mainboard)
        meta = engine._meta_distance(mainboard)
        objective = engine._objective(mainboard, features, mana, meta)
    else:
        mana = engine._synthetic_mana_summary(mainboard)
        meta = {}
        objective = -1_000_000.0 - len(gate.issues)
    return WholeDeckVariant(
        variant_id=f"whole-deck/{deck_hash}",
        deck_hash=deck_hash,
        mainboard=mainboard,
        policy_id=engine.policy.policy_id,
        policy_version=engine.policy.policy_version,
        seed=seed,
        parent_variant_id=parent_variant_id,
        mutation=mutation,
        feature_vector=features,
        mana=mana,
        objective_prior=objective,
        meta_distance=meta,
        hard_gate=gate,
        provenance={
            "search_engine_version": SEARCH_ENGINE_VERSION,
            "data_snapshot_hash": engine.context.snapshot_hash,
            "policy_id": engine.policy.policy_id.value,
            "policy_version": engine.policy.policy_version,
            "current_deck_membership_prior_used": False,
            "control_blind_before_finalist_freeze": engine.policy.policy_id == PolicyId.OWNED_POOL_NEUTRAL,
            "start_type": start_type,
            "simulation_evidence": "NOT_RUN",
        },
    )
