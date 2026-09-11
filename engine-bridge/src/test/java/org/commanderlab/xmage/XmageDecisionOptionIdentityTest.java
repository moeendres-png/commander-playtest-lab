package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageDecisionOptionIdentityTest {

    @Test
    void roundTripsSemanticObjectIdToExactNativeXmageOptionId() {
        String nativeCardId = "123e4567-e89b-12d3-a456-426614174000";
        String semanticObjectId = "P1:deck-card-0001@z0";

        JsonArray nativeOptions = new JsonArray();
        JsonObject cardOption = new JsonObject();
        cardOption.addProperty("option_id", nativeCardId);
        cardOption.addProperty("option_type", "card");
        cardOption.addProperty("label", "Plains");
        nativeOptions.add(cardOption);

        JsonObject stableOption = new JsonObject();
        stableOption.addProperty("option_id", "keep");
        stableOption.addProperty("option_type", "mode");
        stableOption.addProperty("label", "Keep");
        nativeOptions.add(stableOption);

        XmageDecisionOptionIdentity.Binding binding = XmageDecisionOptionIdentity.externalize(
                nativeOptions,
                Map.of(nativeCardId, semanticObjectId)
        );

        assertEquals(semanticObjectId, binding.externalOptions().get(0).getAsJsonObject().get("option_id").getAsString());
        assertEquals("keep", binding.externalOptions().get(1).getAsJsonObject().get("option_id").getAsString());
        assertEquals(nativeCardId, binding.externalToNative().get(semanticObjectId));
        assertEquals("keep", binding.externalToNative().get("keep"));
    }

    @Test
    void failsClosedWhenNativeObjectOptionHasNoVisibleSemanticIdentity() {
        JsonArray nativeOptions = new JsonArray();
        JsonObject cardOption = new JsonObject();
        cardOption.addProperty("option_id", "123e4567-e89b-12d3-a456-426614174000");
        nativeOptions.add(cardOption);

        IllegalStateException failure = assertThrows(
                IllegalStateException.class,
                () -> XmageDecisionOptionIdentity.externalize(nativeOptions, Map.of())
        );

        assertTrue(failure.getMessage().startsWith("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER:"));
    }
}
