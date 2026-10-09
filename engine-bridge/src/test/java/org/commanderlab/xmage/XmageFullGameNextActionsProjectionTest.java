package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * R21 negative regression for Coordinator Finding A: an unprojectable
 * <em>existing</em> next decision must stay observationally distinct from
 * no offered next actions (no silent empty-array success).
 *
 * <p>Runs without an engine: {@link XmageFullGameSession#nextActionsPayload}
 * is the exact fragment {@code submitAction} attaches after the native
 * action already executed (no rollback implied by any status here).</p>
 */
class XmageFullGameNextActionsProjectionTest {

    @Test
    void nullNextDecisionReportsNoPendingDecision() {
        JsonObject fragment = XmageFullGameSession.nextActionsPayload(null);
        assertEquals(0, fragment.getAsJsonArray("next_actions").size());
        assertEquals("no_pending_decision", fragment.get("next_actions_status").getAsString());
        assertFalse(fragment.has("next_actions_projection_error"));
    }

    @Test
    void malformedNextDecisionReportsProjectionFailed() {
        JsonObject malformed = new JsonObject();
        malformed.addProperty("decision_id", "negative-malformed");
        malformed.addProperty("actor_id", "actor-1");
        // decision_class missing -> projector throws, must not become silent [].
        JsonObject fragment = XmageFullGameSession.nextActionsPayload(malformed);
        assertEquals(0, fragment.getAsJsonArray("next_actions").size());
        assertEquals("projection_failed", fragment.get("next_actions_status").getAsString());
        assertTrue(fragment.has("next_actions_projection_error"));
        assertTrue(fragment.get("next_actions_projection_error").getAsString()
                .contains("decision_class"));
    }

    @Test
    void blankDecisionClassReportsProjectionFailed() {
        JsonObject malformed = new JsonObject();
        malformed.addProperty("decision_id", "negative-blank");
        malformed.addProperty("actor_id", "actor-1");
        malformed.addProperty("decision_class", "   ");
        JsonObject fragment = XmageFullGameSession.nextActionsPayload(malformed);
        assertEquals("projection_failed", fragment.get("next_actions_status").getAsString());
        assertTrue(fragment.has("next_actions_projection_error"));
    }

    @Test
    void optionlessNextDecisionReportsProjectionFailed() {
        // #662 SLOT-06 L3 (fact 8): no options and no numeric domain is not
        // "complete, nothing to do"; it cannot be answered and fails closed.
        JsonObject minimal = new JsonObject();
        minimal.addProperty("decision_id", "negative-minimal");
        minimal.addProperty("actor_id", "actor-1");
        minimal.addProperty("decision_class", "mulligan");
        minimal.add("legal_options", new JsonArray());
        JsonObject fragment = XmageFullGameSession.nextActionsPayload(minimal);
        assertEquals(0, fragment.getAsJsonArray("next_actions").size());
        assertEquals("projection_failed", fragment.get("next_actions_status").getAsString());
        assertTrue(fragment.get("next_actions_projection_error").getAsString()
                .startsWith("UNPROJECTABLE_DECISION"));
    }

    @Test
    void projectableNextDecisionReportsProjected() {
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", "d".repeat(64));
        pending.addProperty("actor_id", "actor-1");
        pending.addProperty("decision_class", "mulligan");
        pending.addProperty("minimum_selections", 1);
        pending.addProperty("maximum_selections", 1);
        JsonArray options = new JsonArray();
        options.add(XmageFullGameDecisionController.option("k".repeat(64), "Keep opening hand", "keep", new JsonObject()));
        pending.add("legal_options", options);
        JsonObject fragment = XmageFullGameSession.nextActionsPayload(pending);
        assertEquals(1, fragment.getAsJsonArray("next_actions").size());
        assertEquals("projected", fragment.get("next_actions_status").getAsString());
        assertFalse(fragment.has("next_actions_projection_error"));
    }
}
