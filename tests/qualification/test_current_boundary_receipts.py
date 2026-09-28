"""Adversarial tests for the execution-receipt layer.

The point of these tests is that the *absence* or *defect* of a receipt yields no
credit. A qualification system that can pass without having observed anything is
the exact failure this module exists to make impossible, so every negative case is
asserted explicitly rather than assumed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import receipts as R


def _identity(root: Path, *, dirty: bool = False) -> R.RunnerIdentity:
    return R.RunnerIdentity(
        repository="https://github.com/moeendres-png/commander-playtest-lab",
        commit="a" * 40,
        tree="b" * 40,
        branch="test/branch",
        dirty=dirty,
        dirty_paths=("src/commander_lab/qualification/current_boundary/full107.py",)
        if dirty
        else (),
        input_digests={"scripts/run_current_boundary_qualification.py": "c" * 64},
    )


def _good_receipt(**overrides: object) -> dict:
    doc = {
        "schema_version": R.NATIVE_SUITE_RECEIPT_SCHEMA,
        "candidate": "xmage",
        "group": "direct",
        "command": "mvn -q -pl engine-bridge test",
        "candidate_repository": "https://github.com/moeendres-png/mage",
        "candidate_commit": "d" * 40,
        "candidate_tree": "e" * 40,
        "build_identity": "mage-1.4.61",
        "started_utc": "2026-09-27T10:00:00+00:00",
        "ended_utc": "2026-09-27T10:04:00+00:00",
        "returncode": 0,
        "tests": 34,
        "passed": 34,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "environment": {"python": "3.12.14"},
        "runner": _identity(Path(".")).to_document(),
        "runner_digest": _identity(Path(".")).digest(),
        "classes": ["XmageFull107ResidualRequalificationTest"],
        "positive_fixtures": [],
    }
    doc.update(overrides)
    doc.pop("receipt_digest", None)
    doc["receipt_digest"] = R._digest(doc)
    return doc


# --- Gate 1: native suite receipts are all-or-nothing ------------------------ #


def test_valid_receipt_is_accepted(tmp_path: Path) -> None:
    path = R.persist(tmp_path / "r.json", _good_receipt())
    doc = R.load_native_receipt(path)
    assert doc["candidate"] == "xmage"
    assert doc["tests"] == 34


def test_missing_receipt_yields_no_credit(tmp_path: Path) -> None:
    with pytest.raises(R.ReceiptError, match="NO_CREDIT"):
        R.load_native_receipt(tmp_path / "absent.json")
    valid, rejected = R.collect_receipts(tmp_path)
    # An existing but empty receipt directory legitimately has nothing to reject;
    # it still contributes zero credit, which is the property that matters.
    assert valid == [] and rejected == []


def test_absent_receipt_directory_yields_no_credit(tmp_path: Path) -> None:
    valid, rejected = R.collect_receipts(tmp_path / "never-created")
    assert valid == []
    assert rejected and "NO_CREDIT" in rejected[0]


def test_non_zero_return_code_yields_no_credit(tmp_path: Path) -> None:
    path = R.persist(tmp_path / "r.json", _good_receipt(returncode=1, passed=0))
    with pytest.raises(R.ReceiptError, match="no PASS credit"):
        R.load_native_receipt(path)


def test_reported_failures_yield_no_credit(tmp_path: Path) -> None:
    path = R.persist(tmp_path / "r.json", _good_receipt(failed=2, passed=32))
    with pytest.raises(R.ReceiptError, match="no PASS credit"):
        R.load_native_receipt(path)


def test_reported_errors_yield_no_credit(tmp_path: Path) -> None:
    path = R.persist(tmp_path / "r.json", _good_receipt(errors=1, passed=33))
    with pytest.raises(R.ReceiptError, match="no PASS credit"):
        R.load_native_receipt(path)


def test_tampered_receipt_digest_yields_no_credit(tmp_path: Path) -> None:
    doc = _good_receipt()
    doc["tests"] = 999  # digest no longer matches
    path = R.persist(tmp_path / "r.json", doc)
    with pytest.raises(R.ReceiptError, match="digest mismatch"):
        R.load_native_receipt(path)


def test_wrong_schema_yields_no_credit(tmp_path: Path) -> None:
    path = R.persist(tmp_path / "r.json", _good_receipt(schema_version="something-else/9"))
    with pytest.raises(R.ReceiptError, match="NO_CREDIT"):
        R.load_native_receipt(path)


def test_truncated_receipt_yields_no_credit(tmp_path: Path) -> None:
    doc = _good_receipt()
    doc.pop("candidate_commit")
    doc["receipt_digest"] = R._digest(doc)
    path = R.persist(tmp_path / "r.json", doc)
    with pytest.raises(R.ReceiptError, match="missing 'candidate_commit'"):
        R.load_native_receipt(path)


def test_unparsable_receipt_yields_no_credit(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(R.ReceiptError, match="NO_CREDIT"):
        R.load_native_receipt(path)


def test_one_bad_receipt_does_not_suppress_good_ones(tmp_path: Path) -> None:
    R.persist(tmp_path / "good.json", _good_receipt())
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    valid, rejected = R.collect_receipts(tmp_path)
    assert len(valid) == 1
    assert len(rejected) == 1 and "NO_CREDIT" in rejected[0]


def test_stale_candidate_commit_gets_no_credit() -> None:
    receipts = [_good_receipt()]
    credit = R.native_suite_credit(receipts, candidate="xmage", expected_commit="f" * 40)
    assert credit["groups_credited"] == []
    assert credit["tests"] == 0


def test_credit_aggregates_only_matching_candidate() -> None:
    receipts = [_good_receipt(), _good_receipt(candidate="forge")]
    credit = R.native_suite_credit(receipts, candidate="xmage", expected_commit="d" * 40)
    assert credit["groups_credited"] == ["xmage:direct"]
    assert credit["tests"] == 34


def test_parse_maven_summary_requires_a_summary() -> None:
    with pytest.raises(R.ReceiptError, match="NO_SUMMARY"):
        R.parse_maven_summary("build log with no terminal summary\n")


def test_parse_maven_summary_reads_the_last_summary() -> None:
    text = (
        "[INFO] Tests run: 3, Failures: 1, Errors: 0, Skipped: 0\n"
        "[INFO] Tests run: 34, Failures: 0, Errors: 0, Skipped: 2\n"
    )
    assert R.parse_maven_summary(text) == {"tests": 34, "failures": 0, "errors": 0, "skipped": 2}


# --- Gate 2: positive fixture bindings ------------------------------------- #

_DENOM = {"HIDDEN_02", "MICRO_STACK", "CARD_02"}


def _fixture_receipt(**overrides: object) -> dict:
    doc = {
        "schema_version": R.POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": "xmage",
        "candidate_commit": "d" * 40,
        "fixture_id": "MICRO_STACK",
        "test_identity": "XmageFullGameMicroExecutionTest#microStack",
        "obligation_exercised": "spell resolution on the stack",
        "observed_assertion": "stack depth observed to be 1 after resolution",
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "outcome": "PASS",
        "runtime_receipt_digest": "f" * 64,
    }
    doc.update(overrides)
    return doc


def test_positive_fixture_credit_accepted() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt()], candidate="xmage", expected_commit="d" * 40, denominator=_DENOM
    )
    assert credit == {"MICRO_STACK": ["XmageFullGameMicroExecutionTest#microStack"]}


def test_nested_positive_fixture_in_verified_native_receipt_is_accepted() -> None:
    child = _fixture_receipt()
    # A nested child is cryptographically covered by the parent receipt. It
    # therefore does not need the impossible circular parent receipt digest.
    child.pop("runtime_receipt_digest", None)
    parent = _good_receipt(positive_fixtures=[child])
    credit = R.positive_fixture_credit(
        [parent], candidate="xmage", expected_commit="d" * 40, denominator=_DENOM
    )
    assert credit == {"MICRO_STACK": ["XmageFullGameMicroExecutionTest#microStack"]}


def test_nested_fixture_cannot_escape_parent_candidate_or_head() -> None:
    wrong_candidate = _fixture_receipt(candidate="forge")
    wrong_head = _fixture_receipt(candidate_commit="0" * 40)
    parent = _good_receipt(positive_fixtures=[wrong_candidate, wrong_head])
    credit = R.positive_fixture_credit(
        [parent], candidate="xmage", expected_commit="d" * 40, denominator=_DENOM
    )
    assert credit == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assertion_kind", "CONSTRUCTION_ONLY"),
        ("outcome", "FAIL"),
        ("observed_assertion", ""),
        ("obligation_exercised", ""),
        ("test_identity", ""),
        ("schema_version", "wrong/1"),
    ],
)
def test_nested_nonpositive_or_incomplete_fixture_cannot_promote(field: str, value: str) -> None:
    child = _fixture_receipt(**{field: value})
    parent = _good_receipt(positive_fixtures=[child])
    assert (
        R.positive_fixture_credit(
            [parent], candidate="xmage", expected_commit="d" * 40, denominator=_DENOM
        )
        == {}
    )


def test_nested_fixture_in_failed_or_tampered_parent_cannot_promote() -> None:
    child = _fixture_receipt()
    failed_parent = _good_receipt(positive_fixtures=[child], failed=1, passed=33)
    tampered_parent = _good_receipt(positive_fixtures=[child])
    tampered_parent["tests"] = 999
    assert (
        R.positive_fixture_credit(
            [failed_parent, tampered_parent],
            candidate="xmage",
            expected_commit="d" * 40,
            denominator=_DENOM,
        )
        == {}
    )


def test_collect_receipts_plus_nested_credit_is_end_to_end(tmp_path: Path) -> None:
    child = _fixture_receipt()
    child.pop("runtime_receipt_digest", None)
    R.persist(tmp_path / "native.json", _good_receipt(positive_fixtures=[child]))
    verified, rejected = R.collect_receipts(tmp_path)
    assert rejected == []
    assert R.positive_fixture_credit(
        verified, candidate="xmage", expected_commit="d" * 40, denominator=_DENOM
    ) == {"MICRO_STACK": ["XmageFullGameMicroExecutionTest#microStack"]}


def test_negative_assertion_cannot_promote() -> None:
    """The exact HIDDEN_02 defect: a test asserting FAILURE must never promote."""
    credit = R.positive_fixture_credit(
        [
            _fixture_receipt(
                fixture_id="HIDDEN_02",
                test_identity="XmageHiddenReplayIntegrationTest#hidden02",
                observed_assertion="loading HIDDEN_02 fails with LEGACY_LIBRARY_ORDER_AMBIGUOUS",
                assertion_kind="NEGATIVE_REJECTION",
                outcome="PASS",
            )
        ],
        candidate="xmage",
        expected_commit="d" * 40,
        denominator=_DENOM,
    )
    assert credit == {}


def test_bare_mention_without_observation_cannot_promote() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt(observed_assertion="")],
        candidate="xmage",
        expected_commit="d" * 40,
        denominator=_DENOM,
    )
    assert credit == {}


def test_construction_only_assertion_cannot_promote() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt(assertion_kind="CONSTRUCTION_ONLY")],
        candidate="xmage",
        expected_commit="d" * 40,
        denominator=_DENOM,
    )
    assert credit == {}


def test_failed_outcome_cannot_promote() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt(outcome="FAIL")],
        candidate="xmage",
        expected_commit="d" * 40,
        denominator=_DENOM,
    )
    assert credit == {}


def test_stale_candidate_head_cannot_promote() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt()], candidate="xmage", expected_commit="0" * 40, denominator=_DENOM
    )
    assert credit == {}


def test_wrong_candidate_cannot_promote() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt()], candidate="forge", expected_commit="d" * 40, denominator=_DENOM
    )
    assert credit == {}


def test_fixture_outside_the_denominator_cannot_promote() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt(fixture_id="NOT_A_ROW")],
        candidate="xmage",
        expected_commit="d" * 40,
        denominator=_DENOM,
    )
    assert credit == {}


def test_wrong_schema_cannot_promote() -> None:
    credit = R.positive_fixture_credit(
        [_fixture_receipt(schema_version="nope/1")],
        candidate="xmage",
        expected_commit="d" * 40,
        denominator=_DENOM,
    )
    assert credit == {}


# --- Gate 3: Rules-RNG seed binding --------------------------------------- #


def test_acknowledged_matching_seed_is_controlled() -> None:
    binding = R.classify_seed_binding(
        requested_seed=424242, acknowledged_seed=424242, source="create_response.seed"
    )
    assert binding.classification == R.SEED_ACKNOWLEDGED
    assert binding.to_document()["rng_credit"] is True


def test_unacknowledged_seed_is_uncontrolled() -> None:
    binding = R.classify_seed_binding(
        requested_seed=424242, acknowledged_seed=None, source="absent"
    )
    assert binding.classification == R.SEED_UNCONTROLLED
    assert binding.to_document()["rng_credit"] is False


def test_ignored_seed_is_uncontrolled() -> None:
    binding = R.classify_seed_binding(
        requested_seed=424242, acknowledged_seed=99, source="create_response.seed"
    )
    assert binding.classification == R.SEED_UNCONTROLLED
    assert binding.controlled is False


def test_wrong_seed_is_uncontrolled() -> None:
    binding = R.classify_seed_binding(
        requested_seed=424242, acknowledged_seed=1, source="engine_default"
    )
    assert binding.classification == R.SEED_UNCONTROLLED


def test_string_echoed_seed_is_accepted_only_when_exact() -> None:
    assert (
        R.classify_seed_binding(
            requested_seed=7, acknowledged_seed="7", source="echo"
        ).classification
        == R.SEED_ACKNOWLEDGED
    )
    assert (
        R.classify_seed_binding(
            requested_seed=7, acknowledged_seed="8", source="echo"
        ).classification
        == R.SEED_UNCONTROLLED
    )


def test_boolean_seed_is_not_a_seed() -> None:
    binding = R.classify_seed_binding(requested_seed=1, acknowledged_seed=True, source="bogus")
    assert binding.acknowledged_seed is None
    assert binding.classification == R.SEED_UNCONTROLLED


def test_no_requested_seed_means_uncontrolled() -> None:
    binding = R.classify_seed_binding(
        requested_seed=None, acknowledged_seed=5, source="create_response.seed"
    )
    assert binding.classification == R.SEED_UNCONTROLLED


def test_nan_like_seed_is_not_accepted() -> None:
    binding = R.classify_seed_binding(requested_seed=1, acknowledged_seed="NaN", source="bogus")
    assert binding.acknowledged_seed is None


# --- Gate 4: clean runner identity ---------------------------------------- #


def test_dirty_runner_is_refused() -> None:
    with pytest.raises(R.ReceiptError, match="RUNNER_DIRTY"):
        R.require_clean_runner(_identity(Path("."), dirty=True))


def test_clean_runner_is_accepted() -> None:
    R.require_clean_runner(_identity(Path("."), dirty=False))


def test_capture_binds_real_git_and_file_state(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    target = tmp_path / "scripts"
    target.mkdir()
    (target / "run_current_boundary_qualification.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    identity = R.capture_runner_identity(tmp_path)
    assert identity.dirty is False
    assert identity.dirty_paths == ()
    assert (
        identity.commit
        == subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    assert "scripts/run_current_boundary_qualification.py" in identity.input_digests

    (target / "run_current_boundary_qualification.py").write_text("x = 2\n", encoding="utf-8")
    dirty = R.capture_runner_identity(tmp_path)
    assert dirty.dirty is True
    with pytest.raises(R.ReceiptError, match="RUNNER_DIRTY"):
        R.require_clean_runner(dirty)


def test_runner_mutation_during_run_is_detected(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    target = tmp_path / "scripts"
    target.mkdir()
    script = target / "run_current_boundary_qualification.py"
    script.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    identity = R.capture_runner_identity(tmp_path)
    R.verify_runner_unchanged(tmp_path, identity)  # unchanged is fine
    script.write_text("x = 99\n", encoding="utf-8")
    with pytest.raises(R.ReceiptError, match="RUNNER_MUTATED"):
        R.verify_runner_unchanged(tmp_path, identity)


def test_zero_captured_inputs_refuses_to_bind(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "unrelated.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    with pytest.raises(R.ReceiptError, match="zero executed inputs"):
        R.capture_runner_identity(tmp_path)


def test_receipt_round_trips_through_disk(tmp_path: Path) -> None:
    path = R.persist(tmp_path / "nested" / "r.json", _good_receipt())
    assert json.loads(path.read_text(encoding="utf-8"))["candidate"] == "xmage"


# --- PB-09 class: recorded candidate identity vs executing identity --------- #


def test_matching_candidate_identity_is_accepted() -> None:
    R.verify_candidate_identity(
        recorded_commit="a" * 40, actual_commit="a" * 40, recorded_label="suite"
    )


def test_recorded_commit_differing_from_executing_is_refused() -> None:
    with pytest.raises(R.ReceiptError, match="CANDIDATE_IDENTITY_DIVERGENCE"):
        R.verify_candidate_identity(
            recorded_commit="ef958ee9" + "0" * 32,
            actual_commit="18bba95a4" + "0" * 32,
            recorded_label="native suite forge:direct",
        )


def test_ancestor_is_not_accepted_as_identity() -> None:
    """A descendant is a different tree and may carry Rules-Core changes."""
    with pytest.raises(R.ReceiptError, match="CANDIDATE_IDENTITY_DIVERGENCE"):
        R.verify_candidate_identity(
            recorded_commit="ef958ee91ac6c9ce0152189f2654bf6e05abf273",
            actual_commit="18bba95a4528f6ab5910633f1f87f603b8c4ddf8",
            recorded_label="forge fork",
        )
