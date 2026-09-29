package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.combat.CombatGroup;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * CR 802.2a with an actual card at 3–6 players on the full-game lane:
 * "defending player" in an attacking creature's ability means the player
 * that creature attacks, not every defending player.
 *
 * <p>Impetuous Devils (Oracle: "Trample, haste / When this creature attacks,
 * up to one target creature defending player controls blocks it this combat
 * if able."). P1's Devils attacks P3 and Raging Goblin attacks P2, so P2 is a
 * defending player too; every opponent controls a Grizzly Bears.</p>
 *
 * <ul>
 *   <li>The trigger's targets are exactly P3's Bears.</li>
 *   <li>Once that Bears is targeted, CR 509.1c requires it to block the Devils
 *       if able. It can block nothing else, so that block is P3's only legal
 *       declaration. XMage applies it itself
 *       ({@code Combat.retrieveMustBlockAttackerRequirements}) and does not ask
 *       P3. P2 is still asked about the Goblin.</li>
 * </ul>
 */
class XmageMultiplayerDefendingPlayerTest {

    private static final String DEVILS = "Impetuous Devils";
    private static final String GOBLIN = "Raging Goblin";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void defendingPlayerMeansThePlayerThatCreatureAttacks(int playerCount) {
        String tag = "devils-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(bf("P1", DEVILS));
        objects.add(bf("P1", GOBLIN));
        for (int seat = 2; seat <= playerCount; seat++) {
            objects.add(bf("P" + seat, BEARS));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        UUID p2 = started.seats().get("P2").getId();
        UUID p3 = started.seats().get("P3").getId();
        Permanent p3Bears = only(game, p3, BEARS);
        Permanent devils = only(game, started.seats().get("P1").getId(), DEVILS);

        List<String> targetOwners = null;
        List<String> askedToBlock = new ArrayList<>();
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
                            attackOption(legal, DEVILS.equals(attacker) ? p3 : p2));
                }
                case "target" -> {
                    assertEquals("P1", actor, "the Devils' controller chooses the target");
                    assertTrue(targetOwners == null, "one targeting decision");
                    targetOwners = new ArrayList<>();
                    JsonObject pick = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        if (meta == null || !meta.has("object_id")) {
                            continue;
                        }
                        Permanent option = game.getPermanent(
                                UUID.fromString(meta.get("object_id").getAsString()));
                        assertNotNull(option, "targets are permanents");
                        targetOwners.add(XmageNativeStateRestorationTest.pidOf(
                                started.seats(), option.getControllerId().toString())
                                + ":" + option.getName());
                        if (option.getId().equals(p3Bears.getId())) {
                            pick = element.getAsJsonObject();
                        }
                    }
                    assertNotNull(pick, "P3's Bears must be a legal target: " + legal);
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-target-" + step, pick);
                }
                case "declare_blocker" -> {
                    askedToBlock.add(actor);
                    XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + step);
                }
                default -> fail("unexpected decision " + cls + " for " + actor + ": " + legal);
            }
        }
        assertTrue(blocksDeclared, "combat reached declare blockers");
        assertEquals(List.of("P3:" + BEARS), targetOwners,
                "CR 802.2a: only creatures of the player the Devils attack are targets");
        CombatGroup group = game.getCombat().findGroup(devils.getId());
        assertNotNull(group, "the Devils attack");
        assertEquals(p3, group.getDefendingPlayerId());
        assertEquals(List.of(p3Bears.getId()), group.getBlockers(),
                "P3's targeted Bears blocks the Devils");
        assertEquals(List.of("P2"), askedToBlock,
                "P3's only legal declaration is the required block, which the engine "
                        + "applies itself (509.1c); P2 is still asked; no one else is attacked");
    }

    private static XmageNativeStateRestoration.RequestedObject bf(String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""), name, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
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
}
