package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * A player concedes at its own mulligan decision, at 4P and 5P, in a game
 * started from decks on the full-game lane (CR 103.5, 800.4a).
 *
 * <p>A player who left makes no choices; every other player still makes its
 * own keep/mulligan decision, and the game reaches its first turn with the
 * remaining players. The departed player is never asked again.</p>
 */
class XmageMultiplayerLeaverMulliganTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void theGameStartsWithoutAPlayerWhoConcededAtItsMulligan(int playerCount) {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            List<String> mainboard = new ArrayList<>();
            for (int i = 0; i < 99; i++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck("mull-leave-P" + seat, "mull-leave-hash", mainboard,
                    List.of("Rograkh, Son of Rohgahh")).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                "mull-leave-" + playerCount + "p", handles, 0, 40, 424242L, importer);
        session.start();

        String leaver = null;
        List<String> mulliganActors = new ArrayList<>();
        for (int step = 0; step < 60; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            JsonObject pending = payload.getAsJsonObject("decision");
            String cls = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("priority".equals(cls)) {
                break;
            }
            if ("choose_object".equals(cls) && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                submit(session, "start-" + step, actorId, singleAction(legal, a -> a.get("action_id")
                        .getAsString().endsWith(":" + actorId)));
                continue;
            }
            assertEquals("mulligan", cls, "unexpected " + cls);
            assertFalse(actorId.equals(leaver), "the departed player is asked its mulligan again");
            mulliganActors.add(actorId);
            if (leaver == null && mulliganActors.size() == 2) {
                // The second player asked concedes at its own keep/mulligan decision.
                leaver = actorId;
                JsonObject concede = new JsonObject();
                concede.addProperty("proposal_id", "mull-concede");
                concede.addProperty("actor_id", actorId);
                concede.addProperty("player_id", actorId);
                JsonObject result = session.submitConcede(concede);
                assertTrue(result.get("failure").isJsonNull(), "the game goes on: " + result.get("failure"));
                continue;
            }
            submit(session, "keep-" + step, actorId, singleAction(legal, a -> {
                JsonObject meta = a.getAsJsonObject("metadata");
                return "mulligan".equals(a.get("action_type").getAsString()) && meta.has("option_type")
                        && "keep".equals(meta.get("option_type").getAsString());
            }));
        }
        assertTrue(leaver != null, "control: a player conceded at its mulligan");
        JsonObject payload = session.pendingDecisionPayload();
        assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
        assertEquals("priority", payload.getAsJsonObject("decision").get("decision_class").getAsString(),
                "the game reached its first turn");
        long inGame = session.restorationGame().getPlayers().values().stream()
                .filter(mage.players.Player::isInGame).count();
        assertEquals(playerCount - 1, inGame, "everyone but the leaver is still playing");
        assertEquals(playerCount, mulliganActors.size(), "every player was asked exactly once: " + mulliganActors);
    }

    private static JsonObject singleAction(JsonObject legal, java.util.function.Predicate<JsonObject> test) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            if (test.test(element.getAsJsonObject())) {
                matches.add(element.getAsJsonObject());
            }
        }
        assertEquals(1, matches.size(), "expected exactly one matching action: " + legal);
        return matches.get(0);
    }

    private static void submit(XmageFullGameSession session, String tag, String actorId, JsonObject action) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", action.get("action_id").getAsString());
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        if (after.has("failure") && !after.get("failure").isJsonNull()) {
            fail("submission failed: " + after.get("failure"));
        }
    }
}
