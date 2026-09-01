#!/usr/bin/env python3
"""Run MICRO_REPLACEMENT through Forge's native combat-damage transaction.

This qualification-only fix does not compute or apply damage. It preserves a
pre-damage setup snapshot, then invokes the exact COMBAT_DAMAGE turn-based
sequence used by pinned Forge PhaseHandler: assignCombatDamage(false), followed
by dealAssignedDamage().
"""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    path = args.provider
    java = path.read_text(encoding="utf-8")

    # Scope the first anchor to applyMicroReplacementState. The same latch
    # shape exists in MICRO_STACK and must not be touched here.
    java = replace_once(
        java,
        '''    static void applyMicroReplacementState(Game game, Broker broker) {
        java.util.List<String> lines = java.util.List.of(
''',
        '''    static void applyMicroReplacementState(Game game, Broker broker) {
        java.util.concurrent.atomic.AtomicReference<String> replacementSetupSnapshot = new java.util.concurrent.atomic.AtomicReference<>();
        java.util.List<String> lines = java.util.List.of(
''',
        "replacement method scoped setup snapshot reference",
    )

    java = replace_once(
        java,
        '''                game.updateCombatForView();
                if (!combat.isAttacking(attacker, p2)) throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_COMBAT_MISMATCH");
                game.getPhaseHandler().setPriority(p1);
            } catch (RuntimeException exc) {
''',
        '''                game.updateCombatForView();
                if (!combat.isAttacking(attacker, p2)) throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_COMBAT_MISMATCH");
                game.getPhaseHandler().setPriority(p1);

                // Preserve the exact requested native setup before damage. Then execute
                // the same native turn-based action sequence as PhaseHandler COMBAT_DAMAGE.
                replacementSetupSnapshot.set(microReplacementSetupSnapshot(game, broker));
                if (!combat.assignCombatDamage(false)) {
                    throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_ASSIGNMENT_FAILED");
                }
                combat.dealAssignedDamage();
                broker.recordAutomatic("MICRO_REPLACEMENT_NATIVE_POST_DAMAGE_LIFE:P2:" + p2.getLife());
                if (p2.getLife() != 34) {
                    throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_NATIVE_DAMAGE_MISMATCH:P2=" + p2.getLife());
                }
                // Evidence label only: the amount is independently established by the
                // 40 -> 34 native life transition. No adapter damage is applied here.
                broker.recordAutomatic("MICRO_REPLACEMENT_NATIVE_DAMAGE:P2:6");
                throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_TERMINAL");
            } catch (RuntimeException exc) {
''',
        "native combat damage execution",
    )

    java = replace_once(
        java,
        '''        if (stateFailure.get() != null) throw stateFailure.get();
        broker.out.println("{\\\"protocol\\\":" + esc(PROTOCOL)
            + ",\\\"message_type\\\":\\\"QUALIFICATION_STATE\\\""
            + ",\\\"request_id\\\":\\\"micro-replacement-state\\\""
            + ",\\\"session_id\\\":" + esc(SESSION_ID)
            + ",\\\"payload\\\":{\\\"stage\\\":\\\"after_native_setup_validation\\\",\\\"snapshot\\\":"
            + microReplacementSetupSnapshot(game, broker) + "}}");
        broker.out.flush();
''',
        '''        RuntimeException replacementFailure = stateFailure.get();
        if (replacementSetupSnapshot.get() == null) {
            if (replacementFailure != null) throw replacementFailure;
            throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_SETUP_SNAPSHOT_MISSING");
        }
        broker.out.println("{\\\"protocol\\\":" + esc(PROTOCOL)
            + ",\\\"message_type\\\":\\\"QUALIFICATION_STATE\\\""
            + ",\\\"request_id\\\":\\\"micro-replacement-state\\\""
            + ",\\\"session_id\\\":" + esc(SESSION_ID)
            + ",\\\"payload\\\":{\\\"stage\\\":\\\"after_native_setup_validation\\\",\\\"snapshot\\\":"
            + replacementSetupSnapshot.get() + "}}");
        broker.out.flush();
        if (replacementFailure != null) throw replacementFailure;
''',
        "pre-damage setup evidence before controlled terminal",
    )

    path.write_text(java, encoding="utf-8")
    print("FORGE_MICRO_REPLACEMENT_NATIVE_DAMAGE_FIX=PASS")


if __name__ == "__main__":
    main()
