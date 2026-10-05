"""Fail-closed A/B comparison for Commander agent-efficiency experiments.

Consumes only sanitized session summaries produced by session_stats.py plus an explicit
quality/outcome record. Raw OpenCode exports remain LOCAL_ONLY.

A single pair can establish measured deltas, but can never by itself authorize a default
harness change. Default promotion requires a representative multi-case campaign and the
project's normal review/merge gates.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

SCHEMA_VERSION = "1.0"
OUTCOMES = {"PASS", "FAIL", "UNKNOWN"}
EVIDENCE_CLASSES = {
    "DIRECTLY_VERIFIED",
    "CODE_DERIVED",
    "TECHNICALLY_CONFORMANT",
    "EXTERNALLY_RULE_VALIDATED",
    "MODELED",
    "SYNTHETIC",
    "UNKNOWN",
}
BENCHMARK_EVIDENCE_CLASSES = {
    "DIRECTLY_VERIFIED",
    "TECHNICALLY_CONFORMANT",
    "EXTERNALLY_RULE_VALIDATED",
}

TOP_LEVEL_FIELDS = {"schema_version", "arm", "identity", "session", "quality"}
IDENTITY_FIELDS = {
    "case_id",
    "task_class",
    "source_sha",
    "fixture_digest",
    "required_evidence_class",
}
QUALITY_FIELDS = {
    "technical_outcome",
    "final_validation",
    "evidence_class",
    "evidence_complete",
    "evidence_loss",
    "missed_defects",
    "unresolved_review_findings",
    "scope_violations",
    "failed_attempts",
    "fix_waves",
    "checks_run",
    "context_reloads",
}
SESSION_FIELDS = {
    "session_id",
    "agent",
    "model",
    "provider",
    "variant",
    "cli_version",
    "model_turns",
    "tool_calls",
    "tool_calls_by_tool",
    "tool_errors",
    "patch_count",
    "tokens_input",
    "tokens_output",
    "tokens_reasoning",
    "tokens_cache_read",
    "tokens_cache_write",
    "cost_usd",
    "started_utc",
    "ended_utc",
    "elapsed_seconds",
    "compaction_count",
}
SESSION_REQUIRED_FIELDS = {
    "session_id",
    "agent",
    "model",
    "provider",
    "variant",
    "cli_version",
    "model_turns",
    "tool_calls",
    "tool_calls_by_tool",
    "tool_errors",
    "patch_count",
    "compaction_count",
}

CORE_EFFICIENCY_FIELDS = (
    "tokens_input",
    "tokens_output",
    "elapsed_seconds",
    "tool_calls",
)
OPTIONAL_EFFICIENCY_FIELDS = (
    "tokens_reasoning",
    "tokens_cache_read",
    "tokens_cache_write",
    "cost_usd",
    "model_turns",
    "patch_count",
    "tool_errors",
)
LOWER_IS_BETTER_FIELDS = (
    *CORE_EFFICIENCY_FIELDS,
    "tokens_reasoning",
    "cost_usd",
    "model_turns",
    "patch_count",
    "tool_errors",
    "direct_read_calls",
    "direct_search_calls",
    "failed_attempts",
    "fix_waves",
    "context_reloads",
)

READ_TOOLS = {"read", "list"}
SEARCH_TOOLS = {"grep", "glob", "lsp"}
REJECT_DISPOSITIONS = {"BASELINE_REJECT_QUALITY", "CANDIDATE_REJECT_QUALITY"}
INCONCLUSIVE_DISPOSITIONS = {"INCONCLUSIVE_MISSING_CORE_METRICS"}
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]{0,255}$")


class BenchmarkError(ValueError):
    """Invalid or incomparable benchmark input."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BenchmarkError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise BenchmarkError("non-finite JSON constant")


def _load(path: str) -> dict:
    try:
        data = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise BenchmarkError("cannot read valid benchmark JSON") from exc
    if not isinstance(data, dict):
        raise BenchmarkError("benchmark arm must be a JSON object")
    return data


def _reject_unknown_keys(mapping: dict, allowed: set[str], scope: str) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        raise BenchmarkError(f"{scope} contains unsupported fields")


def _require_fields(mapping: dict, required: set[str], scope: str) -> None:
    if not required.issubset(mapping):
        raise BenchmarkError(f"{scope} is missing required fields")


def _label(value: object, field: str) -> str:
    if not isinstance(value, str) or SAFE_LABEL.fullmatch(value) is None:
        raise BenchmarkError(f"invalid {field}")
    return value


def _number(value: object, field: str, *, integer: bool = False) -> int | float:
    if type(value) not in (int, float) or value < 0:
        raise BenchmarkError(f"invalid {field}")
    if isinstance(value, float) and (
        not math.isfinite(value) or (integer and not value.is_integer())
    ):
        raise BenchmarkError(f"invalid {field}")
    return int(value) if integer else value


