package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Two public facts the pilot and the comparison tools used to guess or lack.
 *
 * <p>A stack object names its controller (who cast a spell is public at a
 * Commander table), as battlefield permanents already do: the controller sees
 * its own real id, every other principal an opaque seat token, and the public
 * view only seat tokens. A game result names the turn on which each player was
 * first seen as lost, or null.</p>
 */
class XmageStackControllerAndLossTurnTest {

    @Test
    void aStackObjectNamesItsControllerActorSafely() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Divination", 0, Zone.HAND));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("stack-controller", 3, "P1", objects);
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "Cast Divination"));
        for (int i = 0; i < 10 && game.getStack().isEmpty(); i++) {
            if ("mana_payment".equals(s.decisionClass())) {
                s.payWith("Island");
            } else {
                fail("unexpected " + s.decisionClass() + " " + s.labels());
            }
        }
        assertFalse(game.getStack().isEmpty(), "Divination is on the stack");

        String p1Real = s.seats.get("P1").getId().toString();
        String p1Token = "op-" + XmageFullGameStateRedactor.seat(game, s.seats.get("P1").getId());
        for (String pid : s.seats.keySet()) {
            JsonObject item = stackItem(XmageFullGameStateRedactor.actorView(game, s.seats.get(pid)));
            assertEquals("Divination", item.get("name").getAsString());
            assertEquals("P1".equals(pid) ? p1Real : p1Token,
                    item.get("controller_id").getAsString(),
                    pid + " sees the controller in its own actor-scoped form");
        }
        JsonObject publicItem = stackItem(XmageFullGameStateRedactor.publicView(game));
        assertEquals(p1Token, publicItem.get("controller_id").getAsString(),
                "the public view names the controller by seat token only");
        assertFalse(XmageFullGameStateRedactor.publicView(game).toString().contains(p1Real),
                "no raw principal id in the public view");
    }

    @Test
    void aResultNamesTheTurnEachPlayerLost() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("loss-turn", 3, "P1", List.of());
        String p2 = s.seats.get("P2").getId().toString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "loss-turn-concede");
        proposal.addProperty("actor_id", p2);
        proposal.addProperty("player_id", p2);
        JsonObject result = s.session.submitConcede(proposal);

        int lostEntries = 0;
        for (JsonElement outcome : result.getAsJsonArray("outcomes")) {
            JsonObject item = outcome.getAsJsonObject();
            assertTrue(item.has("lost_on_turn"), "every outcome carries lost_on_turn");
            if (item.get("lost").getAsBoolean()) {
                lostEntries++;
                assertTrue(item.get("lost_on_turn").getAsInt() >= 1, "a lost player has the turn it lost on");
            } else {
                assertTrue(item.get("lost_on_turn").isJsonNull(), "a player that has not lost has null");
            }
        }
        assertEquals(1, lostEntries, "exactly the conceding player lost");
    }

    private static JsonObject stackItem(JsonObject view) {
        assertEquals(1, view.getAsJsonArray("stack").size(), "one object on the stack");
        return view.getAsJsonArray("stack").get(0).getAsJsonObject();
    }
}
