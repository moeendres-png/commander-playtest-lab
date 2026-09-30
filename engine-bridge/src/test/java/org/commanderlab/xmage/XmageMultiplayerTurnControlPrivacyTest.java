package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.effects.common.continuous.BecomesFaceDownCreatureEffect;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.GameCommanderImpl;
import mage.players.Player;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-27 privacy companion: actual Mindslaver control at 2P through 5P must
 * inherit exactly the controlled player's private in-game visibility under CR 723.4.
 */
class XmageMultiplayerTurnControlPrivacyTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 3, 4, 5})
    void controllerGetsControlledPrivateVisibilityWithoutLeakingOtherPrincipals(int playerCount)
            throws Exception {
        String controlledPid = "P2";
        String unrelated = playerCount > 2 ? "P" + playerCount : null;
        String afterControlled = playerCount == 2 ? "P1" : "P3";
        String pnBearSemantic = "obj:battlefield-" + controlledPid + "-2-GrizzlyBears";
        String otherBearSemantic = unrelated == null
                ? null
                : "obj:battlefield-" + unrelated + "-9-GrizzlyBears";

        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Mindslaver", 0, Zone.BATTLEFIELD));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj(controlledPid, "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(controlledPid, "Mountain", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj(controlledPid, "Grizzly Bears", 2, Zone.BATTLEFIELD));
        if (unrelated != null) {
            objects.add(XmageMultiplayerScenario.obj(
                    unrelated, "Grizzly Bears", 9, Zone.BATTLEFIELD));
        }

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "turn-control-privacy-" + playerCount + "p",
                playerCount,
                "P1",
                objects
        );
        GameCommanderImpl game = s.session.restorationGame();
        XmageNativeStateRestoration restoration = restoration(s.session);
        Player controller = s.seats.get("P1");
        Player controlled = s.seats.get(controlledPid);
        Player unrelatedPlayer = unrelated == null ? null : s.seats.get(unrelated);

        XmageHiddenStateRestoration.apply(
                game,
                s.seats,
                restoration,
                new XmageHiddenStateRestoration.Request(
                        List.of(),
                        List.of(new XmageHiddenStateRestoration.FaceDownState(
                                pnBearSemantic,
                                BecomesFaceDownCreatureEffect.FaceDownType.MANIFESTED
                        ))
                )
        );
        if (otherBearSemantic != null) {
            XmageHiddenStateRestoration.apply(
                    game,
                    s.seats,
                    restoration,
                    new XmageHiddenStateRestoration.Request(
                            List.of(),
                            List.of(new XmageHiddenStateRestoration.FaceDownState(
                                    otherBearSemantic,
                                    BecomesFaceDownCreatureEffect.FaceDownType.MANIFESTED
                            ))
                    )
            );
        }

        String pnBearId = restoration.injectedObjectId(pnBearSemantic).toString();
        String otherBearId = otherBearSemantic == null
                ? null
                : restoration.injectedObjectId(otherBearSemantic).toString();
        int pnSeat = XmageFullGameStateRedactor.seat(game, controlled.getId());
        int unrelatedSeat = unrelatedPlayer == null
                ? -1
                : XmageFullGameStateRedactor.seat(game, unrelatedPlayer.getId());
        int pnLife = controlled.getLife();

        // Before Mindslaver takes effect P1 has no derived entitlement.
        assertFalse(battlefieldItem(
                XmageFullGameStateRedactor.actorView(game, controller), pnBearId)
                .has("private_identity"));
        assertEquals(
                "Grizzly Bears",
                battlefieldItem(
                        XmageFullGameStateRedactor.actorView(game, controlled), pnBearId)
                        .get("private_identity").getAsString()
        );

        boolean activated = false;
        boolean boltCast = false;
        boolean privacyChecked = false;
        for (int i = 0; i < 220; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            String active = XmageNativeStateRestorationTest.pidOf(
                    s.seats, game.getActivePlayerId().toString());
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            boolean actingFor = decision.has("acting_for_seat");

            if (afterControlled.equals(active) && privacyChecked) {
                assertTrue(privacyChecked, "controlled-turn privacy assertions ran");
                assertEquals(pnLife - 3, controlled.getLife(), "controlled Bolt resolved");

                JsonObject afterControl =
                        XmageFullGameStateRedactor.actorView(game, controller);
                assertFalse(
                        battlefieldItem(afterControl, pnBearId).has("private_identity"),
                        "current face-down entitlement ends with the controlled turn"
                );
                assertFalse(
                        playerRow(afterControl, pnSeat).has("hand"),
                        "current hand entitlement ends with the controlled turn"
                );
                assertTrue(
                        hasObservedTitle(afterControl, "F-27 controlled look"),
                        "information already seen during control remains observed"
                );
                return;
            }

            if (controlledPid.equals(active) && actingFor && !privacyChecked) {
                assertEquals("P1", actor);
                assertEquals(pnSeat, decision.get("acting_for_seat").getAsInt());

                JsonObject pilot = decision.getAsJsonObject("pilot_state");
                assertEquals(
                        "Grizzly Bears",
                        battlefieldItem(pilot, pnBearId).get("private_identity").getAsString(),
                        "controller sees the controlled player's face-down identity"
                );
                if (otherBearId != null) {
                    assertFalse(
                            battlefieldItem(pilot, otherBearId).has("private_identity"),
                            "controller must not inherit an unrelated player's face-down identity"
                    );
                }
                assertTrue(playerRow(pilot, pnSeat).has("hand"));
                if (unrelatedPlayer != null) {
                    assertFalse(
                            playerRow(pilot, unrelatedSeat).has("hand"),
                            "unrelated hand remains principal-scoped"
                    );
                }

                XmageFullGameStateRedactor.beginZoneFullLook(controlled, controlled, game,
                        controlled.getLibrary().getCardList());
                try {
                    JsonObject inheritedLook =
                            XmageFullGameStateRedactor.actorView(game, controller);
                    JsonArray controlledLibrary =
                            playerRow(inheritedLook, pnSeat).getAsJsonArray("granted_library");
                    assertTrue(
                            controlledLibrary.size() > 0,
                            "controller inherits the controlled player's active library-look grant"
                    );
                    if (unrelatedPlayer != null) {
                        assertEquals(
                                0,
                                playerRow(inheritedLook, unrelatedSeat)
                                        .getAsJsonArray("granted_library").size(),
                                "unrelated library remains hidden"
                        );
                    }
                } finally {
                    XmageFullGameStateRedactor.endZoneFullLook(controlled, controlled);
                }
                assertEquals(
                        0,
                        playerRow(
                                XmageFullGameStateRedactor.actorView(game, controller), pnSeat)
                                .getAsJsonArray("granted_library").size(),
                        "library entitlement closes with the underlying look window"
                );

                Card looked = controlled.getLibrary().getCards(game).iterator().next();
                XmageFullGameStateRedactor.recordLookedAt(
                        game, controlled.getId(), "F-27 controlled look", List.of(looked));
                assertTrue(
                        hasObservedTitle(
                                XmageFullGameStateRedactor.actorView(game, controller),
                                "F-27 controlled look"
                        ),
                        "controller receives the controlled player's look observation"
                );
                if (unrelatedPlayer != null) {
                    assertFalse(
                            hasObservedTitle(
                                    XmageFullGameStateRedactor.actorView(game, unrelatedPlayer),
                                    "F-27 controlled look"
                            ),
                            "look observation must not leak to an unrelated principal"
                    );
                }
                privacyChecked = true;
            }

            switch (cls) {
                case "priority" -> {
                    if (!activated && "P1".equals(active)) {
                        s.submit(s.action("activate_ability", "Mindslaver"));
                        activated = true;
                    } else if (controlledPid.equals(active) && "P1".equals(actor) && !boltCast
                            && game.getStack().isEmpty()
                            && s.action("activate_ability", "Cast Lightning Bolt") != null) {
                        s.submit(s.action("activate_ability", "Cast Lightning Bolt"));
                        boltCast = true;
                    } else {
                        s.submit(s.action("pass_priority", "Pass"));
                    }
                }
                case "mana_payment" -> s.payWith(controlledPid.equals(active) ? "Mountain" : "Island");
                case "target" -> s.submit(s.action("choose_targets", "Seat 2"));
                case "declare_attacker" -> s.submit(
                        s.action("declare_attackers", "Do not attack with"));
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null),
                        "privacy-d" + i,
                        "Mountain",
                        decision.get("minimum_selections").getAsInt()
                );
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("the turn after P2's was not reached");
    }

    private static XmageNativeStateRestoration restoration(XmageFullGameSession session)
            throws Exception {
        Field field = XmageFullGameSession.class.getDeclaredField("restoration");
        field.setAccessible(true);
        return (XmageNativeStateRestoration) field.get(session);
    }

    private static JsonObject playerRow(JsonObject view, int seat) {
        for (JsonElement element : view.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            if (player.get("seat").getAsInt() == seat) {
                return player;
            }
        }
        throw new AssertionError("player row missing seat " + seat);
    }

    private static JsonObject battlefieldItem(JsonObject view, String objectId) {
        for (JsonElement playerElement : view.getAsJsonArray("players")) {
            for (JsonElement permanentElement
                    : playerElement.getAsJsonObject().getAsJsonArray("battlefield")) {
                JsonObject permanent = permanentElement.getAsJsonObject();
                if (objectId.equals(permanent.get("object_id").getAsString())) {
                    return permanent;
                }
            }
        }
        throw new AssertionError("battlefield object missing " + objectId);
    }

    private static boolean hasObservedTitle(JsonObject view, String title) {
        for (JsonElement element : view.getAsJsonArray("looked_at")) {
            JsonObject observation = element.getAsJsonObject();
            if (observation.has("title") && !observation.get("title").isJsonNull()
                    && title.equals(observation.get("title").getAsString())) {
                return true;
            }
        }
        return false;
    }
}
