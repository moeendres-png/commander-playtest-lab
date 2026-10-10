package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

/**
 * #662 SLOT-06 (c): semantic keys for the full-game replay record.
 *
 * <p>Engine ids are fresh per game, so a recorded choice names its option by a
 * semantic key: option type and label, with engine object ids masked, plus the
 * ordinal among options that share that text. The offered-option digest is the
 * SHA-256 of the sorted keys, so a replay can check that the engine offered the
 * same set at the same point. The record, the keys and the digests are
 * orchestration-only (ruling R4): they never enter a pilot frame.</p>
 */
final class XmageFullGameReplay {

    static final String SCHEMA_VERSION = "xmage-full-game-replay/1.0.0";

    private XmageFullGameReplay() {
    }

    /** The label with engine object ids masked: "[270]" tags and full UUIDs. */
    static String normalizeLabel(String label) {
        if (label == null) {
            return "";
        }
        return label
                .replaceAll("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>")
                .replaceAll("\\[[0-9a-f]{3}\\]", "[id]");
    }

    /** One key per option, in option order: type|label#ordinal. */
    static List<String> semanticKeys(JsonArray legalOptions) {
        List<String> keys = new ArrayList<>();
        Map<String, Integer> seen = new HashMap<>();
        for (JsonElement element : legalOptions) {
            JsonObject option = element.getAsJsonObject();
            String type = option.has("option_type") && !option.get("option_type").isJsonNull()
                    ? option.get("option_type").getAsString() : "generic";
            String label = option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : "";
            String base = type + "|" + normalizeLabel(label);
            int ordinal = seen.merge(base, 1, Integer::sum);
            keys.add(base + "#" + ordinal);
        }
        return keys;
    }

    static List<String> optionIds(JsonArray legalOptions) {
        List<String> ids = new ArrayList<>();
        for (JsonElement element : legalOptions) {
            JsonObject option = element.getAsJsonObject();
            ids.add(option.has("option_id") ? option.get("option_id").getAsString() : "");
        }
        return ids;
    }

    /** Digest of the decision's class, bounds, numeric domain and sorted option keys. */
    static String offeredDigest(JsonObject request) {
        List<String> keys = new ArrayList<>(semanticKeys(request.getAsJsonArray("legal_options")));
        keys.sort(String::compareTo);
        JsonObject basis = new JsonObject();
        basis.addProperty("decision_class", request.get("decision_class").getAsString());
        basis.addProperty("min", request.get("minimum_selections").getAsInt());
        basis.addProperty("max", request.get("maximum_selections").getAsInt());
        JsonObject context = request.has("context") && request.get("context").isJsonObject()
                ? request.getAsJsonObject("context") : new JsonObject();
        for (String field : List.of("numeric_min", "numeric_max", "numeric_total_min", "numeric_total_max")) {
            if (context.has(field)) {
                basis.add(field, context.get(field));
            }
        }
        if (context.has("numeric_legs")) {
            JsonArray legs = new JsonArray();
            for (JsonElement leg : context.getAsJsonArray("numeric_legs")) {
                JsonObject bounds = new JsonObject();
                bounds.add("min", leg.getAsJsonObject().get("min"));
                bounds.add("max", leg.getAsJsonObject().get("max"));
                legs.add(bounds);
            }
            basis.add("numeric_legs", legs);
        }
        JsonArray sorted = new JsonArray();
        keys.forEach(sorted::add);
        basis.add("keys", sorted);
        return sha256(basis.toString());
    }

    static String sha256(String text) {
        try {
            return HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException(exc);
        }
    }
}
