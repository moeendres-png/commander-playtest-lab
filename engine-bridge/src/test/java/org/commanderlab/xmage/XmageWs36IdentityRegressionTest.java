package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageWs36IdentityRegressionTest {

    @Test
    void actorOpaqueOptionRetainsExactNativeUuidBinding() {
        String nativeUuid = "123e4567-e89b-12d3-a456-426614174000";
        String actorOpaque = "obj-actor-opaque-current-frame";
        JsonArray nativeOptions = new JsonArray();
        JsonObject option = new JsonObject();
        option.addProperty("option_id", nativeUuid);
        option.addProperty("option_type", "card");
        option.addProperty("label", "visible object");
        nativeOptions.add(option);

        XmageDecisionOptionIdentity.Binding binding = XmageDecisionOptionIdentity.externalize(
                nativeOptions,
                Map.of(nativeUuid, actorOpaque)
        );

        assertEquals(actorOpaque,
                binding.externalOptions().get(0).getAsJsonObject().get("option_id").getAsString());
        assertEquals(nativeUuid, binding.externalToNative().get(actorOpaque));
        assertTrue(binding.externalToNative().values().stream().allMatch(value ->
                value.equals(nativeUuid)));
    }

    @Test
    @SuppressWarnings("unchecked")
    void nativeAliasMayRebindAcrossProjectionFramesButNotPrivilegedIdentity() throws Exception {
        Class<?> viewerStateClass = Class.forName(
                "org.commanderlab.xmage.XmageActorIdentityProjection$ViewerState"
        );
        Constructor<?> constructor = viewerStateClass.getDeclaredConstructor();
        constructor.setAccessible(true);
        Object viewerState = constructor.newInstance();
        Method aliases = viewerStateClass.getDeclaredMethod("currentNativeAliases", Map.class);
        aliases.setAccessible(true);

        String nativeUuid = "123e4567-e89b-12d3-a456-426614174001";
        Map<String, String> first = (Map<String, String>) aliases.invoke(
                viewerState,
                Map.of(nativeUuid, "semantic-incarnation-a")
        );
        Map<String, String> second = (Map<String, String>) aliases.invoke(
                viewerState,
                Map.of(nativeUuid, "semantic-incarnation-b")
        );
        Map<String, String> firstAgain = (Map<String, String>) aliases.invoke(
                viewerState,
                Map.of(nativeUuid, "semantic-incarnation-a")
        );

        assertNotEquals(first.get(nativeUuid), second.get(nativeUuid));
        assertEquals(first.get(nativeUuid), firstAgain.get(nativeUuid));
    }
}
