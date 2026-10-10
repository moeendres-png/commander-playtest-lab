package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06 R4 (AF05 production-lane component): principal scoping of
 * {@code get_legal_actions} on the full-game lane.
 *
 * <ul>
 *   <li>A read bound to a principal other than the pending actor is refused with
 *       {@code WRONG_ACTOR} and carries no part of the decision.</li>
 *   <li>The frame served to the pending actor names no hidden object of anyone
 *       else: no card in another player's hand and no library card of any player
 *       appears by engine id, across pregame and priority frames.</li>
 * </ul>
 */
class XmageFullGameLegalActionsPrincipalTest {

    @Test
    void anotherPrincipalIsRefusedAndTheActorsFrameHidesOthersCards() {
        XmageFullGameSession session = XmageFullGameCancelRewindTest.started("issue662-principal", 6670L);
        Game game = session.restorationGame();
        int checked = 0;
        for (int step = 0; step < 30; step++) {
            JsonObject frame = session.legalActionsPayload();
            String actor = frame.get("actor_id").getAsString();
            String other = game.getPlayers().keySet().stream()
                    .map(UUID::toString).filter(id -> !id.equals(actor)).findFirst().orElseThrow();

            JsonObject foreign = new JsonObject();
            foreign.addProperty("actor_id", other);
            XmageFullGameDecisionController.DecisionException refused = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> session.legalActionsPayload(foreign));
            assertTrue(refused.getMessage().startsWith("WRONG_ACTOR"), refused.getMessage());

            JsonObject own = new JsonObject();
            own.addProperty("actor_id", actor);
            String text = session.legalActionsPayload(own).toString();
            for (String hidden : hiddenFrom(game, UUID.fromString(actor))) {
                assertFalse(text.contains(hidden), "the actor's frame names another player's hidden card " + hidden);
            }
            checked++;
            // Declared test pilot: pass priority; any other frame takes its first option.
            JsonObject answer = "priority".equals(frame.get("decision_class").getAsString())
                    ? XmageFullGameCancelRewindTest.find(frame, "pass_priority", null)
                    : frame.getAsJsonArray("actions").get(0).getAsJsonObject();
            session.submitAction(XmageFullGameCancelRewindTest.proposal(frame, answer));
        }
        assertEquals(30, checked);
    }

    /** Engine ids of every card the actor may not see: other hands, every library. */
    private static Set<String> hiddenFrom(Game game, UUID actor) {
        Set<String> hidden = new HashSet<>();
        for (Player player : game.getPlayers().values()) {
            if (!player.getId().equals(actor)) {
                for (Card card : player.getHand().getCards(game)) {
                    hidden.add(card.getId().toString());
                }
            }
            for (Card card : player.getLibrary().getCards(game)) {
                hidden.add(card.getId().toString());
            }
        }
        return hidden;
    }
}
