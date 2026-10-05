from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path

import pytest
from tools.foundry import agent_benchmark as bench

SHA = "a" * 40
DIGEST = "b" * 64


def arm(name: str, **overrides: object) -> dict:
    doc = {
        "schema_version": "1.0",
        "arm": name,
        "identity": {
            "case_id": "CI_GATE_DIAG_01",
            "task_class": "ci_gate_diagnosis",
            "source_sha": SHA,
            "fixture_digest": DIGEST,
            "required_evidence_class": "DIRECTLY_VERIFIED",
        },
        "session": {
            "session_id": f"session-{name}",
            "agent": "foundry-implementer",
            "model": "opencode-go/deepseek-v4.1-flash",
            "provider": "opencode-go",
            "variant": "max",
            "cli_version": "1.18.30",
            "tokens_input": 1000,
            "tokens_output": 200,
            "tokens_reasoning": 50,
            "tokens_cache_read": 300,
            "tokens_cache_write": 0,
            "cost_usd": 0.5,
            "elapsed_seconds": 120.0,
            "model_turns": 6,
            "tool_calls": 20,
            "tool_calls_by_tool": {
                "read": 4,
                "grep": 3,
                "glob": 1,
                "bash": 10,
                "edit": 2,
            },
            "tool_errors": 0,
            "patch_count": 2,
            "started_utc": "2026-10-05T12:00:00+00:00",
            "ended_utc": "2026-10-05T12:02:00+00:00",
            "compaction_count": None,
        },
        "quality": {
            "technical_outcome": "PASS",
            "final_validation": "PASS",
            "evidence_class": "DIRECTLY_VERIFIED",
            "evidence_complete": True,
            "evidence_loss": False,
            "missed_defects": 0,
            "unresolved_review_findings": 0,
            "scope_violations": 0,
            "failed_attempts": 1,
            "fix_waves": 1,
            "checks_run": 5,
            "context_reloads": None,
        },
    }
    for key, value in overrides.items():
        if key == "session":
            doc["session"].update(value)
        elif key == "quality":
            doc["quality"].update(value)
        elif key == "identity":
            doc["identity"].update(value)
        else:
            doc[key] = value
    return doc


def test_measured_improvement_preserves_quality_and_provenance() -> None:
    baseline = arm("baseline")
    candidate = arm(
        "candidate",
        session={
            "model": "opencode-go/space-bunny-free",
            "tokens_input": 800,
            "tokens_output": 180,
            "elapsed_seconds": 90.0,
            "tool_calls": 15,
            "tool_calls_by_tool": {
                "read": 2,
                "grep": 2,
                "bash": 9,
                "edit": 2,
            },
        },
        quality={"failed_attempts": 0},
    )
    result = bench.compare(baseline, candidate)
    assert result["disposition"] == "PAIR_MEASURED_EFFICIENCY_IMPROVEMENT"
    assert result["candidate_quality_gate"] == "PASS"
    assert result["baseline_session"]["model"] == "opencode-go/deepseek-v4.1-flash"
    assert result["candidate_session"]["model"] == "opencode-go/space-bunny-free"
    assert result["candidate_session"]["cli_version"] == "1.18.30"
    assert result["efficiency_deltas"]["tokens_input"]["percent"] == -20.0
    assert result["efficiency_deltas"]["elapsed_seconds"]["absolute"] == -30.0
    assert result["efficiency_deltas"]["direct_read_calls"]["candidate"] == 2
    assert result["efficiency_deltas"]["direct_search_calls"]["candidate"] == 2
    assert "tokens_input" in result["efficiency_improved_fields"]
    assert not result["efficiency_regressed_fields"]
    assert result["tool_output_volume"] is None
    assert result["tool_output_volume_status"] == "UNAVAILABLE_FROM_SANITIZED_SESSION_STATS"
    assert result["default_promotion_authorized"] is False


