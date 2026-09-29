package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmagePb03CapabilityManifestTest {

    @Test
    void fullGameCapabilityPublishesItemisedRestorationDimensionsWithoutGlobalPromotion() {
        JsonObject payload = XmageFullGameJsonlBridge.capabilitiesPayload();
        JsonObject capabilities = payload.getAsJsonObject("capabilities");
        assertFalse(capabilities.get("starting_state_injection_supported").getAsBoolean());

        JsonObject lane = payload.getAsJsonObject("full_game_lane");
        JsonObject dimensions = lane.getAsJsonObject("state_restoration_dimensions");
        assertNotNull(dimensions);
        assertFalse(dimensions.get("starting_state_injection_supported").getAsBoolean());

        JsonArray supported = dimensions.getAsJsonArray("supported_dimensions");
        JsonArray unsupported = dimensions.getAsJsonArray("unsupported_dimensions");
        assertTrue(contains(supported, "qualified turn-1"));
        assertTrue(contains(supported, "commander damage matrices"));
        assertTrue(contains(unsupported, "stack spells"));
        assertTrue(contains(unsupported, "controller/owner divergence"));
        assertTrue(contains(unsupported, "zero-life pre-start"));
    }

    private static boolean contains(JsonArray values, String needle) {
        for (JsonElement value : values) {
            if (value.getAsString().contains(needle)) {
                return true;
            }
        }
        return false;
    }
}
