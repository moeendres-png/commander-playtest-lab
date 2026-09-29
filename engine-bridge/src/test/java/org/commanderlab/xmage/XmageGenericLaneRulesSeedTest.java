package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Generic B4-D lane Rules-RNG binding (AF09 / PB-08 XMage half).
 *
 * <p>Evidence that the explicit create-game seed controls XMage's own Rules
 * randomness on the generic lane, not merely that the bridge echoes it:
 * the opening shuffle of every library and every opening hand is a function
 * of the seed, the engine actually consumed its per-game Rules stream, an
 * unseeded game is never reported as controlled, malformed seeds fail closed,
 * and the seed value never reaches a principal-scoped observation.
 */
class XmageGenericLaneRulesSeedTest {

    private static final long SEED = 7_319_457_102_938_475L;

    @Test
    void sameSeedReproducesEveryOpeningLibraryAndHandForTwoToFivePlayers() throws Exception {
        for (int players = 2; players <= 5; players++) {
            Opening first = openSeeded(players, SEED);
            Opening second = openSeeded(players, SEED);
            assertEquals(first.zones(), second.zones(),
                    players + "P: identical seed must reproduce every library and hand");
            assertEquals(first.startingSeat(), second.startingSeat(),
                    players + "P: identical seed must reproduce the starting seat");
            assertTrue(first.rulesRandomCalls() > 0,
                    players + "P: start must consume the per-game Rules stream");
            assertEquals(first.rulesRandomCalls(), second.rulesRandomCalls(),
                    players + "P: identical seed must consume the Rules stream identically");
        }
    }

    @Test
    void differentSeedChangesTheOpeningShuffle() throws Exception {
        Opening base = openSeeded(4, SEED);
        Opening other = openSeeded(4, SEED + 1);
        assertNotEquals(base.zones(), other.zones(),
                "a different seed must change the engine's opening shuffle; equality "
                        + "would mean the seed does not reach the Rules RNG");
    }

    @Test
    void genericBridgePlayerNeverOverridesTheEngineShuffle() {
        for (java.lang.reflect.Method method : XmageBridgePlayer.class.getDeclaredMethods()) {
            assertNotEquals("shuffleLibrary", method.getName(),
                    "library shuffling belongs to PlayerImpl (Rules RNG, SHUFFLE_LIBRARY "
                            + "replacement, LIBRARY_SHUFFLED event), never a bridge override");
        }
    }

