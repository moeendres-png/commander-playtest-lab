package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * PB-03 Wave 2c: genuine-causal control divergence and extra turns
 * (Muse XHIGH).
 *
 * <p>MICRO_CONTROL executes: the record's Control Magic is relocated to hand,
 * cast genuinely with fuel mana, and resolution transfers control through the
 * real effect (never direct assignment). WS05-MP-TURN-5 attempts the genuine
 * double extra-turn sequence; if turn-1 cleanup discards block honest
 * progress, it characterizes instead (row stays BLOCKED).</p>
 */
class XmagePb03Tier2ControlTurnTest {

    private static final long SEED = 424242L;

    // ---- WS05-MP-TURN-5: genuine extra turns, P3 then P2 ----

    @Test
    void mpTurn5ExtraTurnsRunP3ThenP2() {
        JsonObject record =
                XmageNativeStateRestorationTest.frozenRecord("WS05-MP-TURN-5");
        // Relocate both extra-turn spells to hands for genuine casts; fuel
        // Time Warp {3}{U}{U} and Nexus of Fate {5}{U}{U}. Hand arithmetic
        // stays at or below seven at every cleanup, so no discard choice is
        // ever required: P1 7+1-1, P3 7-1+1, P2 observed at turn start.
        java.util.List<XmagePb03Tier2CmdZoneTest.FuelLand> fuel = new java.util.ArrayList<>();
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p1a", "Island", "P1"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p1b", "Island", "P1"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p1c", "Island", "P1"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p1d", "Island", "P1"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p1e", "Island", "P1"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p3a", "Island", "P3"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p3b", "Island", "P3"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p3c", "Island", "P3"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p3d", "Island", "P3"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p3e", "Island", "P3"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p3f", "Island", "P3"));
        fuel.add(new XmagePb03Tier2CmdZoneTest.FuelLand("obj:fuel-p3g", "Island", "P3"));
        XmageNativeStateRestoration.Plan plan =
                XmagePb03Tier2CmdZoneTest.preconditionPlanForTest(record, "pb03-turn5", fuel,
                        Map.of("obj:mp-time-warp", "hand", "obj:mp-nexus", "hand"),
                        Map.of());
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "pb03-turn5");
        XmageFullGameSession session = new XmageFullGameSession(
                "WS05-MP-TURN-5", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict precondition =
                restoration.compare(
                        XmageNativeStateRestoration.readback(
                                session.restorationGame(), seats),
                        seats);
        assertTrue(precondition.match(),
                "TURN-5 precondition must match: " + precondition.mismatches());

        // Creation order determines taking order (LIFO: most recently
        // created extra turn goes first). To take P3 then P2, P3's extra
        // must be created LAST: resolve Warp fully (P2 created) before P3
        // casts Nexus (P3 created). Sequential resolution also respects
        // sorcery timing (Warp needs an empty stack).
        XmagePb03Tier1RowsTest.castSpellAs(
                session, seats, "pb03-turn5", "Time Warp", "P1");
        answerPlayerTarget(session, seats, "P2", "pb03-turn5-warp");
        XmagePb03Tier1RowsTest.payHomogeneous(
                session, "pb03-turn5-warp", "Island \u2014 {T}: Add {U}.");
        assertSpellOnStack(session, "Time Warp", "pb03-turn5");
        resolveUntilStackEmpty(session, seats, "pb03-turn5-warp");
        XmagePb03Tier1RowsTest.castSpellAs(
                session, seats, "pb03-turn5", "Nexus of Fate", "P3");
        XmagePb03Tier1RowsTest.payHomogeneous(
                session, "pb03-turn5-nexus", "Island \u2014 {T}: Add {U}.");
        assertSpellOnStack(session, "Nexus of Fate", "pb03-turn5");
        resolveUntilStackEmpty(session, seats, "pb03-turn5-nexus");
        // Complete turn 1 neutrally; the extra turns run P3 then P2 (LIFO).
        String firstExtra = driveToNextTurn(session, seats, "pb03-turn5-t1", 200);
        assertEquals("P3", firstExtra, "most recently created extra turn goes first");
        String secondExtra = driveToNextTurn(session, seats, "pb03-turn5-t3", 200);
        assertEquals("P2", secondExtra, "then the earlier extra turn");
    }

