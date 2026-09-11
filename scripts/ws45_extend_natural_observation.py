#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD = '''    private static String naturalDecksJson(Game game) {
        StringBuilder decks = new StringBuilder("[");
        List<RegisteredPlayer> rps = game.getMatch().getPlayers();
        for (int i = 0; i < rps.size(); i++) {
            if (i > 0) decks.append(',');
            RegisteredPlayer rp = rps.get(i);
            int mainCount = 0, mountainCount = 0;
            for (Map.Entry<PaperCard,Integer> e : rp.getDeck().getMain()) {
                mainCount += e.getValue();
                if ("Mountain".equals(e.getKey().getName())) mountainCount += e.getValue();
            }
            StringBuilder commanderNames = new StringBuilder("[");
            for (int j = 0; j < rp.getCommanders().size(); j++) {
                if (j > 0) commanderNames.append(','); commanderNames.append(q(rp.getCommanders().get(j).getName()));
            }
            commanderNames.append(']');
            Player p = game.getPlayers().get(i);
            decks.append("{\\"player_id\\":\\"P").append(i + 1).append("\\",\\"main_count\\":").append(mainCount)
                    .append(",\\"mountain_count\\":").append(mountainCount)
                    .append(",\\"commander_count\\":").append(rp.getCommanders().size())
                    .append(",\\"commander_names\\":").append(commanderNames)
                    .append(",\\"registered_starting_life\\":").append(rp.getStartingLife())
                    .append(",\\"live_life\\":").append(p.getLife())
                    .append(",\\"hand_count\\":").append(p.getCardsIn(ZoneType.Hand).size())
                    .append(",\\"library_count\\":").append(p.getCardsIn(ZoneType.Library).size())
                    .append(",\\"native_commander_count\\":").append(p.getCommanders().size()).append('}');
        }
        return decks.append(']').toString();
    }'''

NEW = '''    private static String naturalDecksJson(Game game) {
        StringBuilder decks = new StringBuilder("[");
        List<RegisteredPlayer> rps = game.getMatch().getPlayers();
        for (int i = 0; i < rps.size(); i++) {
            if (i > 0) decks.append(',');
            RegisteredPlayer rp = rps.get(i);
            int mainCount = 0, mountainCount = 0;
            java.util.TreeMap<String,Integer> mainEntries = new java.util.TreeMap<>();
            for (Map.Entry<PaperCard,Integer> e : rp.getDeck().getMain()) {
                mainCount += e.getValue();
                mainEntries.merge(e.getKey().getName(), e.getValue(), Integer::sum);
                if ("Mountain".equals(e.getKey().getName())) mountainCount += e.getValue();
            }
            StringBuilder mainJson = new StringBuilder("[");
            boolean firstEntry = true;
            for (Map.Entry<String,Integer> e : mainEntries.entrySet()) {
                if (!firstEntry) mainJson.append(','); firstEntry = false;
                mainJson.append("{\\"card_identity\\":").append(q(e.getKey())).append(",\\"count\\":").append(e.getValue()).append('}');
            }
            mainJson.append(']');

            java.util.TreeMap<String,Integer> commanderEntries = new java.util.TreeMap<>();
            StringBuilder commanderNames = new StringBuilder("[");
            for (int j = 0; j < rp.getCommanders().size(); j++) {
                PaperCard pc = rp.getCommanders().get(j);
                commanderEntries.merge(pc.getName(), 1, Integer::sum);
                if (j > 0) commanderNames.append(','); commanderNames.append(q(pc.getName()));
            }
            commanderNames.append(']');
            StringBuilder commanderEntryJson = new StringBuilder("[");
            firstEntry = true;
            for (Map.Entry<String,Integer> e : commanderEntries.entrySet()) {
                if (!firstEntry) commanderEntryJson.append(','); firstEntry = false;
                commanderEntryJson.append("{\\"card_identity\\":").append(q(e.getKey())).append(",\\"count\\":").append(e.getValue()).append('}');
            }
            commanderEntryJson.append(']');

            Player p = game.getPlayers().get(i);
            StringBuilder nativeCommanders = new StringBuilder("[");
            for (int j = 0; j < p.getCommanders().size(); j++) {
                Card c = p.getCommanders().get(j);
                if (!c.getCounters().isEmpty()) throw fail("WS45_NATURAL_COMMANDER_COUNTERS_UNEXPECTED:" + c.getId());
                if (j > 0) nativeCommanders.append(',');
                nativeCommanders.append("{\\"card_identity\\":").append(q(c.getPaperCard() == null ? c.getName() : c.getPaperCard().getName()))
                        .append(",\\"owner\\":").append(q(pid(game, c.getOwner().getId())))
                        .append(",\\"controller\\":").append(q(pid(game, c.getController().getId())))
                        .append(",\\"zone\\":").append(q(c.getZone() == null ? null : c.getZone().getZoneType().toString().toLowerCase()))
                        .append(",\\"cast_count\\":").append(c.getOwner().getCommanderCast(c))
                        .append(",\\"tapped\\":").append(c.isTapped())
                        .append(",\\"face_down\\":").append(c.isFaceDown())
                        .append(",\\"counters\\":{} }");
            }
            nativeCommanders.append(']');

            decks.append("{\\"player_id\\":\\"P").append(i + 1).append("\\",\\"main_count\\":").append(mainCount)
                    .append(",\\"mountain_count\\":").append(mountainCount)
                    .append(",\\"main_entries\\":").append(mainJson)
                    .append(",\\"commander_count\\":").append(rp.getCommanders().size())
                    .append(",\\"commander_names\\":").append(commanderNames)
                    .append(",\\"commander_entries\\":").append(commanderEntryJson)
                    .append(",\\"registered_starting_life\\":").append(rp.getStartingLife())
                    .append(",\\"live_life\\":").append(p.getLife())
                    .append(",\\"poison\\":").append(p.getCounters(forge.game.card.CounterEnumType.POISON))
                    .append(",\\"lost\\":").append(p.hasLost())
                    .append(",\\"in_game\\":").append(p.isInGame())
                    .append(",\\"hand_count\\":").append(p.getCardsIn(ZoneType.Hand).size())
                    .append(",\\"library_count\\":").append(p.getCardsIn(ZoneType.Library).size())
                    .append(",\\"native_commander_count\\":").append(p.getCommanders().size())
                    .append(",\\"native_commanders\\":").append(nativeCommanders).append('}');
        }
        return decks.append(']').toString();
    }'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict-java', type=Path, required=True)
    args = ap.parse_args()
    text = args.strict_java.read_text(encoding='utf-8')
    if NEW in text:
        print('WS45_NATURAL_OBSERVATION_EXTENSION=ALREADY_APPLIED')
        return 0
    n = text.count(OLD)
    if n != 1:
        raise SystemExit(f'WS45 natural observation method target count {n}, expected 1')
    text = text.replace(OLD, NEW, 1)
    args.strict_java.write_text(text, encoding='utf-8')
    print('WS45_NATURAL_OBSERVATION_EXTENSION=PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
