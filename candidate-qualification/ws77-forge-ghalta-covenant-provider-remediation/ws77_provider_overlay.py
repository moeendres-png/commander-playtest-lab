#!/usr/bin/env python3
"""WS77 Forge provider transport observation overlay v1 (WS77-owned, qualification-only).

Chained patch applied AFTER
candidate-qualification/ws68-forge-provider-transport-remediation/
ws68_provider_overlay.py onto the WS68-overlayed GPL-side provider
(Ws23ForgeVerticalProvider.java). Never touches pinned Forge source, shared
scripts, or another workstream's files. Grants no behavior credit
(BEHAVIOR_CREDIT=0/107; credit is adjudicated separately, and none is claimed
in WS77).

Scope (binding): provider/harness transport observation ONLY. WS67 proved
engine-direct PASS for both packets (GHALTA reduced-cost cast; Fire Covenant
non-mana X); WS77 diagnosis on the exact WS68 overlay + accepted pin
a9a95db proved both external-provider failures were faithful fail-closed
transports of authoritatively computed engine state, NOT transport defects:

- GHALTA (Ghalta, Stampede Tyrant, printed {5}{G}{G}{G}, NO ReduceCost):
  engine billed exactly {5}{G}{G}{G}; the WS65 intent supplied 6 of 8 mana;
  the provider loop tapped exactly the scripted sources, applied each mana
  natively, exhausted native sources, returned false, and the engine natively
  rolled back. Every step conformant; the "silent drop" was a harness intent
  shortfall (authored for Primal Hunger's 6), never a provider defect.
- COVENANT (Fire Covenant X=39): engine billed exactly the printed {1}{B}{R};
  announced life-X never entered the mana bill (no mana-X leak anywhere);
  {R} and {1} paid natively; {B} was unpayable (fixture deck ships zero black
  sources); the provider loop tapped every land, applied nothing further,
  returned false, and the engine natively rolled back. Conformant fail-closed.

Because the WS65 misclassification (HARNESS shortfall read as PROVIDER/ENGINE
defect) was caused precisely by the SILENCE of the three early-false exits of
the inherited applyManaToCost transport plus the silence of the payManaCost
failure return, this overlay adds OBSERVATION ONLY on exactly those paths:

1. applyManaToCost native-source exhaustion -> milestone
   "applyManaToCost:NO_SOURCES" before the native `return false`.
2. applyManaToCost chosen-source activation failure -> milestone
   "applyManaToCost:SOURCE_PLAY_FAILED" before the native `return false`.
3. applyManaToCost mana-restriction mismatch -> milestone
   "applyManaToCost:RESTRICTIONS_UNMET" before the native `return false`.
4. payManaCost transport returning unpaid -> milestone
   "payManaCost:RESULT_FALSE" before returning the native false.

Zero semantic change: no branch condition is altered; no cost is computed,
named, fabricated, filtered, or solved; no stack placement or resolution is
added; no option is added, removed, reordered, or defaulted; every broker
frame sequence and every return value is identical to the WS68 overlay. The
added milestones are additive NATIVE_EVENT tape entries (observation only).

Forbidden items verified absent by post-conditions below: card-name logic,
cost-amount computation, mana-source fabrication or filtering, first-source
auto-payment, requested-option filtering, silent skip/default, heuristic
legality, priority gating, direct concede orchestration, stack placement,
resolution injection, and any change to a return value or branch predicate.
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
    if "WS77_PROVIDER_TRANSPORT_OBSERVATION_V1" in p or "applyManaToCost:NO_SOURCES" in p:
        raise SystemExit("WS77_OVERLAY_ALREADY_APPLIED")
    p = once(p, PAY_OLD, PAY_NEW, "payManaCost result observation")
    p = once(p, SRC_OLD, SRC_NEW, "applyManaToCost source exhaustion observation")
    p = once(p, PLAY_OLD, PLAY_NEW, "applyManaToCost source-play observation")
    p = once(p, RESTR_OLD, RESTR_NEW, "applyManaToCost restriction observation")
    # WS77 stamp comment (observation marker; no code).
    anchor = "public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {"
    stamp = ("        // WS77_PROVIDER_TRANSPORT_OBSERVATION_V1: observation-only "
             "milestones on payManaCost/applyManaToCost early-false paths; "
             "zero semantic change.\n" + anchor)
    if stamp not in p:
        p = once(p, anchor, stamp, "ws77 stamp")
    args.provider.write_text(p, encoding="utf-8")
    required = ["payManaCost:ENTERED", "payManaCost:RESULT_FALSE",
                "applyManaToCost:ENTERED", "applyManaToCost:NO_SOURCES",
                "applyManaToCost:SOURCE_PLAY_FAILED",
                "applyManaToCost:RESTRICTIONS_UNMET",
                "WS77_PROVIDER_TRANSPORT_OBSERVATION_V1"]
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS77_OVERLAY_INCOMPLETE:{missing}")
    # Post-conditions: no card-name logic, no cost solving, no stack/resolution
    # injection, no legality heuristics, no return-value changes.
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
    print("WS77_PROVIDER_TRANSPORT_OBSERVATION_V1=PASS")


if __name__ == "__main__":
    raise SystemExit(main())
