package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.combat.CombatGroup;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Attack taxes in multiplayer (CR 508.1g–i), with an actual card on the
 * full-game lane.
 *
 * <p>P2 controls Ghostly Prison (Oracle: "Creatures can't attack you unless
 * their controller pays {2} for each creature they control that's attacking
 * you."). P1 attacks with two hasty Raging Goblins and has four Mountains.</p>
 *
 * <ul>
 *   <li>Split attack (one Goblin at P2, one at P3): only the Goblin attacking P2
 *       costs {2}. Both attacks stand, and exactly two Mountains are tapped.</li>
 *   <li>Both Goblins at P2: {2} each, so all four Mountains are tapped.</li>
 * </ul>
 *
 * <p>The payment must offer P1's mana abilities. XMage's getPlayable returns
 * nothing while declare attackers is in its pre-step part (a UI "silent step"
 * shortcut), and attack costs are paid exactly then. The lane therefore uses
 * the engine's own per-object usable mana abilities (as XMage's human player
 * does while paying). Before that fix the only option offered was "Cancel mana
 * payment", so no attack tax could ever be paid.</p>
 */
class XmageMultiplayerAttackTaxTest {

    private static final String GOBLIN = "Raging Goblin";
    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";

    @ParameterizedTest(name = "{0} players, second Goblin attacks {1}")
    @CsvSource({"3, P3", "4, P3", "5, P3", "6, P3", "4, P2", "5, P2"})
    void onlyCreaturesAttackingThePrisonControllerPayTheTax(int playerCount, String second) {
        String tag = "prison-" + playerCount + "p-" + second;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            objects.add(obj("P1", GOBLIN, index));
        }
        for (int index = 0; index < 4; index++) {
            objects.add(obj("P1", "Mountain", index));
        }
        objects.add(obj("P2", "Ghostly Prison", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID p1 = started.seats().get("P1").getId();
        List<UUID> defenders = List.of(started.seats().get("P2").getId(),
                started.seats().get(second).getId());

        int declared = 0;
        int taxQuestions = 0;
        boolean blockersStep = false;
        for (int step = 0; step < 80 && !blockersStep; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            JsonObject legal = started.session().legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    if (game.getStep().getType() == PhaseStep.DECLARE_BLOCKERS) {
                        blockersStep = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> XmageFullGameTaxExecutionTest.submit(started.session(),
                        tag + "-attack-" + step, attackAt(legal, defenders.get(declared++)));
                case "choose_use" -> {
                    taxQuestions++;
                    XmageActualCardCorpusTest.submit(started, tag + "-pay-tax-" + step,
                            XmageActualCardCorpusTest.labelled(started, "Yes"));
                }
                case "mana_payment" -> {
                    boolean offersMana = false;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                        String type = meta.has("option_type") ? meta.get("option_type").getAsString() : "";
                        offersMana |= "mana_ability".equals(type) || "mana_pool".equals(type);
                    }
                    assertTrue(offersMana,
                            "the attack tax payment must offer a way to pay (mana ability or pool mana), not only cancel");
                    XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-mana-" + step,
                            List.of("Mountain"), Set.of(MOUNTAIN_LABEL));
                }
                case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, tag + "-nb-" + step);
                default -> fail("unexpected decision " + cls);
            }
        }
        assertTrue(blockersStep, "combat reached declare blockers");
        int taxed = "P2".equals(second) ? 2 : 1;
        assertEquals(taxed, taxQuestions, "only creatures attacking P2 are taxed");
        int tapped = 0;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(p1)) {
            tapped += "Mountain".equals(permanent.getName()) && permanent.isTapped() ? 1 : 0;
        }
        assertEquals(2 * taxed, tapped, "{2} per creature attacking the Prison's controller");
        java.util.Map<String, Integer> attackersByDefender = new java.util.TreeMap<>();
        for (CombatGroup group : game.getCombat().getGroups()) {
            attackersByDefender.merge(XmageNativeStateRestorationTest.pidOf(started.seats(),
                    group.getDefenderId().toString()), group.getAttackers().size(), Integer::sum);
        }
        assertEquals("P2".equals(second) ? java.util.Map.of("P2", 2) : java.util.Map.of("P2", 1, second, 1),
                attackersByDefender, "both attacks stand");
    }

    private static XmageNativeStateRestoration.RequestedObject obj(String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, mage.constants.Zone.BATTLEFIELD, false);
    }

    private static JsonObject attackAt(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("defender_id")
                    && defender.toString().equals(meta.get("defender_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("attack at " + defender + " not offered: " + legal);
        return null;
    }
}
