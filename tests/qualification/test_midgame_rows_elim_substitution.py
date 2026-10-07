"""A declared causal life substitution is a variance, never an exact label.

The Coordinator ruling on #585 (condition 2) requires the XMage causal
elimination to label its open life substitution exactly as the Forge scenario
lane already labels it: ``ALLOWED_VARIANCE`` with its own ``variance_source``
and the ``BEHAVIOUR_OBSERVED_LAB_DECLARED_CAUSAL_SUBSTITUTION`` assertion class.
The route's own plan substitutes the victim's recorded life (the CR 704.3
state-based-action-pending instant, which no priority point shows) with its
recorded starting life; a receipt that reads ``EXACT`` hides that deliberate
deviation. A real construction mismatch still takes precedence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary import receipts as receipt_mod
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ID = "WS05-MP-ELIM-STACK-3"


def _effective_record(fixture_id: str = FIXTURE_ID) -> dict[str, Any]:
    materialization = load_effective_materialization(REPO_ROOT)
    return materialization.record(fixture_id)


def _declared_plan(record: dict[str, Any]) -> dict[str, Any]:
    """The engine's own plan shape for the record's declared elimination.

    The victim's recorded life is the pre-state-based-action instant; the
    plan openly places the recorded starting life and publishes the pair.
    """
    victim = next(player for player in record["players"] if int(player["life"]) <= 0)
    return {
        "entry_mode": "causal_elimination",
        "actor": "P1",
        "victim": str(victim["player_id"]).lower(),
        "life_substitutions": [
            {
                "player_id": str(victim["player_id"]).lower(),
                "recorded_life": int(victim["life"]),
                "placed_life": int(victim["starting_life"]),
            }
        ],
    }


# --------------------------------------------------------------------------- #
# The pure overlay
# --------------------------------------------------------------------------- #


def test_a_declared_plan_has_real_substitutions_in_the_effective_record() -> None:
    record = _effective_record()
    plan = _declared_plan(record)
    substitution = plan["life_substitutions"][0]
    assert substitution["recorded_life"] <= 0
    assert substitution["placed_life"] > 0
    assert substitution["recorded_life"] != substitution["placed_life"]


def test_an_exact_engine_verdict_becomes_the_declared_variance() -> None:
    verdict, source = mr.construction_with_declared_substitution(
        "EXACT", {"elimination_plan": _declared_plan(_effective_record())}
    )
    assert verdict == "ALLOWED_VARIANCE"
    assert verdict != "EXACT"
    assert source == mr.DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE
    assert "declared causal elimination" in str(source)
    assert "CR 704.3" in str(source)


def test_an_already_allowed_variance_keeps_its_declared_source() -> None:
    verdict, source = mr.construction_with_declared_substitution(
        "ALLOWED_VARIANCE", {"elimination_plan": _declared_plan(_effective_record())}
    )
    assert verdict == "ALLOWED_VARIANCE"
    assert source == mr.DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE


def test_a_construction_mismatch_takes_precedence() -> None:
    verdict, source = mr.construction_with_declared_substitution(
        "MISMATCH", {"elimination_plan": _declared_plan(_effective_record())}
    )
    assert verdict == "MISMATCH"
    assert source is None


def test_only_a_declared_victim_substitution_is_a_variance() -> None:
    plan = _declared_plan(_effective_record())
    # No elimination plan: the engine's own verdict stands verbatim.
    assert mr.construction_with_declared_substitution("EXACT", {}) == ("EXACT", None)
    # A plan that declares no substitution (recorded life placed as is) is exact.
    assert mr.construction_with_declared_substitution(
        "EXACT", {"elimination_plan": {**plan, "life_substitutions": []}}
    ) == ("EXACT", None)
    # A substitution for another seat is not this dimension's.
    other = dict(plan, victim="p1")
    assert mr.construction_with_declared_substitution("EXACT", {"elimination_plan": other}) == (
        "EXACT",
        None,
    )
    # Recorded == placed is not a substitution.
    same = dict(
        plan,
        life_substitutions=[
            {
                **plan["life_substitutions"][0],
                "placed_life": plan["life_substitutions"][0]["recorded_life"],
            }
        ],
    )
    assert mr.construction_with_declared_substitution("EXACT", {"elimination_plan": same}) == (
        "EXACT",
        None,
    )


def test_an_unreadable_plan_fails_the_construction_closed() -> None:
    # A plan that cannot state its substitutions is uninterpretable: the row
    # must not read as exact just because the list is missing or malformed.
    plan = _declared_plan(_effective_record())
    assert mr.construction_with_declared_substitution(
        "EXACT", {"elimination_plan": {**plan, "life_substitutions": None}}
    ) == ("UNRECOGNIZED", None)
    assert mr.construction_with_declared_substitution(
        "EXACT",
        {
            "elimination_plan": {
                **plan,
                "life_substitutions": [{"player_id": "p2", "recorded_life": "0"}],
            }
        },
    ) == ("UNRECOGNIZED", None)
    assert mr.construction_with_declared_substitution(
        "EXACT", {"elimination_plan": {**plan, "victim": None}}
    ) == ("UNRECOGNIZED", None)


# --------------------------------------------------------------------------- #
# The production executor path (the red: the old code reports EXACT)
# --------------------------------------------------------------------------- #


class _ExactArrival:
    construction_verdict = "EXACT"
    mismatches: tuple[str, ...] = ()


class _MismatchArrival:
    construction_verdict = "MISMATCH"
    mismatches = ("zone multiset P2|BATTLEFIELD: requested 1 observed 0",)


class _StubProbe:
    CAUSAL_STACK_ELIMINATION = "causal_stack_elimination"

    def __init__(self, arrival: Any) -> None:
        self._arrival = arrival

    def drive_arrival(self, *args: Any, **kwargs: Any) -> Any:
        return self._arrival


class _FakeClient:
    def events(self, after_offset: int = 0) -> dict[str, Any]:
        return {"events": [], "latest_offset": 0}

    def pending_decision(self, *, attempts: int = 60) -> None:
        return None

    def complete_arrival(self) -> dict[str, Any]:
        return {"observation": {}}


def _execute(
    monkeypatch: pytest.MonkeyPatch, record: dict[str, Any], created: dict[str, Any], arrival: Any
) -> mr.RowExecution:
    monkeypatch.setattr(mr, "probe_module", lambda: _StubProbe(arrival))
    return mr.execute_row(  # type: ignore[arg-type]
        _FakeClient(), record, created, mr.RowSpec()
    )


def test_the_executor_never_labels_a_declared_substitution_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _effective_record()
    created = {"elimination_plan": _declared_plan(record)}
    execution = _execute(monkeypatch, record, created, _ExactArrival())
    # The old code reported the engine's own EXACT for this row; the declared
    # substitution must now be visible as the variance it is.
    assert execution.construction_verdict == "ALLOWED_VARIANCE"
    assert execution.variance_source == mr.DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE
    document = execution.document()
    assert document["construction_verdict"] == "ALLOWED_VARIANCE"
    assert document["variance_source"] == mr.DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE


def test_the_executor_keeps_a_construction_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _effective_record()
    created = {"elimination_plan": _declared_plan(record)}
    execution = _execute(monkeypatch, record, created, _MismatchArrival())
    assert execution.construction_verdict == "MISMATCH"
    assert execution.variance_source is None


def test_a_row_without_an_elimination_plan_keeps_its_exact_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _effective_record()
    execution = _execute(monkeypatch, record, {}, _ExactArrival())
    assert execution.construction_verdict == "EXACT"
    assert execution.variance_source is None


# --------------------------------------------------------------------------- #
# The receipt
# --------------------------------------------------------------------------- #


def _verified_execution(variance_source: str | None) -> mr.RowExecution:
    return mr.RowExecution(
        fixture_id=FIXTURE_ID,
        verified=True,
        construction_verdict=("ALLOWED_VARIANCE" if variance_source else "EXACT"),
        detail="obligation observed",
        token_evidence={"player_leaves:P2": {"events": [1]}},
        terminal_facts={"some fact": True},
        variance_source=variance_source,
    )


def _receipt_record() -> dict[str, Any]:
    return {
        "fixture_id": FIXTURE_ID,
        "expected_events": {"required_events": ["player_leaves:P2"]},
        "terminal_postconditions": [],
        "requested_state_digest": "a" * 64,
        "obligation_digest": "b" * 64,
    }


def test_the_receipt_carries_the_declared_substitution_assertion_class() -> None:
    record = _receipt_record()
    receipt = mr.positive_receipt(
        _verified_execution(mr.DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE),
        record,
        candidate_commit="c" * 40,
        runner_digest="d" * 64,
    )
    assert receipt["construction_verdict"] == "ALLOWED_VARIANCE"
    assert receipt["variance_source"] == mr.DECLARED_CAUSAL_SUBSTITUTION_VARIANCE_SOURCE
    assert receipt["assertion_class"] == "BEHAVIOUR_OBSERVED_LAB_DECLARED_CAUSAL_SUBSTITUTION"
    assert receipt["assertion_kind"] == "POSITIVE_BEHAVIOUR"
    assert receipt["outcome"] == "PASS"
    # The new class neither hides the variance nor blocks the credit path.
    assert (
        receipt_mod._digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        == (receipt["receipt_digest"])
    )
    credited = receipt_mod.positive_fixture_credit(
        [receipt],
        candidate="xmage",
        expected_commit="c" * 40,
        denominator={FIXTURE_ID: record},
        expected_runner_digest="d" * 64,
    )
    assert credited == {FIXTURE_ID: [receipt["test_identity"]]}


def test_a_row_without_a_variance_stays_a_plain_observed_behaviour() -> None:
    receipt = mr.positive_receipt(
        _verified_execution(None),
        _receipt_record(),
        candidate_commit="c" * 40,
        runner_digest="d" * 64,
    )
    assert receipt["construction_verdict"] == "EXACT"
    assert receipt["variance_source"] is None
    assert receipt["assertion_class"] == "BEHAVIOUR_OBSERVED"
