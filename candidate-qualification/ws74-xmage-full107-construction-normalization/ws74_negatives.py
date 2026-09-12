#!/usr/bin/env python3
"""WS74 G49-08-class adversarial normalization controls (staging only).

Plants 8 defect classes into copies of genuine construction readbacks (plus
denominator/binding tampers) and requires the independent normalizer to
detect every one fail-closed with an exact code. Each control imports no
historical PASS credit; detection must come from live comparison.

Controls:
  N1 wrong player/seat ......... active_seat retargeted (P1->P2)
  N2 object identity mismatch .. native card name swapped (Bolt->Shock)
  N3 wrong zone ................ placed object zone rewritten (hand->graveyard)
  N4 wrong controller/owner .... controller UUID swapped to another seat
  N5 hidden-card identity exposure: honey name injected into unentitled view
  N6 stale/incorrect semantic handle: ledger native_id rewired to wrong UUID
  N7 denominator tamper ........ requested digest replaced (denominator drift)
  N8 readback echo / expected-state substitution:
     N8a record-shaped input as readback (no native sections)
     N8b zones overwritten while ledger UUIDs broken (inconsistent forgery)

Every planted defect must yield NORMALIZATION_FAIL (or UNKNOWN only where
no readback exists, which never applies here) with a defect-specific code.
Verdict NORMALIZATION_NEGATIVES=PASS iff 8/8 control families detected
(N8 counts once; both variants must be detected).
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

RUNDIR = HERE / ".scratch" / "run-main7"


def load(fid):
    return json.loads((RUNDIR / (fid + ".json")).read_text())


def native_uuids(rb):
    out = set()
    for pid, p in rb.get("players", {}).items():
        for zone, entries in p.get("zones", {}).items():
            if isinstance(entries, dict):
                continue
            for e in entries:
                if isinstance(e, dict) and e.get("uuid"):
                    out.add(e["uuid"])
    return out


def other_seat_uuid(rb, seat_pid):
    for pid, p in rb.get("players", {}).items():
        if pid != seat_pid:
            return p["native_uuid"]
    return None


def run_normalizer_on(rb_map):
    """Feed tampered readbacks through ws74_normalize core in-process.

    Imports the normalizer MODULE (not constructor assembly): the controls
    execute the same committed normalization code path as validation.
    """
    import ws74_normalize as N

    by_id, ids = N.load_contract()
    results = {}
    for fid, rb in rb_map.items():
        record = by_id[fid]
        result, code, _digest, _proj, _diffs, _carried, _exp = N.adjudicate_one(record, rb)
        results[fid] = (result, code)
    return results


CONTROLS = []


def control(cid, description, expect):
    def deco(fn):
        CONTROLS.append({"id": cid, "description": description, "expect": expect, "fn": fn})
        return fn

    return deco


@control("N1", "wrong player/seat (active_seat P1->P2)", "temporal.active_player")
def _(rb):
    # clean-PASS base so the planted defect is the first diff
    rb = copy.deepcopy(rb)
    rb["game"]["active_seat"] = 2
    return {"NEGATIVE_FIRST_OPTION": rb}


@control("N2", "object identity mismatch (Bolt name swapped)", "card_identity")
def _(rb):
    rb = copy.deepcopy(rb)
    for e in rb["players"]["P1"]["zones"]["hand"]:
        if e.get("name") == "Lightning Bolt":
            e["name"] = "Shock"
    return {"PILOT_TARGET": rb}


@control("N3", "wrong zone (hand object rewritten to graveyard section)", "zone")
def _(rb):
    rb = copy.deepcopy(rb)
    hand = rb["players"]["P1"]["zones"]["hand"]
    moved = [e for e in hand if e.get("name") == "Lightning Bolt"]
    rb["players"]["P1"]["zones"]["hand"] = [e for e in hand if e.get("name") != "Lightning Bolt"]
    rb["players"]["P1"]["zones"]["graveyard"].extend(moved)
    return {"PILOT_TARGET": rb}


@control("N4", "wrong controller (battlefield controller swapped seat)", "controller")
def _(rb):
    rb = copy.deepcopy(rb)
    bf = rb["players"]["P1"]["zones"]["battlefield"]
    swap = other_seat_uuid(rb, "P1")
    for e in bf:
        e["controller"] = swap
    return {"PILOT_TARGET": rb}


@control("N5", "hidden-card identity exposure (honey name into unentitled view)", "HIDDEN_EXPOSURE")
def _(rb):
    rb = copy.deepcopy(rb)
    # HIDDEN_01: Demonic Tutor (P2 honey) injected into P1's hand view
    p1hand = rb["views"]["P1"]["zones"]["P2"]["hand"]
    assert isinstance(p1hand, dict) and p1hand.get("hidden"), "control precondition"
    rb["views"]["P1"]["zones"]["P2"]["hand"] = [
        {"uuid": "00000000-0000-0000-0000-000000000000", "name": "Demonic Tutor"}
    ]
    return {"HIDDEN_01": rb}


@control("N6", "stale semantic handle (ledger rewired to dangling UUID)", "LEDGER_UNRESOLVED")
def _(rb):
    rb = copy.deepcopy(rb)
    for e in rb["construction"]["placement_ledger"]:
        if e["semantic_id"] == "obj:pilot-bolt":
            e["native_id"] = "00000000-0000-0000-0000-000000000000"
    return {"PILOT_TARGET": rb}


@control("N7", "denominator tamper (requested digest replaced)", "DENOMINATOR_DRIFT")
def _(rb):
    rb = copy.deepcopy(rb)
    rb["contract_digest"] = "0" * 64
    return {"NEGATIVE_FIRST_OPTION": rb}


@control("N8a", "echo: record-shaped input as readback", "ECHO_NO_NATIVE_SECTIONS")
def _(_rb):
    import ws74_normalize as N

    by_id, _ = N.load_contract()
    fake = copy.deepcopy(by_id["PILOT_TARGET"])
    # Pass the digest gate so the echo detector itself is exercised.
    fake["contract_digest"] = by_id["PILOT_TARGET"]["requested_state_digest"]
    fake["construction"] = {"result": "CONSTRUCTED"}
    return {"PILOT_TARGET": fake}


@control("N8b", "echo: zones forged with broken ledger consistency", "ECHO_SUBSTITUTION")
def _(rb):
    rb = copy.deepcopy(rb)
    # Drop the bolt's native card from zones but keep the ledger entry.
    rb["players"]["P1"]["zones"]["hand"] = [
        e for e in rb["players"]["P1"]["zones"]["hand"] if e.get("name") != "Lightning Bolt"
    ]
    return {"PILOT_TARGET": rb}


def main() -> int:
    base = {
        "PILOT_TARGET": load("PILOT_TARGET"),
        "HIDDEN_01": load("HIDDEN_01"),
        "NEGATIVE_FIRST_OPTION": load("NEGATIVE_FIRST_OPTION"),
    }
    rows = []
    detected = 0
    for c in CONTROLS:
        if c["id"] == "N5":
            tampered = c["fn"](base["HIDDEN_01"])
        elif c["id"] == "N8a":
            tampered = c["fn"](None)
        elif c["id"] in ("N1", "N7"):
            tampered = c["fn"](base["NEGATIVE_FIRST_OPTION"])
        else:
            tampered = c["fn"](base["PILOT_TARGET"])
        got = run_normalizer_on(tampered)
        fid = next(iter(tampered))
        result, code = got[fid]
        hit = result == "NORMALIZATION_FAIL" and c["expect"].lower() in code.lower()
        rows.append(
            {
                "control": c["id"],
                "description": c["description"],
                "fixture": fid,
                "result": result,
                "code": code,
                "expected_code_contains": c["expect"],
                "detected_fail_closed": hit,
            }
        )
        print("%s %-60s -> %s %s detected=%s" % (c["id"], c["description"][:60], result, code[:70], hit))
        if hit:
            detected += 1
    # N8a+N8b collapse to one family verdict (both must detect)
    families = {}
    for r in rows:
        fam = r["control"][:2]
        families.setdefault(fam, []).append(r["detected_fail_closed"])
    fam_pass = sum(1 for f, v in families.items() if all(v))
    verdict = "PASS" if fam_pass == 8 and detected == len(rows) else "FAIL"
    payload = {
        "schema": "ws74.normalization-negative-controls.v1",
        "evidence_class": "CODE_DERIVED",
        "controls": rows,
        "families_detected": fam_pass,
        "families_required": 8,
        "verdict": verdict,
    }
    (HERE / "NORMALIZATION_NEGATIVE_CONTROLS.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print("NORMALIZATION_NEGATIVES=%s (%d/8 families)" % (verdict, fam_pass))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
