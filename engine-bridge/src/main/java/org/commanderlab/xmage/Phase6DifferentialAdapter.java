package org.commanderlab.xmage;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.abilities.SpellAbility;
import mage.cards.Card;
import mage.cards.decks.Deck;
import mage.constants.CommanderCardType;
import mage.constants.MultiplayerAttackOption;
import mage.constants.PhaseStep;
import mage.constants.RangeOfInfluence;
import mage.constants.Zone;
import mage.game.CommanderFreeForAll;
import mage.game.GameOptions;
import mage.game.events.GameEvent;
import mage.game.mulligan.MulliganType;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import mage.watchers.common.CommanderPlaysCountWatcher;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Provider-bound adapter for the frozen Phase-6 Commander differential fixtures.
 *
 * <p>This adapter deliberately uses XMage's own Commander watchers and
 * GameCommanderImpl state-based-action implementation. The fixture setup is a
 * test-only starting-state injection boundary. Provider-observed state and
 * adapter-derived normalization fields are reported separately through explicit
 * per-field provenance; adapter summaries must not be promoted to provider rules claims.</p>
 */
final class Phase6DifferentialAdapter {

    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final String BACKEND_VERSION = "xmage-1.4.61@77d7646da6958fdf8125ee7c8f4aabd130d21d4c";

    private Phase6DifferentialAdapter() {
    }

    static void run(Path inputPath, Path outputPath) throws IOException {
        JsonElement requestElement = GSON.fromJson(
                Files.readString(inputPath, StandardCharsets.UTF_8),
                JsonElement.class
        );
        if (requestElement == null || !requestElement.isJsonObject()) {
            throw new IllegalArgumentException("request must be a JSON object");
        }
        JsonObject request = requestElement.getAsJsonObject();
        String caseId = requireText(request, "case_id");
        JsonElement inputStateElement = request.get("input_state");
        if (inputStateElement == null || !inputStateElement.isJsonObject()) {
            throw new IllegalArgumentException("input_state must be an object");
        }
        JsonObject inputState = inputStateElement.getAsJsonObject();
        requireExactText(inputState, "format", "commander");

        JsonObject normalized = switch (caseId) {
            case "commander_tax_third_cast" -> commanderTax(inputState);
            case "commander_damage_not_combined" -> commanderDamage(inputState);
            case "commander_damage_exactly_twenty_one" -> commanderDamage(inputState);
            default -> throw new IllegalArgumentException("unsupported Phase-6 case: " + caseId);
        };

        JsonObject response = new JsonObject();
        response.addProperty("backend_version", BACKEND_VERSION);
        response.addProperty("provider", "xmage");
        response.addProperty("provider_commit", "77d7646da6958fdf8125ee7c8f4aabd130d21d4c");
        response.addProperty("scenario_mode", "provider_state_injection_v1");
        response.add("normalized_output", normalized);
        response.add("normalized_output_provenance", normalizedOutputProvenance(caseId));
        Files.writeString(outputPath, GSON.toJson(response) + "\n", StandardCharsets.UTF_8);
    }

    private static JsonObject commanderTax(JsonObject inputState) {
        requireExactText(inputState, "action", "cast_commander");
        String commanderName = requireText(inputState, "commander_name");
        int priorCasts = requireNonNegativeInt(inputState, "prior_command_zone_casts");
        int printedManaValue = requireNonNegativeInt(inputState, "printed_mana_value");
        Scenario scenario = Scenario.singleCommander(commanderName);
        try {
            Player actor = scenario.players().get(0);
            Card commander = findCommander(scenario.game(), actor, commanderName);
            CommanderPlaysCountWatcher watcher = scenario.game().getState()
                    .getWatcher(CommanderPlaysCountWatcher.class);
            if (watcher == null) {
                throw new IllegalStateException("XMage CommanderPlaysCountWatcher is unavailable");
            }

            for (int index = 0; index < priorCasts; index++) {
                SpellAbility source = commander.getSpellAbility().copy();
                source.setControllerId(actor.getId());
                GameEvent event = GameEvent.getEvent(
                        GameEvent.EventType.SPELL_CAST,
                        commander.getId(),
                        source,
                        actor.getId()
                );
                event.setZone(Zone.COMMAND);
                watcher.watch(event, scenario.game());
            }

            int observedPriorCasts = watcher.getPlaysCount(commander.getMainCard().getId());
            SpellAbility ability = commander.getSpellAbility().copy();
            ability.setControllerId(actor.getId());
            int baseCost = ability.getManaCostsToPay().manaValue();
            if (baseCost != printedManaValue) {
                throw new IllegalStateException(
                        "fixture printed_mana_value does not match XMage base spell cost for "
                                + commanderName + ": fixture=" + printedManaValue + ", xmage=" + baseCost
                );
            }
            boolean commanderCostApplied = commander.commanderCost(
                    scenario.game(),
                    ability,
                    ability
            );
            int totalCost = ability.getManaCostsToPay().manaValue();

            JsonObject result = new JsonObject();
            result.addProperty("total_cast_cost", totalCost);
            result.addProperty("commander_tax", totalCost - baseCost);
            result.addProperty("legal", commanderCostApplied && observedPriorCasts == priorCasts);
            return result;
        } finally {
            scenario.close();
        }
    }

