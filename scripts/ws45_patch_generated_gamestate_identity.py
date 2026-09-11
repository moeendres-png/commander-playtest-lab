#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD = '''    private static void bindNonStackObjects(Game game) {
        semanticCards.clear();
        commanderCards.clear();
        for (int i = 0; i < objectSpecs.size(); i++) {
            ObjSpec s = objectSpecs.get(i);
            if ("stack".equals(s.zone)) continue;
            int expectedNativeId = 1000 + i;
            Card c = game.findById(expectedNativeId);
            if (c == null) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_NATIVE_ID_MISSING:" + s.semanticId + ":" + expectedNativeId);
            }
            Set<Card> noneUsed = java.util.Collections.emptySet();
            if (!sameCard(c, s, noneUsed)) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_NATIVE_ID_STATE_MISMATCH:" + s.semanticId + ":" + expectedNativeId);
            }
            if (s.zonePosition != null && ("library".equals(s.zone) || "revealed".equals(s.zone))) {
                Card at = player(game, s.controller).getCardsIn(ZoneType.Library, false).get(s.zonePosition);
                if (at != c) {
                    throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_NATIVE_ID_LIBRARY_POSITION_MISMATCH:" + s.semanticId);
                }
            }
            semanticCards.put(s.semanticId, c);
            if (!s.commanderId.isEmpty()) commanderCards.put(s.commanderId, c);
        }
    }'''

NEW = '''    private static void bindNonStackObjects(Game game, GameState state) {
        semanticCards.clear();
        commanderCards.clear();
        for (int i = 0; i < objectSpecs.size(); i++) {
            ObjSpec s = objectSpecs.get(i);
            if ("stack".equals(s.zone)) continue;
            int expectedStateId = 1000 + i;
            Card c;
            try {
                c = forge.game.qualification.Ws45GameStateIdentityAccess.cardForStateId(state, game, expectedStateId);
            } catch (RuntimeException ex) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_STATE_ID_MISSING:" + s.semanticId + ":" + expectedStateId + ":" + ex.getMessage());
            }
            Set<Card> noneUsed = java.util.Collections.emptySet();
            if (!sameCard(c, s, noneUsed)) {
                String actualName = c.getPaperCard() == null ? c.getName() : c.getPaperCard().getName();
                String actualZone = c.getZone() == null ? "null" : String.valueOf(c.getZone().getZoneType());
                throw new Ws23ForgeVerticalProvider.ControlledStop(
                        "WS45_STATE_BIND_STATE_ID_STATE_MISMATCH:" + s.semanticId + ":" + expectedStateId
                        + ":actual_name=" + actualName + ":expected_name=" + s.name
                        + ":actual_owner=" + playerId(game, c.getOwner()) + ":expected_owner=P" + s.owner
                        + ":actual_controller=" + playerId(game, c.getController()) + ":expected_controller=P" + s.controller
                        + ":actual_zone=" + actualZone + ":expected_zone=" + s.zone);
            }
            if (s.zonePosition != null && ("library".equals(s.zone) || "revealed".equals(s.zone))) {
                Card at = player(game, s.controller).getCardsIn(ZoneType.Library, false).get(s.zonePosition);
                if (at != c) {
                    throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_STATE_ID_LIBRARY_POSITION_MISMATCH:" + s.semanticId);
                }
            }
            semanticCards.put(s.semanticId, c);
            if (!s.commanderId.isEmpty()) commanderCards.put(s.commanderId, c);
        }
    }'''

CALL_OLD = '        bindNonStackObjects(game);'
CALL_NEW = '        bindNonStackObjects(game, state);'

LIFE_OLD = '''            String life = env("COMMANDER_LAB_WS40_LIFE_P" + seat);
            lines.add(prefix + "life=" + (life.isEmpty() ? "40" : life));'''
LIFE_NEW = '''            String life = env("COMMANDER_LAB_WS40_LIFE_P" + seat);
            int requestedLife = life.isEmpty() ? 40 : Integer.parseInt(life);
            // Forge GameState currently checks SBAs during apply. Preserve a requested <=0 life
            // as a post-apply native state-loader assignment so construction can expose the legal
            // pre-SBA state instead of eliminating/reindexing multiplayer seats during loading.
            lines.add(prefix + "life=" + (requestedLife <= 0 ? "1" : Integer.toString(requestedLife)));'''

APPLY_MARKER = '        state.applySynchronously(game);'
APPLY_INSERT = '''
        // Complete non-positive life materialization only after Forge's GameState-internal SBA pass.
        // Use registered-player identity so multiplayer seat identity cannot shift if Forge changes
        // active-player membership. No observation is emitted from the request value; snapshots read
        // the resulting native Player state below.
        for (int seat = 1; seat <= game.getRegisteredPlayers().size(); seat++) {
            String requestedLifeRaw = env("COMMANDER_LAB_WS40_LIFE_P" + seat);
            if (requestedLifeRaw.isEmpty()) continue;
            int requestedLife = Integer.parseInt(requestedLifeRaw);
            if (requestedLife <= 0) {
                Player registered = game.getRegisteredPlayers().get(seat - 1);
                if (registered.hasLost()) {
                    throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_LOAD_PREMATURE_ELIMINATION:P" + seat);
                }
                registered.setLife(requestedLife, null);
            }
        }'''


def replace_exact(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'WS45 expected one {label}, got {count}')
    return text.replace(old, new, 1)


def insert_after_exact(text: str, marker: str, insertion: str, sentinel: str, label: str) -> str:
    if sentinel in text:
        return text
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f'WS45 expected one {label}, got {count}')
    return text.replace(marker, marker + insertion, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-java', type=Path, required=True)
    args = ap.parse_args()
    text = args.state_java.read_text(encoding='utf-8')
    text = replace_exact(text, OLD, NEW, 'obsolete native-id binding block')
    text = replace_exact(text, CALL_OLD, CALL_NEW, 'obsolete bind call')
    text = replace_exact(text, LIFE_OLD, LIFE_NEW, 'multiplayer non-positive life loader block')
    text = insert_after_exact(text, APPLY_MARKER, APPLY_INSERT, 'WS45_STATE_LOAD_PREMATURE_ELIMINATION', 'synchronous GameState apply marker')
    if 'game.findById(expectedNativeId)' in text or 'candidates.get(0)' in text:
        raise SystemExit('WS45 forbidden identity fallback remains')
    if 'WS45_STATE_LOAD_PREMATURE_ELIMINATION' not in text:
        raise SystemExit('WS45 multiplayer life stabilization missing')
    args.state_java.write_text(text, encoding='utf-8')
    print('WS45_GAMESTATE_IDENTITY_BINDING=PASS')
    print('WS45_MULTIPLAYER_NONPOSITIVE_LIFE_STATE_LOAD=PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
