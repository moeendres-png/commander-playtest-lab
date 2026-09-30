"""Tests for the mid-game lane's capability consumer and row classification.

These tests are pure unit tests over the consumer's own logic. They do not
claim engine capability. Engine reachability is proven by the native JUnit
suite (``XmageMidgameLaneTest``) and by
``scripts/run_midgame_capability_probe.py``; what is tested here is that the
consumer refuses to promote anything the engine did not actually report.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import bridge_launcher
from commander_lab.qualification.current_boundary import midgame_lane as ml
from commander_lab.qualification.current_boundary import receipts as receipt_mod

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT = (
    REPO_ROOT
    / "qualification"
    / "pb03-fresh-main-reconciliation-20260929"
    / "MIDGAME_CAPABILITY_PROBE.json"
)


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
        assert verdict.construction_verdict == "EXACT"

    def test_declaration_step_priority_mismatch_is_named_not_hidden(self) -> None:
        """The documented allowance is applied, and reported, never erased.

        The classification is stated explicitly as ALLOWED_VARIANCE rather than
        being inferable only from outcome + raw bit: the engine's own compare
        reported a mismatch, and the row must never read as an exact match.
        """
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
        assert verdict.construction_verdict == "ALLOWED_VARIANCE"
        assert verdict.allowance_applied == ("priority_player: requested P1 observed P2",)

    def test_the_allowance_is_never_vacuous_or_inferred(self) -> None:
        """Only the exact declared prefix is an allowance; nothing else is."""
        exact = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(construction_match=True, mismatches=[]),
            engine_commit="abc",
        )
        assert exact.construction_verdict == "EXACT"
        mismatched = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(
                construction_match=False,
                mismatches=["priority_player: requested P1 observed P2", "hand count mismatch"],
            ),
            engine_commit="abc",
        )
        assert mismatched.outcome == "CONSTRUCTION_MISMATCH"
        assert mismatched.construction_verdict == "MISMATCH"
        assert mismatched.engine_accepted_starting_state is False
        # A negative raw bit with no recognized mismatch is uninterpretable.
        unrecognized = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(construction_match=False, mismatches=[]),
            engine_commit="abc",
        )
        assert unrecognized.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert unrecognized.construction_verdict == "UNRECOGNIZED"

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

    def test_an_unrecorded_terminal_is_not_reachability_credit(self) -> None:
        """A produced route without a recorded terminal is measured blocked.

        Reachability requires the row's terminal obligation to be produced and
        recorded; a caller that supplies no terminal must not inherit credit
        for a route whose terminal was never observed.
        """
        verdict = ml.classification_from_causal_verdict(
            "WS05-MP-ELIM-PRIO-3",
            ml.MIDGAME_LANE,
            "causal_elimination",
            {"causal_match": True, "mismatches": []},
            None,
            engine_commit="abc",
        )
        assert verdict.outcome == "CAUSAL_ROUTE_MEASURED_BLOCKED"
        assert verdict.detail is not None and "terminal" in verdict.detail
        assert verdict.engine_accepted_starting_state is True

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

    def test_a_rejected_causal_row_keeps_its_requested_entry_mode(self) -> None:
        """A causal row rejected before arrival must not be labelled placement.

        The persisted evidence would otherwise claim the probe attempted a route
        it never requested, and the admission/runtime matrix would describe the
        wrong route for that record.
        """
        verdict = ml.rejected_verdict(
            "WS05-MP-ELIM-CONTROL-3",
            ml.MIDGAME_LANE,
            code="midgame_causal_preparation_rejected",
            detail="CAUSAL_ELIMINATION_PREPARATION_REJECTED",
            engine_commit="abc",
            entry_mode="causal_elimination",
        )
        assert verdict.outcome == "ENGINE_REJECTED"
        assert verdict.entry_mode == "causal_elimination"
        assert verdict.as_dict()["entry_mode"] == "causal_elimination"
        assert verdict.requested_state_digest is None


class TestProbeReceipt:
    """Guards the persisted runtime receipt against silent shape drift."""

    def test_receipt_is_present_and_engine_identity_pinned(self) -> None:
        assert RECEIPT.is_file(), f"missing runtime receipt {RECEIPT}"
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        # The receipt must name the canonical live pin, not a historical donor
        # pin: a row observed on another engine epoch is not evidence for this
        # one.
        assert receipt["engine_commit"] == bridge_launcher.canonical_xmage_engine_pin()
        assert receipt["candidate_commit"] == receipt["engine_commit"]
        assert receipt["lane"] == ml.MIDGAME_LANE
        assert receipt["protocol_version"] == ml.PROTOCOL_VERSION
        assert receipt["evidence_class"] == "FRESH_RUNTIME_PROTOCOL2_PROCESS"
        assert receipt["receipt_digest"]
        assert receipt["runner_digest"]
        # The declared commit constant is not enough: the receipt must carry the
        # provider-reported loaded artifact's file-backed digest.
        assert receipt["engine_artifact_kind"] == "file"
        assert re.fullmatch(r"[0-9a-f]{64}", receipt["engine_artifact_sha256"])
        assert receipt["engine_artifact_size"] > 0

    def test_receipt_content_digest_binds_every_field(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
        assert receipt_mod.document_digest(body) == receipt["receipt_digest"]

    def test_probe_and_runtime_ledger_share_the_exact_run_identity(self) -> None:
        """The two PB-03 runtime artifacts must come from the same run.

        They are produced back-to-back on one clean head, so their recorded
        runner digests and engine candidate must agree. Regenerating one without
        the other leaves evidence from two epochs joined as if one, which this
        guard refuses.
        """
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        ledger = json.loads(
            (
                REPO_ROOT
                / "qualification"
                / "final-current-boundary-20260927"
                / "PB03_RUNTIME_EXECUTION.json"
            ).read_text(encoding="utf-8")
        )
        assert receipt["runner_digest"] == ledger["runner_digest"]
        assert receipt["runner_commit"] == ledger["runner_commit"]
        assert receipt["runner_tree"] == ledger["runner_tree"]
        assert receipt["engine_commit"] == ledger["candidate_commit"]
        # Both artifacts must name the same loaded engine artifact.
        assert receipt["engine_artifact_sha256"] == ledger["engine_artifact_sha256"]
        assert receipt["engine_artifact_kind"] == ledger["engine_artifact_kind"] == "file"
        # And the admission handshake of the same run must name it too.
        admission = json.loads(
            (
                REPO_ROOT
                / "qualification"
                / "final-current-boundary-20260927"
                / "PB03_DIMENSION_ADMISSION.json"
            ).read_text(encoding="utf-8")
        )
        assert (
            admission["provider_identity"]["engine_artifact_sha256"]
            == receipt["engine_artifact_sha256"]
        )
        assert receipt["engine_commit"] == bridge_launcher.canonical_xmage_engine_pin()

    def test_every_row_states_its_construction_verdict_explicitly(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        allowed = {"EXACT", "ALLOWED_VARIANCE", "MISMATCH", "UNRECOGNIZED", None}
        for row in receipt["rows"]:
            assert row.get("construction_verdict") in allowed, row["fixture_id"]
            if row["outcome"] == "ENGINE_NATIVE_REACHABLE":
                if row["engine_construction_match"] is True:
                    assert row["construction_verdict"] == "EXACT", row["fixture_id"]
                else:
                    # The raw engine bit said "no match"; the row survives only
                    # as the documented allowance, and that must be visible.
                    assert row["construction_verdict"] == "ALLOWED_VARIANCE", row["fixture_id"]
                    assert row["declaration_step_priority_allowance_applied"], row["fixture_id"]

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
        assert len(probed) == len(receipt["rows"]), "a row id must appear exactly once"
        assert receipt["counts"]["probed"] == len(receipt["rows"])
        total = sum(
            receipt["counts"][key]
            for key in (
                "engine_native_reachable",
                "engine_state_accepted_obligation_not_executed",
                "causal_route_reachable",
                "causal_route_measured_blocked",
                "construction_mismatch",
                "unrecognized_construction_verdict",
                "transport_failure",
                "engine_rejected",
            )
        )
        assert total == len(receipt["rows"]), "row counts must account for every probed row"


class TestReceiptFreshness:
    """A receipt is only fresh when the exact executing identities match.

    Missing, empty or mismatched runner identity is zero credit with an
    auditable stale classification, never a grandfather.
    """

    @staticmethod
    def _receipt(**overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema_version": ml.MIDGAME_RECEIPT_SCHEMA,
            "engine_commit": "a" * 40,
            "candidate_commit": "a" * 40,
            "runner_commit": "b" * 40,
            "runner_tree": "c" * 40,
            "runner_digest": "d" * 64,
            "engine_artifact_kind": "file",
            "engine_artifact_sha256": "e" * 64,
        }
        body.update(overrides)
        body["receipt_digest"] = receipt_mod.document_digest(body)
        return body

    @staticmethod
    def _freshness(receipt: Any, **overrides: Any) -> str:
        expected: dict[str, Any] = {
            "expected_runner_digest": "d" * 64,
            "expected_engine_commit": "a" * 40,
            "expected_engine_artifact_sha256": "e" * 64,
        }
        expected.update(overrides)
        return ml.receipt_freshness(receipt, **expected)

    def test_exact_identities_are_fresh(self) -> None:
        assert self._freshness(self._receipt()) == ml.MIDGAME_RECEIPT_FRESH

    def test_another_runner_or_engine_epoch_is_stale(self) -> None:
        assert (
            self._freshness(self._receipt(), expected_runner_digest="f" * 64)
            == ml.MIDGAME_RECEIPT_STALE
        )
        assert (
            self._freshness(self._receipt(), expected_engine_commit="f" * 40)
            == ml.MIDGAME_RECEIPT_STALE
        )

    def test_a_different_engine_artifact_is_stale(self) -> None:
        """A well-formed digest of another artifact is not this run's identity."""
        assert (
            self._freshness(self._receipt(), expected_engine_artifact_sha256="f" * 64)
            == ml.MIDGAME_RECEIPT_STALE
        )

    def test_a_receipt_without_the_loaded_artifact_identity_is_never_fresh(self) -> None:
        for overrides, expected in (
            ({"engine_artifact_sha256": ""}, ml.MIDGAME_RECEIPT_MISSING),
            ({"engine_artifact_kind": ""}, ml.MIDGAME_RECEIPT_MISSING),
            ({"engine_artifact_kind": "directory"}, ml.MIDGAME_RECEIPT_INVALID),
            ({"engine_artifact_sha256": "not-a-digest"}, ml.MIDGAME_RECEIPT_INVALID),
        ):
            assert self._freshness(self._receipt(**overrides)) == expected, overrides

    def test_missing_identity_is_missing_not_fresh(self) -> None:
        assert self._freshness(self._receipt(runner_digest="")) == ml.MIDGAME_RECEIPT_MISSING
        without_digest = self._receipt()
        del without_digest["receipt_digest"]
        assert self._freshness(without_digest) == ml.MIDGAME_RECEIPT_MISSING

    def test_tampered_or_wrong_schema_is_invalid(self) -> None:
        tampered = self._receipt()
        tampered["engine_commit"] = "9" * 40
        assert (
            self._freshness(tampered, expected_engine_commit="9" * 40) == ml.MIDGAME_RECEIPT_INVALID
        )
        assert (
            self._freshness(self._receipt(schema_version="something-else"))
            == ml.MIDGAME_RECEIPT_INVALID
        )
        assert self._freshness(None) == ml.MIDGAME_RECEIPT_INVALID

    def test_unavailable_expected_identity_is_never_fresh(self) -> None:
        for overrides in (
            {"expected_runner_digest": ""},
            {"expected_engine_commit": ""},
            {"expected_engine_artifact_sha256": ""},
        ):
            assert self._freshness(self._receipt(), **overrides) == ml.MIDGAME_RECEIPT_MISSING


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


