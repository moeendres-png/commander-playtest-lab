package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-31: a library-zone choice shows the chooser exactly the cards the engine
 * put in front of it, with actual cards at 4P and 5P on the full-game lane.
 *
 * <p>Fact or Fiction: "Reveal the top five cards of your library. An opponent
 * separates those cards into two piles." P3 separates and is shown exactly the
 * five revealed cards, never the rest of P1's library or its order. Impulse:
 * "Look at the top four cards of your library. Put one of them into your
 * hand..." P1 is shown exactly those four. Before the fix both were shown the
 * owner's entire library in order.</p>
 */
class XmageMultiplayerLibraryGrantTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void theSeparatingOpponentSeesOnlyTheRevealedCards(int playerCount) {
        Map<String, Integer> grants = run("Fact or Fiction", 4, playerCount, 5);
        assertEquals(Map.of("P3", 5), grants, "only P3 was granted, exactly the five revealed cards");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aTopFourLookSeesOnlyThoseFour(int playerCount) {
        Map<String, Integer> grants = run("Impulse", 2, playerCount, 4);
        assertEquals(Map.of("P1", 4), grants, "only P1 was granted, exactly the top four");
    }

    /** Casts the spell and returns, per chooser, how many of P1's library cards it was granted. */
    private static Map<String, Integer> run(String spell, int islands, int playerCount, int expectedShown) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", spell, 0, Zone.HAND));
        for (int i = 1; i <= islands; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                spell.replace(' ', '-') + "-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        int p1Seat = XmageFullGameStateRedactor.seat(game, s.seats.get("P1").getId());
        List<String> top = new ArrayList<>();
        for (Card card : s.seats.get("P1").getLibrary().getTopCards(game, expectedShown)) {
            top.add(card.getId().toString());
        }
        assertTrue(s.seats.get("P1").getLibrary().size() > expectedShown, "control: more library than shown");

        Map<String, Integer> grants = new TreeMap<>();
        s.submit(s.action("activate_ability", "Cast " + spell));
        boolean cast = false;
        for (int i = 0; i < 40; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            for (JsonElement e : decision.getAsJsonObject("pilot_state").getAsJsonArray("players")) {
                JsonObject p = e.getAsJsonObject();
                int granted = p.getAsJsonArray("granted_library").size();
                if (granted == 0) {
                    continue;
                }
                assertEquals(p1Seat, p.get("seat").getAsInt(), "only P1's library is ever granted");
                assertTrue("choose_object".equals(cls) || "target".equals(cls),
                        "a grant exists only inside the library decision, not " + cls);
                for (JsonElement card : p.getAsJsonArray("granted_library")) {
                    assertTrue(top.contains(card.getAsJsonObject().get("object_id").getAsString()),
                            "granted a card that was not put in front of " + actor);
                }
                grants.merge(actor, granted, Math::max);
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Island");
                case "target" -> {
                    if (s.action("choose_targets", "Seat 3") != null) {
                        s.submit(s.action("choose_targets", "Seat 3"));
                    } else {
                        XmageActualCardCorpusTest.chooseNamed(
                                new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "t" + i,
                                "Mountain", Math.max(1, decision.get("minimum_selections").getAsInt()));
                    }
                }
                case "pile" -> s.submit(firstLabelled(s, "Pile 1"));
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "c" + i, "Mountain",
                        Math.max(1, decision.get("minimum_selections").getAsInt()));
                case "priority" -> {
                    if (cast && game.getStack().isEmpty()) {
                        return grants;
                    }
                    cast |= !game.getStack().isEmpty();
                    s.submit(s.action("pass_priority", "Pass"));
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("the spell did not resolve");
        return grants;
    }

    private static JsonObject firstLabelled(XmageMultiplayerScenario s, String label) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject a = e.getAsJsonObject();
            if (a.getAsJsonObject("metadata").get("label").getAsString().contains(label)) {
                return a;
            }
        }
        fail("no action labelled " + label + " " + s.labels());
        return null;
    }
}
