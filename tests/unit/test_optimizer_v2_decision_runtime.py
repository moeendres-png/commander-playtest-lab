from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.optimizer_v2_decision_runtime import (
    CONFIRMATORY_LOOKS,
    FAMILY_ALPHA,
    MCSE_MAX,
    SEED_BLOCK_COUNT,
    SESOI,
    SHORTLIST_LIMIT,
    _normal_interval,
    _seed_stability,
    _sequential_status,
)
from commander_lab.whole_deck.search_context import SEMANTIC_UNKNOWN

ROOT = Path(__file__).resolve().parents[2]


def _passing_payload() -> dict[str, object]:
    return {
        "mcse": 0.01,
        "seed_stability": {"pass": True},
        "sensitivity": {
            "pilot": {
                "mean_paired_delta": {
                    "strong_deterministic": 0.08,
                    "average_deterministic": 0.07,
                }
            },
            "seat": {"1": 0.06, "2": 0.07, "3": 0.08, "4": 0.07},
            "per_opponent": {"opponent/a": 0.06, "opponent/b": 0.08},
        },
    }


def test_frozen_contract_matches_runtime_constants() -> None:
    contract = json.loads((ROOT / "data/decision/DECISION_CONTRACT_CURRENT.json").read_text())
    precision = contract["confirmatory_precision"]
    holdout = contract["sealed_holdout"]

    assert contract["contract_id"] == "rogshai-hierarchical-pareto-1E-v1"
    assert contract["precision_contract_id"] == "rogshai-hybrid-sequential-2F-v1"
    assert contract["operational_pod_sizes"] == [4]
    assert precision["planned_paired_4p_budgets"] == list(CONFIRMATORY_LOOKS)
    assert precision["shortlist_limit"] == SHORTLIST_LIMIT
    assert precision["family_alpha"] == FAMILY_ALPHA
    assert precision["mcse_max_for_promotion"] == MCSE_MAX
    assert precision["seed_block_count"] == SEED_BLOCK_COUNT
    assert contract["practical_effect"]["sesoi"] == SESOI
    assert contract["practical_effect"]["sesoi_is_model_precision"] is False
    assert holdout["single_challenger_only"] is True
    assert holdout["paired_4p_budget"] == 2048
    assert holdout["planned_looks"] == 1
    assert holdout["consumed_historical_holdout_reuse_forbidden"] is True


def test_full_physical_semantic_projection_covers_current_rogshai_pool() -> None:
    manifest = json.loads(
        (ROOT / "data/cards/FULL_PHYSICAL_CARD_KNOWLEDGE_MANIFEST_CURRENT.json").read_text()
    )
    expected = int(manifest["source_bindings"]["rogshai_context"]["rows"])
    lab = WholeDeckDesignLab(ROOT)

    assert len(lab.context.cards) == expected == 795
    assert all(
        card.effective_semantic_state != SEMANTIC_UNKNOWN for card in lab.context.cards.values()
    )


def test_normal_interval_widens_with_confidence() -> None:
    values = (-1.0, 0.0, 0.0, 1.0) * 16
    low95, high95 = _normal_interval(values, 0.95)
    low99, high99 = _normal_interval(values, 0.99)

    assert low99 < low95
    assert high99 > high95


def test_seed_stability_accepts_stable_same_model_blocks() -> None:
    result = _seed_stability((0.08,) * 128, mcse=0.01)

    assert result["block_count"] == SEED_BLOCK_COUNT
    assert result["direction_consistent"] is True
    assert result["pass"] is True


def test_sequential_status_promotes_only_after_precision_and_robustness() -> None:
    evaluation = SimpleNamespace(interval_low=0.06, interval_high=0.12)
    status, gates = _sequential_status(
        evaluation=evaluation,
        payload=_passing_payload(),
        budget=512,
        semantic_pass=True,
    )

    assert status == "PROMOTION_CANDIDATE"
    assert gates["precision"]["pass"] is True
    assert gates["robustness"]["pass"] is True


def test_sequential_status_blocks_promotion_when_mcse_is_too_large() -> None:
    payload = _passing_payload()
    payload["mcse"] = MCSE_MAX + 0.001
    evaluation = SimpleNamespace(interval_low=0.06, interval_high=0.12)
    status, _ = _sequential_status(
        evaluation=evaluation,
        payload=payload,
        budget=2048,
        semantic_pass=True,
    )

    assert status == "BLOCKED_PRECISION"


def test_sequential_status_has_preregistered_harm_futility_and_ceiling_states() -> None:
    payload = _passing_payload()

    harm, _ = _sequential_status(
        evaluation=SimpleNamespace(interval_low=-0.10, interval_high=-0.01),
        payload=payload,
        budget=128,
        semantic_pass=True,
    )
    futility, _ = _sequential_status(
        evaluation=SimpleNamespace(interval_low=-0.01, interval_high=0.04),
        payload=payload,
        budget=1024,
        semantic_pass=True,
    )
    ceiling, _ = _sequential_status(
        evaluation=SimpleNamespace(interval_low=0.00, interval_high=0.08),
        payload=payload,
        budget=2048,
        semantic_pass=True,
    )

    assert harm == "REJECT_HARM"
    assert futility == "FUTILITY_BELOW_SESOI"
    assert ceiling == "PRECISION_LIMIT"
