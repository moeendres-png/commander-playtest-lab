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
         * B4-D retains the real B4-A/B4-B/B4-C state and action surfaces and
         * adds an externally exportable, monotonic audit event stream plus
         * explicit per-game XMage end/cleanup. The event stream records real
         * bridge/XMage lifecycle and externally controlled action boundaries;
         * it is deliberately not described as an exhaustive internal
         * mage.game.events.GameEvent tap.
         *
         * Global legal-actions/action-submission flags remain false because
         * target, mode, choice and combat classes are not yet complete.
         */
        capabilities.addProperty("commander_supported", true);
        capabilities.addProperty("partner_supported", true);
        capabilities.addProperty("multiplayer_supported", true);
        capabilities.addProperty("max_players", 5);
        capabilities.addProperty("headless_supported", true);
        capabilities.addProperty("seed_supported", false);
        capabilities.addProperty("deck_import_supported", true);
        capabilities.addProperty("legal_actions_supported", false);
        capabilities.addProperty("action_submission_supported", false);
        capabilities.addProperty("event_log_supported", true);
        capabilities.addProperty("replay_supported", false);
        capabilities.addProperty("stack_visible", true);
        capabilities.addProperty("priority_visible", true);
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
        capabilities.addProperty("game_shutdown_supported", true);
        capabilities.addProperty("engine_shutdown_supported", true);
        capabilities.addProperty("runtime_kind", "external_rules_engine");

        JsonArray notes = new JsonArray();
        notes.add(
                "B4-D real XMage bridge audit event log is externally exportable with monotonic sequence, action/decision identity and pre/post state hashes; it covers bridge lifecycle and externally controlled action boundaries and is not an exhaustive raw internal XMage GameEvent tap"
        );
        notes.add(
                "B4-D explicit per-game XMage end/cleanup and deck-handle release are implemented for repeated games in one bridge process"
        );
        notes.add(
                "B4-C bounded current-priority action control remains validated; global legal-action and action-submission completeness remain unavailable"
        );
        notes.add(
                "Seed remains unknown/uncontrolled; no numeric sentinel is synthesized"
        );
        notes.add("NO_PROVIDER_READY remains in force");
        capabilities.add("notes", notes);

        JsonObject result = new JsonObject();
        result.add("capabilities", capabilities);
        return result;
    }
}