class TestFailClosedConstructionVerdicts:
    """Additional wrong-reason controls for the construction verdict.

    The engine's verdict may only become reachability credit when it is a real
    JSON boolean accompanied by a real mismatch list, and a negative raw bit may
    survive only as the documented declaration-step allowance. Each case below
    is an uninterpretable or contradictory response that must earn nothing.
    """

    def test_a_false_match_flag_with_a_missing_mismatch_list_fails_closed(self) -> None:
        arrival = _arrival(construction_match=False)
        arrival.pop("mismatches")
        verdict = ml.classification_from_arrival(
            "WS05-CMD-ELIM-4", ml.MIDGAME_LANE, arrival, engine_commit="abc"
        )
        assert verdict.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert verdict.engine_accepted_starting_state is False

    def test_a_false_match_flag_with_a_null_mismatch_list_fails_closed(self) -> None:
        verdict = ml.classification_from_arrival(
            "WS05-CMD-ELIM-4",
            ml.MIDGAME_LANE,
            _arrival(construction_match=False, mismatches=None),
            engine_commit="abc",
        )
        assert verdict.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert verdict.engine_accepted_starting_state is False

    def test_a_false_match_flag_with_a_malformed_mismatch_list_fails_closed(self) -> None:
        # A bare string is not a mismatch list; reading it as "no mismatches"
        # is exactly how a version-skewed response would be promoted.
        verdict = ml.classification_from_arrival(
            "WS05-CMD-ELIM-4",
            ml.MIDGAME_LANE,
            _arrival(construction_match=False, mismatches="UNSUPPORTED_ZONE"),
            engine_commit="abc",
        )
        assert verdict.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert verdict.engine_accepted_starting_state is False

    def test_a_false_match_flag_with_an_unknown_mismatch_kind_is_not_allowanced(self) -> None:
        # A mismatch this consumer does not model is never converted into the
        # documented allowance. The engine reported a concrete defect, so the
        # bounded classification is CONSTRUCTION_MISMATCH — which still carries
        # no reachability credit.
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(
                construction_match=False,
                mismatches=["something_new: requested X observed Y"],
            ),
            engine_commit="abc",
        )
        assert verdict.outcome == "CONSTRUCTION_MISMATCH"
        assert verdict.outcome != "ENGINE_NATIVE_REACHABLE"
        assert verdict.engine_accepted_starting_state is False
        assert verdict.allowance_applied == ()
        assert verdict.detail is not None and "something_new" in verdict.detail

    def test_a_non_boolean_match_flag_fails_closed(self) -> None:
        # bool("false") is True, so a string flag must never be trusted.
        for raw in ("false", "true", 0, 1, None, []):
            verdict = ml.classification_from_arrival(
                "WS05-CMD-ELIM-4",
                ml.MIDGAME_LANE,
                _arrival(construction_match=raw, mismatches=[]),
                engine_commit="abc",
            )
            assert verdict.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT", raw
            assert verdict.engine_accepted_starting_state is False, raw

    def test_a_positive_match_flag_with_a_real_mismatch_fails_closed(self) -> None:
        # The engine computes match as "mismatches is empty", so a positive flag
        # beside a reported defect is self-contradictory. The named defect is
        # still reported, and the row earns no credit either way.
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(
                construction_match=True, mismatches=["zone multiset X: requested 1 observed 0"]
            ),
            engine_commit="abc",
        )
        assert verdict.outcome == "CONSTRUCTION_MISMATCH"
        assert verdict.outcome != "ENGINE_NATIVE_REACHABLE"
        assert verdict.engine_accepted_starting_state is False

    def test_a_positive_match_flag_with_only_allowance_mismatches_fails_closed(self) -> None:
        # No real defect is named, yet the engine's own flag contradicts its own
        # mismatch list: that response cannot be interpreted, so it is not a pass.
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(
                construction_match=True,
                mismatches=["priority_player: requested P1 observed P2"],
            ),
            engine_commit="abc",
        )
        assert verdict.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert verdict.engine_accepted_starting_state is False

    def test_the_modeled_allowance_survives_a_negative_raw_bit(self) -> None:
        # The only negative-verdict case the contract permits to keep its
        # bounded classification is the documented declaration-step allowance.
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            _arrival(
                construction_match=False,
                mismatches=["priority_player: requested P1 observed P2"],
            ),
            engine_commit="abc",
        )
        assert verdict.outcome == "ENGINE_NATIVE_REACHABLE"
        assert verdict.construction_match is False, "the engine's raw bit is still reported"
        assert verdict.allowance_applied == ("priority_player: requested P1 observed P2",)

    def test_a_causal_verdict_with_a_non_boolean_match_flag_fails_closed(self) -> None:
        verdict = ml.classification_from_causal_verdict(
            "WS05-MP-PRIO-3",
            ml.MIDGAME_LANE,
            "causal_stack",
            {"causal_match": "false", "mismatches": []},
            None,
            engine_commit="abc",
        )
        assert verdict.outcome == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert verdict.engine_accepted_starting_state is False


