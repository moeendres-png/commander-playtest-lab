package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.List;

/** Qualification-only JSONL surface. */
final class XmageWs26QualificationJsonlBridge {

    private final XmageDeckImporter deckImporter = new XmageDeckImporter();
    private XmageWs26QualificationSession session;

    record Result(String json, boolean shutdown) {}

    Result handle(String input) {
        JsonObject request;
        try {
            request = JsonParser.parseString(input).getAsJsonObject();
        } catch (Exception exc) {
            return error("", "invalid_json", "Request is not a valid JSON object");
        }
        String requestId = stringValue(request, "request_id");
        if (!XmageProvider.PROTOCOL_VERSION.equals(stringValue(request, "protocol_version"))) {
            return error(requestId, "protocol_version_mismatch", "Expected " + XmageProvider.PROTOCOL_VERSION);
        }
        String type = stringValue(request, "message_type");
        if (type.isBlank()) type = stringValue(request, "method");
        return switch (type) {
            case "start_engine" -> success(requestId, startedPayload(), false);
            case "get_provider_version" -> success(requestId, XmageProvider.providerVersion(), false);
            case "get_capabilities" -> success(requestId, capabilitiesPayload(), false);
            case "import_deck" -> importDeck(requestId, request);
            case "create_full_game" -> createGame(requestId, request);
            case "configure_qualification_scenario" -> configureScenario(requestId, request);
            case "start_full_game" -> execute(requestId, () -> requireSession().start(), "full_game_start_failed");
            case "get_full_game_decision" -> execute(requestId, () -> requireSession().pendingDecisionPayload(), "full_game_decision_failed");
            case "get_full_game_observation" -> getObservation(requestId, request);
            case "submit_full_game_decision" -> submit(requestId, request);
            case "get_qualification_state" -> execute(requestId, () -> requireSession().qualificationStatePayload(), "qualification_state_failed");
            case "get_full_game_result" -> execute(requestId, () -> requireSession().resultPayload(), "full_game_result_failed");
            case "shutdown_engine" -> success(requestId, shutdownPayload(), true);
            default -> error(requestId, "unsupported_message", "WS-26 lane does not support " + type);
        };
    }

    private Result importDeck(String requestId, JsonObject request) {
        try {
            JsonObject payload = requirePayload(request);
            JsonObject deck = payload.getAsJsonObject("deck");
            if (deck == null) throw new IllegalArgumentException("payload.deck required");
            List<String> mainboard = stringArray(deck, "mainboard");
            List<String> commanders = stringArray(deck, "commander_names");
            XmageDeckImporter.ImportResult imported = deckImporter.importCommanderDeck(
                    requiredText(deck, "deck_id"), requiredText(deck, "deck_hash"), mainboard, commanders
            );
            JsonObject handle = new JsonObject();
            handle.addProperty("handle_id", imported.deckHandle());
            handle.addProperty("deck_id", imported.deckId());
            handle.addProperty("deck_hash", imported.deckHash());
            JsonObject payloadOut = new JsonObject();
            payloadOut.add("deck_handle", handle);
            return success(requestId, payloadOut, false);
        } catch (Exception exc) {
            return error(requestId, "deck_import_failed", exceptionMessage(exc));
        }
    }

    private Result createGame(String requestId, JsonObject request) {
        try {
            if (session != null) throw new IllegalStateException("one game per process");
            JsonObject payload = requirePayload(request);
            List<String> handles = stringArray(payload, "deck_handles");
            long seed = requiredLong(payload, "seed");
            int startingSeat = optionalInt(payload, "starting_player_seat", 0);
            int startingLife = optionalInt(payload, "starting_life", 40);
            session = new XmageWs26QualificationSession(
                    requiredText(payload, "game_id"), new ArrayList<>(handles), startingSeat,
                    startingLife, seed, deckImporter
            );
            JsonObject out = new JsonObject();
            out.addProperty("lane", XmageWs26QualificationSession.LANE);
            out.addProperty("player_count", handles.size());
            out.addProperty("seed", seed);
            out.addProperty("starting_player_seat", startingSeat);
            return success(requestId, out, false);
        } catch (Exception exc) {
            return error(requestId, "full_game_creation_failed", exceptionMessage(exc));
        }
    }

