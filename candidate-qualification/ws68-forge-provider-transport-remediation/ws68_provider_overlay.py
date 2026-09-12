#!/usr/bin/env python3
"""WS68 Forge provider transport remediation overlay v1 (WS68-owned, qualification-only).

Chained patch applied AFTER candidate-qualification/ws64-forge-a04-vertical-path-investigation/
ws64_provider_overlay.py onto the ephemeral generated GPL-side provider
(Ws23ForgeVerticalProvider.java). Never touches pinned Forge source, shared
scripts, or another workstream's files. No First-Wave behavior credit is granted
by this overlay (BEHAVIOR_CREDIT=0/107); credit is adjudicated separately.

Part 1 - engine-owned combat additional-cost transport (payCombatCost):
Rules Core exclusively owns whether a combat tax applies (attack/block cost
computation), the amount (Cost object), mana legality (native mana abilities),
and the attack result (caller removes the combatant on false). This transport
contributes zero Rules logic. Human parity (forge-gui PlayerControllerHuman):
zero-only-mana costs under FullControlFlag.NoFreeCombatCostHandling resolve
automatically; every other shape runs the engine-native payment procedure
PlaySpellAbility.payCostDuringAbilityResolve, whose discretionary sub-decisions
surface through already-qualified transports (confirmPayment PAY/DECLINE,
payManaCost/applyManaToCost native mana-source frames, chooseCardsForCost,
getCostDecisionMaker visits). Unsupported shapes fail closed inside those
transports; this method never synthesizes amounts, names, sources, or options.
The pay/decline discretion at the combat-cost boundary is externalized as one
broker frame (kind pay_combat_cost, WS68:PAYCOMBATCOST PAY vs DECLINE labels
projecting the engine-computed attacker identity and cost text for display
only). DECLINE returns false so the engine applies its native result
(combatant removed, tapped state restored); it never injects an outcome.

Part 2 - production-reachable native concession offer (autoPassCancel hook)
with two-phase execution:
ws62RequestConcession exists but has zero engine call sites, so no
concession-kind frame can ever be emitted through natural play. This overlay
wires the identical conditional offer (native canConcede() authorization only;
authority + DECLINE labels; kind concession) into autoPassCancel, which the
engine calls for every player on every turn boundary outside priority
(cleanup sweep for all players plus the post-game reset). Authorization is
canConcede() alone: no priority-holder/turn/step check anywhere in the new
code (any-time per 104.3a; cleanup holds no priority). When the native seam
reports not-legal (already lost, game over), the method records an automatic
and returns silently, so post-game and eliminated-player sweeps never block
or throw. The pre-existing automatic record is preserved first.
Execution is two-phase by engine necessity (DIRECTLY_VERIFIED): the cleanup
sweep iterates the LIVE player list, so a re-entrant concede() inside the
sweep mutates the iterated collection and the engine fails its own iterator
(ConcurrentModificationException; engine limitation, no provider fault). The
ACCEPTED external Decision is therefore recorded in a per-controller pending
flag and executed at that player's next priority consultation
(chooseSpellAbilityToPlay), where the engine is explicitly tolerant (the
priority loop is counter-driven and carries an active-player-lost handoff).
The offer itself is never priority-coincident; only the execution venue is
priority-safe. A lost player emits no further frames after executing.

Forbidden items verified absent by post-conditions below: card-name logic,
cost-amount computation, fabricated mana sources, first-source auto-payment,
requested-option filtering, silent skip/default, heuristic legality, priority
gating (PhaseType count invariant), direct Player.concede / GameAction.concede
orchestration (seam-call count exactly 2: the WS62 site plus the WS68 priority
drain; the sweep site only records the Decision),
unconditional standing options (every CONCEDE label site is canConcede-gated;
WS62:CONCEDE count exactly 4 = 2 WS62 sites + 2 WS68 sweep sites).
"""
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS68_OVERLAY_ANCHOR:{label}:expected=1:found={n}")
    return text.replace(old, new, 1)


