"""The assembler must not be able to credit anything it did not observe.

These are structural tests over the assembler source itself. The defects they
guard against were silent: the assembler produced plausible PASS counts from a
hand-written literal and from fixture-id strings found in test source. A test
that only checks counts would not have caught either, so these assert that the
promoting code paths are gone and that the credit functions are receipt-only.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import receipts as R

REPO = Path(__file__).resolve().parents[2]
ASSEMBLER = REPO / "scripts" / "assemble_current_boundary_evidence.py"
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_constants(path: Path) -> dict[str, object]:
    tree = ast.parse(_source(path))
    out: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                try:
                    out[target.id] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    out[target.id] = "<computed>"
    return out


def test_hard_coded_native_runs_literal_is_gone() -> None:
    """NATIVE_RUNS was a hand-written literal the assembler consumed as evidence.

    The name may still appear in a comment recording that it was retired, so the
    guard is on the constant existing at all: it must not be assigned anywhere,
    and no name containing it may be defined.
    """
    assert "NATIVE_RUNS" not in _module_constants(ASSEMBLER), (
        "the NATIVE_RUNS literal must not exist as a module constant"
    )
    tree = ast.parse(_source(ASSEMBLER))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            assert "NATIVE_RUNS" not in node.name, f"{node.name} reintroduces the retired literal"
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assert "NATIVE_RUNS" not in target.id, target.id


def test_assembler_never_reads_test_source_for_fixture_ids() -> None:
    """The regex promotion path scanned test source; it must not come back."""
    source = _source(ASSEMBLER)
    assert "engine-bridge/src/test/java" not in source
    assert "pattern.findall" not in source
    assert "read_text(errors=" not in source


def test_assembler_derives_native_credit_from_receipts_only() -> None:
    source = _source(ASSEMBLER)
    assert "collect_receipts" in source
    assert "positive_fixture_credit" in source
    assert "PERSISTED_EXECUTION_RECEIPTS_ONLY" in source
    assert "absent_receipts_yield_no_credit" in source


def test_native_suite_executor_is_on_the_execution_path() -> None:
    """run_native_suite() used to be dead code. It must now be reachable."""
    source = _source(RUNNER)
    tree = ast.parse(source)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "run_native_suite" in called, "run_native_suite is still dead code"
    assert "run_all_native_suites" in called
    # And it must refuse to run against a dirty runner.
    assert "require_clean_runner" in source
    assert "verify_runner_unchanged" in source
    # And it must check the recorded candidate against the executing one.
    # The gate must PROVE the engine is the same engine, not merely assert the
    # commit matches, because the suite has to execute at a descendant that
    # contains its test classes.
    assert "verify_engine_identity" in source
    assert "engine_identity_proof" in source
    assert "executed_commit" in source


def test_fullgame_lane_auxiliary_is_optional_in_a_runtime_epoch(tmp_path: Path) -> None:
    """A runtime epoch does not contain the historical auxiliary artifact.

    The xmage full-game-lane AF01 artifact is produced by an earlier boundary
    epoch, not by the runner. The assembler loaded it unconditionally, so an
    assembly from a fresh runtime epoch crashed on the missing file instead of
    recording that no auxiliary is present.
    """
    asm = _assembler_module()
    assert asm._load_fullgame_lane_auxiliary("forge") is None
    import json

    original = asm.OUT
    try:
        asm.OUT = tmp_path
        assert asm._load_fullgame_lane_auxiliary("xmage") is None
        path = tmp_path / "AF01_XMAGE_FULLGAME_LANE.json"
        path.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
        assert asm._load_fullgame_lane_auxiliary("xmage") == {"verdict": "PASS"}
    finally:
        asm.OUT = original


def test_carried_column_gates_are_annotated_as_historical() -> None:
    """Per-gate verdicts from a carried-forward column are not fresh observations."""
    asm = _assembler_module()
    carried = {
        "class": "CARRIED_FORWARD_FROM_HISTORICAL_EPOCH",
        "source_epoch": "qualification/final-current-boundary-20260927",
    }
    fresh = {"class": "FRESH_CURRENT_BOUNDARY_EXECUTION"}
    gates = [
        {"gate": "AF01", "verdict": "PASS", "nonblocking_limitations": []},
        {"gate": "AF03", "verdict": "PASS"},
    ]
    asm._annotate_carried_gates(gates, fresh)
    assert gates[0]["nonblocking_limitations"] == []
    asm._annotate_carried_gates(gates, carried)
    for gate in gates:
        joined = " ".join(gate["nonblocking_limitations"])
        assert "historical record carried forward" in joined
        assert "not a fresh execution" in joined
        assert carried["source_epoch"] in joined


def test_carried_column_rows_are_never_promoted() -> None:
    """A historical row must not be relabelled FRESH by a promotion.

    The guard is structural because the credited path requires receipts that a
    carried-forward column cannot have; the assertion pins the refusal so a
    future change cannot rediscover the contradiction.
    """
    source = ASSEMBLER.read_text(encoding="utf-8")
    assert "carried_forward = bool(results.get" in source
    assert "if carried_forward:" in source


def test_native_suites_are_scoped_to_the_selected_candidates(monkeypatch) -> None:
    """A Forge-only run must not regenerate XMage native receipts."""
    import importlib.util

    # Importing the runner resolves each native suite's root from the
    # environment and reads that root's tree at module level. Point the Forge
    # root at this repository so the import works on a machine that does not
    # have the historical reference checkout; the test only exercises candidate
    # scoping, and the patched executor never runs a suite.
    monkeypatch.setenv("FORGE_WORKSPACE", str(REPO))
    spec = importlib.util.spec_from_file_location("wsr_runner_mod", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    executed: list[tuple[str, str]] = []

    def _fake(candidate: str, group: str, *, runner: object) -> dict:
        executed.append((candidate, group))
        return {}

    monkeypatch.setattr(module, "run_native_suite", _fake)
    module.run_all_native_suites(object(), ("forge",))
    assert executed, "the forge native suites must still be executed"
    assert {candidate for candidate, _ in executed} == {"forge"}


def test_seed_is_not_recorded_as_engine_owned_without_acknowledgement() -> None:
    """`engine_owned: true` from caller intent alone is the Gate 3 defect.

    The classification lives in the receipts module and is applied by the game
    driver, which must pass the seed to the provider and derive control from the
    acknowledgement rather than from the request.
    """
    driver = (REPO / "src/commander_lab/qualification/current_boundary/game_driver.py").read_text(
        encoding="utf-8"
    )
    receipts = (REPO / "src/commander_lab/qualification/current_boundary/receipts.py").read_text(
        encoding="utf-8"
    )

    # Control is derived from an observed acknowledgement.
    assert "classify_seed_binding" in driver
    assert "_acknowledged_seed" in driver
    assert "ACKNOWLEDGED_ENGINE_SEED" in receipts
    assert "UNCONTROLLED_ENGINE_RNG" in receipts
    assert "REQUESTED_SEED" in receipts

    # The seed must actually reach the provider request. It is built in
    # _create_request, which sends it only when the provider declares support;
    # the behaviour itself is pinned in test_current_boundary_seed_capability.
    create_helper = driver[driver.index("def _create_request(") :]
    create_helper = create_helper[: create_helper.index("\n\ndef ")]
    assert 'request["seed"] = seed' in create_helper
    assert 'request["rules_seed"] = seed' in create_helper
    assert "if seed_supported:" in create_helper

    # And the derived binding is what the evidence records.
    assert '"rules_rng_binding"' in driver


def test_bridge_read_is_deadline_bounded() -> None:
    source = (
        REPO / "src/commander_lab/qualification/current_boundary/bridge_launcher.py"
    ).read_text(encoding="utf-8")
    assert "_read_line_with_deadline" in source
    assert "BridgeTimeout" in source
    # The unbounded read must not be the request path any more.
    request_body = source.split("def request(", 1)[1].split("def _read_line_with_deadline(", 1)[0]
    assert "self.popen.stdout.readline()" not in request_body
    assert "_read_line_with_deadline(" in request_body
    # The only readline lives inside the deadline-bounded reader thread.
    assert source.count("self.popen.stdout.readline()") == 1
    assert "finished.wait(timeout_s)" in source
    assert "_terminate_stalled_child" in source


def test_no_credit_without_receipts_end_to_end(tmp_path: Path) -> None:
    """The end-to-end property: no receipts, no credit, of any kind."""
    valid, rejected = R.collect_receipts(tmp_path / "receipts")
    assert valid == []
    assert rejected  # absent directory is itself a no-credit condition
    assert (
        R.positive_fixture_credit(
            valid,
            candidate="xmage",
            expected_commit="a" * 40,
            denominator={"MICRO_STACK"},
            expected_runner_digest="a" * 64,
        )
        == {}
    )
    credit = R.native_suite_credit(
        valid, candidate="xmage", expected_commit="a" * 40, expected_runner_digest="a" * 64
    )
    assert credit["groups_credited"] == []
    assert credit["tests"] == 0
    assert credit["passed"] == 0


def test_real_evidence_directory_has_no_receipts_yet() -> None:
    """Honest current state: the receipts do not exist, so nothing is credited.

    This is the state that makes the historical FULL107 counts upper bounds. It
    is asserted explicitly so the transition to 'receipts exist' is visible
    rather than silent.
    """
    directory = REPO / "qualification" / "final-current-boundary-20260927" / "receipts"
    if not directory.is_dir():
        pytest.skip("no receipt directory yet; nothing can be credited, which is the point")
    valid, rejected = R.collect_receipts(directory)
    assert valid or rejected


# --- AF11: measured technical facts, never an asserted verdict -------------- #


def _assembler_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("salvage_assembler_under_test", ASSEMBLER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _af11_identities(**overrides: object) -> dict:
    base = {
        "xmage": {
            "results_runtime_identity": {
                "adapter": "engine-bridge/src/main/java/org/commanderlab/xmage",
                "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
            }
        },
        "forge": {
            "results_runtime_identity": {
                "adapter": "forge-protocol2-bridge (read-only reference checkout)",
                "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
            }
        },
    }
    for candidate, identity in overrides.items():
        base[candidate]["results_runtime_identity"] = identity
    return base


def test_af11_is_unknown_when_technical_facts_hold() -> None:
    """Facts hold + policy unresolved must be UNKNOWN, never an asserted FAIL."""
    asm = _assembler_module()
    per_candidate = _af11_identities()
    measured = asm._af11_measure(per_candidate, "xmage", per_candidate["xmage"])
    assert measured["verdict"] == "UNKNOWN"
    assert measured["verdict"] != "PASS"
    joined_evidence = " ".join(measured["evidence"])
    assert "distinct external adapter" in joined_evidence
    assert "no engine code is embedded" in joined_evidence
    assert "no legal conclusion is drawn here" in joined_evidence
    joined_limitations = " ".join(measured["limitations"])
    assert "NOT MEASURED BY THE LAB" in joined_limitations


def test_af11_fails_when_adapter_identity_is_missing() -> None:
    asm = _assembler_module()
    per_candidate = _af11_identities(xmage={})
    measured = asm._af11_measure(per_candidate, "xmage", per_candidate["xmage"])
    assert measured["verdict"] == "FAIL"
    assert any("no adapter identity" in line for line in measured["limitations"])


def test_af11_fails_when_adapters_are_not_distinct() -> None:
    asm = _assembler_module()
    shared = {
        "adapter": "engine-bridge/src/main/java/org/commanderlab/xmage",
        "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    }
    per_candidate = _af11_identities(xmage=shared, forge=shared)
    measured = asm._af11_measure(per_candidate, "xmage", per_candidate["xmage"])
    assert measured["verdict"] == "FAIL"


def test_af11_fails_when_engine_code_is_embedded() -> None:
    asm = _assembler_module()
    per_candidate = _af11_identities(
        xmage={
            "adapter": "commander_lab.engine.rules.bridge",
            "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
        }
    )
    measured = asm._af11_measure(per_candidate, "xmage", per_candidate["xmage"])
    assert measured["verdict"] == "FAIL"
    assert any("embedded" in line for line in measured["limitations"])


def test_af11_unknown_still_blocks_freeze() -> None:
    """UNKNOWN must remain a freeze-blocking verdict: this is not a weakening."""
    from commander_lab.freeze_readiness import NON_PASS_VERDICTS

    assert "UNKNOWN" in NON_PASS_VERDICTS
    assert "PASS" not in NON_PASS_VERDICTS


# --- AF09: seed acknowledgement, refusal and setup are never replay proof --- #


def _refusal_document() -> dict:
    return {
        "semantic_replay": {"error": [{"code": "unsupported_message", "message": "nope"}]},
        "rules_rng_binding": {
            "classification": "UNCONTROLLED_ENGINE_RNG",
            "requested_seed": 424242,
            "acknowledged_seed": None,
        },
    }


def test_af09_refusal_is_recorded_as_refusal() -> None:
    """A refused export must never be worded as an executed one."""
    asm = _assembler_module()
    described = asm._describe_replay_evidence(_refusal_document(), "xmage")
    joined = " ".join(described["evidence"])
    assert "attempted in a live game and refused by the engine" in joined
    assert "unsupported_message" in joined
    assert "executed in a live game" not in joined


def test_af09_seed_acknowledgement_is_not_a_tape() -> None:
    doc = _refusal_document()
    doc["rules_rng_binding"] = {
        "classification": "ACKNOWLEDGED_ENGINE_SEED",
        "requested_seed": 424242,
        "acknowledged_seed": 424242,
    }
    asm = _assembler_module()
    described = asm._describe_replay_evidence(doc, "forge")
    joined = " ".join(described["evidence"])
    assert "ACKNOWLEDGED_ENGINE_SEED" in joined
    assert "not a demonstrated Rules RNG tape" in joined


def test_af09_payload_presence_is_not_replay_proof() -> None:
    doc = _refusal_document()
    doc["semantic_replay"] = {"tape": ["event-1", "event-2"]}
    asm = _assembler_module()
    described = asm._describe_replay_evidence(doc, "xmage")
    joined = " ".join(described["evidence"])
    assert "recorded, not replay proof" in joined


def test_af09_limitations_state_the_generic_distinctions() -> None:
    asm = _assembler_module()
    described = asm._describe_replay_evidence(_refusal_document(), "xmage")
    joined = " ".join(described["limitations"])
    assert "never a satisfied obligation and never a replay PASS" in joined
    assert "is not semantic replay proof" in joined


def test_af09_a_proven_twin_states_the_distinctions_without_blocking() -> None:
    asm = _assembler_module()
    described = asm._describe_replay_evidence(_refusal_document(), "xmage", twin_proven=True)
    assert described["limitations"] == []
    joined = " ".join(described["evidence"])
    assert "attempted in a live game and refused by the engine" in joined
    assert "never a satisfied obligation and never a replay PASS" in joined
    assert "is not semantic replay proof" in joined


REPLAY_ROWS = (
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_STATE_HASHES",
    "RNG_RULES_TAPE",
)


def _bound_twin_document(**overrides: object) -> dict:
    from commander_lab.qualification.current_boundary import replay_twins

    twin = overrides.pop("clean_process_twin", {"candidate_build": {"engine_commit": "c" * 40}})
    document = {
        "execution_mode": "AF09_MIDGAME_CLEAN_PROCESS_REPLAY_TWIN",
        "candidate": "xmage",
        "candidate_commit": "c" * 40,
        "runner_digest": "r" * 64,
        "rows_declared": 5,
        "rows_verified": 5,
        "rows": {
            fixture: {"verified": True, "twin_digest": replay_twins.sha256_json(twin)}
            for fixture in REPLAY_ROWS
        },
        "clean_process_twin": twin,
    }
    document.update(overrides)
    return document


def test_the_midgame_twin_stands_only_for_a_fully_verified_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asm = _assembler_module()
    monkeypatch.setattr(asm, "OUT", tmp_path)
    partial = _bound_twin_document()
    partial["rows"]["RNG_RULES_TAPE"]["verified"] = False
    missing = _bound_twin_document()
    missing["rows"].pop("REPLAY_EVENT_TAPE")
    foreign = _bound_twin_document()
    foreign["clean_process_twin"] = {
        "candidate_build": {"engine_commit": "c" * 40},
        "decisions": "not one of the rows' twins",
    }
    for document in (partial, missing, foreign):
        (tmp_path / "MIDGAME_REPLAY_TWIN_EXECUTIONS.json").write_text(json.dumps(document))
        assert asm.midgame_replay_twin_document("xmage", _fresh_column(), "r" * 64) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"clean_process_twin": "not-a-mapping"},
        {"clean_process_twin": None},
        {"clean_process_twin": {"candidate_build": "not-a-mapping"}},
        {"rows": ["RNG_RULES_TAPE"]},
        {"rows": {fixture: "verified" for fixture in REPLAY_ROWS}},
        {"execution_mode": "OTHER", "clean_process_twin": ["x"]},
    ],
)
def test_a_malformed_midgame_twin_document_is_rejected_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict
) -> None:
    asm = _assembler_module()
    monkeypatch.setattr(asm, "OUT", tmp_path)
    document = _bound_twin_document(**overrides)
    (tmp_path / "MIDGAME_REPLAY_TWIN_EXECUTIONS.json").write_text(json.dumps(document))
    assert asm.midgame_replay_twin_document("xmage", _fresh_column(), "r" * 64) is None


def test_replay_twin_receipts_credit_only_through_the_bound_document() -> None:
    source = _source(ASSEMBLER)
    helper = source[source.index("def native_bindings(") :]
    helper = helper[: helper.index("\ndef ")]
    assert "midgame_replay_twin_mod.bound_receipt_digests(" in helper
    assert "not bound to this epoch's replay-twin document" in helper
    assert helper.index("bound_receipt_digests(") < helper.index("positive_fixture_credit(")


def test_a_demonstrated_replay_divergence_is_recorded_as_fail() -> None:
    source = _source(ASSEMBLER)
    call = source.index("midgame_replay_twin_mod.demonstrated_failures(")
    window = source[call : call + 1400]
    assert "runner_digest=assembly_runner_digest" in window
    assert 'row["exit_state"] = "FAIL"' in window
    assert call < source.index("for fixture, per in bindings.items():")


def _fresh_column(commit: str = "c" * 40) -> dict:
    return {
        "column_provenance": {"class": "FRESH_CURRENT_BOUNDARY_EXECUTION"},
        "results_runtime_identity": {"engine_candidate_commit": commit},
    }


@pytest.mark.parametrize(
    ("candidate", "column", "overrides", "bound"),
    [
        ("xmage", _fresh_column(), {}, True),
        ("forge", _fresh_column(), {"candidate": "forge"}, False),
        (
            "xmage",
            {**_fresh_column(), "column_provenance": {"class": "CARRIED_FORWARD"}},
            {},
            False,
        ),
        ("xmage", _fresh_column(), {"runner_digest": "x" * 64}, False),
        ("xmage", _fresh_column(), {"candidate_commit": "d" * 40}, False),
        (
            "xmage",
            _fresh_column(),
            {"clean_process_twin": {"candidate_build": {"engine_commit": "d" * 40}}},
            False,
        ),
        ("xmage", _fresh_column(), {"execution_mode": "OTHER"}, False),
        ("xmage", _fresh_column(""), {"candidate_commit": ""}, False),
    ],
)
def test_the_midgame_twin_document_is_bound_to_column_and_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidate: str,
    column: dict,
    overrides: dict,
    bound: bool,
) -> None:
    asm = _assembler_module()
    monkeypatch.setattr(asm, "OUT", tmp_path)
    document = _bound_twin_document(**overrides)
    (tmp_path / "MIDGAME_REPLAY_TWIN_EXECUTIONS.json").write_text(json.dumps(document))
    result = asm.midgame_replay_twin_document(candidate, column, "r" * 64)
    assert (result == document) if bound else result is None


def test_a_missing_midgame_twin_document_supplies_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asm = _assembler_module()
    monkeypatch.setattr(asm, "OUT", tmp_path)
    assert asm.midgame_replay_twin_document("xmage", _fresh_column(), "r" * 64) is None


def test_the_assembler_passes_the_bound_midgame_twin_to_af09() -> None:
    source = _source(ASSEMBLER)
    call = source.index("gate_derivations_mod.af09_rng_replay(")
    assert "midgame_twin=midgame_twin_by_candidate[candidate]" in source[call : call + 400]
    binding = source.index("midgame_twin_by_candidate = {")
    assert "assembly_runner_digest" in source[binding : binding + 300]


def test_the_runner_persists_replay_twin_receipts_after_the_pb03_ledger() -> None:
    source = _source(RUNNER)
    ledger = source.index('write("PB03_RUNTIME_EXECUTION.json", pb03_runtime)')
    executions = source.index('"MIDGAME_REPLAY_TWIN_EXECUTIONS.json"')
    assert ledger < executions
    window = source[executions : executions + 700]
    assert "runner_digest=runner.digest()" in window
    assert "candidate_commit=canonical_xmage_engine_pin()" in window
    assert "RECEIPT_DIR / receipt_mod.POSITIVE_RECEIPT_SUBDIR" in window


def test_af09_never_claims_an_executed_export() -> None:
    """The over-claim the donor caught must not come back in any wording."""
    assert "replay export executed in a live game" not in _source(ASSEMBLER)


def test_af09_committed_artifacts_describe_refusals(monkeypatch: pytest.MonkeyPatch) -> None:
    """DIRECTLY_VERIFIED against the committed RNG_REPLAY artifacts: both refused.

    The committed artifacts of record live in the historical WSR22 epoch, which
    stays readable after the runner moved to a source-bound runtime epoch. The
    subject is therefore read explicitly instead of whatever epoch was written
    most recently.
    """
    asm = _assembler_module()
    historical = REPO / "qualification" / "final-current-boundary-20260927"
    monkeypatch.setattr(asm, "OUT", historical)
    for candidate in ("xmage", "forge"):
        document = asm._load_replay_document(candidate)
        assert document is not None, f"missing committed RNG_REPLAY_{candidate.upper()}.json"
        described = asm._describe_replay_evidence(document, candidate)
        assert any("refused by the engine" in line for line in described["evidence"])


def test_a_demonstrated_knowledge_boundary_failure_is_recorded_before_any_promotion() -> None:
    """AF05: a leak the production lane demonstrably showed is a FAIL row.

    The executions document is bound to this column's candidate and the
    assembling runner, a carried-forward column never reads it, and the FAIL is
    written before receipt promotion, which never overwrites a FAIL.
    """
    source = _source(ASSEMBLER)
    call = source.index("knowledge_projection_mod.demonstrated_failures(")
    assert 'if candidate == "xmage" and not carried_forward:' in source[call - 400 : call]
    assert "runner_digest=assembly_runner_digest" in source[call : call + 600]
    assert call < source.index("for fixture, per in bindings.items():")
    # Promotion still refuses to overwrite a contradictory direct failure.
    promotion = source[source.index("for fixture, per in bindings.items():") :]
    assert '"FAIL",' in promotion and "positive_receipt_conflict" in promotion


def test_the_runner_persists_knowledge_projection_receipts_after_the_pb03_ledger() -> None:
    source = _source(RUNNER)
    ledger = source.index('write("PB03_RUNTIME_EXECUTION.json", pb03_runtime)')
    executions = source.index('"KNOWLEDGE_PROJECTION_EXECUTIONS.json"')
    assert ledger < executions
    window = source[executions : executions + 700]
    assert "runner_digest=runner.digest()" in window
    assert "RECEIPT_DIR / receipt_mod.POSITIVE_RECEIPT_SUBDIR" in window


def test_the_runner_persists_actual_card_campaign_receipts_after_the_runner_is_bound() -> None:
    """AF07 credit comes from the same runner identity, in its own receipt subdir."""
    source = _source(RUNNER)
    bound = source.index("receipt_mod.require_clean_runner(runner)")
    executions = source.index('"ACTUAL_CARD_CAMPAIGN_XMAGE.json"')
    assert bound < executions
    window = source[executions : executions + 700]
    assert "runner_digest=runner.digest()" in window
    assert "candidate_commit=canonical_xmage_engine_pin()" in window
    assert "RECEIPT_DIR / actual_card_campaign_mod.RECEIPT_SUBDIR" in window
    assert "POSITIVE_RECEIPT_SUBDIR" not in window


def test_the_assembler_credits_af07_only_from_bound_campaign_receipts() -> None:
    source = _source(ASSEMBLER)
    helper = source[source.index("def actual_card_campaign_credit(") :]
    helper = helper[: helper.index("\ndef ")]
    # A carried-forward column never reads the campaign; the receipts are checked
    # against the current effective records, this runner and this engine commit.
    assert '!= "FRESH_CURRENT_BOUNDARY_EXECUTION"' in helper
    assert "actual_card_campaign_mod.RECEIPT_SUBDIR" in helper
    assert "derive_corpus(REPO)" in helper
    assert "runner_digest=runner_digest" in helper
    assert "test_identity_prefix=actual_card_campaign_mod.TEST_IDENTITY_PREFIX" in helper
    call = source.index("gate_derivations_mod.af07_actual_card(")
    assert "actual_card_campaign_credit(" in source[call : call + 600]
    assert "assembly_runner_digest" in source[call : call + 600]
