package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * A card-name choice (Sorcerous Spyglass, Pithing Needle, ...) offers every card name. Each
 * projected action carries its own choices_schema; inlining all option ids into each of them
 * was quadratic and exhausted an 8 GB heap. Small decisions keep the inlined ids unchanged.
 */
class XmageFullGameLargeChoiceProjectionTest {

    private static JsonObject pending(int optionCount) {
        JsonArray options = new JsonArray();
        for (int i = 0; i < optionCount; i++) {
            options.add(XmageFullGameDecisionController.option(
                    String.format("%064d", i), "Card name " + i, "choice", new JsonObject()));
        }
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", "d".repeat(64));
        pending.addProperty("actor_id", "actor");
        pending.addProperty("decision_class", "choice");
        pending.addProperty("decision_offset", 7L);
        pending.addProperty("minimum_selections", 1);
        pending.addProperty("maximum_selections", 1);
        pending.add("legal_options", options);
        pending.add("context", new JsonObject());
        return pending;
    }

    @Test
    void largeChoiceProjectsEveryOptionWithoutInliningAllIds() {
        int count = 30_000;
        JsonArray actions = XmageFullGameActionProjection.project(pending(count));
        assertEquals(count, actions.size());
        JsonObject schema = actions.get(0).getAsJsonObject().getAsJsonObject("choices_schema");
        assertEquals(count, schema.get("available_option_count").getAsInt());
        assertFalse(schema.has("available_option_ids"));
    }

    @Test
    void smallChoiceKeepsInlinedIds() {
        int count = XmageFullGameActionProjection.AVAILABLE_IDS_INLINE_LIMIT;
        JsonArray actions = XmageFullGameActionProjection.project(pending(count));
        JsonObject schema = actions.get(0).getAsJsonObject().getAsJsonObject("choices_schema");
        assertTrue(schema.has("available_option_ids"));
        assertEquals(count, schema.getAsJsonArray("available_option_ids").size());
        assertEquals(count, schema.get("available_option_count").getAsInt());
    }
}
