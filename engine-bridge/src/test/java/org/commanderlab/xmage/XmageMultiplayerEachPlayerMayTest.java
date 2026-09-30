package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * "Each player may …, then each opponent who didn't …" with an actual card at
 * 3–6 players on the full-game lane.
 *
 * <p>P1 controls Kynaios and Tiro of Meletis (Oracle: "At the beginning of your
 * end step, draw a card. Each player may put a land card from their hand onto
 * the battlefield, then each opponent who didn't draws a card."). Every hand
 * holds Mountains.</p>
 *
 * <ul>
 *   <li>Every player is asked, starting with P1 in turn order (P1, P2, …,
 *       PN); P1 and P3 accept, everyone else declines.</li>
 *   <li>Each accepting player is offered only land cards from their own hand:
 *       no card from another player's hidden hand.</li>
 *   <li>Exactly the opponents who declined draw one card; P3 and P1 don't draw
 *       from this clause (P1 draws one from the first sentence).</li>
 * </ul>
 */
class XmageMultiplayerEachPlayerMayTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void eachPlayerMayPutALandAndDeclinersDraw(int playerCount) {
        String tag = "kynaios-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-P1-0-KynaiosAndTiro", "Kynaios and Tiro of Meletis", "P1", "P1",
                mage.constants.Zone.BATTLEFIELD, false));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        Map<String, Integer> handBefore = new HashMap<>();
        Map<String, Integer> landsBefore = new HashMap<>();
        started.seats().forEach((pid, p) -> {
            handBefore.put(pid, p.getHand().size());
            landsBefore.put(pid, XmageActualCardCorpusTest.onBattlefield(started, pid, "Mountain"));
        });

        List<String> asked = new ArrayList<>();
        int d = 0;
        boolean resolved = false;
        for (int guard = 0; guard < 200 && !resolved; guard++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            String stepTag = tag + "-" + (d++);
            switch (cls) {
                case "priority" -> {
                    if (game.getStep().getType() == PhaseStep.END_TURN && !asked.isEmpty()
                            && game.getStack().isEmpty()) {
                        resolved = true;
                    } else {
                        XmageActualCardCorpusTest.pass(started, stepTag);
                    }
                }
                case "declare_attacker" -> XmageFullGameTaxExecutionTest.submit(session, stepTag,
                        XmageNativeStateRestorationTest.singleActionOfType(legal, "declare_attackers", "hold_attacker"));
                case "choose_use" -> {
                    asked.add(actor);
                    String answer = ("P1".equals(actor) || "P3".equals(actor)) ? "Yes" : "No";
                    JsonObject pick = null;
                    for (JsonElement e : legal.getAsJsonArray("actions")) {
                        if (answer.equals(e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString())) {
                            pick = e.getAsJsonObject();
                        }
                    }
                    assertNotNull(pick, "Yes/No offered to " + actor);
                    XmageFullGameTaxExecutionTest.submit(session, stepTag, pick);
                }
                case "target", "choose_object" -> {
                    UUID actorId = started.seats().get(actor).getId();
                    Player actorPlayer = game.getPlayer(actorId);
                    JsonObject pick = null;
                    for (JsonElement e : legal.getAsJsonArray("actions")) {
                        JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        assertNotNull(meta, "land options carry engine metadata");
                        UUID cardId = UUID.fromString(meta.get("object_id").getAsString());
                        assertTrue(actorPlayer.getHand().contains(cardId),
                                actor + " is offered only cards from their own hand");
                        pick = e.getAsJsonObject();
                    }
                    assertNotNull(pick, actor + " is offered a land");
                    XmageFullGameTaxExecutionTest.submit(session, stepTag, pick);
                }
                default -> fail("unexpected " + cls + " for " + actor);
            }
        }
        assertTrue(resolved, "the trigger resolved in P1's end step");
        List<String> expected = new ArrayList<>();
        expected.add("P1");
        for (int seat = 2; seat <= playerCount; seat++) {
            expected.add("P" + seat);
        }
        assertEquals(expected, asked, "every player may, starting with P1 in turn order");
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            boolean put = pid.equals("P1") || pid.equals("P3");
            int drew = pid.equals("P1") ? 1 : (put ? 0 : 1);
            assertEquals(handBefore.get(pid) + drew - (put ? 1 : 0),
                    started.seats().get(pid).getHand().size(), pid + " hand");
            assertEquals(landsBefore.get(pid) + (put ? 1 : 0),
                    XmageActualCardCorpusTest.onBattlefield(started, pid, "Mountain"), pid + " lands");
        }
    }
}