    private Result configureScenario(String requestId, JsonObject request) {
        try {
            JsonObject payload = requirePayload(request);
            if (!payload.has("scenario") || !payload.get("scenario").isJsonObject()) {
                throw new IllegalArgumentException("payload.scenario required");
            }
            return success(requestId, requireSession().configureScenario(payload.getAsJsonObject("scenario")), false);
        } catch (Exception exc) {
            return error(requestId, "scenario_rejected", exceptionMessage(exc));
        }
    }

    private Result getObservation(String requestId, JsonObject request) {
        try {
            JsonObject payload = requirePayload(request);
            int viewer = requiredInt(payload, "viewer_seat");
            int subject = optionalInt(payload, "decision_subject_seat", viewer);
            return success(requestId, requireSession().observationPayload(viewer, subject), false);
        } catch (Exception exc) {
            return error(requestId, "full_game_observation_failed", exceptionMessage(exc));
        }
    }

    private Result submit(String requestId, JsonObject request) {
        try {
            JsonObject payload = requirePayload(request);
            if (!payload.has("response") || !payload.get("response").isJsonObject()) {
                throw new IllegalArgumentException("payload.response required");
            }
            return success(requestId, requireSession().submit(payload.getAsJsonObject("response")), false);
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return error(requestId, "external_pilot_decision_rejected", exc.getMessage());
        } catch (Exception exc) {
            return error(requestId, "invalid_full_game_decision", exceptionMessage(exc));
        }
    }

    private interface PayloadSupplier { JsonObject get(); }

    private Result execute(String requestId, PayloadSupplier supplier, String code) {
        try {
            return success(requestId, supplier.get(), false);
        } catch (Exception exc) {
            return error(requestId, code, exceptionMessage(exc));
        }
    }

    private XmageWs26QualificationSession requireSession() {
        if (session == null) throw new IllegalStateException("FULL_GAME_NOT_CREATED");
        return session;
    }

    private static JsonObject capabilitiesPayload() {
        JsonObject capabilities = new JsonObject();
        capabilities.addProperty("lane", XmageWs26QualificationSession.LANE);
        capabilities.addProperty("qualification_only", true);
        capabilities.addProperty("scenario_injection_supported", true);
        capabilities.addProperty("starting_state_injection_supported", true);
        capabilities.addProperty("scenario_schema", XmageWs26Scenario.SCHEMA_VERSION);
        capabilities.addProperty("scenario_fail_closed", true);
        capabilities.addProperty("rules_authority", "xmage");
        capabilities.addProperty("external_decision_authority", true);
        capabilities.addProperty("semantic_checkpoints_supported", true);
        capabilities.addProperty("decision_tape_supported", true);
        capabilities.addProperty("semantic_event_tape_supported", true);
        capabilities.addProperty("clean_process_replay_target", true);
        capabilities.add("rules_rng", XmageWs26RulesRngTape.capability());
        JsonArray supported = new JsonArray();
        supported.add("exact_players_and_seats");
        supported.add("life_totals");
        supported.add("native_commander_identity_from_validated_deck");
        supported.add("hand");
        supported.add("library_order");
        supported.add("graveyard");
        supported.add("face_up_exile");
        supported.add("battlefield_owner_controller_equal_owner");
        supported.add("battlefield_tapped_state");
        supported.add("starting_player");
        supported.add("deterministic_rules_seed");
        capabilities.add("supported_scenario_dimensions", supported);
        JsonArray rejected = new JsonArray();
        for (String value : List.of("arbitrary_controller", "counters", "attachments", "face_down",
                "direct_stack_objects", "direct_priority_holder", "direct_turn_phase_step", "direct_mana_pool",
                "external_knowledge_grants", "native_object_ids")) rejected.add(value);
        capabilities.add("fail_closed_scenario_dimensions", rejected);
        return capabilities;
    }

