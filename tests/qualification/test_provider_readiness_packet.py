"""Tests for the section-F provider-readiness packet (issue #255).

The packet is a fail-closed summary of one sealed current-boundary epoch.  These
tests prove the four contracted properties:

1. all 21 section-F dimensions are present;
2. no cell claims PASS without a sealed PASS behind it;
3. UNKNOWN is never shown as PASS, with a red control that fails if the
   summarizer were lenient;
4. the generator is deterministic and ``--check`` rejects non-identical output.

Additionally the tests exercise a tampered-digest control: a modified sealed
artifact must fail closed before anything is read.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "build_provider_readiness_packet.py"
PACKET_DIR = REPO / "docs" / "provider_readiness_packet_20261007"
PACKET_JSON = PACKET_DIR / "PROVIDER_READINESS.json"
PACKET_MD = PACKET_DIR / "PROVIDER_READINESS.md"
EPOCH_NAME = "ff688b58359f-42c21a3659cd"
EPOCH_ROOT = REPO / "qualification" / "current-boundary-epochs" / EPOCH_NAME

EXPECTED_DIMENSION_KEYS = (
    "rules_authority_separation",
    "legal_actions_submission",
    "costs_mana",
    "stack_priority",
    "targets_modes_choices",
    "triggers",
    "replacement_prevention",
    "continuous_effects_layers",
    "state_based_actions",
    "zones",
    "copy_control",
    "combat",
    "commander_rules",
    "multiplayer_2_5p",
    "bounded_6p",
    "hidden_information",
    "rules_rng",
    "semantic_replay",
    "process_isolation",
    "fail_closed_unsupported_paths",
    "actual_card_runtime_coverage",
)

CANDIDATES = ("xmage", "forge")
CANDIDATE_FILES = {"xmage": "XMAGE", "forge": "FORGE"}


def _load_generator() -> Any:
    spec = importlib.util.spec_from_file_location("build_provider_readiness_packet", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator() -> Any:
    return _load_generator()


@pytest.fixture(scope="module")
def packet() -> dict[str, Any]:
    return json.loads(PACKET_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sealed() -> Any:
    def load(relative: str) -> Any:
        return json.loads((REPO / relative).read_text(encoding="utf-8"))

    return load


def _resolve_citation(citation: dict[str, str], sealed: Any) -> Any:
    """Resolve a packet citation's file+field back to the sealed value."""

    document = sealed(relative=citation["file"])
    field = citation["field"]
    node: Any = document
    remainder = field
    while remainder:
        if "[" in remainder and (
            remainder.index("[") < remainder.index(".") if "." in remainder else True
        ):
            head, _, tail = remainder.partition("[")
            if head:
                node = node[head]
            selector, _, remainder = tail.partition("]")
            remainder = remainder.lstrip(".")
            key, _, value = selector.partition("=")
            if key == "gate":
                node = next(item for item in node if item["gate"] == value)
            elif key == "fixture_id":
                node = next(item for item in node if item["fixture_id"] == value)
            else:  # pragma: no cover - defensive
                raise AssertionError(f"unknown selector: {selector}")
        else:
            head, _, remainder = remainder.partition(".")
            if head:
                node = node[head]
    return node


def test_all_21_dimensions_present_in_order(packet: dict[str, Any]) -> None:
    assert packet["schema_version"] == "commander-lab.provider-readiness-section-f/1.0.0"
    dimensions = packet["dimensions"]
    assert len(dimensions) == 21
    assert tuple(dimension["key"] for dimension in dimensions) == EXPECTED_DIMENSION_KEYS
    assert [dimension["id"] for dimension in dimensions] == list(range(1, 22))


