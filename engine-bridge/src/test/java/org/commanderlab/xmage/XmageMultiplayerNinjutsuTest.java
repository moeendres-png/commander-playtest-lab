package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
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
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Ninjutsu in a split attack at 3–6 players, with actual cards on the full-game
 * lane (CR 702.49a/c).
 *
 * <p>P1 attacks P2 with Raging Goblin and P3 with Grizzly Bears. Every opponent
 * controls a Wall of Stone. P2 blocks the Goblin and P3 does not block. In the
 * declare blockers step, P1 activates the ninjutsu ability of Ninja of the
 * Deep Hours (Oracle: "Ninjutsu {1}{U}. Whenever this creature deals combat
 * damage to a player, you may draw a card.").</p>
 *
 * <ul>
 *   <li>Only defending players with an attacker on them are asked to block.</li>
 *   <li>The ninjutsu cost offers only the unblocked attacker, the Bears.</li>
 *   <li>The Ninja enters tapped and attacking the same player the Bears was
 *       attacking, P3, and is unblocked. It deals 2 to P3 and draws P1 a card.
 *       Nobody else takes damage.</li>
 * </ul>
 */
class XmageMultiplayerNinjutsuTest {

    private static final String NINJA = "Ninja of the Deep Hours";
    private static final String GOBLIN = "Raging Goblin";
    private static final String BEARS = "Grizzly Bears";
    private static final String WALL = "Wall of Stone";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void theNinjaAttacksThePlayerTheReturnedCreatureWasAttacking(int playerCount) {
        String tag = "ninjutsu-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", NINJA, 0));
        objects.add(obj("bf", "P1", "Island", 0));
        objects.add(obj("bf", "P1", "Island", 1));
        objects.add(obj("bf", "P1", GOBLIN, 0));
        objects.add(obj("bf", "P1", BEARS, 0));
        for (int seat = 2; seat <= playerCount; seat++) {
            objects.add(obj("bf", "P" + seat, WALL, 0));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));
        Map<String, String> attackAt = Map.of(GOBLIN, "P2", BEARS, "P3");

        List<String> askedToBlock = new ArrayList<>();
        boolean activated = false;
        List<String> returnOffers = null;
        int handBeforeDamage = -1;
        int mayDraw = 0;
        for (int step = 0; step < 200 && game.getStep().getType() != PhaseStep.END_COMBAT; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            PhaseStep phaseStep = game.getStep().getType();
            switch (cls) {
                case "priority" -> {
                    if (!activated && "P1".equals(actor) && phaseStep == PhaseStep.DECLARE_BLOCKERS) {
                        activated = true;
                        XmageActualCardCorpusTest.submit(started, tag + "-ninjutsu",
                                XmageActualCardCorpusTest.labelled(started, NINJA + " — Ninjutsu"));
                    } else {
                        XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                    }
                }
                case "declare_attacker" -> {
                    String attacker = attackerName(legal);
                    XmageActualCardCorpusTest.submit(started, tag + "-attack-" + attacker,
                            attackOption(legal, ids.get(attackAt.get(attacker))));
                }
                case "declare_blocker" -> {
                    askedToBlock.add(actor);
                    if ("P2".equals(actor)) {
                        XmageActualCardCorpusTest.submit(started, tag + "-block",
                                XmageActualCardCorpusTest.labelled(started, WALL + " blocks " + GOBLIN));
                    } else {
                        XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + actor);
                    }
                }
                case "target", "choose_object" -> {
                    assertEquals("P1", actor);
                    returnOffers = new ArrayList<>();
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        returnOffers.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
                    }
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-return", BEARS, 1);
                }
                case "choose_use" -> {
                    assertEquals("P1", actor);
                    assertEquals(PhaseStep.COMBAT_DAMAGE, phaseStep, "the Ninja's may-draw after damage to P3");
                    mayDraw++;
                    XmageActualCardCorpusTest.submit(started, tag + "-draw", XmageActualCardCorpusTest.labelled(started, "Yes"));
                }
                case "mana_payment" -> XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-pay-" + step,
                        List.of("Island"), java.util.Set.of("Island — {T}: Add {U}."));
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at " + phaseStep);
            }
            if (activated && phaseStep == PhaseStep.DECLARE_BLOCKERS && game.getStack().isEmpty()
                    && onBattlefield(game, ids.get("P1"), NINJA) != null && handBeforeDamage == -1) {
                Permanent ninja = onBattlefield(game, ids.get("P1"), NINJA);
                assertTrue(ninja.isAttacking() && ninja.isTapped(), "the Ninja enters tapped and attacking");
                assertEquals(ids.get("P3"), game.getCombat().getDefenderId(ninja.getId()),
                        "the Ninja attacks the player the returned Bears was attacking");
                assertFalse(game.getCombat().findGroup(ninja.getId()).getBlocked(), "the Ninja is unblocked");
                handBeforeDamage = started.seats().get("P1").getHand().size();
            }
        }
        assertEquals(List.of("P2", "P3"), askedToBlock.stream().sorted().toList(),
                "only the attacked players are asked to block");
        assertNotNull(returnOffers, "ninjutsu was activated and its cost chosen");
        assertEquals(List.of(BEARS), returnOffers, "only the unblocked attacker can be returned");
        assertTrue(handBeforeDamage >= 0, "Ninja snapshot taken before damage");
        assertEquals(1, mayDraw, "one combat-damage trigger (to P3)");
        assertEquals(1, started.seats().get("P1").getHand().getCards(game).stream()
                .filter(card -> BEARS.equals(card.getName())).count(), "the Bears returned to hand");
        assertEquals(handBeforeDamage + 1, started.seats().get("P1").getHand().size(),
                "the Ninja's combat-damage trigger drew P1 a card");
        Map<String, Integer> expected = new LinkedHashMap<>();
        ids.keySet().forEach(pid -> expected.put(pid, 40));
        expected.put("P3", 38);
        Map<String, Integer> life = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> life.put(pid, player.getLife()));
        assertEquals(expected, life, "only P3 takes damage (the Goblin was blocked)");
    }

    private static Permanent onBattlefield(Game game, UUID controller, String name) {
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(controller)) {
            if (name.equals(permanent.getName())) {
                return permanent;
            }
        }
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

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}