    private static JsonObject startedPayload() {
        XmageProvider.verifyRuntimeLoaded();
        JsonObject out = new JsonObject();
        out.addProperty("engine", XmageProvider.ENGINE);
        out.addProperty("started", true);
        out.addProperty("lane", XmageWs26QualificationSession.LANE);
        out.addProperty("qualification_only", true);
        return out;
    }

    private static JsonObject shutdownPayload() {
        JsonObject out = new JsonObject();
        out.addProperty("engine", XmageProvider.ENGINE);
        out.addProperty("shutdown", true);
        out.addProperty("lane", XmageWs26QualificationSession.LANE);
        return out;
    }

    private static Result success(String requestId, JsonObject payload, boolean shutdown) {
        JsonObject response = base(requestId);
        response.addProperty("success", true);
        response.addProperty("status", "ok");
        response.add("payload", payload);
        response.addProperty("engine_event_offset", 0);
        return new Result(response.toString(), shutdown);
    }

    private static Result error(String requestId, String code, String message) {
        JsonObject response = base(requestId);
        response.addProperty("success", false);
        response.addProperty("status", "error");
        JsonObject err = new JsonObject();
        err.addProperty("code", code);
        err.addProperty("message", message == null ? code : message);
        err.addProperty("retryable", false);
        JsonArray errors = new JsonArray();
        errors.add(err);
        response.add("errors", errors);
        response.addProperty("engine_event_offset", 0);
        return new Result(response.toString(), false);
    }

    private static JsonObject base(String requestId) {
        JsonObject response = new JsonObject();
        response.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        response.addProperty("request_id", requestId);
        return response;
    }

    private static JsonObject requirePayload(JsonObject request) {
        if (!request.has("payload") || !request.get("payload").isJsonObject()) {
            throw new IllegalArgumentException("object payload required");
        }
        return request.getAsJsonObject("payload");
    }

    private static List<String> stringArray(JsonObject object, String key) {
        if (!object.has(key) || !object.get(key).isJsonArray()) throw new IllegalArgumentException(key + " array required");
        List<String> out = new ArrayList<>();
        for (var element : object.getAsJsonArray(key)) {
            if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isString()) {
                throw new IllegalArgumentException(key + " must contain strings");
            }
            String value = element.getAsString().trim();
            if (value.isEmpty()) throw new IllegalArgumentException(key + " contains blank");
            out.add(value);
        }
        return List.copyOf(out);
    }

    private static String requiredText(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) throw new IllegalArgumentException(key + " required");
        String value = object.get(key).getAsString().trim();
        if (value.isEmpty()) throw new IllegalArgumentException(key + " must be nonblank");
        return value;
    }

    private static long requiredLong(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) throw new IllegalArgumentException(key + " required");
        String raw = object.get(key).getAsString();
        if (!raw.matches("-?\\d+")) throw new IllegalArgumentException(key + " integer required");
        return Long.parseLong(raw);
    }

    private static int requiredInt(JsonObject object, String key) {
        long value = requiredLong(object, key);
        if (value < Integer.MIN_VALUE || value > Integer.MAX_VALUE) throw new IllegalArgumentException(key + " out of range");
        return (int) value;
    }

    private static int optionalInt(JsonObject object, String key, int fallback) {
        return !object.has(key) || object.get(key).isJsonNull() ? fallback : requiredInt(object, key);
    }

    private static String stringValue(JsonObject object, String key) {
        return !object.has(key) || object.get(key).isJsonNull() ? "" : object.get(key).getAsString();
    }

    private static String exceptionMessage(Exception exc) {
        String message = exc.getMessage();
        return exc.getClass().getSimpleName() + ": " + (message == null ? "<no message>" : message);
    }
}