def test_every_dimension_carries_both_candidates_and_required_fields(
    packet: dict[str, Any],
) -> None:
    for dimension in packet["dimensions"]:
        assert set(dimension["candidates"]) == set(CANDIDATES)
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            for field in (
                "status",
                "backing_af_verdicts",
                "fixture_ids",
                "fixture_classes",
                "gate_blocking_rows",
                "gate_nonblocking_limitations",
                "blocking_rows",
                "residuals",
                "citations",
            ):
                assert field in cell, f"{dimension['key']}/{candidate} lacks {field}"
            assert cell["status"] in packet["dimension_status_vocabulary"]


def test_status_vocabulary_and_class_vocabulary(packet: dict[str, Any]) -> None:
    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            for fixture_class in cell["fixture_classes"].values():
                assert fixture_class in packet["fixture_class_vocabulary"]


def test_fail_or_unknown_backing_af_never_summarized_as_pass(packet: dict[str, Any]) -> None:
    """Task hard gate: a non-PASS backing AF can never be summarized as PASS."""

    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            if cell["status"] != "PASS":
                continue
            for gate, verdict in cell["backing_af_verdicts"].items():
                assert verdict == "PASS", f"{dimension['key']}/{candidate}: {gate}={verdict}"
            non_pass_counts = {
                state: count
                for state, count in cell["fixture_status_counts"].items()
                if state != "PASS"
            }
            assert not non_pass_counts, f"{dimension['key']}/{candidate}: {non_pass_counts}"
            assert not cell["blocking_rows"]


def test_every_pass_cell_cites_a_sealed_pass(packet: dict[str, Any], sealed: Any) -> None:
    """Every PASS cell must resolve to sealed PASS values for each cited field."""

    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            if cell["status"] != "PASS":
                continue
            pass_citations = [
                citation
                for citation in cell["citations"]
                if citation["kind"] in {"AF_GATE_VERDICT", "FIXTURE_ROW_STATE"}
            ]
            assert pass_citations, f"PASS cell without a sealed PASS citation: {dimension['key']}"
            for citation in cell["citations"]:
                resolved = _resolve_citation(citation, sealed)
                assert citation["value"] == str(resolved)
                if citation["kind"] in {"AF_GATE_VERDICT", "FIXTURE_ROW_STATE"}:
                    assert citation["value"] == "PASS"


def test_all_citations_resolve_into_the_sealed_epoch(packet: dict[str, Any], sealed: Any) -> None:
    root = packet["sealed_evidence_root"]
    allowed_kind = {
        "AF_GATE_VERDICT",
        "AF_GATE_BLOCKING_ROWS",
        "AF_GATE_NONBLOCKING_LIMITATIONS",
        "FIXTURE_ROW_STATE",
        "FIXTURE_CLASS",
        "BOUNDED_6P_RESULT",
    }
    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            for citation in dimension["candidates"][candidate]["citations"]:
                assert citation["kind"] in allowed_kind
                assert citation["file"].startswith(root)
                resolved = _resolve_citation(citation, sealed)
                assert citation["value"] == str(resolved), citation


def test_lenient_summarizer_red_control(generator: Any, packet: dict[str, Any]) -> None:
    """A summarizer that maps UNKNOWN to PASS must fail the packet invariant.

    The red control is explicit: ``derive_status`` is strict (UNKNOWN stays
    UNKNOWN), a deliberately lenient summarizer maps the same input to PASS, and
    the packet validator rejects a packet built by the lenient mapping.
    """

    strict = generator.derive_status({"AF06": "UNKNOWN"}, ["PASS", "PASS"])
    assert strict == "UNKNOWN"

    def lenient_summarizer(verdicts: dict[str, str], states: list[str]) -> str:
        status = generator.derive_status(verdicts, states)
        return "PASS" if status == "UNKNOWN" else status

    assert lenient_summarizer({"AF06": "UNKNOWN"}, ["PASS", "PASS"]) == "PASS"
    assert strict != lenient_summarizer({"AF06": "UNKNOWN"}, ["PASS", "PASS"])

    lenient_packet = copy.deepcopy(packet)
    for dimension in lenient_packet["dimensions"]:
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            verdicts = dict(cell["backing_af_verdicts"])
            states = [
                "PASS" if state == "PASS" else "UNKNOWN"
                for state in (cell["fixture_status_counts"] or {"PASS": 0})
            ]
            cell["status"] = lenient_summarizer(verdicts, states)
    with pytest.raises(generator.FailClosed):
        generator.validate_packet(lenient_packet)


