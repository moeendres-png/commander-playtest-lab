#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, got {n}")
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-java', type=Path, required=True)
    args = ap.parse_args()
    p = args.state_java
    s = p.read_text(encoding='utf-8')

    s = once(s,
        '            if (candidates.size() != 1) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BIND_NONUNIQUE:" + s.semanticId + ":" + candidates.size());\n            }\n            Card c = candidates.get(0);',
        '            if (candidates.isEmpty()) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BIND_MISSING:" + s.semanticId);\n            }\n            // Equal physical cards are intentionally indistinguishable to Forge. Semantic identity is a\n            // provider-neutral mapping layer only; choose the first still-unbound card in native zone order.\n            Card c = candidates.get(0);',
        'duplicate physical card binding')

    # GameState.applyToGame can trigger native command-zone effect maintenance while we bind
    # semantic identities. Iterate a stable copy of each native zone to avoid observing a live
    # ArrayList while Forge performs that native housekeeping.
    s = once(s,
        '            for (Card c : player(game, s.controller).getCardsIn(zoneType(s.zone), false)) {',
        '            for (Card c : new ArrayList<>(player(game, s.controller).getCardsIn(zoneType(s.zone), false))) {',
        'stable native zone binding iteration')

    s = once(s,
        '        for (String[] p : rows("COMMANDER_LAB_WS40_STACK_SPECS_B64")) {',
        '        List<String[]> ws40StackRows = rows("COMMANDER_LAB_WS40_STACK_SPECS_B64");\n        java.util.Collections.reverse(ws40StackRows);\n        for (String[] p : ws40StackRows) {',
        'stack construction order')

    s = once(s,
        '        for (var e : c.getCounters().entrySet()) entries.add(Map.entry(e.getKey(), e.getValue()));',
        '        for (var e : c.getCounters().entrySet()) entries.add(Map.entry(e.getElement(), e.getCount()));',
        'guava multiset counter entries')

    s = s.replace('c.isSick()', 'c.hasSickness()')

    # Natural construction evidence is bound to the same provider configuration digest as native-state-load records.
    s = once(s,
        '            + ",\\\"decks\\\":" + decks + ",\\\"rules_commander\\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander) + "}";',
        '            + ",\\\"decks\\\":" + decks + ",\\\"rules_commander\\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)\n            + ",\\\"config_binding_digest\\\":" + Ws23ForgeVerticalProvider.esc(env("COMMANDER_LAB_WS40_CONFIG_BINDING_DIGEST")) + "}";',
        'natural config binding')

    p.write_text(s, encoding='utf-8')
    print('WS40_SUCCESSOR_STATE_JAVA_FIX=PASS')


if __name__ == '__main__':
    main()
