package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.stack.StackObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Copying another player's spell, with actual cards at 4P and 5P on the
 * full-game lane.
 *
 * <p>P1 casts Lightning Bolt at P2. P3 (not active) responds with Reverberate
 * (Oracle: "Copy target instant or sorcery spell. You may choose new targets
 * for the copy."). A copy of a spell is controlled by the player who put it on
 * the stack (707.10), so P3 controls the copy and P3, not P1, decides whether
 * to change its target; P3 redirects it to P4.</p>
 */
class XmageMultiplayerCopySpellTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void theCopierControlsTheCopyAndChoosesItsNewTarget(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P3", "Reverberate", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P3", "Mountain", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P3", "Mountain", 2, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("copy-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        UUID p3 = s.seats.get("P3").getId();

        s.submit(s.action("activate_ability", "Cast Lightning Bolt"));
        List<String> retargetAsked = new ArrayList<>();
        boolean copyChecked = false;
        for (int i = 0; i < 80; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            if ("priority".equals(cls) && game.getStack().isEmpty() && copyChecked) {
                break;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Mountain");
                case "priority" -> {
                    JsonObject reverberate = s.action("activate_ability", "Cast Reverberate");
                    if ("P3".equals(actor) && reverberate != null && game.getStack().size() == 1) {
                        s.submit(reverberate);
                    } else {
                        if (!copyChecked) {
                            for (StackObject o : game.getStack()) {
                                if (o.isCopy() && "Lightning Bolt".equals(o.getName())) {
                                    assertEquals(p3, o.getControllerId(), "707.10: P3 controls the copy");
                                    copyChecked = true;
                                }
                            }
                        }
                        s.submit(s.action("pass_priority", "Pass"));
                    }
                }
                case "choose_use" -> {
                    retargetAsked.add(actor);
                    s.submit(pick(s, "Yes"));
                }
                case "target" -> {
                    String wanted = switch (actor) {
                        case "P1" -> "Seat 2";
                        case "P3" -> game.getStack().size() >= 2 ? "Lightning Bolt" : "Seat 4";
                        default -> null;
                    };
                    if ("P3".equals(actor) && !retargetAsked.isEmpty()) {
                        wanted = "Seat 4";
                    }
                    assertNotNull(wanted, "unexpected target decision for " + actor);
                    s.submit(pick(s, wanted));
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        assertTrue(copyChecked, "the copy was on the stack");
        assertEquals(List.of("P3"), retargetAsked, "only the copy's controller P3 may change its target");
        assertEquals(40 - 3, s.seats.get("P2").getLife(), "the original Bolt hit P2");
        assertEquals(40 - 3, s.seats.get("P4").getLife(), "P3's copy hit P4");
        assertEquals(40, s.seats.get("P3").getLife());
        assertEquals(40, s.seats.get("P1").getLife());
    }

    private static JsonObject pick(XmageMultiplayerScenario s, String labelPart) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            String label = e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            if (label.equals(labelPart) || label.contains(labelPart)) {
                return e.getAsJsonObject();
            }
        }
        fail("no option " + labelPart + " in " + s.labels());
        return null;
    }
}
