package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * An ability "any player may activate" on another player's permanent, at 4P
 * and 5P on the full-game lane (CR 602.2, legal-action completeness).
 *
 * <p>Lethal Vapors (Oracle): "Whenever a creature enters, destroy it. {0}:
 * Destroy Lethal Vapors. You skip your next turn. Any player may activate this
 * ability." P2 controls it. The active P1 must be offered the activation in its
 * own priority frame; activating it destroys Lethal Vapors, and "you" is the
 * activating player, so P1 skips its next turn (CR 500.11): after P1's turn the
 * seats run P2 … PN and then P2 again.</p>
 */
class XmageMultiplayerAnyPlayerActivatesTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void anyPlayerMayActivateAndTheActivatorSkipsItsNextTurn(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P2", "Lethal Vapors", 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("vapors-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        assertEquals("P1", s.actor(), "control: P1 has priority");
        JsonObject activate = s.action("activate_ability", "Lethal Vapors");
        assertNotNull(activate, "P1 is offered the ability any player may activate: " + s.labels());
        s.submit(activate);

        List<String> turns = new ArrayList<>();
        int lastTurn = game.getTurnNum();
        turns.add(s.pidOf(game.getActivePlayerId().toString()));
        for (int i = 0; i < 3000 && turns.size() < playerCount + 1; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            if (game.getTurnNum() != lastTurn) {
                lastTurn = game.getTurnNum();
                turns.add(s.pidOf(game.getActivePlayerId().toString()));
                continue;
            }
            String cls = s.decisionClass();
            switch (cls) {
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_object", "target" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "d" + i, "Mountain",
                        payload.getAsJsonObject("decision").get("minimum_selections").getAsInt());
                default -> fail("unexpected " + cls + " for " + s.actor() + " " + s.labels() + " " + s.prompt());
            }
        }
        assertEquals(0, XmageActualCardCorpusTest.onBattlefield(
                new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "P2", "Lethal Vapors"),
                "Lethal Vapors was destroyed");
        List<String> expected = new ArrayList<>();
        expected.add("P1");
        for (int seat = 2; seat <= playerCount; seat++) {
            expected.add("P" + seat);
        }
        expected.add("P2");
        assertEquals(expected, turns, "500.11: P1, who activated it, skips its next turn");
    }

    /**
     * Volrath's Dungeon (Oracle): "Pay 5 life: Destroy Volrath's Dungeon. Any
     * player may activate this ability but only during their turn." P2 controls
     * it. P1 is offered the ability during its own turn, but not during P2's
     * turn, while P2 is offered it there (no over-offering, 602.5).
     */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void anyPlayerOnlyDuringTheirTurnIsOfferedOnlyToTheActivePlayer(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P2", "Volrath's Dungeon", 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("dungeon-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        assertEquals("P1", s.actor(), "control: P1 has priority in its own turn");
        assertNotNull(s.action("activate_ability", "Pay 5 life"),
                "P1 is offered the ability during its own turn: " + s.labels());
        boolean p1CheckedInP2Turn = false;
        boolean p2CheckedInP2Turn = false;
        for (int i = 0; i < 3000 && !(p1CheckedInP2Turn && p2CheckedInP2Turn); i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            String actor = s.actor();
            String active = s.pidOf(game.getActivePlayerId().toString());
            if ("priority".equals(cls) && "P2".equals(active)) {
                JsonObject offer = s.action("activate_ability", "Pay 5 life");
                if ("P1".equals(actor)) {
                    assertTrue(offer == null, "P1 must not be offered it during P2's turn: " + s.labels());
                    p1CheckedInP2Turn = true;
                } else if ("P2".equals(actor)) {
                    assertNotNull(offer, "P2 is offered it during its own turn: " + s.labels());
                    p2CheckedInP2Turn = true;
                }
            }
            switch (cls) {
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_object", "target" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "d" + i, "Mountain",
                        payload.getAsJsonObject("decision").get("minimum_selections").getAsInt());
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels() + " " + s.prompt());
            }
        }
        assertTrue(p1CheckedInP2Turn && p2CheckedInP2Turn, "control: both were checked during P2's turn");
    }
}
