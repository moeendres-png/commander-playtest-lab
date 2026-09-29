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
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-33: a face-down spell on the stack keeps its identity from every
 * principal but its controller, with actual cards at 4P and 5P.
 *
 * <p>P1 casts Exalted Angel face down using morph. While it is on the stack
 * (CR 708.4: a face-down spell has no characteristics an opponent may see;
 * CR 708.5: its controller may look at it) every opponent is asked for
 * priority; none of their decisions names the card, and P2's Counterspell
 * targets it without learning its name. P1 is shown its name; the public view
 * is not.</p>
 */
class XmageMultiplayerFaceDownSpellTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aFaceDownSpellIsNamedOnlyToItsController(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Exalted Angel", 0, Zone.HAND));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P2", "Counterspell", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P2", "Island", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Island", 2, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("morph-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "using Morph"));

        int opponentDecisionsWhileOnStack = 0;
        boolean countered = false;
        for (int i = 0; i < 40; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            boolean onStack = !game.getStack().isEmpty();
            if (onStack && !"P1".equals(actor)) {
                opponentDecisionsWhileOnStack++;
                assertFalse(decision.toString().contains("Exalted Angel"),
                        actor + " must not learn the face-down spell (" + cls + ")");
            }
            if (onStack && "P1".equals(actor) && "priority".equals(cls)) {
                JsonObject own = faceDownItem(decision.getAsJsonObject("pilot_state"));
                assertEquals("Exalted Angel", own.get("name").getAsString(), "P1 may look at its own spell");
                assertTrue(faceDownItem(XmageFullGameStateRedactor.publicView(game)).get("name").isJsonNull(),
                        "the public view carries no face-down name");
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("P2".equals(actor) ? "Island" : "Mountain");
                case "target" -> {
                    assertEquals("P2", actor);
                    JsonObject spell = null;
                    for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
                        JsonObject a = e.getAsJsonObject();
                        if (!a.getAsJsonObject("metadata").get("label").getAsString().startsWith("Full Game Seat")) {
                            spell = a;
                        }
                    }
                    if (spell == null) {
                        fail("the face-down spell is not a Counterspell target: " + s.labels());
                    }
                    s.submit(spell);
                }
                case "priority" -> {
                    if (onStack && "P2".equals(actor) && !countered) {
                        s.submit(s.action("activate_ability", "Cast Counterspell"));
                        countered = true;
                    } else if (!onStack && countered) {
                        assertTrue(opponentDecisionsWhileOnStack >= playerCount - 1, "every opponent was asked");
                        assertTrue(s.seats.get("P1").getGraveyard().getCards(game).stream()
                                        .anyMatch(c -> "Exalted Angel".equals(c.getName())),
                                "Counterspell countered the face-down spell");
                        return;
                    } else {
                        s.submit(s.action("pass_priority", "Pass"));
                    }
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("the stack did not resolve");
    }

    /**
     * The resolved face-down permanent (CR 708.5): P1 is shown which card it
     * is; no other principal and not the public view.
     */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aFaceDownPermanentIsIdentifiedOnlyToItsController(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Exalted Angel", 0, Zone.HAND));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("morph-bf-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "using Morph"));
        for (int i = 0; i < 20 && !faceDownOnBattlefield(game); i++) {
            if ("mana_payment".equals(s.decisionClass())) {
                s.payWith("Mountain");
            } else {
                s.submit(s.action("pass_priority", "Pass"));
            }
        }
        assertTrue(faceDownOnBattlefield(game), "the morph resolved face down");
        int p1Seat = XmageFullGameStateRedactor.seat(game, s.seats.get("P1").getId());
        for (String pid : s.seats.keySet()) {
            JsonObject view = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid));
            JsonObject permanent = faceDownPermanent(view, p1Seat);
            if ("P1".equals(pid)) {
                assertEquals("Exalted Angel", permanent.get("private_identity").getAsString(),
                        "P1 may look at its face-down permanent");
            } else {
                assertFalse(permanent.has("private_identity"), pid + " must not learn the face-down card");
                assertFalse(view.toString().contains("Exalted Angel"), pid + " must not learn it anywhere");
            }
        }
        assertFalse(XmageFullGameStateRedactor.publicView(game).toString().contains("Exalted Angel"),
                "the public view carries no face-down identity");
    }

    private static boolean faceDownOnBattlefield(Game game) {
        return game.getBattlefield().getAllActivePermanents().stream().anyMatch(p -> p.isFaceDown(game));
    }

    private static JsonObject faceDownPermanent(JsonObject view, int seat) {
        for (JsonElement e : view.getAsJsonArray("players")) {
            JsonObject p = e.getAsJsonObject();
            if (p.get("seat").getAsInt() != seat) {
                continue;
            }
            for (JsonElement b : p.getAsJsonArray("battlefield")) {
                if (b.getAsJsonObject().get("face_down").getAsBoolean()) {
                    return b.getAsJsonObject();
                }
            }
        }
        fail("no face-down permanent for seat " + seat);
        return null;
    }

    private static JsonObject faceDownItem(JsonObject view) {
        for (JsonElement e : view.getAsJsonArray("stack")) {
            if (e.getAsJsonObject().has("face_down")) {
                return e.getAsJsonObject();
            }
        }
        fail("no face-down stack item: " + view.getAsJsonArray("stack"));
        return null;
    }
}
