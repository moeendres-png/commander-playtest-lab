package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Per-defender attack limits with an actual card at 3–6 players on the
 * full-game lane (F-25).
 *
 * <p>P1 controls Crawlspace (Oracle: "No more than two creatures can attack
 * you each combat."). On its turn PN has Grizzly Bears, Raging Goblin and
 * Runeclaw Bear and tries to send each of them at P1, otherwise at P2. The
 * limit restricts attacks on P1 only (508.1c: the declaration as a whole must
 * obey it); it does not restrict attacks on other players.</p>
 *
 * <p>The lane asks one {@code declare_attacker} decision per creature. Before
 * F-25 it still offered "attacks P1" to the third creature; the engine then
 * silently refused that attacker, so the pilot's selection was dropped with
 * no decision. Now a player whose limit the already-declared attackers have
 * reached is no longer offered.</p>
 */
class XmageMultiplayerAttackLimitTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void aPlayerAtItsAttackLimitIsNoLongerOffered(int playerCount) {
        String tag = "limit-" + playerCount + "p";
        String pn = "P" + playerCount;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(bf("P1", "Crawlspace", 0));
        objects.add(bf(pn, "Grizzly Bears", 0));
        objects.add(bf(pn, "Raging Goblin", 0));
        objects.add(bf(pn, "Runeclaw Bear", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        UUID p1 = started.seats().get("P1").getId();
        UUID p2 = started.seats().get("P2").getId();
        Map<String, Set<String>> offeredDefenders = new LinkedHashMap<>();
        Map<String, String> chosen = new LinkedHashMap<>();
        int decisions = 0;
        for (int guard = 0; guard < 300; guard++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            if ("priority".equals(cls) && game.getStep().getType() == PhaseStep.POSTCOMBAT_MAIN
                    && started.seats().get(pn).getId().equals(game.getActivePlayerId())) {
                break;
            }
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            String stepTag = tag + "-" + (decisions++);
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, stepTag);
                case "declare_attacker" -> {
                    if (!pn.equals(actor)) {
                        XmageFullGameTaxExecutionTest.submit(session, stepTag,
                                XmageNativeStateRestorationTest.singleActionOfType(
                                        legal, "declare_attackers", "hold_attacker"));
                        continue;
                    }
                    String attacker = null;
                    Set<String> defenders = new TreeSet<>();
                    JsonObject atP1 = null;
                    JsonObject atP2 = null;
                    for (JsonElement e : legal.getAsJsonArray("actions")) {
                        JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        attacker = meta.get("name").getAsString();
                        if (!meta.has("defender_id")) {
                            continue;
                        }
                        String defender = meta.get("defender_id").getAsString();
                        defenders.add(pidOf(started, defender));
                        if (p1.toString().equals(defender)) {
                            atP1 = e.getAsJsonObject();
                        } else if (p2.toString().equals(defender)) {
                            atP2 = e.getAsJsonObject();
                        }
                    }
                    offeredDefenders.put(attacker, defenders);
                    JsonObject pick = atP1 != null ? atP1 : atP2;
                    chosen.put(attacker, atP1 != null ? "P1" : "P2");
                    XmageFullGameTaxExecutionTest.submit(session, stepTag, pick);
                }
                case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, stepTag);
                case "choose_object" -> {
                    assertEquals(PhaseStep.CLEANUP, game.getStep().getType(), "only cleanup discards");
                    XmageActualCardCorpusTest.chooseNamed(started, stepTag, "Mountain",
                            session.pendingDecisionPayload().getAsJsonObject("decision")
                                    .get("minimum_selections").getAsInt());
                }
                default -> fail("unexpected " + cls + " for " + actor);
            }
        }
        // attackers are asked in a stable (name) order
        assertEquals(List.of("Grizzly Bears", "Raging Goblin", "Runeclaw Bear"),
                new ArrayList<>(offeredDefenders.keySet()));
        assertTrue(offeredDefenders.get("Grizzly Bears").contains("P1"));
        assertTrue(offeredDefenders.get("Raging Goblin").contains("P1"));
        assertFalse(offeredDefenders.get("Runeclaw Bear").contains("P1"),
                "two creatures already attack P1, so P1 is no longer offered: " + offeredDefenders);
        Set<String> others = new TreeSet<>();
        for (int seat = 2; seat < playerCount; seat++) {
            others.add("P" + seat);
        }
        assertEquals(others, offeredDefenders.get("Runeclaw Bear"),
                "every other opponent is still offered");
        assertEquals(Map.of("Grizzly Bears", "P1", "Raging Goblin", "P1", "Runeclaw Bear", "P2"), chosen);
        assertEquals(40 - 2 - 1, started.seats().get("P1").getLife(), "exactly the two chosen attackers hit P1");
        assertEquals(40 - 2, started.seats().get("P2").getLife(), "Runeclaw Bear hit P2");
    }

    private static String pidOf(XmageActualCardCorpusTest.Started started, String id) {
        for (var seat : started.seats().entrySet()) {
            if (seat.getValue().getId().toString().equals(id)) {
                return seat.getKey();
            }
        }
        return id;
    }

    private static XmageNativeStateRestoration.RequestedObject bf(String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""), name, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
    }
}
