#!/usr/bin/env python3
"""WS-39 qualification-only provider overlay for native commander-history restore.

This overlay only translates canonical state into the narrow XMage Rules-Core
state-load API added by WS-39.  It does not calculate commander tax, fabricate
historical cast events, or choose any player action.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"WS39_OVERLAY_ANCHOR_MISMATCH:{label}:count={text.count(old)}")
    return text.replace(old, new)


def main() -> int:
    text = SCENARIO.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "import mage.constants.Zone;\n",
        "import mage.constants.CommanderCardType;\nimport mage.constants.Zone;\n",
        "commander-card-type-import",
    )
    text = replace_once(
        text,
        "import mage.players.Player;\n",
        "import mage.players.Player;\n"
        "import mage.watchers.common.CommanderPlaysCountState;\n"
        "import mage.watchers.common.CommanderPlaysCountWatcher;\n",
        "watcher-imports",
    )
    text = replace_once(
        text,
        '            "execution_entry_mode", "temporal_state"\n',
        '            "execution_entry_mode", "temporal_state", "commander_history"\n',
        "top-key",
    )

    anchor = '''        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);\n        return new Applied(\n'''
    replacement = '''        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);\n        JsonObject commanderHistoryValidation = restoreCommanderHistory(\n                optionalArray(scenario, "commander_history"), game, players\n        );\n        validation.add("commander_history", commanderHistoryValidation);\n        return new Applied(\n'''
    text = replace_once(text, anchor, replacement, "restore-call")

    method_anchor = '''    private static JsonObject validateNaturalStart(List<Deck> decks, Map<Integer, JsonObject> specs) {\n'''
    method = r'''    private static JsonObject restoreCommanderHistory(
            JsonArray specs,
            Game game,
            List<? extends Player> players
    ) {
        Set<String> allowed = Set.of("seat", "commander_id", "card_name", "prior_command_zone_cast_count");
        Set<String> semanticCommanderIds = new HashSet<>();
        Set<UUID> nativeCommanderIds = new HashSet<>();
        List<CommanderPlaysCountState.Count> counts = new ArrayList<>();
        Map<UUID, Integer> expectedNative = new LinkedHashMap<>();
        Map<UUID, Integer> expectedPlayers = new LinkedHashMap<>();
        JsonArray readback = new JsonArray();

        for (JsonElement element : specs) {
            if (!element.isJsonObject()) throw fail("INVALID_COMMANDER_HISTORY: entry must be object");
            JsonObject spec = element.getAsJsonObject();
            rejectUnknown(spec, allowed, "commander_history");
            int seat = integer(spec, "seat");
            if (seat < 1 || seat > players.size()) {
                throw fail("INVALID_COMMANDER_HISTORY_PLAYER: seat=" + seat);
            }
            String semanticCommanderId = text(spec, "commander_id");
            if (!semanticCommanderIds.add(semanticCommanderId)) {
                throw fail("DUPLICATE_COMMANDER_HISTORY_ID: " + semanticCommanderId);
            }
            String cardName = text(spec, "card_name");
            int priorCount = integer(spec, "prior_command_zone_cast_count");
            if (priorCount < 0) throw fail("NEGATIVE_COMMANDER_HISTORY_COUNT");

            Player player = players.get(seat - 1);
            List<UUID> matches = new ArrayList<>();
            for (UUID commanderId : game.getCommandersIds(player, CommanderCardType.ANY, false)) {
                Card card = game.getCard(commanderId);
                if (card != null && cardName.equals(card.getName())) {
                    matches.add(commanderId);
                }
            }
            if (matches.size() != 1) {
                throw fail("COMMANDER_HISTORY_NATIVE_MAPPING_NOT_UNIQUE:" + semanticCommanderId
                        + ":matches=" + matches.size());
            }
            UUID nativeId = matches.get(0);
            if (!nativeCommanderIds.add(nativeId)) {
                throw fail("COMMANDER_HISTORY_NATIVE_ID_DUPLICATE:" + semanticCommanderId);
            }
            counts.add(new CommanderPlaysCountState.Count(nativeId, priorCount));
            expectedNative.put(nativeId, priorCount);
            expectedPlayers.merge(player.getId(), priorCount, Math::addExact);
        }

        CommanderPlaysCountWatcher watcher = game.getState().getWatcher(CommanderPlaysCountWatcher.class);
        if (watcher == null) throw fail("COMMANDER_HISTORY_WATCHER_MISSING");
        watcher.restoreStateForGameLoad(new CommanderPlaysCountState(counts), game);

        for (JsonElement element : specs) {
            JsonObject spec = element.getAsJsonObject();
            int seat = integer(spec, "seat");
            String semanticCommanderId = text(spec, "commander_id");
            String cardName = text(spec, "card_name");
            int expected = integer(spec, "prior_command_zone_cast_count");
            Player player = players.get(seat - 1);
            UUID nativeId = null;
            for (UUID candidate : game.getCommandersIds(player, CommanderCardType.ANY, false)) {
                Card card = game.getCard(candidate);
                if (card != null && cardName.equals(card.getName())) {
                    if (nativeId != null) throw fail("COMMANDER_HISTORY_READBACK_MAPPING_NOT_UNIQUE");
                    nativeId = candidate;
                }
            }
            if (nativeId == null) throw fail("COMMANDER_HISTORY_READBACK_MAPPING_MISSING");
            int actual = watcher.getPlaysCount(nativeId);
            requireNative(actual == expected, "commander-history:" + semanticCommanderId);
            JsonObject row = new JsonObject();
            row.addProperty("seat", seat);
            row.addProperty("commander_id", semanticCommanderId);
            row.addProperty("card_name", cardName);
            row.addProperty("prior_command_zone_cast_count", actual);
            readback.add(row);
        }
        for (int zero = 0; zero < players.size(); zero++) {
            Player player = players.get(zero);
            int expected = expectedPlayers.getOrDefault(player.getId(), 0);
            requireNative(watcher.getPlayerCount(player.getId()) == expected, "commander-history-player:P" + (zero + 1));
        }

        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-native-commander-history-state/1.0.0");
        result.addProperty("rules_core_authoritative", true);
        result.addProperty("synthetic_historical_events", false);
        result.addProperty("entry_count", specs.size());
        result.add("commanders", readback);
        result.addProperty("valid", true);
        return result;
    }

'''
    text = replace_once(text, method_anchor, method + method_anchor, "restore-method")

    SCENARIO.write_text(text, encoding="utf-8")
    print("WS39_PROVIDER_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
