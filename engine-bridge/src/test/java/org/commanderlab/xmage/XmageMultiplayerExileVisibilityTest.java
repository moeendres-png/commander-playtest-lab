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
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-32: exiled cards are shown to exactly the principals entitled to them,
 * with actual cards at 2P through 5P on the full-game lane.
 *
 * <p>Swords to Plowshares exiles P3's Grizzly Bears face up: a face-up exiled
 * card is public, so every principal and the public view are shown it. Gonti,
 * Lord of Luxury exiles one of P3's top four cards face down, and "you may
 * look at that card for as long as it remains exiled": only P1, the principal
 * the engine lets look at it, is shown it; P3 (its owner), the others and the
 * public view see only the count. Before the fix no exiled identity was ever
 * projected.</p>
 */
class XmageMultiplayerExileVisibilityTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 3, 4, 5})
    void aFaceUpExiledCardIsPublic(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Swords to Plowshares", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 1, Zone.BATTLEFIELD));
        String targetPlayer = "P" + Math.min(3, playerCount);
        objects.add(XmageMultiplayerScenario.obj(targetPlayer, "Grizzly Bears", 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("stp-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        int targetSeat = XmageFullGameStateRedactor.seat(game, s.seats.get(targetPlayer).getId());
        for (String pid : s.seats.keySet()) {
            assertEquals(0, exileOf(XmageFullGameStateRedactor.actorView(game, s.seats.get(pid)), targetSeat).size(),
                    "control: nothing exiled yet");
        }
        resolve(s, "Swords to Plowshares", "Plains", "Grizzly Bears");
        for (String pid : s.seats.keySet()) {
            JsonArray exile = exileOf(XmageFullGameStateRedactor.actorView(game, s.seats.get(pid)), targetSeat);
            assertEquals(1, exile.size(), pid + " is shown P3's exile: " + exile);
            assertEquals("Grizzly Bears", exile.get(0).getAsJsonObject().get("name").getAsString());
        }
        assertEquals(1, exileOf(XmageFullGameStateRedactor.publicView(game), targetSeat).size(),
                "a face-up exiled card is public");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 3, 4, 5})
    void aFaceDownExiledCardIsShownOnlyToWhoMayLookAtIt(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Gonti, Lord of Luxury", 0, Zone.HAND));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("gonti-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String targetPlayer = "P" + Math.min(3, playerCount);
        int targetSeat = XmageFullGameStateRedactor.seat(game, s.seats.get(targetPlayer).getId());
        resolve(s, "Gonti, Lord of Luxury", "Swamp", "Seat " + (targetSeat + 1));
        assertEquals(1, game.getExile().getCardsOwned(game, s.seats.get(targetPlayer).getId()).size(),
                "engine: one target-opponent card is exiled face down");
        for (String pid : s.seats.keySet()) {
            JsonObject view = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid));
            JsonArray exile = exileOf(view, targetSeat);
            if ("P1".equals(pid)) {
                assertEquals(1, exile.size(), "P1 may look at the card: " + exile);
                assertTrue(exile.get(0).getAsJsonObject().get("face_down").getAsBoolean());
            } else {
                assertEquals(0, exile.size(), pid + " must not see the face-down card: " + exile);
            }
            assertEquals(1, countOf(view, targetSeat), pid + " sees the exile count");
        }
        assertEquals(0, exileOf(XmageFullGameStateRedactor.publicView(game), targetSeat).size(),
                "the public view carries no face-down identity");
    }

    /** P1 casts the spell and answers every decision explicitly until the stack is empty again. */
    private static void resolve(XmageMultiplayerScenario s, String spell, String land, String targetLabel) {
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "Cast " + spell));
        boolean cast = false;
        for (int i = 0; i < 60; i++) {
            String cls = s.decisionClass();
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            switch (cls) {
                case "mana_payment" -> s.payWith(land);
                case "target", "choose_object" -> {
                    JsonObject labelled = s.action("choose_targets", targetLabel);
                    if (labelled != null) {
                        s.submit(labelled);
                    } else {
                        XmageActualCardCorpusTest.chooseNamed(
                                new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "c" + i,
                                "Mountain", Math.max(1, decision.get("minimum_selections").getAsInt()));
                    }
                }
                case "choose_use" -> s.submit(s.action("choose_use", "Yes") != null
                        ? s.action("choose_use", "Yes") : firstAction(s));
                case "priority" -> {
                    if (cast && game.getStack().isEmpty()) {
                        return;
                    }
                    cast |= !game.getStack().isEmpty();
                    s.submit(s.action("pass_priority", "Pass"));
                }
                default -> fail("unexpected " + cls + " " + s.labels());
            }
        }
        fail(spell + " did not resolve");
    }

    private static JsonObject firstAction(XmageMultiplayerScenario s) {
        fail("unexpected choose_use " + s.labels());
        return null;
    }

    private static JsonArray exileOf(JsonObject view, int seat) {
        for (JsonElement e : view.getAsJsonArray("players")) {
            JsonObject p = e.getAsJsonObject();
            if (p.get("seat").getAsInt() == seat) {
                return p.has("exile") ? p.getAsJsonArray("exile") : new JsonArray();
            }
        }
        return new JsonArray();
    }

    private static int countOf(JsonObject view, int seat) {
        for (JsonElement e : view.getAsJsonArray("players")) {
            JsonObject p = e.getAsJsonObject();
            if (p.get("seat").getAsInt() == seat) {
                return p.get("exile_count").getAsInt();
            }
        }
        return -1;
    }
}
