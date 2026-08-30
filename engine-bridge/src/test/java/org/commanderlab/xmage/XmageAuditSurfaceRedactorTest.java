package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageAuditSurfaceRedactorTest {

    private static final String HONEYCARD = "WS22 PRIVATE HONEYCARD 7f5f1db9";

    @Test
    void durableTranscriptWhitelistDropsHoneycardPromptLabelsIdsMetadataAndFailureDetail() {
        JsonArray raw = new JsonArray();

        JsonObject requested = new JsonObject();
        requested.addProperty("sequence", 1);
        requested.addProperty("kind", "decision_requested");
        requested.addProperty("decision_class", "target");
        requested.addProperty("actor_seat", 0);
        requested.addProperty("decision_subject_seat", 0);
        requested.addProperty("prompt", "Choose " + HONEYCARD);
        requested.addProperty("public_state_reference", "actor-view:" + HONEYCARD);
        requested.addProperty("private_actor_state_reference", HONEYCARD);
        JsonArray types = new JsonArray();
        types.add("card");
        requested.add("legal_option_types", types);
        JsonArray labels = new JsonArray();
        labels.add(HONEYCARD);
        requested.add("legal_option_labels", labels);
        JsonArray ids = new JsonArray();
        ids.add(HONEYCARD);
        requested.add("legal_option_ids", ids);
        JsonObject metadata = new JsonObject();
        metadata.addProperty("private_name", HONEYCARD);
        requested.add("metadata", metadata);
        raw.add(requested);

        JsonObject accepted = new JsonObject();
        accepted.addProperty("sequence", 2);
        accepted.addProperty("kind", "decision_accepted");
        accepted.addProperty("decision_class", "target");
        accepted.addProperty("actor_seat", 0);
        accepted.addProperty("decision_subject_seat", 0);
        accepted.addProperty("prompt", HONEYCARD);
        JsonArray selectedTypes = new JsonArray();
        selectedTypes.add("card");
        accepted.add("selected_option_types", selectedTypes);
        JsonArray selectedLabels = new JsonArray();
        selectedLabels.add(HONEYCARD);
        accepted.add("selected_option_labels", selectedLabels);
        accepted.add("numeric_choice", JsonNull.INSTANCE);
        raw.add(accepted);

        JsonObject failure = new JsonObject();
        failure.addProperty("offset", 3);
        failure.addProperty("event_type", "controller_failure");
        JsonObject payload = new JsonObject();
        payload.addProperty("message", "PILOT_RESPONSE_INVALID: " + HONEYCARD);
        failure.add("payload", payload);
        raw.add(failure);

        JsonArray safe = XmageAuditSurfaceRedactor.redactTranscript(raw);
        String serialized = safe.toString();

        assertFalse(serialized.contains(HONEYCARD));
        assertFalse(serialized.contains("prompt"));
        assertFalse(serialized.contains("label"));
        assertFalse(serialized.contains("private_actor_state_reference"));
        assertEquals(1, safe.get(0).getAsJsonObject().get("legal_option_count").getAsInt());
        assertEquals(1, safe.get(1).getAsJsonObject().get("selected_option_count").getAsInt());
        assertFalse(safe.get(1).getAsJsonObject().get("numeric_choice_present").getAsBoolean());
        assertEquals(
                "PILOT_RESPONSE_INVALID",
                safe.get(2).getAsJsonObject().get("failure_code").getAsString()
        );
    }

    @Test
    void exportedFailureRetainsOnlyTypeAndTypedCode() {
        JsonObject safe = XmageAuditSurfaceRedactor.redactFailure(
                "decision_controller",
                "COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER: " + HONEYCARD
        );

        assertEquals("decision_controller", safe.get("type").getAsString());
        assertEquals(
                "COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER",
                safe.get("code").getAsString()
        );
        assertFalse(safe.toString().contains(HONEYCARD));
        assertTrue(safe.entrySet().stream().allMatch(
                entry -> entry.getKey().equals("type") || entry.getKey().equals("code")
        ));
    }
}
