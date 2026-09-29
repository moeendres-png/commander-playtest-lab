package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Will of the council with a word vote, with an actual card at 3–6 players on
 * the full-game lane.
 *
 * <p>Plea for Power (Oracle: "Will of the council — Starting with you, each
 * player votes for time or knowledge. If time gets more votes, take an extra
 * turn after this one. If knowledge gets more votes or the vote is tied, draw
 * three cards."). P1 casts it.</p>
 *
 * <ul>
 *   <li>Every player votes once, through the external surface, starting with
 *       P1 in turn order (P1, PN, …, P2), and is offered exactly the two
 *       words.</li>
 *   <li>Time wins only with strictly more votes: then P1 takes the next turn
 *       and draws nothing from the spell; a tie or a knowledge majority draws
 *       three and the next turn is PN's.</li>
 * </ul>
 */
class XmageMultiplayerWordVoteTest {

    private static final String TIME = "Time (extra turn)";
    private static final String KNOWLEDGE = "Knowledge (draw 3 cards)";

    @ParameterizedTest(name = "{0} players, time voters {1}")
    @CsvSource({
            "3, P1, false",          // 1 time vs 2 knowledge
            "4, P1 P4, false",       // 2 vs 2: tie draws
            "5, P1 P5 P4, true",     // 3 vs 2: extra turn
            "6, P6 P5 P4 P3 P2, true"})
    void timeWinsOnlyWithMoreVotes(int playerCount, String timeVoters, boolean extraTurn) {
        Set<String> time = new TreeSet<>(Arrays.asList(timeVoters.split(" ")));
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Plea for Power", 0, Zone.HAND));
        for (int i = 0; i < 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "plea-" + playerCount + "p-" + time.size(), playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        int handBefore = s.seats.get("P1").getHand().size();

        s.submit(s.action("activate_ability", "Cast Plea for Power"));
        List<String> voters = new ArrayList<>();
        for (int i = 0; i < 80; i++) {
            String cls = s.decisionClass();
            if ("priority".equals(cls) && voters.size() == playerCount && game.getStack().isEmpty()) {
                break;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Island");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_use" -> {
                    String actor = s.actor();
                    voters.add(actor);
                    List<String> labels = s.labels();
                    assertEquals(List.of(TIME, KNOWLEDGE), labels, actor + " is offered exactly the two words");
                    String word = time.contains(actor) ? TIME : KNOWLEDGE;
                    JsonObject pick = null;
                    for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
                        if (word.equals(e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString())) {
                            pick = e.getAsJsonObject();
                        }
                    }
                    assertNotNull(pick);
                    s.submit(pick);
                }
                default -> fail("unexpected " + cls + " " + s.labels());
            }
        }
        List<String> expectedVoters = new ArrayList<>();
        expectedVoters.add("P1");
        for (int seat = playerCount; seat >= 2; seat--) {
            expectedVoters.add("P" + seat);
        }
        assertEquals(expectedVoters, voters, "starting with P1, in turn order, each player votes once");
        int handAfter = s.seats.get("P1").getHand().size();
        if (extraTurn) {
            assertEquals(handBefore - 1, handAfter, "time won: no cards drawn");
            assertEquals(1, game.getState().getTurnMods().stream().filter(m -> m.isExtraTurn()).count(),
                    "time won: exactly one extra turn is scheduled");
            assertEquals(s.seats.get("P1").getId(), game.getState().getTurnMods().stream()
                    .filter(m -> m.isExtraTurn()).findFirst().get().getPlayerId(), "the extra turn is P1's");
        } else {
            assertEquals(handBefore - 1 + 3, handAfter, "tie or knowledge: P1 drew three");
            assertEquals(0, game.getState().getTurnMods().stream().filter(m -> m.isExtraTurn()).count(),
                    "no extra turn");
        }
    }
}
