from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from commander_lab.whole_deck import optimizer_runtime
from commander_lab.whole_deck.mechanics_fidelity import assess_variant_mechanics
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.optimizer_runtime import _initial_variants
from commander_lab.whole_deck.search_models import WholeDeckHardGate, WholeDeckVariant


def _variant(
    *,
    variant_id: str,
    deck_hash: str,
    mainboard: tuple[str, ...],
    policy_id: PolicyId,
    objective_prior: float,
) -> WholeDeckVariant:
    return WholeDeckVariant(
        variant_id=variant_id,
        deck_hash=deck_hash,
        mainboard=mainboard,
        policy_id=policy_id,
        policy_version="test",
        seed=1,
        objective_prior=objective_prior,
        hard_gate=WholeDeckHardGate(
            valid=True,
            card_count=len(mainboard),
            land_count=len(mainboard),
            basic_count=len(mainboard),
        ),
    )


def test_initial_variants_includes_exact_control_anchor_when_zero_safe_construction_finalists(
    monkeypatch,
) -> None:
    control = ("Island",)
    context = SimpleNamespace(cards={})
    observed_results: dict[PolicyId, SimpleNamespace] = {}

    class _Engine:
        def __init__(self, _context, policy, *, config, enrichment, answer_map) -> None:
            del _context, config, enrichment, answer_map
            self.policy = policy

        def run(self, *, current_control):
            assert current_control == control
            policy_id = self.policy.policy_id
            unsafe = _variant(
                variant_id=f"unsafe-{policy_id.value}",
                deck_hash=("a" if policy_id == PolicyId.CURRENT_CONTROL else "b") * 64,
                mainboard=("Mountain",),
                policy_id=policy_id,
                objective_prior=10.0,
            )
            control_arm = _variant(
                variant_id=f"control-{policy_id.value}",
                deck_hash="c" * 64,
                mainboard=control,
                policy_id=policy_id,
                objective_prior=-10.0,
            )
            result = SimpleNamespace(
                finalist_variant_ids=(unsafe.variant_id,),
                variants=(unsafe, control_arm),
                control_variant_id=control_arm.variant_id,
            )
            observed_results[policy_id] = result
            return result

    monkeypatch.setattr(optimizer_runtime, "current_control_mainboard", lambda _root: control)
    monkeypatch.setattr(optimizer_runtime, "EnrichedWholeDeckSearchEngine", _Engine)
    lab = SimpleNamespace(
        root=Path("/tmp/project"),
        context=context,
        enrichment=None,
        answer_map={},
    )
    manifest = SimpleNamespace(search_seed=123)

    engines, initial = _initial_variants(
        lab,
        manifest,
        policies=(PolicyId.CURRENT_CONTROL.value, PolicyId.OWNED_POOL_NEUTRAL.value),
        diversified_starts=1,
        steps_per_start=1,
        finalists_per_policy=1,
    )

    assert set(engines) == {PolicyId.CURRENT_CONTROL.value, PolicyId.OWNED_POOL_NEUTRAL.value}
    current_result = observed_results[PolicyId.CURRENT_CONTROL]
    assert current_result.control_variant_id not in current_result.finalist_variant_ids

    anchor = next(variant for variant in initial if variant.deck_hash == "c" * 64)
    assert anchor.mainboard == control
    assert anchor.policy_id == PolicyId.CURRENT_CONTROL
    assert assess_variant_mechanics(
        context,
        control=control,
        candidate=anchor.mainboard,
        deck_hash=anchor.deck_hash,
    )["pass"] is True

    construction_finalists = [variant for variant in initial if variant.deck_hash != anchor.deck_hash]
    assert construction_finalists
    assert all(
        assess_variant_mechanics(
            context,
            control=control,
            candidate=variant.mainboard,
            deck_hash=variant.deck_hash,
        )["pass"]
        is False
        for variant in construction_finalists
    )