class TestTransportDeadlineAndClassification:
    """The advertised timeout must bound the wait, and transport failures must
    never be reported as an accepted engine state.

    These are deterministic: the child processes below are local one-liners with
    a known behaviour, so nothing here depends on the pinned engine.
    """

    @staticmethod
    def _client(code: str) -> ml.MidgameLaneClient:
        return ml.MidgameLaneClient(
            (sys.executable, "-c", code), Path(__file__).resolve().parents[2]
        )

    def test_a_stalled_child_times_out_and_is_reaped(self) -> None:
        # The child reads the request and then never answers.
        code = "import sys, time\nsys.stdin.readline()\ntime.sleep(600)\n"
        client = self._client(code)
        with pytest.raises(ml.MidgameLaneTimeout) as excinfo, client:
            client.request("get_capabilities", None, timeout_s=1.0)
        assert "MIDGAME_LANE_TIMEOUT" in str(excinfo.value)
        # The timeout is recorded on the tape with its applied deadline.
        timeout_entries = [e for e in client.tape if e.get("direction") == "timeout"]
        assert len(timeout_entries) == 1
        assert timeout_entries[0]["timeout_s"] == 1.0
        assert timeout_entries[0]["classification"] == "TIMEOUT"
        # The child was reaped, so no zombie survives the failed row.
        assert client._process is None
        assert not any(e.get("message_type") == "shutdown_engine" for e in client.tape)

    def test_a_timeout_is_a_transport_failure_not_an_accepted_state(self) -> None:
        verdict, outcome = ml.failure_verdict(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            ml.MidgameLaneTimeout("MIDGAME_LANE_TIMEOUT: stalled"),
            engine_commit="abc",
        )
        assert outcome == "TRANSPORT_FAILURE"
        assert verdict.outcome == "TRANSPORT_FAILURE"
        assert verdict.engine_accepted_starting_state is False
        assert verdict.construction_match is None
        assert verdict.requested_state_digest is None

    def test_a_closed_child_is_a_transport_failure(self) -> None:
        # The child exits before answering, so stdout closes with no line.
        client = self._client("import sys\nsys.stdin.readline()\nsys.exit(0)\n")
        with pytest.raises(ml.MidgameLaneTransportError) as excinfo, client:
            client.request("get_capabilities", None, timeout_s=30.0)
        assert not isinstance(excinfo.value, ml.MidgameLaneTimeout)
        verdict, outcome = ml.failure_verdict(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            excinfo.value,
            engine_commit="abc",
        )
        assert outcome == "TRANSPORT_FAILURE"
        assert verdict.engine_accepted_starting_state is False

    def test_a_non_json_answer_is_a_protocol_failure(self) -> None:
        client = self._client(
            "import sys\nsys.stdin.readline()\nsys.stdout.write('not json\\n')\nsys.stdout.flush()\n"
        )
        with pytest.raises(ml.MidgameLaneProtocolError) as excinfo, client:
            client.request("get_capabilities", None, timeout_s=30.0)
        assert isinstance(excinfo.value, ml.MidgameLaneTransportError)
        verdict, outcome = ml.failure_verdict(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            excinfo.value,
            engine_commit="abc",
        )
        assert outcome == "TRANSPORT_FAILURE"
        assert verdict.outcome == "TRANSPORT_FAILURE"
        assert verdict.engine_accepted_starting_state is False

    def test_a_non_object_answer_is_a_protocol_failure(self) -> None:
        client = self._client(
            "import sys\nsys.stdin.readline()\nsys.stdout.write('[1,2,3]\\n')\nsys.stdout.flush()\n"
        )
        with pytest.raises(ml.MidgameLaneProtocolError), client:
            client.request("get_capabilities", None, timeout_s=30.0)

    def test_a_broken_pipe_is_a_transport_failure(self) -> None:
        # The child dies at once, so the write fails or the read closes.
        client = self._client("import sys\nsys.exit(0)\n")
        with pytest.raises(ml.MidgameLaneTransportError) as excinfo, client:
            client.request("get_capabilities", None, timeout_s=30.0)
        verdict, outcome = ml.failure_verdict(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            excinfo.value,
            engine_commit="abc",
        )
        assert outcome == "TRANSPORT_FAILURE"
        assert verdict.engine_accepted_starting_state is False

    def test_only_a_recognized_obligation_case_is_reported_as_accepted(self) -> None:
        verdict, outcome = ml.failure_verdict(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            ml.MidgameLaneError("the engine offered no keep option for the mulligan"),
            engine_commit="abc",
            obligation_code="OBLIGATION_NOT_EXECUTED",
        )
        assert outcome == "ENGINE_STATE_ACCEPTED"
        assert verdict.outcome == "ENGINE_REJECTED"
        assert verdict.engine_accepted_starting_state is True
        # Even the accepted-obligation case earns no reachability outcome.
        assert verdict.outcome != "ENGINE_NATIVE_REACHABLE"

    def test_an_unrelated_exception_is_never_converted(self) -> None:
        with pytest.raises(TypeError):
            ml.failure_verdict(
                "WS05-MP-COMBAT-4",
                ml.MIDGAME_LANE,
                RuntimeError("something else entirely"),
                engine_commit="abc",
            )

    def test_a_request_without_a_live_child_is_a_transport_failure(self) -> None:
        client = ml.MidgameLaneClient((sys.executable, "-c", "pass"), Path("."))
        with pytest.raises(ml.MidgameLaneTransportError):
            client.request("get_capabilities", None, timeout_s=5.0)