def test_unknown_backing_gate_is_never_pass(packet: dict[str, Any]) -> None:
    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            if "UNKNOWN" in cell["backing_af_verdicts"].values():
                assert cell["status"] != "PASS", f"{dimension['key']}/{candidate}"


def test_tampered_digest_control(generator: Any, tmp_path: Path) -> None:
    """A modified sealed artifact must fail closed before any read."""

    fake_repo = tmp_path / "repo"
    target = fake_repo / "qualification" / "current-boundary-epochs" / EPOCH_NAME
    target.parent.mkdir(parents=True)
    shutil.copytree(EPOCH_ROOT, target)
    victim = target / "FULL107_XMAGE_RESULTS.json"
    victim.write_text(victim.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(generator.FailClosed, match="digest mismatch"):
        generator.verify_epoch(target, fake_repo)


def test_missing_manifest_entry_fails_closed(generator: Any, tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo2"
    target = fake_repo / "qualification" / "current-boundary-epochs" / EPOCH_NAME
    target.parent.mkdir(parents=True)
    shutil.copytree(EPOCH_ROOT, target)
    (target / "UNLISTED.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(generator.FailClosed, match="coverage mismatch"):
        generator.verify_epoch(target, fake_repo)


def test_check_mode_is_deterministic_and_byte_identical(
    generator: Any, packet: dict[str, Any]
) -> None:
    first_json, first_md = generator.render_outputs()
    second_json, second_md = generator.render_outputs()
    assert first_json == second_json
    assert first_md == second_md
    assert PACKET_JSON.read_text(encoding="utf-8") == first_json
    assert PACKET_MD.read_text(encoding="utf-8") == first_md

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "byte-identical" in result.stdout


def test_strict_derivation_matches_committed_packet(generator: Any, packet: dict[str, Any]) -> None:
    rebuilt = generator.build_packet()
    assert rebuilt == packet


def test_fixture_classes_match_sealed_comparison(packet: dict[str, Any], sealed: Any) -> None:
    comparison = sealed(f"{packet['sealed_evidence_root']}/CURRENT_BOUNDARY_COMPARISON.json")
    expected = {row["fixture_id"]: row["disposition"] for row in comparison["rows"]}
    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            for fixture_id, fixture_class in dimension["candidates"][candidate][
                "fixture_classes"
            ].items():
                assert expected[fixture_id] == fixture_class


def test_all_denominator_rows_covered(packet: dict[str, Any], sealed: Any) -> None:
    manifest = sealed(f"{packet['sealed_evidence_root']}/EFFECTIVE_FULL107_MANIFEST.json")
    denominator = {row["fixture_id"] for row in manifest["rows"]}
    assert len(denominator) == 107
    covered = {
        fixture_id
        for dimension in packet["dimensions"]
        for fixture_id in dimension["candidates"]["xmage"]["fixture_ids"]
    }
    assert denominator <= covered


def test_known_residuals_reported_with_current_sealed_state(
    packet: dict[str, Any], sealed: Any
) -> None:
    residuals = {(item["residual"], item["candidate"]): item for item in packet["known_residuals"]}
    for residual in (
        "HIDDEN_05",
        "HIDDEN_06",
        "HIDDEN_08",
        "HIDDEN_11",
        "HIDDEN_12",
        "WS05-CMD-MULL-2",
    ):
        assert (residual, "forge") in residuals
    assert ("WS05-CMD-MULL-2", "xmage") in residuals
    for item in residuals.values():
        candidate = item["candidate"]
        document = sealed(
            f"{packet['sealed_evidence_root']}/FULL107_{CANDIDATE_FILES[candidate]}_RESULTS.json"
        )
        row = next(row for row in document["rows"] if row["fixture_id"] == item["residual"])
        assert item["sealed_state"] == row["exit_state"]
        if (item["residual"], candidate) == ("WS05-CMD-MULL-2", "xmage"):
            # Resolved in the new sealed epoch: the row is PASS and the packet
            # still lists it with its issue-recorded label rather than hiding it.
            assert item["sealed_state"] == "PASS"
        else:
            assert item["sealed_state"] != "PASS"
        assert item["disposition"] == "REPORTED_NOT_REMEDIATED_IN_THIS_PACKET"


def test_non_claims_and_no_ranking(packet: dict[str, Any]) -> None:
    non_claims = packet["non_claims"]
    assert non_claims["production_provider"] == "NOT_SELECTED"
    assert non_claims["architecture_freeze"] == "NOT_CLAIMED"
    assert non_claims["production_repository"] == "NOT_CREATED"
    assert non_claims["ranking"] == "NONE"
    assert non_claims["recommendation"] == "NONE"
    assert "selects no provider" in packet["authority"]


def test_bounded_6p_success_is_pass_with_sealed_citations(
    packet: dict[str, Any], sealed: Any
) -> None:
    """A sealed 6P success renders PASS and cites every fact it rests on."""

    dimension = next(item for item in packet["dimensions"] if item["key"] == "bounded_6p")
    for candidate in CANDIDATES:
        cell = dimension["candidates"][candidate]
        document = sealed(
            f"{packet['sealed_evidence_root']}/PLAYER_CARDINALITY_{CANDIDATE_FILES[candidate]}.json"
        )
        result = document["results"]["6P"]
        terminal_facts = result["terminal_facts"]
        assert result["failure_kind"] is None
        assert result["failure"] is None
        assert cell["status"] == "PASS"
        assert cell["status_basis"] == "BOUNDED_6P_LIFECYCLE_AND_AF04_BOUNDED_SECONDARY_PROVEN"
        assert cell["backing_af_verdicts"] == {"AF02": "PASS"}
        assert not cell["blocking_rows"]
        assert any("established by the sealed facts" in residual for residual in cell["residuals"])

        cited_fields = {
            citation["field"]
            for citation in cell["citations"]
            if citation["kind"] == "BOUNDED_6P_RESULT"
        }
        assert {
            "results.6P.failure_kind",
            "results.6P.steps_completed",
            "results.6P.terminal_facts.start_status",
            "results.6P.terminal_facts.created_player_count",
            "results.6P.terminal_facts.priority_reached",
        } <= cited_fields
        gate_fields = {
            citation["field"]: citation["value"]
            for citation in cell["citations"]
            if citation["kind"] in {"AF_GATE_VERDICT", "AF_GATE_BLOCKING_ROWS"}
        }
        assert gate_fields["gates[gate=AF02].verdict"] == "PASS"
        assert gate_fields["gates[gate=AF04].verdict"] == "PASS"
        assert gate_fields["gates[gate=AF04].blocking_rows"] == "[]"
        for citation in cell["citations"]:
            assert citation["value"] == str(_resolve_citation(citation, sealed))
        # The cited facts are the sealed ones, including the published start
        # status (Forge "started"; XMage publishes none, so the lifecycle proof
        # carries and the cell states the absent status explicitly).
        cited_by_field = {citation["field"]: citation["value"] for citation in cell["citations"]}
        assert cited_by_field["results.6P.terminal_facts.start_status"] == str(
            terminal_facts.get("start_status")
        )
        assert cited_by_field["results.6P.terminal_facts.created_player_count"] == str(
            terminal_facts.get("created_player_count")
        )
        assert terminal_facts.get("priority_reached") is True


def _claimed_6p_success() -> dict[str, Any]:
    return {
        "failure_kind": None,
        "failure": None,
        "player_count": 6,
        "steps_completed": [
            "handshake",
            "import_deck",
            "create_commander_game",
            "start_game",
            "decision_drive",
        ],
        "decision_tape": [{"chosen_option_id": "engine-offered-option"}],
        "terminal_facts": {
            "start_status": "started",
            "created_player_count": 6,
            "priority_reached": True,
        },
    }


def test_bounded_6p_claimed_success_with_af04_gap_is_not_pass(generator: Any) -> None:
    """Red control: a success claim with a sealed AF04 gap is never PASS."""

    gapped = {
        "verdict": "PASS",
        "blocking_rows": ["PLAYER_COUNT_6P"],
        "decision_boundary": {"contradictions": []},
    }
    status, basis, kind = generator.derive_bounded_6p_status(
        "forge", _claimed_6p_success(), af02_verdict="PASS", af04_gate=gapped
    )
    assert status != "PASS"
    assert status == "UNKNOWN"
    assert "AF04_BOUNDED_SECONDARY_GAPS" in basis
    assert "PLAYER_COUNT_6P" in basis
    assert kind == "success_unproven"

    contaminated = {
        "verdict": "PASS",
        "blocking_rows": [],
        "decision_boundary": {"contradictions": [{"severity": "CONTRADICTION"}]},
    }
    status, basis, _ = generator.derive_bounded_6p_status(
        "forge", _claimed_6p_success(), af02_verdict="PASS", af04_gate=contaminated
    )
    assert status == "UNKNOWN"
    assert "AF04_DECISION_BOUNDARY_CONTRADICTIONS" in basis

    # Positive control: the same claim with clean sealed facts is PASS.
    clean = {"verdict": "PASS", "blocking_rows": [], "decision_boundary": {"contradictions": []}}
    status, basis, kind = generator.derive_bounded_6p_status(
        "forge", _claimed_6p_success(), af02_verdict="PASS", af04_gate=clean
    )
    assert status == "PASS"
    assert basis == "BOUNDED_6P_LIFECYCLE_AND_AF04_BOUNDED_SECONDARY_PROVEN"
    assert kind == "success"


def test_bounded_6p_success_claim_without_af02_or_lifecycle_is_not_pass(generator: Any) -> None:
    """Red control: missing AF02 PASS or an incomplete lifecycle is never PASS."""

    clean = {"verdict": "PASS", "blocking_rows": [], "decision_boundary": {"contradictions": []}}
    status, basis, _ = generator.derive_bounded_6p_status(
        "forge", _claimed_6p_success(), af02_verdict="UNKNOWN", af04_gate=clean
    )
    assert status == "UNKNOWN"
    assert "AF02_PLAYER_CARDINALITY" in basis

    incomplete = _claimed_6p_success()
    incomplete["terminal_facts"]["priority_reached"] = False
    incomplete["steps_completed"] = ["handshake", "import_deck"]
    status, basis, _ = generator.derive_bounded_6p_status(
        "forge", incomplete, af02_verdict="PASS", af04_gate=clean
    )
    assert status == "UNKNOWN"
    assert "PRIORITY_NOT_REACHED" in basis
    assert "LIFECYCLE_STEPS_MISSING" in basis

    status, basis, _ = generator.derive_bounded_6p_status("forge", _claimed_6p_success())
    assert status == "UNKNOWN"
    assert "AF02_PLAYER_CARDINALITY" in basis
    assert "AF04_BOUNDED_SECONDARY_GAPS" in basis


def test_fail_class_bounded_6p_never_renders_benign(generator: Any) -> None:
    """Red control: a FAIL-class 6P result must never become NOT_RUN/UNSUPPORTED."""

    for failure_kind in (
        "FAIL",
        "CRASH",
        "TIMEOUT",
        "PROTOCOL_FAILURE",
        "ENGINE_RUNTIME_ERROR",
    ):
        status, basis, kind = generator.derive_bounded_6p_status(
            "forge", {"failure_kind": failure_kind, "failure": "sealed failure"}
        )
        assert status == "FAIL", failure_kind
        assert status not in {"NOT_RUN", "UNSUPPORTED"}
        assert failure_kind in basis
        assert kind == failure_kind
    with pytest.raises(generator.FailClosed, match="unknown bounded-6P failure_kind"):
        generator.derive_bounded_6p_status(
            "forge", {"failure_kind": "SOMETHING_NEW", "failure": "sealed failure"}
        )
    with pytest.raises(generator.FailClosed, match="unknown bounded-6P start_status"):
        claimed = _claimed_6p_success()
        claimed["terminal_facts"]["start_status"] = "SOMETHING_NEW"
        generator.derive_bounded_6p_status(
            "forge",
            claimed,
            af02_verdict="PASS",
            af04_gate={"verdict": "PASS", "blocking_rows": []},
        )


def test_gate_blocking_rows_reach_dimension_cells(packet: dict[str, Any], sealed: Any) -> None:
    """AF-gate blocking rows are carried into the cells and the residuals."""

    checked_rows = 0
    checked_limitations = 0
    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            sealed_gates = {
                gate["gate"]: gate
                for gate in sealed(
                    f"{packet['sealed_evidence_root']}/AF00_AF11_{CANDIDATE_FILES[candidate]}.json"
                )["gates"]
            }
            for gate_id in dimension["backing_af_gates"]:
                sealed_gate = sealed_gates[gate_id]
                assert cell["gate_blocking_rows"][gate_id] == sealed_gate["blocking_rows"]
                for row in sealed_gate["blocking_rows"]:
                    assert f"{gate_id} blocking row: {row}" in cell["residuals"]
                    checked_rows += 1
                for limitation in sealed_gate["nonblocking_limitations"]:
                    assert f"{gate_id} limitation: {limitation}" in cell["residuals"]
                    checked_limitations += 1
    # The carrying path must be exercised: Forge's AF05/AF06/AF08 gates carry
    # blocking rows in every current epoch.
    assert checked_rows > 0
    assert checked_limitations > 0
    af04_cell = next(item for item in packet["dimensions"] if item["id"] == 2)["candidates"][
        "forge"
    ]
    assert af04_cell["gate_blocking_rows"]["AF04"] == []


def test_pass_cells_render_backing_gate_nonblocking_limitations(
    packet: dict[str, Any],
) -> None:
    """PASS cells keep every backing gate's nonblocking limitations."""

    dimension = next(item for item in packet["dimensions"] if item["id"] == 1)
    for candidate in CANDIDATES:
        cell = dimension["candidates"][candidate]
        assert cell["status"] == "PASS"
        limitations = cell["gate_nonblocking_limitations"]["AF03"]
        assert any(
            "not an exhaustive proof of deck legality" in limitation for limitation in limitations
        )
        assert any(
            "not an exhaustive proof of deck legality" in residual for residual in cell["residuals"]
        )
        assert not cell["gate_blocking_rows"]["AF03"]


def test_process_isolation_mapping_is_explicit(packet: dict[str, Any]) -> None:
    """Dimension 19 maps explicitly and cannot inherit PASS from AF11 alone."""

    dimension = next(item for item in packet["dimensions"] if item["id"] == 19)
    assert dimension["backing_af_gates"] == ["AF11"]
    required = dimension["required_gate_evidence"]
    assert required
    assert all(item["gate"] == "AF11" for item in required)
    for candidate in CANDIDATES:
        cell = dimension["candidates"][candidate]
        assert cell["backing_af_verdicts"]["AF11"] != "PASS"
        assert cell["status"] != "PASS"


def test_process_isolation_pass_requires_process_isolation_evidence(generator: Any) -> None:
    """Red control: AF11 PASS without the process-isolation facts fails closed."""

    requirements = generator.REQUIRED_GATE_EVIDENCE["process_isolation"]
    dimension = next(item for item in generator.DIMENSIONS if item["key"] == "process_isolation")
    bare_gate = {
        "gate": "AF11",
        "verdict": "PASS",
        "evidence": [],
        "blocking_rows": [],
        "nonblocking_limitations": [],
    }
    bare = {"AF11": bare_gate}
    assert generator.missing_required_gate_evidence(bare, requirements)
    with pytest.raises(generator.FailClosed, match="required gate evidence"):
        generator._candidate_dimension(
            "xmage", dimension, {"AF11": "PASS"}, {}, {}, "epoch-root", {}, bare
        )

    full_gate = copy.deepcopy(bare_gate)
    full_gate["evidence"] = [item["evidence_prefix"] + ": sealed fact" for item in requirements]
    full = {"AF11": full_gate}
    assert generator.missing_required_gate_evidence(full, requirements) == []
    cell = generator._candidate_dimension(
        "xmage", dimension, {"AF11": "PASS"}, {}, {}, "epoch-root", {}, full
    )
    assert cell["status"] == "PASS"


def test_manifest_parser_rejects_non_hex_and_duplicate_digests(
    generator: Any, tmp_path: Path
) -> None:
    """Red controls for the manifest parser: non-64-hex and duplicate entries."""

    fake_repo = tmp_path / "repo-manifest"
    target = fake_repo / "epoch"
    target.mkdir(parents=True)
    artifact = target / "a.json"
    artifact.write_text("{}\n", encoding="utf-8")
    manifest = target / "CURRENT_BOUNDARY_SHA256SUMS"

    manifest.write_text("z" * 64 + "  epoch/a.json\n", encoding="utf-8")
    with pytest.raises(generator.FailClosed, match="malformed manifest"):
        generator.verify_epoch(target, fake_repo)

    manifest.write_text("abc  epoch/a.json\n", encoding="utf-8")
    with pytest.raises(generator.FailClosed, match="malformed manifest"):
        generator.verify_epoch(target, fake_repo)

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest.write_text(f"{digest}  epoch/a.json\n{digest}  epoch/a.json\n", encoding="utf-8")
    with pytest.raises(generator.FailClosed, match="duplicate manifest entry"):
        generator.verify_epoch(target, fake_repo)


def test_markdown_mirrors_json(packet: dict[str, Any]) -> None:
    markdown = PACKET_MD.read_text(encoding="utf-8")
    assert "PRODUCTION_PROVIDER = NOT_SELECTED" in markdown
    assert "ARCHITECTURE_FREEZE = NOT_CLAIMED" in markdown
    assert "Dimension-to-backing-gate mapping" in markdown
    assert "Backing-gate residuals" in markdown
    assert "not an exhaustive proof of deck legality" in markdown
    for dimension in packet["dimensions"]:
        assert dimension["name"] in markdown
    for residual in packet["known_residuals"]:
        assert residual["residual"] in markdown


def test_source_lock_binds_epoch_and_pins(packet: dict[str, Any]) -> None:
    lock = packet["source_lock"]
    assert lock["sealed_epoch"]["epoch_id"] == EPOCH_NAME
    assert (
        lock["sealed_epoch"]["manifest"]["verified"] == lock["sealed_epoch"]["manifest"]["entries"]
    )
    assert lock["sealed_epoch"]["manifest"]["mismatches"] == 0
    assert (
        lock["effective_contract"]["effective_manifest_contract_id"]
        == "commander-lab.full107/1.0.24-successor"
    )
    xmage_pin = lock["engine_pins"]["xmage"]["commit"]
    forge_pin = lock["engine_pins"]["forge_rules_core"]["commit"]
    bridge_pin = lock["engine_pins"]["forge_bridge_source"]["commit"]
    bindings = lock["evidence_identity_bindings"]
    assert bindings["xmage_candidate_commit"] == xmage_pin
    assert bindings["forge_rules_core_commit"] == forge_pin
    assert bindings["forge_build_commit"] == bridge_pin
    assert lock["drift_records"]
    for record in lock["drift_records"]:
        assert record["verdict"] in {"IDENTICAL", "DIFFERS"}
