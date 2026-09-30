package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Damage divided among several players at 4P and 5P on the full-game lane.
 *
 * <p>Arc Lightning (Oracle): "Arc Lightning deals 3 damage divided as you
 * choose among one, two, or three targets." The division is announced while
 * casting (601.2d) and each share must reach exactly its own player; no other
 * player is affected.</p>
 */
class XmageMultiplayerDividedDamageTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void oneEachToThreeDifferentPlayers(int playerCount) {
        Map<String, Integer> split = new LinkedHashMap<>();
        split.put("P2", 1);
        split.put("P3", 1);
        split.put("P4", 1);
        assertLife(arc(playerCount, split, "arc-111"), playerCount, split);
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void anUnevenSplitReachesEachChosenPlayer(int playerCount) {
        Map<String, Integer> split = new LinkedHashMap<>();
        split.put("P4", 2);
        split.put("P2", 1);
        assertLife(arc(playerCount, split, "arc-21"), playerCount, split);
    }

    private static void assertLife(XmageMultiplayerScenario s, int playerCount, Map<String, Integer> split) {
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            assertEquals(40 - split.getOrDefault(pid, 0), s.seats.get(pid).getLife(),
                    pid + " takes exactly its share " + split);
        }
    }

    private static XmageMultiplayerScenario arc(int playerCount, Map<String, Integer> split, String tag) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Arc Lightning", 0, Zone.HAND));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag + "-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        XmageActualCardCorpusTest.Started started = new XmageActualCardCorpusTest.Started(s.session, s.seats, null);
        List<Map.Entry<String, Integer>> shares = new ArrayList<>(split.entrySet());
        int next = 0;
        boolean cast = false;
        s.submit(s.action("activate_ability", "Cast Arc Lightning"));
        for (int i = 0; i < 80; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            if ("priority".equals(cls) && game.getStack().isEmpty() && cast) {
                break;
            }
            switch (cls) {
                case "target_amount" -> {
                    cast = true;
                    if (next < shares.size()) {
                        Map.Entry<String, Integer> share = shares.get(next++);
                        submitTargetAmount(s, tag + "-share-" + next,
                                s.seats.get(share.getKey()).getId().toString(), share.getValue());
                    } else {
                        XmageActualCardCorpusTest.chooseNone(started, tag + "-done");
                    }
                }
                case "mana_payment" -> s.payWith("Mountain");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                default -> fail("unexpected " + cls + " for " + s.actor() + " " + s.labels() + " " + s.prompt());
            }
        }
        assertEquals(shares.size(), next, "every share was announced");
        return s;
    }

    /** One target by engine id plus its share, as one response. */
    private static void submitTargetAmount(XmageMultiplayerScenario s, String tag, String objectId, int amount) {
        JsonObject pending = s.session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = s.session.legalActionsPayload();
        String optionId = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            if (engine != null && engine.has("object_id") && objectId.equals(engine.get("object_id").getAsString())) {
                assertTrue(optionId == null, "unique target option expected");
                optionId = meta.get("option_id").getAsString();
            }
        }
        assertNotNull(optionId, "target must be engine-offered: " + objectId + " " + s.labels());
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + optionId);
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        choices.add("selected_option_ids", selected);
        choices.addProperty("numeric_choice", amount);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = s.session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }
}