    private static void assertSpellOnStack(
            XmageFullGameSession session, String cardName, String tag) {
        boolean found = false;
        for (mage.game.stack.StackObject stackObject
                : session.restorationGame().getStack()) {
            if (cardName.equals(stackObject.getName())) {
                found = true;
            }
        }
        assertTrue(found, tag + ": " + cardName + " must be on the stack after payment");
    }

    private static void resolveUntilStackEmpty(
            XmageFullGameSession session, Map<String, Player> seats, String tag) {
        for (int step = 0; step < 80; step++) {
            if (session.restorationGame().getStack().isEmpty()) {
                return;
            }
            driveNeutral(session, seats, tag + "-" + step);
        }
        fail(tag + ": stack did not empty");
    }

    private static boolean hasExtraTurn(
            XmageFullGameSession session, Map<String, Player> seats) {
        return XmageNativeStateRestoration.readback(
                session.restorationGame(), seats).get("has_extra_turn").getAsBoolean();
    }

    private static void answerPlayerTarget(
            XmageFullGameSession session,
            Map<String, Player> seats,
            String targetSeat,
            String tag) {
        for (int step = 0; step < 10; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail(tag + ": engine terminal seeking target decision");
            }
            String decisionClass = payload.getAsJsonObject("decision")
                    .get("decision_class").getAsString();
            if (!"target".equals(decisionClass)) {
                return;
            }
            Player target = seats.get(targetSeat);
            assertNotNull(target, "target seat must exist");
            XmagePb03Tier1RowsTest.submit(session, tag + "-target-" + step,
                    XmagePb03Tier1RowsTest.findTargetOffer(
                            session, target.getId().toString(), targetSeat));
        }
        fail(tag + ": target decisions did not complete");
    }

    private static void driveNeutral(
            XmageFullGameSession session, Map<String, Player> seats, String tag) {
        String pending = pendingClass(session);
        if (pending == null) {
            return;
        }
        if ("declare_attacker".equals(pending)) {
            XmagePb03Tier1RowsTest.submit(session, tag,
                    XmageNativeStateRestorationTest.singleActionOfType(
                            session.legalActionsPayload(),
                            "declare_attackers", "hold_attacker"));
            return;
        }
        if ("declare_blocker".equals(pending)) {
            XmagePb03Tier1RowsTest.submitProposal(session, tag,
                    XmagePb03Tier1RowsTest.emptyBlockProposal(
                            tag, session.legalActionsPayload()));
            return;
        }
        if (!"priority".equals(pending)) {
            fail("unexpected " + pending + " driving neutrally");
        }
        XmagePb03Tier1RowsTest.passPriority(session, tag);
    }

    private static String activePlayerPid(
            XmageFullGameSession session, Map<String, Player> seats) {
        return XmageNativeStateRestoration.readback(
                session.restorationGame(), seats).get("active_player").getAsString();
    }

    private static String activeSeat(
            XmageFullGameSession session, Map<String, Player> seats) {
        String active = activePlayerPid(session, seats);
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            if (active.equals(entry.getValue().getId().toString())
                    || active.equals(entry.getKey())) {
                return entry.getKey();
            }
        }
        fail("unresolvable active player: " + active);
        return "?";
    }

    private static String driveToNextTurn(
            XmageFullGameSession session, Map<String, Player> seats, String tag, int bound) {
        String startActive = activeSeat(session, seats);
        for (int step = 0; step < bound; step++) {
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if ("choose_object".equals(pending)) {
                // Cleanup discards on the way (restored+drawn spares can push
                // a hand to eight). Identical options make the choice
                // outcome-neutral; anything mixed fails loudly instead.
                JsonObject legal = session.legalActionsPayload();
                String firstName = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    String label = element.getAsJsonObject().getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if (firstName == null) {
                        firstName = label;
                    }
                    assertEquals(firstName, label,
                            tag + ": cleanup discard options must be identical");
                }
                assertNotNull(firstName, tag + ": discard must offer options");
                XmagePb03Tier1RowsTest.submit(session, tag + "-discard-" + step,
                        legal.getAsJsonArray("actions").get(0).getAsJsonObject());
                continue;
            }
            if (!"priority".equals(pending)
                    && !"declare_attacker".equals(pending)
                    && !"declare_blocker".equals(pending)) {
                JsonObject legal = session.legalActionsPayload();
                StringBuilder options = new StringBuilder();
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    options.append("  ").append(element.getAsJsonObject()
                            .getAsJsonObject("metadata")).append("\n");
                }
                fail(tag + ": unexpected " + pending + " completing turn; options:\n" + options);
            }
            driveNeutral(session, seats, tag + "-" + step);
            String now = activeSeat(session, seats);
            if (!startActive.equals(now)) {
                return now;
            }
        }
        fail(tag + ": turn did not advance from " + startActive);
        return "?";
    }

    private static String pendingClass(XmageFullGameSession session) {
        return XmagePb03Tier1RowsTest.pendingClass(session);
    }

    @Test
    void microControlMagicTransfersBearsToP1() {
        JsonObject record =
                XmageNativeStateRestorationTest.frozenRecord("MICRO_CONTROL");
        // Relocate Control Magic to hand for a genuine cast; fuel the {3}{U}.
        List<XmagePb03Tier2CmdZoneTest.FuelLand> fuel = List.of(
                new XmagePb03Tier2CmdZoneTest.FuelLand(
                        "obj:fuel-island-a", "Island", "P1"),
                new XmagePb03Tier2CmdZoneTest.FuelLand(
                        "obj:fuel-island-b", "Island", "P1"),
                new XmagePb03Tier2CmdZoneTest.FuelLand(
                        "obj:fuel-island-c", "Island", "P1"),
                new XmagePb03Tier2CmdZoneTest.FuelLand(
                        "obj:fuel-island-d", "Island", "P1"));
        XmageNativeStateRestoration.Plan plan =
                XmagePb03Tier2CmdZoneTest.preconditionPlanForTest(record, "pb03-control", fuel,
                        Map.of("obj:micro-controlmagic", "hand"),
                        // Pre-cause control: P2 owns and controls the Bears;
                        // the genuine Control Magic transfers it to P1.
                        Map.of("obj:micro-controlled", "P2"));
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "pb03-control");
        XmageFullGameSession session = new XmageFullGameSession(
                "MICRO_CONTROL", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict precondition =
                restoration.compare(
                        XmageNativeStateRestoration.readback(
                                session.restorationGame(), seats),
                        seats);
        assertTrue(precondition.match(),
                "MICRO_CONTROL precondition must match: " + precondition.mismatches());

        XmagePb03Tier1RowsTest.castSpellAs(
                session, seats, "pb03-control", "Control Magic", "P1");
        // Target the P2 Bears.
        for (int step = 0; step < 10; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("pb03-control: engine terminal seeking target decision");
            }
            String decisionClass = payload.getAsJsonObject("decision")
                    .get("decision_class").getAsString();
            if (!"target".equals(decisionClass)) {
                break;
            }
            UUID bearsId = restoration.injectedObjectId("obj:micro-controlled");
            XmagePb03Tier1RowsTest.submit(session, "pb03-control-target-" + step,
                    XmagePb03Tier1RowsTest.findTargetOffer(
                            session, bearsId.toString(), "obj:micro-controlled"));
        }
        XmagePb03Tier1RowsTest.payHomogeneous(
                session, "pb03-control", "Island \u2014 {T}: Add {U}.");
        // Control must resolve precombat (no cleanup traversal: P1's hand
        // is mixed and no discard may be chosen). Break at the Aura ETB.
        for (int step = 0; step < 40; step++) {
            boolean resolved = false;
            for (Permanent permanent : session.restorationGame()
                    .getBattlefield().getAllPermanents()) {
                if (permanent.getName().equals("Control Magic")
                        && seats.get("P1").getId().equals(permanent.getControllerId())) {
                    resolved = true;
                }
            }
            if (resolved) {
                break;
            }
            String pending = XmagePb03Tier1RowsTest.pendingClass(session);
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + pending + " resolving Control Magic");
            }
            XmagePb03Tier1RowsTest.passPriority(session, "pb03-control-pass-" + step);
        }

        // Owner/controller divergence created only by the genuine effect.
        UUID controlledId = restoration.injectedObjectId("obj:micro-controlled");
        Permanent controlled = session.restorationGame().getPermanent(controlledId);
        assertNotNull(controlled, "controlled Bears must exist");
        assertEquals(seats.get("P2").getId(), controlled.getOwnerId(), "owner remains P2");
        assertEquals(seats.get("P1").getId(), controlled.getControllerId(),
                "controller is P1 through the resolved Control Magic");
    }
}
