"""Tests for the mid-game lane's capability consumer and row classification.

These tests are pure unit tests over the consumer's own logic. They do not
claim engine capability. Engine reachability is proven by the native JUnit
suite (``XmageMidgameLaneTest``) and by
``scripts/run_midgame_capability_probe.py``; what is tested here is that the
consumer refuses to promote anything the engine did not actually report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_lane as ml

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT = REPO_ROOT / "qualification" / "midgame-lane-20260929" / "MIDGAME_CAPABILITY_PROBE.json"


def _arrival(**overrides: Any) -> dict[str, Any]:
    arrival: dict[str, Any] = {
        "construction_match": True,
        "mismatches": [],
        "requested_state_digest": "a" * 64,
        "constructed_state_digest": "b" * 64,
        "observation": {},
    }
    arrival.update(overrides)
    return arrival


class TestManifestConsumer:
    def test_missing_manifest_fails_closed_instead_of_falling_back(self) -> None:
        """A provider without the per-dimension manifest must never fall back.

        The coarse global flag is exactly the statement that caused the
        current-boundary lane to fail 44 rows closed. Reading it as a
        substitute for the manifest would reintroduce the original defect.
        """

        class _Client(ml.MidgameLaneClient):
            def __init__(self) -> None:
                self.requests: list[tuple[str, Any]] = []
                self._engine_commit = None

            def request(self, message_type: str, payload: Any, **_: Any) -> dict[str, Any]:
                self.requests.append((message_type, payload))
                return {
                    "success": True,
                    "payload": {
                        "capabilities": {
                            "starting_state_injection_supported": False,
                        }
                    },
                }

        with pytest.raises(ml.MidgameLaneError, match="per-dimension starting-state manifest"):
            _Client().read_dimension_manifest()

    def test_manifest_is_read_from_the_engine_verbatim(self) -> None:
        raw_manifest = {
            "schema_version": "native-state-restoration-dimensions-1.1.0",
            "supported_dimensions": ["a supported dimension"],
            "unsupported_dimensions": ["an unsupported dimension"],
        }

        class _Client(ml.MidgameLaneClient):
            def __init__(self) -> None:
                self._engine_commit = None

            def request(self, message_type: str, payload: Any, **_: Any) -> dict[str, Any]:
                return {
                    "success": True,
                    "payload": {
                        "capabilities": {
                            "starting_state_injection_supported": False,
                            "starting_state_dimensions_supported": True,
                            "starting_state_dimensions": raw_manifest,
                        }
                    },
                }

        manifest = _Client().read_dimension_manifest()
        assert manifest.global_supported is False
        assert manifest.per_dimension_supported is True
        assert manifest.supported == ("a supported dimension",)
        assert manifest.unsupported == ("an unsupported dimension",)
        assert manifest.as_dict()["schema_version"] == raw_manifest["schema_version"]


class TestRowClassification:
    def test_clean_arrival_is_reachable(self) -> None:
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4", ml.MIDGAME_LANE, _arrival(), engine_commit="abc"
        )
        assert verdict.outcome == "ENGINE_NATIVE_REACHABLE"
        assert verdict.engine_accepted_starting_state is True
        assert verdict.mismatches == ()

    def test_declaration_step_priority_mismatch_is_named_not_hidden(self) -> None:
        """The documented allowance is applied, and reported, never erased."""
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(
                construction_match=False, mismatches=["priority_player: requested P1 observed P2"]
            ),
            engine_commit="abc",
        )
        assert verdict.outcome == "ENGINE_NATIVE_REACHABLE"
        assert verdict.construction_match is False, "the engine's own raw bit must be reported"
        assert verdict.allowance_applied == ("priority_player: requested P1 observed P2",)

    def test_a_zone_mismatch_is_never_allowanced(self) -> None:
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(
                construction_match=False,
                mismatches=[
                    "priority_player: requested P1 observed P2",
                    "zone multiset P1|BATTLEFIELD|Grizzly Bears: requested 3 observed 1",
                ],
            ),
            engine_commit="abc",
        )
        assert verdict.outcome == "CONSTRUCTION_MISMATCH"
        assert verdict.detail is not None and "Grizzly Bears" in verdict.detail

    def test_a_false_match_flag_with_no_mismatch_listing_is_not_promoted(self) -> None:
        verdict = ml.classification_from_arrival(
            "WS05-CMD-ELIM-4",
            ml.MIDGAME_LANE,
            _arrival(construction_match=False),
            engine_commit="abc",
        )
        # A false verdict with an empty mismatch list is uninterpretable, not
        # a construction success: it fails closed with no reachability credit.
        assert verdict.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert verdict.engine_accepted_starting_state is False

    def test_causal_verdict_requires_both_engine_match_and_terminal(self) -> None:
        stack_verdict = {"causal_match": True, "mismatches": []}
        terminal = {"kind": "priority_ring_with_live_response", "observed": True}
        verdict = ml.classification_from_causal_verdict(
            "WS05-MP-PRIO-3",
            ml.MIDGAME_LANE,
            "causal_stack",
            stack_verdict,
            terminal,
            engine_commit="abc",
        )
        assert verdict.outcome == "CAUSAL_ROUTE_REACHABLE"
        assert verdict.engine_accepted_starting_state is True
        assert verdict.entry_mode == "causal_stack"

    def test_causal_stack_without_terminal_observation_stays_measured(self) -> None:
        stack_verdict = {"causal_match": True, "mismatches": []}
        terminal = {"kind": "commander_zone_choice", "observed": False, "detail": "absent"}
        verdict = ml.classification_from_causal_verdict(
            "WS05-CMD-ZONE-GY-YES",
            ml.MIDGAME_LANE,
            "causal_stack",
            stack_verdict,
            terminal,
            engine_commit="abc",
        )
        assert verdict.outcome == "CAUSAL_ROUTE_MEASURED_BLOCKED"
        assert verdict.detail is not None and "absent" in verdict.detail

    def test_causal_mismatch_is_never_promoted(self) -> None:
        stack_verdict = {"causal_match": False, "mismatches": ["STACK_SOURCE_ABSENT: x"]}
        verdict = ml.classification_from_causal_verdict(
            "WS05-MP-PRIO-3",
            ml.MIDGAME_LANE,
            "causal_stack",
            stack_verdict,
            None,
            engine_commit="abc",
        )
        assert verdict.outcome == "CONSTRUCTION_MISMATCH"

    def test_rejected_row_records_the_engine_code_and_no_credit(self) -> None:
        verdict = ml.rejected_verdict(
            "WS05-MP-PRIO-3",
            ml.MIDGAME_LANE,
            code="midgame_starting_state_rejected",
            detail="UNSUPPORTED_ZONE",
            engine_commit="abc",
        )
        assert verdict.outcome == "ENGINE_REJECTED"
        assert verdict.engine_accepted_starting_state is False
        assert verdict.construction_match is None
        assert verdict.requested_state_digest is None


class TestProbeReceipt:
    """Guards the persisted runtime receipt against silent shape drift."""

    def test_receipt_is_present_and_engine_identity_pinned(self) -> None:
        assert RECEIPT.is_file(), f"missing runtime receipt {RECEIPT}"
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        assert receipt["engine_commit"] == "b19596980f2734496ea1896504253e1bdd2756dd"
        assert receipt["lane"] == ml.MIDGAME_LANE
        assert receipt["protocol_version"] == ml.PROTOCOL_VERSION
        assert receipt["evidence_class"] == "FRESH_RUNTIME_PROTOCOL2_PROCESS"

    def test_receipt_publishes_the_per_dimension_manifest(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        manifest = receipt["starting_state_dimensions_manifest"]
        assert manifest["per_dimension_supported"] is True
        assert manifest["supported_dimensions"], "supported dimensions must be enumerated"
        assert manifest["unsupported_dimensions"], "unsupported dimensions must be enumerated"

    def test_every_row_carries_an_explicit_outcome_and_never_a_bare_pass(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        allowed = {
            "ENGINE_NATIVE_REACHABLE",
            "ENGINE_STATE_ACCEPTED",
            "CAUSAL_ROUTE_REACHABLE",
            "CAUSAL_ROUTE_MEASURED_BLOCKED",
            "CONSTRUCTION_MISMATCH",
            "ENGINE_REJECTED",
            "TRANSPORT_FAILURE",
        }
        assert receipt["rows"], "the receipt must contain probed rows"
        for row in receipt["rows"]:
            assert row["outcome"] in allowed, row
            assert row["outcome"] != "PASS"
            assert row["lane"] == ml.MIDGAME_LANE
            if row["outcome"] == "ENGINE_REJECTED":
                assert row["code"], "an engine-rejected row must carry the engine's own code"
                assert row["engine_accepted_starting_state"] is False

    def test_reachable_rows_all_carry_the_engine_construction_evidence(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        reachable = [row for row in receipt["rows"] if row["outcome"] == "ENGINE_NATIVE_REACHABLE"]
        assert reachable, "the probe must demonstrate at least one engine-native reachable row"
        for row in reachable:
            assert row["engine_accepted_starting_state"] is True
            assert row["requested_state_digest"]
            assert row["constructed_state_digest"]
            unexpected = [
                mismatch
                for mismatch in row["mismatches"]
                if not mismatch.startswith(ml.DECLARATION_STEP_PRIORITY_ALLOWANCE)
            ]
            assert not unexpected, (row["fixture_id"], unexpected)

    def test_receipt_declares_the_row_set_it_probed(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        probed = {row["fixture_id"] for row in receipt["rows"]}
        assert probed == {row["fixture_id"] for row in receipt["rows"]}
        assert receipt["counts"]["probed"] == len(receipt["rows"])
        total = sum(
            receipt["counts"][key]
            for key in (
                "engine_native_reachable",
                "engine_state_accepted_obligation_not_executed",
                "causal_route_reachable",
                "causal_route_measured_blocked",
                "construction_mismatch",
                "engine_rejected",
            )
        )
        assert total == len(receipt["rows"]), "row counts must account for every probed row"


class TestFrozenRecords:
    def test_frozen_record_lookup_fails_closed_when_absent(self) -> None:
        materialization = (
            REPO_ROOT / "qualification" / "ws47" / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
        )
        assert materialization.is_file()
        with pytest.raises(KeyError):
            ml.frozen_record(materialization, "NO-SUCH-FIXTURE")

    def test_a_probed_frozen_record_really_exists(self) -> None:
        materialization = (
            REPO_ROOT / "qualification" / "ws47" / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
        )
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        for row in receipt["rows"]:
            record = ml.frozen_record(materialization, row["fixture_id"])
            assert record["requested_state_digest"], row["fixture_id"]
            assert record["execution_entry_mode"] == "NATIVE_STATE_LOAD", row["fixture_id"]
