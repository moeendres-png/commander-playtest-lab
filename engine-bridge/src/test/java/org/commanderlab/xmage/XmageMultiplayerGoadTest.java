package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Goad in 4-player Commander on the XMage full-game lane (CR 701.38): after
 * P1 casts Disrupt Decorum, P2's goaded Grizzly Bears must attack on P2's
 * turn, and must attack a player other than P1. The engine seats
 * counterclockwise, so P2's turn is the fourth; XMage asks for the forced
 * attack as a required single choice among the non-goader opponents.
 */
class XmageMultiplayerGoadTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    private static XmageNativeStateRestoration.RequestedObject obj(
            String pid, String name, int index, Zone zone) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zone.name().toLowerCase() + "-" + pid + "-" + index + "-" + slug,
                name, pid, pid, zone, false);
    }

    private static JsonObject action(XmageFullGameSession session, String actionType,
            String labelPart) {
        for (JsonElement e : session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject a = e.getAsJsonObject();
            if (actionType.equals(a.get("action_type").getAsString())
                    && a.getAsJsonObject("metadata").get("label").getAsString()
                            .contains(labelPart)) {
                return a;
            }
        }
        return null;
    }

    @Test
    void goadedBearsAttackAPlayerOtherThanTheGoader() {
        String tag = "xmage-goad-4p";
        int count = 4;
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= count; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
        }
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", "Disrupt Decorum", 0, Zone.HAND));
        for (int i = 0; i < 4; i++) {
            objects.add(obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        objects.add(obj("P2", "Grizzly Bears", 0, Zone.BATTLEFIELD));
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, count, 424242L, List.copyOf(players), List.copyOf(commanders),
                List.copyOf(objects), 1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(tag + "-" + player.playerId(),
                    tag + "-hash", mainboard, List.of(ROGRAKH)).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);

        boolean cast = false;
        JsonObject p2Attack = null;
        StringBuilder trace = new StringBuilder();
        for (int step = 0; step < 300 && p2Attack == null; step++) {
            JsonObject legal = session.legalActionsPayload();
            if (legal.get("decision_class") == null || legal.get("decision_class").isJsonNull()) {
                fail("terminal before P2's attack; trace:\n" + trace);
            }
            String cls = legal.get("decision_class").getAsString();
            String actor = XmageNativeStateRestorationTest.pidOf(seats,
                    legal.get("actor_id").getAsString());
            trace.append(step).append(' ').append(actor).append(' ').append(cls)
                    .append(" active=").append(XmageNativeStateRestorationTest.pidOf(seats,
                            session.restorationGame().getActivePlayerId().toString()))
                    .append(" turn=").append(session.restorationGame().getTurnNum())
                    .append(" step=").append(session.restorationGame().getStep().getType())
                    .append('\n');
            JsonObject next;
            if ("priority".equals(cls) && "P1".equals(actor) && !cast) {
                next = action(session, "activate_ability", "Cast Disrupt Decorum");
                cast = true;
            } else if ("mana_payment".equals(cls)) {
                next = action(session, "pay_cost", "Spend ");
                if (next == null) {
                    next = action(session, "pay_cost", "Mountain");
                }
            } else if (("declare_attacker".equals(cls) || "target".equals(cls))
                    && "P2".equals(actor)) {
                p2Attack = legal;
                break;
            } else if ("declare_attacker".equals(cls)) {
                next = null;
                fail(actor + " asked to attack; only P2 controls a creature");
            } else if ("choose_object".equals(cls) && session.pendingDecisionPayload()
                    .getAsJsonObject("decision").get("prompt").getAsString()
                    .contains("discard")) {
                // Cleanup hand-size discard: the test pilot discards a Mountain.
                next = action(session, "choose_targets", "Mountain");
            } else if ("priority".equals(cls)) {
                next = action(session, "pass_priority", "Pass");
            } else {
                next = null;
                fail("unexpected " + cls + " for " + actor + " prompt="
                        + session.pendingDecisionPayload().getAsJsonObject("decision")
                                .get("prompt") + "; trace:\n" + trace);
            }
            assertNotNull(next, "no action for " + cls + " / " + actor + "; trace:\n" + trace);
            XmageFullGameTaxExecutionTest.submit(session, tag + "-" + step, next);
        }
        assertNotNull(p2Attack, "P2 was never asked to attack (goaded Bears must attack); trace:\n"
                + trace);
        List<String> defenders = new ArrayList<>();
        StringBuilder dump = new StringBuilder();
        for (JsonElement e : p2Attack.getAsJsonArray("actions")) {
            JsonObject metadata = e.getAsJsonObject().getAsJsonObject("metadata");
            dump.append(metadata.get("label")).append(' ')
                    .append(metadata.get("xmage_option_metadata")).append('\n');
            JsonObject nativeMeta = metadata.getAsJsonObject("xmage_option_metadata");
            String id = nativeMeta == null ? null
                    : nativeMeta.has("defender_id") ? nativeMeta.get("defender_id").getAsString()
                    : nativeMeta.has("object_id") ? nativeMeta.get("object_id").getAsString()
                    : null;
            if (id == null) {
                id = e.getAsJsonObject().getAsJsonObject("metadata").get("option_id")
                        .getAsString();
            }
            defenders.add(XmageNativeStateRestorationTest.pidOf(seats, id));
        }
        JsonObject decision = session.pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals(List.of("P3", "P4"), defenders.stream().sorted().toList(),
                "goaded Bears may attack only players other than P1:\n" + dump);
        assertEquals(1, decision.get("minimum_selections").getAsInt(),
                "attacking is required (goad: attacks each combat if able):\n" + dump);
        assertEquals(1, decision.get("maximum_selections").getAsInt(), dump.toString());
    }
}
