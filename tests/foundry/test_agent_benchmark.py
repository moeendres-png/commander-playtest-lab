from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import agent_benchmark as bench  # noqa: E402


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
        },
        "session": {
            "model": "opencode-go/deepseek-v4.1-flash",
            "variant": "max",
            "tokens_input": 1000,
            "tokens_output": 200,
            "tokens_reasoning": 50,
            "tokens_cache_read": 300,
            "tokens_cache_write": 0,
            "elapsed_seconds": 120.0,
            "tool_calls": 20,
            "model_turns": 6,
            "patch_count": 2,
            "tool_calls_by_tool": {
                "read": 4,
                "grep": 3,
                "glob": 1,
                "bash": 10,
                "edit": 2,
            },
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


def test_measured_pair_preserves_quality_and_reports_deltas() -> None:
    baseline = arm("baseline")
    candidate = arm(
        "candidate",
        session={
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
    assert result["disposition"] == "PAIR_MEASURED_QUALITY_PRESERVED"
    assert result["candidate_quality_gate"] == "PASS"
    assert result["efficiency_deltas"]["tokens_input"]["percent"] == -20.0
    assert result["efficiency_deltas"]["elapsed_seconds"]["absolute"] == -30.0
    assert result["efficiency_deltas"]["direct_read_calls"]["candidate"] == 2
    assert result["efficiency_deltas"]["direct_search_calls"]["candidate"] == 2
    assert result["tool_output_volume"] is None
    assert result["default_promotion_authorized"] is False


@pytest.mark.parametrize(
    "quality_patch,reason",
    [
        ({"evidence_loss": True}, "evidence_loss"),
        ({"missed_defects": 1}, "missed_defects"),
        ({"unresolved_review_findings": 1}, "unresolved_review_findings"),
        ({"scope_violations": 1}, "scope_violations"),
        ({"final_validation": "UNKNOWN"}, "final_validation_not_pass"),
        ({"evidence_class": "UNKNOWN"}, "insufficient_evidence_class"),
    ],
)
def test_quality_loss_always_rejects_candidate(
    quality_patch: dict, reason: str
) -> None:
    result = bench.compare(
        arm("baseline"),
        arm("candidate", quality=quality_patch),
    )
    assert result["disposition"] == "CANDIDATE_REJECT_QUALITY"
    assert result["candidate_quality_gate"] == "FAIL"
    assert reason in result["candidate_quality_reasons"]


def test_missing_core_metrics_is_inconclusive_not_savings_claim() -> None:
    baseline = arm("baseline")
    candidate = arm("candidate")
    del baseline["session"]["tokens_input"]
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("tokens_input", True),
        ("tokens_input", -1),
        ("tool_calls", 1.5),
        ("elapsed_seconds", float("inf")),
    ],
)
def test_invalid_measurements_rejected(field: str, value: object) -> None:
    with pytest.raises(bench.BenchmarkError):
        bench.compare(
            arm("baseline"),
            arm("candidate", session={field: value}),
        )


def test_cli_rejects_duplicate_json_keys_without_echoing_content(
    tmp_path: Path, capsys
) -> None:
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


def test_cli_atomic_output(tmp_path: Path) -> None:
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "result.json"
    baseline.write_text(
        json.dumps(arm("baseline")),
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
                "--output",
                str(output),
            ]
        )
        == 0
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["disposition"] == "PAIR_MEASURED_QUALITY_PRESERVED"
    assert not list(tmp_path.glob(".agent-benchmark-*"))
