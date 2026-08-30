package org.commanderlab.xmage;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.Zone;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Semantic replay evidence recorded at deterministic external-decision boundaries.
 * It does not decide rules or legal actions.
 */
final class XmageWs26ReplayRecorder {

    private static final String PRIORITY_PASS_SEMANTIC_ID = "priority:pass";

    record Checkpoint(long sequence, JsonObject payload) {
    }

    private final Game game;
    private final List<? extends Player> players;
    private final XmageKnowledgeLedger ledger;
    private final Map<UUID, String> scenarioObjectIds;
    private final JsonArray decisionTape = new JsonArray();
    private final JsonArray eventTape = new JsonArray();
    private final JsonArray checkpoints = new JsonArray();
    private long checkpointSequence;
    private long decisionRevision;
    private long eventSequence;

    XmageWs26ReplayRecorder(
            Game game,
            List<? extends Player> players,
            XmageKnowledgeLedger ledger,
            Map<UUID, String> scenarioObjectIds
    ) {
        this.game = game;
        this.players = players;
        this.ledger = ledger;
        this.scenarioObjectIds = scenarioObjectIds == null ? Map.of() : Map.copyOf(scenarioObjectIds);
    }

    synchronized Checkpoint checkpoint(String boundary) {
        checkpointSequence++;
        JsonArray actorViews = new JsonArray();
        JsonArray actorHashes = new JsonArray();
        for (int seat = 0; seat < players.size(); seat++) {
            Player player = players.get(seat);
            JsonObject view = ledger.snapshot(game, player, player);
            actorViews.add(view);
            JsonObject actorHash = new JsonObject();
            actorHash.addProperty("seat", seat + 1);
            actorHash.addProperty("sha256", hash(view));
            actorHashes.add(actorHash);
        }

        JsonObject privileged = privilegedState(actorViews);
        JsonObject publicState = publicProjection(actorViews.size() == 0
                ? new JsonObject() : actorViews.get(0).getAsJsonObject());

        JsonObject payload = new JsonObject();
        payload.addProperty("schema_version", "semantic-checkpoint/1.0.0");
        payload.addProperty("sequence", checkpointSequence);
        payload.addProperty("boundary", boundary);
        payload.addProperty("turn", game.getState().getTurnNum());
        payload.addProperty("privileged_state_sha256", hash(privileged));
        payload.addProperty("public_state_sha256", hash(publicState));
        payload.add("actor_state_hashes", actorHashes);
        payload.add("privileged_state", privileged);
        payload.add("public_state", publicState);
        checkpoints.add(payload);
        return new Checkpoint(checkpointSequence, payload.deepCopy());
    }

    synchronized void recordAcceptedDecision(
            JsonObject pending,
            JsonObject submitted,
            Checkpoint before,
            Checkpoint after
    ) {
        decisionRevision++;
        JsonObject tape = decisionRecord(pending, submitted, "accepted", null);
        tape.addProperty("revision", decisionRevision);
        decisionTape.add(tape);

        eventSequence++;
        JsonObject event = new JsonObject();
        event.addProperty("schema_version", "semantic-event/1.0.0");
        event.addProperty("sequence", eventSequence);
        event.addProperty("event_kind", "external_decision_boundary");
        event.addProperty("decision_revision", decisionRevision);
        event.addProperty("actor_seat", pending.get("seat").getAsInt() + 1);
        event.addProperty("decision_kind", pending.get("decision_class").getAsString());
        event.addProperty("before_checkpoint", before.sequence());
        event.addProperty("after_checkpoint", after.sequence());
        event.addProperty("before_privileged_state_sha256",
                before.payload().get("privileged_state_sha256").getAsString());
        event.addProperty("after_privileged_state_sha256",
                after.payload().get("privileged_state_sha256").getAsString());
        event.addProperty("before_public_state_sha256",
                before.payload().get("public_state_sha256").getAsString());
        event.addProperty("after_public_state_sha256",
                after.payload().get("public_state_sha256").getAsString());
        eventTape.add(event);
    }

    synchronized void recordRejectedDecision(JsonObject pending, JsonObject submitted, String reason) {
        decisionRevision++;
        JsonObject tape = decisionRecord(pending, submitted, "rejected", reason);
        tape.addProperty("revision", decisionRevision);
        decisionTape.add(tape);
    }

