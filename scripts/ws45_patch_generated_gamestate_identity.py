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
                        + ":actual_owner=" + playerIndex(c.getOwner()) + ":expected_owner=" + s.owner
                        + ":actual_controller=" + playerIndex(c.getController()) + ":expected_controller=" + s.controller
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-java', type=Path, required=True)
    args = ap.parse_args()
    text = args.state_java.read_text(encoding='utf-8')
    if NEW in text and CALL_NEW in text:
        print('WS45_GAMESTATE_IDENTITY_BINDING=ALREADY_APPLIED')
        return 0
    if text.count(OLD) != 1:
        raise SystemExit(f'WS45 expected one obsolete native-id binding block, got {text.count(OLD)}')
    if text.count(CALL_OLD) != 1:
        raise SystemExit(f'WS45 expected one obsolete bind call, got {text.count(CALL_OLD)}')
    text = text.replace(OLD, NEW, 1).replace(CALL_OLD, CALL_NEW, 1)
    if 'game.findById(expectedNativeId)' in text or 'candidates.get(0)' in text:
        raise SystemExit('WS45 forbidden identity fallback remains')
    args.state_java.write_text(text, encoding='utf-8')
    print('WS45_GAMESTATE_IDENTITY_BINDING=PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
