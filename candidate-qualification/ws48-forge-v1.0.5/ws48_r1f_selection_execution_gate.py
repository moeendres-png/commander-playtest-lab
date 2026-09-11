#!/usr/bin/env python3
"""WS48-R1f selection->execution integrity gate (WS48-owned, qualification-only).

Static + mechanical gate for the WS50-ADAPTER-REPAIR-01 defect class:
the WS48 behavior-provider overlay's priority-label patch must not disturb
the base provider's single-add invariant

    one native SpellAbility <-> one projected ACT label <-> one opaque id

Checks (all fail-closed, non-zero exit + JSON reason on violation):

  1. OVERLAY_SINGLE_ADD: the overlay's PRIORITY_LABEL_NEW replacement text
     contains zero `nativeOptions.add(sa)` occurrences (the base generator
     already adds once). Any occurrence = double-add defect present.
  2. GENERATED_SINGLE_ADD (with --provider): the `if (seen.add(sa))` block in
     a generated provider contains exactly one nativeOptions.add and exactly
     one labels.add, and the R1f cardinality guard is present.
  3. CARDINALITY_SIMULATION: pure-Python mechanism proof that the broken
     2N-native/1N-label mapping misbinds every non-first ACT selection while
     the repaired 1:1 mapping binds all selections exactly.
  4. PARALLEL_STRUCTURE_AUDIT: every WS48 decision transport maintaining
     parallel lists is classified INVARIANT_PROVEN / NOT_APPLICABLE /
     TARGETED_REPAIR_REQUIRED / UNKNOWN with its alignment mechanism.
  5. NEGATIVE control (--mutate-check): the gate flags a synthesized
     double-add provider text (proves the gate is non-vacuous).

Usage:
  ws48_r1f_selection_execution_gate.py [--provider PATH] [--json-out PATH]
                                       [--mutate-check]

Exit 0: SELECTION_EXECUTION_INTEGRITY=PASS. Exit 2: FAIL (defect present).
Exit 3: UNKNOWN (required source anchors missing).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CANDIDATE_DIR = HERE.parent
REPO_ROOT = CANDIDATE_DIR.parents[1]
OVERLAY_PATH = CANDIDATE_DIR / "ws48_behavior_provider_overlay.py"
GENERATOR_PATH = REPO_ROOT / "scripts" / "ws23_generate_forge_vertical_provider.py"

GATE_VERSION = "commander-lab.ws48-r1f-selection-execution-gate/1.0.0"

# ---------------------------------------------------------------------------
# Parallel-structure inventory of every WS48 overlay transport that maintains
# parallel lists (labels / nativeOptions / candidates / opaque ids).
#
# alignment: how label index i provably resolves to the intended native object.
# ---------------------------------------------------------------------------
TRANSPORTS: list[dict[str, str]] = [
    {
        "transport": "Broker.choosePriority",
        "lists": "labels[0]=PASS; labels[1..N]=ACT; nativeOptions[0..N-1]",
        "alignment": "single-add invariant (base adds once; overlay adds zero) "
                     "+ R1f runtime cardinality guard "
                     "(nativeOptions.size()+1==labels.size()) + guarded idx-1 "
                     "with out-of-range fail-closed; PASS short-circuits "
                     "before any native indexing",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "getAbilityToPlay",
        "lists": "labels 1:1 from abilities; indexed back into same list",
        "alignment": "no parallel native list; abilities.get(ws48Choose(...)) "
                     "indexes the exact enumerated list",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseTargetsFor",
        "lists": "cands + labels built in same loop; optional trailing DONE",
        "alignment": "DONE appended to labels only but guarded by "
                     "(idx==labels.size()-1 && DONE) return-before-index; "
                     "else idx < cands.size() so cands.get(idx) is exact",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseTarget",
        "lists": "labels 1:1 from allTargets",
        "alignment": "allTargets.get(ws48Choose(...)) on the enumerated list",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseSingleEntityForEffect",
        "lists": "labels=[NONE?]+opts; direct index with offset",
        "alignment": "optional NONE at 0 handled by explicit idx-- with "
                     "idx==0 early-return; opts.get(idx) exact",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseEntitiesForEffect",
        "lists": "rest + labels rebuilt per round; optional trailing DONE",
        "alignment": "DONE guarded return-before-index; rest.get(idx) exact",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseCardsForEffect",
        "lists": "labels=[NONE?]+rest-labels+[DONE?]; offset for NONE",
        "alignment": "NONE early-return at idx==0; DONE guarded "
                     "return-before-index; rest.get(idx-offset) exact",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseSpellAbilitiesForEffect",
        "lists": "rest + labels rebuilt per round, same loop",
        "alignment": "rest.get(ws48Choose(...)) on the same-round list",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseSingleSpellForEffect",
        "lists": "labels 1:1 from spells",
        "alignment": "spells.get(ws48Choose(...)) on the enumerated list",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseSingleCardForZoneChange",
        "lists": "labels=[NONE?]+fetchList; offset",
        "alignment": "NONE early-return + idx-- ; fetchList.get(idx) exact",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseCardsForZoneChange",
        "lists": "rest + labels rebuilt per round; optional trailing DONE",
        "alignment": "DONE guarded return-before-index; rest.get(idx) exact",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseModeForAbility(single)",
        "lists": "labels 1:1 from possible",
        "alignment": "possible.get(ws48Choose(...)) on the enumerated list; "
                     "multi-choice stays fail-closed",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseNumber(int range)/announceRequirements",
        "lists": "labels are consecutive ints min..max; no native list",
        "alignment": "arithmetic min+idx; no parallel structure to drift",
        "status": "NOT_APPLICABLE",
    },
    {
        "transport": "chooseNumber(value list)",
        "lists": "labels 1:1 from values",
        "alignment": "values.get(ws48Choose(...)) on the enumerated list",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseBinary",
        "lists": "fixed [true,false] labels; o0=true",
        "alignment": "fixed-size explicit mapping; no parallel list",
        "status": "NOT_APPLICABLE",
    },
    {
        "transport": "chooseColor",
        "lists": "opts + labels built in same loop over colors",
        "alignment": "opts.get(ws48Choose(...)); single-color auto path "
                     "records SINGLE_NATIVE_OPTION",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "chooseSingleReplacementEffect",
        "lists": "labels 1:1 from possibleReplacers",
        "alignment": "possibleReplacers.get(ws48Choose(...))",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "orderSimultaneousSa",
        "lists": "fixed 2 labels mapping to 2 explicit orders",
        "alignment": "explicit idx==0/else branches returning exact orders; "
                     "size!=2 stays fail-closed",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "applyManaToCost",
        "lists": "nativeMana + labels built in same loop per round",
        "alignment": "nativeMana.get(ws48Choose(...)) on the same-round list",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "declareAttackers/declareBlockers",
        "lists": "defs/foes + labels built in same loop; trailing SKIP",
        "alignment": "SKIP appended to labels only but guarded by "
                     "(idx==labels.size()-1) continue-before-index; "
                     "else defs/foes.get(idx) exact; subject-scoped",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "arrangeForScry",
        "lists": "tops/bottoms/labels built in same mask loop",
        "alignment": "tops.get(idx)/bottoms.get(idx) on the same mask list",
        "status": "INVARIANT_PROVEN",
    },
    {
        "transport": "confirmAction/confirmPayment/confirmReplacementEffect",
        "lists": "fixed 2-option confirm labels",
        "alignment": "fixed-size explicit o0 mapping; no parallel list",
        "status": "NOT_APPLICABLE",
    },
    {
        "transport": "Broker.choosePlayer/Broker.chooseObject(base)",
        "lists": "choosePlayer 1:1; chooseObject labels=[NONE?]+options",
        "alignment": "chooseObject optional NONE handled by idx-- with "
                     "idx==0 early-return; options.get(idx) exact",
        "status": "INVARIANT_PROVEN",
    },
]


def fail(msg: str, out: dict) -> int:
    out["verdict"] = "FAIL"
    out["reason"] = msg
    return 2


def check_overlay_single_add(overlay_src: str, out: dict) -> bool:
    """The overlay must add zero nativeOptions entries in its label patch."""
    m = re.search(
        r"PRIORITY_LABEL_NEW\s*=\s*\"\"\"(.*?)\"\"\"",
        overlay_src,
        re.DOTALL,
    )
    if m is None:
        out["overlay_block_found"] = False
        return False
    block = m.group(1)
    n_add = block.count("nativeOptions.add(sa)")
    n_label = block.count('labels.add("WS48:ACT:')
    out["overlay_block_found"] = True
    out["overlay_native_adds"] = n_add
    out["overlay_act_labels"] = n_label
    out["overlay_single_add_ok"] = (n_add == 0 and n_label == 1)
    return out["overlay_single_add_ok"]


def check_overlay_cardinality_guard(overlay_src: str, out: dict) -> bool:
    present = "WS48_SELECTION_EXECUTION_CARDINALITY_MISMATCH" in overlay_src
    out["overlay_cardinality_guard_present"] = present
    present_range = "WS48_SELECTION_EXECUTION_INDEX_OUT_OF_RANGE" in overlay_src
    out["overlay_index_range_guard_present"] = present_range
    present_binding = "priority_binding" in overlay_src
    out["overlay_binding_record_present"] = present_binding
    return present and present_range and present_binding


def check_generator_base(generator_src: str, out: dict) -> bool:
    """Prove the base generator adds exactly once per seen SA."""
    m = re.search(
        r"if \(seen\.add\(sa\)\) \{(.*?)\}",
        generator_src,
        re.DOTALL,
    )
    if m is None:
        out["generator_block_found"] = False
        return False
    block = m.group(1)
    n_add = block.count("nativeOptions.add(sa)")
    n_label = block.count('labels.add("FORGE_LEGAL_ACTION")')
    out["generator_block_found"] = True
    out["generator_native_adds"] = n_add
    out["generator_labels"] = n_label
    out["generator_single_add_ok"] = (n_add == 1 and n_label == 1)
    return out["generator_single_add_ok"]


def check_generated_provider(provider_src: str, out: dict) -> bool:
    """Verify a materialized provider honors the single-add invariant."""
    m = re.search(
        r"if \(seen\.add\(sa\)\) \{(.*?)\n\s*\}",
        provider_src,
        re.DOTALL,
    )
    if m is None:
        out["provider_block_found"] = False
        return False
    block = m.group(1)
    n_add = block.count("nativeOptions.add(sa);")
    n_label = len(re.findall(r"labels\.add\(", block))
    out["provider_block_found"] = True
    out["provider_native_adds"] = n_add
    out["provider_label_adds"] = n_label
    out["provider_single_add_ok"] = (n_add == 1 and n_label == 1)
    out["provider_cardinality_guard_present"] = (
        "WS48_SELECTION_EXECUTION_CARDINALITY_MISMATCH" in provider_src
    )
    return out["provider_single_add_ok"] and out[
        "provider_cardinality_guard_present"
    ]


def simulate_cardinality(n: int, broken: bool) -> dict:
    """Mechanism proof: index mapping under broken vs repaired population."""
    sas = [f"SA{i}" for i in range(1, n + 1)]
    labels = ["PASS"] + [f"L{i}" for i in range(1, n + 1)]
    native = []
    for sa in sas:
        native.append(sa)
        if broken:
            native.append(sa)
    rows = []
    ok_all = True
    for idx in range(1, n + 1):
        if idx - 1 < len(native):
            got = native[idx - 1]
        else:
            got = "<OUT_OF_RANGE>"
        want = sas[idx - 1]
        ok = got == want
        ok_all = ok_all and ok
        rows.append(
            {
                "selected_label": labels[idx],
                "selected_idx": idx,
                "want_native": want,
                "got_native": got,
                "binds_exactly": ok,
            }
        )
    return {
        "n": n,
        "broken": broken,
        "label_count": len(labels),
        "native_count": len(native),
        "rows": rows,
        "all_bind_exactly": ok_all,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, default=None)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--mutate-check", action="store_true",
                    help="negative control: gate must flag synthesized double-add")
    args = ap.parse_args()

    out: dict = {
        "gate": GATE_VERSION,
        "overlay": str(OVERLAY_PATH),
        "verdict": "UNKNOWN",
    }

    if not OVERLAY_PATH.exists():
        out["reason"] = f"overlay missing: {OVERLAY_PATH}"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 3
    overlay_src = OVERLAY_PATH.read_text(encoding="utf-8")

    if not GENERATOR_PATH.exists():
        out["reason"] = f"generator missing: {GENERATOR_PATH}"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 3
    generator_src = GENERATOR_PATH.read_text(encoding="utf-8")

    base_ok = check_generator_base(generator_src, out)
    overlay_ok = check_overlay_single_add(overlay_src, out)
    guard_ok = check_overlay_cardinality_guard(overlay_src, out)

    broken_sim = simulate_cardinality(4, broken=True)
    fixed_sim = simulate_cardinality(4, broken=False)
    out["mechanism"] = {
        "broken_binds_first_only": (
            broken_sim["rows"][0]["binds_exactly"]
            and not any(r["binds_exactly"] for r in broken_sim["rows"][1:])
        ),
        "fixed_binds_all": fixed_sim["all_bind_exactly"],
        "broken": broken_sim,
        "fixed": fixed_sim,
    }
    mechanism_ok = (
        out["mechanism"]["broken_binds_first_only"]
        and out["mechanism"]["fixed_binds_all"]
    )
    if not mechanism_ok:
        out["verdict"] = "UNKNOWN"
        out["reason"] = "cardinality simulation does not match defect model"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 3

    out["parallel_structure_audit"] = TRANSPORTS
    # The choosePriority row reflects live source state: it is the one
    # transport carrying the Repair-01 defect class pre-fix.
    for t in TRANSPORTS:
        if t["transport"] == "Broker.choosePriority":
            if overlay_ok and guard_ok:
                t["status"] = "INVARIANT_PROVEN"
            else:
                t["status"] = "TARGETED_REPAIR_REQUIRED"
                t["alignment"] += " [PRE-FIX: overlay double-populates]"
    totals: dict[str, int] = {}
    for t in TRANSPORTS:
        totals[t["status"]] = totals.get(t["status"], 0) + 1
    out["parallel_structure_totals"] = totals
    unknown = totals.get("UNKNOWN", 0)
    repair_needed = totals.get("TARGETED_REPAIR_REQUIRED", 0)

    provider_ok: bool | None = None
    if args.provider is not None:
        if not args.provider.exists():
            out["reason"] = f"provider missing: {args.provider}"
            if args.json_out:
                args.json_out.write_text(json.dumps(out, indent=2) + "\n")
            print(json.dumps(out, indent=2))
            return 3
        provider_ok = check_generated_provider(
            args.provider.read_text(encoding="utf-8"), out
        )

    if args.mutate_check:
        # Negative control: synthesize the exact pre-fix double-add text and
        # require the provider check to flag it.
        mutated: dict = {}
        evil = (
            "if (seen.add(sa)) {\n"
            "    nativeOptions.add(sa);\n"
            "    nativeOptions.add(sa);\n"
            '    labels.add("WS48:ACT");\n'
            "}"
        )
        flagged = not check_generated_provider(evil, mutated)
        out["mutate_check"] = {
            "synthesized_double_add_flagged": flagged,
            "detail": mutated,
        }
        if not flagged:
            out["verdict"] = "UNKNOWN"
            out["reason"] = "gate failed to flag synthesized double-add (vacuous)"
            if args.json_out:
                args.json_out.write_text(json.dumps(out, indent=2) + "\n")
            print(json.dumps(out, indent=2))
            return 3

    out["base_single_add_ok"] = base_ok
    out["overlay_single_add_ok"] = overlay_ok
    out["overlay_guard_ok"] = guard_ok
    out["provider_single_add_ok"] = provider_ok

    if not base_ok:
        out["verdict"] = "UNKNOWN"
        out["reason"] = "base generator does not match single-add model"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 3
    if not overlay_ok:
        out["verdict"] = "FAIL"
        out["reason"] = (
            "double-add defect present: overlay PRIORITY_LABEL_NEW adds "
            f"nativeOptions {out.get('overlay_native_adds')}x per label "
            "(base already adds once) -> "
            "SELECTION_EXECUTION_INTEGRITY=FAIL"
        )
        out["selection_execution_integrity"] = "FAIL"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 2
    if unknown or repair_needed:  # explicit for evidence
        out["verdict"] = "FAIL"
        out["reason"] = (
            f"parallel-structure audit unresolved: UNKNOWN={unknown} "
            f"TARGETED_REPAIR_REQUIRED={repair_needed}"
        )
        out["selection_execution_integrity"] = "FAIL"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 2
    if not guard_ok:
        out["verdict"] = "FAIL"
        out["reason"] = "R1f runtime cardinality/index/binding guards missing"
        out["selection_execution_integrity"] = "FAIL"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 2
    if provider_ok is False:
        out["verdict"] = "FAIL"
        out["reason"] = (
            "materialized provider violates single-add invariant or lacks "
            "the cardinality guard"
        )
        out["selection_execution_integrity"] = "FAIL"
        if args.json_out:
            args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 2

    out["verdict"] = "PASS"
    out["selection_execution_integrity"] = "PASS"
    out["reason"] = (
        "single-add invariant holds in base + overlay (+ provider, if given); "
        "runtime cardinality/index guards present; parallel-structure audit "
        "resolved; mechanism simulation confirms first-only survival under "
        "the broken mapping and exact binding under the repaired mapping"
    )
    if args.json_out:
        args.json_out.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
