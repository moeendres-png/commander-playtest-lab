package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Opponent-driven triggers whose choices and results belong to a player other
 * than the trigger's controller, at 3–6 players on the full-game lane.
 *
 * <p>Turns run in seat order (F-41), so the turn after P1's is P2's.</p>
 *
 * <ul>
 *   <li>Smothering Tithe (P1). Oracle: "Whenever an opponent draws a card, that
 *       player may pay {2}. If the player doesn't, you create a Treasure token."
 *       In P2's draw step, P2 (now active) is the one asked, through the external
 *       surface. If P2 pays, no Treasure; if P2 declines, P1 gets exactly one
 *       Treasure.</li>
 *   <li>Curse of Opulence (P1, cast on PN). Oracle: "Whenever enchanted player
 *       is attacked, create a Gold token. Each opponent attacking that player does
 *       the same." When P2 attacks PN, the curse's controller P1 and the attacking
 *       opponent P2 each get one Gold, and nobody else does.</li>
 * </ul>
 */
class XmageMultiplayerOpponentTriggerTest {

    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";

    @ParameterizedTest(name = "{0} players, next player pays: {1}")
    @CsvSource({"4, true", "4, false", "5, true", "5, false"})
    void theDrawingOpponentDecidesSmotheringTithe(int playerCount, boolean pays) {
        String tag = "tithe-" + playerCount + "p-" + pays;
        String next = "P2";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // Cast, not restored: a pre-placed Tithe would see the opening-hand draws
        // during arrival (restoration finding F-15).
        objects.add(obj("hand", "P1", "Smothering Tithe", 0));
        for (int index = 0; index < 4; index++) {
            objects.add(obj("bf", "P1", "Plains", index));
        }
        objects.add(obj("bf", next, "Mountain", 0));
        objects.add(obj("bf", next, "Mountain", 1));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID nextId = started.seats().get(next).getId();
        XmageActualCardCorpusTest.cast(started, tag + "-cast", "Smothering Tithe");
        XmageActualCardCorpusTest.resolveAll(started, tag, PLAINS_LABEL, XmageActualCardCorpusTest.NONE);
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Smothering Tithe"));

        List<String> asks = new ArrayList<>();
        for (int step = 0; step < 200; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            if ("priority".equals(cls) && nextId.equals(game.getActivePlayerId())
                    && game.getStep().getType() == PhaseStep.PRECOMBAT_MAIN) {
                break;
            }
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "choose_use" -> {
                    String prompt = prompt(started);
                    assertTrue(prompt.contains("pay {2}"), "Tithe payment question: " + prompt);
                    asks.add(actor);
                    XmageActualCardCorpusTest.submit(started, tag + "-use-" + step,
                            XmageActualCardCorpusTest.labelled(started, pays ? "Yes" : "No"));
                }
                case "mana_payment" -> {
                    assertEquals(next, actor, "only the drawing opponent pays");
                    XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-pay-" + step,
                            List.of("Mountain"), Set.of(MOUNTAIN_LABEL));
                }
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(started,
                        tag + "-discard-" + step, "Mountain", minimum(started));
                default -> fail("unexpected decision " + cls + " for " + actor);
            }
        }
        assertEquals(List.of(next), asks, "only " + next + ", the opponent who drew, is asked");
        assertEquals(pays ? 0 : 1, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Treasure Token"),
                pays ? "paid: no Treasure" : "declined: P1 creates one Treasure");
        for (int seat = 2; seat <= playerCount; seat++) {
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, "P" + seat, "Treasure Token"));
        }
        int tapped = 0;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(nextId)) {
            tapped += "Mountain".equals(permanent.getName()) && permanent.isTapped() ? 1 : 0;
        }
        assertEquals(pays ? 2 : 0, tapped, next + " paid {2} only if they chose to");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void anotherOpponentAttackingTheCursedPlayerAlsoGetsGold(int playerCount) {
        String tag = "opulence-" + playerCount + "p";
        String next = "P2";
        String cursed = "P" + playerCount;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", "Curse of Opulence", 0));
        objects.add(obj("bf", "P1", "Mountain", 0));
        objects.add(obj("bf", next, "Grizzly Bears", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID cursedId = started.seats().get(cursed).getId();
        UUID nextId = started.seats().get(next).getId();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", "Curse of Opulence");
        XmageActualCardCorpusTest.resolveAll(started, tag, MOUNTAIN_LABEL, (cls, step) -> {
            if (!"target".equals(cls)) {
                return false;
            }
            XmageActualCardCorpusTest.submit(started, tag + "-enchant",
                    XmageActualCardCorpusTest.playerTarget(started, cursed));
            return true;
        });
        Permanent curse = null;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents()) {
            if ("Curse of Opulence".equals(permanent.getName())) {
                curse = permanent;
            }
        }
        assertNotNull(curse, "the Curse resolved");
        assertEquals(cursedId, curse.getAttachedTo(), "it enchants " + cursed);

        boolean attacked = false;
        for (int step = 0; step < 300; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            if (attacked && "priority".equals(cls)
                    && game.getStep().getType() == PhaseStep.DECLARE_ATTACKERS
                    && game.getStack().isEmpty()) {
                break;
            }
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "declare_attacker" -> {
                    assertEquals(next, actor, "only " + next + " has a creature");
                    XmageFullGameTaxExecutionTest.submit(started.session(), tag + "-attack", attackAt(legal, cursedId));
                    attacked = true;
                }
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(started,
                        tag + "-discard-" + step, "Mountain", minimum(started));
                default -> fail("unexpected decision " + cls + " for " + actor);
            }
        }
        assertTrue(attacked, next + " attacked " + cursed);
        assertEquals(nextId, game.getActivePlayerId());
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Gold Token"),
                "the Curse's controller creates a Gold");
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, next, "Gold Token"),
                "the opponent attacking " + cursed + " does the same");
        for (int seat = 3; seat <= playerCount; seat++) {
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, "P" + seat, "Gold Token"),
                    "P" + seat + " did not attack " + cursed);
        }
    }

    private static String prompt(XmageActualCardCorpusTest.Started started) {
        return started.session().pendingDecisionPayload().getAsJsonObject("decision")
                .get("prompt").getAsString().toLowerCase(Locale.ROOT);
    }

    private static int minimum(XmageActualCardCorpusTest.Started started) {
        return Math.max(1, started.session().pendingDecisionPayload().getAsJsonObject("decision")
                .get("minimum_selections").getAsInt());
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

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}
