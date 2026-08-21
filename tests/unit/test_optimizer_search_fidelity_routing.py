from __future__ import annotations

from types import SimpleNamespace

from commander_lab.whole_deck import optimizer_search
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.optimizer_search import AdaptiveWholeDeckSearch
from commander_lab.whole_deck.optimizer_v2 import (
    EvidenceContext,
    ExploratoryEvaluation,
    LearningConfig,
    QDConfig,
    RacingConfig,
)
from commander_lab.whole_deck.search_models import WholeDeckHardGate, WholeDeckVariant


def _variant(deck_hash: str) -> WholeDeckVariant:
    return WholeDeckVariant(
        variant_id=f"variant-{deck_hash[0]}",
        deck_hash=deck_hash,
        mainboard=("Island",),
        policy_id=PolicyId.OWNED_POOL_NEUTRAL,
        policy_version="test",
        seed=1,
        objective_prior=0.0,
        hard_gate=WholeDeckHardGate(
            valid=True,
            card_count=1,
            land_count=1,
            basic_count=1,
        ),
    )


class _Evaluator:
    def __init__(self, safe_hash: str) -> None:
        self.safe_hash = safe_hash
        self.calls: list[tuple[str, int]] = []

    def structural_decision_safe(self, variant: WholeDeckVariant) -> bool:
        return variant.deck_hash == self.safe_hash

    def __call__(
        self, variant: WholeDeckVariant, budget: int, statistics_offset: int
    ) -> ExploratoryEvaluation:
        del statistics_offset
        self.calls.append((variant.deck_hash, budget))
        return ExploratoryEvaluation(
            candidate_id=variant.variant_id,
            deck_hash=variant.deck_hash,
            generation=0,
            operator="test",
            policy_id=variant.policy_id.value,
            budget=budget,
            score=0.0,
            interval_low=-0.1,
            interval_high=0.1,
            robust_lower_bound=0.0,
            qd_cell="test",
            evidence_context=EvidenceContext.EXPLORATORY,
        )


class _Archive:
    def variants(self) -> tuple[WholeDeckVariant, ...]:
        return ()

    def admit(self, variant: WholeDeckVariant, evaluation: ExploratoryEvaluation) -> None:
        del variant, evaluation


def test_screening_only_candidate_does_not_receive_later_structural_racing_budget(
    monkeypatch,
) -> None:
    safe_hash = "a" * 64
    unsafe_hash = "b" * 64
    safe = _variant(safe_hash)
    unsafe = _variant(unsafe_hash)
    evaluator = _Evaluator(safe_hash)
    monkeypatch.setattr(
        optimizer_search,
        "descriptor_for_variant",
        lambda _variant: SimpleNamespace(cell=lambda _config: "test"),
    )
    monkeypatch.setattr(optimizer_search, "novelty_score", lambda *_args, **_kwargs: 0.0)
    search = AdaptiveWholeDeckSearch(
        {PolicyId.OWNED_POOL_NEUTRAL.value: SimpleNamespace()},
        evaluator=evaluator,
        seed=1,
        qd=QDConfig(),
        racing=RacingConfig(budgets=(2, 4), minimum_survivors=1),
        learning=LearningConfig(),
    )

    search._evaluate_batch([safe, unsafe], generation=0, archive=_Archive())

    assert (safe_hash, 2) in evaluator.calls
    assert (safe_hash, 4) in evaluator.calls
    assert (unsafe_hash, 2) in evaluator.calls
    assert (unsafe_hash, 4) not in evaluator.calls
