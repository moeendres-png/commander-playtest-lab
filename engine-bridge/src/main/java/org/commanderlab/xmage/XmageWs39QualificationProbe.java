package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.Mana;
import mage.abilities.SpellAbility;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.game.Game;
import mage.players.Player;
import mage.watchers.common.CommanderPlaysCountWatcher;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * WS-39 qualification-only readback/probe surface.
 *
 * <p>This class never changes the native game state. Commander-cost probing is
 * performed on a copied SpellAbility and delegates the cost modification to
 * the XMage Card implementation. The bridge neither calculates Commander tax
 * nor fabricates historical events.</p>
 */
final class XmageWs39QualificationProbe {

    private XmageWs39QualificationProbe() {}

    static JsonObject snapshot(
            JsonObject configuredScenario,
            Game game,
            List<? extends Player> sessionPlayers
    ) {
        if (configuredScenario == null || !configuredScenario.has("commander_history")) {
            throw new IllegalStateException("WS39_COMMANDER_HISTORY_NOT_CONFIGURED");
        }
        if (!configuredScenario.get("commander_history").isJsonArray()) {
            throw new IllegalStateException("WS39_COMMANDER_HISTORY_NOT_ARRAY");
        }
        CommanderPlaysCountWatcher watcher = game.getState().getWatcher(CommanderPlaysCountWatcher.class);
        if (watcher == null) {
            throw new IllegalStateException("WS39_COMMANDER_HISTORY_WATCHER_MISSING");
        }

        JsonArray history = new JsonArray();
        JsonArray costs = new JsonArray();
        Map<Integer, Integer> expectedBySeat = new LinkedHashMap<>();
        Map<Integer, Integer> actualBySeat = new LinkedHashMap<>();

        for (JsonElement element : configuredScenario.getAsJsonArray("commander_history")) {
            if (!element.isJsonObject()) {
                throw new IllegalStateException("WS39_COMMANDER_HISTORY_ENTRY_NOT_OBJECT");
            }
            JsonObject spec = element.getAsJsonObject();
            int seat = spec.get("seat").getAsInt();
            String semanticId = spec.get("commander_id").getAsString();
            String cardName = spec.get("card_name").getAsString();
            int expectedInitial = spec.get("prior_command_zone_cast_count").getAsInt();
            if (seat < 1 || seat > sessionPlayers.size() || expectedInitial < 0) {
                throw new IllegalStateException("WS39_COMMANDER_HISTORY_ENTRY_INVALID:" + semanticId);
            }

            Player player = currentPlayer(game, sessionPlayers.get(seat - 1));
            Card commander = uniqueCommander(game, player, cardName, semanticId);
            int actual = watcher.getPlaysCount(commander.getMainCard().getId());
            expectedBySeat.merge(seat, expectedInitial, Math::addExact);
            actualBySeat.merge(seat, actual, Math::addExact);

            JsonObject historyRow = new JsonObject();
            historyRow.addProperty("seat", seat);
            historyRow.addProperty("commander_id", semanticId);
            historyRow.addProperty("card_name", cardName);
            historyRow.addProperty("initial_prior_command_zone_cast_count", expectedInitial);
            historyRow.addProperty("live_command_zone_cast_count", actual);
            history.add(historyRow);

            SpellAbility original = commander.getSpellAbility();
            if (original == null) {
                throw new IllegalStateException("WS39_COMMANDER_SPELL_ABILITY_MISSING:" + semanticId);
            }
            SpellAbility probe = original.copy();
            probe.setControllerId(player.getId());
            probe.resetCosts();
            Mana base = probe.getManaCosts().getMana();
            boolean accepted = commander.commanderCost(game, probe, probe);
            if (!accepted) {
                throw new IllegalStateException("WS39_COMMANDER_COST_PROBE_REJECTED:" + semanticId);
            }
            Mana adjusted = probe.getManaCostsToPay().getMana();

            JsonObject costRow = new JsonObject();
            costRow.addProperty("seat", seat);
            costRow.addProperty("commander_id", semanticId);
            costRow.addProperty("card_name", cardName);
            costRow.addProperty("native_base_mana", base.toString());
            costRow.addProperty("native_base_mana_count", base.count());
            costRow.addProperty("native_commander_adjusted_mana", adjusted.toString());
            costRow.addProperty("native_commander_adjusted_mana_count", adjusted.count());
            costRow.addProperty("rules_core_method", "Card.commanderCost");
            costs.add(costRow);
        }

        JsonArray playerTotals = new JsonArray();
        for (int seat = 1; seat <= sessionPlayers.size(); seat++) {
            Player player = currentPlayer(game, sessionPlayers.get(seat - 1));
            int actual = watcher.getPlayerCount(player.getId());
            int summed = actualBySeat.getOrDefault(seat, 0);
            if (actual != summed) {
                throw new IllegalStateException(
                        "WS39_COMMANDER_HISTORY_PLAYER_AGGREGATE_MISMATCH:P" + seat
                                + ":watcher=" + actual + ":summed=" + summed
                );
            }
            JsonObject row = new JsonObject();
            row.addProperty("seat", seat);
            row.addProperty("initial_expected_total", expectedBySeat.getOrDefault(seat, 0));
            row.addProperty("live_player_cast_count", actual);
            playerTotals.add(row);
        }

        JsonObject result = new JsonObject();
        result.addProperty("schema_version", "xmage-ws39-commander-probe/1.0.0");
        result.addProperty("rules_core_authoritative", true);
        result.addProperty("read_only_game_state", true);
        result.addProperty("synthetic_historical_events", false);
        result.add("commander_history", history);
        result.add("player_totals", playerTotals);
        result.add("commander_costs", costs);
        return result;
    }

    private static Player currentPlayer(Game game, Player sessionPlayer) {
        Player current = game.getPlayer(sessionPlayer.getId());
        if (current == null) {
            throw new IllegalStateException("WS39_CURRENT_PLAYER_MISSING:" + sessionPlayer.getId());
        }
        return current;
    }

    private static Card uniqueCommander(
            Game game,
            Player player,
            String cardName,
            String semanticId
    ) {
        List<Card> matches = new ArrayList<>();
        for (UUID commanderId : game.getCommandersIds(player, CommanderCardType.ANY, false)) {
            Card card = game.getCard(commanderId);
            if (card != null && cardName.equals(card.getName())) {
                matches.add(card);
            }
        }
        if (matches.size() != 1) {
            throw new IllegalStateException(
                    "WS39_COMMANDER_NATIVE_MAPPING_NOT_UNIQUE:" + semanticId + ":matches=" + matches.size()
            );
        }
        return matches.get(0);
    }
}
