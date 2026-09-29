package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.combat.CombatGroup;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Menace with split attacks at 3–6 players, with actual cards on the
 * full-game lane (CR 702.111b, 509.1b, 802.4a, 802.4b).
 *
 * <p>P1 attacks P2 with Broadside Bombardiers (Oracle: "Menace, haste / …")
 * and P3 with Raging Goblin. Every other opponent controls one Grizzly
 * Bears; P2 controls {@code p2Bears} of them. P2's first declaration is a
 * single Bears blocking the Bombardiers, which menace forbids.</p>
 *
 * <ul>
 *   <li>Two P2 Bears: a legal menace block exists, so the engine rejects the
 *       single block and asks P2 again. On the second round both Bears block,
 *       and that stands.</li>
 *   <li>One P2 Bears: no legal block of the Bombardiers exists, so the only
 *       legal declaration is none. The engine discards the single block without
 *       asking again, and the Bombardiers are unblocked.</li>
 *   <li>In both cases P3's creatures are never offered the Bombardiers, so no
 *       other player's creature can make up P2's menace block (802.4b).</li>
 * </ul>
 *
 * <p>The lane asks one decision per blocker, so a single block that is
 * illegal only as a whole declaration is still offered; the engine's own
 * validation settles it (review finding F-17).</p>
 */
class XmageMultiplayerMenaceTest {

    private static final String MENACE = "Broadside Bombardiers";
    private static final String GOBLIN = "Raging Goblin";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players, P2 has {1} Bears")
    @CsvSource({"3, 2", "4, 2", "5, 2", "6, 2", "4, 1", "5, 1"})
    void menaceBlockIsSettledByTheEngineWithinTheDefendingPlayer(int playerCount, int p2Bears) {
        String tag = "menace-" + playerCount + "p-" + p2Bears;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(bf("P1", MENACE, 0));
        objects.add(bf("P1", GOBLIN, 0));
        for (int index = 0; index < p2Bears; index++) {
            objects.add(bf("P2", BEARS, index));
        }
        for (int seat = 3; seat <= playerCount; seat++) {
            objects.add(bf("P" + seat, BEARS, 0));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        UUID p2 = started.seats().get("P2").getId();
        UUID p3 = started.seats().get("P3").getId();

        int p2Asks = 0;
        List<String> otherOffers = new ArrayList<>();
        boolean blocksDeclared = false;
        for (int step = 0; step < 200 && !blocksDeclared; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    if (game.getStep().getType() == mage.constants.PhaseStep.DECLARE_BLOCKERS) {
                        blocksDeclared = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> {
                    String attacker = attackerName(legal);
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-attack-" + step,
                            attackOption(legal, MENACE.equals(attacker) ? p2 : p3));
                }
                case "declare_blocker" -> {
                    List<String> offered = offeredAttackers(game, legal);
                    if ("P2".equals(actor)) {
                        assertEquals(List.of(MENACE), offered,
                                "P2's Bears may block only the creature attacking P2");
                        // Round 1: only the first Bears blocks (illegal under
                        // menace). Round 2: every Bears blocks.
                        boolean block = p2Asks == 0 || p2Asks >= p2Bears;
                        p2Asks++;
                        if (block) {
                            selectAll(session, tag + "-block-" + step);
                        } else {
                            XmageActualCardCorpusTest.chooseNone(started, tag + "-hold-" + step);
                        }
                    } else {
                        otherOffers.addAll(offered);
                        XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + step);
                    }
                }
                default -> fail("unexpected decision " + cls + " for " + actor + ": " + legal);
            }
        }
        assertTrue(blocksDeclared, "combat reached declare blockers");
        assertTrue(!otherOffers.contains(MENACE),
                "802.4a/b: no other player's creature is offered the Bombardiers: " + otherOffers);

        Permanent menace = only(game, started.seats().get("P1").getId(), MENACE);
        CombatGroup group = game.getCombat().findGroup(menace.getId());
        assertNotNull(group, "the Bombardiers attack");
        assertEquals(p2, group.getDefendingPlayerId());
        if (p2Bears == 2) {
            assertEquals(4, p2Asks,
                    "the illegal single block is rejected and both Bears are asked again");
            assertEquals(2, group.getBlockers().size(), "both P2 Bears block on the second round");
            for (UUID blocker : group.getBlockers()) {
                assertEquals(p2, game.getPermanent(blocker).getControllerId());
            }
        } else {
            assertEquals(1, p2Asks,
                    "no legal menace block exists, so the engine does not ask again");
            assertTrue(group.getBlockers().isEmpty(),
                    "the only legal declaration is no block; the single block is discarded");
        }
    }

    private static XmageNativeStateRestoration.RequestedObject bf(
            String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, mage.constants.Zone.BATTLEFIELD, false);
    }

    private static Permanent only(Game game, UUID controller, String name) {
        Permanent found = null;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(controller)) {
            if (name.equals(permanent.getName())) {
                assertTrue(found == null, "unique " + name);
                found = permanent;
            }
        }
        assertNotNull(found, name);
        return found;
    }

    private static List<String> offeredAttackers(Game game, JsonObject legal) {
        List<String> offered = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            offered.add(game.getPermanent(
                    UUID.fromString(meta.get("attacker_id").getAsString())).getName());
        }
        return offered;
    }

    private static String attackerName(JsonObject legal) {
        String name = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            String candidate = meta.get("name").getAsString();
            assertTrue(name == null || name.equals(candidate), "one attacker per decision");
            name = candidate;
        }
        assertNotNull(name);
        return name;
    }

    private static JsonObject attackOption(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta.has("defender_id")
                    && defender.toString().equals(meta.get("defender_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("attack at " + defender + " not offered: " + legal);
        return null;
    }

    private static void selectAll(XmageFullGameSession session, String tag) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        JsonArray selected = new JsonArray();
        String first = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            String optionId = element.getAsJsonObject().getAsJsonObject("metadata")
                    .get("option_id").getAsString();
            selected.add(optionId);
            first = first == null ? optionId : first;
        }
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + first);
        proposal.addProperty("action_type", "declare_blockers");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        session.submitAction(proposal);
    }
}