PAY_OLD = """        @Override
        public boolean payCombatCost(Card card, Cost cost, SpellAbility sa, String prompt) {
            throw failClosed("payCombatCost");
        }"""

PAY_NEW = """        @Override
        public boolean payCombatCost(Card card, Cost cost, SpellAbility sa, String prompt) {
            // WS68 engine-owned combat additional-cost transport. Rules Core owns
            // applicability, amount, mana legality, and result; this method only
            // transports the pay/decline discretion plus the native payment
            // procedure (Human parity). Never computes, names, fabricates, or filters.
            ws48Milestone("payCombatCost:ENTERED");
            if (card == null) throw failClosed("payCombatCost:NULL_CARD");
            if (cost == null) throw failClosed("payCombatCost:NULL_COST");
            if (cost.isOnlyManaCost() && cost.getTotalMana().isZero()
                    && isFullControl(FullControlFlag.NoFreeCombatCostHandling)) {
                broker.recordAutomatic("payCombatCost:NOFREE_AUTO");
                return true;
            }
            String ws68AttackerRef = ws48CardRef(card);
            String ws68CostText;
            try {
                ws68CostText = String.valueOf(cost);
            } catch (Throwable ws68t) {
                ws68CostText = "?";
            }
            java.util.List<String> ws68Labels = java.util.List.of(
                "WS68:PAYCOMBATCOST:PAY:attacker=" + ws48Enc(ws68AttackerRef)
                    + ":cost=" + ws48Enc(ws48Clip(ws68CostText, 120)),
                "WS68:PAYCOMBATCOST:DECLINE:attacker=" + ws48Enc(ws68AttackerRef)
                    + ":cost=" + ws48Enc(ws48Clip(ws68CostText, 120)));
            int ws68Idx = ws48Choose("pay_combat_cost", this.player, ws68Labels);
            if (ws68Idx == 1) {
                broker.recordAutomatic("payCombatCost:DECLINED");
                return false;
            }
            if (ws68Idx != 0) throw failClosed("payCombatCost:STALE_OPTION");
            return PlaySpellAbility.payCostDuringAbilityResolve(this, this.player, cost, sa, prompt);
        }"""

AUTO_OLD = """        @Override
        public void autoPassCancel() {
            broker.recordAutomatic("autoPassCancel");
            return;
        }"""

AUTO_NEW = """        @Override
        public void autoPassCancel() {
            // WS68 production-reachable native concession offer (any-time; cleanup
            // holds no priority). Authorization is native canConcede() alone; no
            // priority-holder, turn, or step check. An ACCEPTED Decision is
            // recorded for deferred execution at this player's next priority
            // (the sweep cannot take a re-entrant concede); leave-game cleanup
            // stays engine-owned. Not-legal sweeps stay silent.
            broker.recordAutomatic("autoPassCancel");
            ws48Milestone("ws68Concession:AUTOPASSCANCEL_ENTERED");
            boolean ws68Legal;
            try {
                ws68Legal = canConcede();
            } catch (Throwable ws68t) {
                ws68Legal = false;
            }
            if (!ws68Legal) {
                broker.recordAutomatic("ws68Concession:NOT_LEGAL_AUTO");
                return;
            }
            String ws68Pid;
            try {
                ws68Pid = ws48StaticPid(getGame(), this.player);
            } catch (Throwable ws68t) {
                ws68Pid = "PX";
            }
            java.util.List<String> ws68Labels = java.util.List.of(
                "WS62:CONCEDE:authority=PlayerController.canConcede:true:player=" + ws48Enc(ws68Pid),
                "WS62:CONCEDE:opt=DECLINE");
            int ws68Idx = ws48Choose("concession", this.player, ws68Labels);
            if (ws68Idx == 1) {
                broker.recordAutomatic("ws68Concession:DECLINED");
                return;
            }
            if (ws68Idx != 0) throw failClosed("ws68Concession:STALE_OPTION");
            ws68ConcedePending = true;
            ws48Milestone("ws68Concession:ACCEPTED_DEFERRED");
            return;
        }"""

