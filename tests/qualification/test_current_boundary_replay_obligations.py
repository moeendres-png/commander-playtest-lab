"""Per-obligation PB-08 replay/RNG disposition.

The load-bearing property is the negative one: a fail-closed refusal is an
absent capability, and treating it as a satisfied obligation would invert the
meaning of the evidence. These tests pin that, plus the distinction between an
acknowledged seed and a demonstrated RulesRngTape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary.replay_obligations import (
    ACKNOWLEDGED,
    UNACKNOWLEDGED,
    assess_replay_obligations,
    load_catalog,
)

CATALOG = Path("qualification/obligations/QUALIFICATION_OBLIGATION_CATALOG_v1.json")
REPLAY_ROWS = (
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
)


@pytest.fixture()
def catalog() -> list[dict[str, Any]]:
    return load_catalog(CATALOG)


def _artifact(
    *,
    controlled: bool,
    acknowledged: int | None,
    requested: int = 424242,
    replay: Any = None,
) -> dict[str, Any]:
    return {
        "rules_rng_binding": {
            "requested_seed": requested,
            "acknowledged_seed": acknowledged,
            "classification": "ACKNOWLEDGED_ENGINE_SEED"
            if controlled
            else "UNCONTROLLED_ENGINE_RNG",
            "controlled": controlled,
        },
        "semantic_replay": replay,
    }


_REFUSAL = {"error": [{"code": "unsupported_message", "message": "does not support export_replay"}]}


def test_catalog_carries_the_five_replay_and_rng_obligations(catalog: list[dict[str, Any]]) -> None:
    ids = {
        o["obligation_id"] for o in catalog if o["obligation_id"].startswith(("REPLAY_", "RNG_"))
    }
    assert ids == {"RNG_RULES_TAPE", *REPLAY_ROWS}


def test_an_acknowledged_seed_is_a_precondition_not_a_completed_tape(
    catalog: list[dict[str, Any]],
) -> None:
    out = assess_replay_obligations(
        _artifact(controlled=True, acknowledged=424242, replay=_REFUSAL), catalog=catalog
    )
    entry = out["dispositions"]["RNG_RULES_TAPE"]
    assert entry["disposition"] == ACKNOWLEDGED
    # The precondition is met, but the obligation itself is still not done.
    assert "not established by the acknowledgement alone" in entry["reason"]


def test_an_unacknowledged_seed_cannot_demonstrate_the_tape(catalog: list[dict[str, Any]]) -> None:
    out = assess_replay_obligations(
        _artifact(controlled=False, acknowledged=None, replay=_REFUSAL), catalog=catalog
    )
    assert out["dispositions"]["RNG_RULES_TAPE"]["disposition"] == UNACKNOWLEDGED
    assert "without an acknowledged root seed" in out["dispositions"]["RNG_RULES_TAPE"]["reason"]


def test_a_mismatched_seed_does_not_count_as_acknowledged(catalog: list[dict[str, Any]]) -> None:
    """Acknowledging a different seed than the one requested is not control."""
    out = assess_replay_obligations(
        _artifact(controlled=True, acknowledged=999, requested=424242, replay=_REFUSAL),
        catalog=catalog,
    )
    assert out["dispositions"]["RNG_RULES_TAPE"]["disposition"] == UNACKNOWLEDGED


@pytest.mark.parametrize("obligation_id", REPLAY_ROWS)
def test_a_fail_closed_refusal_is_never_a_pass(
    obligation_id: str, catalog: list[dict[str, Any]]
) -> None:
    out = assess_replay_obligations(
        _artifact(controlled=True, acknowledged=424242, replay=_REFUSAL), catalog=catalog
    )
    entry = out["dispositions"][obligation_id]
    assert entry["disposition"] == UNACKNOWLEDGED
    assert "never a satisfied obligation" in entry["reason"]
    assert out["replay_export_seam"]["refused"] is True


def test_a_missing_replay_response_is_still_a_refusal(catalog: list[dict[str, Any]]) -> None:
    out = assess_replay_obligations(
        _artifact(controlled=True, acknowledged=424242, replay=None), catalog=catalog
    )
    assert out["replay_export_seam"]["refused"] is True
    assert all(out["dispositions"][r]["disposition"] == UNACKNOWLEDGED for r in REPLAY_ROWS)


def test_a_returned_replay_payload_is_not_credited_here(
    catalog: list[dict[str, Any]],
) -> None:
    """Seam availability is not tape correctness; the module must not conflate them."""
    out = assess_replay_obligations(
        _artifact(
            controlled=True,
            acknowledged=424242,
            replay={"events": [{"kind": "draw"}], "seed": 424242},
        ),
        catalog=catalog,
    )
    assert all(out["dispositions"][r]["disposition"] == UNACKNOWLEDGED for r in REPLAY_ROWS)
    assert "seam availability only" in out["replay_export_seam"]["detail"]


def test_disposition_never_claims_a_row_promotion(catalog: list[dict[str, Any]]) -> None:
    out = assess_replay_obligations(
        _artifact(controlled=True, acknowledged=424242, replay=_REFUSAL), catalog=catalog
    )
    assert "does not itself flip a FULL107 row" in out["promotion_note"]


def test_counts_cover_every_disposition(catalog: list[dict[str, Any]]) -> None:
    out = assess_replay_obligations(
        _artifact(controlled=True, acknowledged=424242, replay=_REFUSAL), catalog=catalog
    )
    assert out["counts"]["total"] == 5
    assert out["counts"][ACKNOWLEDGED] + out["counts"][UNACKNOWLEDGED] == 5


# ---------------------------------------------------------------------------
# Persisted evidence must agree with the disposition it came from.
# ---------------------------------------------------------------------------

_OUT = Path("qualification/final-current-boundary-20260927")


@pytest.mark.parametrize("candidate", ["XMAGE", "FORGE"])
def test_persisted_seed_binding_matches_the_run(candidate: str) -> None:
    document = json.loads((_OUT / f"RNG_REPLAY_{candidate}.json").read_text(encoding="utf-8"))
    out = assess_replay_obligations(document, catalog=load_catalog(CATALOG))
    assert out["seed_binding"]["requested_seed"] == document["rules_rng_binding"]["requested_seed"]
    assert (
        out["seed_binding"]["acknowledged_seed"]
        == document["rules_rng_binding"]["acknowledged_seed"]
    )
    assert out["seed_binding"]["controlled"] == document["rules_rng_binding"]["controlled"]


@pytest.mark.parametrize("candidate", ["XMAGE", "FORGE"])
def test_the_replay_seam_is_observed_refused_for_both(candidate: str) -> None:
    """Both candidates fail closed today; if that ever changes the evidence must follow."""
    document = json.loads((_OUT / f"RNG_REPLAY_{candidate}.json").read_text(encoding="utf-8"))
    out = assess_replay_obligations(document, catalog=load_catalog(CATALOG))
    assert out["replay_export_seam"]["refused"] is True
    assert out["replay_export_seam"]["detail"]
