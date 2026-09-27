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
    effective["schema_version"] = successor["contract_id"]
    effective["protocol"] = "commander-lab.pre-freeze-qualification/2.0.0"
    effective["protocol_version"] = "2.0.0"
    effective["supersedes"] = {
        "historical_schema_version": bundle.get("schema_version"),
        "historical_canonical_bundle_digest": bundle.get("canonical_bundle_digest"),
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
                historical_digests[key] = record.pop(key)
        record["historical_digests"] = historical_digests

        for key, value in patch["replace"].items():
            record[key] = copy.deepcopy(value)
        record["knowledge_state"]["channel_policy"] = patch[
            "knowledge_state_channel_policy"
        ]
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
        record["materialization_version"] = successor["contract_id"]
        record["repair_provenance"] = {
            "predecessor_version": bundle.get("schema_version"),
            "predecessor_requested_state_digest": patch["predecessor_requested_state_digest"],
            "correction_class": successor["change_accounting"]["change_class"],
            "provider_semantics_used": False,
            "historical_record_preserved": True,
        }
        digest = requested_state_digest(record)
        if digest != patch["successor_requested_state_digest"]:
            raise ContractError(f"successor requested-state digest mismatch for {fixture_id}")
        record["requested_state_digest"] = digest

    if seen != expected_changed:
        raise ContractError("not every successor fixture was found in historical materialization")
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
