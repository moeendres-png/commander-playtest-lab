#!/usr/bin/env python3
"""WS64 provider overlay (WS64-owned, qualification-only).

Repairs exact native transport continuity for non-discretionary counter-type
selection (Human/AI parity), without Rules reconstruction, synthesis, or
counter arithmetic.

Defect (PROVIDER_TRANSPORT_DEFECT, proven by WS64 vertical trace on accepted
Forge a9a95db): Ws23ForgeVerticalProvider.chooseCounterType threw
WS23_FAIL_CLOSED_UNSUPPORTED for every call, including the singleton P1P1
choice required by Stonecoil Serpent ETB PutCounter (CounterType P1P1, cost
{0}, ETB True). Human (PlayerControllerHuman.chooseCounterType) and AI
(PlayerControllerAi.chooseCounterType) both return the single option
automatically when options.size() <= 1 and only consult external choice
when multiple options exist. The provider's unconditional failClosed caused
CountersPutEffect.chooseTypeFromList to throw, caught inside Forge as
Counter type mismatch with early return, putting 0 counters into the ETB
table. The Moved replacement framework was reached (singleton own
etbCounter, X=3, unlinked false, spell_resolved X=3 fizzled=false), but the
base CounterMap stayed empty, so Doubling Season / Hardened Scales never
contested (no second Moved with CounterMap), Serpent entered as 0/0 and died
via SBA. Journal shape: X=3, 3 G paid, stack 32, 0 replacement_effect
frames (singleton automatic), gy 32.

Repair (transport only, no semantics):
- options == null -> failClosed (engine contract violation, never valid).
- options empty -> return null (Human parity: getFirst empty -> null).
- options size 1 -> recordAutomatic SINGLE_NATIVE_OPTION and return it
  (no harness frame, no external decision, engine still owns amount,
  ordering, and application).
- options size >1 -> failClosed (discretionary multi-type choice needs
  future harness transport; failing closed per Milestone D, no synthesis).

Forbidden items remain absent: no provider X solver, no counter arithmetic,
no replacement synthesis, no outcome injection, no manual X/move/counter,
no first/random/default, no AI/GUI fallback, no silent skip, no card-name
legality. Engine still owns legality, X, costs, stack, replacement effects,
zones, and outcomes.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS64_OVERLAY_ANCHOR:{label}:expected=1:found={n}")
    return text.replace(old, new, 1)


OLD = """        @Override
        public CounterType chooseCounterType(List<CounterType> options, SpellAbility sa, String prompt, Map<String, Object> params) {
            throw failClosed("chooseCounterType");
        }"""

NEW = """        @Override
        public CounterType chooseCounterType(List<CounterType> options, SpellAbility sa, String prompt, Map<String, Object> params) {
            if (options == null) throw failClosed("chooseCounterType:NULL");
            if (options.isEmpty()) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseCounterType:EMPTY");
                return null;
            }
            if (options.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseCounterType");
                return options.get(0);
            }
            throw failClosed("chooseCounterType:MULTI_UNSUPPORTED");
        }"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    p = args.provider.read_text(encoding="utf-8")
    if "WS62:CONCEDE" not in p or "ws62Target:STACK_SA_BOUND" not in p:
        raise SystemExit("WS64_OVERLAY_PREREQ_MISSING:WS62 v2 overlay")
    if "chooseCounterType:MULTI_UNSUPPORTED" in p:
        raise SystemExit("WS64_OVERLAY_ALREADY_APPLIED")
    p = once(p, OLD, NEW, "countertype singleton transport")
    args.provider.write_text(p, encoding="utf-8")
    required = [
        "chooseCounterType:MULTI_UNSUPPORTED",
        "SINGLE_NATIVE_OPTION:chooseCounterType",
        "chooseCounterType:NULL",
    ]
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS64_OVERLAY_INCOMPLETE:{missing}")
    print("WS64_PROVIDER_OVERLAY=PASS")


if __name__ == "__main__":
    raise SystemExit(main())
