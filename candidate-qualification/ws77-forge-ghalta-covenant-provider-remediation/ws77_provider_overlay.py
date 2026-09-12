#!/usr/bin/env python3
"""WS77 Forge provider transport remediation overlay v2 (WS77-owned, qualification-only).

Chained patch applied AFTER
candidate-qualification/ws68-forge-provider-transport-remediation/
ws68_provider_overlay.py onto the WS68-overlayed GPL-side provider
(Ws23ForgeVerticalProvider.java). Never touches pinned Forge source, shared
scripts, or another workstream's files. Grants no behavior credit
(BEHAVIOR_CREDIT=0/107; credit is adjudicated separately, and none is claimed
in WS77).

Scope (binding): provider/harness transport ONLY. WS67 proved engine-direct
PASS for both packets (GHALTA reduced-cost cast; Fire Covenant non-mana X).
WS77 diagnosis on the exact WS68 overlay + accepted pin a9a95db established:

- GHALTA (Ghalta, Stampede Tyrant, printed {5}{G}{G}{G}, NO ReduceCost):
  engine billed exactly {5}{G}{G}{G}; the WS65 intent supplied 6 of 8 mana;
  the provider loop tapped exactly the scripted sources, applied each mana
  natively, exhausted native sources, returned false, and the engine natively
  rolled back. Every step conformant; the "silent drop" was a harness intent
  shortfall (authored for Primal Hunger's 6), never a provider defect. No
  provider change warranted on this path.
- COVENANT X-BILLING hypothesis REFUTED (Fire Covenant X=39): engine billed
  exactly the printed {1}{B}{R}; announced life-X never entered the mana bill
  (no mana-X leak anywhere); {R} and {1} paid natively; {B} was unpayable
  (fixture deck ships zero black sources); conformant fail-closed rollback.
- COVENANT DIVISION DEFECT FOUND AND REPAIRED HERE (Fire Covenant X=5, actual
  card, corrected fixture with black mana): payment completes in full
  ({1}{B}{R} mana + 5 life, spell reaches the stack), then the engine NPEs at
  resolution because NO divided allocation was ever recorded. Root cause is a
  provider Human-parity gap: PlayerControllerHuman.chooseTargetsFor assigns
  divided-as-you-choose allocations controller-side after target selection;
  the inherited provider chooseTargetsFor returns without assigning, so
  TargetChoices.getDividedValue is null and DamageDealEffect unboxes null.
  (ENGINE_EXTERNAL_DECISION_SEAM NPE; engine Rules accounting itself is sound
  per WS67.)

Part 1 - divided-as-you-choose allocation transport (Human parity, generic):
after successful target selection, mirror the Human post-selection block.
Determined shapes are assigned natively with zero discretion (single target
takes the whole remaining amount; N targets with amount N take 1 each);
impossible division (more positive targets than amount) returns false exactly
as Human aborts the cast (engine-native rollback follows); genuinely
discretionary multi-target division and DividedUpTo choice fail closed with a
labeled ControlledStop (no first/default/random allocation). Non-divided
spells are untouched (getStillToDivide() == 0 takes the early return).
No card names, no amounts computed (amount comes from the engine's own
getStillToDivide), no options offered or defaulted, no stack or resolution
semantics touched.

Part 2 - observation only (unchanged from v1): additive milestones on the
three silent early-false exits of the inherited applyManaToCost transport
plus the payManaCost unpaid return, so future forensics can distinguish
underpayment-rollback from silent drop without changing one branch predicate
or return value:

1. applyManaToCost native-source exhaustion -> milestone
   "applyManaToCost:NO_SOURCES" before the native `return false`.
2. applyManaToCost chosen-source activation failure -> milestone
   "applyManaToCost:SOURCE_PLAY_FAILED" before the native `return false`.
3. applyManaToCost mana-restriction mismatch -> milestone
   "applyManaToCost:RESTRICTIONS_UNMET" before the native `return false`.
4. payManaCost transport returning unpaid -> milestone
   "payManaCost:RESULT_FALSE" before returning the native false.

Forbidden items verified absent by post-conditions below: card-name logic,
cost-amount computation or solving, mana-source fabrication or filtering,
first-source auto-payment, requested-option filtering, silent skip/default,
heuristic legality, priority gating, direct concede orchestration, stack
placement, resolution injection, and (Part 2) any change to a return value or
branch predicate.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS77_OVERLAY_ANCHOR:{label}:expected=1:found={n}")
    return text.replace(old, new, 1)


# --- 4. payManaCost unpaid-result observation (keep native return value) ---
PAY_OLD = """        public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {
            ws48Milestone("payManaCost:ENTERED");
            return PlaySpellAbility.payManaCost(this, toPay, costPartMana, sa, this.player, prompt, matrix, effect);
        }"""

PAY_NEW = """        public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {
            ws48Milestone("payManaCost:ENTERED");
            // WS77 observation only: flag the unpaid return so future forensics
            // can distinguish engine-native rollback-after-underpayment from a
            // silent transport drop. Branch predicate and return value native.
            boolean ws77Paid = PlaySpellAbility.payManaCost(this, toPay, costPartMana, sa, this.player, prompt, matrix, effect);
            if (!ws77Paid) ws48Milestone("payManaCost:RESULT_FALSE");
            return ws77Paid;
        }"""

# --- 1. native-source exhaustion observation (keep native return false) ---
SRC_OLD = """                if (nativeMana.isEmpty()) return false;"""

SRC_NEW = """                // WS77 observation only: exhausted native mana sources is a
                // conformant fail-closed (Human parity: cancel with nothing to
                // tap). Return value native.
                if (nativeMana.isEmpty()) { ws48Milestone("applyManaToCost:NO_SOURCES"); return false; }"""

# --- 2. chosen-source activation failure observation (keep native return) ---
PLAY_OLD = """                if (!PlaySpellAbility.playSpellAbility(this, this.player, chosen)) return false;"""

PLAY_NEW = """                // WS77 observation only. Return value native.
                if (!PlaySpellAbility.playSpellAbility(this, this.player, chosen)) { ws48Milestone("applyManaToCost:SOURCE_PLAY_FAILED"); return false; }"""

# --- 3. mana-restriction mismatch observation (keep native return) ---
RESTR_OLD = """                if (!restrictionsMet) return false;"""

RESTR_NEW = """                // WS77 observation only: a restriction-blocked source is
                // skipped by Human parity via re-pick; the inherited transport
                // aborts the payment (conformant fail-closed via native
                // rollback). Return value native; predicate untouched.
                if (!restrictionsMet) { ws48Milestone("applyManaToCost:RESTRICTIONS_UNMET"); return false; }"""


# --- Part 1: divided-as-you-choose allocation transport (Human parity) ---
DIV_HELPER_ANCHOR = """        @Override
        public boolean chooseTargetsFor(SpellAbility currentAbility) {"""

DIV_HELPER = """        boolean ws77AssignDivided(SpellAbility currentAbility) {
            // WS77 divided-as-you-choose transport (Human parity:
            // PlayerControllerHuman.chooseTargetsFor post-selection block).
            // Determined shapes are assigned natively with zero discretion
            // (single target takes the whole remaining amount; N targets with
            // amount N take 1 each); impossible division (more positive
            // targets than amount) returns false exactly as Human aborts the
            // cast (engine-native rollback follows); genuinely discretionary
            // multi-target division and DividedUpTo choice fail closed with a
            // labeled ControlledStop (no first/default/random allocation).
            // Non-divided spells are untouched (getStillToDivide() == 0).
            // The amount is engine-authoritative (getStillToDivide); nothing
            // is computed, solved, offered, or defaulted here.
            java.lang.Iterable<GameEntity> ws77tgts = currentAbility.getTargets().getTargetEntities();
            int ws77size = 0;
            for (GameEntity ws77e : ws77tgts) ws77size++;
            int ws77amount = currentAbility.getStillToDivide();
            if (!(ws77size > 0 && ws77amount > 0)) {
                ws48Milestone("chooseTargetsFor:UNDIVIDED");
                return true;
            }
            if (currentAbility.hasParam("DividedUpTo")) throw failClosed("chooseTargetsFor:DIVIDED_UP_TO_DISCRETIONARY");
            if (ws77size == 1) {
                GameObject ws77only = null;
                for (GameEntity ws77e : ws77tgts) { ws77only = (GameObject) ws77e; break; }
                currentAbility.addDividedAllocation(ws77only, ws77amount);
                ws48Milestone("chooseTargetsFor:DIVIDED_SINGLE");
                return true;
            }
            if (ws77size == ws77amount) {
                for (GameEntity ws77e : ws77tgts) currentAbility.addDividedAllocation((GameObject) ws77e, 1);
                ws48Milestone("chooseTargetsFor:DIVIDED_ONE_EACH");
                return true;
            }
            if (ws77size > ws77amount) return false;
            throw failClosed("chooseTargetsFor:DIVIDED_DISCRETIONARY");
        }

        @Override
        public boolean chooseTargetsFor(SpellAbility currentAbility) {"""

DIV_LOOP_TOP_OLD = """            while (true) {
                if (++guard > 32) throw failClosed("chooseTargetsFor:GUARD");
                if (currentAbility.getTargets().size() >= currentAbility.getMaxTargets()) return true;"""

DIV_LOOP_TOP_NEW = """            while (true) {
                if (++guard > 32) throw failClosed("chooseTargetsFor:GUARD");
                if (currentAbility.getTargets().size() >= currentAbility.getMaxTargets()) return ws77AssignDivided(currentAbility);"""

DIV_DONE_OLD = """                if (idx == labels.size() - 1 && currentAbility.getTargets().size() >= currentAbility.getMinTargets()
                        && labels.get(idx).equals("WS48:TARGET:DONE")) {
                    return true;
                }"""

DIV_DONE_NEW = """                if (idx == labels.size() - 1 && currentAbility.getTargets().size() >= currentAbility.getMinTargets()
                        && labels.get(idx).equals("WS48:TARGET:DONE")) {
                    return ws77AssignDivided(currentAbility);
                }"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    p = args.provider.read_text(encoding="utf-8")
    # Prereqs: the full WS68 chain output (repaired WS48 + WS53 + WS55 breadth
    # + WS62 concession/stack-SA + WS64 countertype + WS68 payCombatCost and
    # two-phase concession offer).
    for marker in ("WS48:ATTACK:attacker=", "ws50AllObservations",
                   "WS55:COSTEXILE:opt=", "ws55Permutations",
                   "chooseSingleReplacementEffect:CALLED:n=",
                   "WS62:CONCEDE:authority=PlayerController.canConcede:true",
                   "ws62Target:STACK_SA_BOUND",
                   "chooseCounterType:MULTI_UNSUPPORTED",
                   "WS68:PAYCOMBATCOST:PAY", "ws68Concession:ACCEPTED_DEFERRED",
                   "payCostDuringAbilityResolve(this, this.player, cost, sa, prompt)"):
        if marker not in p:
            raise SystemExit(f"WS77_OVERLAY_PREREQ_MISSING:{marker}")
    if "WS77_PROVIDER_TRANSPORT_REMEDIATION_V2" in p or "applyManaToCost:NO_SOURCES" in p:
        raise SystemExit("WS77_OVERLAY_ALREADY_APPLIED")
    p = once(p, PAY_OLD, PAY_NEW, "payManaCost result observation")
    p = once(p, SRC_OLD, SRC_NEW, "applyManaToCost source exhaustion observation")
    p = once(p, PLAY_OLD, PLAY_NEW, "applyManaToCost source-play observation")
    p = once(p, RESTR_OLD, RESTR_NEW, "applyManaToCost restriction observation")
    p = once(p, DIV_HELPER_ANCHOR, DIV_HELPER, "divided allocation helper")
    p = once(p, DIV_LOOP_TOP_OLD, DIV_LOOP_TOP_NEW, "divided allocation at max-targets exit")
    p = once(p, DIV_DONE_OLD, DIV_DONE_NEW, "divided allocation at DONE exit")
    # WS77 stamp comment (observation marker; no code).
    anchor = "public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {"
    stamp = ("        // WS77_PROVIDER_TRANSPORT_REMEDIATION_V2: divided-as-you-choose "
             "allocation transport (Human parity, determined shapes native, "
             "discretionary fails closed) + observation-only milestones on "
             "payManaCost/applyManaToCost early-false paths.\n" + anchor)
    if stamp not in p:
        p = once(p, anchor, stamp, "ws77 stamp")
    args.provider.write_text(p, encoding="utf-8")
    required = ["payManaCost:ENTERED", "payManaCost:RESULT_FALSE",
                "applyManaToCost:ENTERED", "applyManaToCost:NO_SOURCES",
                "applyManaToCost:SOURCE_PLAY_FAILED",
                "applyManaToCost:RESTRICTIONS_UNMET",
                "ws77AssignDivided", "getStillToDivide",
                "chooseTargetsFor:UNDIVIDED", "chooseTargetsFor:DIVIDED_SINGLE",
                "chooseTargetsFor:DIVIDED_ONE_EACH",
                "chooseTargetsFor:DIVIDED_UP_TO_DISCRETIONARY",
                "chooseTargetsFor:DIVIDED_DISCRETIONARY",
                "WS77_PROVIDER_TRANSPORT_REMEDIATION_V2"]
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS77_OVERLAY_INCOMPLETE:{missing}")
    # Post-conditions: no card-name logic, no cost solving, no stack/resolution
    # injection, no legality heuristics. Return-value changes are confined to
    # the Human-parity divided-allocation exits (documented in Part 1).
    for bad in ("Ghalta", "Covenant", "Fireball", "Primal Hunger",
                "addAndUnfreeze", "moveToStack", "ComputerUtilMana",
                "candidates.get(0)", "ManaCostBeingPaid("):
        if bad in p:
            raise SystemExit(f"WS77_OVERLAY_FORBIDDEN_PRESENT:{bad}")
    # Exactly one native seam call pair for concession (WS68 invariant kept).
    if p.count("concede();") != 2:
        raise SystemExit(f"WS77_OVERLAY_SEAM_COUNT:{p.count('concede();')}")
    if p.count("WS68:PAYCOMBATCOST") != 2:
        raise SystemExit(f"WS77_OVERLAY_PAYCOMBATTAX_LABEL_COUNT:{p.count('WS68:PAYCOMBATCOST')}")
    # Divided-allocation exits are the only new chooseTargetsFor predicates.
    if p.count("ws77AssignDivided(currentAbility)") != 2:
        raise SystemExit("WS77_OVERLAY_DIVIDED_EXIT_COUNT")
    print("WS77_PROVIDER_TRANSPORT_REMEDIATION_V2=PASS")


if __name__ == "__main__":
    raise SystemExit(main())