    private static JsonObject commanderDamage(JsonObject inputState) {
        requireExactText(inputState, "action", "check_state_based_actions");
        int defendingLife = requireNonNegativeInt(inputState, "defending_player_life");
        if (defendingLife != 40) {
            throw new IllegalArgumentException(
                    "provider_state_injection_v1 currently supports defending_player_life=40 only"
            );
        }
        JsonElement requestedDamageElement = inputState.get("commander_damage");
        if (requestedDamageElement == null || !requestedDamageElement.isJsonObject()) {
            throw new IllegalArgumentException("commander_damage must be a non-empty object");
        }
        JsonObject requestedDamage = requestedDamageElement.getAsJsonObject();
        if (requestedDamage.size() == 0) {
            throw new IllegalArgumentException("commander_damage must be a non-empty object");
        }
        List<String> commanderNames = new ArrayList<>();
        Map<String, Integer> validatedDamage = new LinkedHashMap<>();
        for (String name : requestedDamage.keySet()) {
            commanderNames.add(name);
            validatedDamage.put(name, requireNonNegativeInt(requestedDamage, name));
        }
        Scenario scenario = Scenario.partnerCommanders(commanderNames);
        try {
            Player attacker = scenario.players().get(0);
            Player defender = scenario.players().get(1);
            int maximum = 0;

            for (Map.Entry<String, Integer> entry : validatedDamage.entrySet()) {
                String commanderName = entry.getKey();
                int amount = entry.getValue();
                Card commander = findCommander(scenario.game(), attacker, commanderName);
                CommanderInfoWatcher watcher = scenario.game().getState().getWatcher(
                        CommanderInfoWatcher.class,
                        commander.getMainCard().getId()
                );
                if (watcher == null) {
                    throw new IllegalStateException(
                            "XMage CommanderInfoWatcher unavailable for " + commanderName
                    );
                }
                // Explicit test-only starting-state injection into XMage's own
                // CommanderInfoWatcher. The loss rule is then evaluated by
                // GameCommanderImpl.checkStateBasedActions(), not by this adapter.
                watcher.getDamageToPlayer().put(defender.getId(), amount);
                maximum = Math.max(maximum, watcher.getDamageToPlayer().get(defender.getId()));
            }

            scenario.game().runCommanderStateBasedActions();
            boolean loses = defender.hasLost();

            JsonObject result = new JsonObject();
            result.addProperty("player_loses", loses);
            if (loses) {
                result.addProperty("loss_reason", "commander_damage");
            } else {
                result.add("loss_reason", JsonNull.INSTANCE);
            }
            result.addProperty("maximum_single_commander_damage", maximum);
            return result;
        } finally {
            scenario.close();
        }
    }

