"""WS74 Phase-0 mechanical denominator binding (no behavior, no construction).

Reads the exact WS47 authority artifacts via pinned git objects, verifies
135/107/28 counts, membership, uniqueness, order, and SHA provenance, then
freezes the ordered denominator for all downstream WS74 staging tools.

Evidence class: DIRECTLY_VERIFIED (mechanical re-read) / CODE_DERIVED (checks).
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

WS47_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
MATERIALIZATION_PATH = "qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
DENOMINATOR_PATH = "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"
FREEZE_PATH = "qualification/ws47/WS47_FREEZE_RESULT.json"
SCHEMA_VERSION = "commander-lab.semantic-fixture-materialization/1.0.5"

MATERIALIZATION_SHA256 = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
CANONICAL_BUNDLE_DIGEST = "631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"
COMMON_MANIFEST_SHA256 = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"

EXPECTED_EXCLUDED = (
    ["CARD_01"] + ["CARD_%02d" % n for n in range(3, 30)]
)


def git_show(rev_path: str) -> bytes:
    out = subprocess.run(
        ["git", "show", rev_path],
        capture_output=True,
        cwd=str(REPO),
        check=True,
    )
    return out.stdout


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


STATE_KEYS = (
    "execution_entry_mode",
    "players",
    "deck_state",
    "commander_state",
    "semantic_objects",
    "temporal_state",
    "knowledge_state",
    "rules_randomness",
    "combat_state",
    "stack_state",
    "continuous_rules_effects",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
    "setup_validation",
)


def bind() -> dict:
    mat_raw = git_show(WS47_COMMIT + ":" + MATERIALIZATION_PATH)
    den_raw = git_show(WS47_COMMIT + ":" + DENOMINATOR_PATH)
    freeze_raw = git_show(WS47_COMMIT + ":" + FREEZE_PATH)

    file_sha = hashlib.sha256(mat_raw).hexdigest()
    if file_sha != MATERIALIZATION_SHA256:
        raise RuntimeError("WS74_MATERIALIZATION_FILE_SHA_MISMATCH:%s" % file_sha)

    mat = json.loads(mat_raw)
    den = json.loads(den_raw)
    freeze = json.loads(freeze_raw)

    if mat.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("WS74_SCHEMA_VERSION_MISMATCH")
    if mat.get("canonical_bundle_digest") != CANONICAL_BUNDLE_DIGEST:
        raise RuntimeError("WS74_CANONICAL_BUNDLE_DIGEST_MISMATCH")
    if mat.get("common_fixture_manifest_sha256") != COMMON_MANIFEST_SHA256:
        raise RuntimeError("WS74_COMMON_MANIFEST_SHA_MISMATCH")

    records = mat.get("records")
    if not isinstance(records, list) or len(records) != 135:
        raise RuntimeError("WS74_MATERIALIZATION_RECORD_COUNT_MISMATCH")
    if mat.get("record_count") != 135:
        raise RuntimeError("WS74_MATERIALIZATION_RECORD_COUNT_FIELD_MISMATCH")

    ids135 = [r.get("fixture_id") for r in records]
    if len(set(ids135)) != 135 or any(not i for i in ids135):
        raise RuntimeError("WS74_MATERIALIZATION_IDS_NOT_UNIQUE")

    # Per-record digest recomputation (byte-level contract fidelity).
    for r in records:
        clone = {k: v for k, v in r.items() if k != "materialization_digest"}
        if r.get("materialization_digest") != canonical_sha(clone):
            raise RuntimeError("WS74_RECORD_DIGEST_MISMATCH:%s" % r.get("fixture_id"))
        proj = {k: r[k] for k in STATE_KEYS if k in r}
        if r.get("requested_state_digest") != canonical_sha(proj):
            raise RuntimeError("WS74_REQUESTED_STATE_DIGEST_MISMATCH:%s" % r.get("fixture_id"))
        if r.get("semantic_executability") != "SEMANTIC_EXECUTABLE":
            raise RuntimeError("WS74_RECORD_NOT_EXECUTABLE:%s" % r.get("fixture_id"))

    fixture_ids = den.get("fixture_ids")
    excluded = den.get("excluded_fixture_ids")
    if not isinstance(fixture_ids, list) or len(fixture_ids) != 107:
        raise RuntimeError("WS74_DENOMINATOR_COUNT_MISMATCH")
    if len(set(fixture_ids)) != 107:
        raise RuntimeError("WS74_DENOMINATOR_IDS_NOT_UNIQUE")
    if not isinstance(excluded, list) or len(excluded) != 28:
        raise RuntimeError("WS74_EXCLUDED_COUNT_MISMATCH")
    if sorted(excluded) != sorted(EXPECTED_EXCLUDED):
        raise RuntimeError("WS74_EXCLUDED_SET_MISMATCH")

    by_id = {r["fixture_id"]: r for r in records}
    missing = [i for i in fixture_ids if i not in by_id]
    if missing:
        raise RuntimeError("WS74_DENOMINATOR_NOT_IN_MATERIALIZATION:%s" % missing)
    missing_ex = [i for i in excluded if i not in by_id]
    if missing_ex:
        raise RuntimeError("WS74_EXCLUDED_NOT_IN_MATERIALIZATION:%s" % missing_ex)
    if set(fixture_ids) & set(excluded):
        raise RuntimeError("WS74_DENOMINATOR_EXCLUDED_OVERLAP")
    if set(fixture_ids) | set(excluded) != set(ids135):
        raise RuntimeError("WS74_DENOMINATOR_EXCLUDED_UNION_MISMATCH")

    # RQ-C3 namespace disjointness (never construct RQ-C3 scenarios as fixtures).
    for i in fixture_ids:
        if i.startswith("RQ-C"):
            raise RuntimeError("WS74_SCENARIO_ID_IN_DENOMINATOR:%s" % i)

    if den.get("provider_denominator_count") != 107:
        raise RuntimeError("WS74_DENOMINATOR_COUNT_FIELD_MISMATCH")
    if den.get("materialization_record_count") != 135:
        raise RuntimeError("WS74_DENOMINATOR_RECORD_COUNT_FIELD_MISMATCH")
    if freeze.get("provider_denominator") != 107 or freeze.get("record_count") != 135:
        raise RuntimeError("WS74_FREEZE_COUNT_MISMATCH")
    if freeze.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("WS74_FREEZE_SCHEMA_MISMATCH")

    ordered = [
        {
            "fixture_id": fid,
            "fixture_family": by_id[fid].get("fixture_family"),
            "execution_entry_mode": by_id[fid].get("execution_entry_mode"),
            "materialization_digest": by_id[fid].get("materialization_digest"),
            "requested_state_digest": by_id[fid].get("requested_state_digest"),
        }
        for fid in fixture_ids
    ]

    binding = {
        "schema": "ws74.full107-denominator-binding.v1",
        "evidence_class": "DIRECTLY_VERIFIED",
        "ws47_commit": WS47_COMMIT,
        "materialization_path": MATERIALIZATION_PATH,
        "materialization_sha256_file": MATERIALIZATION_SHA256,
        "denominator_path": DENOMINATOR_PATH,
        "denominator_sha256_file": hashlib.sha256(den_raw).hexdigest(),
        "freeze_sha256_file": hashlib.sha256(freeze_raw).hexdigest(),
        "canonical_bundle_digest": CANONICAL_BUNDLE_DIGEST,
        "schema_version": SCHEMA_VERSION,
        "materialization_records": 135,
        "provider_denominator": 107,
        "excluded": 28,
        "denominator_ids_unique": True,
        "denominator_subset_of_materialization": True,
        "denominator_union_excluded_is_135": True,
        "no_rqc_scenario_ids": True,
        "ordered_denominator": ordered,
        "excluded_ids": sorted(excluded),
        "binding_sha256": canonical_sha([o["fixture_id"] for o in ordered]),
    }
    return binding


def main() -> int:
    out_path = HERE / "FULL107_DENOMINATOR_BINDING.json"
    partial = len(sys.argv) > 1 and sys.argv[1] == "--print-only"
    binding = bind()
    payload = dict(binding)
    payload["verdict"] = (
        "PASS"
        if (
            binding["materialization_records"] == 135
            and binding["provider_denominator"] == 107
            and binding["excluded"] == 28
        )
        else "FAIL"
    )
    if not partial:
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        "WS74_DENOMINATOR_BINDING=%s MATERIALIZATION_RECORDS=135 "
        "PROVIDER_DENOMINATOR=107 EXCLUDED=28 BINDING_SHA=%s"
        % (payload["verdict"], binding["binding_sha256"][:16])
    )
    return 0 if payload["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
