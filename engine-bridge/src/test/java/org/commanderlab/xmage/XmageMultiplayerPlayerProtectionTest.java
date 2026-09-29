package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Protection on a player in multiplayer (CR 702.16b/e/j), with actual cards on
 * the full-game lane.
 *
 * <p>On P1's turn, P2, the last player in the engine's turn order to get
 * priority, casts Teferi's Protection. Oracle: "Until your next turn, your life
 * total can't change and you gain protection from everything. All permanents
 * you control phase out."</p>
 *
 * <ul>
 *   <li>P2's Grizzly Bears phases out.</li>
 *   <li>P1's Lightning Bolt cannot target P2 (702.16b/j) nor the phased-out
 *       Bears, but can target P3.</li>
 *   <li>P1's Flame Rift ("4 damage to each player") changes every life total
 *       except P2's.</li>
 *   <li>P1's Raging Goblin may still attack P2: protection doesn't stop
 *       attacks. Its combat damage is prevented and P2 stays at 40.</li>
 * </ul>
 */
class XmageMultiplayerPlayerProtectionTest {

    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void aProtectedPlayerCannotBeTargetedOrDamagedButCanBeAttacked(int playerCount) {
        String tag = "teferi-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P2", "Teferi's Protection", 0));
        for (int index = 0; index < 3; index++) {
            objects.add(obj("bf", "P2", "Plains", index));
            objects.add(obj("bf", "P1", "Mountain", index));
        }
        objects.add(obj("bf", "P2", "Grizzly Bears", 0));
        objects.add(obj("bf", "P1", "Raging Goblin", 0));
        objects.add(obj("hand", "P1", "Lightning Bolt", 0));
        objects.add(obj("hand", "P1", "Flame Rift", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID p2 = started.seats().get("P2").getId();
        Permanent bears = null;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(p2)) {
            if ("Grizzly Bears".equals(permanent.getName())) {
                bears = permanent;
            }
        }
        assertNotNull(bears);
        UUID bearsId = bears.getId();

        // P1 passes; the priority round reaches P2 last, who casts Teferi's Protection.
        boolean cast = false;
        for (int step = 0; step < 40 && !cast; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            if (!"priority".equals(cls)) {
                fail("unexpected decision " + cls + " for " + actor);
            }
            if ("P2".equals(actor)) {
                XmageActualCardCorpusTest.cast(started, tag + "-teferi", "Teferi's Protection");
                cast = true;
            } else {
                XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
            }
        }
        assertTrue(cast, "P2 got priority on P1's turn");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-teferi", PLAINS_LABEL,
                XmageActualCardCorpusTest.NONE);
        assertEquals(PhaseStep.PRECOMBAT_MAIN, game.getStep().getType(), "still P1's main phase");
        assertTrue(game.getPermanent(bearsId) == null || game.getPermanent(bearsId).isPhasedIn() == false,
                "P2's Bears phased out");

        // Lightning Bolt: P2 and the phased-out Bears are not legal targets; P3 is.
        XmageActualCardCorpusTest.cast(started, tag + "-bolt", "Lightning Bolt");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-bolt", MOUNTAIN_LABEL, (cls, step) -> {
            if (!"target".equals(cls)) {
                return false;
            }
            Set<String> offered = new java.util.HashSet<>();
            for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
                JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                        .getAsJsonObject("xmage_option_metadata");
                if (meta != null && meta.has("object_id")) {
                    offered.add(meta.get("object_id").getAsString());
                }
            }
            assertFalse(offered.contains(p2.toString()), "702.16j: P2 cannot be targeted");
            assertFalse(offered.contains(bearsId.toString()), "a phased-out permanent cannot be targeted");
            XmageActualCardCorpusTest.submit(started, tag + "-bolt-target",
                    XmageActualCardCorpusTest.playerTarget(started, "P3"));
            return true;
        });
        assertEquals(37, started.seats().get("P3").getLife());

        // Flame Rift: everyone but P2 takes 4.
        XmageActualCardCorpusTest.cast(started, tag + "-rift", "Flame Rift");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-rift", MOUNTAIN_LABEL,
                XmageActualCardCorpusTest.NONE);
        assertEquals(40, started.seats().get("P2").getLife(), "P2's life total can't change");
        assertEquals(36, started.seats().get("P1").getLife());
        assertEquals(33, started.seats().get("P3").getLife());
        for (int seat = 4; seat <= playerCount; seat++) {
            assertEquals(36, started.seats().get("P" + seat).getLife());
        }

        // Combat: the Goblin may attack P2 (protection doesn't stop attacks); no damage.
        boolean attacked = false;
        for (int step = 0; step < 60; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            if ("priority".equals(cls) && game.getStep().getType() == PhaseStep.END_COMBAT) {
                break;
            }
            JsonObject legal = started.session().legalActionsPayload();
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-cpass-" + step);
                case "declare_attacker" -> {
                    JsonObject atP2 = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        if (meta != null && meta.has("defender_id")
                                && p2.toString().equals(meta.get("defender_id").getAsString())) {
                            atP2 = element.getAsJsonObject();
                        }
                    }
                    assertNotNull(atP2, "a player with protection can still be attacked: " + legal);
                    XmageFullGameTaxExecutionTest.submit(started.session(), tag + "-attack", atP2);
                    attacked = true;
                }
                case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, tag + "-nb-" + step);
                default -> fail("unexpected decision " + cls);
            }
        }
        assertTrue(attacked, "the Goblin attacked P2");
        assertEquals(40, started.seats().get("P2").getLife(), "702.16e: the combat damage is prevented");
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}
