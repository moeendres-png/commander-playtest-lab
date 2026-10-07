package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * MULL-2 step 2 (#592): the generic Protocol2 lane projects the native London
 * bottom-card callback (CR 103.5) as its own engine-authored external decision.
 *
 * <p>The bridge never chooses a card. Each test reads the offered engine card
 * ids and names from the decision frame, answers explicitly, and red controls
 * prove a wrong actor, non-offered id, wrong count and stale decision id all
 * fail closed while leaving the decision pending.</p>
 */
class XmageGenericLaneBottomDecisionTest {

    @Test
    void londonBottomFrameAndReadback() {
        Harness harness = driveToBottom();
        XmageGameManager.LegalActionsSnapshot bottom = harness.bottom;

        assertEquals("london_bottom", bottom.decisionKind());
        assertEquals(harness.mulliganActorId, bottom.actorId());
        JsonObject context = bottom.context();
        assertTrue(context.get("bottom_of_library_selection").getAsBoolean());
        assertEquals(1, context.get("count").getAsInt(), "2P grants no free mulligan");

        JsonArray actions = new JsonArray();
        bottom.actions().forEach(actions::add);
        assertEquals(7, actions.size(), "the whole seven-card hand is offered");
        for (JsonElement element : actions) {
            JsonObject action = element.getAsJsonObject();
            assertEquals("bottom_card", action.get("action_type").getAsString());
            assertEquals(harness.mulliganActorId, action.get("actor_id").getAsString());
            JsonObject metadata = action.getAsJsonObject("metadata");
            assertFalse(metadata.get("engine_card_id").getAsString().isBlank());
            assertEquals("Mountain", metadata.get("card_name").getAsString());
        }
        long distinctOffered = actions.asList().stream()
                .map(element -> element.getAsJsonObject()
                        .getAsJsonObject("metadata")
                        .get("engine_card_id")
                        .getAsString())
                .distinct()
                .count();
        assertEquals(7, distinctOffered);

        String chosenId = actions.get(0).getAsJsonObject()
                .getAsJsonObject("metadata")
                .get("engine_card_id").getAsString();
        XmageActionExecutor.ExecutionResult executed = harness.manager.resolveBottom(
                harness.handle,
                bottom.decisionId(),
                harness.mulliganActorId,
                List.of(chosenId)
        );
        assertEquals("london_bottom", executed.actionType());
        assertEquals(bottom.decisionId(), executed.decisionId());

        Game game = harness.manager.requireGame(harness.handle);
        Player owner = game.getPlayer(UUID.fromString(harness.mulliganActorId));
        Card bottomCard = owner.getLibrary().getFromBottom(game);
        assertNotNull(bottomCard, "library must be nonempty");
        assertEquals(chosenId, bottomCard.getId().toString(),
                "the submitted card must be the library bottom");
        assertFalse(owner.getHand().contains(UUID.fromString(chosenId)),
                "the bottomed card must have left its owner's hand");
        assertEquals(93, owner.getLibrary().size(), "99 - 7 redraw + 1 bottomed");
        assertEquals(6, owner.getHand().size());
    }

    @Test
    void redControlsRejectInvalidSelectionsAndKeepDecisionPending() {
        Harness harness = driveToBottom();
        XmageGameManager.LegalActionsSnapshot bottom = harness.bottom;
        String offeredId = bottom.actions().get(0).getAsJsonObject("metadata")
                .get("engine_card_id").getAsString();

        assertRejected(
                harness,
                bottom.decisionId(),
                harness.otherActorId,
                List.of(offeredId),
                "EXTERNAL_DECISION_ACTOR_MISMATCH"
        );
        assertRejected(
                harness,
                bottom.decisionId(),
                harness.mulliganActorId,
                List.of(UUID.randomUUID().toString()),
                "EXTERNAL_DECISION_DOMAIN_INVALID"
        );
        assertRejected(
                harness,
                bottom.decisionId(),
                harness.mulliganActorId,
                List.of(),
                "EXTERNAL_DECISION_DOMAIN_INVALID"
        );
        assertRejected(
                harness,
                "stale-decision-id",
                harness.mulliganActorId,
                List.of(offeredId),
                "STALE_EXTERNAL_DECISION"
        );

        // Every rejection above left the decision pending: the valid answer
        // still resolves it and moves the chosen card.
        harness.manager.resolveBottom(
                harness.handle,
                bottom.decisionId(),
                harness.mulliganActorId,
                List.of(offeredId)
        );
        Game game = harness.manager.requireGame(harness.handle);
        Player owner = game.getPlayer(UUID.fromString(harness.mulliganActorId));
        assertEquals(offeredId, owner.getLibrary().getFromBottom(game).getId().toString());
    }

    @Test
    void jsonlBridgePublishesBottomContextAndResolvesExternally() {
        JsonlBridge bridge = new JsonlBridge();
        assertTrue(success(bridge.handle(request("bottom-r0", "start_engine"))));

        String firstHandle = importDeck(bridge, "bottom-p1", "bottom-hash-p1");
        String secondHandle = importDeck(bridge, "bottom-p2", "bottom-hash-p2");
        String gameId = "mull2-bottom-jsonl";
        assertTrue(success(bridge.handle(createGameRequest(
                "bottom-r1",
                gameId,
                List.of(firstHandle, secondHandle)
        ))));
        assertTrue(success(bridge.handle(startGameRequest("bottom-r2", gameId))));

        boolean mulliganTaken = false;
        JsonObject legal = legalActions(bridge, gameId);
        for (int step = 0; step < 24; step++) {
            JsonObject payload = legal.getAsJsonObject("payload");
            String decisionKind = payload.get("decision_kind").getAsString();
            if ("london_bottom".equals(decisionKind)) {
                break;
            }
            assertEquals("mulligan", decisionKind, legal.toString());
            boolean keep = mulliganTaken;
            JsonObject resolved = resolveMulligan(
                    bridge,
                    gameId,
                    payload.get("decision_id").getAsString(),
                    payload.get("actor_id").getAsString(),
                    keep
            );
            assertTrue(success(resolved), resolved.toString());
            mulliganTaken = true;
            legal = legalActions(bridge, gameId);
        }

        JsonObject payload = legal.getAsJsonObject("payload");
        assertEquals("london_bottom", payload.get("decision_kind").getAsString());
        JsonObject context = payload.getAsJsonObject("context");
        assertTrue(context.get("bottom_of_library_selection").getAsBoolean());
        assertEquals(1, context.get("count").getAsInt());
        String actorId = payload.get("actor_id").getAsString();
        String decisionId = payload.get("decision_id").getAsString();
        JsonArray actions = payload.getAsJsonArray("actions");
        assertEquals(7, actions.size());
        String offeredId = actions.get(0).getAsJsonObject()
                .getAsJsonObject("metadata")
                .get("engine_card_id")
                .getAsString();
        assertEquals("Mountain", actions.get(0).getAsJsonObject()
                .getAsJsonObject("metadata")
                .get("card_name")
                .getAsString());

        JsonObject rejected = resolveBottom(
                bridge,
                gameId,
                decisionId,
                actorId,
                List.of(UUID.randomUUID().toString())
        );
        assertFalse(success(rejected), rejected.toString());
        assertTrue(
                firstErrorMessage(rejected).contains("EXTERNAL_DECISION_DOMAIN_INVALID"),
                rejected.toString()
        );

        JsonObject accepted = resolveBottom(bridge, gameId, decisionId, actorId, List.of(offeredId));
        assertTrue(success(accepted), accepted.toString());
        JsonObject acceptedPayload = accepted.getAsJsonObject("payload");
        assertTrue(acceptedPayload.get("bottom_selection_external").getAsBoolean());
        assertEquals(1, acceptedPayload.get("bottom_card_count").getAsInt());
        assertTrue(acceptedPayload.has("next_decision"));
        assertEquals(
                decisionId,
                acceptedPayload.get("executed_decision_id").getAsString()
        );
    }

    private static void assertRejected(
            Harness harness,
            String decisionId,
            String actorId,
            List<String> cardIds,
            String expectedCode
    ) {
        XmageGameManager.GameException exc = assertThrows(
                XmageGameManager.GameException.class,
                () -> harness.manager.resolveBottom(
                        harness.handle,
                        decisionId,
                        actorId,
                        cardIds
                )
        );
        assertTrue(
                exc.getMessage().contains(expectedCode),
                "expected " + expectedCode + " in " + exc.getMessage()
        );
    }

    private static final class Harness {
        final XmageGameManager manager;
        final String handle;
        final String mulliganActorId;
        final String otherActorId;
        final XmageGameManager.LegalActionsSnapshot bottom;

        Harness(
                XmageGameManager manager,
                String handle,
                String mulliganActorId,
                String otherActorId,
                XmageGameManager.LegalActionsSnapshot bottom
        ) {
            this.manager = manager;
            this.handle = handle;
            this.mulliganActorId = mulliganActorId;
            this.otherActorId = otherActorId;
            this.bottom = bottom;
        }
    }

    private static Harness driveToBottom() {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> firstDeck = new ArrayList<>();
        for (int index = 0; index < 99; index++) {
            firstDeck.add("Mountain");
        }
        List<String> secondDeck = new ArrayList<>();
        for (int index = 0; index < 99; index++) {
            secondDeck.add("Mountain");
        }
        String firstHandle = importer.importCommanderDeck(
                "mull2-bottom-p1",
                "mull2-bottom-hash-1",
                firstDeck,
                List.of("Rograkh, Son of Rohgahh")
        ).deckHandle();
        String secondHandle = importer.importCommanderDeck(
                "mull2-bottom-p2",
                "mull2-bottom-hash-2",
                secondDeck,
                List.of("Rograkh, Son of Rohgahh")
        ).deckHandle();

        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "mull2-bottom-manager",
                List.of(firstHandle, secondHandle),
                0,
                40,
                true
        );
        manager.startGame(created.gameHandle());

        boolean mulliganTaken = false;
        String mulliganActorId = null;
        XmageGameManager.LegalActionsSnapshot bottom = null;
        for (int step = 0; step < 24 && bottom == null; step++) {
            XmageGameManager.LegalActionsSnapshot decision =
                    manager.legalActions(created.gameHandle());
            if ("mulligan".equals(decision.decisionKind())) {
                boolean take = !mulliganTaken;
                manager.resolveMulligan(
                        created.gameHandle(),
                        decision.decisionId(),
                        decision.actorId(),
                        !take,
                        List.of()
                );
                if (take) {
                    mulliganTaken = true;
                    mulliganActorId = decision.actorId();
                }
                continue;
            }
            if ("london_bottom".equals(decision.decisionKind())) {
                bottom = decision;
                break;
            }
            throw new AssertionError(
                    "unexpected generic-lane decision kind " + decision.decisionKind()
            );
        }
        assertTrue(mulliganTaken, "the driver must take exactly one mulligan");
        assertNotNull(mulliganActorId, "the mulliganing actor must be known");
        assertNotNull(bottom, "expected a london_bottom decision");

        Game game = manager.requireGame(created.gameHandle());
        String otherActorId = null;
        for (UUID playerId : game.getPlayers().keySet()) {
            if (!playerId.toString().equals(mulliganActorId)) {
                otherActorId = playerId.toString();
            }
        }
        assertNotNull(otherActorId, "expected a second seat");
        return new Harness(
                manager,
                created.gameHandle(),
                mulliganActorId,
                otherActorId,
                bottom
        );
    }

    private static String importDeck(
            JsonlBridge bridge,
            String deckId,
            String deckHash
    ) {
        JsonArray mainboard = new JsonArray();
        for (int index = 0; index < 99; index++) {
            mainboard.add("Mountain");
        }
        JsonArray commanders = new JsonArray();
        commanders.add("Rograkh, Son of Rohgahh");
        JsonObject deck = new JsonObject();
        deck.addProperty("deck_id", deckId);
        deck.addProperty("deck_hash", deckHash);
        deck.add("mainboard", mainboard);
        deck.add("commander_names", commanders);
        JsonObject payload = new JsonObject();
        payload.add("deck", deck);
        JsonObject response = JsonParser.parseString(
                bridge.handle(requestWithPayload("import-" + deckId, "import_deck", payload)).json()
        ).getAsJsonObject();
        assertTrue(success(response), response.toString());
        return response.getAsJsonObject("payload")
                .getAsJsonObject("deck_handle")
                .get("handle_id")
                .getAsString();
    }

    private static String createGameRequest(
            String requestId,
            String gameId,
            List<String> deckHandles
    ) {
        JsonArray handles = new JsonArray();
        deckHandles.forEach(handles::add);
        JsonObject gameRequest = new JsonObject();
        gameRequest.addProperty("game_id", gameId);
        gameRequest.add("deck_handles", handles);
        gameRequest.addProperty("format", "commander");
        gameRequest.addProperty("starting_player_seat", 0);
        gameRequest.addProperty("starting_life", 40);
        gameRequest.addProperty("external_control", true);
        JsonObject payload = new JsonObject();
        payload.add("request", gameRequest);
        return requestWithPayload(requestId, "create_commander_game", payload);
    }

    private static String startGameRequest(String requestId, String gameId) {
        return requestWithPayload(requestId, "start_game", gameId, new JsonObject());
    }

    private static String request(String requestId, String messageType) {
        return requestWithPayload(requestId, messageType, new JsonObject());
    }

    private static String requestWithPayload(
            String requestId,
            String messageType,
            JsonObject payload
    ) {
        return requestWithPayload(requestId, messageType, null, payload);
    }

    private static String requestWithPayload(
            String requestId,
            String messageType,
            String gameId,
            JsonObject payload
    ) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", "2.0.0");
        request.addProperty("request_id", requestId);
        request.addProperty("engine", "xmage");
        if (gameId != null) {
            request.addProperty("game_id", gameId);
        }
        request.addProperty("message_type", messageType);
        request.addProperty("method", messageType);
        request.add("payload", payload);
        request.add("params", new JsonObject());
        return request.toString();
    }

    private static JsonObject legalActions(JsonlBridge bridge, String gameId) {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", gameId);
        return JsonParser.parseString(
                bridge.handle(requestWithPayload("legal-" + UUID.randomUUID(), "get_legal_actions", payload)).json()
        ).getAsJsonObject();
    }

    private static JsonObject resolveMulligan(
            JsonlBridge bridge,
            String gameId,
            String decisionId,
            String actorId,
            boolean keep
    ) {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", gameId);
        payload.addProperty("decision_id", decisionId);
        payload.addProperty("player_id", actorId);
        payload.addProperty("keep", keep);
        payload.add("bottom_card_ids", new JsonArray());
        return JsonParser.parseString(
                bridge.handle(requestWithPayload("mull-" + UUID.randomUUID(), "resolve_mulligan", payload)).json()
        ).getAsJsonObject();
    }

    private static JsonObject resolveBottom(
            JsonlBridge bridge,
            String gameId,
            String decisionId,
            String actorId,
            List<String> cardIds
    ) {
        JsonArray ids = new JsonArray();
        cardIds.forEach(ids::add);
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", gameId);
        payload.addProperty("decision_id", decisionId);
        payload.addProperty("player_id", actorId);
        payload.add("card_ids", ids);
        return JsonParser.parseString(
                bridge.handle(requestWithPayload("bottom-" + UUID.randomUUID(), "resolve_bottom", payload)).json()
        ).getAsJsonObject();
    }

    private static boolean success(JsonObject response) {
        return response.get("success").getAsBoolean();
    }

    private static boolean success(String json) {
        return JsonParser.parseString(json).getAsJsonObject()
                .get("success").getAsBoolean();
    }

    private static boolean success(JsonlBridge.Result result) {
        return success(result.json());
    }

    private static String firstErrorMessage(JsonObject response) {
        return response.getAsJsonArray("errors").get(0)
                .getAsJsonObject()
                .get("message")
                .getAsString();
    }
}
