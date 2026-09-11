#!/usr/bin/env python3
"""WS62 successor concession-transport provider overlay v1 (WS62-owned, qualification-only).

Chained patch applied AFTER candidate-qualification/ws55-forge-mandatory-decision-breadth/
ws55_provider_overlay.py onto the ephemeral generated GPL-side provider
(Ws23ForgeVerticalProvider.java). Never touches pinned Forge source, shared
scripts, WS48/WS53/WS55-owned files, or another workstream's files.

Rules-Core authority preserved: concession is engine-owned (CR 104.3a at any
time, not priority-gated; CR 800.4 cleanup via GameAction.concede). Provider
may transport ONLY as direct conditional delegation of the native seam:

  PlayerController.canConcede() -> external decision -> PlayerController.concede()

Forbidden and verified absent here and in the output:
- unconditional standing CONCEDE pseudo-option (this method fails closed when
  canConcede() is false; it never appends CONCEDE to engine-enumerated ACTs)
- orchestration direct Player.concede() (submission calls concede(), the
  controller/native seam, never player.concede())
- priority/phase gating (no phase check; canConcede() itself is not gated)
- heuristic legality, fabricated options, first/random/default, AI/GUI fallback,
  silent skip, manual outcome/target injection, requested-option filtering

Method added to Ws23Controller (inner class extending PlayerController):

  public boolean ws62RequestConcession()

Behavior:
- milestone ws62Concession:ENTERED (diagnostic NATIVE_EVENT)
- boolean legal = canConcede() (native authority consulted first)
- if (!legal) throw failClosed("ws62Concession:NOT_LEGAL")
- labels: WS62:CONCEDE:authority=PlayerController.canConcede:true:player=<pid>
  plus WS62:CONCEDE:opt=DECLINE (decline performs no engine call)
- broker kind "concession" (new kind; harness must answer by exact identity)
- idx 0 -> concede() (native seam) -> true; idx 1 -> recordAutomatic declined
  -> false; else failClosed STALE (ws48Choose already range-checks)

The engine never calls this method by itself (concession is an action, not a
callback). Harness/test invokes it explicitly when a concession probe is due.
2P/3P cleanup remains engine-owned (GameAction.concede ->
checkGameOverCondition -> Game.onPlayerLost).
"""
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS62_OVERLAY_ANCHOR:{label}:expected=1:found={n}")
    return text.replace(old, new, 1)


FAILCLOSED_ANCHOR = """        RuntimeException failClosed(String method) {
            return new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:" + method);
        }"""

CONCESSION_METHOD = """        RuntimeException failClosed(String method) {
            return new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:" + method);
        }

        /**
         * WS62 direct transport of the engine-native concession action.
         * Engine-owned (CR 104.3a any-time; CR 800.4 cleanup). Conditional on
         * native canConcede(); never an unconditional pseudo-option; never a
         * direct Player.concede() call (submission uses concede() seam only).
         */
        public boolean ws62RequestConcession() {
            ws48Milestone("ws62Concession:ENTERED");
            boolean ws62Legal = canConcede();
            if (!ws62Legal) throw failClosed("ws62Concession:NOT_LEGAL");
            String ws62Pid;
            try {
                ws62Pid = ws48StaticPid(getGame(), this.player);
            } catch (Throwable ws62t) {
                ws62Pid = "PX";
            }
            java.util.List<String> ws62Labels = java.util.List.of(
                "WS62:CONCEDE:authority=PlayerController.canConcede:true:player=" + ws48Enc(ws62Pid),
                "WS62:CONCEDE:opt=DECLINE");
            int ws62Idx = ws48Choose("concession", this.player, ws62Labels);
            if (ws62Idx == 1) {
                broker.recordAutomatic("ws62Concession:DECLINED");
                return false;
            }
            if (ws62Idx != 0) throw failClosed("ws62Concession:STALE_OPTION");
            concede();
            return true;
        }"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    p = args.provider.read_text(encoding="utf-8")
    # Prereqs: converged WS55 provider (repaired WS48 + WS53 + WS55 breadth).
    for marker in ("WS48:ATTACK:attacker=", "ws50AllObservations",
                   "WS55:CONCEDE" if False else "WS55:COSTEXILE:opt=",
                   "ws55Permutations", "chooseSingleReplacementEffect:CALLED:n="):
        if marker not in p:
            raise SystemExit(f"WS62_OVERLAY_PREREQ_MISSING:{marker}")
    # Defense: never resurrect Repair-01 doubled add; never add unconditional pseudo-option.
    if "nativeOptions.add(sa);\n                            nativeOptions.add(sa);" in p:
        raise SystemExit("WS62_OVERLAY_REPAIR01_RESURRECTED")
    if "WS62:CONCEDE" in p:
        raise SystemExit("WS62_OVERLAY_ALREADY_APPLIED")
    # Forbid direct Player.concede injection in provider input (must use seam).
    # Note: GameAction.concede / Player.concede definitions live in engine, not provider.
    # Provider must not contain ".concede()" except via our new method (added below).
    # Check input has zero direct concede calls (engine seam not yet referenced).
    if ".concede()" in p:
        raise SystemExit("WS62_OVERLAY_INPUT_UNEXPECTED_CONCEDE_CALL")
    if "Player.concede" in p or "player.concede()" in p:
        raise SystemExit("WS62_OVERLAY_INPUT_HAS_DIRECT_CONCEDE")
    p = once(p, FAILCLOSED_ANCHOR, CONCESSION_METHOD, "concession transport")
    args.provider.write_text(p, encoding="utf-8")
    required = ["ws62RequestConcession", "WS62:CONCEDE:authority=PlayerController.canConcede:true",
                "WS62:CONCEDE:opt=DECLINE", 'ws48Choose("concession"',
                "ws62Concession:ENTERED", "ws62Concession:NOT_LEGAL",
                "ws62Concession:DECLINED"]
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS62_OVERLAY_INCOMPLETE:{missing}")
    # Post-conditions: exactly one native seam call, zero direct Player.concede calls.
    if p.count("concede();") != 1:
        raise SystemExit(f"WS62_OVERLAY_SEAM_COUNT:{p.count('concede();')}")
    if "player.concede()" in p or "Player.concede" in p:
        raise SystemExit("WS62_OVERLAY_DIRECT_CONCEDE_PRESENT")
    # No unconditional standing option: CONCEDE appears only inside ws62RequestConcession.
    if p.count("WS62:CONCEDE") != 2:
        raise SystemExit(f"WS62_OVERLAY_LABEL_COUNT:{p.count('WS62:CONCEDE')}")
    print("WS62_CONCESSION_TRANSPORT_OVERLAY_V1=PASS")


if __name__ == "__main__":
    raise SystemExit(main())
