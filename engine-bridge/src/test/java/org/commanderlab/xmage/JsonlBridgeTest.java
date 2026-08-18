package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class JsonlBridgeTest {

    private final JsonlBridge bridge = new JsonlBridge();

    private static String request(
            String requestId,
            String method
    ) {
        return """
                {
                  "protocol_version": "2.0.0",
                  "request_id": "%s",
                  "engine": "xmage",
                  "message_type": "%s",
                  "payload": {},
                  "method": "%s",
                  "params": {}
                }
                """.formatted(
                requestId,
                method,
                method
        );
    }

    @Test
    void startEngineLoadsRealXmageRuntime() {
        JsonlBridge.Result result =
                bridge.handle(request("r1", "start_engine"));

        JsonObject response =
                JsonParser.parseString(result.json())
                        .getAsJsonObject();

        assertTrue(response.get("success").getAsBoolean());
        assertFalse(result.shutdown());
        assertEquals(
                "xmage",
                response.getAsJsonObject("payload")
                        .get("engine")
                        .getAsString()
        );
    }

    @Test
    void providerVersionIdentifiesPinnedXmage() {
        JsonlBridge.Result result =
                bridge.handle(
                        request("r2", "get_provider_version")
                );

        JsonObject payload =
                JsonParser.parseString(result.json())
                        .getAsJsonObject()
                        .getAsJsonObject("payload");

        assertEquals("xmage", payload.get("engine").getAsString());
        assertEquals(
                "1.4.61",
                payload.get("engine_version").getAsString()
        );
        assertEquals(
                "77d7646da6958fdf8125ee7c8f4aabd130d21d4c",
                payload.get("engine_commit").getAsString()
        );
        assertTrue(payload.has("xmage_code_source"));
    }

    @Test
    void b3AdvertisesOnlyProvenConstructionAndStartCapabilities() {
        JsonlBridge.Result result =
                bridge.handle(
                        request("r3", "get_capabilities")
                );

        JsonObject capabilities =
                JsonParser.parseString(result.json())
                        .getAsJsonObject()
                        .getAsJsonObject("payload")
                        .getAsJsonObject("capabilities");

        assertEquals(
                "external_rules_engine",
                capabilities.get("runtime_kind").getAsString()
        );

        assertTrue(
                capabilities.get("commander_supported")
                        .getAsBoolean()
        );

        assertTrue(
                capabilities.get("partner_supported")
                        .getAsBoolean()
        );
        assertTrue(
                capabilities.get("multiplayer_supported")
                        .getAsBoolean()
        );

        assertEquals(
                5,
                capabilities.get("max_players")
                        .getAsInt()
        );

        assertTrue(
                capabilities.get("headless_supported")
                        .getAsBoolean()
        );
        assertTrue(
                capabilities.get("deck_import_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("seed_supported")
                        .getAsBoolean()
        );

        assertFalse(
                capabilities.get("mulligan_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("legal_actions_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("action_submission_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("event_log_supported")
                        .getAsBoolean()
        );

        assertTrue(
                capabilities.get("engine_shutdown_supported")
                        .getAsBoolean()
        );
    }

    @Test
    void importDeckCreatesRealXmageProcessLocalHandle()
            throws Exception {

        JsonlBridge.Result result =
                bridge.handle(
                        rogShaiImportRequest(
                                "r-import"
                        )
                );

        JsonObject response =
                JsonParser.parseString(
                        result.json()
                ).getAsJsonObject();

        assertTrue(
                response.get("success")
                        .getAsBoolean()
        );

        assertFalse(result.shutdown());

        JsonObject handle =
                response
                        .getAsJsonObject("payload")
                        .getAsJsonObject("deck_handle");

        assertEquals(
                "xmage",
                handle.get("backend")
                        .getAsString()
        );

        assertTrue(
                handle.get("handle_id")
                        .getAsString()
                        .startsWith("xmage-deck-")
        );

        assertEquals(
                "rogshai/current",
                handle.get("deck_id")
                        .getAsString()
        );

        assertEquals(
                "1704b6f1574e4d3152f08cf9936c389683f0ae6efa98a8a277a64daa37f583e3",
                handle.get("deck_hash")
                        .getAsString()
        );

        assertEquals(
                100,
                handle.get("accepted_cards")
                        .getAsInt()
        );

        assertEquals(
                2,
                handle.getAsJsonArray(
                                "commander_names"
                        )
                        .size()
        );

        assertEquals(
                0,
                handle.getAsJsonArray(
                                "rejected_cards"
                        )
                        .size()
        );

        assertEquals(
                0,
                handle.getAsJsonArray(
                                "warnings"
                        )
                        .size()
        );
    }

    @Test
    void shutdownIsImplemented() {
        JsonlBridge.Result result =
                bridge.handle(
                        request("r4", "shutdown_engine")
                );

        assertTrue(result.shutdown());
    }
    @Test
    void b3CreatesAndStartsRealFourPlayerCommanderGameThroughJsonl()
            throws Exception {

        List<String> handles =
                List.of(
                        importRogShaiHandle("r-b3-import-1"),
                        importRogShaiHandle("r-b3-import-2"),
                        importRogShaiHandle("r-b3-import-3"),
                        importRogShaiHandle("r-b3-import-4")
                );

        JsonlBridge.Result createResult =
                bridge.handle(
                        createGameRequest(
                                "r-b3-create",
                                "b3-jsonl/four-player",
                                handles,
                                2,
                                40
                        )
                );

        JsonObject createResponse =
                JsonParser.parseString(
                        createResult.json()
                ).getAsJsonObject();

        assertTrue(
                createResponse.get("success")
                        .getAsBoolean()
        );

        assertFalse(createResult.shutdown());

        JsonObject created =
                createResponse
                        .getAsJsonObject("payload");

        assertEquals(
                "b3-jsonl/four-player",
                created.get("game_id")
                        .getAsString()
        );

        assertTrue(
                created.get("game_handle")
                        .getAsString()
                        .startsWith("xmage-game-")
        );

        assertFalse(
                created.get("engine_game_id")
                        .getAsString()
                        .isBlank()
        );

        assertEquals(
                4,
                created.get("player_count")
                        .getAsInt()
        );

        assertEquals(
                2,
                created.get("starting_player_seat")
                        .getAsInt()
        );

        JsonlBridge.Result startResult =
                bridge.handle(
                        startGameRequest(
                                "r-b3-start",
                                "b3-jsonl/four-player"
                        )
                );

        JsonObject startResponse =
                JsonParser.parseString(
                        startResult.json()
                ).getAsJsonObject();

        assertTrue(
                startResponse.get("success")
                        .getAsBoolean()
        );

        assertFalse(startResult.shutdown());

        JsonObject started =
                startResponse
                        .getAsJsonObject("payload");

        assertEquals(
                "b3-jsonl/four-player",
                started.get("game_id")
                        .getAsString()
        );

        assertEquals(
                created.get("game_handle")
                        .getAsString(),
                started.get("game_handle")
                        .getAsString()
        );

        assertEquals(
                created.get("engine_game_id")
                        .getAsString(),
                started.get("engine_game_id")
                        .getAsString()
        );

        assertEquals(
                4,
                started.get("player_count")
                        .getAsInt()
        );

        assertFalse(
                started.get("starting_player_id")
                        .getAsString()
                        .isBlank()
        );

        assertEquals(
                1,
                started.get("turn_number")
                        .getAsInt()
        );

        assertTrue(
                started.get("paused")
                        .getAsBoolean()
        );
    }

    @Test
    void b3UnknownGameIdFailsClosed() {
        JsonlBridge.Result result =
                bridge.handle(
                        startGameRequest(
                                "r-b3-unknown-start",
                                "missing/game"
                        )
                );

        JsonObject response =
                JsonParser.parseString(
                        result.json()
                ).getAsJsonObject();

        assertFalse(
                response.get("success")
                        .getAsBoolean()
        );

        assertEquals(
                "unknown_game_id",
                response
                        .getAsJsonArray("errors")
                        .get(0)
                        .getAsJsonObject()
                        .get("code")
                        .getAsString()
        );
    }
@Test
    void protocolMismatchIsRejected() {
        String request = """
                {
                  "protocol_version": "999.0",
                  "request_id": "bad-version",
                  "engine": "xmage",
                  "message_type": "start_engine",
                  "payload": {}
                }
                """;

        JsonlBridge.Result result = bridge.handle(request);

        JsonObject response =
                JsonParser.parseString(result.json())
                        .getAsJsonObject();

        assertFalse(response.get("success").getAsBoolean());
    }
    private String importRogShaiHandle(
            String requestId
    ) throws Exception {

        JsonlBridge.Result result =
                bridge.handle(
                        rogShaiImportRequest(
                                requestId
                        )
                );

        JsonObject response =
                JsonParser.parseString(
                        result.json()
                ).getAsJsonObject();

        assertTrue(
                response.get("success")
                        .getAsBoolean()
        );

        return response
                .getAsJsonObject("payload")
                .getAsJsonObject("deck_handle")
                .get("handle_id")
                .getAsString();
    }

    private static String createGameRequest(
            String requestId,
            String gameId,
            List<String> deckHandles,
            int startingPlayerSeat,
            int startingLife
    ) {
        JsonArray handles =
                new JsonArray();

        deckHandles.forEach(
                handles::add
        );

        JsonObject gameRequest =
                new JsonObject();

        gameRequest.addProperty(
                "game_id",
                gameId
        );

        gameRequest.add(
                "deck_handles",
                handles
        );

        gameRequest.addProperty(
                "format",
                "commander"
        );

        gameRequest.add(
                "seed",
                com.google.gson.JsonNull.INSTANCE
        );

        gameRequest.addProperty(
                "starting_player_seat",
                startingPlayerSeat
        );

        gameRequest.addProperty(
                "starting_life",
                startingLife
        );

        gameRequest.add(
                "deterministic_starting_state",
                com.google.gson.JsonNull.INSTANCE
        );

        JsonObject payload =
                new JsonObject();

        payload.add(
                "request",
                gameRequest
        );

        JsonObject request =
                new JsonObject();

        request.addProperty(
                "protocol_version",
                "2.0.0"
        );

        request.addProperty(
                "request_id",
                requestId
        );

        request.addProperty(
                "engine",
                "xmage"
        );

        request.addProperty(
                "game_id",
                gameId
        );

        request.addProperty(
                "message_type",
                "create_commander_game"
        );

        request.addProperty(
                "method",
                "create_commander_game"
        );

        request.add(
                "payload",
                payload
        );

        request.add(
                "params",
                new JsonObject()
        );

        return request.toString();
    }

    private static String startGameRequest(
            String requestId,
            String gameId
    ) {
        JsonObject payload =
                new JsonObject();

        JsonObject request =
                new JsonObject();

        request.addProperty(
                "protocol_version",
                "2.0.0"
        );

        request.addProperty(
                "request_id",
                requestId
        );

        request.addProperty(
                "engine",
                "xmage"
        );

        request.addProperty(
                "game_id",
                gameId
        );

        request.addProperty(
                "message_type",
                "start_game"
        );

        request.addProperty(
                "method",
                "start_game"
        );

        request.add(
                "payload",
                payload
        );

        request.add(
                "params",
                new JsonObject()
        );

        return request.toString();
    }

    private static String rogShaiImportRequest(
            String requestId
    ) throws Exception {

        String repoRoot =
                System.getProperty(
                        "commanderlab.repoRoot"
                );

        if (repoRoot == null
                || repoRoot.isBlank()) {
            throw new IllegalStateException(
                    "commanderlab.repoRoot is missing"
            );
        }

        Path path =
                Path.of(
                        repoRoot,
                        "data",
                        "decks",
                        "rogshai_current.json"
                ).normalize();

        JsonObject source =
                JsonParser.parseString(
                        Files.readString(
                                path,
                                StandardCharsets.UTF_8
                        )
                ).getAsJsonObject();

        JsonArray mainboard =
                new JsonArray();

        JsonArray commanders =
                new JsonArray();

        source
                .getAsJsonArray("cards")
                .forEach(element -> {
                    JsonObject card =
                            element.getAsJsonObject();

                    String name =
                            card.get("oracle_name")
                                    .getAsString();

                    int quantity =
                            card.get("quantity")
                                    .getAsInt();

                    String zone =
                            card.get("zone")
                                    .getAsString();

                    JsonArray destination;

                    if ("main".equals(zone)) {
                        destination = mainboard;
                    } else if (
                            "commander".equals(zone)
                    ) {
                        destination = commanders;
                    } else {
                        throw new IllegalStateException(
                                "Unexpected zone: "
                                        + zone
                        );
                    }

                    for (
                            int copy = 0;
                            copy < quantity;
                            copy++
                    ) {
                        destination.add(name);
                    }
                });

        assertEquals(
                98,
                mainboard.size()
        );

        assertEquals(
                2,
                commanders.size()
        );

        JsonObject deck =
                new JsonObject();

        deck.addProperty(
                "deck_id",
                source.get("deck_id")
                        .getAsString()
        );

        deck.addProperty(
                "name",
                source.get("name")
                        .getAsString()
        );

        deck.addProperty(
                "deck_hash",
                source.get("deck_hash")
                        .getAsString()
        );

        deck.add(
                "mainboard",
                mainboard
        );

        deck.add(
                "commander_names",
                commanders
        );

        deck.add(
                "sideboard",
                new JsonArray()
        );

        JsonObject payload =
                new JsonObject();

        payload.add(
                "deck",
                deck
        );

        JsonObject request =
                new JsonObject();

        request.addProperty(
                "protocol_version",
                "2.0.0"
        );

        request.addProperty(
                "request_id",
                requestId
        );

        request.addProperty(
                "engine",
                "xmage"
        );

        request.addProperty(
                "message_type",
                "import_deck"
        );

        request.addProperty(
                "method",
                "import_deck"
        );

        request.add(
                "payload",
                payload
        );

        request.add(
                "params",
                new JsonObject()
        );

        return request.toString();
    }

}
