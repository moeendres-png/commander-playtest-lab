package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.util.RandomUtil;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;

/** Qualification-only bridge to the reproducible WS-26 RandomUtil instrumentation patch. */
final class XmageWs26RulesRngTape {

    private static final String PATCH_API = "ws26-randomutil-recording/1.0.0";

    private XmageWs26RulesRngTape() {
    }

    static void begin() {
        invokeVoid("beginRulesRngTape");
    }

    static JsonObject snapshot(long seed) {
        Object value = invoke("getRulesRngTape");
        if (!(value instanceof List<?> list)) {
            throw new IllegalStateException("XMAGE_RULES_RNG_TAPE_INVALID");
        }
        JsonArray operations = new JsonArray();
        for (Object item : list) {
            if (!(item instanceof String text)) {
                throw new IllegalStateException("XMAGE_RULES_RNG_TAPE_INVALID_ENTRY");
            }
            operations.add(text);
        }
        JsonObject payload = new JsonObject();
        payload.addProperty("schema_version", "rules-rng-tape/1.0.0");
        payload.addProperty("authority", "mage.util.RandomUtil");
        payload.addProperty("source_identity", PATCH_API);
        payload.addProperty("seed", seed);
        payload.addProperty("pilot_rng_mixed", false);
        payload.add("operations", operations);
        payload.addProperty("operation_count", operations.size());
        payload.addProperty("sha256", sha256(operations.toString()));
        return payload;
    }

    static JsonObject capability() {
        JsonObject payload = new JsonObject();
        payload.addProperty("source_identity", PATCH_API);
        try {
            RandomUtil.class.getMethod("beginRulesRngTape");
            RandomUtil.class.getMethod("getRulesRngTape");
            payload.addProperty("instrumentation_available", true);
        } catch (NoSuchMethodException exc) {
            payload.addProperty("instrumentation_available", false);
        }
        return payload;
    }

    private static void invokeVoid(String methodName) {
        invoke(methodName);
    }

    private static Object invoke(String methodName) {
        try {
            Method method = RandomUtil.class.getMethod(methodName);
            return method.invoke(null);
        } catch (NoSuchMethodException exc) {
            throw new IllegalStateException("XMAGE_RULES_RNG_TAPE_UNAVAILABLE", exc);
        } catch (IllegalAccessException | InvocationTargetException exc) {
            throw new IllegalStateException("XMAGE_RULES_RNG_TAPE_FAILURE", exc);
        }
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException(exc);
        }
    }
}
