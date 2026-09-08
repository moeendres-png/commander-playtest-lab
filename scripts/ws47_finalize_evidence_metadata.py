#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

VERSION = "commander-lab.semantic-fixture-materialization/1.0.5"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, type=Path)
    args = ap.parse_args()
    root = args.input_dir

    audit_path = root / "WS47_REFERENTIAL_INTEGRITY_AUDIT_135.json"
    inventory_path = root / "WS47_REFERENCE_FIELD_INVENTORY.json"
    audit = load(audit_path)
    inventory = load(inventory_path)

    if audit.get("terminal_status") != "PASS" or audit.get("defect_count") != 0 or audit.get("record_count") != 135:
        raise SystemExit("WS47_REFERENCE_AUDIT_NOT_PASS")
    legacy_negative = audit.get("historical_negative_regression")
    if legacy_negative != {
        "value": "obj:P2-bears",
        "exact_resolution_expected": 0,
        "implicit_resolution_forbidden": True,
    }:
        raise SystemExit(f"WS47_UNEXPECTED_LEGACY_NEGATIVE_REGRESSION:{legacy_negative!r}")

    audit["artifact_version"] = "commander-lab.ws47-referential-integrity-audit/1.0.0"
    audit["materialization_version"] = VERSION
    audit["historical_negative_regression"] = {
        "scope_fixture_ids": ["MICRO_PRIORITY", "MICRO_STACK"],
        "value": "obj:P2-bears",
        "exact_resolution_expected_within_scoped_fixtures": 0,
        "implicit_resolution_forbidden": True,
        "scope_note": "This inherited regression is record-local to the two historical MICRO dangling-reference fixtures. WS05-MP-BLOCK-4 legitimately declares obj:P2-bears in v1.0.4/v1.0.5 and is intentionally outside this negative-regression scope.",
    }
    audit["ws47_metadata_retag_only"] = True

    inventory["artifact_version"] = "commander-lab.ws47-reference-field-inventory/1.0.0"
    inventory["materialization_version"] = VERSION
    inventory["ws47_metadata_retag_only"] = True

    dump(audit_path, audit)
    dump(inventory_path, inventory)
    print("WS47_REFERENCE_EVIDENCE_METADATA=PASS")


if __name__ == "__main__":
    main()
