#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator

VERDICTS = {"PASS", "FAIL", "UNKNOWN", "NOT_RUN", "PARTIAL", "UNSUPPORTED", "NOT_APPLICABLE"}
SATISFYING = {"PASS"}
ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def validate(instance, schema):
    Draft202012Validator(schema).validate(instance)


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
        req = {
            "protocol": manifest["protocol"],
            "message_type": "RUN_FIXTURE",
            "request_id": "ws17-" + fx["fixture_id"],
            "session_id": None,
            "actor_id": fx.get("actor_id"),
            "state_revision": None,
            "payload": {
                "fixture": fx,
                "authority_lock_sha256": manifest["authority_lock_sha256"],
                "denominator_hashes": manifest["denominator_hashes"],
            },
        }
        resp, err = run_provider(command, req)
        if err:
            r = normalize_missing(candidate, source_lock, fx, err, "RUNTIME_NOT_RUN")
            results.append(r)
            continue
        payload = resp.get("payload", {}) if isinstance(resp, dict) else {}
        verdict = payload.get("verdict", "UNKNOWN")
        if verdict not in VERDICTS:
            verdict = "UNKNOWN"
        results.append(
            {
                "fixture_id": fx["fixture_id"],
                "candidate": candidate,
                "source_lock": source_lock,
                "verdict": verdict,
                "evidence_class": payload.get(
                    "evidence_class",
                    "RUNTIME_VERIFIED" if verdict in {"PASS", "FAIL"} else "NOT_RUN",
                ),
                "reason": payload.get("reason", "provider response"),
                "classification": "RUNTIME_PASS"
                if verdict == "PASS"
                else (
                    "RUNTIME_NOT_RUN" if verdict in {"NOT_RUN", "UNKNOWN"} else "DIRECT_RULES_FAIL"
                ),
                "artifact_hashes": payload.get("artifact_hashes", {}),
            }
        )
    return results


def aggregate(results, required_fixture_ids):
    by = {r["fixture_id"]: r for r in results}
    missing = [fid for fid in required_fixture_ids if fid not in by]
    bad = [r for fid, r in by.items() if fid in required_fixture_ids and r.get("verdict") != "PASS"]
    admission = "PASS" if not missing and not bad else "FAIL"
    return {
        "production_admission": admission,
        "required_fixture_count": len(required_fixture_ids),
        "pass_count": sum(
            1 for fid in required_fixture_ids if by.get(fid, {}).get("verdict") == "PASS"
        ),
        "missing_fixture_ids": missing,
        "blocking_results": [
            {"fixture_id": r["fixture_id"], "verdict": r["verdict"], "reason": r.get("reason", "")}
            for r in bad
        ],
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
                rr["fixture_results"], [x["fixture_id"] for x in m["fixtures"] if x["mandatory"]]
            )
            out.update({"admitted_main_sha": args.admitted_main_sha, "actual_sha": args.actual_sha})
        dump(args.output, out)
        if args.md_output:
            Path(args.md_output).write_text(render_md(args.output), encoding="utf-8")


if __name__ == "__main__":
    main()
