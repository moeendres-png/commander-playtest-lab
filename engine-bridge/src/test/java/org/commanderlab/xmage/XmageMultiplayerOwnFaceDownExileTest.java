package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-32 coverage: a card its owner exiles face down and may look at is shown
 * to that owner only, with actual cards at 4P and 5P on the full-game lane.
 *
 * <ul>
 *   <li>Foretell (CR 702.143a, Saw It Coming): "During your turn, you may pay
 *   {2} and exile this card from your hand face down."</li>
 *   <li>Hideaway 4 (CR 702.75a, Mosswort Bridge): "look at the top four cards
 *   of your library, exile one face down, then put the rest on the bottom";
 *   its controller may look at the exiled card.</li>
 * </ul>
 * <p>P1 is shown the exiled card; no other principal and not the public view.
 * Correct on pin {@code f79e4168}.</p>
 */
class XmageMultiplayerOwnFaceDownExileTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aForetoldCardIsShownOnlyToItsOwner(int playerCount) {
        XmageMultiplayerScenario s = start("foretell-" + playerCount + "p", playerCount, "Saw It Coming");
        s.submit(labelled(s, "Saw It Coming — Foretell"));
        resolve(s);
        assertOnlyP1Sees(s, "Saw It Coming");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aHiddenAwayCardIsShownOnlyToItsController(int playerCount) {
        XmageMultiplayerScenario s = start("hideaway-" + playerCount + "p", playerCount, "Mosswort Bridge");
        s.submit(labelled(s, "Play Mosswort Bridge"));
        resolve(s);
        assertOnlyP1Sees(s, "Mountain");
    }

    private static XmageMultiplayerScenario start(String tag, int playerCount, String card) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", card, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 2, Zone.BATTLEFIELD));
        return XmageMultiplayerScenario.start(tag, playerCount, "P1", objects);
    }

    /** Answers every decision explicitly until P1 has priority with an empty stack. */
    private static void resolve(XmageMultiplayerScenario s) {
        Game game = s.session.restorationGame();
        for (int i = 0; i < 30; i++) {
            String cls = s.decisionClass();
            switch (cls) {
                case "priority" -> {
                    if (game.getStack().isEmpty() && "P1".equals(s.actor())) {
                        return;
                    }
                    s.submit(s.action("pass_priority", "Pass"));
                }
                case "mana_payment" -> s.payWith("Island");
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "c" + i, "Mountain", 1);
                default -> fail("unexpected " + cls + " for " + s.actor() + " " + s.labels());
            }
        }
        fail("did not settle");
    }

    private static void assertOnlyP1Sees(XmageMultiplayerScenario s, String name) {
        Game game = s.session.restorationGame();
        assertEquals(1, game.getExile().getCardsOwned(game, s.seats.get("P1").getId()).size(),
                "engine: one P1 card exiled face down");
        int p1Seat = XmageFullGameStateRedactor.seat(game, s.seats.get("P1").getId());
        for (String pid : s.seats.keySet()) {
            JsonArray exile = exileOf(XmageFullGameStateRedactor.actorView(game, s.seats.get(pid)), p1Seat);
            if ("P1".equals(pid)) {
                assertEquals(1, exile.size(), "P1 may look at its card: " + exile);
                assertEquals(name, exile.get(0).getAsJsonObject().get("name").getAsString());
                assertTrue(exile.get(0).getAsJsonObject().get("face_down").getAsBoolean());
            } else {
                assertEquals(0, exile.size(), pid + " must not see P1's face-down card: " + exile);
            }
        }
        assertEquals(0, exileOf(XmageFullGameStateRedactor.publicView(game), p1Seat).size(),
                "the public view carries no face-down identity");
        assertFalse(XmageFullGameStateRedactor.publicView(game).toString().contains("\"face_down\":true,"),
                "no face-down exile entry in the public view");
    }

    private static JsonArray exileOf(JsonObject view, int seat) {
        for (JsonElement e : view.getAsJsonArray("players")) {
            JsonObject p = e.getAsJsonObject();
            if (p.get("seat").getAsInt() == seat) {
                return p.getAsJsonArray("exile");
            }
        }
        fail("no seat " + seat);
        return null;
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String part) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            if (e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString().contains(part)) {
                return e.getAsJsonObject();
            }
        }
        fail("no " + part + " in " + s.labels());
        return null;
    }
}
