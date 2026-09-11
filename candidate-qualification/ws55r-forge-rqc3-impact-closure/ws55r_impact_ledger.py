#!/usr/bin/env python3
"""WS55R impact ledger: classify every WS55 Decision family against RQ-C3.

Mechanical premises (asserted, fail loud):
  - may / generic ordering present in WS55 (RQ-C1) union, absent in RQ-C3 union.
  - corrected E02 kinds == {attackers, defender per attacker, blockers,
    combat damage assignment, pass} (no ordering).
  - replacement ordering / concession / alternate cost / combat damage
    assignment retained in RQ-C3 union.
  - C01 contributes hidden-zone selection in RQ-C3 (absent in RQ-C1 C01).
  - all other per-scenario kind sets unchanged per the delta map.
Adjudicative layer (evidence-preserving, no inference of 20/20):
  - may, ordering -> RECLASSIFIED_NONBLOCKING (proofs preserved, non-required).
  - concession, hidden-zone selection, replacement ordering ->
    TARGETED_REQUALIFICATION_REQUIRED (G04 architecture / C01 pitch context /
    A04 exact fixture; historical gaps or unreached contexts, not invalidated).
  - remaining 17 families -> NO_IMPACT (requirements unchanged + WS55 proven).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS55 = HERE.parent / "ws55-forge-mandatory-decision-breadth"
RQC3_REF = "897d72f0b57bb8febe045870acaa3d2dba4bde56"
BASE = "research/candidate-qualification/common/rq-c3"


def show(ref_path: str) -> dict:
    out = subprocess.run(
        ["git", "show", f"{RQC3_REF}:{ref_path}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def main() -> int:
    ws55_req = json.loads((WS55 / "WS55_FIRST_WAVE_DECISION_REQUIREMENTS.json").read_text())
    ws55_matrix = json.loads((WS55 / "WS55_DECISION_BREADTH_MATRIX.json").read_text())
    rqc3_req = show(f"{BASE}/RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json")
    delta = show(f"{BASE}/RQ_C3_DECISION_REQUIREMENT_DELTA.json")

    ws55_union = set(ws55_req["FIRST_WAVE_REQUIRED_DECISION_KINDS"])
    assert len(ws55_union) == 22, ws55_union
    rqc3_union = set(rqc3_req["union"].keys())
    assert len(rqc3_union) == 20, rqc3_union

    # Premise 1: removals.
    assert "may" in ws55_union and "may" not in rqc3_union
    assert "ordering" in ws55_union and "ordering" not in rqc3_union
    # Premise 2: E02 corrected kinds.
    assert sorted(rqc3_req["per_scenario"]["RQ-C3-E02"]) == sorted(
        ["attackers", "blockers", "combat damage assignment",
         "defender per attacker", "pass"])
    assert sorted(ws55_req["per_scenario"]["RQ-C1-E02"]["decision_kinds"]) == sorted(
        ["attackers", "blockers", "combat damage assignment",
         "defender per attacker", "ordering", "pass"])
    # Premise 3: retentions.
    for kind in ("replacement ordering", "concession", "alternate cost",
                 "combat damage assignment"):
        assert kind in ws55_union and kind in rqc3_union, kind
    # Premise 4: C01 hidden-zone extension.
    assert "hidden-zone selection" not in ws55_req["per_scenario"]["RQ-C1-C01"]["decision_kinds"]
    assert "hidden-zone selection" in rqc3_req["per_scenario"]["RQ-C3-C01"]
    # Premise 5: all other per-scenario deltas empty.
    for scen, dd in delta["per_scenario_delta"].items():
        rqc1, rqc3 = scen.split(" -> ")
        expect_removed = {"RQ-C1-A03 -> RQ-C3-A03": ["may"],
                          "RQ-C1-E02 -> RQ-C3-E02": ["ordering"]}.get(scen, [])
        expect_added = {"RQ-C1-C01 -> RQ-C3-C01": ["hidden-zone selection"]}.get(scen, [])
        assert sorted(dd["removed"]) == sorted(expect_removed), (scen, dd)
        assert sorted(dd["added"]) == sorted(expect_added), (scen, dd)
    # Premise 6: WS55 support classifications for the reclassified pair.
    assert ws55_matrix["rows"]["may"]["support_classification"] == "PROVEN_NATIVE_EXTERNALIZABLE"
    assert ws55_matrix["rows"]["ordering"]["support_classification"] == "PROVEN_NATIVE_EXTERNALIZABLE"
    assert ws55_matrix["rows"]["replacement ordering"]["support_classification"] == \
        "ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE"
    assert ws55_matrix["rows"]["concession"]["support_classification"] == \
        "ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE"

    families: dict[str, dict] = {}

    def put(family: str, verdict: str, basis: str) -> None:
        families[family] = {"verdict": verdict, "mechanical_basis": basis}

    # 17 NO_IMPACT: RQ-C3 requirements unchanged for every contributing
    # scenario AND WS55 kind-level proof stands (matrix PROVEN).
    no_impact = [
        "Commander movement", "X", "activate", "alternate cost", "attackers",
        "blockers", "cast", "combat damage assignment", "copy choices",
        "defender per attacker", "mana payment", "mana source", "modes",
        "pass", "search", "targets", "trigger ordering",
    ]
    for fam in no_impact:
        key = fam
        row = ws55_matrix["rows"][key]
        assert row["support_classification"] == "PROVEN_NATIVE_EXTERNALIZABLE", fam
        put(fam, "NO_IMPACT",
            f"RQ-C3 per-scenario delta empty for all {fam} contributors "
            f"(delta per_scenario_delta); WS55 kind proof stands "
            f"({row['evidence'][:120]}...). No rerun.")
    # Document carried subgaps without invalidating kind proof.
    families["alternate cost"]["carried_subgap"] = (
        "FoW-pitch end-to-end payment still NOT_REACHED behind the spell-stack "
        "target gap (WS55 matrix); tracked by WS55R_C01, not a kind invalidation.")
    families["targets"]["carried_subgap"] = (
        "Stack-spell candidacy engine raw=0 (WS55 EG-4) still blocks the C01 "
        "subpath only; battlefield/player targeting proof stands; tracked by WS55R_C01.")

    put("may", "RECLASSIFIED_NONBLOCKING",
        "Present in RQ-C1 union (A03 contributor), absent in RQ-C3 union "
        "(delta REMOVED 701.19a automatic). WS55 proof (confirmTrigger NO, "
        "copy YES/NO, regen activation) preserved as non-required capability. "
        "No rerun; must not be counted toward the corrected 20.")
    put("ordering", "RECLASSIFIED_NONBLOCKING",
        "Present in RQ-C1 union (E02 contributor), absent in RQ-C3 union "
        "(delta REMOVED 510.1c no ordering step). WS55 proofs (orderBlockers "
        "2-perm + legacy damage under orderCombatants=1; zone-move 6/6) "
        "preserved as non-required capability. E02 is no longer conditional "
        "on orderCombatants merely for this kind. No rerun.")
    put("concession", "TARGETED_REQUALIFICATION_REQUIRED",
        "Retained in RQ-C3 union via G04. WS55 status "
        "ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE (never offered; no "
        "PlayerController seam) is preserved, NOT invalidated; G04 native "
        "concession architecture determination is new targeted work (WS55R_G04).")
    put("hidden-zone selection", "TARGETED_REQUALIFICATION_REQUIRED",
        "Extended in RQ-C3: C01 adds pitch-selection context (delta "
        "RETAINED+EXTENDED). WS55 F01 search proof stands for the search "
        "subpath; the C01 cost/pitch hidden-zone context was never reached "
        "(behind spell-stack target gap) and is new targeted work (WS55R_C01).")
    put("replacement ordering", "TARGETED_REQUALIFICATION_REQUIRED",
        "Retained in RQ-C3 union via A04. WS55 status "
        "ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE over three non-exact shapes "
        "(Serpent-ETB-alone, TravelPrep, regen-vs-RIP) is preserved, NOT "
        "invalidated; the exact RQ-C3 A04 fixture (Doubling Season + Hardened "
        "Scales + Serpent X=3) was never tried and is new targeted work (WS55R_A04).")

    assert len(families) == 22, len(families)
    totals = {"NO_IMPACT": 0, "RECLASSIFIED_NONBLOCKING": 0,
              "TARGETED_REQUALIFICATION_REQUIRED": 0, "INVALIDATED": 0, "UNKNOWN": 0}
    for fam in families.values():
        totals[fam["verdict"]] += 1
    assert totals == {"NO_IMPACT": 17, "RECLASSIFIED_NONBLOCKING": 2,
                      "TARGETED_REQUALIFICATION_REQUIRED": 3,
                      "INVALIDATED": 0, "UNKNOWN": 0}, totals

    ledger = {
        "schema": "ws55r.rqc3-impact-ledger.v1",
        "authority": "RQ-C3 delta applied to WS55 (RQ-C1) evidence; mechanical premises asserted",
        "ws55_head": "47a1e714903a91d8929f48df6451365e8b7a7996",
        "rq_c3_ref": RQC3_REF,
        "warning": ("Historical WS55 20/22 is NOT 20/20: the proven 20 included "
                    "now-removed may + ordering; replacement ordering, concession, and "
                    "C01 pitch context remain unproven under RQ-C3."),
        "totals": totals,
        "families": families,
        "preservation_rule": ("All NO_IMPACT evidence is preserved without rerun. "
                              "No provider/shared/Forge file was modified by WS55R so far; "
                              "no shared-implementation change exists that would force reruns."),
        "grants_behavior_credit": False,
        "evidence_class": "CODE_DERIVED",
    }
    out = HERE / "WS55R_RQC3_IMPACT_LEDGER.json"
    out.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    print(f"WS55R impact ledger OK: {totals} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