class TestReceiptCarriesNoHiddenIdentity:
    """The persisted receipt is a public artifact: it must carry no hand identity.

    The probe names no request principal, so the lane answers it with the
    principal-neutral projection and the receipt can only contain public counts.
    This is the end-to-end negative control for the hidden-information finding.
    """

    def test_no_seat_in_any_row_observation_carries_a_hand_identity_array(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        checked = 0
        for row in receipt["rows"]:
            if "observation" in row:
                raise AssertionError(
                    "the receipt must not persist a per-row observation dump: "
                    + str(row.get("fixture_id"))
                )
            causal = row.get("causal_verdict")
            if isinstance(causal, dict) and "observation" in causal:
                raise AssertionError("the causal verdict must not persist an observation dump")
            checked += 1
        assert checked == len(receipt["rows"])

    def test_the_receipt_never_names_a_principal_hand_identity(self) -> None:
        import re

        text = RECEIPT.read_text(encoding="utf-8")
        # A hand identity list would appear as a JSON array of card names under a
        # "hand" key. Neither the key nor an opponent-hand dump may appear.
        assert not re.search(r'"hand"\s*:\s*\[', text), (
            "the receipt must not contain a hand identity array"
        )
        # Non-vacuity: the receipt really does describe the probed rows.
        receipt = json.loads(text)
        assert len(receipt["rows"]) == receipt["counts"]["probed"] > 0, (
            "the control must run against a receipt that actually carries rows"
        )


class TestRedactionAndVerdictIntegrity:
    """The external response is redacted; the engine's verdict consequence is not.

    Redaction itself is proven at the protocol boundary in
    ``XmageMidgameReviewRemediationTest`` (the process that owns the response).
    These controls prove the consumer side: a mismatch the engine reported is
    still a mismatch after redaction, and a clean arrival is still exactly a
    match, so redaction cannot launder credit in either direction.
    """

    REDACTED_HAND_MISMATCH = "hand subset P2|HAND|<hand-identity-redacted>: requested 1 observed 0"

    def test_a_redacted_hand_mismatch_still_denies_credit(self) -> None:
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            {
                "construction_match": False,
                "mismatches": [self.REDACTED_HAND_MISMATCH],
                "requested_state_digest": "a" * 64,
                "constructed_state_digest": "b" * 64,
            },
            engine_commit="abc",
        )
        assert verdict.outcome == "CONSTRUCTION_MISMATCH"
        assert verdict.engine_accepted_starting_state is False
        assert verdict.outcome not in ("ENGINE_NATIVE_REACHABLE", "CAUSAL_ROUTE_REACHABLE")

    def test_redaction_never_appears_as_a_recognized_allowance(self) -> None:
        # A redacted hand identity must not be mistaken for the documented
        # declaration-step allowance, which is the only negative-verdict case the
        # contract lets keep its bounded classification.
        verdict = ml.classification_from_arrival(
            "WS05-MP-COMBAT-4",
            ml.MIDGAME_LANE,
            {
                "construction_match": False,
                "mismatches": [self.REDACTED_HAND_MISMATCH],
                "requested_state_digest": "a" * 64,
                "constructed_state_digest": "b" * 64,
            },
            engine_commit="abc",
        )
        assert verdict.allowance_applied == ()

    def test_a_clean_arrival_still_reports_an_exact_internal_verdict(self) -> None:
        verdict = ml.classification_from_arrival(
            "WS05-CMD-TAX-2",
            ml.MIDGAME_LANE,
            {
                "construction_match": True,
                "mismatches": [],
                "requested_state_digest": "a" * 64,
                "constructed_state_digest": "b" * 64,
            },
            engine_commit="abc",
        )
        assert verdict.outcome == "ENGINE_NATIVE_REACHABLE"
        assert verdict.engine_accepted_starting_state is True
        assert verdict.mismatches == ()


