#!/usr/bin/env python3
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--neutral-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.neutral_root)
    q = root / "qualification" / "finalist_convergence"
    union_path = q / "KNOWN_PASS_UNION_50_v1_0_1.json"
    exec_path = q / "SEMANTIC_EXECUTABILITY_REPORT.json"
    starter_path = q / "DIFFERENTIAL_STARTER_18_v1_0_1.json"

    union = load(union_path)
    execution = load(exec_path)
    starter = load(starter_path)

    exec_rows = {r["fixture_id"]: r for r in execution["records"]}
    union_ids = list(union["fixture_ids"])
    starter_ids = list(starter["fixture_ids"])

    assert len(union_ids) == 50 and len(set(union_ids)) == 50
    assert len(starter_ids) == 18 and len(set(starter_ids)) == 18
    assert set(starter_ids).issubset(union_ids)
    assert len(exec_rows) == 135

    union_rows = [exec_rows[i] for i in union_ids]
    starter_rows = [exec_rows[i] for i in starter_ids]
    counts = Counter(r["status"] for r in union_rows)
    starter_counts = Counter(r["status"] for r in starter_rows)

    contract_defects = []
    executable = []
    for row in union_rows:
        if row["status"] == "PASS":
            executable.append(row["fixture_id"])
        else:
            contract_defects.append({
                "fixture_id": row["fixture_id"],
                "materialization_digest": row["materialization_digest"],
                "defects": row.get("defects", []),
            })

    all_counts = Counter(r["status"] for r in execution["records"])
    output = {
        "schema_version": "commander-lab.finalist-convergence-scope-audit/1.0.0",
        "neutral_contract": {
            "schema_version": execution["input_schema_version"],
            "bundle_digest": execution["input_bundle_digest"],
            "union50_sha256": sha256(union_path),
            "starter18_sha256": sha256(starter_path),
            "executability_report_sha256": sha256(exec_path),
        },
        "starter18": {
            "count": 18,
            "contract_status_counts": dict(sorted(starter_counts.items())),
            "contract_executable_ids": [r["fixture_id"] for r in starter_rows if r["status"] == "PASS"],
        },
        "known_pass_union50": {
            "count": 50,
            "contract_status_counts": dict(sorted(counts.items())),
            "contract_executable_count": len(executable),
            "contract_executable_ids": executable,
            "contract_defect_count": len(contract_defects),
            "contract_defects": contract_defects,
        },
        "full_135": {
            "count": 135,
            "contract_status_counts": dict(sorted(all_counts.items())),
        },
        "interpretation": {
            "authority_or_contract_pass_is_not_runtime_credit": True,
            "candidate_must_not_be_blamed_for_contract_defect": True,
            "v1_0_1_is_immutable": True,
            "contract_defect_requires_new_immutable_errata_before_runtime_credit": True,
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "union50": output["known_pass_union50"]["contract_status_counts"],
        "full135": output["full_135"]["contract_status_counts"],
        "contract_defect_ids": [d["fixture_id"] for d in contract_defects],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
