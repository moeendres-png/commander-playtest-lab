#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD = '''    private static String eligibleBlockersJson(Game game) {
        Combat combat = game.getCombat();
        if (combat == null) return "[]";
        List<String> ids = new ArrayList<>();
        Player active = game.getPhaseHandler().getPlayerTurn();
        for (Player defender : game.getPlayers()) {
            if (defender == active) continue;
            for (Card blocker : defender.getCreaturesInPlay()) {
                boolean legal = false;
                for (Card attacker : combat.getAttackers()) {
                    if (CombatUtil.canBlock(attacker, blocker, combat)) { legal = true; break; }
                }
                if (!legal) continue;
                String sid = semanticOf(blocker);
                if (sid == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_COMBAT_NATIVE_ELIGIBLE_BLOCKER_IDENTITY_UNAVAILABLE:" + blocker);
                ids.add(sid);
            }
        }
        ids.sort(String::compareTo);
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < ids.size(); i++) { if (i > 0) b.append(','); b.append(Ws23ForgeVerticalProvider.esc(ids.get(i))); }
        return b.append(']').toString();
    }
'''

NEW = '''    private static String eligibleBlockersJson(Game game) {
        Combat combat = game.getCombat();
        if (combat == null) return "[]";
        // This is a legal-option observation surface, not a request-state mirror.
        // Blocker options exist only during Forge's native Declare Blockers step.
        if (game.getPhaseHandler().getPhase() != PhaseType.COMBAT_DECLARE_BLOCKERS) {
            return "[]";
        }
        Player defender = game.getPhaseHandler().getPriorityPlayer();
        if (defender == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_COMBAT_NATIVE_BLOCKER_ACTOR_UNAVAILABLE");
        }
        if (defender == game.getPhaseHandler().getPlayerTurn()) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_COMBAT_NATIVE_BLOCKER_ACTOR_IS_ACTIVE_PLAYER");
        }
        List<String> ids = new ArrayList<>();
        for (Card blocker : defender.getCreaturesInPlay()) {
            boolean legal = false;
            for (Card attacker : combat.getAttackers()) {
                // Forge owns multiplayer defending-player partition (CR 802.4a)
                // and all attacker/blocker restrictions through this Core API.
                // No requested option list is read or used to filter the result.
                if (CombatUtil.canBlock(attacker, blocker, combat)) { legal = true; break; }
            }
            if (!legal) continue;
            String sid = semanticOf(blocker);
            if (sid == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_COMBAT_NATIVE_ELIGIBLE_BLOCKER_IDENTITY_UNAVAILABLE:" + blocker);
            ids.add(sid);
        }
        ids.sort(String::compareTo);
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < ids.size(); i++) { if (i > 0) b.append(','); b.append(Ws23ForgeVerticalProvider.esc(ids.get(i))); }
        return b.append(']').toString();
    }
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path, required=True)
    args = ap.parse_args()
    path = args.state_java
    text = path.read_text(encoding="utf-8")
    if NEW in text:
        print("WS45_V104_NATIVE_BLOCKER_PARTITION=ALREADY_APPLIED")
        return 0
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"WS45_V104_NATIVE_BLOCKER_PARTITION_TARGET:expected=1:actual={count}")
    text = text.replace(OLD, NEW, 1)
    required = [
        'getPhase() != PhaseType.COMBAT_DECLARE_BLOCKERS',
        'getPriorityPlayer()',
        'WS45_COMBAT_NATIVE_BLOCKER_ACTOR_IS_ACTIVE_PLAYER',
        'CombatUtil.canBlock(attacker, blocker, combat)',
    ]
    if not all(x in text for x in required):
        raise SystemExit("WS45_V104_NATIVE_BLOCKER_PARTITION_INCOMPLETE")
    path.write_text(text, encoding="utf-8")
    print("WS45_V104_NATIVE_BLOCKER_PARTITION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
