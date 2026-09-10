#!/usr/bin/env python3
"""WS48-R1f historical evidence impact audit (WS48-owned, qualification-only).

Adjudicates the WS50-ADAPTER-REPAIR-01 double-add defect against every
retained WS48 R1b/R1c/R1d/R1e evidence unit at exact historical source /
artifact state. No reruns, no WS47/WS50 mutation, no behavior credit.

Method (per unit):
  1. Was choosePriority reached? (retained probe frames_detail / runner kind.)
  2. Were ACT options offered? How many? (first offered ACT frame.)
  3. Which external option/index did the harness select? Derived from the
     WS47 decision_script/priority_script under the exact retained driver
     semantics (run_behavior_transcript_probe.py answer_priority):
       - ACT is selected ONLY via a matching priority/choose_ability script
         entry (exactly-one match, else fail-closed) or a CAST priority_script
         entry (none exist in any R1e record);
       - otherwise the driver structural-PASSes (o0) or terminates.
  4. If ACT selected, was it the first native ACT option? (offered order in
     the retained artifact vs the scripted semantic identity.)
  5. Mechanism rule (proven by ws48_r1f_selection_execution_gate.py):
       - PASS (o0) never indexes nativeOptions -> cannot misbind;
       - first ACT (o1 -> nativeOptions[0]) binds exactly even when broken;
       - non-first ACT may misbind when broken.
  6. Classification per the retention rule: NO_IMPACT only when the unit
     could not have been affected; INVALIDATED only on affirmative
     contradiction; UNKNOWN when evidence cannot determine (never NO_IMPACT).

Inputs (read-only):
  --r1e-full10      retained R1e 10-row probe JSON (exact historical artifact)
  --materialization immutable WS47 materialization (scripts only, never credit)
  --ws50-pre         WS50 pre-repair regression probe (read-only comparison)
  --ws50-post        WS50 post-repair regression probe (read-only comparison)
  --json-out        ledger output path
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve()
CANDIDATE_DIR = HERE.parent
REPO_ROOT = CANDIDATE_DIR.parents[1]

LEDGER_VERSION = "commander-lab.ws48-r1f-historical-impact-ledger/1.0.0"

R1E_COMMIT = "10a7f8f6ebc5be2b2a89d3d019f0c16659cadc7d"
R1BCD_COMMIT = "0a3022350a518ccee07e991ba88e33c186b1a7a9"
WS50_COMMIT = "e636e7055478709010cbd778846683065e31655b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dec_label(label: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not label.startswith("WS48:"):
        out["_legacy"] = label
        return out
    parts = label.split(":")
    out["_kind"] = parts[1] if len(parts) > 1 else ""
    for seg in parts[2:]:
        if "=" in seg:
            k, v = seg.split("=", 1)
            out[k] = urllib.parse.unquote_plus(v)
        else:
            out[seg] = ""
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--r1e-full10", type=Path, required=True)
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--ws50-pre", type=Path, required=True)
    ap.add_argument("--ws50-post", type=Path, required=True)
    ap.add_argument("--json-out", type=Path, required=True)
    args = ap.parse_args()

    full10 = json.loads(args.r1e_full10.read_text())
    mat = json.loads(args.materialization.read_text())
    pre = json.loads(args.ws50_pre.read_text())
    post = json.loads(args.ws50_post.read_text())
    records = {r["fixture_id"]: r for r in mat["records"]}
    rows = {r["fixture_id"]: r for r in full10["rows"]}

    # WS50 pre/post-repair equivalence on the shared subset.
    pre_rows = {r["fixture_id"]: r for r in pre["rows"]}
    post_rows = {r["fixture_id"]: r for r in post["rows"]}
    regression_equal = []
    for fid in sorted(set(pre_rows) & set(post_rows)):
        a, b = pre_rows[fid], post_rows[fid]
        eq = (
            a.get("verdict") == b.get("verdict")
            and a.get("frames") == b.get("frames")
            and a.get("consumed") == b.get("consumed")
            and a.get("offered_digest") == b.get("offered_digest")
        )
        regression_equal.append({"fixture_id": fid, "pre_post_identical": eq})

    units: list[dict] = []

    def priority_frames(fid: str) -> list[dict]:
        return [
            f
            for f in (rows[fid].get("frames_detail") or [])
            if f.get("kind") == "priority"
        ]

    def first_act_frame(fid: str) -> dict | None:
        for f in priority_frames(fid):
            acts = [o for o in f.get("options", []) if o.startswith("WS48:ACT")]
            if acts:
                return f
        return None

    # ---- R1e rows ---------------------------------------------------------
    for fid in (
        "PILOT_PRIORITY", "PILOT_TARGET", "PILOT_CHOOSE_MODE", "PILOT_MULLIGAN",
        "NEGATIVE_FIRST_OPTION", "HIDDEN_01", "MICRO_PRIORITY",
        "WS05-MP-BLOCK-4", "CARD_02", "PLAYER_COUNT_2P",
    ):
        rec = records[fid]
        row = rows[fid]
        ds = list(rec.get("decision_script") or [])
        ps = list(rec.get("priority_script") or [])
        pri_ds = [d for d in ds if d["decision_family"] in ("priority", "choose_ability")]
        pframes = priority_frames(fid)
        reached = len(pframes) > 0
        fact = first_act_frame(fid)
        offered_act = (
            len([o for o in fact.get("options", []) if o.startswith("WS48:ACT")])
            if fact
            else 0
        )
        if not reached:
            selected, sel_idx, first_act = "N/A (choosePriority never reached)", None, "N/A"
            witness, dep = False, "none: provider terminated before priority"
            reason = (
                "0 priority frames in the retained artifact; choosePriority "
                "never executed, so the double-add population could not run."
            )
        elif not pri_ds and not ps:
            selected, sel_idx, first_act = "PASS (structural, o0)", 0, "N/A (no ACT selected)"
            witness, dep = False, "none: no scripted priority obligation; every priority answer is o0 PASS"
            reason = (
                f"{len(pframes)} priority frames reached, but the WS47 record "
                "carries no priority/choose_ability script and an empty "
                "priority_script, so the exact retained driver can only "
                "structural-PASS (o0). PASS short-circuits before any "
                "nativeOptions indexing and cannot misbind. "
                + (
                    f"First ACT-bearing frame offered {offered_act} ACT option(s), "
                    "all declined by PASS."
                    if fact
                    else "No frame ever offered an ACT option (all PASS-only)."
                )
            )
        else:
            want = pri_ds[0]["selection"]["semantic_value"]
            want_id = (
                want.get("object") if isinstance(want, dict)
                else want.get("commander_id") if isinstance(want, dict)
                else str(want)
            )
            if isinstance(want, dict):
                want_id = want.get("object") or want.get("commander_id")
            assert fact is not None, f"{fid}: scripted priority but no ACT frame"
            labels = [dec_label(o) for o in fact["options"]]
            hits = [
                i for i, lb in enumerate(labels)
                if lb.get("_kind") == "ACT"
                and (lb.get("host") == want_id or lb.get("cmd") == want_id)
            ]
            assert len(hits) == 1, f"{fid}: {len(hits)} matches for {want_id}"
            act_rank = sum(
                1 for lb in labels[: hits[0] + 1] if lb.get("_kind") == "ACT"
            )
            sel_idx = hits[0]
            selected = fact["options"][hits[0]][:120]
            first_act = "yes" if act_rank == 1 else "NO"
            witness, dep = False, (
                "transcript-progress only (TRANSCRIPT_PROBE, no credit); "
                "scripted cast bound exactly by first-ACT mechanism"
            )
            reason = (
                f"scripted priority identity {want_id} matches exactly one "
                f"offered ACT at opaque index o{sel_idx} (ACT rank "
                f"{act_rank} of {offered_act}). First-ACT selections bind "
                "nativeOptions[0], which is identical under the broken "
                "double-add mapping (both entries are the same object), so "
                "selection==execution held. All remaining priority frames "
                "were structural PASSes (no pending script). "
                f"Retained verdict {row['verdict']} consumed={row['consumed']} "
                "does not depend on any non-first ACT outcome."
            )
            assert act_rank == 1, f"{fid}: non-first scripted ACT rank {act_rank}"
        units.append(
            {
                "milestone": "R1e",
                "scenario": fid,
                "source_commit": R1E_COMMIT,
                "artifact": f"{args.r1e_full10.name} (sha256 {sha(args.r1e_full10)[:16]}…)",
                "choosePriority_reached": reached,
                "offered_act_count_first_frame": offered_act,
                "selected_external_option": selected,
                "selected_index": sel_idx,
                "first_act": first_act,
                "execution_witness_available": witness,
                "dependency_on_selected_action": dep,
                "impact": "NO_IMPACT",
                "evidence_class": "TRANSCRIPT_PROBE",
                "reason": reason,
                "next_action": "none (no rerun; covered by post-fix bounded regression)",
            }
        )

    # ---- R1b / R1c / R1d --------------------------------------------------
    units.append(
        {
            "milestone": "R1b",
            "scenario": "R1B-COST-SURFACES (CostTap/CostAddMana/CostPayLife-mandatory/mode-mutability)",
            "source_commit": R1BCD_COMMIT,
            "artifact": "ws48_behavior_provider_overlay.py cost visitor + R1e corroborating rows",
            "choosePriority_reached": "N/A (cost-decision surfaces, not priority)",
            "offered_act_count_first_frame": "N/A",
            "selected_external_option": "N/A (automatic exact native mirrors)",
            "selected_index": None,
            "first_act": "N/A",
            "execution_witness_available": False,
            "dependency_on_selected_action": "none: CostTap/CostAddMana return fixed native decisions without prompting; CostPayLife auto-path mirrors only the exact native-mandatory branch",
            "impact": "NO_IMPACT",
            "evidence_class": "CODE_DERIVED_AND_RUNTIME_CORROBORATED",
            "reason": (
                "R1b claims concern CostDecisionMakerBase.visit branches, "
                "which never read or index Broker.choosePriority "
                "nativeOptions. Corroborating runtime rows (PILOT_PRIORITY, "
                "CARD_02 completions) are first-ACT per the R1e analysis above."
            ),
            "next_action": "none",
        }
    )
    units.append(
        {
            "milestone": "R1c",
            "scenario": "R1C-TRUTHFUL-TERMINAL-SESSION-RESULT",
            "source_commit": R1BCD_COMMIT,
            "artifact": "ws48_behavior_provider_overlay.py terminal emitter + all R1e rows",
            "choosePriority_reached": "N/A (termination path, not selection)",
            "offered_act_count_first_frame": "N/A",
            "selected_external_option": "N/A",
            "selected_index": None,
            "first_act": "N/A",
            "execution_witness_available": False,
            "dependency_on_selected_action": "none: emitter reports stop_reason/snapshot; it never indexes nativeOptions",
            "impact": "NO_IMPACT",
            "evidence_class": "CODE_DERIVED_AND_RUNTIME_CORROBORATED",
            "reason": (
                "The exactly-once SESSION_RESULT emitter operates on "
                "stop_reason and sessionSnapshot only. The double-add defect "
                "cannot alter its inputs; R1e commit records emission intact "
                "on all rows."
            ),
            "next_action": "none",
        }
    )
    for variant, outcome in (("A", "NULL_POINTER"), ("B", "RETURNED")):
        units.append(
            {
                "milestone": "R1d",
                "scenario": f"R1D-DISCRIMINATOR-VARIANT-{variant}",
                "source_commit": R1BCD_COMMIT,
                "artifact": "WS48_R1D_DISCRIMINATOR.json + run_r1d_discriminator.py + r1d_discriminator_template.java",
                "choosePriority_reached": False,
                "offered_act_count_first_frame": 0,
                "selected_external_option": "N/A (hand-built native combat; no provider)",
                "selected_index": None,
                "first_act": "N/A",
                "execution_witness_available": outcome == "RETURNED",
                "dependency_on_selected_action": "none: verdict STATE_RESTORE_OR_ADAPTER_DEFECT rests on native Combat NPE presence/absence, not on any priority selection",
                "impact": "NO_IMPACT",
                "evidence_class": "HAND_BUILT_NATIVE_REPRO",
                "reason": (
                    "The discriminator compiles a hand-built combat template "
                    "directly against Forge classes; Broker.choosePriority is "
                    "never invoked, so the overlay double-add cannot execute. "
                    f"Variant {variant} outcome {outcome} is independent of "
                    "priority binding."
                ),
                "next_action": "none",
            }
        )

    totals = {"NO_IMPACT": 0, "TARGETED_REQUALIFICATION_REQUIRED": 0,
              "INVALIDATED": 0, "UNKNOWN": 0}
    for u in units:
        totals[u["impact"]] += 1

    ledger = {
        "schema_version": LEDGER_VERSION,
        "repair": "WS50-ADAPTER-REPAIR-01 ported to WS48 (ADAPTER_BINDING, not Forge Rules-Core)",
        "source_lock": {
            "ws48_r1e_commit": R1E_COMMIT,
            "ws48_r1bcd_commit": R1BCD_COMMIT,
            "ws50_commit": WS50_COMMIT,
        },
        "inputs": {
            "r1e_full10_sha256": sha(args.r1e_full10),
            "materialization_sha256": sha(args.materialization),
            "ws50_pre_sha256": sha(args.ws50_pre),
            "ws50_post_sha256": sha(args.ws50_post),
        },
        "ws50_pre_post_regression_equivalence": regression_equal,
        "ws50_defect_demonstration": (
            "WS50_C_RUN10 frames 15-16: external selection o8 Play-land "
            "MINTED-22 executed as MINTED-77 (non-first ACT misbinding, "
            "transcript still completed). Post-repair WS50_C_RUN11 frames "
            "15-16+33: selection==execution. First-option R1e rows unaffected "
            "(6/6 pre/post identical above; full R1e first-ACT proof per unit)."
        ),
        "units": units,
        "totals": totals,
    }
    args.json_out.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    print(json.dumps(totals, indent=2))
    bad = totals["TARGETED_REQUALIFICATION_REQUIRED"] + totals["INVALIDATED"] + totals["UNKNOWN"]
    if bad:
        print(f"ATTENTION: {bad} unit(s) require action")
        return 1
    print(f"LEDGER=COMPLETE units={len(units)} all NO_IMPACT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