class TestCausalCreditGating:
    """A causal route may only be credited when the engine's own construction
    verdict for the pre-causal arrival established bounded native reachability.

    Layers kept distinct: transport success, construction success, causal-route
    success and obligation satisfaction are separate facts, and only the
    strongest fact actually observed is credited.
    """

    @staticmethod
    def _arrival(outcome: str) -> ml.RowVerdict:
        return ml.RowVerdict(
            fixture_id="WS05-MP-BLOCK-4",
            outcome=outcome,  # type: ignore[arg-type]
            code=None,
            detail=None,
            construction_match=outcome == "ENGINE_NATIVE_REACHABLE",
            mismatches=(),
            requested_state_digest=None,
            constructed_state_digest=None,
            lane=ml.MIDGAME_LANE,
            engine_commit="abc",
        )

    def test_a_reachable_arrival_lets_the_causal_route_proceed(self) -> None:
        assert (
            ml.causal_credit_gate(
                "WS05-MP-BLOCK-4",
                "causal_stack",
                self._arrival("ENGINE_NATIVE_REACHABLE"),
                engine_commit="abc",
            )
            is None
        )

    def test_a_construction_mismatch_withholds_causal_credit(self) -> None:
        withheld = ml.causal_credit_gate(
            "WS05-MP-BLOCK-4",
            "causal_stack",
            self._arrival("CONSTRUCTION_MISMATCH"),
            engine_commit="abc",
        )
        assert withheld is not None
        assert withheld["outcome"] == "CONSTRUCTION_MISMATCH"
        assert withheld["engine_accepted_starting_state"] is False
        assert withheld["outcome"] != "CAUSAL_ROUTE_REACHABLE"

    def test_an_unrecognized_verdict_withholds_causal_credit(self) -> None:
        withheld = ml.causal_credit_gate(
            "WS05-MP-BLOCK-4",
            "causal_elimination",
            self._arrival("UNRECOGNIZED_CONSTRUCTION_VERDICT"),
            engine_commit="abc",
        )
        assert withheld is not None
        assert withheld["outcome"] == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
        assert withheld["engine_accepted_starting_state"] is False

    def test_a_transport_failure_withholds_causal_credit(self) -> None:
        withheld = ml.causal_credit_gate(
            "WS05-MP-BLOCK-4",
            "causal_stack",
            self._arrival("TRANSPORT_FAILURE"),
            engine_commit="abc",
        )
        assert withheld is not None
        assert withheld["outcome"] == "TRANSPORT_FAILURE"
        assert withheld["engine_accepted_starting_state"] is False

    def test_a_rejected_arrival_withholds_causal_credit(self) -> None:
        withheld = ml.causal_credit_gate(
            "WS05-MP-BLOCK-4",
            "causal_stack",
            self._arrival("ENGINE_REJECTED"),
            engine_commit="abc",
        )
        assert withheld is not None
        assert withheld["outcome"] == "ENGINE_REJECTED"
        assert withheld["engine_accepted_starting_state"] is False

    def test_a_missing_arrival_verdict_withholds_causal_credit(self) -> None:
        withheld = ml.causal_credit_gate(
            "WS05-MP-BLOCK-4", "causal_stack", None, engine_commit="abc"
        )
        assert withheld is not None
        assert withheld["code"] == "ARRIVAL_VERDICT_MISSING"
        assert withheld["engine_accepted_starting_state"] is False
        assert withheld["outcome"] == "ENGINE_REJECTED"

    def test_the_gate_names_the_entry_mode_so_the_row_stays_diagnosable(self) -> None:
        withheld = ml.causal_credit_gate(
            "WS05-MP-BLOCK-4",
            "causal_elimination",
            self._arrival("CONSTRUCTION_MISMATCH"),
            engine_commit="abc",
        )
        assert withheld is not None
        assert withheld["entry_mode"] == "causal_elimination"