@pytest.mark.parametrize(
    "quality_patch,reason",
    [
        ({"evidence_loss": True}, "evidence_loss"),
        ({"missed_defects": 1}, "missed_defects"),
        ({"unresolved_review_findings": 1}, "unresolved_review_findings"),
        ({"scope_violations": 1}, "scope_violations"),
        ({"final_validation": "UNKNOWN"}, "final_validation_not_pass"),
        ({"evidence_class": "UNKNOWN"}, "evidence_class_mismatch"),
    ],
)
def test_quality_loss_always_rejects_candidate(quality_patch: dict, reason: str) -> None:
    result = bench.compare(
        arm("baseline"),
        arm("candidate", quality=quality_patch),
    )
    assert result["disposition"] == "CANDIDATE_REJECT_QUALITY"
    assert result["candidate_quality_gate"] == "FAIL"
    assert reason in result["candidate_quality_reasons"]


def test_required_evidence_class_mismatch_rejects_candidate() -> None:
    result = bench.compare(
        arm("baseline"),
        arm(
            "candidate",
            quality={"evidence_class": "TECHNICALLY_CONFORMANT"},
        ),
    )
    assert result["disposition"] == "CANDIDATE_REJECT_QUALITY"
    assert result["candidate_quality_gate"] == "FAIL"
    assert "evidence_class_mismatch" in result["candidate_quality_reasons"]


def test_weak_required_evidence_class_rejected_before_comparison() -> None:
    with pytest.raises(bench.BenchmarkError, match="too weak"):
        bench.compare(
            arm("baseline", identity={"required_evidence_class": "CODE_DERIVED"}),
            arm("candidate", identity={"required_evidence_class": "CODE_DERIVED"}),
        )


def test_invalid_baseline_quality_cannot_authorize_measured_pair() -> None:
    result = bench.compare(
        arm("baseline", quality={"final_validation": "UNKNOWN"}),
        arm("candidate"),
    )
    assert result["baseline_quality_gate"] == "FAIL"
    assert result["disposition"] == "BASELINE_REJECT_QUALITY"
    assert result["default_promotion_authorized"] is False


@pytest.mark.parametrize("missing_from", ["both", "baseline", "candidate"])
def test_missing_core_metrics_is_inconclusive_not_savings_claim(
    missing_from: str,
) -> None:
    baseline = arm("baseline")
    candidate = arm("candidate")
    if missing_from in {"both", "baseline"}:
        del baseline["session"]["tokens_input"]
    if missing_from in {"both", "candidate"}:
        del candidate["session"]["tokens_input"]
    result = bench.compare(baseline, candidate)
    assert result["disposition"] == "INCONCLUSIVE_MISSING_CORE_METRICS"
    assert "tokens_input" not in result["core_efficiency_fields_compared"]
    assert result["default_promotion_authorized"] is False


def test_identity_mismatch_rejected() -> None:
    with pytest.raises(bench.BenchmarkError, match="identity-equivalent"):
        bench.compare(
            arm("baseline"),
            arm("candidate", identity={"source_sha": "c" * 40}),
        )


def test_unknown_identity_field_rejected_instead_of_dropped() -> None:
    candidate = arm("candidate")
    candidate["identity"]["case_seed"] = "seed-A"
    with pytest.raises(bench.BenchmarkError, match="unsupported fields"):
        bench.compare(arm("baseline"), candidate)


@pytest.mark.parametrize(
    "scope,patch",
    [
        ("benchmark arm", {"extra": "value"}),
        ("quality", {"quality": {"extra": 1}}),
        ("session", {"session": {"extra": 1}}),
    ],
)
def test_unknown_fields_fail_closed(scope: str, patch: dict) -> None:
    candidate = arm("candidate", **patch)
    with pytest.raises(bench.BenchmarkError, match=scope):
        bench.compare(arm("baseline"), candidate)


def test_same_session_cannot_be_compared_to_itself() -> None:
    candidate = arm("candidate", session={"session_id": "session-baseline"})
    with pytest.raises(bench.BenchmarkError, match="distinct sessions"):
        bench.compare(arm("baseline"), candidate)


def test_cli_version_mismatch_rejected() -> None:
    candidate = arm("candidate", session={"cli_version": "1.18.31"})
    with pytest.raises(bench.BenchmarkError, match="same CLI version"):
        bench.compare(arm("baseline"), candidate)


@pytest.mark.parametrize(
    "tool_calls,by_tool",
    [
        (3, {"read": 400, "grep": 400, "bash": 5}),
        (100, {"read": 4, "grep": 3, "glob": 1, "bash": 10, "edit": 2}),
    ],
)
def test_tool_count_integrity_rejected(tool_calls: int, by_tool: dict[str, int]) -> None:
    candidate = arm(
        "candidate",
        session={"tool_calls": tool_calls, "tool_calls_by_tool": by_tool},
    )
    with pytest.raises(bench.BenchmarkError, match="do not sum"):
        bench.compare(arm("baseline"), candidate)


