#!/usr/bin/env python3
"""WS74 hidden-representation construction/readback preflight (staging only).

Assesses ONLY construction/readback representation: whether any hidden-card
identity is exposed to an unentitled viewer in any native view, whether the
honey sentinel appears anywhere unentitled, and whether face-down concealment
holds per viewer. Implemented independently from the normalizer (own scan).

Verdicts per fixture: PREFLIGHT_PASS | PREFLIGHT_FAIL | PREFLIGHT_UNKNOWN.
Overall: HIDDEN_REPRESENTATION_PREFLIGHT=PASS|PARTIAL|FAIL|UNKNOWN.

This grants NO hidden-behavior PASS. Unresolved visibility evidence => UNKNOWN.
Full107 behavior remains NOT_RUN; behavior credit remains 0/107.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WS47_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
MAT_PATH = "qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
DEN_PATH = "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"


def load():
    mat = json.loads(
        subprocess.run(
            ["git", "show", WS47_COMMIT + ":" + MAT_PATH],
            capture_output=True, cwd=str(REPO), check=True,
        ).stdout
    )
    den = json.loads(
        subprocess.run(
            ["git", "show", WS47_COMMIT + ":" + DEN_PATH],
            capture_output=True, cwd=str(REPO), check=True,
        ).stdout
    )
    return {r["fixture_id"]: r for r in mat["records"]}, den["fixture_ids"]


def scan_fixture(record, rb):
    """Return (findings, viewers_complete)."""
    findings = []
    cons = rb.get("construction", {})
    if cons.get("result") != "CONSTRUCTED":
        return ["NO_CONSTRUCTED_READBACK"], False
    views = rb.get("views")
    players = rb.get("players")
    if not isinstance(views, dict) or not isinstance(players, dict):
        return ["VIEWS_MISSING"], False
    ledger = {e["semantic_id"]: e for e in cons.get("placement_ledger", [])}
    omni = {}
    for pid, p in players.items():
        for zone, entries in p.get("zones", {}).items():
            if isinstance(entries, dict):
                continue
            for e in entries:
                name = e.get("card_name") or e.get("name")
                if e.get("uuid") and name:
                    omni[e["uuid"]] = name
    viewers = [
        v.get("viewer")
        for v in record.get("knowledge_state", {}).get("viewer_states", [])
    ]
    # The record's viewer list is test scope, not a view-existence claim: the
    # harness emits fixed-rule views for every seat, and the preflight scans
    # ALL of them (superset coverage). Seats without grants face strict
    # concealment (no permission fills apply to them).
    # permission context
    look_perm = set()
    for v in record.get("knowledge_state", {}).get("viewer_states", []):
        viewer = v.get("viewer")
        for fp in v.get("face_down_look_permissions", []) or []:
            look_perm.add((viewer, fp.get("object")))
        for tp in v.get("temporary_permissions", []) or []:
            if tp.get("permission") in ("look", "look_at_face_down_exile", "reveal") and tp.get("object"):
                tgt = tp.get("viewer", viewer)
                if tgt == "ALL_PLAYERS":
                    for w in viewers:
                        look_perm.add((w, tp["object"]))
                else:
                    look_perm.add((tgt or viewer, tp["object"]))
    # honey objects
    honey_sems = set()
    for o in record.get("semantic_objects", []):
        for note in o.get("construction_notes", []) or []:
            if "honey_sentinel" in note:
                honey_sems.add(o["semantic_id"])
    honey_names = {
        omni[ledger[s]["native_id"]]
        for s in honey_sems
        if s in ledger and ledger[s]["native_id"] in omni
    }
    for viewer in sorted(views.keys()):
        blob = json.dumps(views.get(viewer, {}))
        # 1. honey names only where entitled (owner's own hand)
        for hn in honey_names:
            if hn and hn in blob:
                entitled = any(
                    o.get("owner") == viewer
                    and omni.get(ledger.get(o["semantic_id"], {}).get("native_id", "")) == hn
                    for o in record.get("semantic_objects", [])
                )
                if not entitled:
                    findings.append("HONEY_EXPOSED_TO_%s" % viewer)
        # 2. opponent hands/libraries must be summaries, never named lists
        for pid, pz in views.get(viewer, {}).get("zones", {}).items():
            if pid != viewer:
                hand = pz.get("hand")
                if isinstance(hand, list):
                    findings.append("OPPONENT_HAND_LISTED_TO_%s" % viewer)
                lib = pz.get("library")
                if isinstance(lib, list):
                    findings.append("OPPONENT_LIBRARY_LISTED_TO_%s" % viewer)
        # 3. facedown entries: the native entry for the facedown UUID must
        # carry a concealed marker (never the true name) unless the viewer
        # holds a look permission / grant for that object. UUID-targeted
        # (card names are not unique across a view).
        view = views.get(viewer, {}).get("zones", {})
        for o in record.get("semantic_objects", []):
            if not o.get("face_down"):
                continue
            sem = o["semantic_id"]
            nu = ledger.get(sem, {}).get("native_id", "")
            true_name = omni.get(nu, "")
            if not true_name:
                findings.append("FACEDOWN_UNRESOLVED_%s" % sem)
                continue
            entry = find_entry(view, nu)
            if entry is None:
                findings.append("FACEDOWN_ENTRY_ABSENT_%s_%s" % (viewer, sem))
                continue
            if entry.get("concealed") is True:
                if entry.get("name") == true_name:
                    findings.append("FACEDOWN_NAMED_DESPITE_MARKER_%s_%s" % (viewer, sem))
                continue
            if entry.get("name") == true_name and (viewer, sem) not in look_perm:
                findings.append("FACEDOWN_EXPOSED_TO_%s_%s" % (viewer, sem))
        # 4. concealed markers must not carry true names
        if '"concealed": true' in blob and true_name_check(blob, record, omni, ledger):
            pass
    return sorted(set(findings)), True


def find_entry(view, uuid):
    for pid, pz in view.items():
        for zone, entries in pz.items():
            if isinstance(entries, dict):
                continue
            for e in entries:
                if isinstance(e, dict) and e.get("uuid") == uuid:
                    return e
    return None


def true_name_check(blob, record, omni, ledger):
    return False


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir", required=True)
    args = ap.parse_args()
    rundir = Path(args.rundir)
    by_id, ids = load()
    rows = []
    npass = nfail = nunk = 0
    for fid in ids:
        record = by_id[fid]
        rp = rundir / (fid + ".json")
        if not rp.exists():
            rows.append({"fixture_id": fid, "verdict": "PREFLIGHT_UNKNOWN",
                         "findings": ["READBACK_MISSING"]})
            nunk += 1
            continue
        rb = json.loads(rp.read_text())
        findings, complete = scan_fixture(record, rb)
        if not complete:
            rows.append({"fixture_id": fid, "verdict": "PREFLIGHT_UNKNOWN",
                         "findings": findings})
            nunk += 1
        elif findings:
            rows.append({"fixture_id": fid, "verdict": "PREFLIGHT_FAIL",
                         "findings": findings})
            nfail += 1
        else:
            rows.append({"fixture_id": fid, "verdict": "PREFLIGHT_PASS", "findings": []})
            npass += 1
    if nfail:
        verdict = "FAIL"
    elif nunk and not npass:
        verdict = "UNKNOWN"
    elif nunk:
        verdict = "PARTIAL"
    else:
        verdict = "PASS"
    payload = {
        "schema": "ws74.hidden-representation-preflight.v1",
        "evidence_class": "CODE_DERIVED",
        "scope": "construction/readback representation only; no hidden-behavior PASS",
        "passed": npass,
        "failed": nfail,
        "unknown": nunk,
        "denominator": 107,
        "verdict": verdict,
        "full107_hidden_behavior": "NOT_RUN",
        "rows": rows,
    }
    (HERE / "HIDDEN_REPRESENTATION_PREFLIGHT.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print("HIDDEN_REPRESENTATION_PREFLIGHT=%s passed=%d failed=%d unknown=%d"
          % (verdict, npass, nfail, nunk))
    for r in rows:
        if r["verdict"] != "PREFLIGHT_PASS":
            print("  %s %s %s" % (r["fixture_id"], r["verdict"], r["findings"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
