package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.combat.CombatGroup;
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
 * CR 509.1a with an actual card on the full-game lane: Palace Guard ("can
 * block any number of creatures") must be offered one block decision over
 * every attacker, and blocking both must stand in the engine's combat.
 *
 * <p>XMage encodes "any number" as maxBlocks == 0. Before blockCapacity(),
 * selectBlockers computed min(0, offered) and skipped the Guard, so its
 * controller was never asked and it could not block.</p>
 */
class XmagePalaceGuardBlockTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    private static XmageNativeStateRestoration.RequestedObject battlefield(
            String pid, String name, int index) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-" + index + "-" + slug, name, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
    }

    @Test
    void palaceGuardIsAskedOnceAndBlocksBothAttackers() {
        String tag = "palace-guard-block";
        List<XmageNativeStateRestoration.RequestedObject> objects = List.of(
                battlefield("P1", "Raging Goblin", 0),
                battlefield("P1", "Raging Goblin", 1),
                battlefield("P2", "Palace Guard", 0));
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
        Game game = session.restorationGame();
        UUID p2 = seats.get("P2").getId();

        JsonObject blockDecision = null;
        for (int step = 0; step < 80 && blockDecision == null; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before blockers");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actor = XmageNativeStateRestorationTest.pidOf(
                    seats, legal.get("actor_id").getAsString());
            switch (decisionClass) {
                case "priority" -> XmageFullGameTaxExecutionTest.submit(session,
                        tag + "-pass-" + step, XmageNativeStateRestorationTest
                                .singleActionOfType(legal, "pass_priority", null));
                case "declare_attacker" -> {
                    if (!"P1".equals(actor)) {
                        fail("P1's combat ended without Palace Guard's controller being asked "
                                + "to block (maxBlocks == 0 skipped); P2 life "
                                + seats.get("P2").getLife());
                    }
                    XmageFullGameTaxExecutionTest.submit(session,
                            tag + "-attack-" + step, attackAt(legal, p2));
                }
                case "declare_blocker" -> {
                    assertEquals("P2", actor, "only P2 defends");
                    blockDecision = pending;
                }
                default -> fail("unexpected decision before blocks: " + decisionClass);
            }
        }
        assertNotNull(blockDecision,
                "Palace Guard's controller was never asked to block (maxBlocks == 0 skipped)");
        assertEquals(0, blockDecision.get("minimum_selections").getAsInt());
        assertEquals(2, blockDecision.get("maximum_selections").getAsInt(),
                "Palace Guard may block every attacker");

        JsonObject legal = session.legalActionsPayload();
        List<String> offered = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            offered.add(element.getAsJsonObject().getAsJsonObject("metadata")
                    .get("option_id").getAsString());
        }
        assertEquals(2, offered.size(), "one option per attacking Raging Goblin");
        String decisionId = blockDecision.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag + "-block");
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + offered.get(0));
        proposal.addProperty("action_type", "declare_blockers");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", blockDecision.get("decision_offset").getAsLong());
        JsonArray selected = new JsonArray();
        offered.forEach(selected::add);
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        session.submitAction(proposal);

        Permanent guard = null;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(p2)) {
            if (permanent.getName().equals("Palace Guard")) {
                guard = permanent;
            }
        }
        assertNotNull(guard, "Palace Guard on the battlefield");
        int blocked = 0;
        for (CombatGroup group : game.getCombat().getGroups()) {
            if (group.getBlockers().contains(guard.getId())) {
                blocked += group.getAttackers().size();
            }
        }
        assertEquals(2, blocked, "Palace Guard blocks both Raging Goblins in the engine's combat");
        assertTrue(guard.getBlocking() >= 2, "engine records two blocks for the Guard");
    }

    private static JsonObject attackAt(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if ("declare_attackers".equals(action.get("action_type").getAsString())
                    && metadata != null && metadata.has("defender_id")
                    && defender.toString().equals(metadata.get("defender_id").getAsString())) {
                return action;
            }
        }
        fail("no attack at P2 offered: " + legal);
        return null;
    }
}