def test_tool_errors_cannot_exceed_tool_calls() -> None:
    candidate = arm("candidate", session={"tool_errors": 21})
    with pytest.raises(bench.BenchmarkError, match="cannot exceed"):
        bench.compare(arm("baseline"), candidate)


@pytest.mark.parametrize("field", ["model_turns", "tool_errors", "patch_count"])
def test_required_session_counters_cannot_be_null(field: str) -> None:
    candidate = arm("candidate", session={field: None})
    with pytest.raises(bench.BenchmarkError, match="is required"):
        bench.compare(arm("baseline"), candidate)


def test_tool_error_regression_is_machine_readable() -> None:
    result = bench.compare(
        arm("baseline"),
        arm("candidate", session={"tool_errors": 2}),
    )
    assert result["disposition"] == "PAIR_MEASURED_EFFICIENCY_REGRESSION"
    assert "tool_errors" in result["efficiency_regressed_fields"]


def test_dramatically_worse_candidate_is_not_labeled_favorable() -> None:
    result = bench.compare(
        arm("baseline"),
        arm(
            "candidate",
            session={
                "tokens_input": 9_001_000,
                "elapsed_seconds": 100_119.0,
            },
            quality={"failed_attempts": 77, "fix_waves": 40},
        ),
    )
    assert result["disposition"] == "PAIR_MEASURED_EFFICIENCY_REGRESSION"
    assert "tokens_input" in result["efficiency_regressed_fields"]
    assert "elapsed_seconds" in result["efficiency_regressed_fields"]
    assert "failed_attempts" in result["efficiency_regressed_fields"]
    assert "fix_waves" in result["efficiency_regressed_fields"]


def test_cost_regression_is_machine_readable() -> None:
    result = bench.compare(
        arm("baseline"),
        arm("candidate", session={"cost_usd": 5.0}),
    )
    assert result["disposition"] == "PAIR_MEASURED_EFFICIENCY_REGRESSION"
    assert "cost_usd" in result["efficiency_regressed_fields"]
    assert result["efficiency_deltas"]["cost_usd"]["change"] == "increased"


def test_reasoning_and_direct_read_regressions_are_machine_readable() -> None:
    result = bench.compare(
        arm("baseline"),
        arm(
            "candidate",
            session={
                "tokens_reasoning": 500,
                "tool_calls_by_tool": {
                    "read": 10,
                    "grep": 3,
                    "glob": 1,
                    "bash": 4,
                    "edit": 2,
                },
            },
        ),
    )
    assert result["disposition"] == "PAIR_MEASURED_EFFICIENCY_REGRESSION"
    assert "tokens_reasoning" in result["efficiency_regressed_fields"]
    assert "direct_read_calls" in result["efficiency_regressed_fields"]


def test_reduced_verification_checks_reject_candidate() -> None:
    result = bench.compare(
        arm("baseline"),
        arm("candidate", quality={"checks_run": 4}),
    )
    assert result["disposition"] == "CANDIDATE_REJECT_QUALITY"
    assert "verification_checks_reduced" in result["candidate_quality_reasons"]
    assert result["efficiency_deltas"]["checks_run"]["change"] == "decreased"


def test_cache_read_delta_is_observation_not_efficiency_direction() -> None:
    result = bench.compare(
        arm("baseline"),
        arm("candidate", session={"tokens_cache_read": 100}),
    )
    assert "tokens_cache_read" not in result["efficiency_improved_fields"]
    assert "tokens_cache_read" not in result["efficiency_regressed_fields"]
    assert result["efficiency_deltas"]["tokens_cache_read"]["change"] == "decreased"


def test_mixed_efficiency_has_explicit_disposition() -> None:
    result = bench.compare(
        arm("baseline"),
        arm(
            "candidate",
            session={"tokens_input": 800, "elapsed_seconds": 180.0},
        ),
    )
    assert result["disposition"] == "PAIR_MEASURED_MIXED_EFFICIENCY"
    assert "tokens_input" in result["efficiency_improved_fields"]
    assert "elapsed_seconds" in result["efficiency_regressed_fields"]


