package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Owner decision 2026-10-15: batch runs may opt in to several games per JVM.
 *
 * <p>Without the property a process plays exactly one game. With it, the next game
 * may start only after the previous one was shut down, and never more games than
 * the property allows.</p>
 */
class XmageFullGameGamesPerJvmTest {

    @AfterEach
    void clearProperty() {
        System.clearProperty(XmageFullGameJsonlBridge.GAMES_PER_JVM_PROPERTY);
    }

    @Test
    void defaultAllowsOneGameEvenAfterShutdown() {
        XmageFullGameJsonlBridge bridge = engine();
        playAndShutDown(bridge, "default-1");
        assertRefused(create(bridge, "default-2"));
    }

    @Test
    void optInAllowsTheNextGameOnlyAfterShutdownAndUpToTheLimit() {
        System.setProperty(XmageFullGameJsonlBridge.GAMES_PER_JVM_PROPERTY, "2");
        XmageFullGameJsonlBridge bridge = engine();
        assertTrue(create(bridge, "batch-1").get("success").getAsBoolean());
        ok(bridge, "start_full_game");
        assertRefused(create(bridge, "batch-early"));
        ok(bridge, "shutdown_game");
        playAndShutDown(bridge, "batch-2");
        assertRefused(create(bridge, "batch-3"));
    }

    private static void playAndShutDown(XmageFullGameJsonlBridge bridge, String gameId) {
        JsonObject created = create(bridge, gameId);
        assertTrue(created.get("success").getAsBoolean(), created.toString());
        ok(bridge, "start_full_game");
        ok(bridge, "shutdown_game");
    }

    private static void assertRefused(JsonObject response) {
        assertFalse(response.get("success").getAsBoolean(), response.toString());
        assertEquals("full_game_process_already_used",
                response.getAsJsonArray("errors").get(0).getAsJsonObject().get("code").getAsString());
    }

    private static XmageFullGameJsonlBridge engine() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        ok(bridge, "start_engine");
        return bridge;
    }

    private static JsonObject create(XmageFullGameJsonlBridge bridge, String gameId) {
        JsonArray handles = new JsonArray();
        for (int seat = 0; seat < 2; seat++) {
            JsonObject deckPayload = new JsonObject();
            deckPayload.add("deck", deck(gameId + "-" + seat));
            JsonObject imported = response(bridge.handle(request("import_deck", deckPayload)).json());
            handles.add(imported.getAsJsonObject("payload").getAsJsonObject("deck_handle")
                    .get("handle_id").getAsString());
        }
        JsonObject create = new JsonObject();
        create.addProperty("game_id", gameId);
        create.add("deck_handles", handles);
        create.addProperty("seed", 6620L);
        create.addProperty("starting_player_seat", 0);
        create.addProperty("starting_life", 40);
        return response(bridge.handle(request("create_full_game", create)).json());
    }

    private static JsonObject deck(String deckId) {
        JsonObject deck = new JsonObject();
        deck.addProperty("deck_id", deckId);
        deck.addProperty("deck_hash", "0".repeat(64));
        JsonArray commanders = new JsonArray();
        commanders.add("Isamaru, Hound of Konda");
        deck.add("commander_names", commanders);
        JsonArray mainboard = new JsonArray();
        for (int index = 0; index < 99; index++) {
            mainboard.add("Plains");
        }
        deck.add("mainboard", mainboard);
        deck.add("sideboard", new JsonArray());
        return deck;
    }

    private static void ok(XmageFullGameJsonlBridge bridge, String type) {
        JsonObject response = response(bridge.handle(request(type, new JsonObject())).json());
        assertTrue(response.get("success").getAsBoolean(), type + " failed: " + response);
    }

    private static String request(String messageType, JsonObject payload) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "games-per-jvm-" + messageType);
        request.addProperty("message_type", messageType);
        request.add("payload", payload);
        return request.toString();
    }

    private static JsonObject response(String json) {
        return JsonParser.parseString(json).getAsJsonObject();
    }
}
