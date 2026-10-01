from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = REPO_ROOT / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
PROJECTION_KEYS = (
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
OBLIGATION_KEYS = (
    "fixture_id",
    "fixture_family",
    "frozen_contract_binding",
    "card_authority_binding",
    "expected_events",
    "terminal_postconditions",
)


class ContractError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def requested_state_digest(record: dict[str, Any]) -> str:
    projected = {key: record[key] for key in PROJECTION_KEYS if key in record}
    return hashlib.sha256(canonical_json(projected).encode("utf-8")).hexdigest()


def obligation_digest(record: dict[str, Any]) -> str:
    projected = {key: record.get(key) for key in OBLIGATION_KEYS}
    return hashlib.sha256(canonical_json(projected).encode("utf-8")).hexdigest()


def materialization_digest(record: dict[str, Any]) -> str:
    projected = copy.deepcopy(record)
    projected.pop("materialization_digest", None)
    return hashlib.sha256(canonical_json(projected).encode("utf-8")).hexdigest()


def canonical_bundle_digest(bundle: dict[str, Any]) -> str:
    projected = copy.deepcopy(bundle)
    projected.pop("canonical_bundle_digest", None)
    return hashlib.sha256(canonical_json(projected).encode("utf-8")).hexdigest()


def load_effective_materialization() -> dict[str, Any]:
    authority = _load(AUTHORITY_PATH)
    full107 = authority["full107"]
    base_path = REPO_ROOT / full107["historical_base_materialization"]
    base_bytes = base_path.read_bytes()
    if _sha256_bytes(base_bytes) != full107["historical_base_sha256"]:
        raise ContractError("historical FULL107 base bytes drifted")

    bundle = json.loads(base_bytes.decode("utf-8"))
    successor = _load(REPO_ROOT / full107["successor_contract"])
    patches = {item["fixture_id"]: item for item in successor["record_successors"]}
    expected_changed = set(authority["full107"]["changed_fixture_ids"])
    if set(patches) != expected_changed:
        raise ContractError("successor patch set differs from current authority")

    effective = copy.deepcopy(bundle)
    historical_authority_lock = copy.deepcopy(effective.get("authority_lock"))
    historical_bundle_digest = effective.pop("canonical_bundle_digest", None)
    historical_supersedes = copy.deepcopy(effective.get("supersedes"))

    effective["schema_version"] = "commander-lab.semantic-fixture-materialization/1.0.7-successor"
    effective["contract_id"] = successor["contract_id"]
    effective["qualification_boundary"] = "commander-lab.pre-freeze-qualification/2.0.0"
    effective["qualification_protocol_version"] = "2.0.0"
    effective["protocol_role"] = "HISTORICAL_FIXTURE_ENCODING_PROVENANCE"
    effective["authority_lock"] = {
        "receipt_path": "qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json",
        "effective_date": successor["rules_authority"]["effective_date"],
        "rule": successor["rules_authority"]["rule"],
    }
    effective["current_rules_authority"] = copy.deepcopy(effective["authority_lock"])
    effective["historical_authority_lock"] = historical_authority_lock
    effective["evidence_migration"] = copy.deepcopy(full107["evidence_migration"])
    effective["supersedes"] = {
        "historical_schema_version": bundle.get("schema_version"),
        "historical_canonical_bundle_digest": historical_bundle_digest,
        "historical_supersedes": historical_supersedes,
        "successor_contract": full107["successor_contract"],
    }

    seen: set[str] = set()
    for record in effective["records"]:
        fixture_id = record["fixture_id"]
        patch = patches.get(fixture_id)
        if patch is None:
            continue
        seen.add(fixture_id)
        if record.get("requested_state_digest") != patch["predecessor_requested_state_digest"]:
            raise ContractError(f"predecessor digest mismatch for {fixture_id}")

        historical_digests = {}
        for key in ("materialization_digest", "obligation_digest", "supersedes_record_digest"):
            if key in record:
                historical_digests[key] = record[key]
        record["historical_digests"] = historical_digests
        predecessor_materialization_digest = record.pop("materialization_digest", None)
        record.pop("obligation_digest", None)
        record.pop("supersedes_record_digest", None)

        for key, value in patch["replace"].items():
            record[key] = copy.deepcopy(value)
        record["knowledge_state"]["channel_policy"] = patch["knowledge_state_channel_policy"]
        record.setdefault("native_procedure", []).extend(
            copy.deepcopy(patch["append_native_procedure"])
        )
        provenance = record.setdefault("authority_provenance", {})
        historical_rsp = provenance.pop("rsp", None)
        overlay = copy.deepcopy(patch["authority_overlay"])
        if historical_rsp is not None and overlay["historical_rsp"] != historical_rsp:
            raise ContractError(f"historical RSP mismatch for {fixture_id}")
        provenance.update(overlay)

        record["materialization_status"] = "AUTHORITY_CORRECTED_SUCCESSOR"
        record["materialization_version"] = (
            "commander-lab.semantic-fixture-materialization/1.0.7-successor"
        )
        record["repair_provenance"] = {
            "predecessor_version": bundle.get("schema_version"),
            "predecessor_requested_state_digest": patch["predecessor_requested_state_digest"],
            # A per-record erratum class is more precise than the contract-level
            # one, which now covers several distinct corrections (a CR authority
            # correction, script errata and a CR 307.1 fixture-defect repair).
            # The contract-level class remains the fallback for historical
            # patches that only carry it.
            "correction_class": patch.get(
                "correction_class", successor["change_accounting"]["change_class"]
            ),
            "provider_semantics_used": False,
            "historical_record_preserved": True,
            "current_boundary_runtime_credit": "NOT_GRANTED_BY_MATERIALIZATION",
        }
        digest = requested_state_digest(record)
        if digest != patch["successor_requested_state_digest"]:
            raise ContractError(f"successor requested-state digest mismatch for {fixture_id}")
        record["requested_state_digest"] = digest
        record["obligation_digest"] = obligation_digest(record)
        if predecessor_materialization_digest is None:
            raise ContractError(f"predecessor materialization digest missing for {fixture_id}")
        record["supersedes_record_digest"] = predecessor_materialization_digest
        record["materialization_digest"] = materialization_digest(record)

    if seen != expected_changed:
        raise ContractError("not every successor fixture was found in historical materialization")
    effective["canonical_bundle_digest"] = canonical_bundle_digest(effective)
    return effective


def effective_record(fixture_id: str) -> dict[str, Any]:
    for record in load_effective_materialization()["records"]:
        if record["fixture_id"] == fixture_id:
            return record
    raise ContractError(f"fixture not found: {fixture_id}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_id")
    args = parser.parse_args()
    print(json.dumps(effective_record(args.fixture_id), indent=2, sort_keys=True))
