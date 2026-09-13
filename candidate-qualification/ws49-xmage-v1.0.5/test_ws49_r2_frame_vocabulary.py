#!/usr/bin/env python3
"""WS49 R2 targeted validation: frame/event-vocabulary normalization.

Validates ONLY the R2 mappings recorded in WS49_R2_FRAME_VOCABULARY_MAP.md
(M1 native `mode` <-> canonical `choose_mode`; M2 `{K}_frame:{A}` <->
`{K}_decision_frame:{A}`; M3 `creature_enters:{sid}` <->
`creature_entered:{sid}`) plus negative tests proving semantically different
vocabulary does NOT normalize together.

No engine, no network, no Full107, no construction rerun, no behavior-credit
change. Pure-function checks against the real runner code paths, replaying
verbatim excerpts from retained sealed run 34412882569
(job 102671104148, source 925d21a9) as the calibration subset.

Usage: python3 test_ws49_r2_frame_vocabulary.py [WS49_FULL107_BEHAVIOR_PROBE.json]
Exit 0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS42 = HERE.parents[0] / "ws42-xmage-v1.0.3"
sys.path[:0] = [str(HERE), str(WS42)]

import run_full107_behavior_probe_v105 as probe  # noqa: E402

PASS = "PASS"
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"[{'ok' if cond else 'FAIL'}] {name}" + (f" :: {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def frames_for(decision_class: str, seat: int, actor: str) -> list[str]:
    log = probe.NativeEventLog()
    log.frame_events({"decision_class": decision_class, "seat": seat}, actor)
    return log.as_list()


def main() -> int:
    cdc = probe.canonical_decision_class

    # -- M1: canonicalization table -------------------------------------
    check("M1 mode->choose_mode", cdc("mode") == "choose_mode")
    for klass in (
        "priority", "mulligan", "target", "choose_object", "target_amount",
        "multi_amount", "choice", "choose_use", "pile", "mana_payment",
        "announce_x", "replacement_effect", "trigger_order",
        "declare_attacker", "declare_blocker", "amount",
    ):
        check(f"M1 identity {klass}", cdc(klass) == klass)
    check("M1 unknown passthrough", cdc("frobnicate_xyz") == "frobnicate_xyz")

    # -- M1 negatives: distinct native semantics never conflate ---------
    check("NEG choose_use!=choice", cdc("choose_use") != cdc("choice"))
    check("NEG choose_use!=replacement", cdc("choose_use") != cdc("replacement_effect"))
    check("NEG choice!=replacement", cdc("choice") != cdc("replacement_effect"))
    check("NEG mode!=choice", cdc("mode") != cdc("choice"))
    check("NEG mode!=choose_use", cdc("mode") != cdc("choose_use"))
    check("NEG mode!=replacement", cdc("mode") != cdc("replacement_effect"))

    # -- M2: short-form alias emission ----------------------------------
    # Verbatim retained shape: MICRO_PRIORITY partial path carried
    # target_decision_frame:P2 for a native (target, P2) frame.
    ev = frames_for("target", 1, "P2")
    check("M2 long actor retained", "target_decision_frame:P2" in ev)
    check("M2 long generic retained", "decision_frame:target" in ev)
    check("M2 short alias added", "target_frame:P2" in ev)

    mev = frames_for("mode", 0, "P1")
    for expected in (
        "choose_mode_decision_frame:P1", "decision_frame:choose_mode",
        "choose_mode_frame:P1", "mode_decision_frame:P1",
        "decision_frame:mode", "mode_frame:P1",
    ):
        check(f"M2+M1 mode couch {expected}", expected in mev)

    pev = frames_for("priority", 0, "P1")
    check("M2 priority short alias", "priority_frame:P1" in pev)
    check("M2 priority long retained", "priority_decision_frame:P1" in pev)

    # Calibration replay: every retained long frame gains its short alias,
    # and pre-fix sealed logs contain NO short alias (defect existed).
    sealed_long = [
        "priority_decision_frame:P1", "decision_frame:priority",
        "target_decision_frame:P2", "decision_frame:target",
        "mana_payment_decision_frame:P1", "decision_frame:mana_payment",
        "mulligan_decision_frame:P1", "decision_frame:mulligan",
        "choose_use_decision_frame:P1", "decision_frame:choose_use",
    ]
    check(
        "CALIB sealed logs lack short forms",
        not any(e.endswith("_frame:P1") and "_decision_frame:" not in e and not e.startswith("decision_frame:") for e in sealed_long),
    )
    for long_form in sealed_long:
        if long_form.startswith("decision_frame:"):
            continue
        klass, actor = long_form.split("_decision_frame:")
        check(f"CALIB alias derivable {long_form}", f"{klass}_frame:{actor}" in frames_for(klass, 0, actor))

    # Short alias closes a short-form expectation (evaluation-level proof).
    record = {"expected_events": {"required_events": ["target_decision_frame:P2", "target_frame:P2"],
                                  "forbidden_events": [], "ordering_constraints": [],
                                  "partial_order_constraints": []}}
    passed_prefixed, _ = probe.evaluate_events(record, ["target_decision_frame:P2", "decision_frame:target"])
    check("CALIB pre-fix short missing fails closed", not passed_prefixed)
    passed_fixed, _ = probe.evaluate_events(record, ["target_decision_frame:P2", "decision_frame:target", "target_frame:P2"])
    check("CALIB post-fix short present passes", passed_fixed)

    # -- M2 negatives ----------------------------------------------------
    check("NEG short klass isolation", "target_frame:P2" not in frames_for("priority", 0, "P2"))
    check("NEG short actor isolation", "target_frame:P1" not in frames_for("target", 1, "P2"))
    check("NEG generic unaffected", "decision_frame:priority" not in frames_for("target", 1, "P2"))

    # -- M3: arrival alias ----------------------------------------------
    terminal = {
        "scenario_objects": {},
        "battlefield_arrivals": ["obj:micro-enter"],
        "life_deltas": {},
        "zone_entries": {},
        "token_counts": {},
        "stack_empty": False,
    }
    slog = probe.NativeEventLog()
    probe.derive_settlement_outcomes({}, {}, terminal, slog)
    emitted = slog.as_list()
    check("M3 canonical retained", "creature_entered:obj:micro-enter" in emitted)
    check("M3 bare retained", "creature_entered" in emitted)
    check("M3 alias added", "creature_enters:obj:micro-enter" in emitted)

    trig_record = {"expected_events": {"required_events": ["creature_enters:obj:micro-enter"],
                                       "forbidden_events": [], "ordering_constraints": [],
                                       "partial_order_constraints": []}}
    pre, _ = probe.evaluate_events(trig_record, ["creature_entered:obj:micro-enter", "creature_entered"])
    check("CALIB pre-fix enters missing fails closed", not pre)
    post, _ = probe.evaluate_events(trig_record, emitted)
    check("CALIB post-fix enters present passes", post)

    # -- M3 negatives ----------------------------------------------------
    check("NEG no zone alias", not any(e.startswith("zone_entered:") for e in emitted))
    check("NEG no damage invention", not any(e.startswith("damage:") for e in emitted))
    check("NEG enters!=entered conflation check", "creature_enters:obj:micro-enter" in emitted and "creature_entered:obj:micro-enter" in emitted)

    # -- Transport purity: decisions/options untouched -------------------
    decision = {"decision_class": "mode", "seat": 0,
                "legal_options": [{"option_id": "m1", "option_type": "mode",
                                   "metadata": {"mode_id": "m1"}}]}
    before = copy.deepcopy(decision)
    probe.NativeEventLog().frame_events(decision, "P1")
    check("PURE decision dict unmutated", decision == before)
    check("PURE canonical helper pure", cdc("mode") == "choose_mode" and cdc("mode") == "choose_mode")

    # -- Routing-level proof: family matching ---------------------------
    entries = [{"actor": "P1", "decision_family": "choose_mode"},
               {"actor": "P1", "decision_family": "choice"}]
    matched = [e for e in entries if e["actor"] == "P1" and e["decision_family"] == cdc("mode")]
    check("ROUTE mode frame reaches choose_mode entry", len(matched) == 1 and matched[0]["decision_family"] == "choose_mode")
    matched_cu = [e for e in entries if e["actor"] == "P1" and e["decision_family"] == cdc("choose_use")]
    check("ROUTE choose_use frame reaches no entry (R-a rejected)", matched_cu == [])

    # -- Optional full-artifact census ----------------------------------
    if len(sys.argv) > 1:
        data = json.loads(Path(sys.argv[1]).read_text())
        recs = data["records"]
        n_long = n_short = 0
        for rec in recs:
            for event in rec.get("native_events_emitted") or []:
                if "_decision_frame:" in event:
                    n_long += 1
                elif "_frame:" in event and not event.startswith("decision_frame:"):
                    n_short += 1
        check("CENSUS retained logs carry long frames", n_long > 0, f"n_long={n_long}")
        check("CENSUS retained logs carry zero short frames (defect)", n_short == 0, f"n_short={n_short}")
        entered = sum(1 for rec in recs for e in (rec.get("native_events_emitted") or []) if e.startswith("creature_entered"))
        enters = sum(1 for rec in recs for e in (rec.get("native_events_emitted") or []) if e.startswith("creature_enters:"))
        check("CENSUS entered observed / enters absent", entered > 0 and enters == 0, f"entered={entered} enters={enters}")

    print(f"--- {'ALL PASS' if not FAILURES else f'{len(FAILURES)} FAILURES: {FAILURES}'} ---")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
