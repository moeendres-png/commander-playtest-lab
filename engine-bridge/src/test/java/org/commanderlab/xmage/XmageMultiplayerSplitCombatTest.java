package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Attacks split across two opponents at 3–6 players, with actual cards on
 * the full-game lane.
 *
 * <p>P1 attacks P2 with Raging Goblin and P3 with Hellrider (Oracle: "Haste.
 * Whenever a creature you control attacks, this creature deals 1 damage to the
 * player or planeswalker it's attacking."). Every opponent controls a Grizzly
 * Bears.</p>
 *
 * <ul>
 *   <li>Hellrider: each trigger damages the player that creature attacks, so P2
 *       and P3 lose 1 each and nobody else loses life.</li>
 *   <li>CR 802.4a: a defending player's creatures can block only creatures
 *       attacking that player. So P2's Bears is offered exactly the Goblin, P3's
 *       Bears exactly Hellrider, and players nobody attacks are never asked to
 *       block.</li>
 *   <li>Before the fix, the lane offered every attacker to every defending
 *       blocker (via {@code Permanent.canBlock}, which checks only "is an
 *       opponent"). The engine then silently dropped a block chosen against
 *       another player's attacker ({@code CombatGroup.canBlock} rejects it).</li>
 * </ul>
 */
class XmageMultiplayerSplitCombatTest {

    private static final String GOBLIN = "Raging Goblin";
    private static final String HELLRIDER = "Hellrider";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void eachDefenderMayBlockOnlyTheCreaturesAttackingThem(int playerCount) {
        String tag = "split-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(bf("P1", GOBLIN));
        objects.add(bf("P1", HELLRIDER));
        for (int seat = 2; seat <= playerCount; seat++) {
            objects.add(bf("P" + seat, BEARS));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));
        Map<String, String> attackAt = Map.of(GOBLIN, "P2", HELLRIDER, "P3");

        Map<String, List<String>> blockOffers = new LinkedHashMap<>();
        boolean damageDealt = false;
        for (int step = 0; step < 200 && !damageDealt; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    if (game.getStep().getType() == mage.constants.PhaseStep.END_COMBAT) {
                        damageDealt = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> {
                    assertEquals("P1", actor);
                    String attacker = attackerName(legal);
                    UUID defender = ids.get(attackAt.get(attacker));
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-attack-" + step,
                            attackOption(legal, defender));
                }
                case "trigger_order" -> XmageFullGameTaxExecutionTest.submit(session,
                        tag + "-order-" + step, equivalentHellriderTrigger(legal));
                case "declare_blocker" -> {
                    List<String> offered = new ArrayList<>();
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        Permanent attacker = game.getPermanent(
                                UUID.fromString(meta.get("attacker_id").getAsString()));
                        offered.add(attacker.getName());
                    }
                    assertTrue(blockOffers.put(actor, offered) == null,
                            actor + " is asked once for its one Bears");
                    if ("P2".equals(actor)) {
                        blockWithEveryOffer(session, tag + "-block-" + step);
                    } else {
                        XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + step);
                    }
                }
                default -> fail("unexpected decision " + cls + " for " + actor);
            }
        }
        assertTrue(damageDealt, "combat reached its end step");

        assertEquals(Map.of("P2", List.of(GOBLIN), "P3", List.of(HELLRIDER)), blockOffers,
                "CR 802.4a: each defender is offered only its own attacker; "
                        + "unattacked players are not asked");
        assertEquals(39, started.seats().get("P2").getLife(),
                "P2: 1 from Hellrider's trigger for the Goblin; the Goblin was blocked");
        assertEquals(36, started.seats().get("P3").getLife(),
                "P3: 1 from Hellrider's own trigger plus 3 unblocked combat damage");
        for (int seat = 4; seat <= playerCount; seat++) {
            assertEquals(40, started.seats().get("P" + seat).getLife(),
                    "P" + seat + " was not attacked");
        }
        assertEquals(40, started.seats().get("P1").getLife());
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", GOBLIN),
                "the Goblin died to P2's blocking Bears");
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P2", BEARS));
    }

    private static XmageNativeStateRestoration.RequestedObject bf(String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""), name, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
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

    /** Both triggers are Hellrider's own and rules-equivalent; take the lowest id. */
    private static JsonObject equivalentHellriderTrigger(JsonObject legal) {
        JsonObject chosen = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            assertEquals(HELLRIDER, engine.get("source_name").getAsString(),
                    "only Hellrider triggers are ordered");
            if (chosen == null || meta.get("option_id").getAsString().compareTo(
                    chosen.getAsJsonObject("metadata").get("option_id").getAsString()) < 0) {
                chosen = action;
            }
        }
        assertNotNull(chosen);
        return chosen;
    }

    private static void blockWithEveryOffer(XmageFullGameSession session, String tag) {
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