class TestPlacementObligationClassification:
    """A placement entry has no stack route to reconstruct, so it may not claim a
    causal match the engine never reported, and an unobserved obligation earns no
    acceptance statement.
    """

    def test_an_observed_obligation_is_the_only_credbearing_case(self) -> None:
        verdict = ml.classification_from_placement_obligation(
            "WS05-MP-BLOCK-4",
            ml.MIDGAME_LANE,
            {"kind": "blocker_partition", "observed": True},
            engine_commit="abc",
        )
        assert verdict.outcome == "CAUSAL_ROUTE_REACHABLE"
        assert verdict.engine_accepted_starting_state is True
        assert verdict.causal_verdict is not None
        assert verdict.causal_verdict["engine_reports_causal_match"] is False, (
            "the lane must not present a fabricated engine causal_match"
        )
        assert "causal_match" not in verdict.causal_verdict

    def test_an_unobserved_obligation_earns_no_acceptance(self) -> None:
        verdict = ml.classification_from_placement_obligation(
            "WS05-MP-BLOCK-4",
            ml.MIDGAME_LANE,
            {"kind": "blocker_partition", "observed": False, "detail": "no partition"},
            engine_commit="abc",
        )
        assert verdict.outcome == "CAUSAL_ROUTE_MEASURED_BLOCKED"
        assert verdict.engine_accepted_starting_state is False
        assert verdict.detail is not None and "partition" in verdict.detail

    def test_a_missing_obligation_record_earns_no_acceptance(self) -> None:
        verdict = ml.classification_from_placement_obligation(
            "WS05-MP-BLOCK-4", ml.MIDGAME_LANE, None, engine_commit="abc"
        )
        assert verdict.outcome == "CAUSAL_ROUTE_MEASURED_BLOCKED"
        assert verdict.engine_accepted_starting_state is False
