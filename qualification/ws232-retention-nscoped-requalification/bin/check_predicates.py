#!/usr/bin/env python3
"""WS232 predicate checker: evaluate every bind of every retention predicate
against the current tree. Emits RETENTION_PREDICATE_RESULTS.json.

STATIC_PASS requires every bind to match. Any STATIC_FAIL classifies impact
(rerun that evidence) instead of weakening the predicate. Behavior discharge
(current rerun pointers / UNKNOWN) is joined later by the disposition sealer;
this artifact records the static half plus the join contract.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"


def file_sha(path: str) -> str:
    return hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()


def resolve_value(path: str):
    """Resolve expected_value binds from the current tree."""
    if path == "config/rules_engines.json#primary_engine.commit":
        return json.loads((REPO_ROOT / "config/rules_engines.json").read_text())["primary_engine"][
            "commit"
        ]
    if path == "config/rules_engines.json#protocol_version":
        return json.loads((REPO_ROOT / "config/rules_engines.json").read_text())["protocol_version"]
    if path == "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json#seed":
        rows = json.loads(
            (REPO_ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json").read_text()
        )["fixtures"]
        seeds = {r.get("seed") for r in rows}
        return seeds.pop() if len(seeds) == 1 else sorted(seeds)
    if path.endswith("#TAPE_SCHEMA_VERSION"):
        import re

        src = (REPO_ROOT / "src/commander_lab/semantic_replay/tape.py").read_text()
        m = re.search(r'TAPE_SCHEMA_VERSION(?::\s*Final)?\s*=\s*"([^"]+)"', src)
        return m.group(1) if m else None
    if path.endswith("#rules-seed-binding"):
        sess = (
            REPO_ROOT
            / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java"
        ).read_text()
        ok = (
            "setRulesSeed" in sess
            and "setRequireExplicitSeed(true)" in sess
            and "getRulesRandomCalls" in sess
        )
        return (
            "setRulesSeed+setRequireExplicitSeed(true)+getRulesRandomCalls"
            if ok
            else "MISSING_BINDING"
        )
    if ".card_identity" in path:
        fid = path.split("#")[1].split(".")[0]
        rows = json.loads(
            (REPO_ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json").read_text()
        )["fixtures"]
        return next(r.get("card_identity") for r in rows if r["fixture_id"] == fid)
    raise AssertionError(path)


def main() -> int:
    preds = json.loads((NS / "RETENTION_PREDICATES.json").read_text())
    manifest = json.loads(
        (REPO_ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json").read_text()
    )
    manifest_rows = {f["fixture_id"]: f for f in manifest["fixtures"]}

    results = []
    for p in preds["predicates"]:
        bind_results = []
        for b in p["binds"]:
            kind, path = b["kind"], b["path"]
            if kind in (
                "path_blob_sha256",
                "fixture_bytes_sha256",
                "card_domain_entry",
                "rules_authority",
                "provider_identity",
            ):
                if "#" in path and kind == "fixture_bytes_sha256":
                    fid = path.split("#")[1]
                    canon = json.dumps(
                        manifest_rows[fid], sort_keys=True, separators=(",", ":")
                    ).encode()
                    actual = hashlib.sha256(canon).hexdigest()
                else:
                    actual = file_sha(path)
                match = actual == b["expected_sha256"]
                bind_results.append(
                    {
                        "path": path,
                        "kind": kind,
                        "match": match,
                        "actual_sha256": actual,
                        "expected_sha256": b["expected_sha256"],
                    }
                )
            else:
                actual = resolve_value(path)
                match = actual == b["expected_value"]
                bind_results.append(
                    {
                        "path": path,
                        "kind": kind,
                        "match": match,
                        "actual_value": actual,
                        "expected_value": b["expected_value"],
                    }
                )
        static_pass = all(r["match"] for r in bind_results)
        results.append(
            {
                "predicate_id": p["predicate_id"],
                "fixture_id": p["fixture_id"],
                "category": p["category"],
                "static_verdict": "STATIC_PASS" if static_pass else "STATIC_FAIL",
                "bind_results": bind_results,
                "behavior_discharge": "PENDING_N_SCOPED_RERUN_JOIN",
                "n_scoped_rerun_required": p["n_scoped_rerun_required"],
            }
        )

    npass = sum(1 for r in results if r["static_verdict"] == "STATIC_PASS")
    out = {
        "schema_version": "ws232-retention-predicate-results-1.0.0",
        "evaluated_predicates": len(results),
        "static_pass": npass,
        "static_fail": len(results) - npass,
        "impact_rule": "any STATIC_FAIL => rerun that fixture's evidence; never weaken the predicate",
        "results": results,
    }
    (NS / "RETENTION_PREDICATE_RESULTS.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n"
    )
    print(f"evaluated={len(results)} static_pass={npass} static_fail={len(results) - npass}")
    for r in results:
        if r["static_verdict"] != "STATIC_PASS":
            print("FAIL:", r["predicate_id"], [b for b in r["bind_results"] if not b["match"]])
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
