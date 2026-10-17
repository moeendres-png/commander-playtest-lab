package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #866: the engine's London mulligan asks for its bottom card through
 * {@code chooseTarget}, so the full-game lane must mark that decision with the
 * structured {@code bottom_of_library_selection} context (the pilot routes it
 * to its opening-hand bottom valuation); every other decision stays unmarked.
 */
class XmageLondonBottomMarkerTest {

    private static final int DECISION_LIMIT = 400;

    private static boolean marked(JsonObject legal) {
        JsonObject context = legal.getAsJsonObject("decision").getAsJsonObject("context");
        return context.has("bottom_of_library_selection")
                && context.get("bottom_of_library_selection").getAsBoolean();
    }

    private static JsonObject mulliganOption(JsonObject legal) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if ("mulligan".equals(action.get("action_type").getAsString())
                    && "mulligan".equals(metadata.get("option_type").getAsString())) {
                return action;
            }
        }
        throw new AssertionError("mulligan option missing");
    }

    /** Plays until a marked decision shows up (returns it) or the limit is hit (null). */
    private static JsonObject playUntilMarked(
            XmageFullGameSession session, int mulligansWanted, Map<String, Integer> taken) {
        for (int i = 0; i < DECISION_LIMIT; i++) {
            if (session.pendingDecisionPayload().get("decision").isJsonNull()) {
                return null;
            }
            JsonObject legal = session.legalActionsPayload();
            if (marked(legal)) {
                return legal;
            }
            String actor = legal.get("actor_id").getAsString();
            if ("mulligan".equals(legal.get("decision_class").getAsString())
                    && taken.getOrDefault(actor, 0) < mulligansWanted) {
                taken.merge(actor, 1, Integer::sum);
                session.submitAction(FullGameTestPilot.proposal(legal, mulliganOption(legal)));
                continue;
            }
            session.submitAction(FullGameTestPilot.choose(legal));
        }
        return null;
    }

    @Test
    void secondMulliganBottomChoiceIsMarkedAndOffersTheHand() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("issue866-marked", 4, 6660L);
        Map<String, Integer> taken = new HashMap<>();
        // 4 players: the first mulligan is free (no bottom), the second bottoms one card.
        JsonObject bottom = playUntilMarked(session, 2, taken);
        assertTrue(bottom != null, "no marked London bottom decision within the limit");
        assertTrue(taken.values().stream().anyMatch(count -> count == 2), taken.toString());
        JsonObject decision = bottom.getAsJsonObject("decision");
        assertEquals(1, decision.get("minimum_selections").getAsInt());
        // Seven drawn cards are offered; one goes to the bottom.
        assertEquals(7, bottom.getAsJsonArray("actions").size());
    }

    @Test
    void noMulliganMeansNoMarkedDecision() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("issue866-control", 4, 6660L);
        JsonObject bottom = playUntilMarked(session, 0, new HashMap<>());
        assertFalse(bottom != null, "a marked bottom decision appeared without any mulligan");
    }
}
