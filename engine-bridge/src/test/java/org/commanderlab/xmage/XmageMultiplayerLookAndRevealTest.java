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
 * F-26: what a look or a reveal shows reaches exactly the principals entitled
 * to it, with actual cards at 4P and 5P on the full-game lane.
 *
 * <p>XMage keeps looked-at and revealed cards only until the next client
 * update, so before the fix the pilot never learned what Peek showed it.
 * Peek (Oracle: "Look at target player's hand. Draw a card."): only P1, the
 * looking player, is shown P3's hand; no other principal and not the public
 * view. Duress (Oracle: "Target opponent reveals their hand. You choose a
 * noncreature, nonland card from it. That player discards that card."):
 * a revealed hand is public (701.16a), so every principal and the public view
 * are shown it.</p>
 */
class XmageMultiplayerLookAndRevealTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aLookIsShownOnlyToTheLookingPlayer(int playerCount) {
        XmageMultiplayerScenario s = castAtP3("Peek", "Island", "look-" + playerCount + "p", playerCount);
        Game game = s.session.restorationGame();

        JsonObject pilot = pilotState(s);
        assertEquals("P1", s.actor());
        JsonArray looked = pilot.getAsJsonArray("looked_at");
        assertEquals(1, looked.size(), "P1 sees exactly the one look: " + looked);
        assertTrue(hasCard(looked.get(0).getAsJsonObject(), "Craw Wurm",
                        XmageFullGameStateRedactor.seat(game, s.seats.get("P3").getId())),
                "P1 is shown P3's Craw Wurm: " + looked);
        assertTrue(looked.get(0).getAsJsonObject().get("title").getAsString().startsWith("Peek"),
                "the engine window title names the source: " + looked);
        assertEquals(0, pilot.getAsJsonArray("revealed").size());

        for (String pid : s.seats.keySet()) {
            if ("P1".equals(pid)) {
                continue;
            }
            JsonObject other = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid));
            assertEquals(0, other.getAsJsonArray("looked_at").size(), pid + " was not shown P1's look");
            assertFalse(other.toString().contains("Craw Wurm") && !"P3".equals(pid),
                    pid + " must not learn P3's hand");
        }
        JsonObject publicView = XmageFullGameStateRedactor.publicView(game);
        assertFalse(publicView.has("looked_at"));
        assertFalse(publicView.toString().contains("Craw Wurm"), "the public view carries no look");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aRevealIsShownToEveryPlayer(int playerCount) {
        XmageMultiplayerScenario s = castAtP3("Duress", "Swamp", "reveal-" + playerCount + "p", playerCount);
        Game game = s.session.restorationGame();
        int p3Seat = XmageFullGameStateRedactor.seat(game, s.seats.get("P3").getId());

        for (String pid : s.seats.keySet()) {
            JsonObject view = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid));
            JsonArray revealed = view.getAsJsonArray("revealed");
            assertEquals(1, revealed.size(), pid + " sees the one reveal: " + revealed);
            JsonObject entry = revealed.get(0).getAsJsonObject();
            assertEquals(p3Seat, entry.get("revealed_by_seat").getAsInt());
            assertTrue(hasCard(entry, "Craw Wurm", p3Seat), pid + " is shown P3's hand: " + revealed);
            assertEquals(0, view.getAsJsonArray("looked_at").size());
        }
        JsonArray publicRevealed = XmageFullGameStateRedactor.publicView(game).getAsJsonArray("revealed");
        assertEquals(1, publicRevealed.size(), "a reveal is public");
    }

    /**
     * Telepathy ("Your opponents play with their hands revealed.") refreshes a
     * standing reveal every time effects apply. Each opponent's hand is shown
     * as one current entry; repeated refreshes never pile up.
     */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aStandingRevealStaysOneCurrentEntryPerPlayer(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Telepathy", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P3", "Craw Wurm", 0, Zone.HAND));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("telepathy-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        int p3Seat = XmageFullGameStateRedactor.seat(game, s.seats.get("P3").getId());
        s.submit(s.action("activate_ability", "Cast Telepathy"));
        s.payWith("Island");
        for (int pass = 0; pass < 3 * playerCount; pass++) {
            assertEquals("priority", s.decisionClass());
            s.submit(s.action("pass_priority", "Pass"));
        }
        JsonArray revealed = pilotState(s).getAsJsonArray("revealed");
        assertEquals(playerCount - 1, revealed.size(), "one standing entry per opponent: " + revealed);
        boolean p3Shown = false;
        for (JsonElement e : revealed) {
            JsonObject entry = e.getAsJsonObject();
            if (entry.get("revealed_by_seat").getAsInt() == p3Seat) {
                p3Shown = hasCard(entry, "Craw Wurm", p3Seat);
            }
        }
        assertTrue(p3Shown, "P3's current hand is shown: " + revealed);
    }

    /**
     * Vizier of the Menagerie ("You may look at the top card of your library
     * any time.") repeats the same look every time effects apply. P1 is shown
     * its current top card as one entry; no other principal is shown it.
     */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aStandingLookStaysOneEntryWhileTheCardIsUnchanged(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Vizier of the Menagerie", 0, Zone.HAND));
        for (int f = 1; f <= 4; f++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", f, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("vizier-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "Cast Vizier of the Menagerie"));
        while ("mana_payment".equals(s.decisionClass())) {
            s.payWith("Forest");
        }
        for (int pass = 0; pass < 3 * playerCount; pass++) {
            assertEquals("priority", s.decisionClass());
            s.submit(s.action("pass_priority", "Pass"));
        }
        assertEquals("P1", s.actor());
        JsonArray looked = pilotState(s).getAsJsonArray("looked_at");
        assertEquals(1, looked.size(), "one entry for the unchanged top card: " + looked);
        String top = s.seats.get("P1").getLibrary().getFromTop(game).getName();
        assertTrue(hasCard(looked.get(0).getAsJsonObject(), top,
                        XmageFullGameStateRedactor.seat(game, s.seats.get("P1").getId())),
                "P1 is shown its current top card " + top + ": " + looked);
        for (String pid : s.seats.keySet()) {
            if (!"P1".equals(pid)) {
                assertEquals(0, XmageFullGameStateRedactor.actorView(game, s.seats.get(pid))
                        .getAsJsonArray("looked_at").size(), pid + " is not shown P1's top card");
            }
        }
    }

    /**
     * Courser of Kruphix ("Play with the top card of your library revealed.")
     * shows P1's current top card to every principal and to the public view;
     * no other player's top card is shown.
     */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aRevealedTopCardIsPublic(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Courser of Kruphix", 0, Zone.HAND));
        for (int f = 1; f <= 3; f++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", f, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("courser-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        int p1Seat = XmageFullGameStateRedactor.seat(game, s.seats.get("P1").getId());
        for (String pid : s.seats.keySet()) {
            assertTrue(topRevealed(XmageFullGameStateRedactor.actorView(game, s.seats.get(pid)), p1Seat) == null,
                    "control: nothing is revealed before Courser");
        }
        s.submit(s.action("activate_ability", "Cast Courser of Kruphix"));
        while ("mana_payment".equals(s.decisionClass())) {
            s.payWith("Forest");
        }
        for (int pass = 0; pass < playerCount; pass++) {
            s.submit(s.action("pass_priority", "Pass"));
        }
        String top = s.seats.get("P1").getLibrary().getFromTop(game).getName();
        for (String pid : s.seats.keySet()) {
            JsonObject view = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid));
            assertEquals(top, topRevealed(view, p1Seat), pid + " is shown P1's revealed top card");
            for (JsonElement e : view.getAsJsonArray("players")) {
                JsonObject p = e.getAsJsonObject();
                if (p.get("seat").getAsInt() != p1Seat) {
                    assertTrue(p.get("library_top_revealed").isJsonNull(), "only P1's top card is revealed");
                }
            }
        }
        assertEquals(top, topRevealed(XmageFullGameStateRedactor.publicView(game), p1Seat));
    }

    private static String topRevealed(JsonObject view, int seat) {
        for (JsonElement e : view.getAsJsonArray("players")) {
            JsonObject p = e.getAsJsonObject();
            if (p.get("seat").getAsInt() == seat) {
                JsonElement top = p.get("library_top_revealed");
                return top == null || top.isJsonNull() ? null : top.getAsJsonObject().get("name").getAsString();
            }
        }
        return null;
    }

    /** P1 casts the spell at P3, who holds only Craw Wurm; returns at P1's next empty-stack priority. */
    private static XmageMultiplayerScenario castAtP3(String spell, String land, String tag, int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", spell, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", land, 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P3", "Craw Wurm", 0, Zone.HAND));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, playerCount, "P1", objects);
        Game game = s.session.restorationGame();

        for (String pid : s.seats.keySet()) {
            JsonObject before = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid));
            assertEquals(0, before.getAsJsonArray("looked_at").size(), "control: nothing looked at yet");
            assertEquals(0, before.getAsJsonArray("revealed").size(), "control: nothing revealed yet");
        }

        s.submit(s.action("activate_ability", "Cast " + spell));
        boolean cast = false;
        for (int i = 0; i < 40; i++) {
            String cls = s.decisionClass();
            switch (cls) {
                case "mana_payment" -> s.payWith(land);
                case "target" -> s.submit(s.action("choose_targets", "Seat 3"));
                case "priority" -> {
                    if (cast && game.getStack().isEmpty() && "P1".equals(s.actor())) {
                        return s;
                    }
                    cast |= !game.getStack().isEmpty();
                    s.submit(s.action("pass_priority", "Pass"));
                }
                default -> fail("unexpected " + cls + " " + s.labels());
            }
        }
        fail("the spell did not resolve");
        return s;
    }

    private static JsonObject pilotState(XmageMultiplayerScenario s) {
        return s.session.pendingDecisionPayload().getAsJsonObject("decision").getAsJsonObject("pilot_state");
    }

    private static boolean hasCard(JsonObject entry, String name, int ownerSeat) {
        for (JsonElement e : entry.getAsJsonArray("cards")) {
            JsonObject card = e.getAsJsonObject();
            if (name.equals(card.get("name").getAsString()) && card.get("owner_seat").getAsInt() == ownerSeat) {
                return true;
            }
        }
        return false;
    }
}
