package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonNull;
import com.google.gson.JsonParser;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS52-owned external-pilot driver for the full-game JSONL lane.
 *
 * <p>The driver acts strictly as an external pilot: it reads pending
 * decision frames published by XMage, echoes back exact offered option
 * identifiers, and never synthesizes identifiers, legality, or fallback
 * choices. Test-side ground truth comes only from pilot-visible frames,
 * never from native UUIDs.</p>
 */
final class Ws52 {

    static final long SEED_A = 5201L;
    static final long SEED_B = 5202L;
    static final int STARTING_LIFE = 40;

    private Ws52() {
    }

    // ------------------------------------------------------------------
    // JSONL transport
    // ------------------------------------------------------------------

    static JsonObject send(XmageFullGameJsonlBridge bridge, String messageType, JsonObject payload) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "ws52-" + messageType + "-" + System.nanoTime());
        request.addProperty("message_type", messageType);
        request.add("payload", payload == null ? new JsonObject() : payload);
        XmageFullGameJsonlBridge.Result result = bridge.handle(request.toString());
        return JsonParser.parseString(result.json()).getAsJsonObject();
    }

    static JsonObject requireSuccess(JsonObject response) {
        assertTrue(response.get("success").getAsBoolean(),
                () -> "expected JSONL success: " + response);
        return response.getAsJsonObject("payload");
    }

    static JsonObject requireFailure(JsonObject response) {
        assertTrue(!response.get("success").getAsBoolean(),
                () -> "expected JSONL failure: " + response);
        return response;
    }

    static String errorText(JsonObject failure) {
        JsonArray errors = failure.getAsJsonArray("errors");
        StringBuilder out = new StringBuilder();
        for (JsonElement element : errors) {
            JsonObject error = element.getAsJsonObject();
            out.append(error.get("code").getAsString())
                    .append(':')
                    .append(error.get("message").getAsString())
                    .append(';');
        }
        return out.toString();
    }

    // ------------------------------------------------------------------
    // Decks
    // ------------------------------------------------------------------

    /** Sentinel deck A: 99 Islands + Ishai (mainboard names disjoint from B). */
    static DeckSpec sentinelDeckA() {
        List<String> main = new ArrayList<>(Collections.nCopies(99, "Island"));
        return new DeckSpec("ws52/sentinel-a", "sentinel-a-hash", main,
                List.of("Ishai, Ojutai Dragonspeaker"));
    }

    /** Sentinel deck B: 99 Mountains + Rograkh (mainboard names disjoint from A). */
    static DeckSpec sentinelDeckB() {
        List<String> main = new ArrayList<>(Collections.nCopies(99, "Mountain"));
        return new DeckSpec("ws52/sentinel-b", "sentinel-b-hash", main,
                List.of("Rograkh, Son of Rohgahh"));
    }

    static DeckSpec rogshaiDeck() throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        Path path = Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize();
        JsonObject root = JsonParser.parseString(
                Files.readString(path, StandardCharsets.UTF_8)).getAsJsonObject();
        List<String> mainboard = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        root.getAsJsonArray("cards").forEach(element -> {
            JsonObject card = element.getAsJsonObject();
            String name = card.get("oracle_name").getAsString();
            int quantity = card.get("quantity").getAsInt();
            String zone = card.get("zone").getAsString();
            List<String> target;
            if ("main".equals(zone)) {
                target = mainboard;
            } else if ("commander".equals(zone)) {
                target = commanders;
            } else {
                throw new IllegalStateException("Unexpected zone: " + zone);
            }
            for (int copy = 0; copy < quantity; copy++) {
                target.add(name);
            }
        });
        return new DeckSpec(root.get("deck_id").getAsString(),
                root.get("deck_hash").getAsString(), List.copyOf(mainboard), List.copyOf(commanders));
    }

    record DeckSpec(String deckId, String deckHash, List<String> mainboard, List<String> commanders) {
    }

    static String importDeck(XmageFullGameJsonlBridge bridge, DeckSpec spec) {
        JsonObject deck = new JsonObject();
        deck.addProperty("deck_id", spec.deckId());
        deck.addProperty("deck_hash", spec.deckHash());
        JsonArray main = new JsonArray();
        spec.mainboard().forEach(main::add);
        deck.add("mainboard", main);
        JsonArray commanders = new JsonArray();
        spec.commanders().forEach(commanders::add);
        deck.add("commander_names", commanders);
        JsonObject payload = new JsonObject();
        payload.add("deck", deck);
        JsonObject imported = requireSuccess(send(bridge, "import_deck", payload));
        return imported.getAsJsonObject("deck_handle").get("handle_id").getAsString();
    }

    // ------------------------------------------------------------------
    // Game lifecycle
    // ------------------------------------------------------------------

    static void createFullGame(XmageFullGameJsonlBridge bridge, String gameId,
            List<String> deckHandles, long seed) {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", gameId);
        JsonArray handles = new JsonArray();
        deckHandles.forEach(handles::add);
        payload.add("deck_handles", handles);
        payload.addProperty("seed", seed);
        payload.addProperty("starting_player_seat", 0);
        payload.addProperty("starting_life", STARTING_LIFE);
        JsonObject created = requireSuccess(send(bridge, "create_full_game", payload));
        assertEquals(gameId, created.get("game_id").getAsString());
        assertTrue(created.get("seed_controlled").getAsBoolean());
    }

    static JsonObject startFullGame(XmageFullGameJsonlBridge bridge) {
        return requireSuccess(send(bridge, "start_full_game", new JsonObject()));
    }

    /** Full pending-decision payload: status fields plus the `decision` frame (possibly null). */
    static JsonObject getDecision(XmageFullGameJsonlBridge bridge) {
        return requireSuccess(send(bridge, "get_full_game_decision", new JsonObject()));
    }

    static JsonObject requirePendingDecision(JsonObject decisionPayload) {
        assertTrue(decisionPayload.has("decision") && decisionPayload.get("decision").isJsonObject(),
                () -> "expected a pending decision frame: " + decisionPayload);
        return decisionPayload.getAsJsonObject("decision");
    }

    static JsonObject getObservation(XmageFullGameJsonlBridge bridge, int viewerSeat) {
        JsonObject payload = new JsonObject();
        payload.addProperty("viewer_seat", viewerSeat);
        payload.addProperty("decision_subject_seat", viewerSeat);
        return requireSuccess(send(bridge, "get_full_game_observation", payload));
    }

    // ------------------------------------------------------------------
    // Pilot policy (echo exact offered ids; select by structure, never by rematch)
    // ------------------------------------------------------------------

    static JsonArray legalOptions(JsonObject decision) {
        return decision.getAsJsonArray("legal_options");
    }

    static String optionId(JsonObject option) {
        return option.get("option_id").getAsString();
    }

    static String optionType(JsonObject option) {
        return option.has("option_type") && !option.get("option_type").isJsonNull()
                ? option.get("option_type").getAsString() : "generic";
    }

    static String optionLabel(JsonObject option) {
        return option.has("label") && !option.get("label").isJsonNull()
                ? option.get("label").getAsString() : "";
    }

    static List<String> optionIdsByType(JsonObject decision, String type) {
        List<String> out = new ArrayList<>();
        for (JsonElement element : legalOptions(decision)) {
            JsonObject option = element.getAsJsonObject();
            if (type.equals(optionType(option))) {
                out.add(optionId(option));
            }
        }
        return out;
    }

    static String singleOptionIdByType(JsonObject decision, String type) {
        List<String> matches = optionIdsByType(decision, type);
        assertEquals(1, matches.size(),
                () -> "expected exactly one option of type " + type + ": " + decision);
        return matches.get(0);
    }

    static JsonObject submitResponse(JsonObject decision, List<String> selectedOptionIds,
            Integer numericChoice) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", decision.get("decision_id").getAsString());
        response.addProperty("actor_id", decision.get("actor_id").getAsString());
        JsonArray selected = new JsonArray();
        selectedOptionIds.forEach(selected::add);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        if (numericChoice == null) {
            response.add("numeric_choice", JsonNull.INSTANCE);
        } else {
            response.addProperty("numeric_choice", numericChoice);
        }
        JsonObject payload = new JsonObject();
        payload.add("response", response);
        return payload;
    }

    static JsonObject submit(XmageFullGameJsonlBridge bridge, JsonObject decision,
            List<String> selectedOptionIds) {
        return requireSuccess(
                send(bridge, "submit_full_game_decision",
                        submitResponse(decision, selectedOptionIds, null)));
    }

    /**
     * Deterministic opening prelude: the engine opens with a "Select a
     * starting player" frame (engine-computed player set), then one London
     * mulligan frame per player. The pilot always installs Seat 1 as the
     * starting player and keeps every hand.
     */
    static Opening pilotOpening(XmageFullGameJsonlBridge bridge) {
        int startingChoices = 0;
        for (int i = 0; i < 2; i++) {
            JsonObject payload = getDecision(bridge);
            if (!payload.has("decision") || !payload.get("decision").isJsonObject()) {
                break;
            }
            JsonObject decision = payload.getAsJsonObject("decision");
            if (!"choose_object".equals(decision.get("decision_class").getAsString())) {
                break;
            }
            String seat1 = null;
            for (JsonElement element : legalOptions(decision)) {
                JsonObject option = element.getAsJsonObject();
                if (optionLabel(option).endsWith("Seat 1")) {
                    seat1 = optionId(option);
                }
            }
            assertTrue(seat1 != null,
                    () -> "starting-player frame must offer Seat 1: " + decision);
            submit(bridge, decision, List.of(seat1));
            startingChoices++;
        }
        int mulligans = keepAllMulligans(bridge, 6);
        return new Opening(startingChoices, mulligans);
    }

    record Opening(int startingPlayerChoices, int mulligans) {
    }

    /** Keep every mulligan frame until no mulligan is pending; returns frames consumed. */
    static int keepAllMulligans(XmageFullGameJsonlBridge bridge, int maxFrames) {        int consumed = 0;
        for (int i = 0; i < maxFrames; i++) {
            JsonObject payload = getDecision(bridge);
            if (!payload.has("decision") || !payload.get("decision").isJsonObject()) {
                break;
            }
            JsonObject decision = payload.getAsJsonObject("decision");
            if (!"mulligan".equals(decision.get("decision_class").getAsString())) {
                break;
            }
            List<JsonObject> keeps = new ArrayList<>();
            for (JsonElement element : legalOptions(decision)) {
                JsonObject option = element.getAsJsonObject();
                if ("Keep opening hand".equals(optionLabel(option))) {
                    keeps.add(option);
                }
            }
            assertEquals(1, keeps.size(), () -> "mulligan frame must offer exactly one keep: " + decision);
            submit(bridge, decision, List.of(optionId(keeps.get(0))));
            consumed++;
        }
        return consumed;
    }

    static void assertUniqueOptionIds(JsonObject decision) {
        List<String> ids = new ArrayList<>();
        for (JsonElement element : legalOptions(decision)) {
            ids.add(optionId(element.getAsJsonObject()));
        }
        assertEquals(ids.size(), ids.stream().distinct().count(),
                () -> "duplicate option ids in decision frame: " + decision);
        for (String id : ids) {
            if (id == null || id.isBlank()) {
                fail("blank option id in decision frame: " + decision);
            }
        }
    }
}
