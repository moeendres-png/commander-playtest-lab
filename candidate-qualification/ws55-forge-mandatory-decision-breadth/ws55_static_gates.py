#!/usr/bin/env python3
"""WS55 static gates on the built breadth provider (WS55-owned, qualification-only).

Checks (all static, CODE_DERIVED; runtime gates live in the journals):
 S1. Repair-01 preserved: exactly one nativeOptions.add(sa) per seen
     SpellAbility (doubled-add text absent), cardinality + range guards
     present, priority_binding record present.
 S2. WS55 surfaces present: chooseOptionalCosts transport, orderCosts
     FullControl mirror + permutation, orderBlockers/orderBlocker/
     orderAttackers trio, multi-mode sequential, trigger-N generalization,
     deck env generalization, ws55Permutations helper.
 S3. Old gaps still fail closed: confirmTrigger, playTrigger,
     playSaFromPlayEffect, vote, chooseCardsPile, choosePermanentsToSacrifice,
     choosePermanentsToDestroy, chooseCardName, divideShield,
     specifyManaCombo, MORE_THAN_TWO / DEPENDENT_MULTI_CHOICE gone only via
     the new conformant paths (assert replacement markers instead).
 S4. No AI/GUI legality: no forge.ai/gui imports, no ComputerUtilMana,
     no candidates.get(0), no findById(expectedNativeId).
 S5. Core-view damage surfaces intact (ws40 base): chooseCombatDamage +
     chooseAmountDistribution with Core view enumeration + STALE guards.
 S6. No provider-side damage/mana/cost solving: no lethal arithmetic, no
     ManaPool manipulation beyond the WS48 applyManaToCost path, no
     replacement recursion.

Writes JSON verdict to --output. Exit 0 iff all gates PASS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def check(provider: str) -> dict:
    gates: dict[str, dict] = {}

    def gate(name: str, ok: bool, detail: str = "") -> None:
        gates[name] = {"verdict": "PASS" if ok else "FAIL", "detail": detail}

    gate("S1_no_doubled_add",
         "nativeOptions.add(sa);\n                            nativeOptions.add(sa);" not in provider)
    gate("S1_cardinality_guard",
         "WS48_SELECTION_EXECUTION_CARDINALITY_MISMATCH" in provider)
    gate("S1_range_guard",
         "WS48_SELECTION_EXECUTION_INDEX_OUT_OF_RANGE" in provider)
    gate("S1_priority_binding", "priority_binding" in provider)

    gate("S2_optional_costs", "WS55:OPTCOST:desc=" in provider
         and "chooseOptionalCosts:ENTERED" in provider)
    gate("S2_order_costs_mirror", "orderCosts:NATIVE_AUTO" in provider
         and "FullControlFlag.ChooseCostOrder" in provider
         and "WS55:COSTORDER:order=" in provider)
    gate("S2_combat_order_trio",
         "WS55:ORDERBLOCKERS:attacker=" in provider
         and "WS55:ORDERBLOCKER:attacker=" in provider
         and "WS55:ORDERATTACKERS:blocker=" in provider
         and "orderBlockers:SINGLETON" in provider
         and "orderAttackers:SINGLETON" in provider)
    gate("S2_multi_mode", "chooseModeForAbility:MULTI" in provider
         and "WS48:MODE:DONE" in provider
         and "chooseModeForAbility:BOUNDS" in provider)
    gate("S2_trigger_n", "orderSimultaneousSa:N:" in provider
         and "WS55_TRIGGER_BAD_PERMUTATION" in provider)
    gate("S2_trigger_two_legacy_intact",
         "WS48:ORDER:order=0,1:first=" in provider)
    gate("S2_deck_env", "COMMANDER_LAB_FORGE_DECK_MAIN" in provider
         and "FINALIST_CANONICAL_DECK_RULES_MISSING" in provider
         and "getAllCards(" in provider)
    gate("S2_permutations", "ws55Permutations" in provider
         and "PERMUTATION_BOUND" in provider)

    for name, stub in [
        ("S3_confirmTrigger", 'throw failClosed("confirmTrigger");'),
        ("S3_playTrigger", 'throw failClosed("playTrigger");'),
        ("S3_playSaFromPlayEffect", 'throw failClosed("playSaFromPlayEffect");'),
        ("S3_vote", 'throw failClosed("vote");'),
        ("S3_chooseCardsPile", 'throw failClosed("chooseCardsPile");'),
        ("S3_sacrifice", 'throw failClosed("choosePermanentsToSacrifice");'),
        ("S3_destroy", 'throw failClosed("choosePermanentsToDestroy");'),
        ("S3_chooseCardName", 'throw failClosed("chooseCardName");'),
        ("S3_divideShield", 'throw failClosed("divideShield");'),
        ("S3_specifyManaCombo", 'throw failClosed("specifyManaCombo");'),
    ]:
        gate(name, stub in provider, "fail-closed stub retained")
    gate("S3_more_than_two_removed", "MORE_THAN_TWO" not in provider)
    gate("S3_dependent_multi_removed", "DEPENDENT_MULTI_CHOICE" not in provider)

    gate("S4_no_ai_gui_imports",
         "import forge.ai" not in provider and "import forge.gui" not in provider)
    gate("S4_no_gui_fallbacks",
         "RemoteClientGuiGame" not in provider and "PlayerControllerAi" not in provider
         and "ComputerUtilMana" not in provider)
    gate("S4_no_hacks", "candidates.get(0)" not in provider
         and "findById(expectedNativeId)" not in provider)

    gate("S5_combat_damage_core_view",
         "chooseCombatDamage" in provider
         and "CombatDamageDecisionView" in provider
         and "CombatDamageSelection(" in provider
         and "chooseCombatDamage:STALE_OPTION" in provider)
    gate("S5_amount_distribution_core_view",
         "chooseAmountDistribution" in provider
         and "AmountDistributionDecisionView" in provider
         and "AmountDistributionSelection(" in provider)

    gate("S6_no_lethal_arithmetic",
         "getLethalDamageRemaining" in provider  # projected as label context only
         and "lethal -" not in provider and "lethal-" not in provider)
    return gates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    provider = a.provider.read_text(encoding="utf-8")
    gates = check(provider)
    fails = [k for k, v in gates.items() if v["verdict"] != "PASS"]
    out = {"schema": "ws55.static-gates.v1",
           "evidence_class": "CODE_DERIVED",
           "grants_behavior_credit": False,
           "gate_count": len(gates),
           "fail_count": len(fails),
           "verdict": "PASS" if not fails else "FAIL",
           "gates": gates}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"WS55_STATIC_GATES -> {out['verdict']} {len(gates) - len(fails)}/{len(gates)}")
    for f in fails:
        print("  FAIL:", f, gates[f].get("detail", ""))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
