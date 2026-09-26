from __future__ import annotations

import json
from types import SimpleNamespace

from commander_lab.models.roles import CardRole
from commander_lab.whole_deck import mechanics_fidelity
from commander_lab.whole_deck.mechanics_fidelity import (
    assess_frontier_mechanics,
    write_structural_confirmatory_frontier,
)


def _card(*, roles: tuple[CardRole, ...] = (), is_basic: bool = False) -> SimpleNamespace:
    profile = SimpleNamespace(roles=frozenset(roles), mechanic_tags=frozenset())
    return SimpleNamespace(
        effective_semantic_state="structurally_modeled",
        profile=profile,
        is_basic=is_basic,
    )


def _variant(deck_hash: str, card_name: str) -> dict[str, object]:
    return {
        "variant_id": f"variant-{deck_hash[0]}",
        "deck_hash": deck_hash,
        "mainboard": [card_name],
        "policy_id": "OWNED_POOL_NEUTRAL",
        "policy_version": "test",
        "seed": 1,
        "objective_prior": 0.0,
        "hard_gate": {
            "valid": True,
            "issues": [],
            "card_count": 1,
            "land_count": int(card_name in {"Island", "Plains"}),
            "basic_count": int(card_name in {"Island", "Plains"}),
        },
    }


def test_blocked_frontier_elite_does_not_block_unrelated_safe_candidate(
    tmp_path, monkeypatch
) -> None:
    unsafe_hash = "a" * 64
    safe_hash = "b" * 64
    context = SimpleNamespace(
        cards={
            "Island": _card(is_basic=True),
            "Plains": _card(is_basic=True),
            "Silence": _card(roles=(CardRole.COUNTER,)),
        }
    )
    monkeypatch.setattr(
        mechanics_fidelity,
        "WholeDeckDesignLab",
        lambda _root: SimpleNamespace(context=context),
    )
    monkeypatch.setattr(
        mechanics_fidelity,
        "current_control_mainboard",
        lambda _root: ("Island",),
    )
    frontier = tmp_path / "frontier.json"
    frontier.write_text(
        json.dumps(
            {
                "manifest_hash": "manifest-test",
                "elites": [
                    {
                        "deck_hash": unsafe_hash,
                        "variant": _variant(unsafe_hash, "Silence"),
                        "evaluation": {
                            "robust_lower_bound": 1.0,
                            "score": 1.0,
                            "qd_cell": "cell-a",
                        },
                    },
                    {
                        "deck_hash": safe_hash,
                        "variant": _variant(safe_hash, "Plains"),
                        "evaluation": {
                            "robust_lower_bound": 0.5,
                            "score": 0.5,
                            "qd_cell": "cell-b",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = assess_frontier_mechanics(tmp_path, frontier)

    assert report["pass"] is True
    assert report["blocked_variant_hashes"] == [unsafe_hash]
    assert report["structural_confirmatory_eligible_hashes"] == [safe_hash]
    assert report["frontier_candidate_count"] == 2
    assert report["shortlist_size"] == 1

    routed_path = write_structural_confirmatory_frontier(
        frontier,
        fidelity=report,
        output_path=tmp_path / "routed-frontier.json",
    )
    routed = json.loads(routed_path.read_text(encoding="utf-8"))
    assert [row["deck_hash"] for row in routed["elites"]] == [safe_hash]
    assert routed["holdout_used"] is False
    assert routed["canonical_deck_mutation"] is False


def test_frontier_routing_fails_closed_when_no_candidate_is_decision_safe(
    tmp_path, monkeypatch
) -> None:
    unsafe_hash = "c" * 64
    context = SimpleNamespace(
        cards={
            "Island": _card(is_basic=True),
            "Silence": _card(roles=(CardRole.COUNTER,)),
        }
    )
    monkeypatch.setattr(
        mechanics_fidelity,
        "WholeDeckDesignLab",
        lambda _root: SimpleNamespace(context=context),
    )
    monkeypatch.setattr(
        mechanics_fidelity,
        "current_control_mainboard",
        lambda _root: ("Island",),
    )
    frontier = tmp_path / "frontier.json"
    frontier.write_text(
        json.dumps(
            {
                "manifest_hash": "manifest-test",
                "elites": [
                    {
                        "deck_hash": unsafe_hash,
                        "variant": _variant(unsafe_hash, "Silence"),
                        "evaluation": {
                            "robust_lower_bound": 1.0,
                            "score": 1.0,
                            "qd_cell": "cell-a",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = assess_frontier_mechanics(tmp_path, frontier)

    assert report["pass"] is False
    assert report["structural_confirmatory_eligible_hashes"] == []
    assert report["blocked_variant_hashes"] == [unsafe_hash]