    @Test
    void unseededGameIsNeverReportedAsControlled() throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "seed-test/unseeded", importCopies(importer, 3), 0, 40);
        assertNull(created.rulesSeedBinding());
        assertNull(created.rulesSeed());
        assertFalse(manager.seedControlled(created.gameHandle()));
        assertFalse(manager.requireGame(created.gameHandle()).isRulesSeedExplicit());

        XmageGameManager.StartResult started = manager.startGame(created.gameHandle());
        assertNull(started.rulesSeedBinding());
        assertFalse(manager.seedControlled(created.gameHandle()));
    }

    @Test
    void bridgeAcknowledgesTheSeedFromEngineReadback() throws Exception {
        JsonlBridge bridge = new JsonlBridge();
        assertTrue(capabilities(bridge).get("seed_supported").getAsBoolean());

        JsonObject request = createRequest("seed-test/bridge", importHandles(bridge, 4));
        request.addProperty("seed", SEED);
        request.addProperty("rules_seed", SEED);
        JsonObject options = new JsonObject();
        options.addProperty("seed", SEED);
        options.addProperty("rules_seed", SEED);
        request.add("options", options);

        JsonObject created = call(bridge, "create_commander_game", "seed-test/bridge",
                wrap(request));
        assertTrue(created.get("success").getAsBoolean(), created.toString());
        JsonObject createdPayload = created.getAsJsonObject("payload");
        assertTrue(createdPayload.get("seed_controlled").getAsBoolean());
        assertEquals(SEED, createdPayload.get("rules_seed").getAsLong());
        JsonObject binding = createdPayload.getAsJsonObject("rules_seed_binding");
        assertTrue(binding.get("rules_seed_matches").getAsBoolean());
        assertTrue(binding.get("rules_seed_explicit").getAsBoolean());
        assertEquals(0L, binding.get("rules_random_calls").getAsLong(),
                "no Rules randomness may be consumed before start");

        JsonObject started = call(bridge, "start_game", "seed-test/bridge", new JsonObject());
        assertTrue(started.get("success").getAsBoolean(), started.toString());
        JsonObject startedBinding = started.getAsJsonObject("payload")
                .getAsJsonObject("rules_seed_binding");
        assertTrue(startedBinding.get("rules_random_calls").getAsLong() > 0);
        assertEquals(SEED, startedBinding.get("rules_seed").getAsLong());
    }

    @Test
    void principalScopedStateNeverCarriesTheSeedValue() throws Exception {
        JsonlBridge bridge = new JsonlBridge();
        String gameId = "seed-test/redaction";
        JsonObject request = createRequest(gameId, importHandles(bridge, 4));
        request.addProperty("seed", SEED);
        assertTrue(call(bridge, "create_commander_game", gameId, wrap(request))
                .get("success").getAsBoolean());
        assertTrue(call(bridge, "start_game", gameId, new JsonObject())
                .get("success").getAsBoolean());

        for (String observer : List.of("p1", "p2", "p3", "p4")) {
            JsonObject payload = new JsonObject();
            payload.addProperty("observer_player_id", observer);
            JsonObject state = call(bridge, "get_game_state", gameId, payload);
            assertTrue(state.get("success").getAsBoolean(), state.toString());
            JsonObject statePayload = state.getAsJsonObject("payload");
            assertTrue(statePayload.get("seed_controlled").getAsBoolean());
            assertTrue(statePayload.getAsJsonObject("state").get("seed").isJsonNull());
            assertFalse(state.toString().contains(Long.toString(SEED)),
                    observer + " observation must not disclose the Rules seed");
        }
    }

    @Test
    void malformedOrConflictingSeedsFailClosed() throws Exception {
        List<JsonObject> invalid = new ArrayList<>();
        invalid.add(seedRequest("seed", JsonParser.parseString("1.5")));
        invalid.add(seedRequest("seed", JsonParser.parseString("1e3")));
        invalid.add(seedRequest("seed", JsonParser.parseString("\"42\"")));
        invalid.add(seedRequest("seed", JsonParser.parseString("true")));
        invalid.add(seedRequest("seed", JsonParser.parseString("92233720368547758070")));
        JsonObject conflicting = seedRequest("seed", JsonParser.parseString("1"));
        conflicting.addProperty("rules_seed", 2);
        invalid.add(conflicting);
        JsonObject conflictingOption = seedRequest("rules_seed", JsonParser.parseString("5"));
        JsonObject options = new JsonObject();
        options.addProperty("seed", 6);
        conflictingOption.add("options", options);
        invalid.add(conflictingOption);

        for (JsonObject request : invalid) {
            JsonlBridge bridge = new JsonlBridge();
            List<String> handles = importHandles(bridge, 2);
            JsonArray handleArray = new JsonArray();
            handles.forEach(handleArray::add);
            request.add("deck_handles", handleArray);
            JsonObject response = call(bridge, "create_commander_game",
                    request.get("game_id").getAsString(), wrap(request));
            assertFalse(response.get("success").getAsBoolean(), request.toString());
            assertEquals("invalid_seed", response.getAsJsonArray("errors").get(0)
                    .getAsJsonObject().get("code").getAsString(), request.toString());
        }
    }

    // ------------------------------------------------------------------ //

    private record Opening(List<List<String>> zones, int startingSeat, long rulesRandomCalls) {
    }

    private static Opening openSeeded(int players, long seed) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "seed-test/" + players + "p-" + UUID.randomUUID(),
                importCopies(importer, players), 0, 40, false, seed);
        assertEquals(seed, created.rulesSeed());
        assertTrue(manager.seedControlled(created.gameHandle()));

        XmageGameManager.StartResult started = manager.startGame(created.gameHandle());
        Game game = manager.requireGame(created.gameHandle());
        List<List<String>> zones = new ArrayList<>();
        List<UUID> order = new ArrayList<>(game.getState().getPlayerList());
        int startingSeat = -1;
        int seat = 0;
        for (Player player : game.getPlayers().values()) {
            if (player.getId().equals(game.getStartingPlayerId())) {
                startingSeat = seat;
            }
            seat++;
            List<String> library = new ArrayList<>();
            for (Card card : player.getLibrary().getCards(game)) {
                library.add(card.getName());
            }
            List<String> hand = new ArrayList<>();
            for (Card card : player.getHand().getCards(game)) {
                hand.add(card.getName());
            }
            hand.sort(String::compareTo);
            zones.add(library);
            zones.add(hand);
        }
        assertEquals(players, order.size());
        assertTrue(startingSeat >= 0);
        return new Opening(zones, startingSeat,
                started.rulesSeedBinding().get("rules_random_calls").getAsLong());
    }

    private static JsonObject seedRequest(String key, JsonElement value) {
        JsonObject request = createRequest("seed-test/invalid-" + UUID.randomUUID(), List.of());
        request.add(key, value);
        return request;
    }

    private static JsonObject createRequest(String gameId, List<String> handles) {
        JsonObject request = new JsonObject();
        request.addProperty("game_id", gameId);
        request.addProperty("format", "commander");
        JsonArray handleArray = new JsonArray();
        handles.forEach(handleArray::add);
        request.add("deck_handles", handleArray);
        request.addProperty("starting_player_seat", 0);
        request.addProperty("starting_life", 40);
        return request;
    }

    private static JsonObject wrap(JsonObject gameRequest) {
        JsonObject payload = new JsonObject();
        payload.add("request", gameRequest);
        return payload;
    }

    private static JsonObject capabilities(JsonlBridge bridge) {
        return call(bridge, "get_capabilities", null, new JsonObject())
                .getAsJsonObject("payload").getAsJsonObject("capabilities");
    }

    private static JsonObject call(
            JsonlBridge bridge, String method, String gameId, JsonObject payload) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", "2.0.0");
        request.addProperty("request_id", "seed-" + UUID.randomUUID());
        request.addProperty("engine", "xmage");
        if (gameId != null) {
            request.addProperty("game_id", gameId);
        }
        request.addProperty("message_type", method);
        request.addProperty("method", method);
        request.add("payload", payload);
        request.add("params", new JsonObject());
        return JsonParser.parseString(bridge.handle(request.toString()).json())
                .getAsJsonObject();
    }

    private static List<String> importHandles(JsonlBridge bridge, int count) throws Exception {
        JsonObject source = rogShai();
        List<String> handles = new ArrayList<>();
        for (int copy = 0; copy < count; copy++) {
            JsonObject deck = new JsonObject();
            deck.addProperty("deck_id", source.get("deck_id").getAsString());
            deck.addProperty("name", source.get("name").getAsString());
            deck.addProperty("deck_hash", source.get("deck_hash").getAsString());
            deck.add("mainboard", names(source, "main"));
            deck.add("commander_names", names(source, "commander"));
            deck.add("sideboard", new JsonArray());
            JsonObject payload = new JsonObject();
            payload.add("deck", deck);
            JsonObject response = call(bridge, "import_deck", null, payload);
            assertTrue(response.get("success").getAsBoolean(), response.toString());
            handles.add(response.getAsJsonObject("payload").getAsJsonObject("deck_handle")
                    .get("handle_id").getAsString());
        }
        return handles;
    }

    private static List<String> importCopies(XmageDeckImporter importer, int count)
            throws Exception {
        JsonObject source = rogShai();
        List<String> mainboard = new ArrayList<>();
        names(source, "main").forEach(name -> mainboard.add(name.getAsString()));
        List<String> commanders = new ArrayList<>();
        names(source, "commander").forEach(name -> commanders.add(name.getAsString()));
        List<String> handles = new ArrayList<>();
        for (int copy = 0; copy < count; copy++) {
            handles.add(importer.importCommanderDeck(
                    source.get("deck_id").getAsString(),
                    source.get("deck_hash").getAsString(),
                    mainboard,
                    commanders
            ).deckHandle());
        }
        return handles;
    }

    private static JsonArray names(JsonObject source, String zone) {
        JsonArray names = new JsonArray();
        for (JsonElement element : source.getAsJsonArray("cards")) {
            JsonObject card = element.getAsJsonObject();
            if (!zone.equals(card.get("zone").getAsString())) {
                continue;
            }
            for (int copy = 0; copy < card.get("quantity").getAsInt(); copy++) {
                names.add(card.get("oracle_name").getAsString());
            }
        }
        return names;
    }

    private static JsonObject rogShai() throws Exception {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        Path path = Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize();
        return JsonParser.parseString(Files.readString(path, StandardCharsets.UTF_8))
                .getAsJsonObject();
    }
}
