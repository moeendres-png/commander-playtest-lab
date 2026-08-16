package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class JsonlBridgeTest {

    private final JsonlBridge bridge = new JsonlBridge();

    private static String request(
            String requestId,
            String method
    ) {
        return """
                {
                  "protocol_version": "2.0.0",
                  "request_id": "%s",
                  "engine": "xmage",
                  "message_type": "%s",
                  "payload": {},
                  "method": "%s",
                  "params": {}
                }
                """.formatted(
                requestId,
                method,
                method
        );
    }

    @Test
    void startEngineLoadsRealXmageRuntime() {
        JsonlBridge.Result result =
                bridge.handle(request("r1", "start_engine"));

        JsonObject response =
                JsonParser.parseString(result.json())
                        .getAsJsonObject();

        assertTrue(response.get("success").getAsBoolean());
        assertFalse(result.shutdown());
        assertEquals(
                "xmage",
                response.getAsJsonObject("payload")
                        .get("engine")
                        .getAsString()
        );
    }

    @Test
    void providerVersionIdentifiesPinnedXmage() {
        JsonlBridge.Result result =
                bridge.handle(
                        request("r2", "get_provider_version")
                );

        JsonObject payload =
                JsonParser.parseString(result.json())
                        .getAsJsonObject()
                        .getAsJsonObject("payload");

        assertEquals("xmage", payload.get("engine").getAsString());
        assertEquals(
                "1.4.61",
                payload.get("engine_version").getAsString()
        );
        assertEquals(
                "77d7646da6958fdf8125ee7c8f4aabd130d21d4c",
                payload.get("engine_commit").getAsString()
        );
        assertTrue(payload.has("xmage_code_source"));
    }

    @Test
    void b1CapabilitiesRemainFailClosed() {
        JsonlBridge.Result result =
                bridge.handle(
                        request("r3", "get_capabilities")
                );

        JsonObject capabilities =
                JsonParser.parseString(result.json())
                        .getAsJsonObject()
                        .getAsJsonObject("payload")
                        .getAsJsonObject("capabilities");

        assertEquals(
                "external_rules_engine",
                capabilities.get("runtime_kind").getAsString()
        );

        assertFalse(
                capabilities.get("commander_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("multiplayer_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("deck_import_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("legal_actions_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("action_submission_supported")
                        .getAsBoolean()
        );
        assertFalse(
                capabilities.get("event_log_supported")
                        .getAsBoolean()
        );

        assertTrue(
                capabilities.get("engine_shutdown_supported")
                        .getAsBoolean()
        );
    }

    @Test
    void shutdownIsImplemented() {
        JsonlBridge.Result result =
                bridge.handle(
                        request("r4", "shutdown_engine")
                );

        assertTrue(result.shutdown());
    }

    @Test
    void unsupportedGameplayMessageFailsClosed() {
        JsonlBridge.Result result =
                bridge.handle(
                        request("r5", "import_deck")
                );

        JsonObject response =
                JsonParser.parseString(result.json())
                        .getAsJsonObject();

        assertFalse(response.get("success").getAsBoolean());
        assertEquals("error", response.get("status").getAsString());
    }

    @Test
    void protocolMismatchIsRejected() {
        String request = """
                {
                  "protocol_version": "999.0",
                  "request_id": "bad-version",
                  "engine": "xmage",
                  "message_type": "start_engine",
                  "payload": {}
                }
                """;

        JsonlBridge.Result result = bridge.handle(request);

        JsonObject response =
                JsonParser.parseString(result.json())
                        .getAsJsonObject();

        assertFalse(response.get("success").getAsBoolean());
    }
}