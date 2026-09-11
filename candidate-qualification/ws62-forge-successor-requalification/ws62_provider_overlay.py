#!/usr/bin/env python3
"""WS62 successor provider overlay v2 (WS62-owned, qualification-only).

Chained patch applied AFTER candidate-qualification/ws55-forge-mandatory-decision-breadth/
ws55_provider_overlay.py onto the ephemeral generated GPL-side provider
(Ws23ForgeVerticalProvider.java). Never touches pinned Forge source, shared
scripts, WS48/WS53/WS55-owned files, or another workstream's files.

Part 1 — concession transport (see v1):
Rules-Core authority preserved: concession is engine-owned (CR 104.3a at any
time, not priority-gated; CR 800.4 cleanup via GameAction concede path).
Provider may transport ONLY as direct conditional delegation of the native seam:
  PlayerController.canConcede() -> external decision -> controller seam
Forbidden: unconditional standing pseudo-option, orchestration direct call,
priority gating, heuristic legality, fabricated options, first/random/default,
AI/GUI fallback, silent skip, manual outcome/target injection,
requested-option filtering.

Part 2 — stack-spell target binding (WS62 fix for C01 continuation):
Human parity (forge-gui TargetSelection.chooseCardFromStack): for Stack-zone
targets the engine-authorized choice is the SpellAbility on the stack, not the
host Card proxy. The WS59 successor makes the host Card pass canTarget via a
general proxy exception, but TargetChoices.add(Card) does not target the stack
spell, so a FoW-style counter fizzles (Elves survives on battlefield). This
patch binds the authoritative SpellAbility while keeping the harness-visible
label on the host Card (MINTED-xxx stable identity):
- enumerate exactly getAllCandidates + canTarget (engine authority, no filter)
- for a Stack-zone host Card with TargetType: resolve the single authoritative
  stack SA via game.getStack() + canTargetSpellAbility + host-ID match (fail
  closed when zero/multiple; never fabricate)
- verify canTarget(SA) (proxy-unfolded engine authority) and not already targeted
- store the SA as the native option (cands holds the SA), label the host Card
- milestone ws62Target:STACK_SA_BOUND (diagnostic parity with Human path)
Non-stack candidates keep the exact WS48/WS55 path (Card/Player binding).
No provider color filtering, cost solving, manual payment, or outcome injection.
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
         * direct player-dot-concede call (submission uses seam only).
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

TARGET_STACK_OLD = """                for (GameEntity cand : restrictions.getAllCandidates(currentAbility)) {
                    if (!(cand instanceof GameObject)) continue;
                    if (!currentAbility.canTarget((GameObject) cand)) continue;
                    if (currentAbility.getTargets().contains(cand)) continue;
                    cands.add(cand);
                    labels.add("WS48:TARGET:tgt=" + ws48Enc(ws48EntityRef(cand)));
                }"""

TARGET_STACK_NEW = """                for (GameEntity cand : restrictions.getAllCandidates(currentAbility)) {
                    // WS62 stack-spell proxy: bind the authoritative SpellAbility (Human
                    // chooseCardFromStack parity), label the host Card for harness identity.
                    if (cand instanceof Card ws62Card
                            && ws62Card.getZone() != null
                            && ws62Card.getZone().is(ZoneType.Stack)
                            && currentAbility.hasParam("TargetType")) {
                        SpellAbility ws62sa = null;
                        int ws62matches = 0;
                        for (SpellAbilityStackInstance ws62si : getGame().getStack()) {
                            SpellAbility ws62stackSA = ws62si.getSpellAbility();
                            if (ws62stackSA == null || ws62stackSA.getHostCard() == null) continue;
                            if (ws62stackSA.getHostCard().getId() != ws62Card.getId()
                                    && !ws62stackSA.getHostCard().equals(ws62Card)) continue;
                            if (!currentAbility.canTargetSpellAbility(ws62stackSA)) continue;
                            ws62sa = ws62stackSA;
                            ws62matches++;
                        }
                        if (ws62sa == null || ws62matches != 1) continue;
                        if (!currentAbility.canTarget(ws62sa)) continue;
                        if (currentAbility.getTargets().contains(ws62sa)) continue;
                        cands.add(ws62sa);
                        labels.add("WS48:TARGET:tgt=" + ws48Enc(ws48EntityRef(ws62Card)));
                        ws48Milestone("ws62Target:STACK_SA_BOUND");
                        continue;
                    }
                    if (!(cand instanceof GameObject)) continue;
                    if (!currentAbility.canTarget((GameObject) cand)) continue;
                    if (currentAbility.getTargets().contains(cand)) continue;
                    cands.add(cand);
                    labels.add("WS48:TARGET:tgt=" + ws48Enc(ws48EntityRef(cand)));
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
    p = once(p, TARGET_STACK_OLD, TARGET_STACK_NEW, "stack-spell SA binding")
    args.provider.write_text(p, encoding="utf-8")
    required = ["ws62RequestConcession", "WS62:CONCEDE:authority=PlayerController.canConcede:true",
                "WS62:CONCEDE:opt=DECLINE", 'ws48Choose("concession"',
                "ws62Concession:ENTERED", "ws62Concession:NOT_LEGAL",
                "ws62Concession:DECLINED",
                "ws62Target:STACK_SA_BOUND", "canTargetSpellAbility(ws62stackSA)"]
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
    if p.count("ws62Target:STACK_SA_BOUND") != 1:
        raise SystemExit("WS62_OVERLAY_STACK_MILESTONE_COUNT")
    # Stack binding must not fabricate: exactly one authoritative SA resolution path.
    if p.count("canTargetSpellAbility(ws62stackSA)") != 1:
        raise SystemExit("WS62_OVERLAY_STACK_AUTHORITY_COUNT")
    print("WS62_PROVIDER_OVERLAY_V2=PASS")
    # Back-compat: v1 gate string still emitted for build-script greps that expect it.
    print("WS62_CONCESSION_TRANSPORT_OVERLAY_V1=PASS")


if __name__ == "__main__":
    raise SystemExit(main())