def test_no_efficiency_change_is_explicit() -> None:
    result = bench.compare(arm("baseline"), arm("candidate"))
    assert result["disposition"] == "PAIR_MEASURED_NO_EFFICIENCY_CHANGE"
    assert not result["efficiency_improved_fields"]
    assert not result["efficiency_regressed_fields"]


def test_verification_check_collapse_rejects_candidate() -> None:
    result = bench.compare(
        arm("baseline"),
        arm("candidate", quality={"checks_run": 0}),
    )
    assert result["disposition"] == "CANDIDATE_REJECT_QUALITY"
    assert "verification_checks_reduced" in result["candidate_quality_reasons"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("tokens_input", True),
        ("tokens_input", -1),
        ("tool_calls", 1.5),
        ("elapsed_seconds", float("inf")),
        ("cost_usd", -0.1),
    ],
)
def test_invalid_measurements_rejected(field: str, value: object) -> None:
    with pytest.raises(bench.BenchmarkError):
        bench.compare(
            arm("baseline"),
            arm("candidate", session={field: value}),
        )


def test_extreme_json_integer_literal_rejected_without_traceback(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        '{"schema_version":"1.0","arm":"baseline","identity":{"case_id":' + "9" * 5000 + "}}",
        encoding="utf-8",
    )
    candidate.write_text(json.dumps(arm("candidate")), encoding="utf-8")
    assert bench.main(["--baseline", str(baseline), "--candidate", str(candidate)]) == 2
    captured = capsys.readouterr()
    assert "AGENT_BENCHMARK_REJECT" in captured.out
    assert "Traceback" not in captured.out
    assert "9999999999" not in captured.out


def test_huge_finite_integer_delta_rejected_cleanly(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps(arm("baseline")), encoding="utf-8")
    candidate.write_text(
        json.dumps(arm("candidate", session={"tokens_input": 10**400})),
        encoding="utf-8",
    )
    assert bench.main(["--baseline", str(baseline), "--candidate", str(candidate)]) == 2
    captured = capsys.readouterr()
    assert "AGENT_BENCHMARK_REJECT" in captured.out
    assert "Traceback" not in captured.out


def test_non_finite_delta_from_finite_inputs_rejected_cleanly() -> None:
    baseline = arm("baseline", session={"elapsed_seconds": 5e-324})
    candidate = arm("candidate", session={"elapsed_seconds": 1e308})
    with pytest.raises(bench.BenchmarkError, match="numeric range"):
        bench.compare(baseline, candidate)


def test_zero_baseline_percent_is_null_not_zero() -> None:
    result = bench.compare(
        arm("baseline", session={"cost_usd": 0.0}),
        arm("candidate", session={"cost_usd": 1.0}),
    )
    delta = result["efficiency_deltas"]["cost_usd"]
    assert delta["percent"] is None
    assert delta["change"] == "increased"
    assert result["disposition"] == "PAIR_MEASURED_EFFICIENCY_REGRESSION"


def test_required_evidence_class_is_part_of_identity_equivalence() -> None:
    baseline = arm("baseline")
    candidate = arm(
        "candidate",
        identity={"required_evidence_class": "TECHNICALLY_CONFORMANT"},
        quality={"evidence_class": "TECHNICALLY_CONFORMANT"},
    )
    with pytest.raises(bench.BenchmarkError, match="identity-equivalent"):
        bench.compare(baseline, candidate)


def test_arm_label_must_match_role() -> None:
    with pytest.raises(bench.BenchmarkError, match="arm must be candidate"):
        bench.compare(arm("baseline"), arm("baseline"))


def test_non_null_compaction_count_rejected() -> None:
    candidate = arm("candidate", session={"compaction_count": 1})
    with pytest.raises(bench.BenchmarkError, match="must remain unavailable"):
        bench.compare(arm("baseline"), candidate)