    synchronized JsonObject evidence(long seed) {
        JsonObject payload = new JsonObject();
        payload.addProperty("schema_version", "xmage-semantic-replay-evidence/1.0.0");
        payload.add("rules_rng_tape", XmageWs26RulesRngTape.snapshot(seed));
        payload.add("decision_tape", decisionTape.deepCopy());
        payload.add("event_tape", eventTape.deepCopy());
        payload.add("checkpoints", checkpoints.deepCopy());
        payload.addProperty("decision_tape_sha256", hash(decisionTape));
        payload.addProperty("event_tape_sha256", hash(eventTape));
        payload.addProperty("checkpoints_sha256", hash(checkpoints));
        return payload;
    }

    synchronized JsonObject currentState() {
        JsonArray actorViews = new JsonArray();
        for (Player player : players) {
            actorViews.add(ledger.snapshot(game, player, player));
        }
        JsonObject state = privilegedState(actorViews);
        state.addProperty("sha256", hash(state));
        return state;
    }

    private JsonObject decisionRecord(
            JsonObject pending,
            JsonObject submitted,
            String result,
            String rejection
    ) {
        JsonObject tape = new JsonObject();
        tape.addProperty("schema_version", "semantic-decision/1.0.0");
        tape.addProperty("actor_seat", pending.get("seat").getAsInt() + 1);
        tape.addProperty("decision_kind", pending.get("decision_class").getAsString());
        JsonArray offered = pending.getAsJsonArray("legal_options");
        JsonArray offeredIds = new JsonArray();
        List<String> seenSemanticIds = new ArrayList<>();
        for (JsonElement element : offered) {
            JsonObject option = element.getAsJsonObject();
            String semanticId = semanticOptionId(option);
            if (seenSemanticIds.contains(semanticId)) {
                throw new IllegalStateException("duplicate semantic option id in replay tape: " + semanticId);
            }
            seenSemanticIds.add(semanticId);
            offeredIds.add(semanticId);
        }
        tape.add("offered_semantic_option_ids", offeredIds);
        tape.addProperty("offered_options_sha256", hash(offeredIds));
        tape.add("selected_semantic_option_ids", semanticSubmittedIds(offered, submitted, "selected_option_ids"));
        tape.add("ordering", semanticSubmittedIds(offered, submitted, "ordering"));
        tape.add("numeric_choice",
                submitted.has("numeric_choice") ? submitted.get("numeric_choice").deepCopy() : JsonNull.INSTANCE);
        tape.addProperty("result", result);
        if (rejection == null) {
            tape.add("rejection", JsonNull.INSTANCE);
        } else {
            tape.addProperty("rejection", rejection);
        }
        return tape;
    }

    private static JsonArray semanticSubmittedIds(JsonArray offered, JsonObject submitted, String field) {
        JsonArray result = new JsonArray();
        if (!submitted.has(field) || submitted.get(field).isJsonNull()) {
            return result;
        }
        if (!submitted.get(field).isJsonArray()) {
            throw new IllegalStateException("replay submission field is not an array: " + field);
        }
        for (JsonElement selected : submitted.getAsJsonArray(field)) {
            String rawId = selected.getAsString();
            String semanticId = null;
            int matches = 0;
            for (JsonElement element : offered) {
                JsonObject option = element.getAsJsonObject();
                if (rawId.equals(option.get("option_id").getAsString())) {
                    semanticId = semanticOptionId(option);
                    matches++;
                }
            }
            if (matches != 1 || semanticId == null) {
                throw new IllegalStateException(
                        "submitted option id did not resolve exactly once in offered set: " + rawId
                );
            }
            result.add(semanticId);
        }
        return result;
    }

    private static String semanticOptionId(JsonObject option) {
        if (!option.has("option_id") || !option.get("option_id").isJsonPrimitive()) {
            throw new IllegalStateException("replay option is missing option_id");
        }
        String rawId = option.get("option_id").getAsString();
        String type = option.has("option_type") && option.get("option_type").isJsonPrimitive()
                ? option.get("option_type").getAsString() : "";
        if (!"pass_priority".equals(type)) {
            return rawId;
        }
        String label = option.has("label") && option.get("label").isJsonPrimitive()
                ? option.get("label").getAsString() : "";
        JsonElement metadata = option.get("metadata");
        if (!"Pass priority".equals(label)
                || metadata == null
                || !metadata.isJsonObject()
                || !metadata.getAsJsonObject().entrySet().isEmpty()) {
            throw new IllegalStateException(
                    "pass_priority semantic signature changed: " + option
            );
        }
        return PRIORITY_PASS_SEMANTIC_ID;
    }