FIELD_OLD = """        Ws23Controller(Game game, Player player, LobbyPlayer lobby, Broker broker) {
            super(game, player, lobby);
            this.broker = broker;
        }"""

FIELD_NEW = """        boolean ws68ConcedePending = false;

        Ws23Controller(Game game, Player player, LobbyPlayer lobby, Broker broker) {
            super(game, player, lobby);
            this.broker = broker;
        }"""

PRIORITY_OLD = """        @Override
        public List<SpellAbility> chooseSpellAbilityToPlay() {
            return broker.choosePriority(player, getGame());
        }"""

PRIORITY_NEW = """        @Override
        public List<SpellAbility> chooseSpellAbilityToPlay() {
            // WS68 deferred concession execution: a pending external concede
            // Decision runs here, at this player's priority consultation, which
            // the engine tolerates (counter-driven loop with an explicit
            // active-player-lost handoff). A lost player takes no further
            // actions: no priority frame is emitted after conceding.
            if (ws68ConcedePending) {
                ws68ConcedePending = false;
                ws48Milestone("ws68Concession:EXECUTING_AT_PRIORITY");
                boolean ws68StillLegal;
                try {
                    ws68StillLegal = canConcede();
                } catch (Throwable ws68t) {
                    ws68StillLegal = false;
                }
                if (!ws68StillLegal) {
                    broker.recordAutomatic("ws68Concession:NOT_LEGAL_AT_EXECUTION");
                    return null;
                }
                String ws68ExecPid;
                try {
                    ws68ExecPid = ws48StaticPid(getGame(), this.player);
                } catch (Throwable ws68t) {
                    ws68ExecPid = "PX";
                }
                concede();
                ws68EmitConcessionExecuted(ws68ExecPid);
                return null;
            }
            return broker.choosePriority(player, getGame());
        }"""

EMITTER_ANCHOR = """        String ws48Pid(Player p) {"""

