package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.game.Game;

final class XmageProvider {

    static final String ENGINE = "xmage";
    static final String ENGINE_VERSION = "1.4.61";
    static final String ENGINE_COMMIT =
            "77d7646da6958fdf8125ee7c8f4aabd130d21d4c";
    static final String PROTOCOL_VERSION = "2.0.0";

    private XmageProvider() {
    }

    static void verifyRuntimeLoaded() {
        if (Game.class.getProtectionDomain() == null
                || Game.class.getProtectionDomain().getCodeSource() == null) {
            throw new IllegalStateException(
                    "Unable to identify loaded XMage runtime"
            );
        }
    }

    static JsonObject providerVersion() {
        verifyRuntimeLoaded();

        JsonObject payload = new JsonObject();
        payload.addProperty("engine", ENGINE);
        payload.addProperty("engine_version", ENGINE_VERSION);
        payload.addProperty("engine_commit", ENGINE_COMMIT);
        payload.addProperty("protocol_version", PROTOCOL_VERSION);
        payload.addProperty(
                "xmage_code_source",
                Game.class.getProtectionDomain()
                        .getCodeSource()
                        .getLocation()
                        .toString()
        );
        return payload;
    }

    static JsonObject capabilitiesPayload() {
        JsonObject capabilities = new JsonObject();

        /*
         * B1 deliberately advertises no gameplay capability.
         * Loading a real XMage runtime is not equivalent to implementing
         * Commander gameplay through the Lab protocol.
         */
        capabilities.addProperty("commander_supported", false);
        capabilities.addProperty("partner_supported", false);
        capabilities.addProperty("multiplayer_supported", false);
        capabilities.addProperty("headless_supported", false);
        capabilities.addProperty("seed_supported", false);
        capabilities.addProperty("deck_import_supported", true);
        capabilities.addProperty("legal_actions_supported", false);
        capabilities.addProperty("action_submission_supported", false);
        capabilities.addProperty("event_log_supported", false);
        capabilities.addProperty("replay_supported", false);
        capabilities.addProperty("stack_visible", false);
        capabilities.addProperty("priority_visible", false);
        capabilities.addProperty("commander_damage_visible", false);
        capabilities.addProperty("commander_tax_visible", false);
        capabilities.addProperty("starting_state_injection_supported", false);
        capabilities.addProperty("scenario_injection_supported", false);

        capabilities.addProperty("healthcheck_supported", true);

        capabilities.addProperty("target_selection_supported", false);
        capabilities.addProperty("mode_selection_supported", false);
        capabilities.addProperty("trigger_order_supported", false);
        capabilities.addProperty("mulligan_supported", false);
        capabilities.addProperty("concede_supported", false);
        capabilities.addProperty("game_shutdown_supported", false);

        /*
         * Process shutdown itself is implemented in B1.
         */
        capabilities.addProperty("engine_shutdown_supported", true);

        /*
         * This identifies the kind of runtime behind the bridge.
         * It does NOT grant semantic external-engine validation.
         * The Lab health gate must still report DEGRADED because the
         * required gameplay capabilities above are false.
         */
        capabilities.addProperty(
                "runtime_kind",
                "external_rules_engine"
        );

        JsonArray notes = new JsonArray();
        notes.add(
                "B2 real XMage deck import implemented; gameplay capabilities not implemented"
        );
        notes.add(
                "NO_PROVIDER_READY remains in force"
        );
        capabilities.add("notes", notes);

        JsonObject result = new JsonObject();
        result.add("capabilities", capabilities);
        return result;
    }
}