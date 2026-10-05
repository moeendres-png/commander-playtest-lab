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
    "model_turns",
    "patch_count",
)

READ_TOOLS = {"read", "list"}
SEARCH_TOOLS = {"grep", "glob", "lsp"}


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
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        BenchmarkError,
        RecursionError,
    ) as exc:
        raise BenchmarkError("cannot read valid benchmark JSON") from exc
    if not isinstance(data, dict):
        raise BenchmarkError("benchmark arm must be a JSON object")
    return data


def _label(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or any(ord(char) < 32 for char in value)
    ):
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


def _optional_number(
    mapping: dict, field: str, *, integer: bool = False
) -> int | float | None:
    value = mapping.get(field)
    if value is None:
        return None
    return _number(value, field, integer=integer)


def _validate_identity(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise BenchmarkError("identity must be an object")
    required = (
        "case_id",
        "task_class",
        "source_sha",
        "fixture_digest",
        "required_evidence_class",
    )
    result = {key: _label(value.get(key), f"identity.{key}") for key in required}
    if len(result["source_sha"]) != 40 or any(
        char not in "0123456789abcdefABCDEF" for char in result["source_sha"]
    ):
        raise BenchmarkError("identity.source_sha must be a full 40-hex SHA")
    if len(result["fixture_digest"]) != 64 or any(
        char not in "0123456789abcdefABCDEF" for char in result["fixture_digest"]
    ):
        raise BenchmarkError("identity.fixture_digest must be a 64-hex digest")
    if result["required_evidence_class"] not in EVIDENCE_CLASSES:
        raise BenchmarkError("unsupported identity.required_evidence_class")
    return result


def _validate_quality(value: object) -> dict:
    if not isinstance(value, dict):
        raise BenchmarkError("quality must be an object")
    result = {
        "technical_outcome": _label(
            value.get("technical_outcome"), "quality.technical_outcome"
        ),
        "final_validation": _label(
            value.get("final_validation"), "quality.final_validation"
        ),
        "evidence_class": _label(
            value.get("evidence_class"), "quality.evidence_class"
        ),
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
    result: dict[str, object] = {}
    for field in (*CORE_EFFICIENCY_FIELDS, *OPTIONAL_EFFICIENCY_FIELDS):
        number = _optional_number(
            value, field, integer=field != "elapsed_seconds"
        )
        if number is not None:
            result[field] = number
    by_tool = value.get("tool_calls_by_tool")
    if by_tool is not None:
        if not isinstance(by_tool, dict):
            raise BenchmarkError("session.tool_calls_by_tool must be an object")
        clean: dict[str, int] = {}
        for tool, count in by_tool.items():
            name = _label(tool, "tool name")
            clean[name] = int(
                _number(count, f"tool count for {name}", integer=True)
            )
        result["tool_calls_by_tool"] = dict(sorted(clean.items()))
    for field in ("model", "variant", "agent", "cli_version"):
        if value.get(field) is not None:
            result[field] = _label(value[field], f"session.{field}")
    return result


def validate_arm(doc: dict) -> dict:
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError(f"schema_version must be {SCHEMA_VERSION}")
    arm = _label(doc.get("arm"), "arm")
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


def _direct_tool_counts(session: dict) -> dict[str, int] | None:
    by_tool = session.get("tool_calls_by_tool")
    if not isinstance(by_tool, dict):
        return None
    return {
        "direct_read_calls": sum(
            int(by_tool.get(name, 0)) for name in READ_TOOLS
        ),
        "direct_search_calls": sum(
            int(by_tool.get(name, 0)) for name in SEARCH_TOOLS
        ),
    }


def _quality_gate(
    quality: dict, required_evidence_class: str
) -> tuple[str, list[str]]:
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
    if quality["evidence_class"] in {"UNKNOWN", "MODELED", "SYNTHETIC"}:
        reasons.append("insufficient_evidence_class")
    return ("PASS" if not reasons else "FAIL", reasons)


def _delta(baseline: int | float, candidate: int | float) -> dict:
    absolute = candidate - baseline
    percent = None if baseline == 0 else (absolute / baseline) * 100.0
    return {
        "baseline": baseline,
        "candidate": candidate,
        "absolute": absolute,
        "percent": None if percent is None else round(percent, 3),
    }


def compare(baseline_doc: dict, candidate_doc: dict) -> dict:
    baseline = validate_arm(baseline_doc)
    candidate = validate_arm(candidate_doc)
    if baseline["identity"] != candidate["identity"]:
        raise BenchmarkError("A/B arms are not identity-equivalent")

    required_evidence_class = baseline["identity"]["required_evidence_class"]
    baseline_quality, baseline_reasons = _quality_gate(
        baseline["quality"], required_evidence_class
    )
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
    if baseline_direct is not None and candidate_direct is not None:
        for field in ("direct_read_calls", "direct_search_calls"):
            deltas[field] = _delta(
                baseline_direct[field], candidate_direct[field]
            )

    for field in ("failed_attempts", "fix_waves", "checks_run"):
        deltas[field] = _delta(
            baseline["quality"][field], candidate["quality"][field]
        )
    if (
        baseline["quality"]["context_reloads"] is not None
        and candidate["quality"]["context_reloads"] is not None
    ):
        deltas["context_reloads"] = _delta(
            baseline["quality"]["context_reloads"],
            candidate["quality"]["context_reloads"],
        )

    comparable_core = [
        field for field in CORE_EFFICIENCY_FIELDS if field in deltas
    ]
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

    if quality_regression:
        disposition = "CANDIDATE_REJECT_QUALITY"
    elif len(comparable_core) < len(CORE_EFFICIENCY_FIELDS):
        disposition = "INCONCLUSIVE_MISSING_CORE_METRICS"
    else:
        disposition = "PAIR_MEASURED_QUALITY_PRESERVED"

    return {
        "schema_version": SCHEMA_VERSION,
        "identity": baseline["identity"],
        "baseline_arm": baseline["arm"],
        "candidate_arm": candidate["arm"],
        "baseline_quality_gate": baseline_quality,
        "baseline_quality_reasons": sorted(set(baseline_reasons)),
        "candidate_quality_gate": candidate_quality,
        "candidate_quality_reasons": sorted(set(candidate_reasons)),
        "efficiency_deltas": dict(sorted(deltas.items())),
        "core_efficiency_fields_compared": comparable_core,
        "tool_output_volume": None,
        "tool_output_volume_status": (
            "UNAVAILABLE_FROM_SANITIZED_SESSION_STATS"
        ),
        "default_promotion_authorized": False,
        "default_promotion_reason": (
            "single A/B pair is never sufficient for a default harness change"
        ),
        "disposition": disposition,
    }


def _atomic_write(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
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
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                Path(temporary).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare one sanitized Commander agent A/B pair."
    )
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        result = compare(_load(args.baseline), _load(args.candidate))
    except BenchmarkError as exc:
        print(f"AGENT_BENCHMARK_REJECT: {exc}")
        return 2
    if args.output:
        try:
            _atomic_write(args.output, result)
        except OSError:
            print("AGENT_BENCHMARK_REJECT: cannot publish output")
            return 2
    else:
        print(
            json.dumps(
                result,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
