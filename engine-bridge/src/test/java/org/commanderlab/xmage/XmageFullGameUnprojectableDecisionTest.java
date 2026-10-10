package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06 L3 (ruling fact 8): a pending decision that offers no option and
 * no numeric or joint domain cannot be answered through the generic API, so its
 * projection fails closed with a typed error. Before #662 it returned an empty
 * action list that the lane reported as {@code complete: true}.
 *
 * <p>Control: a decision with one offered option, or with a numeric domain and
 * no options, still projects.</p>
 */
class XmageFullGameUnprojectableDecisionTest {

    @Test
    void optionlessDecisionWithoutNumericDomainFailsClosed() {
        for (String decisionClass : new String[] {"choice", "target", "mulligan", "priority"}) {
            JsonObject pending = pending(decisionClass, new JsonArray(), new JsonObject());
            XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                    XmageFullGameActionProjection.ProjectionException.class,
                    () -> XmageFullGameActionProjection.project(pending),
                    decisionClass);
            assertTrue(failure.getMessage().startsWith("UNPROJECTABLE_DECISION"), failure.getMessage());
            JsonObject next = XmageFullGameSession.nextActionsPayload(pending);
            assertEquals("projection_failed", next.get("next_actions_status").getAsString());
            assertEquals(0, next.getAsJsonArray("next_actions").size());
        }
    }

    @Test
    void controlsStillProject() {
        JsonArray options = new JsonArray();
        options.add(XmageFullGameDecisionController.option(
                "k".repeat(64), "Keep opening hand", "keep", new JsonObject()));
        assertEquals(1, XmageFullGameActionProjection.project(
                pending("mulligan", options, new JsonObject())).size());

        JsonObject numeric = new JsonObject();
        numeric.addProperty("numeric_min", 0);
        numeric.addProperty("numeric_max", 3);
        assertEquals(1, XmageFullGameActionProjection.project(
                pending("amount", new JsonArray(), numeric)).size());
    }

    private static JsonObject pending(String decisionClass, JsonArray options, JsonObject context) {
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", "d".repeat(64));
        pending.addProperty("actor_id", "actor");
        pending.addProperty("decision_class", decisionClass);
        pending.addProperty("decision_offset", 7L);
        pending.addProperty("minimum_selections", options.size() == 0 ? 0 : 1);
        pending.addProperty("maximum_selections", 1);
        pending.add("legal_options", options);
        pending.add("context", context);
        return pending;
    }
}