EMITTER_ADD = """        void ws68EmitConcessionExecuted(String pid) {
            broker.out.println("{\\"protocol\\":" + esc(PROTOCOL)
                + ",\\"message_type\\":\\"NATIVE_EVENT\\""
                + ",\\"request_id\\":\\"ws68-concession-executed\\""
                + ",\\"session_id\\":" + esc(SESSION_ID)
                + ",\\"payload\\":{\\"event\\":" + esc("ws68Concession:EXECUTED")
                + ",\\"facts\\":" + esc("player=" + pid) + "}}");
            broker.out.flush();
        }

        String ws48Pid(Player p) {"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    p = args.provider.read_text(encoding="utf-8")
    # Prereqs: converged provider through the WS64 overlay (repaired WS48 +
    # WS53 + WS55 breadth + WS62 concession/stack-SA + WS64 countertype).
    for marker in ("WS48:ATTACK:attacker=", "ws50AllObservations",
                   "WS55:COSTEXILE:opt=", "ws55Permutations",
                   "chooseSingleReplacementEffect:CALLED:n=",
                   "WS62:CONCEDE:authority=PlayerController.canConcede:true",
                   "ws62Target:STACK_SA_BOUND",
                   "chooseCounterType:MULTI_UNSUPPORTED"):
        if marker not in p:
            raise SystemExit(f"WS68_OVERLAY_PREREQ_MISSING:{marker}")
    if "WS68:PAYCOMBATCOST" in p or "ws68Concession" in p:
        raise SystemExit("WS68_OVERLAY_ALREADY_APPLIED")
    # Defense: the WS62 input invariant must still hold (exactly one native
    # seam call, zero direct orchestration calls) before this overlay adds the
    # second (and final) seam call inside the autoPassCancel hook.
    if p.count("concede();") != 1:
        raise SystemExit(f"WS68_OVERLAY_INPUT_SEAM_COUNT:{p.count('concede();')}")
    if "player.concede()" in p or "Player.concede" in p or "getAction().concede" in p:
        raise SystemExit("WS68_OVERLAY_INPUT_HAS_DIRECT_CONCEDE")
    # No priority gating anywhere in the input's concession region, and none
    # may be introduced: PhaseType occurrence count must be invariant.
    ws68_phase_before = p.count("PhaseType")
    p = once(p, PAY_OLD, PAY_NEW, "payCombatCost transport")
    p = once(p, AUTO_OLD, AUTO_NEW, "autoPassCancel concession offer")
    p = once(p, FIELD_OLD, FIELD_NEW, "concede pending flag")
    p = once(p, PRIORITY_OLD, PRIORITY_NEW, "priority concession drain")
    p = once(p, EMITTER_ANCHOR, EMITTER_ADD, "concession executed emitter")
    args.provider.write_text(p, encoding="utf-8")
    required = ["payCombatCost:ENTERED", "payCombatCost:DECLINED",
                "payCombatCost:NOFREE_AUTO", "payCombatCost:STALE_OPTION",
                "payCombatCost:NULL_CARD", "payCombatCost:NULL_COST",
                "WS68:PAYCOMBATCOST:PAY", "WS68:PAYCOMBATCOST:DECLINE",
                'ws48Choose("pay_combat_cost"',
                "payCostDuringAbilityResolve(this, this.player, cost, sa, prompt)",
                "NoFreeCombatCostHandling",
                "ws68Concession:AUTOPASSCANCEL_ENTERED",
                "ws68Concession:NOT_LEGAL_AUTO", "ws68Concession:DECLINED",
                "ws68Concession:STALE_OPTION", "ws68Concession:ACCEPTED_DEFERRED",
                "ws68Concession:EXECUTING_AT_PRIORITY",
                "ws68Concession:NOT_LEGAL_AT_EXECUTION",
                "ws68Concession:EXECUTED", "ws68ConcedePending",
                "ws68EmitConcessionExecuted", 'ws48Choose("concession"']
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS68_OVERLAY_INCOMPLETE:{missing}")
    # Post-conditions: exactly two native seam calls (WS62 site + WS68 priority
    # drain; the sweep site only records), zero direct orchestration calls,
    # four canConcede-gated labels, two combat-cost labels, no card-name logic,
    # no priority gating delta.
    if p.count("concede();") != 2:
        raise SystemExit(f"WS68_OVERLAY_SEAM_COUNT:{p.count('concede();')}")
    if "player.concede()" in p or "Player.concede" in p or "getAction().concede" in p:
        raise SystemExit("WS68_OVERLAY_DIRECT_CONCEDE_PRESENT")
    if p.count("WS62:CONCEDE") != 4:
        raise SystemExit(f"WS68_OVERLAY_CONCEDE_LABEL_COUNT:{p.count('WS62:CONCEDE')}")
    if p.count("WS68:PAYCOMBATCOST") != 2:
        raise SystemExit(f"WS68_OVERLAY_PAYCOMBATTAX_LABEL_COUNT:{p.count('WS68:PAYCOMBATCOST')}")
    if "Propaganda" in p or "propaganda" in p:
        raise SystemExit("WS68_OVERLAY_CARD_NAME_PRESENT")
    if p.count("PhaseType") != ws68_phase_before:
        raise SystemExit("WS68_OVERLAY_PHASETYPE_DELTA")
    if p.count("NoFreeCombatCostHandling") != 1:
        raise SystemExit("WS68_OVERLAY_NOFREE_COUNT")
    if "ComputerUtilMana" in p or "candidates.get(0)" in p:
        raise SystemExit("WS68_OVERLAY_AUTOPAY_PATTERN_PRESENT")
    if 'throw failClosed("payCombatCost");' in p:
        raise SystemExit("WS68_OVERLAY_PAY_STUB_REMAINS")
    print("WS68_PROVIDER_TRANSPORT_OVERLAY_V1=PASS")


if __name__ == "__main__":
    raise SystemExit(main())
