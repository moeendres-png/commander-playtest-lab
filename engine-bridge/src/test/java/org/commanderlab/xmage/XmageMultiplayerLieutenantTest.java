package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
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
 * Lieutenant (a Commander mechanic) combined with "defending player" targeting
 * (CR 802.2a) at 3–6 players, with an actual card on the full-game lane.
 *
 * <p>P1's Tyrant's Familiar (Oracle: "Flying, haste. Lieutenant — As long as you
 * control your commander, this creature gets +2/+2 and has 'Whenever this
 * creature attacks, it deals 7 damage to target creature defending player
 * controls.'") attacks P3. P2 and P3 each control a Hill Giant.</p>
 *
 * <ul>
 *   <li>With P1's commander (Rograkh, cast first) on the battlefield: the
 *       Familiar is 7/7, and its attack trigger is offered exactly P3's Hill
 *       Giant, not P2's and not P1's own commander. The Giant dies and P3 takes
 *       7.</li>
 *   <li>Without the commander: the Familiar is 5/5, nothing triggers, and P3
 *       takes 5.</li>
 * </ul>
 */
class XmageMultiplayerLieutenantTest {

    private static final String FAMILIAR = "Tyrant's Familiar";
    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    @ParameterizedTest(name = "{0} players, commander on battlefield: {1}")
    @CsvSource({"3, true", "3, false", "4, true", "4, false", "5, true", "5, false", "6, true", "6, false"})
    void lieutenantDependsOnTheCommanderAndTargetsTheDefendingPlayersCreature(
            int playerCount, boolean commanderOut) {
        String tag = "lieutenant-" + playerCount + "p-" + commanderOut;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", FAMILIAR));
        objects.add(obj("P2", "Hill Giant"));
        objects.add(obj("P3", "Hill Giant"));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID p3 = started.seats().get("P3").getId();
        UUID p3Giant = only(game, p3, "Hill Giant").getId();

        if (commanderOut) {
            XmageActualCardCorpusTest.cast(started, tag + "-rograkh", ROGRAKH);
            XmageActualCardCorpusTest.resolveAll(started, tag + "-rograkh", null, XmageActualCardCorpusTest.NONE);
            assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", ROGRAKH));
        }
        Permanent familiar = only(game, started.seats().get("P1").getId(), FAMILIAR);
        assertEquals(commanderOut ? 7 : 5, familiar.getPower().getValue(), "lieutenant +2/+2");

        List<String> targetOwners = new ArrayList<>();
        boolean combatDone = false;
        for (int step = 0; step < 80 && !combatDone; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            JsonObject legal = started.session().legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    if (game.getStep().getType() == PhaseStep.END_COMBAT
                            || game.getStep().getType() == PhaseStep.POSTCOMBAT_MAIN) {
                        combatDone = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> {
                    JsonObject pick = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        String name = meta == null || !meta.has("name") ? "" : meta.get("name").getAsString();
                        if (FAMILIAR.equals(name) && meta.has("defender_id")
                                && p3.toString().equals(meta.get("defender_id").getAsString())) {
                            pick = element.getAsJsonObject();
                        }
                        if (!FAMILIAR.equals(name) && pick == null && element.getAsJsonObject()
                                .getAsJsonObject("metadata").get("label").getAsString().startsWith("Do not attack")) {
                            pick = element.getAsJsonObject(); // Rograkh (0 power) holds
                        }
                    }
                    assertNotNull(pick, "attack or hold offered: " + legal);
                    XmageFullGameTaxExecutionTest.submit(started.session(), tag + "-attack-" + step, pick);
                }
                case "target" -> {
                    JsonObject giant = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        if (meta == null || !meta.has("object_id")) {
                            continue;
                        }
                        Permanent option = game.getPermanent(UUID.fromString(meta.get("object_id").getAsString()));
                        assertNotNull(option);
                        targetOwners.add(XmageNativeStateRestorationTest.pidOf(started.seats(),
                                option.getControllerId().toString()) + ":" + option.getName());
                        if (option.getId().equals(p3Giant)) {
                            giant = element.getAsJsonObject();
                        }
                    }
                    assertNotNull(giant, "P3's Giant must be targetable");
                    XmageFullGameTaxExecutionTest.submit(started.session(), tag + "-target", giant);
                }
                case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, tag + "-nb-" + step);
                default -> fail("unexpected decision " + cls);
            }
        }
        assertTrue(combatDone, "combat finished");
        if (commanderOut) {
            assertEquals(List.of("P3:Hill Giant"), targetOwners,
                    "802.2a: only creatures of the player the Familiar attacks");
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, "P3", "Hill Giant"),
                    "7 damage kills P3's Giant");
        } else {
            assertEquals(List.of(), targetOwners, "without the commander there is no trigger");
            assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P3", "Hill Giant"));
        }
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P2", "Hill Giant"));
        assertEquals(40 - (commanderOut ? 7 : 5), started.seats().get("P3").getLife(),
                "P3 takes the Familiar's combat damage");
        assertEquals(40, started.seats().get("P2").getLife());
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

    private static XmageNativeStateRestoration.RequestedObject obj(String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""), name, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
    }
}
