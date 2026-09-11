#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import jsonschema
import ws44_build_successor as B

PRE_MAT = Path("qualification/ws44/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json")
PRE_SHA = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
PRE_VERSION = "commander-lab.semantic-fixture-materialization/1.0.4"
POST_VERSION = "commander-lab.semantic-fixture-materialization/1.0.5"
TARGET = "WS05-MP-BLOCK-4"
OLD = ["obj:mp-p2-blocker"]
NEW = ["obj:P2-bears", "obj:mp-p2-blocker"]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def by_id(bundle):
    return {r["fixture_id"]: r for r in bundle["records"]}


def normalize_unrelated_successor(record, predecessor):
    x = copy.deepcopy(record)
    x["materialization_version"] = PRE_VERSION
    x["materialization_digest"] = predecessor["materialization_digest"]
    return x


def validate(out: Path) -> dict:
    if sha(PRE_MAT.read_bytes()) != PRE_SHA:
        raise RuntimeError("predecessor file SHA mismatch")
    pre = load(PRE_MAT)
    post = load(out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")
    schema = load(out / "SEMANTIC_FIXTURE_SCHEMA_v1_0_5.json")
    denom = load(out / "WS47_PROVIDER_DENOMINATOR_107.json")
    supersedes = load(out / "SUPERSEDES_v1_0_4.json")
    blocker = load(out / "WS47_BLOCKER_SURFACE_REGRESSION.json")
    change = load(out / "WS47_CHANGE_ACCOUNTING.json")

    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(post), key=lambda e: list(e.path))
    if errors:
        raise RuntimeError("schema validation failed: " + " | ".join(e.message for e in errors[:10]))

    if pre.get("schema_version") != PRE_VERSION or post.get("schema_version") != POST_VERSION:
        raise RuntimeError("schema identity mismatch")
    pre_ids = [r["fixture_id"] for r in pre["records"]]
    post_ids = [r["fixture_id"] for r in post["records"]]
    if pre_ids != post_ids or len(post_ids) != 135:
        raise RuntimeError("record identity/order/count drift")
    if denom.get("provider_denominator_count") != 107 or len(denom.get("fixture_ids", [])) != 107:
        raise RuntimeError("provider denominator count drift")
    if denom.get("fixture_ids") != load("qualification/ws44/WS44_PROVIDER_DENOMINATOR_107.json").get("fixture_ids"):
        raise RuntimeError("provider denominator identity/order drift")

    pre_by, post_by = by_id(pre), by_id(post)
    forbidden_unrelated = []
    state_changed = []
    obligation_changed = []
    for fid in pre_ids:
        a, b = pre_by[fid], post_by[fid]
        if B.legacy.requested_state_digest(a) != B.legacy.requested_state_digest(b):
            state_changed.append(fid)
        if B.legacy.obligation_digest(a) != B.legacy.obligation_digest(b):
            obligation_changed.append(fid)
        if fid != TARGET and normalize_unrelated_successor(b, a) != a:
            forbidden_unrelated.append(fid)
    if state_changed != [TARGET]:
        raise RuntimeError(f"requested-state change set mismatch: {state_changed}")
    if obligation_changed:
        raise RuntimeError(f"obligation changed: {obligation_changed}")
    if forbidden_unrelated:
        raise RuntimeError(f"unrelated record byte/semantic drift after envelope normalization: {forbidden_unrelated}")

    old_target = pre_by[TARGET]
    new_target = post_by[TARGET]
    if old_target.get("combat_state", {}).get("eligible_blockers") != OLD:
        raise RuntimeError("predecessor target blocker precondition mismatch")
    if new_target.get("combat_state", {}).get("eligible_blockers") != NEW:
        raise RuntimeError("successor target blocker surface mismatch")
    ids = {o.get("semantic_id"): o for o in new_target.get("semantic_objects", [])}
    for sid, card in (("obj:P2-bears", "Grizzly Bears"), ("obj:mp-p2-blocker", "Runeclaw Bear")):
        o = ids.get(sid)
        if not o:
            raise RuntimeError(f"missing target semantic object {sid}")
        required = {"card_identity": card, "controller": "P2", "owner": "P2", "zone": "battlefield", "tapped": False, "face_down": False, "counters": {}}
        if any(o.get(k) != v for k, v in required.items()):
            raise RuntimeError(f"authority state precondition drift for {sid}")
    p3 = {o.get("semantic_id") for o in new_target.get("semantic_objects", []) if o.get("controller") == "P3"}
    if p3.intersection(NEW):
        raise RuntimeError("P3-controlled object leaked into P2 blocker surface")
    if new_target.get("continuous_rules_effects") not in ([], None):
        raise RuntimeError("unexpected blocking-effect surface")

    for r in post["records"]:
        projected = dict(r); stored = projected.pop("materialization_digest")
        if stored != sha(canonical(projected)):
            raise RuntimeError(f"record materialization digest mismatch: {r['fixture_id']}")
        if r["requested_state_digest"] != B.legacy.requested_state_digest(r):
            raise RuntimeError(f"requested-state digest mismatch: {r['fixture_id']}")
        if r["obligation_digest"] != B.legacy.obligation_digest(r):
            raise RuntimeError(f"obligation digest mismatch: {r['fixture_id']}")
    top = dict(post); stored_top = top.pop("canonical_bundle_digest")
    if stored_top != sha(canonical(top)):
        raise RuntimeError("canonical bundle digest mismatch")

    if supersedes.get("requested_state_changed_count") != 1 or supersedes.get("requested_state_changed_fixture_ids") != [TARGET] or supersedes.get("obligation_changed") is not False:
        raise RuntimeError("supersession accounting mismatch")
    if blocker.get("terminal_status") != "PASS" or blocker.get("general_rules_engine_implemented") is not False or blocker.get("provider_queried") is not False:
        raise RuntimeError("blocker regression evidence invalid")
    if change.get("terminal_status") != "PASS" or change.get("requested_state_changed_fixture_ids") != [TARGET]:
        raise RuntimeError("change accounting evidence invalid")

    actual_ids = [f"CARD_{n:02d}" for n in range(1, 30)]
    for fid in actual_ids:
        if normalize_unrelated_successor(post_by[fid], pre_by[fid]) != pre_by[fid]:
            raise RuntimeError(f"actual-card preservation failed: {fid}")

    return {
        "artifact_version": "commander-lab.ws47-independent-validation/1.0.0",
        "schema_validation": "PASS",
        "record_identity_order_count": "135/135 PASS",
        "provider_denominator": "107/107 IDENTITY_AND_ORDER_PASS",
        "referential_report": "SEPARATE_BUILDER_GATE",
        "requested_state_changed_fixture_ids": state_changed,
        "obligation_changed_fixture_ids": obligation_changed,
        "unrelated_record_equivalence": "134/134 PASS_AFTER_VERSION_AND_MATERIALIZATION_DIGEST_ENVELOPE_NORMALIZATION",
        "actual_card_preservation": "29/29 PASS_AFTER_ENVELOPE_NORMALIZATION",
        "blocker_surface": NEW,
        "canonical_bundle_digest": post["canonical_bundle_digest"],
        "materialization_sha256": sha((out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json").read_bytes()),
        "terminal_status": "PASS",
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--input-dir", required=True, type=Path); ap.add_argument("--report", required=True, type=Path); args = ap.parse_args()
    report = validate(args.input_dir)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("WS47_INDEPENDENT_VALIDATION=PASS")


if __name__ == "__main__":
    main()
