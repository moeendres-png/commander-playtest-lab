package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.BooleanSupplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Provider-neutral actual-card checks on the XMage full-game lane.
 *
 * <p>These are the staples whose Forge bridge surfaces were fixed in
 * moeendres-png/forge#7: shock lands (non-mana "unless" cost), Rhystic Study
 * ("unless that player pays"), kicker (optional additional cost) and crew
 * (tap creatures with total power N). Each case asks whether the deciding
 * player is asked, whether every legal answer is offered, and whether the
 * engine applies the answer. XMage passed every case without a bridge change;
 * this class keeps it that way.</p>
 */
class XmageStapleDecisionTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    private record Started(XmageFullGameSession session, Map<String, Player> seats) {
        Game game() {
            return session.restorationGame();
        }

        Player p(String pid) {
            return seats.get(pid);
        }
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String pid, String name, int index, Zone zone) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zone.name().toLowerCase() + "-" + pid + "-" + index + "-" + slug,
                name, pid, pid, zone, false);
    }

    /** 2P restoration at P1's turn 1 precombat main, P1 holding priority. */
    private static Started start(String tag,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= 2; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, 2, 424242L, List.copyOf(players), List.copyOf(commanders), objects,
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
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
        return new Started(session, seats);
    }

    private static String decisionClass(Started s) {
        return s.session().legalActionsPayload().get("decision_class").getAsString();
    }

    private static String actor(Started s) {
        return XmageNativeStateRestorationTest.pidOf(s.seats(),
                s.session().legalActionsPayload().get("actor_id").getAsString());
    }

    private static List<String> labels(Started s) {
        List<String> out = new ArrayList<>();
        for (JsonElement e : s.session().legalActionsPayload().getAsJsonArray("actions")) {
            out.add(e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
        }
        return out;
    }

    private static JsonObject action(Started s, String actionType, String labelPart) {
        for (JsonElement e : s.session().legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject a = e.getAsJsonObject();
            if (actionType.equals(a.get("action_type").getAsString())
                    && a.getAsJsonObject("metadata").get("label").getAsString()
                            .contains(labelPart)) {
                return a;
            }
        }
        fail(actionType + " '" + labelPart + "' not offered in " + decisionClass(s)
                + " to " + actor(s) + ": " + labels(s));
        return null;
    }

    private static int step;

    private static void take(Started s, String actionType, String labelPart) {
        XmageFullGameTaxExecutionTest.submit(s.session(), "staple-" + (step++),
                action(s, actionType, labelPart));
    }

    /** Pays the pending mana cost from the named land type, spending pool mana first. */
    private static void payWith(Started s, String land) {
        for (int i = 0; i < 20 && "mana_payment".equals(decisionClass(s)); i++) {
            boolean poolOffered = labels(s).stream().anyMatch(l -> l.startsWith("Spend "));
            take(s, "pay_cost", poolOffered ? "Spend " : land);
        }
    }

    /** Passes priority until {@code done} holds or a non-priority decision appears. */
    private static void passUntil(Started s, BooleanSupplier done) {
        for (int i = 0; i < 20 && !done.getAsBoolean()
                && "priority".equals(decisionClass(s)); i++) {
            take(s, "pass_priority", "Pass");
        }
    }

    private static Permanent permanent(Started s, String pid, String name) {
        for (Permanent p : s.game().getBattlefield().getAllActivePermanents(s.p(pid).getId())) {
            if (p.getName().equals(name)) {
                return p;
            }
        }
        return null;
    }

    private static long tapped(Started s, String pid, String name) {
        return s.game().getBattlefield().getAllActivePermanents(s.p(pid).getId()).stream()
                .filter(p -> p.getName().equals(name) && p.isTapped()).count();
    }

    // ---- Shock land: "you may pay 2 life. If you don't, it enters tapped." ----

    private static void wateryGrave(boolean pay) {
        Started s = start("staple-shock-" + pay,
                List.of(obj("P1", "Watery Grave", 0, Zone.HAND)));
        take(s, "play_land", "Watery Grave");
        assertEquals("choose_use", decisionClass(s), "the land's controller decides");
        assertEquals("P1", actor(s));
        assertEquals(List.of("Yes", "No"), labels(s), "both answers offered");
        take(s, "structural_decision", pay ? "Yes" : "No");
        Permanent grave = permanent(s, "P1", "Watery Grave");
        assertNotNull(grave, "Watery Grave entered");
        assertEquals(!pay, grave.isTapped(), pay ? "paid: untapped" : "declined: tapped");
        assertEquals(pay ? 38 : 40, s.p("P1").getLife());
    }

    @Test
    void shockLandPaidEntersUntapped() {
        wateryGrave(true);
    }

    @Test
    void shockLandDeclinedEntersTapped() {
        wateryGrave(false);
    }

    // ---- Rhystic Study: "you may draw a card unless that player pays {1}" ----

    private static void rhystic(boolean studyOwnerDraws, boolean casterPays) {
        Started s = start("staple-rhystic-" + studyOwnerDraws + "-" + casterPays, List.of(
                obj("P1", "Grizzly Bears", 0, Zone.HAND),
                obj("P1", "Forest", 0, Zone.BATTLEFIELD),
                obj("P1", "Forest", 1, Zone.BATTLEFIELD),
                obj("P1", "Forest", 2, Zone.BATTLEFIELD),
                obj("P2", "Rhystic Study", 0, Zone.BATTLEFIELD)));
        int p2Hand = s.p("P2").getHand().size();
        take(s, "activate_ability", "Cast Grizzly Bears");
        payWith(s, "Forest");
        assertEquals(2, s.game().getStack().size(), "Rhystic Study triggered over the Bears");
        passUntil(s, () -> false);
        assertEquals("choose_use", decisionClass(s));
        assertEquals("P2", actor(s), "Study's controller decides whether to draw");
        take(s, "structural_decision", studyOwnerDraws ? "Yes" : "No");
        if (studyOwnerDraws) {
            assertEquals("choose_use", decisionClass(s));
            assertEquals("P1", actor(s), "the caster decides whether to pay {1}");
            assertEquals(List.of("Yes", "No"), labels(s));
            take(s, "structural_decision", casterPays ? "Yes" : "No");
            if (casterPays) {
                payWith(s, "Forest");
            }
        }
        assertEquals(1, s.game().getStack().size(), "trigger resolved; Bears still on the stack");
        boolean drew = studyOwnerDraws && !casterPays;
        assertEquals(p2Hand + (drew ? 1 : 0), s.p("P2").getHand().size());
        assertEquals(studyOwnerDraws && casterPays ? 3 : 2, tapped(s, "P1", "Forest"),
                "{1} paid only when the caster chose to pay");
        passUntil(s, () -> s.game().getStack().isEmpty());
        assertNotNull(permanent(s, "P1", "Grizzly Bears"), "the spell resolved either way");
    }

    @Test
    void rhysticStudyCasterPays() {
        rhystic(true, true);
    }

    @Test
    void rhysticStudyCasterDeclines() {
        rhystic(true, false);
    }

    @Test
    void rhysticStudyOwnerMayDecline() {
        rhystic(false, false);
    }

    // ---- Kicker: Burst Lightning, 2 damage or 4 if kicked ({4}) ----

    private static void burstLightning(boolean kick) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", "Burst Lightning", 0, Zone.HAND));
        for (int i = 0; i < 5; i++) {
            objects.add(obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        Started s = start("staple-kicker-" + kick, objects);
        take(s, "activate_ability", "Cast Burst Lightning");
        assertEquals("choose_use", decisionClass(s), "the caster chooses whether to kick");
        assertEquals("P1", actor(s));
        take(s, "structural_decision", kick ? "Yes" : "No");
        assertEquals("target", decisionClass(s));
        take(s, "choose_targets", "Seat 2");
        payWith(s, "Mountain");
        assertEquals(kick ? 5 : 1, tapped(s, "P1", "Mountain"),
                kick ? "{R} plus kicker {4}" : "{R} only");
        passUntil(s, () -> s.game().getStack().isEmpty());
        assertEquals(kick ? 36 : 38, s.p("P2").getLife());
    }

    @Test
    void kickedBurstLightningDealsFour() {
        burstLightning(true);
    }

    @Test
    void unkickedBurstLightningDealsTwo() {
        burstLightning(false);
    }

    // ---- Crew 1: Smuggler's Copter; the pilot picks which creatures tap ----

    @Test
    void crewIsThePilotsChoiceAndMayStopAtTheThreshold() {
        Started s = start("staple-crew", List.of(
                obj("P1", "Smuggler's Copter", 0, Zone.BATTLEFIELD),
                obj("P1", "Grizzly Bears", 0, Zone.BATTLEFIELD),
                obj("P1", "Raging Goblin", 0, Zone.BATTLEFIELD)));
        take(s, "activate_ability", "Crew 1");
        assertEquals("choose_object", decisionClass(s));
        assertEquals(List.of("Raging Goblin", "Grizzly Bears").stream().sorted().toList(),
                labels(s).stream().sorted().toList(), "every untapped creature offered");
        take(s, "choose_targets", "Raging Goblin");
        // Threshold reached: XMage asks for more with minimum_selections 0,
        // so the pilot may stop without tapping the Bears.
        assertEquals("choose_object", decisionClass(s));
        JsonObject pending = s.session().pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals(0, pending.get("minimum_selections").getAsInt(), "stopping is legal");
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "staple-crew-done");
        proposal.addProperty("actor_id", pending.get("actor_id").getAsString());
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        s.session().submitAction(proposal);
        passUntil(s, () -> s.game().getStack().isEmpty());
        Permanent copter = permanent(s, "P1", "Smuggler's Copter");
        assertTrue(copter.isCreature(s.game()), "Copter crewed");
        assertTrue(permanent(s, "P1", "Raging Goblin").isTapped(), "the goblin crewed it");
        assertFalse(permanent(s, "P1", "Grizzly Bears").isTapped(), "the Bears untouched");
    }
}