    private JsonObject privilegedState(JsonArray actorViews) {
        JsonObject state = new JsonObject();
        state.addProperty("schema_version", "xmage-privileged-semantic-state/1.0.0");
        state.addProperty("turn", game.getState().getTurnNum());
        state.addProperty("player_count", players.size());
        state.add("actor_entitled_union", actorViews.deepCopy());

        JsonArray objects = new JsonArray();
        List<Map.Entry<UUID, String>> declared = new ArrayList<>(scenarioObjectIds.entrySet());
        declared.sort(Map.Entry.comparingByValue());
        for (Map.Entry<UUID, String> entry : declared) {
            UUID nativeId = entry.getKey();
            Card card = game.getCard(nativeId);
            JsonObject item = new JsonObject();
            item.addProperty("semantic_id", entry.getValue());
            Zone zone = game.getState().getZone(nativeId);
            item.addProperty("zone", zone == null ? "unknown" : zone.name().toLowerCase());
            if (card != null) {
                item.addProperty("card_name", card.getName());
                item.addProperty("owner_seat", seat(card.getOwnerId()));
                item.addProperty("zone_change_counter", card.getZoneChangeCounter(game));
            }
            Permanent permanent = game.getPermanent(nativeId);
            if (permanent != null) {
                item.addProperty("controller_seat", seat(permanent.getControllerId()));
                item.addProperty("tapped", permanent.isTapped());
                item.addProperty("damage", permanent.getDamage());
                item.addProperty("power", permanent.getPower().getValue());
                item.addProperty("toughness", permanent.getToughness().getValue());
                JsonObject counters = new JsonObject();
                for (CounterType type : CounterType.values()) {
                    int count = permanent.getCounters(game).getCount(type);
                    if (count != 0) {
                        counters.addProperty(type.name().toLowerCase(), count);
                    }
                }
                item.add("counters", counters);
            }
            objects.add(item);
        }
        state.add("scenario_objects", objects);
        return state;
    }

    private int seat(UUID playerId) {
        int zero = ledger.seat(playerId);
        return zero < 0 ? -1 : zero + 1;
    }

    private static JsonObject publicProjection(JsonObject actorView) {
        JsonObject copy = actorView.deepCopy();
        sanitizePublic(copy);
        return copy;
    }

    private static void sanitizePublic(JsonElement element) {
        if (element == null || element.isJsonNull() || element.isJsonPrimitive()) {
            return;
        }
        if (element.isJsonArray()) {
            for (JsonElement child : element.getAsJsonArray()) {
                sanitizePublic(child);
            }
            return;
        }
        JsonObject object = element.getAsJsonObject();
        for (String key : List.of(
                "hand", "known_library", "remembered_library_composition", "mana_pool",
                "viewer_player_id", "decision_subject_player_id", "decision_authority_player_id",
                "is_viewer", "is_decision_subject"
        )) {
            object.remove(key);
        }
        if (object.has("face_down") && object.get("face_down").isJsonPrimitive()
                && object.get("face_down").getAsBoolean() && object.has("name")) {
            object.addProperty("name", "Hidden card");
        }
        for (Map.Entry<String, JsonElement> entry : new ArrayList<>(object.entrySet())) {
            sanitizePublic(entry.getValue());
        }
    }

    static String hash(JsonElement value) {
        String canonical = canonicalize(value);
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException(exc);
        }
    }

    private static String canonicalize(JsonElement value) {
        if (value == null || value.isJsonNull() || value.isJsonPrimitive()) {
            return value == null ? "null" : value.toString();
        }
        if (value.isJsonArray()) {
            List<String> items = new ArrayList<>();
            for (JsonElement item : value.getAsJsonArray()) {
                items.add(canonicalize(item));
            }
            return "[" + String.join(",", items) + "]";
        }
        JsonObject object = value.getAsJsonObject();
        List<String> keys = new ArrayList<>(object.keySet());
        keys.sort(String::compareTo);
        List<String> fields = new ArrayList<>();
        Gson gson = new Gson();
        for (String key : keys) {
            fields.add(gson.toJson(key) + ":" + canonicalize(object.get(key)));
        }
        return "{" + String.join(",", fields) + "}";
    }
}
