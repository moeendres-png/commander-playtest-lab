#!/usr/bin/env python3
"""WS68 transport-remediation runner shim (WS68-owned, qualification-only).

WS65-verbatim delegation to
candidate-qualification/ws65-forge-rqc3-first-wave/ws65_runner.py (itself
ws64-verbatim + full native tape), EXCEPT the marked WS68 deltas below. No
engine, provider, Decision, or intent semantics change. Grants no behavior
credit by itself (BEHAVIOR_CREDIT=0/107; credit is adjudicated separately in
WS68 evidence from journals).

WS68 DELTA-1 (successor EV dir): COMMANDER_LAB_FORGE_PROVIDER_CMD must
reference /tmp/ws68-ev (fresh WS68 provider build with the payCombatCost +
concession-offer overlay against the exact Forge checkout
/tmp/ws65-forge-src-a9a95db) and must contain no old-pin path. Fails loud
otherwise.

WS68 DELTA-2 (pay_combat_cost family): answer externally-offered
"pay_combat_cost" frames by matching ONLY provider-offered options:
{"decision": "pay"} selects the single WS68:PAYCOMBATCOST:PAY authority
option; {"decision": "decline"} selects DECLINE. Zero-match and multi-match
fail closed. No legality reconstruction, no amount computation, no outcome
injection: the engine owns the cost and the result; the harness only selects
among offered native options. Unscripted pay_combat_cost frames fail closed
(combat-tax disposition is scenario-specific; never defaulted).

WS68 DELTA-3 (concession pilot standing instruction): answer
externally-offered "concession" frames via exact WS65 semantics when a script
entry is due (offered-options-only matching, fail closed otherwise). When NO
script entry is due, the pilot applies its standing instruction -- never
concede except when scripted -- by selecting the single offered DECLINE
option. This is pilot behavior (like passing unscripted priority), not a
provider default: the provider offers both native options every time through
the normal broker frame path, consults native canConcede() first, and never
auto-selects. Pilot declines are counted in WS68_PILOT_DECLINES for evidence.

WS68 DELTA-4: output journals additionally stamp ws68_runner identity
(additive only; never rewrites proof).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS65_DIR = HERE.parent / "ws65-forge-rqc3-first-wave"
WS64_DIR = HERE.parent / "ws64-forge-a04-vertical-path-investigation"
WS62_DIR = HERE.parent / "ws62-forge-successor-requalification"
WS53_DIR = HERE.parent / "ws53-forge-convergence-native-progression"
WS48_DIR = HERE.parent / "ws48-forge-v1.0.5"
sys.path.insert(0, str(WS65_DIR))
sys.path.insert(0, str(WS64_DIR))
sys.path.insert(0, str(WS62_DIR))
sys.path.insert(0, str(WS53_DIR))
sys.path.insert(0, str(WS48_DIR))

import ws65_runner as ws65  # noqa: E402,E401
import run_behavior_transcript_probe as base  # noqa: E402

FORGE_COMMIT = "a9a95db6662c2d28814390a9c0c2f986e39aa8b4"
FORGE_TREE = "2c18327f79e330f2ed167067166ffd42d61b0849"
FORGE_OLD_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"

# Pilot standing-instruction declines (actor, decision_id) for evidence census.
WS68_PILOT_DECLINES: list[tuple[str, str]] = []


def _ws68_due_concession(drv, actor: str, phase, turn) -> list[dict]:
    return [e for e in drv.script
            if e.get("decision_family") == "concession"
            and e.get("actor") == actor
            and (e.get("phases") is None or phase in (e.get("phases") or []))
            and (e.get("turns") is None or turn in (e.get("turns") or []))]


def answer_pay_combat_cost(drv, actor: str, opts: list[dict],
                           labels: list[dict[str, str]], phase, turn) -> str:
    due = [e for e in drv.script
           if e.get("decision_family") == "pay_combat_cost"
           and e.get("actor") == actor
           and (e.get("phases") is None or phase in (e.get("phases") or []))
           and (e.get("turns") is None or turn in (e.get("turns") or []))]
    if not due:
        raise base.Blocked("pay_combat_cost", f"unscripted pay_combat_cost for {actor} "
                                              f"(kind-family binding: no due entry)")
    d = due[0]
    drv.script.remove(d)
    sv = (d.get("selection") or {}).get("semantic_value") or {}
    want = sv.get("decision")
    texts = [str(o.get("kind", "")) for o in opts]
    pay = [i for i, t in enumerate(texts) if "WS68:PAYCOMBATCOST:PAY" in t]
    dec = [i for i, t in enumerate(texts) if "WS68:PAYCOMBATCOST:DECLINE" in t]
    if want == "pay":
        picks = pay
    elif want == "decline":
        picks = dec
    else:
        drv.script.insert(0, d)
        raise base.Blocked("pay_combat_cost", f"unknown decision {want}")
    if len(picks) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("pay_combat_cost", f"{want}: {len(picks)} matches of {len(opts)}")
    drv.consumed.append(d)
    return str(opts[picks[0]]["option_id"])


def answer_concession_ws68(drv, actor: str, opts: list[dict],
                           labels: list[dict[str, str]], phase, turn) -> str:
    if _ws68_due_concession(drv, actor, phase, turn):
        # Scripted concession: exact WS65 offered-options-only semantics.
        return ws65.answer_concession(drv, actor, opts, labels, phase, turn)
    # Unscripted: pilot standing instruction (never concede except when
    # scripted). Select the single offered DECLINE; fail closed otherwise.
    # The provider still offered both native options; nothing is defaulted
    # provider-side and no script entry is consumed.
    texts = [str(o.get("kind", "")) for o in opts]
    auth = [i for i, t in enumerate(texts)
            if "WS62:CONCEDE" in t and "DECLINE" not in t]
    dec = [i for i, t in enumerate(texts) if "DECLINE" in t]
    if len(auth) != 1 or len(dec) != 1:
        raise base.Blocked("concession", f"pilot-decline: authority={len(auth)} "
                                         f"decline={len(dec)} of {len(opts)}")
    WS68_PILOT_DECLINES.append((actor, str(opts[dec[0]].get("option_id", ""))))
    return str(opts[dec[0]]["option_id"])


def ws68_answer(drv, kind: str, actor: str, opts: list[dict],
                labels: list[dict[str, str]], record, phase=None, turn=None) -> str:
    if kind == "pay_combat_cost":
        return answer_pay_combat_cost(drv, actor, opts, labels, phase, turn)
    if kind == "concession":
        return answer_concession_ws68(drv, actor, opts, labels, phase, turn)
    return ws65.ws65_answer(drv, kind, actor, opts, labels, record, phase, turn)


ws65.ws53.ws53_answer = ws68_answer  # type: ignore[assignment]
ws65.ws62.ws53.ws53_answer = ws68_answer  # type: ignore[assignment]


def _assert_ws68_runtime() -> None:
    cmd = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD", "")
    if "/tmp/ws68-ev" not in cmd:
        raise SystemExit("WS68_RUNNER_PROVIDER_CMD_NOT_WS68:/tmp/ws68-ev missing")
    if FORGE_OLD_COMMIT in cmd or "forge-66caae" in cmd:
        raise SystemExit("WS68_RUNNER_OLD_PIN_ON_CMD_FAIL_CLOSED")
    if "/tmp/ws65-ev" in cmd:
        raise SystemExit("WS68_RUNNER_WS65_EV_ON_CMD_FAIL_CLOSED")
    if not os.environ.get("COMMANDER_LAB_FORGE_LANG_DIR"):
        raise SystemExit("WS68_RUNNER_LANG_DIR_MISSING")


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--output", type=Path, required=True)
    known, _rest = ap.parse_known_args()
    _assert_ws68_runtime()
    rc = ws65.ws62.main()
    try:
        doc = json.loads(known.output.read_text())
    except Exception as ex:
        raise SystemExit(f"WS68_RUNNER_OUTPUT_MISSING:{ex}") from ex
    if (doc.get("forge") or {}).get("commit") != FORGE_COMMIT:
        raise SystemExit(f"WS68_JOURNAL_PIN_MISMATCH:{(doc.get('forge') or {}).get('commit')}")
    if (doc.get("forge") or {}).get("tree") != FORGE_TREE:
        raise SystemExit("WS68_JOURNAL_TREE_MISMATCH")
    doc["ws68_runner"] = ("ws68_runner.py (ws65 verbatim + pay_combat_cost family + "
                          "concession pilot-decline + ws68 pin gate)")
    doc["ws68_forge"] = {"commit": FORGE_COMMIT, "tree": FORGE_TREE}
    doc["ws68_old_pin_absent"] = FORGE_OLD_COMMIT not in json.dumps(doc)
    doc["ws68_pilot_declines"] = len(WS68_PILOT_DECLINES)
    known.output.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"WS68_RUNNER_PIN_OK:{FORGE_COMMIT[:7]}:pilot_declines={len(WS68_PILOT_DECLINES)}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