def _optional_number(mapping: dict, field: str, *, integer: bool = False) -> int | float | None:
    value = mapping.get(field)
    if value is None:
        return None
    return _number(value, field, integer=integer)


def _optional_label(mapping: dict, field: str) -> str | None:
    value = mapping.get(field)
    if value is None:
        return None
    return _label(value, f"session.{field}")


def _validate_identity(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise BenchmarkError("identity must be an object")
    _reject_unknown_keys(value, IDENTITY_FIELDS, "identity")
    _require_fields(value, IDENTITY_FIELDS, "identity")
    result = {key: _label(value.get(key), f"identity.{key}") for key in IDENTITY_FIELDS}
    if len(result["source_sha"]) != 40 or any(
        char not in "0123456789abcdefABCDEF" for char in result["source_sha"]
    ):
        raise BenchmarkError("identity.source_sha must be a full 40-hex SHA")
    if len(result["fixture_digest"]) != 64 or any(
        char not in "0123456789abcdefABCDEF" for char in result["fixture_digest"]
    ):
        raise BenchmarkError("identity.fixture_digest must be a 64-hex digest")
    if result["required_evidence_class"] not in BENCHMARK_EVIDENCE_CLASSES:
        raise BenchmarkError("identity.required_evidence_class is too weak for benchmarking")
    return result


def _validate_quality(value: object) -> dict:
    if not isinstance(value, dict):
        raise BenchmarkError("quality must be an object")
    _reject_unknown_keys(value, QUALITY_FIELDS, "quality")
    _require_fields(value, QUALITY_FIELDS, "quality")
    result = {
        "technical_outcome": _label(value.get("technical_outcome"), "quality.technical_outcome"),
        "final_validation": _label(value.get("final_validation"), "quality.final_validation"),
        "evidence_class": _label(value.get("evidence_class"), "quality.evidence_class"),
    }
    if result["technical_outcome"] not in OUTCOMES:
        raise BenchmarkError("unsupported quality.technical_outcome")
    if result["final_validation"] not in OUTCOMES:
        raise BenchmarkError("unsupported quality.final_validation")
    if result["evidence_class"] not in EVIDENCE_CLASSES:
        raise BenchmarkError("unsupported quality.evidence_class")
    for field in ("evidence_complete", "evidence_loss"):
        raw = value.get(field)
        if type(raw) is not bool:
            raise BenchmarkError(f"quality.{field} must be boolean")
        result[field] = raw
    for field in (
        "missed_defects",
        "unresolved_review_findings",
        "scope_violations",
        "failed_attempts",
        "fix_waves",
        "checks_run",
    ):
        result[field] = _number(value.get(field), f"quality.{field}", integer=True)
    context_reloads = value.get("context_reloads")
    result["context_reloads"] = (
        None
        if context_reloads is None
        else _number(context_reloads, "quality.context_reloads", integer=True)
    )
    return result


def _validate_session(value: object) -> dict:
    if not isinstance(value, dict):
        raise BenchmarkError("session must be a sanitized session_stats object")
    _reject_unknown_keys(value, SESSION_FIELDS, "session")
    _require_fields(value, SESSION_REQUIRED_FIELDS, "session")

    result: dict[str, object] = {
        "session_id": _label(value.get("session_id"), "session.session_id"),
        "agent": _label(value.get("agent"), "session.agent"),
        "model": _label(value.get("model"), "session.model"),
        "provider": _label(value.get("provider"), "session.provider"),
        "variant": _label(value.get("variant"), "session.variant"),
        "cli_version": _label(value.get("cli_version"), "session.cli_version"),
    }
    for field in (*CORE_EFFICIENCY_FIELDS, *OPTIONAL_EFFICIENCY_FIELDS):
        number = _optional_number(
            value,
            field,
            integer=field != "elapsed_seconds" and field != "cost_usd",
        )
        if number is not None:
            result[field] = number

    by_tool = value.get("tool_calls_by_tool")
    if not isinstance(by_tool, dict):
        raise BenchmarkError("session.tool_calls_by_tool must be an object")
    clean: dict[str, int] = {}
    for tool, count in by_tool.items():
        name = _label(tool, "tool name")
        clean[name] = int(_number(count, "tool count", integer=True))
    result["tool_calls_by_tool"] = dict(sorted(clean.items()))

    for field in ("model_turns", "tool_calls", "tool_errors", "patch_count"):
        if result.get(field) is None:
            raise BenchmarkError(f"session.{field} is required")

    tool_calls = int(result["tool_calls"])
    tool_errors = int(result["tool_errors"])
    if sum(clean.values()) != tool_calls:
        raise BenchmarkError("session tool counts do not sum to tool_calls")
    if tool_errors > tool_calls:
        raise BenchmarkError("session.tool_errors cannot exceed tool_calls")

    for field in ("started_utc", "ended_utc"):
        label = _optional_label(value, field)
        if label is not None:
            result[field] = label

    if value.get("compaction_count") is not None:
        raise BenchmarkError("session.compaction_count must remain unavailable")
    result["compaction_count"] = None
    return result


def validate_arm(doc: dict, expected_arm: str) -> dict:
    _reject_unknown_keys(doc, TOP_LEVEL_FIELDS, "benchmark arm")
    _require_fields(doc, TOP_LEVEL_FIELDS, "benchmark arm")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError(f"schema_version must be {SCHEMA_VERSION}")
    arm = _label(doc.get("arm"), "arm")
    if arm != expected_arm:
        raise BenchmarkError(f"arm must be {expected_arm}")
    identity = _validate_identity(doc.get("identity"))
    session = _validate_session(doc.get("session"))
    quality = _validate_quality(doc.get("quality"))
    return {
        "schema_version": SCHEMA_VERSION,
        "arm": arm,
        "identity": identity,
        "session": session,
        "quality": quality,
    }


def _direct_tool_counts(session: dict) -> dict[str, int]:
    by_tool = session["tool_calls_by_tool"]
    return {
        "direct_read_calls": sum(int(by_tool.get(name, 0)) for name in READ_TOOLS),
        "direct_search_calls": sum(int(by_tool.get(name, 0)) for name in SEARCH_TOOLS),
    }


def _quality_gate(quality: dict, required_evidence_class: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if quality["technical_outcome"] != "PASS":
        reasons.append("technical_outcome_not_pass")
    if quality["final_validation"] != "PASS":
        reasons.append("final_validation_not_pass")
    if quality["evidence_complete"] is not True:
        reasons.append("evidence_incomplete")
    if quality["evidence_loss"] is not False:
        reasons.append("evidence_loss")
    if quality["missed_defects"] != 0:
        reasons.append("missed_defects")
    if quality["unresolved_review_findings"] != 0:
        reasons.append("unresolved_review_findings")
    if quality["scope_violations"] != 0:
        reasons.append("scope_violations")
    if quality["evidence_class"] != required_evidence_class:
        reasons.append("evidence_class_mismatch")
    if quality["evidence_class"] not in BENCHMARK_EVIDENCE_CLASSES:
        reasons.append("insufficient_evidence_class")
    return ("PASS" if not reasons else "FAIL", reasons)


def _delta(baseline: int | float, candidate: int | float) -> dict:
    try:
        # A huge int against a float overflows in the subtraction itself.
        absolute = candidate - baseline
        percent = None if baseline == 0 else (absolute / baseline) * 100.0
    except ArithmeticError as exc:
        raise BenchmarkError("delta outside supported numeric range") from exc
    if isinstance(absolute, float) and not math.isfinite(absolute):
        raise BenchmarkError("delta outside supported numeric range")
    if isinstance(percent, float) and not math.isfinite(percent):
        raise BenchmarkError("delta outside supported numeric range")
    return {
        "baseline": baseline,
        "candidate": candidate,
        "absolute": absolute,
        "percent": None if percent is None else round(percent, 3),
        "change": "decreased" if absolute < 0 else "increased" if absolute > 0 else "unchanged",
    }


def _efficiency_direction(deltas: dict[str, dict]) -> tuple[list[str], list[str], list[str]]:
    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []
    for field in LOWER_IS_BETTER_FIELDS:
        delta = deltas.get(field)
        if delta is None:
            continue
        change = delta["change"]
        if change == "decreased":
            improved.append(field)
        elif change == "increased":
            regressed.append(field)
        else:
            unchanged.append(field)
    return improved, regressed, unchanged


def compare(baseline_doc: dict, candidate_doc: dict) -> dict:
    baseline = validate_arm(baseline_doc, "baseline")
    candidate = validate_arm(candidate_doc, "candidate")
    if baseline["identity"] != candidate["identity"]:
        raise BenchmarkError("A/B arms are not identity-equivalent")
    if baseline["session"]["session_id"] == candidate["session"]["session_id"]:
        raise BenchmarkError("A/B arms must come from distinct sessions")
    if baseline["session"]["cli_version"] != candidate["session"]["cli_version"]:
        raise BenchmarkError("A/B arms must use the same CLI version")

    required_evidence_class = baseline["identity"]["required_evidence_class"]
    baseline_quality, baseline_reasons = _quality_gate(baseline["quality"], required_evidence_class)
    candidate_quality, candidate_reasons = _quality_gate(
        candidate["quality"], required_evidence_class
    )

    deltas: dict[str, dict] = {}
    for field in (*CORE_EFFICIENCY_FIELDS, *OPTIONAL_EFFICIENCY_FIELDS):
        before = baseline["session"].get(field)
        after = candidate["session"].get(field)
        if before is not None and after is not None:
            deltas[field] = _delta(before, after)

    baseline_direct = _direct_tool_counts(baseline["session"])
    candidate_direct = _direct_tool_counts(candidate["session"])
    for field in ("direct_read_calls", "direct_search_calls"):
        deltas[field] = _delta(baseline_direct[field], candidate_direct[field])

    for field in ("failed_attempts", "fix_waves", "checks_run"):
        deltas[field] = _delta(baseline["quality"][field], candidate["quality"][field])
    if (
        baseline["quality"]["context_reloads"] is not None
        and candidate["quality"]["context_reloads"] is not None
    ):
        deltas["context_reloads"] = _delta(
            baseline["quality"]["context_reloads"],
            candidate["quality"]["context_reloads"],
        )

    comparable_core = [field for field in CORE_EFFICIENCY_FIELDS if field in deltas]
    quality_regression = candidate_quality != "PASS"
    if baseline_quality == "PASS":
        for field in (
            "missed_defects",
            "unresolved_review_findings",
            "scope_violations",
        ):
            if candidate["quality"][field] > baseline["quality"][field]:
                quality_regression = True
                candidate_reasons.append(f"regressed_{field}")
        if candidate["quality"]["checks_run"] < baseline["quality"]["checks_run"]:
            quality_regression = True
            candidate_reasons.append("verification_checks_reduced")

    improved, regressed, unchanged = _efficiency_direction(deltas)
    if baseline_quality != "PASS":
        disposition = "BASELINE_REJECT_QUALITY"
    elif quality_regression:
        disposition = "CANDIDATE_REJECT_QUALITY"
    elif len(comparable_core) < len(CORE_EFFICIENCY_FIELDS):
        disposition = "INCONCLUSIVE_MISSING_CORE_METRICS"
    elif regressed and improved:
        disposition = "PAIR_MEASURED_MIXED_EFFICIENCY"
    elif regressed:
        disposition = "PAIR_MEASURED_EFFICIENCY_REGRESSION"
    elif improved:
        disposition = "PAIR_MEASURED_EFFICIENCY_IMPROVEMENT"
    else:
        disposition = "PAIR_MEASURED_NO_EFFICIENCY_CHANGE"

    return {
        "schema_version": SCHEMA_VERSION,
        "identity": baseline["identity"],
        "baseline_arm": baseline["arm"],
        "candidate_arm": candidate["arm"],
        "baseline_session": baseline["session"],
        "candidate_session": candidate["session"],
        "baseline_quality_gate": baseline_quality,
        "baseline_quality_reasons": sorted(set(baseline_reasons)),
        "candidate_quality_gate": candidate_quality,
        "candidate_quality_reasons": sorted(set(candidate_reasons)),
        "efficiency_deltas": dict(sorted(deltas.items())),
        "efficiency_improved_fields": improved,
        "efficiency_regressed_fields": regressed,
        "efficiency_unchanged_fields": unchanged,
        "core_efficiency_fields_compared": comparable_core,
        "tool_output_volume": None,
        "tool_output_volume_status": "UNAVAILABLE_FROM_SANITIZED_SESSION_STATS",
        "default_promotion_authorized": False,
        "default_promotion_reason": (
            "single A/B pair is never sufficient for a default harness change"
        ),
        "disposition": disposition,
    }


def _atomic_write_new(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise BenchmarkError("output already exists; benchmark artifacts are write-once")

    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=".agent-benchmark-",
            delete=False,
        ) as stream:
            temporary = stream.name
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            stream.write("\n")
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise BenchmarkError(
                "output already exists; benchmark artifacts are write-once"
            ) from exc
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                Path(temporary).unlink(missing_ok=True)


def _exit_code(result: dict) -> int:
    if result["disposition"] in REJECT_DISPOSITIONS:
        return 3
    if result["disposition"] in INCONCLUSIVE_DISPOSITIONS:
        return 4
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare one sanitized Commander agent A/B pair.")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        result = compare(_load(args.baseline), _load(args.candidate))
    except BenchmarkError as exc:
        print(f"AGENT_BENCHMARK_REJECT: {exc}")
        return 2

    try:
        if args.output:
            _atomic_write_new(args.output, result)
        else:
            print(
                json.dumps(
                    result,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
            )
    except (ValueError, ArithmeticError) as exc:
        message = str(exc) if isinstance(exc, BenchmarkError) else "cannot serialize result"
        print(f"AGENT_BENCHMARK_REJECT: {message}")
        return 2
    except OSError:
        print("AGENT_BENCHMARK_REJECT: cannot publish output")
        return 2
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
