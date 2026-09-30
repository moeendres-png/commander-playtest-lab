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
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Triggers on one opponent attacking another, at 3–6 players, with actual cards
 * on the full-game lane.
 *
 * <p>P1 controls Karazikar, the Eye Tyrant (Oracle, second ability: "Whenever an
 * opponent attacks another one of your opponents, you and the attacking player
 * each draw a card and lose 1 life.") and Edric, Spymaster of Trest ("Whenever
 * a creature deals combat damage to one of your opponents, its controller may
 * draw a card.").</p>
 *
 * <p>On turn 2, P2's turn, P2 attacks P1 with Grizzly Bears, and P3 with Hill
 * Giant and Raging Goblin.</p>
 *
 * <ul>
 *   <li>Karazikar triggers exactly once. It triggers per attacked player, not per
 *       attacking creature, and not for the attack on P1 itself. P1 and P2 each
 *       draw one card and lose 1 life.</li>
 *   <li>Edric triggers twice, once for each creature that damaged P3, and not
 *       for the Bears that damaged P1. Each "may draw" is P2's decision, not
 *       Edric's controller's. P2 accepts the first and declines the second, so P2
 *       draws exactly one card from Edric.</li>
 * </ul>
 */
class XmageMultiplayerThirdPartyCombatTest {

    private static final String KARAZIKAR = "Karazikar, the Eye Tyrant";
    private static final String EDRIC = "Edric, Spymaster of Trest";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void anOpponentAttackingAnotherOpponentTriggersPerDefenderAndPerDamagingCreature(int playerCount) {
        String tag = "third-party-" + playerCount + "p";
        String attackerPid = "P2";
        String victim = "P3";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", KARAZIKAR));
        objects.add(obj("P1", EDRIC));
        objects.add(obj(attackerPid, "Grizzly Bears"));
        objects.add(obj(attackerPid, "Hill Giant"));
        objects.add(obj(attackerPid, "Raging Goblin"));
        Map<String, String> attackAt = Map.of("Grizzly Bears", "P1", "Hill Giant", victim, "Raging Goblin", victim);
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));

        Map<String, Integer> handAtAttack = new LinkedHashMap<>();
        List<String> edricAnswers = new ArrayList<>();
        int karazikarResolutions = 0;
        for (int step = 0; step < 400; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            PhaseStep phaseStep = game.getStep().getType();
            if (game.getTurnNum() == 2 && phaseStep == PhaseStep.END_COMBAT) {
                break;
            }
            JsonObject legal = started.session().legalActionsPayload();
            String prompt = started.session().pendingDecisionPayload().getAsJsonObject("decision")
                    .get("prompt").getAsString();
            switch (cls) {
                case "priority" -> {
                    if (game.getTurnNum() == 2 && phaseStep == PhaseStep.DECLARE_ATTACKERS
                            && !game.getStack().isEmpty()) {
                        karazikarResolutions = Math.max(karazikarResolutions, countOnStack(game, KARAZIKAR));
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> {
                    String attacker = attackerName(legal);
                    if (game.getTurnNum() == 1) {
                        assertEquals("P1", actor);
                        XmageActualCardCorpusTest.submit(started, tag + "-hold-" + step,
                                XmageActualCardCorpusTest.labelled(started, "Do not attack"));
                    } else {
                        assertEquals(attackerPid, actor);
                        if (handAtAttack.isEmpty()) {
                            started.seats().forEach((pid, player) -> handAtAttack.put(pid, player.getHand().size()));
                        }
                        XmageActualCardCorpusTest.submit(started, tag + "-attack-" + step,
                                attackOption(legal, ids.get(attackAt.get(attacker))));
                    }
                }
                case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + step);
                case "trigger_order" -> {
                    // Two identical Edric triggers: an explicit, id-scripted order.
                    JsonObject first = null;
                    String firstId = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                        assertTrue(meta.get("label").getAsString().startsWith(EDRIC), meta.get("label").getAsString());
                        String optionId = meta.get("option_id").getAsString();
                        if (firstId == null || optionId.compareTo(firstId) < 0) {
                            firstId = optionId;
                            first = element.getAsJsonObject();
                        }
                    }
                    XmageActualCardCorpusTest.submit(started, tag + "-order-" + step, first);
                }
                case "choose_use" -> {
                    assertEquals(2, game.getTurnNum());
                    assertEquals("Use draw effect?", prompt);
                    assertEquals(attackerPid, actor, "Edric: the damaging creature's controller decides");
                    boolean accept = edricAnswers.isEmpty();
                    edricAnswers.add(actor + (accept ? ":yes" : ":no"));
                    XmageActualCardCorpusTest.submit(started, tag + "-edric-" + step,
                            booleanOption(legal, accept));
                }
                case "choose_object" -> {
                    assertEquals(PhaseStep.CLEANUP, phaseStep);
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-discard-" + step, "Mountain", 1);
                }
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at " + phaseStep
                        + " prompt=" + prompt);
            }
        }
        assertEquals(2, game.getTurnNum());
        assertEquals(PhaseStep.END_COMBAT, game.getStep().getType());
        assertEquals(1, karazikarResolutions, "Karazikar: one trigger for the one other opponent attacked");
        assertEquals(List.of(attackerPid + ":yes", attackerPid + ":no"), edricAnswers,
                "Edric: one may-draw per creature that damaged an opponent of P1, asked to its controller");

        Map<String, Integer> life = new LinkedHashMap<>();
        Map<String, Integer> drawn = new LinkedHashMap<>();
        for (String pid : ids.keySet()) {
            life.put(pid, started.seats().get(pid).getLife());
            drawn.put(pid, started.seats().get(pid).getHand().size() - handAtAttack.get(pid));
        }
        Map<String, Integer> expectedLife = new LinkedHashMap<>();
        Map<String, Integer> expectedDrawn = new LinkedHashMap<>();
        for (String pid : ids.keySet()) {
            expectedLife.put(pid, 40);
            expectedDrawn.put(pid, 0);
        }
        expectedLife.put("P1", 40 - 2 - 1);
        expectedLife.put(attackerPid, 40 - 1);
        expectedLife.put(victim, 40 - 3 - 1);
        expectedDrawn.put("P1", 1);
        expectedDrawn.put(attackerPid, 2);
        assertEquals(expectedLife, life, "combat damage plus Karazikar's life loss for P1 and P2");
        assertEquals(expectedDrawn, drawn, "Karazikar: P1 and P2 draw one; Edric: P2 draws one (accepted once)");
    }

    private static int countOnStack(Game game, String sourceName) {
        int count = 0;
        for (mage.game.stack.StackObject object : game.getStack()) {
            if (sourceName.equals(object.getName())
                    || object.getStackAbility() != null && game.getObject(object.getSourceId()) != null
                    && sourceName.equals(game.getObject(object.getSourceId()).getName())) {
                count++;
            }
        }
        return count;
    }

    private static JsonObject booleanOption(JsonObject legal, boolean value) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            String label = meta.get("label").getAsString();
            if (value ? "Yes".equals(label) : "No".equals(label)) {
                return element.getAsJsonObject();
            }
        }
        fail("no " + value + " option: " + legal);
        return null;
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
            if (meta.has("defender_id") && defender.toString().equals(meta.get("defender_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("attack at " + defender + " not offered: " + legal);
        return null;
    }

    private static XmageNativeStateRestoration.RequestedObject obj(String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, mage.constants.Zone.BATTLEFIELD, false);
    }
}