    private static Card findCommander(
            DifferentialCommanderGame game,
            Player player,
            String expectedName
    ) {
        Set<UUID> commanderIds = game.getCommandersIds(
                player,
                CommanderCardType.COMMANDER_OR_OATHBREAKER,
                false
        );
        return commanderIds.stream()
                .map(game::getCard)
                .filter(card -> card != null && expectedName.equals(card.getName()))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException(
                        "XMage commander not found in scenario: " + expectedName
                ));
    }

    private static String requireText(JsonObject object, String name) {
        if (!object.has(name) || object.get(name).isJsonNull()) {
            throw new IllegalArgumentException(name + " is required");
        }
        String value = object.get(name).getAsString().trim();
        if (value.isEmpty()) {
            throw new IllegalArgumentException(name + " must be nonblank");
        }
        return value;
    }

    private static void requireExactText(JsonObject object, String name, String expected) {
        String observed = requireText(object, name);
        if (!expected.equals(observed)) {
            throw new IllegalArgumentException(
                    name + " must be " + expected + " for provider_state_injection_v1, observed " + observed
            );
        }
    }

    private static int requireNonNegativeInt(JsonObject object, String name) {
        if (!object.has(name) || object.get(name).isJsonNull()) {
            throw new IllegalArgumentException(name + " is required");
        }
        JsonElement element = object.get(name);
        if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isNumber()) {
            throw new IllegalArgumentException(name + " must be an integer");
        }
        final int value;
        try {
            BigDecimal numeric = element.getAsBigDecimal();
            value = numeric.intValueExact();
        } catch (ArithmeticException | NumberFormatException exc) {
            throw new IllegalArgumentException(name + " must be a 32-bit integer", exc);
        }
        if (value < 0) {
            throw new IllegalArgumentException(name + " must be non-negative");
        }
        return value;
    }

    private static JsonObject normalizedOutputProvenance(String caseId) {
        JsonObject provenance = new JsonObject();
        switch (caseId) {
            case "commander_tax_third_cast" -> {
                provenance.addProperty(
                        "total_cast_cost",
                        "xmage_spell_ability_after_CommanderCostModification"
                );
                provenance.addProperty(
                        "commander_tax",
                        "adapter_difference_of_xmage_total_and_base_spell_cost"
                );
                provenance.addProperty(
                        "legal",
                        "adapter_validation_of_xmage_commander_cost_application_and_watcher_count"
                );
            }
            case "commander_damage_not_combined", "commander_damage_exactly_twenty_one" -> {
                provenance.addProperty("player_loses", "xmage_player_hasLost_after_commander_state_based_actions");
                provenance.addProperty(
                        "loss_reason",
                        "adapter_label_from_fixture_scope_when_xmage_player_hasLost_is_true"
                );
                provenance.addProperty(
                        "maximum_single_commander_damage",
                        "adapter_summary_of_injected_xmage_CommanderInfoWatcher_state"
                );
            }
            default -> throw new IllegalArgumentException("unsupported Phase-6 case: " + caseId);
        }
        return provenance;
    }

    private record Scenario(
            XmageDeckImporter importer,
            DifferentialCommanderGame game,
            List<Player> players
    ) {

        static Scenario singleCommander(String commanderName) {
            List<String> mainboard = new ArrayList<>();
            addCopies(mainboard, "Mountain", 33);
            addCopies(mainboard, "Forest", 33);
            addCopies(mainboard, "Swamp", 33);
            return create(mainboard, List.of(commanderName));
        }

        static Scenario partnerCommanders(List<String> commanderNames) {
            if (commanderNames.size() == 1) {
                String only = commanderNames.get(0);
                List<String> mainboard = new ArrayList<>();
                if ("Ishai, Ojutai Dragonspeaker".equals(only)) {
                    addCopies(mainboard, "Plains", 50);
                    addCopies(mainboard, "Island", 49);
                } else if ("Rograkh, Son of Rohgahh".equals(only)) {
                    addCopies(mainboard, "Mountain", 99);
                } else {
                    throw new IllegalArgumentException("unsupported commander-damage fixture commander: " + only);
                }
                return create(mainboard, List.of(only));
            }
            List<String> sorted = commanderNames.stream().sorted().toList();
            List<String> supported = List.of(
                    "Ishai, Ojutai Dragonspeaker",
                    "Rograkh, Son of Rohgahh"
            ).stream().sorted().toList();
            if (!sorted.equals(supported)) {
                throw new IllegalArgumentException("unsupported partner commander set: " + commanderNames);
            }
            List<String> mainboard = new ArrayList<>();
            addCopies(mainboard, "Plains", 33);
            addCopies(mainboard, "Island", 33);
            addCopies(mainboard, "Mountain", 32);
            return create(mainboard, commanderNames);
        }

        private static Scenario create(List<String> mainboard, List<String> commanders) {
            XmageDeckImporter importer = new XmageDeckImporter();
            List<Deck> decks = new ArrayList<>();
            for (int seat = 0; seat < 4; seat++) {
                XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                        "phase6-seat-" + seat,
                        "phase6-provider-scenario-v1-seat-" + seat,
                        mainboard,
                        commanders
                );
                decks.add(importer.requireDeck(imported.deckHandle()));
            }

            DifferentialCommanderGame game = new DifferentialCommanderGame();
            game.setNumPlayers(4);
            GameOptions options = new GameOptions();
            options.rollbackTurnsAllowed = false;
            options.stopOnTurn = 1;
            options.stopAtStep = PhaseStep.UPKEEP;
            game.setGameOptions(options);

            List<Player> players = new ArrayList<>();
            for (int seat = 0; seat < decks.size(); seat++) {
                Deck deck = decks.get(seat);
                XmageBridgePlayer player = new XmageBridgePlayer(
                        "Phase6 Seat " + (seat + 1),
                        RangeOfInfluence.ALL,
                        null
                );
                player.init(game);
                game.loadCards(deck.getCards(), player.getId());
                game.loadCards(deck.getSideboard(), player.getId());
                game.addPlayer(player, deck);
                players.add(player);
            }
            game.start(players.get(0).getId());
            if (!game.isPaused() || game.getPlayers().size() != 4) {
                throw new IllegalStateException("XMage Phase-6 scenario did not reach bounded 4-player handoff");
            }
            return new Scenario(importer, game, List.copyOf(players));
        }

        void close() {
            game.end();
            game.cleanUp();
        }

        private static void addCopies(List<String> cards, String name, int count) {
            for (int i = 0; i < count; i++) {
                cards.add(name);
            }
        }
    }

    private static final class DifferentialCommanderGame extends CommanderFreeForAll {

        DifferentialCommanderGame() {
            super(
                    MultiplayerAttackOption.MULTIPLE,
                    RangeOfInfluence.ALL,
                    MulliganType.GAME_DEFAULT.getMulligan(0),
                    40,
                    7
            );
        }

        boolean runCommanderStateBasedActions() {
            return checkStateBasedActions();
        }
    }
}
