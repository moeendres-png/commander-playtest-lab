#!/usr/bin/env python3
"""WS55R mechanical derivation of the corrected Forge RQ-C3 Decision-Seam denominator.

Reads the BINDING RQ-C3 authority artifacts read-only via `git show` of the
locked RQ-C3 ref (never the working tree), cross-checks:
  1. RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json union (must be 20 kinds),
  2. RQ_C3_DECISION_REQUIREMENT_DELTA.json (may/ordering removals, C01 hidden-zone),
  3. RQ_C3_FIRST_WAVE_EXECUTION_PACK.json per-scenario decision_kinds (must match),
and writes WS55R_CORRECTED_DENOMINATOR.json. Fails loud on any divergence.

Grants no behavior credit. FULL107 NOT_RUN.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RQC3_REF = "897d72f0b57bb8febe045870acaa3d2dba4bde56"
RQC3_TREE = "1b8c8a46f1b81277f73a0ec808055dde25fadbe5"
BASE = "research/candidate-qualification/common/rq-c3"
REQ = f"{BASE}/RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json"
DELTA = f"{BASE}/RQ_C3_DECISION_REQUIREMENT_DELTA.json"
PACK = f"{BASE}/RQ_C3_FIRST_WAVE_EXECUTION_PACK.json"

HERE = Path(__file__).resolve().parent


def show(ref_path: str) -> dict:
    out = subprocess.run(
        ["git", "show", f"{RQC3_REF}:{ref_path}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def main() -> int:
    # Pin check: ref tree must match the locked RQ-C3 tree.
    tree = subprocess.run(
        ["git", "rev-parse", f"{RQC3_REF}^{{tree}}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert tree == RQC3_TREE, f"RQC3 tree mismatch: {tree} != {RQC3_TREE}"

    req = show(REQ)
    delta = show(DELTA)
    pack = show(PACK)

    union = sorted(req["union"].keys())
    assert len(union) == 20, f"corrected union must be 20 kinds, got {len(union)}: {union}"
    assert "may" not in union, "may must be absent from corrected union"
    assert "ordering" not in union, "generic ordering must be absent from corrected union"
    assert "replacement ordering" in union, "replacement ordering must be retained"
    assert "concession" in union, "concession must be retained"
    assert "alternate cost" in union, "alternate cost must be retained"
    assert "combat damage assignment" in union, "combat damage assignment must be retained"
    assert sorted(req["union"]["hidden-zone selection"]) == ["RQ-C3-C01", "RQ-C3-F01"], \
        "hidden-zone selection must be contributed by C01+F01"

    # Delta cross-check.
    assert delta["rq_c1_union_counts"].get("may") == 1
    assert delta["rq_c1_union_counts"].get("ordering") == 1
    assert "may" not in delta["rq_c3_union_counts"]
    assert "ordering" not in delta["rq_c3_union_counts"]
    assert len(delta["rq_c3_union_counts"]) == 20, \
        f"delta RQ-C3 union must be 20, got {len(delta['rq_c3_union_counts'])}"
    assert set(delta["rq_c3_union_counts"].keys()) == set(union), \
        "delta union keys must equal requirements union keys"

    # Execution-pack cross-check: per-scenario kinds must match requirements map.
    pack_by_id = {s["rqc3_scenario_id"]: sorted(s["decision_kinds"]) for s in pack["scenarios"]}
    assert len(pack_by_id) == 15, f"pack must carry 15 scenarios, got {len(pack_by_id)}"
    for sid, kinds in req["per_scenario"].items():
        assert sid in pack_by_id, f"{sid} missing from execution pack"
        assert pack_by_id[sid] == sorted(kinds), \
            f"{sid} kinds mismatch pack {pack_by_id[sid]} vs req {sorted(kinds)}"

    # Union recomputed from per-scenario maps must equal the stated union.
    recomputed = sorted({k for kinds in req["per_scenario"].values() for k in kinds})
    assert recomputed == union, f"recomputed union mismatch: {recomputed}"

    denom = {
        "schema": "ws55r.corrected-denominator.v1",
        "authority": "RQ-C3 binding (requirements + delta + execution pack triple-agree)",
        "rq_c3_ref": RQC3_REF,
        "rq_c3_tree": RQC3_TREE,
        "CORRECTED_FIRST_WAVE_REQUIRED_DECISION_KINDS": union,
        "CORRECTED_FIRST_WAVE_REQUIRED_DECISION_KINDS_COUNT": 20,
        "removed_vs_rq_c1": ["may", "ordering"],
        "extended_vs_rq_c1": {"hidden-zone selection": ["RQ-C3-C01", "RQ-C3-F01"]},
        "retained_blocking": ["alternate cost", "combat damage assignment",
                              "replacement ordering", "concession"],
        "first_wave_scenario_count": 15,
        "per_scenario": {sid: sorted(k) for sid, k in req["per_scenario"].items()},
        "union_counts": req["union_counts"],
        "grants_behavior_credit": False,
        "evidence_class": "CODE_DERIVED",
    }
    out = HERE / "WS55R_CORRECTED_DENOMINATOR.json"
    out.write_text(json.dumps(denom, indent=1, sort_keys=True) + "\n")
    print(f"WS55R corrected denominator OK: 20 kinds, 15 scenarios -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
