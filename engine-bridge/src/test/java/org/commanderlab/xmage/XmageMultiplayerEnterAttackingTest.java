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
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Creatures put onto the battlefield attacking, at 3–6 players, with actual
 * cards on the full-game lane (CR 508.4, 508.4c, 802.2).
 *
 * <p>P1 attacks P2 with Hero of Bladehold (Oracle: "Battle cry. Whenever Hero of
 * Bladehold attacks, create two 1/1 white Soldier creature tokens that are
 * tapped and attacking."). P3 controls Ghostly Prison ("Creatures can't attack
 * you unless their controller pays {2} for each creature they control that's
 * attacking you."). P1 has four untapped Plains.</p>
 *
 * <ul>
 *   <li>For each token, P1 chooses which defending player it attacks. Every
 *       opponent is offered, including those nobody attacked (802.2), and P1
 *       itself is not. The tokens go to P3 and PN, both to P3 at 3P.</li>
 *   <li>Ghostly Prison demands no payment for the token attacking P3, because
 *       the tokens were never declared as attackers (508.4c). P1's Plains stay
 *       untapped.</li>
 *   <li>The token trigger resolves before battle cry, so each Soldier gets +1/+0.
 *       Life totals are exact.</li>
 * </ul>
 */
class XmageMultiplayerEnterAttackingTest {

    private static final String HERO = "Hero of Bladehold";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void theControllerChoosesAnyDefendingPlayerAndAttackCostsDoNotApply(int playerCount) {
        String tag = "hero-" + playerCount + "p";
        String pn = "P" + playerCount;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", HERO, 0));
        for (int index = 0; index < 4; index++) {
            objects.add(obj("P1", "Plains", index));
        }
        objects.add(obj("P3", "Ghostly Prison", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));
        List<String> tokenDefenders = new ArrayList<>(List.of("P3", pn));

        List<String> chosen = new ArrayList<>();
        for (int step = 0; step < 200 && game.getStep().getType() != PhaseStep.END_COMBAT; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "declare_attacker" -> {
                    assertEquals("P1", actor);
                    XmageActualCardCorpusTest.submit(started, tag + "-attack",
                            XmageActualCardCorpusTest.labelled(started, HERO + " attacks "
                                    + started.seats().get("P2").getName()));
                }
                case "trigger_order" -> {
                    // Battle cry first onto the stack, so the token trigger resolves first
                    // and battle cry then pumps the Soldiers.
                    XmageActualCardCorpusTest.submit(started, tag + "-order",
                            XmageActualCardCorpusTest.labelled(started, "Battle cry"));
                }
                case "target" -> {
                    assertEquals("P1", actor, "the tokens' controller chooses what they attack");
                    List<String> offered = new ArrayList<>();
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        offered.add(XmageNativeStateRestorationTest.pidOf(started.seats(),
                                element.getAsJsonObject().getAsJsonObject("metadata")
                                        .getAsJsonObject("xmage_option_metadata").get("object_id").getAsString()));
                    }
                    List<String> opponents = new ArrayList<>(ids.keySet());
                    opponents.remove("P1");
                    assertEquals(opponents.stream().sorted().toList(), offered.stream().sorted().toList(),
                            "every opponent is a defending player (802.2), including unattacked ones");
                    String defender = tokenDefenders.get(chosen.size());
                    chosen.add(defender);
                    XmageActualCardCorpusTest.submit(started, tag + "-token-" + defender,
                            XmageActualCardCorpusTest.playerTarget(started, defender));
                }
                case "declare_blocker" -> fail("no defending player controls a creature");
                case "mana_payment" -> fail("508.4c: no attack cost applies to a creature put onto the battlefield "
                        + "attacking (Ghostly Prison asked " + actor + " to pay)");
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at " + game.getStep().getType());
            }
        }
        assertEquals(tokenDefenders, chosen, "one defender choice per token");
        int soldiers = 0;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(ids.get("P1"))) {
            if (permanent.getName().startsWith("Soldier")) {
                soldiers++;
            }
            if ("Plains".equals(permanent.getName())) {
                assertTrue(!permanent.isTapped(), "no mana was spent on an attack cost");
            }
        }
        assertEquals(2, soldiers);
        Map<String, Integer> expected = new LinkedHashMap<>();
        ids.keySet().forEach(pid -> expected.put(pid, 40));
        expected.put("P2", 40 - 3);
        for (String defender : tokenDefenders) {
            expected.merge(defender, -2, Integer::sum);
        }
        Map<String, Integer> life = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> life.put(pid, player.getLife()));
        assertEquals(expected, life, "Hero 3 to P2; each 2/1 Soldier (battle cry) to its chosen defender");
    }

    private static XmageNativeStateRestoration.RequestedObject obj(String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, mage.constants.Zone.BATTLEFIELD, false);
    }
}
