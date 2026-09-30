package org.commanderlab.xmage;

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
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-42: a player who leaves while its own "may" choice of another player's
 * spell is pending makes no choice, with actual cards at 4P and 5P.
 *
 * <p>P1 casts Tempt with Discovery (Oracle: "Tempting offer — Search your
 * library for a land card and put it onto the battlefield. Each opponent may
 * search their library for a land card and put it onto the battlefield. For
 * each opponent who does, search your library for a land card and put it onto
 * the battlefield. ..."). The first opponent asked concedes while its "may" is
 * open; every remaining opponent accepts. CR 800.4a: a player who left makes
 * no choices, so P1 searches once for itself and once for each <em>remaining</em>
 * opponent. Before the fix the departed player's stale frame was still
 * answered and counted, and P1 searched once more.</p>
 *
 * <p>The same holds for a pending object choice (the {@code choose_object}
 * class): Innocent Blood ("Each player sacrifices a creature.") and Council's
 * Judgment ("Will of the council — Starting with you, each player votes for a
 * nonland permanent you don't control. Exile each permanent with the most
 * votes or tied for most votes."). The first opponent asked concedes at its
 * choice; it neither sacrifices nor votes, and no frame is exposed to it.</p>
 */
class XmageMultiplayerLeaverMayChoiceTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aDepartedOpponentsTemptingOfferIsNotCounted(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Tempt with Discovery", 0, Zone.HAND));
        for (int i = 0; i < 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", i + 1, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("may-leave-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "Cast Tempt with Discovery"));
        String leaver = null;
        int p1SearchesAfterLeave = 0;
        List<String> accepted = new ArrayList<>();
        for (int i = 0; i < 80; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            String actor = s.actor();
            if (leaver != null) {
                assertFalse(leaver.equals(actor), "no " + cls + " frame is exposed to " + leaver + " after it left");
                if ("priority".equals(cls) && game.getStack().isEmpty()) {
                    break;
                }
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Forest");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_use" -> {
                    if (leaver == null) {
                        leaver = actor;
                        concede(s, actor);
                        assertFalse(s.seats.get(actor).isInGame(), actor + " left the game");
                    } else {
                        accepted.add(actor);
                        s.submit(labelled(s, "Yes"));
                    }
                }
                case "choose_object", "target" -> {
                    if (leaver != null && "P1".equals(actor)) {
                        p1SearchesAfterLeave++;
                    }
                    XmageActualCardCorpusTest.chooseNamed(
                            new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "o" + i, "Mountain", 1);
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        assertNotNull(leaver, "control: an opponent was asked the tempting offer");
        assertEquals(playerCount - 2, accepted.size(), "every remaining opponent was asked once and accepted");
        assertEquals(accepted.size(), p1SearchesAfterLeave,
                "P1 searches once per remaining opponent who accepted; the departed player's offer is not counted");
        boolean cancelled = false;
        for (JsonElement event : s.session.resultPayload().getAsJsonArray("transcript")) {
            JsonObject e = event.getAsJsonObject();
            if ("engine_decision_cancelled".equals(e.get("event_type") == null ? null : e.get("event_type").getAsString())) {
                cancelled |= e.getAsJsonObject("payload").get("reason").getAsString().equals("player_left_game");
            }
        }
        assertTrue(cancelled, "the retirement of the departed player's frame is recorded");
    }

    private static void concede(XmageMultiplayerScenario s, String pid) {
        String id = s.seats.get(pid).getId().toString();
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", pid + "-concede");
        concede.addProperty("actor_id", id);
        concede.addProperty("player_id", id);
        assertTrue(s.session.submitConcede(concede).get("failure").isJsonNull());
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String label) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            if (label.equals(e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString())) {
                return e.getAsJsonObject();
            }
        }
        fail("no " + label + " in " + s.labels());
        return null;
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aDepartedPlayerNeitherSacrificesNorIsAsked(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Innocent Blood", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", 1, Zone.BATTLEFIELD));
        for (int seat = 1; seat <= playerCount; seat++) {
            objects.add(XmageMultiplayerScenario.obj("P" + seat, "Grizzly Bears", 20, Zone.BATTLEFIELD));
            objects.add(XmageMultiplayerScenario.obj("P" + seat, "Hill Giant", 21, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("blood-leave-" + playerCount + "p",
                playerCount, "P1", objects);
        String leaver = resolveWithFirstOpponentLeaving(s, "Innocent Blood", "Swamp", actor -> "Grizzly Bears");
        Game game = s.session.restorationGame();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            if (pid.equals(leaver)) {
                continue;
            }
            List<String> creatures = new ArrayList<>();
            game.getBattlefield().getAllActivePermanents().stream()
                    .filter(p -> p.isCreature(game) && p.getControllerId().equals(s.seats.get(pid).getId()))
                    .forEach(p -> creatures.add(p.getName()));
            assertEquals(List.of("Hill Giant"), creatures, pid + " sacrificed exactly the creature it chose");
        }
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aDepartedPlayerDoesNotVote(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Council's Judgment", 0, Zone.HAND));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Plains", i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P2", "Hill Giant", 21, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P3", "Grizzly Bears", 20, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("judgment-leave-" + playerCount + "p",
                playerCount, "P1", objects);
        // Everyone votes for P2's Hill Giant except P3, who votes for its own Grizzly Bears.
        resolveWithFirstOpponentLeaving(s, "Council's Judgment", "Plains",
                actor -> "P3".equals(actor) ? "Grizzly Bears" : "Hill Giant");
        Game game = s.session.restorationGame();
        List<String> remaining = new ArrayList<>();
        game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> p.isCreature(game)).forEach(p -> remaining.add(p.getName()));
        assertEquals(List.of("Grizzly Bears"), remaining,
                "only the Hill Giant had the most votes; the departed player cast none");
    }

    /**
     * P1 casts the spell; the first opponent asked an object choice concedes at it. Afterwards
     * no frame of any class is exposed to it, and its retirement is recorded. Returns the leaver.
     */
    private static String resolveWithFirstOpponentLeaving(XmageMultiplayerScenario s, String spell, String land,
            java.util.function.Function<String, String> choiceFor) {
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "Cast " + spell));
        String leaver = null;
        for (int i = 0; i < 80; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            String actor = s.actor();
            if (leaver != null) {
                assertFalse(leaver.equals(actor), "no " + cls + " frame is exposed to " + leaver + " after it left");
                if ("priority".equals(cls) && game.getStack().isEmpty()) {
                    break;
                }
            }
            switch (cls) {
                case "mana_payment" -> s.payWith(land);
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_object" -> {
                    if (leaver == null && !"P1".equals(actor)) {
                        leaver = actor;
                        concede(s, actor);
                    } else {
                        s.submit(labelled(s, choiceFor.apply(actor)));
                    }
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        assertNotNull(leaver, "control: an opponent was asked to choose");
        boolean cancelled = false;
        for (JsonElement event : s.session.resultPayload().getAsJsonArray("transcript")) {
            JsonObject e = event.getAsJsonObject();
            if (e.has("event_type") && "engine_decision_cancelled".equals(e.get("event_type").getAsString())) {
                cancelled |= "player_left_game".equals(e.getAsJsonObject("payload").get("reason").getAsString());
            }
        }
        assertTrue(cancelled, "the retirement of the departed player's frame is recorded");
        return leaver;
    }

    /**
     * Systemic rule: a departed player's pending frame of a class that has no
     * qualified native unwind is never left answerable; the lane fails closed.
     * P1 casts Fact or Fiction and concedes while choosing a pile.
     */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aDepartedPlayersUnqualifiedPendingDecisionFailsClosed(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Fact or Fiction", 0, Zone.HAND));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("fof-leave-" + playerCount + "p",
                playerCount, "P1", objects);
        s.submit(s.action("activate_ability", "Cast Fact or Fiction"));
        for (int i = 0; i < 40; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "control: the lane runs until P1's pile choice");
            String cls = s.decisionClass();
            String actor = s.actor();
            if ("pile".equals(cls)) {
                assertEquals("P1", actor, "control: the caster chooses a pile");
                String p1 = s.seats.get("P1").getId().toString();
                JsonObject concede = new JsonObject();
                concede.addProperty("proposal_id", "p1-concede-pile");
                concede.addProperty("actor_id", p1);
                concede.addProperty("player_id", p1);
                JsonObject result = s.session.submitConcede(concede);
                assertFalse(s.seats.get("P1").isInGame(), "P1 left the game");
                assertTrue(result.get("decision").isJsonNull(), "no pile frame stays answerable for P1: " + result);
                assertTrue(result.getAsJsonObject("failure").get("message").getAsString()
                        .startsWith("PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: pile"), result.get("failure").toString());
                return;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Island");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "target" -> s.submit(s.action("choose_targets", "Seat " + Math.min(3, playerCount)));
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "c" + i, "Mountain",
                        Math.max(1, s.session.pendingDecisionPayload().getAsJsonObject("decision")
                                .get("minimum_selections").getAsInt()));
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("P1 never reached its pile choice");
    }
}
