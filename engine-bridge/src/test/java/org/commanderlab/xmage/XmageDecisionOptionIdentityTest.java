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

    @Test
    void preservesNativeBindingAfterActorSafeProjectionChangesOptionId() {
        String nativePlayerId = "123e4567-e89b-12d3-a456-426614174001";
        JsonArray nativeOptions = new JsonArray();
        JsonObject nativeOption = new JsonObject();
        nativeOption.addProperty("option_id", nativePlayerId);
        nativeOption.addProperty("option_type", "choice");
        nativeOptions.add(nativeOption);

        XmageDecisionOptionIdentity.Binding initial = XmageDecisionOptionIdentity.externalize(
                nativeOptions,
                Map.of(nativePlayerId, "P1")
        );
        JsonArray projected = initial.externalOptions().deepCopy();
        projected.get(0).getAsJsonObject().addProperty("option_id", "obj-actor-visible-player");

        XmageDecisionOptionIdentity.Binding rebound =
                XmageDecisionOptionIdentity.rebindAfterOutboundProjection(initial, projected);

        assertEquals(nativePlayerId, rebound.externalToNative().get("obj-actor-visible-player"));
    }

    @Test
    void failsClosedWhenProjectionCollapsesDistinctOptions() {
        JsonArray options = new JsonArray();
        JsonObject first = new JsonObject();
        first.addProperty("option_id", "keep");
        JsonObject second = new JsonObject();
        second.addProperty("option_id", "mulligan");
        options.add(first);
        options.add(second);
        XmageDecisionOptionIdentity.Binding initial = XmageDecisionOptionIdentity.externalize(options, Map.of());
        JsonArray collapsed = initial.externalOptions().deepCopy();
        collapsed.get(0).getAsJsonObject().addProperty("option_id", "same");
        collapsed.get(1).getAsJsonObject().addProperty("option_id", "same");

        IllegalStateException failure = assertThrows(
                IllegalStateException.class,
                () -> XmageDecisionOptionIdentity.rebindAfterOutboundProjection(initial, collapsed)
        );

        assertTrue(failure.getMessage().startsWith("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER:"));
    }
}
