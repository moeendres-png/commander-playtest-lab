#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

VERDICTS = {"PASS", "FAIL", "UNKNOWN", "NOT_RUN", "PARTIAL", "UNSUPPORTED", "NOT_APPLICABLE"}
SATISFYING = {"PASS"}
ROOT = Path(__file__).resolve().parents[1]
RSP_ENVELOPE_SCHEMA = ROOT / "qualification/protocol/ws10r/rules_service_protocol_v1.schema.json"
RSP_SEMANTICS_SCHEMA = ROOT / "qualification/protocol/ws10r/rsp_semantics_v1.schema.json"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical_sha256(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate(instance, schema):
    Draft202012Validator(schema).validate(instance)


def _schema_problem(instance, schema):
    errors = list(Draft202012Validator(schema).iter_errors(instance))
    if not errors:
        return None
    error = sorted(errors, key=lambda item: tuple(str(part) for part in item.absolute_path))[0]
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"schema_validation_failed:path={path}:rule={error.validator}"


def _fixture_result_schema():
    semantics = load(RSP_SEMANTICS_SCHEMA)
    return {
        "$schema": semantics["$schema"],
        "$defs": semantics["$defs"],
        "$ref": "#/$defs/fixtureResult",
    }


def run_provider(command, request, timeout=120):
    cp = subprocess.run(
        command,
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=True,
    )
    if cp.returncode != 0:
        return None, f"provider_exit_{cp.returncode}: {cp.stderr.strip()}"
    lines = [x for x in cp.stdout.splitlines() if x.strip()]
    if not lines:
        return None, "provider_empty_output"
    try:
        return json.loads(lines[-1]), None
    except Exception as e:
        return None, f"provider_invalid_json:{e}"


def normalize_missing(
    candidate, source_lock, fixture, reason, classification="PROTOCOL_ADAPTER_MISSING"
):
    return {
        "fixture_id": fixture["fixture_id"],
        "candidate": candidate,
        "source_lock": source_lock,
        "verdict": "NOT_RUN",
        "evidence_class": "NOT_RUN",
        "reason": reason,
        "classification": classification,
        "artifact_hashes": {},
    }


def normalize_invalid_provider(candidate, source_lock, fixture, reason):
    return {
        "fixture_id": fixture["fixture_id"],
        "candidate": candidate,
        "source_lock": source_lock,
        "verdict": "FAIL",
        "evidence_class": "NOT_RUN",
        "reason": f"provider_response_invalid:{reason}",
        "classification": "QUALIFICATION_INFRASTRUCTURE_MISSING",
        "artifact_hashes": {},
    }


def _qualification_binding(candidate, source_lock, manifest, fixture):
    candidate_locks = source_lock.get("candidate_locks")
    if not isinstance(candidate_locks, dict):
        raise ValueError("source_lock_candidate_locks_missing")
    provider_lock = candidate_locks.get(candidate)
    if not isinstance(provider_lock, dict):
        raise ValueError(f"candidate_not_bound_in_source_lock:{candidate}")
    for required in ("repository", "commit"):
        value = provider_lock.get(required)
        if not isinstance(value, str) or not value:
            raise ValueError(f"provider_lock_missing_{required}")
    core = {
        "candidate": candidate,
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": canonical_sha256(fixture),
        "source_lock_sha256": canonical_sha256(source_lock),
        "authority_lock_sha256": manifest["authority_lock_sha256"],
        "denominator_hashes": manifest["denominator_hashes"],
        "provider_lock": provider_lock,
    }
    return {
        **core,
        "binding_sha256": canonical_sha256(core),
    }


def _validate_provider_identity(provider_identity, candidate, source_lock, binding):
    if not isinstance(provider_identity, dict):
        return "provider_identity_missing_or_invalid"
    provider_lock = source_lock["candidate_locks"][candidate]
    expected = {
        "candidate": candidate,
        "repository": provider_lock["repository"],
        "commit": provider_lock["commit"],
        "source_lock_sha256": canonical_sha256(source_lock),
        "qualification_binding_sha256": binding["binding_sha256"],
    }
    for optional in ("tree", "version"):
        if optional in provider_lock:
            expected[optional] = provider_lock[optional]
    for key, value in expected.items():
        if provider_identity.get(key) != value:
            return f"provider_identity_mismatch:{key}"
    return None


def _validate_artifact_provenance(payload, binding):
    artifact_hashes = payload.get("artifact_hashes")
    if not isinstance(artifact_hashes, dict):
        return "artifact_hashes_missing_or_invalid"
    required = {"fixture_result_sha256", "qualification_binding_sha256"}
    missing = sorted(required - set(artifact_hashes))
    if missing:
        return "artifact_hashes_missing:" + ",".join(missing)
    if artifact_hashes["qualification_binding_sha256"] != binding["binding_sha256"]:
        return "artifact_binding_hash_mismatch"
    result_payload = {key: value for key, value in payload.items() if key != "artifact_hashes"}
    if artifact_hashes["fixture_result_sha256"] != canonical_sha256(result_payload):
        return "fixture_result_hash_mismatch"
    return None


def _validated_provider_result(candidate, source_lock, manifest, fixture, request, response):
    envelope_problem = _schema_problem(response, load(RSP_ENVELOPE_SCHEMA))
    if envelope_problem:
        return None, envelope_problem
    if response.get("protocol") != request["protocol"]:
        return None, "protocol_mismatch"
    if response.get("message_type") != "FIXTURE_RESULT":
        return None, "message_type_mismatch"
    if response.get("request_id") != request["request_id"]:
        return None, "request_id_mismatch"
    if "session_id" not in response or response.get("session_id") != request.get("session_id"):
        return None, "session_id_mismatch"

    payload = response.get("payload")
    fixture_problem = _schema_problem(payload, _fixture_result_schema())
    if fixture_problem:
        return None, fixture_problem
    if payload["fixture_id"] != fixture["fixture_id"]:
        return None, "fixture_id_mismatch"

    try:
        binding = _qualification_binding(candidate, source_lock, manifest, fixture)
    except ValueError as exc:
        return None, str(exc)

    identity_problem = _validate_provider_identity(
        payload["provider_identity"], candidate, source_lock, binding
    )
    if identity_problem:
        return None, identity_problem

    verdict = payload["verdict"]
    evidence_class = payload["evidence_class"]
    if verdict == "PASS":
        expected_class = fixture.get("expected_evidence_class")
        if evidence_class != "RUNTIME_VERIFIED" or evidence_class != expected_class:
            return None, "pass_requires_explicit_expected_runtime_evidence_class"

    provenance_problem = _validate_artifact_provenance(payload, binding)
    if provenance_problem:
        return None, provenance_problem

    return payload, None


def execute(candidate, source_lock, manifest, command=None):
    results = []
    for fx in manifest["fixtures"]:
        if not command:
            results.append(
                normalize_missing(
                    candidate,
                    source_lock,
                    fx,
                    "No common RSP 1.1 adapter command configured; required runtime not executed.",
                )
            )
            continue

        try:
            binding = _qualification_binding(candidate, source_lock, manifest, fx)
        except ValueError as exc:
            results.append(normalize_invalid_provider(candidate, source_lock, fx, str(exc)))
            continue

        req = {
            "protocol": manifest["protocol"],
            "message_type": "RUN_FIXTURE",
            "request_id": "ws17-" + fx["fixture_id"] + "-" + uuid.uuid4().hex,
            "session_id": None,
            "actor_id": fx.get("actor_id"),
            "state_revision": None,
            "payload": {
                "fixture": fx,
                "authority_lock_sha256": manifest["authority_lock_sha256"],
                "denominator_hashes": manifest["denominator_hashes"],
                "qualification_binding": binding,
            },
        }
        resp, err = run_provider(command, req)
        if err:
            results.append(
                normalize_missing(candidate, source_lock, fx, err, "RUNTIME_NOT_RUN")
            )
            continue

        payload, validation_error = _validated_provider_result(
            candidate, source_lock, manifest, fx, req, resp
        )
        if validation_error:
            results.append(
                normalize_invalid_provider(candidate, source_lock, fx, validation_error)
            )
            continue

        verdict = payload["verdict"]
        results.append(
            {
                "fixture_id": payload["fixture_id"],
                "candidate": candidate,
                "source_lock": source_lock,
                "verdict": verdict,
                "evidence_class": payload["evidence_class"],
                "reason": payload.get("reason", "provider response"),
                "classification": (
                    "RUNTIME_PASS"
                    if verdict == "PASS"
                    else (
                        "RUNTIME_NOT_RUN"
                        if verdict in {"NOT_RUN", "UNKNOWN"}
                        else "DIRECT_RULES_FAIL"
                    )
                ),
                "artifact_hashes": payload["artifact_hashes"],
            }
        )
    return results


def aggregate(results, required_fixture_ids):
    well_formed = [
        r
        for r in results
        if isinstance(r, dict) and isinstance(r.get("fixture_id"), str) and r["fixture_id"]
    ]
    malformed_count = len(results) - len(well_formed)
    counts = Counter(r["fixture_id"] for r in well_formed)
    duplicate_fixture_ids = sorted(fid for fid, count in counts.items() if count > 1)

    by = {r["fixture_id"]: r for r in well_formed if counts[r["fixture_id"]] == 1}
    present_ids = set(counts)
    missing = [fid for fid in required_fixture_ids if fid not in present_ids]
    bad = [
        by[fid]
        for fid in required_fixture_ids
        if fid in by and by[fid].get("verdict") != "PASS"
    ]

    blocking_results = [
        {
            "fixture_id": r["fixture_id"],
            "verdict": r["verdict"],
            "reason": r.get("reason", ""),
        }
        for r in bad
    ]
    blocking_results.extend(
        {
            "fixture_id": fid,
            "verdict": "FAIL",
            "reason": "duplicate fixture result; qualification credit is ambiguous",
        }
        for fid in duplicate_fixture_ids
    )
    if malformed_count:
        blocking_results.append(
            {
                "fixture_id": "MALFORMED_RESULT",
                "verdict": "FAIL",
                "reason": f"{malformed_count} result(s) missing a valid fixture_id",
            }
        )

    admission = (
        "PASS"
        if not missing and not bad and not duplicate_fixture_ids and malformed_count == 0
        else "FAIL"
    )
    return {
        "production_admission": admission,
        "required_fixture_count": len(required_fixture_ids),
        "pass_count": sum(
            1
            for fid in required_fixture_ids
            if fid in by and by[fid].get("verdict") == "PASS"
        ),
        "missing_fixture_ids": missing,
        "duplicate_fixture_ids": duplicate_fixture_ids,
        "blocking_results": blocking_results,
    }


def render_md(admission_json):
    d = load(admission_json)
    lines = [
        "# PRODUCTION ADMISSION",
        "",
        f"**Verdict:** `{d['production_admission']}`",
        "",
        f"Exact admitted SHA: `{d.get('admitted_main_sha')}`",
        "",
        f"Required fixtures: {d.get('required_fixture_count', 0)}",
        f"PASS fixtures: {d.get('pass_count', 0)}",
        "",
        "> This file is generated from `PRODUCTION_ADMISSION.json`; do not maintain it independently.",
        "",
    ]
    if d.get("blocking_results"):
        lines += ["## Blocking results", ""] + [
            f"- `{x['fixture_id']}` — `{x['verdict']}` — {x.get('reason', '')}"
            for x in d["blocking_results"][:80]
        ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("instance")
    v.add_argument("schema")
    r = sub.add_parser("run")
    r.add_argument("--candidate", required=True)
    r.add_argument("--source-lock", required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--command")
    r.add_argument("--output", required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("--manifest", required=True)
    a.add_argument("--results", required=True)
    a.add_argument("--admitted-main-sha", required=True)
    a.add_argument("--actual-sha", required=True)
    a.add_argument("--output", required=True)
    a.add_argument("--md-output")
    args = ap.parse_args()
    if args.cmd == "validate":
        validate(load(args.instance), load(args.schema))
        print("PASS")
        return
    if args.cmd == "run":
        manifest = load(args.manifest)
        lock = load(args.source_lock)
        out = execute(args.candidate, lock, manifest, args.command)
        dump(args.output, {"candidate": args.candidate, "fixture_results": out})
        return
    if args.cmd == "aggregate":
        if args.admitted_main_sha != args.actual_sha:
            out = {
                "production_admission": "FAIL",
                "admitted_main_sha": args.admitted_main_sha,
                "actual_sha": args.actual_sha,
                "required_fixture_count": len(load(args.manifest)["fixtures"]),
                "pass_count": 0,
                "blocking_results": [
                    {
                        "fixture_id": "EXACT_MAIN_SHA",
                        "verdict": "FAIL",
                        "reason": "Run SHA does not equal admitted main SHA",
                    }
                ],
            }
        else:
            m = load(args.manifest)
            rr = load(args.results)
            out = aggregate(
                rr["fixture_results"],
                [x["fixture_id"] for x in m["fixtures"] if x["mandatory"]],
            )
            out.update(
                {
                    "admitted_main_sha": args.admitted_main_sha,
                    "actual_sha": args.actual_sha,
                }
            )
        dump(args.output, out)
        if args.md_output:
            Path(args.md_output).write_text(render_md(args.output), encoding="utf-8")


if __name__ == "__main__":
    main()
