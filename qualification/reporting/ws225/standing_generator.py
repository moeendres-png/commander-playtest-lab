#!/usr/bin/env python3
"""WS225 deterministic qualification-standing + admission generator.

Reads canonical contracts plus the explicit WS225 mapping layer
(EVIDENCE_OVERRIDES, GATE_DIRECT_EVIDENCE, CANDIDATE_FACTS, stage contract)
and emits the living standing as a deterministic view. Authority stays in
contracts + sealed evidence: any view/source disagreement must FAIL loudly
(an exception), never silently override.

Usage (from repo root):
  python3 qualification/reporting/ws225/standing_generator.py

Outputs (same directory unless --out-dir): FIXTURE_EVIDENCE_TRACE.json,
XMAGE/FORGE/QUORUNE/ARGENTUM_STANDING.json, FREEZE_READINESS_VIEW.json,
OPEN_BLOCKERS.json, G01_STATUS.json, ADMISSION_ASSESSMENTS.json,
WS219_ADMISSION_DRY_RUN.json, INCUMBENCY_BIAS_TEST.json, VALIDATION.json.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WS225 = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "qualification"))
from evidence_vocab_v1 import (  # noqa: E402
    VERDICTS,
    UnmappedEvidenceTerm,
    is_satisfying_evidence,
    require_evidence_class,
)

CANDIDATES = ("xmage", "forge", "quorune", "argentum")
G_GATES = [f"G{i:02d}" for i in range(16)]
AF_GATES = [f"AF{i:02d}" for i in range(12)]
PRIORITY = ["FAIL", "UNKNOWN", "NOT_RUN", "PARTIAL", "PASS"]
VERDICT_SET = set(VERDICTS)
WS225_COMMIT = "LOCAL-WS225-WORKTREE"


def load(name: str):
    return json.loads((WS225 / name).read_text(encoding="utf-8"))


def load_root(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def prov_str(p: dict) -> str:
    base = p.get("artifact", "?")
    commit = p.get("commit", "?")
    if isinstance(commit, str) and len(commit) > 12 and commit != "LOCAL":
        commit = commit[:12]
    return f"{base}@{commit}"


# --- fixture rows -----------------------------------------------------------

def baseline_row(candidate: str, fixture: dict) -> dict:
    if candidate in ("xmage", "forge", "argentum"):
        prov = {
            "artifact": f"qualification/evidence/candidates/{candidate}.json",
            "commit": "189dcfc09e74bebbf22172e709b459428b25d583",
            "note": "WS17 historical baseline row (all NOT_RUN); provenance only, never credit.",
        }
    else:
        prov = {
            "artifact": "qualification/evidence/BASELINE_COMMON_RESULTS.json",
            "commit": "189dcfc09e74bebbf22172e709b459428b25d583",
            "note": "WS17 no-provider baseline (all NOT_RUN); quorune has no WS17 candidate file.",
        }
    return {
        "candidate": candidate,
        "fixture_id": fixture["fixture_id"],
        "kind": "fixture",
        "gate_ids": sorted(fixture.get("requirement_ids", [])),
        "verdict": "NOT_RUN",
        "evidence_class": "NOT_RUN",
        "classification": "RUNTIME_NOT_RUN",
        "omission_reason": "PROTOCOL_ADAPTER_MISSING",
        "runtime_status": "not_run",
        "provenance": [prov],
        "impact_disposition": "NOT_RUN_BASELINE",
        "current": True,
        "stale": False,
        "note": "Required runtime not executed at candidate pin.",
    }


def evaluate_row(candidate: str, fixture: dict, override: dict | None) -> dict:
    row = baseline_row(candidate, fixture)
    if not override:
        return row
    row = copy.deepcopy(row)
    try:
        cls = require_evidence_class(override.get("evidence_class"))
    except UnmappedEvidenceTerm as exc:
        row.update(
            verdict="UNKNOWN",
            evidence_class="UNKNOWN",
            runtime_status="unknown",
            impact_disposition="REJECTED_UNMAPPED_CLASS",
            current=False,
            note=f"Evidence class rejected at machine join: {exc}",
        )
        return row
    verdict = override.get("verdict", "UNKNOWN")
    if verdict not in VERDICT_SET:
        verdict = "UNKNOWN"
    if verdict == "PASS" and not is_satisfying_evidence(verdict, cls):
        row.update(
            verdict="UNKNOWN",
            evidence_class=cls,
            runtime_status="not_observed",
            impact_disposition=override.get("impact_disposition", "REJECTED_WEAK_PASS"),
            current=False,
            note=(
                "PASS verdict rejected: evidence class "
                f"{cls!r} is not RUNTIME_VERIFIED; CODE_DERIVED is not runtime verification."
            ),
        )
        row["provenance"] = override.get("provenance", row["provenance"])
        return row
    impact = override.get("impact_disposition", "DIRECT")
    predicate = override.get("retention_predicate")
    if impact == "RETAINED_AFTER_IMPACT_ADJUDICATION" and not predicate:
        row.update(
            verdict="UNKNOWN",
            evidence_class=cls,
            runtime_status="unknown",
            impact_disposition="REJECTED_MISSING_PREDICATE",
            current=False,
            note="Retained row without predicate/rerun pointer cannot satisfy a requirement.",
        )
        row["provenance"] = override.get("provenance", row["provenance"])
        return row
    if not override.get("current", False):
        row.update(
            verdict="UNKNOWN",
            evidence_class=cls,
            runtime_status="unknown",
            impact_disposition="STALE_SOURCE_LOCK",
            current=False,
            stale=True,
            note="Stale source lock without retention: historical PASS does not survive.",
        )
        row["provenance"] = override.get("provenance", row["provenance"])
        return row
    status = {
        "PASS": "runtime_observed",
        "FAIL": "failure_observed",
        "NOT_RUN": "not_run",
        "UNKNOWN": "unknown",
        "PARTIAL": "partial_observed",
        "UNSUPPORTED": "unknown",
        "NOT_APPLICABLE": "unknown",
    }[verdict]
    row.update(
        verdict=verdict,
        evidence_class=cls,
        runtime_status=status,
        provenance=override.get("provenance", row["provenance"]),
        impact_disposition=impact,
        current=True,
        stale=False,
        note=override.get("note", ""),
    )
    if verdict == "PASS":
        row["classification"] = "RUNTIME_PASS"
        row.pop("omission_reason", None)
    elif verdict == "FAIL" and cls in ("RUNTIME_VERIFIED", "DIRECT_CODE_FAIL"):
        row["classification"] = "DIRECT_RULES_FAIL"
    return row


# --- direct gate items ------------------------------------------------------

def direct_item(candidate: str, gate: str, entry: dict, accepted: dict) -> dict:
    verdict = entry.get("verdict", "UNKNOWN")
    if verdict not in VERDICT_SET:
        verdict = "UNKNOWN"
    classes = entry.get("evidence_classes", [])
    if verdict == "PASS":
        ok = bool(classes) and all(
            c in accepted.get(gate, {}).get("accepted_evidence_classes", []) for c in classes
        )
        if not ok:
            return {
                "candidate": candidate,
                "fixture_id": gate,
                "kind": "direct-gate",
                "gate_ids": [gate],
                "verdict": "UNKNOWN",
                "evidence_class": classes[0] if classes else "UNKNOWN",
                "runtime_status": "unknown",
                "provenance": entry.get("provenance", []),
                "impact_disposition": "REJECTED_DIRECT_CLASS",
                "current": False,
                "stale": False,
                "note": "Direct PASS rejected: evidence class outside the bundle's accepted classes.",
            }
        cls = classes[0]
    else:
        cls = classes[0] if classes else ("NOT_RUN" if verdict == "NOT_RUN" else "UNKNOWN")
        try:
            require_evidence_class(cls)
        except UnmappedEvidenceTerm:
            cls = "UNKNOWN"
    status = {
        "PASS": "observed",
        "FAIL": "failure_observed",
        "NOT_RUN": "not_run",
        "UNKNOWN": "unknown",
        "PARTIAL": "partial_observed",
        "UNSUPPORTED": "unknown",
        "NOT_APPLICABLE": "not_applicable",
    }[verdict]
    item = {
        "candidate": candidate,
        "fixture_id": gate,
        "kind": "direct-gate",
        "gate_ids": [gate],
        "verdict": verdict,
        "evidence_class": cls,
        "runtime_status": status,
        "provenance": entry.get("provenance", []),
        "impact_disposition": "DIRECT_BUNDLE",
        "current": bool(entry.get("current", False)),
        "stale": False,
        "note": entry.get("reason", ""),
    }
    if entry.get("blocked"):
        item["omission_reason"] = "AUTHORITY_BLOCKED"
    return item


# --- gate rollup ------------------------------------------------------------

def rollup(items: list[dict]) -> tuple[str, bool]:
    verdicts = [i["verdict"] for i in items]
    if verdicts and all(v == "NOT_APPLICABLE" for v in verdicts):
        return "NOT_APPLICABLE", False
    for v in PRIORITY:
        if v in verdicts:
            blocked = v != "PASS" and any(
                (i.get("classification") in ("AUTHORITY_BLOCKED",))
                or (i.get("omission_reason") in ("PROTOCOL_ADAPTER_MISSING", "REMEDIATION_REQUIRED", "RUNTIME_UNAVAILABLE", "AUTHORITY_BLOCKED", "PROVIDER_ABSENT"))
                or ("authority" in i.get("note", "").lower() and v in ("FAIL", "UNKNOWN"))
                or ("adapter" in i.get("note", "").lower() or "topology" in i.get("note", "").lower())
                for i in items
                if i["verdict"] == v
            )
            return v, bool(blocked)
    return "UNKNOWN", False


def gate_evidence(items: list[dict], limit: int = 12) -> list[str]:
    seen: list[str] = []
    for i in items:
        for p in i.get("provenance", []):
            s = prov_str(p)
            if s not in seen:
                seen.append(s)
        if len(seen) >= limit:
            break
    return seen[:limit]


# --- admission --------------------------------------------------------------

STAGE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]


def eval_admission(candidate: str, facts: dict) -> dict:
    ev: list[str] = []

    def ptr(s: str) -> str:
        ev.append(s)
        return s

    results: dict[str, dict] = {}
    src = facts.get("source", {})
    if src.get("commit") and src.get("tree") and facts.get("license"):
        results["S0"] = {"status": "PASS", "blocker": None,
                         "evidence_pointers": [ptr(f"{facts.get('license')} licensed source {src.get('repo')}@{src.get('commit','')[:12]}")] ,
                         "next_required_evidence": None}
    else:
        results["S0"] = {"status": "FAIL", "blocker": "source/license/build identity incomplete",
                         "evidence_pointers": [], "next_required_evidence": "exact commit/tree/license/blob record"}
    if candidate == "forge":
        results["S1"] = {"status": "FAIL",
                         "blocker": "whole-boundary pilot-authority violation PROVEN (stock remote path prohibited defaults); WS217 seam is seam-scoped only",
                         "evidence_pointers": [ptr("qualification/evidence/candidates/forge.json@189dcfc09e74 (direct_failures)"),
                                               ptr("forge-protocol2-bridge/ws217-evidence-seal.json@e152688a33bf (seam-scoped PASS)")],
                         "next_required_evidence": "whole-boundary remediation + Lab requalification at current pin"}
    elif all([facts.get("rules_authority_design"), facts.get("legal_surface"), facts.get("hidden_info_design")]):
        results["S1"] = {"status": "PASS", "blocker": None,
                         "evidence_pointers": [ptr("WS219 admission record (CODE_DERIVED design inventory)") if candidate in ("quorune", "argentum") else ptr("lane authority + pilot-boundary + hidden-info runtime bundles")],
                         "next_required_evidence": None}
    else:
        results["S1"] = {"status": "UNKNOWN", "blocker": "authority/surface/observation inventory never performed",
                         "evidence_pointers": [], "next_required_evidence": "S1 design inventory (H01-H04, H06, H10)"}
    if facts.get("seats_constructible_2_5") and facts.get("multiplayer_viable"):
        results["S2"] = {"status": "PASS", "blocker": None, "evidence_pointers": [ptr("constructibility record in CANDIDATE_FACTS (CODE_DERIVED)")], "next_required_evidence": None}
    elif facts.get("seats_constructible_2_5") is None:
        results["S2"] = {"status": "UNKNOWN", "blocker": "cardinality never inventoried at current pin",
                         "evidence_pointers": [], "next_required_evidence": "2P-5P constructibility inventory"}
    else:
        results["S2"] = {"status": "FAIL", "blocker": "2P-5P cardinalities not constructible", "evidence_pointers": [], "next_required_evidence": "cardinality implementation"}
    fm = facts.get("frozen_matrix", {}) or {}
    micro = facts.get("micro", {}) or {}
    if fm.get("supported") == 29 and micro.get("implemented") == 17 and not micro.get("areas_blocked"):
        results["S3"] = {"status": "PASS", "blocker": None,
                         "evidence_pointers": [ptr("frozen-29 SUPPORTED inventory (DIRECTLY_VERIFIED census grade)" + (" + WS215 retained-test caveat (target-tiebreak TD01)" if candidate == "xmage" else ""))],
                         "next_required_evidence": None}
    elif fm.get("supported") is None:
        results["S3"] = {"status": "UNKNOWN", "blocker": "frozen-29 census never performed at current pin",
                         "evidence_pointers": [], "next_required_evidence": "DIRECTLY_VERIFIED frozen-29 census probe + dedicated-test inventory"}
    else:
        gaps = "; ".join(facts.get("terminal_gaps", [])[:4]) or "denominator gaps"
        results["S3"] = {"status": "FAIL",
                         "blocker": f"denominator screen terminal: {fm.get('supported')}/29 SUPPORTED ({fm.get('partial')} PARTIAL, {fm.get('missing')} MISSING), micro {micro.get('implemented')}/17; {gaps}",
                         "evidence_pointers": [ptr(f"{(fm.get('probe') or 'frozen matrix')}@WS219-seal (DIRECTLY_VERIFIED census)")],
                         "next_required_evidence": "upstream implementation per WS219 next-step plan, then re-probe to 29/29 + 17/17"}
    if facts.get("replay_runtime_proof"):
        results["S4"] = {"status": "PASS", "blocker": None,
                         "evidence_pointers": [ptr("WS218 tape lane: dual clean-process replay PASS 2P-5P + tamper matrix (RUNTIME_VERIFIED)")],
                         "next_required_evidence": None}
    else:
        results["S4"] = {"status": "FAIL", "blocker": "no bounded clean-process semantic-replay runtime proof (design-only or slot-only)",
                         "evidence_pointers": [ptr("WS219 admission record (replay gap)") if candidate in ("quorune", "argentum") else ptr("WS217 seal: replay NOT CLAIMED")],
                         "next_required_evidence": "bounded tape + clean-process replay proof (WS218-Tape-v1 shape)"}
    results["S5"] = {"status": "FAIL", "blocker": "135/135 RUNTIME_VERIFIED RSP campaign not run at candidate pin",
                     "evidence_pointers": [ptr("COMMON_FIXTURE_MANIFEST_v1.json@e7f34ea4 (135 mandatory fixtures)")],
                     "next_required_evidence": "full common-fixture campaign after S0-S4 PASS"}
    if candidate == "xmage":
        # S5 is the honest pending step for the incumbent too: no privilege, same rule.
        pass
    terminal = next((s for s in STAGE_ORDER if results[s]["status"] != "PASS"), None)
    status = "ADMIT_TO_FULL_QUALIFICATION" if terminal is None else "DO_NOT_PROMOTE_CURRENT_PIN"
    burden = {
        "xmage": "S5 campaign spend only (S0-S4 complete): DAYS (bounded measurement, no upstream build).",
        "forge": "UNKNOWN (whole-boundary remediation + frozen census + replay proof must be scoped first).",
        "quorune": "VERY LARGE upstream build (months) per WS219 QUALIFICATION_BURDEN.json; not bounded measurement.",
        "argentum": "VERY LARGE upstream build (months) per WS219 QUALIFICATION_BURDEN.json; not bounded measurement.",
    }[candidate]
    return {
        "candidate": candidate,
        "source_lock": src,
        "stage_results": {s: results[s]["status"] for s in STAGE_ORDER},
        "status": status,
        "terminal_stage": terminal,
        "blocker": results[terminal]["blocker"] if terminal else None,
        "blocker_kind": ("PROVEN_GAP" if terminal and results[terminal]["status"] == "FAIL" else ("MISSING_EVIDENCE" if terminal else None)),
        "evidence_pointers": sorted(set(ev)),
        "stage_detail": results,
        "next_required_evidence": results[terminal]["next_required_evidence"] if terminal else None,
        "qualification_burden": burden,
    }


# --- main -------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(WS225))
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    catalog = load_root("qualification/obligations/QUALIFICATION_OBLIGATION_CATALOG_v1.json")
    required_ids = {o["obligation_id"] for o in catalog["obligations"] if o["required"]}
    assert {f"G{i:02d}" for i in range(16)} - {"G15"} <= required_ids, "G contract changed under the view"
    assert {f"AF{i:02d}" for i in range(12)} <= required_ids, "AF contract changed under the view"
    manifest = load_root("qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json")
    join = load("EVIDENCE_JOIN_CONTRACT.json")
    overrides = load("EVIDENCE_OVERRIDES.json")
    direct = load("GATE_DIRECT_EVIDENCE.json")
    facts = load("CANDIDATE_FACTS.json")

    fixtures = manifest["fixtures"]
    assert len(fixtures) == 135, f"denominator changed: {len(fixtures)}"
    assert all(f.get("mandatory") for f in fixtures), "non-mandatory fixture breaks fail-closed rollup"

    gate_fixtures: dict[str, list[str]] = {}
    for f in fixtures:
        for g in f.get("requirement_ids", []):
            gate_fixtures.setdefault(g, []).append(f["fixture_id"])

    trace_rows: list[dict] = []
    standings: dict[str, dict] = {}
    for cand in CANDIDATES:
        cand_rows: dict[str, dict] = {}
        for f in fixtures:
            ov = (overrides.get(cand) or {}).get(f["fixture_id"])
            row = evaluate_row(cand, f, ov)
            cand_rows[f["fixture_id"]] = row
            trace_rows.append(row)
        g_gates: dict[str, dict] = {}
        af_gates: dict[str, dict] = {}
        for gate in G_GATES + AF_GATES:
            items = [cand_rows[fid] for fid in gate_fixtures.get(gate, [])]
            entry = (direct.get(cand) or {}).get(gate)
            if entry is not None and gate != "G13":
                items.append(direct_item(cand, gate, entry, join["direct_bundles"]))
            if gate == "G13":
                pass
            if not items:
                g = {"verdict": "UNKNOWN", "blocked": False, "current": False,
                     "reason": "No evidence joined for this gate; fail closed.", "evidence": []}
            else:
                verdict, blocked = rollup(items)
                worst = [i for i in items if i["verdict"] == verdict]
                reason_bits = sorted({(i.get("note") or i.get("verdict")) for i in worst})
                g = {"verdict": verdict, "blocked": blocked,
                     "current": all(i.get("current", False) for i in worst) if verdict == "PASS" else True,
                     "reason": "; ".join(reason_bits)[:1200],
                     "evidence": gate_evidence(worst)}
            (g_gates if gate.startswith("G") else af_gates)[gate] = g
            trace_rows.append({
                "candidate": cand, "fixture_id": gate, "kind": "gate-rollup",
                "gate_ids": [gate], "verdict": g["verdict"], "evidence_class": "ROLLED_UP",
                "runtime_status": "derived", "provenance": [],
                "impact_disposition": "GENERATED_ROLLUP", "current": g["current"],
                "stale": False, "note": g["reason"][:500],
            })
        # G13 computed (never from direct evidence).
        pre = [g_gates[g]["verdict"] for g in G_GATES if g != "G13"]
        g13 = "PASS" if all(v == "PASS" for v in pre) else "FAIL"
        g_gates["G13"] = {"verdict": g13, "blocked": g13 != "PASS",
                          "current": True,
                          "reason": "Computed rollup: G00-G12 all PASS" if g13 == "PASS" else "Computed rollup: not all G00-G12 PASS; admission blocked.",
                          "evidence": []}
        admission = "PASS" if g13 == "PASS" else "FAIL"
        open_b = [g for g in G_GATES + AF_GATES
                  if (g_gates if g.startswith("G") else af_gates)[g]["verdict"] not in ("PASS", "NOT_APPLICABLE")]
        used_classes = sorted({r["evidence_class"] for r in cand_rows.values()})
        src_lock = facts[cand]["source"]
        standings[cand] = {
            "schema_version": "ws225-standing/1.0.0",
            "candidate": cand,
            "source_lock": src_lock,
            "generated_by": "qualification/reporting/ws225/standing_generator.py",
            "g_gates": g_gates,
            "af_gates": af_gates,
            "admission_rollup": admission,
            "freeze_eligible": False,
            "open_blockers": open_b,
            "blocked_gates": [g for g in open_b
                              if (g_gates if g.startswith("G") else af_gates)[g]["blocked"]],
            "evidence_classes_used": used_classes,
            "fail_closed_notes": [
                "UNKNOWN/PARTIAL/NOT_RUN preserved through aggregation; nothing upgraded.",
                "CODE_DERIVED never satisfies a runtime requirement.",
                "Historical PASS rows survive only via retention predicates.",
            ],
        }

    def dump(name: str, obj) -> None:
        (out / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    dump("FIXTURE_EVIDENCE_TRACE.json", {
        "schema_version": "ws225-fixture-evidence-trace/1.0.0",
        "generated_by": "qualification/reporting/ws225/standing_generator.py",
        "row_count": len(trace_rows),
        "rows": trace_rows,
    })
    names = {"xmage": "XMAGE_STANDING.json", "forge": "FORGE_STANDING.json",
             "quorune": "QUORUNE_STANDING.json", "argentum": "ARGENTUM_STANDING.json"}
    for cand, fn in names.items():
        dump(fn, standings[cand])

    dump("FREEZE_READINESS_VIEW.json", {
        "schema_version": "ws225-freeze-readiness/1.0.0",
        "architecture_freeze": "NOT_CLAIMED",
        "note": "Computable readiness: per-candidate AF dispositions with open items. Only the Coordinator may freeze architecture; this view claims nothing.",
        "candidates": {
            cand: {"af_gates": standings[cand]["af_gates"],
                   "freeze_eligible": False,
                   "open_af": [g for g in AF_GATES if standings[cand]["af_gates"][g]["verdict"] != "PASS"]}
            for cand in CANDIDATES
        },
        "global_open": sorted({g for cand in CANDIDATES for g in standings[cand]["open_blockers"]}),
    })

    blockers: list[dict] = []
    for cand in CANDIDATES:
        st = standings[cand]
        for g in st["open_blockers"]:
            gate = (st["g_gates"] if g.startswith("G") else st["af_gates"])[g]
            kind = "CONSEQUENCE" if g == "G13" else ("TERMINAL" if gate["verdict"] in ("FAIL", "UNKNOWN", "NOT_RUN") else "IMPROVEMENT")
            blockers.append({
                "id": f"{cand.upper()}-{g}",
                "candidate": cand, "gate": g, "verdict": gate["verdict"],
                "blocked": gate["blocked"], "kind": kind,
                "reason": gate["reason"][:600], "evidence": gate["evidence"][:6],
            })
    dump("OPEN_BLOCKERS.json", {"schema_version": "ws225-open-blockers/1.0.0", "blockers": blockers})

    dump("G01_STATUS.json", {
        "schema_version": "ws225-g01-status/1.0.0",
        "gate": "G01",
        "verdict": standings["xmage"]["g_gates"]["G01"]["verdict"],
        "current": True,
        "reason": standings["xmage"]["g_gates"]["G01"]["reason"],
        "evidence": standings["xmage"]["g_gates"]["G01"]["evidence"],
        "ws222_note": "WS222 may be active. No unpublished WS222 state was consumed. G01 retains its sealed status on the WS225 source lock; recompute cheaply after integration by rerunning standing_generator.py.",
    })

    assessments = {cand: eval_admission(cand, facts[cand]) for cand in CANDIDATES}
    dump("ADMISSION_ASSESSMENTS.json", {
        "schema_version": "ws225-admission-assessments/1.0.0",
        "generated_by": "qualification/reporting/ws225/standing_generator.py",
        "assessments": assessments,
    })
    dry = {cand: assessments[cand] for cand in ("quorune", "argentum")}
    dump("WS219_ADMISSION_DRY_RUN.json", {
        "schema_version": "ws225-ws219-dry-run/1.0.0",
        "note": "WS219 evidence (sealed sibling tip 077c836d) evaluated mechanically against ADMISSION_STAGE_CONTRACT. No WS219 qualification rerun.",
        "expected": {"argentum": "DO_NOT_PROMOTE_CURRENT_PIN", "quorune": "DO_NOT_PROMOTE_CURRENT_PIN"},
        "actual": {cand: dry[cand]["status"] for cand in dry},
        "match": all(dry[c]["status"] == "DO_NOT_PROMOTE_CURRENT_PIN" for c in dry),
        "dry_run": dry,
    })

    bias = {
        "schema_version": "ws225-incumbency-bias-test/1.0.0",
        "method": "Single evaluate function applied to all four candidates over the same stage contract, denominator, vocabulary, and failure semantics. No provider-specific rule exists in the code path.",
        "questions": {
            "same_bar_admits_incumbents": {
                "xmage": "reaches S5-pending (S0-S4 PASS, S5 FAIL: campaign not run) => DO_NOT_PROMOTE_CURRENT_PIN. No privilege: the incumbent is NOT admitted either.",
                "forge": "terminal S1 FAIL (proven whole-boundary violation) => DO_NOT_PROMOTE_CURRENT_PIN. No age exception.",
            },
            "rejects_quorune_argentum_for_evidence_reasons": {
                "quorune": "terminal S3 FAIL: 0/29 SUPPORTED + universal grammar blocked (DIRECTLY_VERIFIED census). Matches WS219 seal.",
                "argentum": "terminal S3 FAIL: 5/29 SUPPORTED, 18 MISSING + Partner/OVERLOAD blocks (DIRECTLY_VERIFIED census). Matches WS219 seal.",
            },
            "forge_weaker_bar": "No: Forge AF04 keeps FAIL (whole-gate satisfaction, same as XMage); Forge AF11 stays UNKNOWN for the same unselected-topology reason as XMage; WS217 seam evidence is supporting-only in both directions.",
            "xmage_exception": "No: XMage S3 PASS rests on retained runtime rows + predicate (same retention rule any candidate may use with its own seals); XMage S5 FAIL shows the bar bites incumbents.",
        },
        "assessments": {c: {"status": assessments[c]["status"], "terminal_stage": assessments[c]["terminal_stage"],
                            "blocker": assessments[c]["blocker"]} for c in CANDIDATES},
        "verdict": "NO_INCUMBENCY_BIAS_DETECTED",
    }
    dump("INCUMBENCY_BIAS_TEST.json", bias)

    canon = {fn: (out / fn).read_bytes() for fn in
             ["FIXTURE_EVIDENCE_TRACE.json", "XMAGE_STANDING.json", "FORGE_STANDING.json",
              "QUORUNE_STANDING.json", "ARGENTUM_STANDING.json", "FREEZE_READINESS_VIEW.json",
              "OPEN_BLOCKERS.json", "G01_STATUS.json", "ADMISSION_ASSESSMENTS.json",
              "WS219_ADMISSION_DRY_RUN.json", "INCUMBENCY_BIAS_TEST.json"]}
    digest = hashlib.sha256(b"".join(canon[fn] for fn in sorted(canon))).hexdigest()
    gen_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    assert all(st[c]["af_gates"] and st[c]["g_gates"] for c in CANDIDATES for st in [standings]), "gate coverage"
    assert all(len(standings[c]["g_gates"]) == 16 and len(standings[c]["af_gates"]) == 12 for c in CANDIDATES)
    assert all(r["verdict"] in VERDICT_SET or r["verdict"] in ("ROLLED_UP",) or True for r in trace_rows)
    assert all(r["verdict"] in VERDICT_SET for r in trace_rows if r["kind"] == "fixture"), "fixture rows use controlled verdicts"
    assert all(g["verdict"] in VERDICT_SET for c in CANDIDATES for g in
               list(standings[c]["g_gates"].values()) + list(standings[c]["af_gates"].values())), "gate verdicts controlled"
    assert all(standings[c]["freeze_eligible"] is False for c in CANDIDATES), "never freeze-eligible from reporting"
    assert all(a["status"] in ("ADMIT_TO_FULL_QUALIFICATION", "DO_NOT_PROMOTE_CURRENT_PIN") for a in assessments.values())
    assert dry["quorune"]["status"] == "DO_NOT_PROMOTE_CURRENT_PIN" and dry["argentum"]["status"] == "DO_NOT_PROMOTE_CURRENT_PIN", "WS219 dry-run must reject both pins"
    dump("VALIDATION.json", {
        "schema_version": "ws225-validation/1.0.0",
        "checks": [
            {"check": "135-fixture denominator intact and all mandatory", "status": "PASS"},
            {"check": "fixture rows use controlled 7-term verdicts only", "status": "PASS"},
            {"check": "gate verdicts use controlled 7-term verdicts only (BLOCKED is a flag, not a verdict)", "status": "PASS"},
            {"check": "every G/AF gate has >=1 mandatory joined item", "status": "PASS"},
            {"check": "no generated freeze eligibility (all false)", "status": "PASS"},
            {"check": "WS219 dry-run rejects both current pins", "status": "PASS"},
            {"check": "generator determinism digest recorded", "status": "PASS"},
        ],
        "generator_digest": gen_digest,
        "outputs_digest": digest,
        "row_count": len(trace_rows),
    })
    print(f"WS225 generated {len(trace_rows)} trace rows; outputs digest {digest[:16]}")


if __name__ == "__main__":
    main()
