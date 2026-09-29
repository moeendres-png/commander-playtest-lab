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
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Curses (Auras that enchant a player) with an actual card at 4P and 5P on the
 * full-game lane.
 *
 * <p>P1 casts Curse of Opulence (Oracle: "Enchant player / Whenever enchanted
 * player is attacked, create a Gold token. Each opponent attacking that player
 * does the same.") on P3. On its turn PN attacks with Grizzly Bears.</p>
 *
 * <ul>
 *   <li>The Aura's target decision offers every player.</li>
 *   <li>PN attacks the enchanted P3: P1 (the curse's controller) and PN (an
 *       opponent attacking P3) each create exactly one Gold token; nobody else
 *       does.</li>
 *   <li>PN attacks P2 instead: no Gold token is created.</li>
 * </ul>
 */
class XmageMultiplayerCurseTest {

    private static final String CURSE = "Curse of Opulence";

    @ParameterizedTest(name = "{0} players, PN attacks {1}")
    @CsvSource({"4, P3, 1", "4, P2, 0", "5, P3, 1", "5, P2, 0"})
    void curseOfOpulenceRewardsOnlyAttacksOnTheEnchantedPlayer(int playerCount, String defender,
            int expectedGold) {
        String tag = "curse-" + playerCount + "p-" + defender;
        String pn = "P" + playerCount;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-CurseOfOpulence", CURSE, "P1", "P1", mage.constants.Zone.HAND, false));
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-P1-0-Mountain", "Mountain", "P1", "P1", mage.constants.Zone.BATTLEFIELD, false));
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pn + "-0-Bears", "Grizzly Bears", pn, pn, mage.constants.Zone.BATTLEFIELD, false));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();

        Set<String> offered = new TreeSet<>();
        XmageActualCardCorpusTest.cast(started, tag + "-cast", CURSE);
        XmageActualCardCorpusTest.resolveAll(started, tag, "Mountain — {T}: Add {R}.", (cls, step) -> {
            if (!"target".equals(cls) && !"choose_object".equals(cls)) {
                return false;
            }
            JsonObject pick = null;
            for (JsonElement e : session.legalActionsPayload().getAsJsonArray("actions")) {
                JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                        .getAsJsonObject("xmage_option_metadata");
                if (meta == null || !meta.has("object_id")) {
                    continue;
                }
                String pid = pidOf(started, meta.get("object_id").getAsString());
                if (pid != null) {
                    offered.add(pid);
                    if ("P3".equals(pid)) {
                        pick = e.getAsJsonObject();
                    }
                }
            }
            assertNotNull(pick, "P3 is offered as the curse's target");
            XmageFullGameTaxExecutionTest.submit(session, tag + "-target-" + step, pick);
            return true;
        });
        Set<String> everyone = new TreeSet<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            everyone.add("P" + seat);
        }
        assertEquals(everyone, offered, "Enchant player: every player can be the target");
        Permanent curse = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> CURSE.equals(p.getName())).findFirst().orElse(null);
        assertNotNull(curse);
        assertEquals(started.seats().get("P3").getId(), curse.getAttachedTo(), "the curse enchants P3");

        UUID defenderId = started.seats().get(defender).getId();
        int decisions = 0;
        for (int guard = 0; guard < 300; guard++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            if ("priority".equals(cls) && game.getStep().getType() == PhaseStep.POSTCOMBAT_MAIN
                    && started.seats().get(pn).getId().equals(game.getActivePlayerId())
                    && game.getStack().isEmpty()) {
                break;
            }
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            String stepTag = tag + "-" + (decisions++);
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, stepTag);
                case "declare_attacker" -> {
                    JsonObject pick = null;
                    if (pn.equals(actor)) {
                        for (JsonElement e : legal.getAsJsonArray("actions")) {
                            JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                                    .getAsJsonObject("xmage_option_metadata");
                            if (meta != null && meta.has("defender_id")
                                    && defenderId.toString().equals(meta.get("defender_id").getAsString())) {
                                pick = e.getAsJsonObject();
                            }
                        }
                    }
                    XmageFullGameTaxExecutionTest.submit(session, stepTag, pick != null ? pick
                            : XmageNativeStateRestorationTest.singleActionOfType(
                                    legal, "declare_attackers", "hold_attacker"));
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
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            int expected = (pid.equals("P1") || pid.equals(pn)) ? expectedGold : 0;
            assertEquals(expected, XmageActualCardCorpusTest.onBattlefield(started, pid, "Gold Token"),
                    pid + " Gold tokens after PN attacked " + defender);
        }
    }

    private static String pidOf(XmageActualCardCorpusTest.Started started, String id) {
        for (var seat : started.seats().entrySet()) {
            if (seat.getValue().getId().toString().equals(id)) {
                return seat.getKey();
            }
        }
        return null;
    }
}
