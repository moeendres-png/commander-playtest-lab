#!/usr/bin/env python3
"""Fresh v1.0.3 -> v1.0.4 record/digest/repair reconciliation for WS-46."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from successor_contract_v104 import (
    CANONICAL_MATERIALIZATION_DIGEST,
    CONTRACT_VERSION,
    MATERIALIZATION_FILE_SHA256,
    canonical_sha,
    load_contract,
    provider_records,
    record_digest,
    requested_state_digest,
)

V103_VERSION = "commander-lab.semantic-fixture-materialization/1.0.3"
V103_BUNDLE = "545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b"
V103_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"
DERIVED_RECORD_FIELDS = {
    "materialization_digest",
    "requested_state_digest",
    "materialization_version",
    "repair_provenance",
}


def load_v103(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != V103_SHA256:
        raise SystemExit(f"WS46_V103_SHA_MISMATCH:{actual}")
    value = json.loads(raw)
    if value.get("schema_version") != V103_VERSION or value.get("canonical_bundle_digest") != V103_BUNDLE:
        raise SystemExit("WS46_V103_IDENTITY_MISMATCH")
    if len(value.get("records") or []) != 135:
        raise SystemExit("WS46_V103_RECORD_COUNT_MISMATCH")
    for r in value["records"]:
        if r.get("materialization_digest") != record_digest(r):
            raise SystemExit(f"WS46_V103_RECORD_DIGEST_MISMATCH:{r.get('fixture_id')}")
        if r.get("requested_state_digest") != requested_state_digest(r):
            raise SystemExit(f"WS46_V103_REQUESTED_STATE_DIGEST_MISMATCH:{r.get('fixture_id')}")
    return value


def without_derived(record: dict[str, Any]) -> dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in record.items() if k not in DERIVED_RECORD_FIELDS}


def diff_paths(a: Any, b: Any, path: str = "$") -> list[str]:
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict):
        out: list[str] = []
        for key in sorted(set(a) | set(b)):
            child = f"{path}.{key}"
            if key not in a or key not in b:
                out.append(child)
            else:
                out.extend(diff_paths(a[key], b[key], child))
        return out
    if isinstance(a, list):
        out = []
        for i in range(max(len(a), len(b))):
            child = f"{path}[{i}]"
            if i >= len(a) or i >= len(b):
                out.append(child)
            else:
                out.extend(diff_paths(a[i], b[i], child))
        return out
    return [] if a == b else [path]


def path_tokens(path: str) -> list[Any]:
    p = path[2:] if path.startswith("$.") else path
    tokens: list[Any] = []
    for part in p.split("."):
        if not part:
            continue
        m = re.match(r"^([^\[]+)", part)
        if m:
            tokens.append(m.group(1))
        for idx in re.findall(r"\[(\d+)\]", part):
            tokens.append(int(idx))
    return tokens


def get_path(value: Any, path: str) -> Any:
    cur = value
    for token in path_tokens(path):
        cur = cur[token]
    return cur


def _relative_dotted_value(actual: dict[str, Any], key: str) -> tuple[bool, Any]:
    """Resolve a frozen repair-matrix dotted relative key exactly.

    Literal dictionary keys take precedence.  Otherwise every dotted segment
    must exist as a nested mapping key; no fuzzy, case-folded, alias or provider
    lookup is performed.
    """
    if key in actual:
        return True, actual[key]
    if "." not in key:
        return False, None
    cur: Any = actual
    for segment in key.split("."):
        if not isinstance(cur, dict) or segment not in cur:
            return False, None
        cur = cur[segment]
    return True, cur


def contains_subset(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, expected_value in expected.items():
            found, actual_value = _relative_dotted_value(actual, key)
            if not found or not contains_subset(actual_value, expected_value):
                return False
        return True
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


def recursive_contains(value: Any, needle: Any) -> bool:
    if value == needle:
        return True
    if isinstance(value, dict):
        return any(recursive_contains(v, needle) for v in value.values())
    if isinstance(value, list):
        return any(recursive_contains(v, needle) for v in value)
    return False


def record_local_identity_representation_bound(value: Any, semantic_id: Any, path: str) -> bool:
    """Bind exactly the immutable WS-44 record-local identity rewrite forms."""
    if recursive_contains(value, semantic_id):
        return True
    if not path.endswith(".card_lineage_id"):
        return False
    return isinstance(value, str) and isinstance(semantic_id, str) and value == f"line:{semantic_id}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--v103", type=Path, required=True)
    p.add_argument("--v104", type=Path, required=True)
    p.add_argument("--repair-matrix", type=Path, required=True)
    p.add_argument("--target-adjudication", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    old = load_v103(args.v103)
    new = load_contract(args.v104)
    old_by = {r["fixture_id"]: r for r in old["records"]}
    new_by = {r["fixture_id"]: r for r in new["records"]}
    if set(old_by) != set(new_by):
        raise SystemExit("WS46_V103_V104_FIXTURE_ID_SET_MISMATCH")

    changed: list[dict[str, Any]] = []
    for fid in [r["fixture_id"] for r in new["records"]]:
        paths = diff_paths(without_derived(old_by[fid]), without_derived(new_by[fid]))
        if paths:
            changed.append({"fixture_id": fid, "changed_paths": paths})

    derived_provider_ids = {r["fixture_id"] for r in provider_records(new)}
    changed_ids = {r["fixture_id"] for r in changed}
    changed_provider = [r for r in changed if r["fixture_id"] in derived_provider_ids]

    repair_raw = args.repair_matrix.read_bytes()
    repair = json.loads(repair_raw)
    if repair.get("obligation_changed") is not False:
        raise SystemExit("WS46_REPAIR_MATRIX_OBLIGATION_CHANGED")
    rows = repair.get("rows") or []
    if repair.get("repair_count") != len(rows):
        raise SystemExit("WS46_REPAIR_MATRIX_COUNT_MISMATCH")
    repair_fixtures = {r["fixture_id"] for r in rows}
    if repair.get("changed_fixture_count") != len(repair_fixtures):
        raise SystemExit("WS46_REPAIR_MATRIX_FIXTURE_COUNT_MISMATCH")
    if repair_fixtures != changed_ids:
        raise SystemExit(f"WS46_REPAIR_MATRIX_ACTUAL_DELTA_SET_MISMATCH:matrix={sorted(repair_fixtures)}:actual={sorted(changed_ids)}")

    verified_repairs = []
    for row in rows:
        if row.get("provider_semantics_used") is not False or row.get("obligation_changed") is not False:
            raise SystemExit(f"WS46_REPAIR_NOT_PROVIDER_NEUTRAL:{row.get('fixture_id')}")
        fid = row["fixture_id"]
        before, after = old_by[fid], new_by[fid]
        if "path" in row:
            ov = get_path(before, row["path"])
            nv = get_path(after, row["path"])
            if not contains_subset(ov, row["old"]) or not contains_subset(nv, row["new"]):
                raise SystemExit(f"WS46_REPAIR_PATH_VALUE_MISMATCH:{fid}:{row['path']}")
            verified_paths = ["$." + row["path"]]
        else:
            verified_paths = row.get("changed_representation_paths") or []
            if not verified_paths:
                raise SystemExit(f"WS46_REPAIR_HAS_NO_PATHS:{fid}")
            for path in verified_paths:
                ov, nv = get_path(before, path), get_path(after, path)
                if ov == nv:
                    raise SystemExit(f"WS46_REPAIR_DECLARED_PATH_NOT_CHANGED:{fid}:{path}")
                if row.get("repair_kind") == "RECORD_LOCAL_IDENTITY_RENAME":
                    old_bound = record_local_identity_representation_bound(ov, row["old"], path)
                    new_bound = record_local_identity_representation_bound(nv, row["new"], path)
                else:
                    old_bound = recursive_contains(ov, row["old"]) or ov == row["old"]
                    new_bound = recursive_contains(nv, row["new"]) or nv == row["new"]
                if not old_bound:
                    raise SystemExit(f"WS46_REPAIR_OLD_NOT_BOUND:{fid}:{path}")
                if not new_bound:
                    raise SystemExit(f"WS46_REPAIR_NEW_NOT_BOUND:{fid}:{path}")
        verified_repairs.append({"fixture_id": fid, "repair_kind": row["repair_kind"], "verified_paths": verified_paths})

    target_raw = args.target_adjudication.read_bytes()
    target = json.loads(target_raw)
    if target.get("terminal_status") != "PASS" or target.get("authority_resolution") != "PROVEN_PROVIDER_NEUTRALLY":
        raise SystemExit("WS46_MICRO_TARGET_ADJUDICATION_NOT_PASS")
    target_checks = []
    for row in target.get("rows") or []:
        if row.get("provider_semantics_used") is not False:
            raise SystemExit("WS46_MICRO_TARGET_PROVIDER_HEURISTIC_PRESENT")
        fid = row["fixture_id"]
        record = new_by[fid]
        exact = row["intended_target"]
        dangling = row["dangling_requested_target"]
        stack_target = get_path(record, "stack_state[0].targets[0]")
        if stack_target != exact:
            raise SystemExit(f"WS46_MICRO_TARGET_STACK_MISMATCH:{fid}:{stack_target}:{exact}")
        if not recursive_contains(record.get("decision_script"), row["decision_script_exact_target"]):
            raise SystemExit(f"WS46_MICRO_TARGET_DECISION_NOT_EXACT:{fid}")
        if not recursive_contains(record.get("native_procedure"), row["native_procedure_exact_target"]):
            raise SystemExit(f"WS46_MICRO_TARGET_PROCEDURE_NOT_EXACT:{fid}")
        semantic_ids = {o.get("semantic_id") for o in (record.get("semantic_objects") or [])}
        plausible_ids = {ref.get("semantic_id") for ref in (row.get("plausible_referents") or [])}
        if exact not in semantic_ids or exact not in plausible_ids or not plausible_ids.issubset(semantic_ids):
            raise SystemExit(f"WS46_MICRO_TARGET_REFERENT_SET_INCOMPLETE:{fid}")
        if dangling in semantic_ids:
            raise SystemExit(f"WS46_MICRO_TARGET_DANGLING_ID_STILL_BOUND:{fid}")
        if exact == dangling:
            raise SystemExit(f"WS46_MICRO_TARGET_AMBIGUITY_NOT_RESOLVED:{fid}")
        target_checks.append(
            {
                "fixture_id": fid,
                "exact_target": exact,
                "dangling_requested_target": dangling,
                "plausible_referent_semantic_ids": sorted(plausible_ids),
                "all_plausible_referents_record_local": True,
                "dangling_requested_target_absent_from_semantic_ids": True,
                "provider_heuristic_required": False,
            }
        )

    output = {
        "artifact_version": "commander-lab.ws46-v104-impact-reconciliation/1.0.1",
        "historical_successor_runtime_credit_imported": 0,
        "v103": {"version": V103_VERSION, "sha256": V103_SHA256, "canonical_bundle_digest": V103_BUNDLE},
        "v104": {"version": CONTRACT_VERSION, "sha256": MATERIALIZATION_FILE_SHA256, "canonical_bundle_digest": CANONICAL_MATERIALIZATION_DIGEST},
        "fixture_id_set_equal": True,
        "record_count": 135,
        "provider_denominator": 107,
        "all_v104_requested_state_digests_independently_recomputed_equal": True,
        "provider_impact_projection_excluded_fields": sorted(DERIVED_RECORD_FIELDS),
        "changed_fixture_count": len(changed),
        "changed_fixtures": changed,
        "changed_provider_fixture_count": len(changed_provider),
        "changed_provider_fixtures": changed_provider,
        "repair_matrix": {
            "sha256": hashlib.sha256(repair_raw).hexdigest(),
            "repair_count": len(rows),
            "changed_fixture_count": len(repair_fixtures),
            "obligation_changed": False,
            "provider_semantics_used": False,
            "verified_repairs": verified_repairs,
        },
        "micro_target_identity": {
            "sha256": hashlib.sha256(target_raw).hexdigest(),
            "terminal_status": "PASS",
            "checks": target_checks,
            "provider_heuristic_required": False,
        },
        "gate": "PASS",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate": "PASS", "changed_fixture_count": len(changed), "changed_provider_fixture_count": len(changed_provider), "changed_provider_ids": [r["fixture_id"] for r in changed_provider]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        result = main()
    except SystemExit as exc:
        diagnostic = Path("artifacts/ws46-v104-reconciliation/reconciler_exit.txt")
        diagnostic.parent.mkdir(parents=True, exist_ok=True)
        diagnostic.write_text(f"{exc}\n", encoding="utf-8")
        raise
    raise SystemExit(result)