def test_cli_rejects_duplicate_json_keys_without_echoing_content(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        '{"schema_version":"1.0","schema_version":"PRIVATE_SENTINEL"}',
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(arm("candidate")),
        encoding="utf-8",
    )
    assert (
        bench.main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "AGENT_BENCHMARK_REJECT" in captured.out
    assert "PRIVATE_SENTINEL" not in captured.out


def test_invalid_tool_count_does_not_echo_tool_name(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    bad = arm(
        "candidate",
        session={
            "tool_calls_by_tool": {
                "read_PRIVATE_SENTINEL": -1,
                "grep": 3,
                "glob": 1,
                "bash": 10,
                "edit": 2,
            }
        },
    )
    baseline.write_text(json.dumps(arm("baseline")), encoding="utf-8")
    candidate.write_text(json.dumps(bad), encoding="utf-8")
    assert (
        bench.main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "PRIVATE_SENTINEL" not in captured.out


@pytest.mark.parametrize("kind", ["same", "symlink", "hardlink"])
def test_cli_output_cannot_alias_input(tmp_path: Path, capsys, kind: str) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps(arm("baseline")), encoding="utf-8")
    candidate.write_text(json.dumps(arm("candidate")), encoding="utf-8")
    before = baseline.read_bytes()
    output = baseline
    if kind != "same":
        output = tmp_path / "alias.json"
        try:
            if kind == "symlink":
                output.symlink_to(baseline)
            else:
                os.link(baseline, output)
        except OSError:
            pytest.skip(f"{kind} creation unavailable")

    assert (
        bench.main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert baseline.read_bytes() == before
    captured = capsys.readouterr()
    assert "write-once" in captured.out


def test_existing_non_input_output_is_never_overwritten(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "existing.json"
    baseline.write_text(json.dumps(arm("baseline")), encoding="utf-8")
    candidate.write_text(json.dumps(arm("candidate")), encoding="utf-8")
    output.write_text("PRIVATE_SENTINEL\n", encoding="utf-8")
    assert (
        bench.main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert output.read_text(encoding="utf-8") == "PRIVATE_SENTINEL\n"
    captured = capsys.readouterr()
    assert "PRIVATE_SENTINEL" not in captured.out


def test_atomic_write_once_survives_concurrent_publishers(tmp_path: Path) -> None:
    output = tmp_path / "race.json"
    payload = {"disposition": "PAIR_MEASURED_NO_EFFICIENCY_CHANGE"}

    def publish() -> bool:
        try:
            bench._atomic_write_new(str(output), payload)
        except bench.BenchmarkError:
            return False
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: publish(), range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert not list(tmp_path.glob(".agent-benchmark-*"))


def test_cli_atomic_write_once_output(tmp_path: Path) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "result.json"
    baseline.write_text(json.dumps(arm("baseline")), encoding="utf-8")
    candidate.write_text(
        json.dumps(arm("candidate", session={"tokens_input": 800})),
        encoding="utf-8",
    )
    assert (
        bench.main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["disposition"] == "PAIR_MEASURED_EFFICIENCY_IMPROVEMENT"
    assert not list(tmp_path.glob(".agent-benchmark-*"))


def test_inconclusive_cli_returns_distinct_nonzero(tmp_path: Path, capsys) -> None:
    baseline_doc = arm("baseline")
    candidate_doc = arm("candidate")
    del candidate_doc["session"]["tokens_input"]
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps(baseline_doc), encoding="utf-8")
    candidate.write_text(json.dumps(candidate_doc), encoding="utf-8")
    assert bench.main(["--baseline", str(baseline), "--candidate", str(candidate)]) == 4
    result = json.loads(capsys.readouterr().out)
    assert result["disposition"] == "INCONCLUSIVE_MISSING_CORE_METRICS"


def test_quality_rejection_writes_artifact_but_returns_distinct_nonzero(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "reject.json"
    baseline.write_text(json.dumps(arm("baseline")), encoding="utf-8")
    candidate.write_text(
        json.dumps(
            arm(
                "candidate",
                quality={"evidence_loss": True},
            )
        ),
        encoding="utf-8",
    )
    assert (
        bench.main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--output",
                str(output),
            ]
        )
        == 3
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["disposition"] == "CANDIDATE_REJECT_QUALITY"


def test_quality_rejection_stdout_returns_distinct_nonzero(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        json.dumps(arm("baseline", quality={"final_validation": "UNKNOWN"})),
        encoding="utf-8",
    )
    candidate.write_text(json.dumps(arm("candidate")), encoding="utf-8")
    assert (
        bench.main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
            ]
        )
        == 3
    )
    result = json.loads(capsys.readouterr().out)
    assert result["disposition"] == "BASELINE_REJECT_QUALITY"
