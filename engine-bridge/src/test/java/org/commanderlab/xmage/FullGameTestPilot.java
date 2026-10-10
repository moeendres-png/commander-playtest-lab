package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * #662 test support: a deterministic test pilot for real-deck full games.
 *
 * <p>It answers by semantic key only (never by engine id or position among equal
 * labels): play a land when offered, pay with advancing pool mana or the first mana
 * ability, otherwise pass priority; numeric decisions take the minimum, joint
 * vectors fill legs in order to the minimum total, selections take the minimum
 * count of the smallest keys. A test declaration, not a production pilot.</p>
 */
final class FullGameTestPilot {

    static final List<String> DECKS = List.of(
            "data/decks/rogshai_current.json",
            "data/decks/opponents/kaervek/current/deck.json",
            "data/opponents/hosts_of_mordor_precon.json",
            "data/opponents/lorehold_spirit_precon.json");

    private FullGameTestPilot() {
    }

    static XmageFullGameSession realDeckSession(String gameId, int players, long seed) throws IOException {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        for (int seat = 0; seat < players; seat++) {
            JsonObject root = JsonParser.parseString(Files.readString(
                    XmageNativeStateRestorationTest.repoRoot().resolve(DECKS.get(seat % DECKS.size())),
                    StandardCharsets.UTF_8)).getAsJsonObject();
            if (root.has("deck") && root.get("deck").isJsonObject()) {
                root = root.getAsJsonObject("deck");
            }
            List<String> main = new ArrayList<>();
            List<String> commanders = new ArrayList<>();
            for (JsonElement element : root.getAsJsonArray("cards")) {
                JsonObject card = element.getAsJsonObject();
                List<String> target = "commander".equals(card.get("zone").getAsString()) ? commanders : main;
                for (int copy = 0; copy < card.get("quantity").getAsInt(); copy++) {
                    target.add(card.get("oracle_name").getAsString());
                }
            }
            handles.add(importer.importCommanderDeck(
                    "pilot-deck-" + seat, "0".repeat(64), main, commanders).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(gameId, handles, 0, 40, seed, importer);
        session.start();
        return session;
    }

    /** Answer up to {@code decisions} decisions; returns how many were answered. */
    static int play(XmageFullGameSession session, int decisions) {
        int answered = 0;
        while (answered < decisions) {
            JsonObject status = session.pendingDecisionPayload();
            if (status.get("decision") == null || status.get("decision").isJsonNull()) {
                return answered;
            }
            JsonObject legal = session.legalActionsPayload();
            session.submitAction(choose(legal));
            answered++;
        }
        return answered;
    }

    static JsonObject choose(JsonObject legal) {
        List<JsonObject> actions = new ArrayList<>();
        legal.getAsJsonArray("actions").forEach(element -> actions.add(element.getAsJsonObject()));
        actions.sort(Comparator.comparing(FullGameTestPilot::key));
        JsonObject context = legal.getAsJsonObject("decision").getAsJsonObject("context");
        // The smallest semantic key, never a position among the engine's options.
        JsonObject first = actions.stream().min(Comparator.comparing(FullGameTestPilot::key)).orElseThrow();
        JsonObject proposal = proposal(legal, first);
        if (context.has("numeric_legs")) {
            JsonArray vector = new JsonArray();
            int remaining = context.get("numeric_total_min").getAsInt();
            for (JsonElement leg : context.getAsJsonArray("numeric_legs")) {
                int take = Math.max(leg.getAsJsonObject().get("min").getAsInt(),
                        Math.min(leg.getAsJsonObject().get("max").getAsInt(), remaining));
                vector.add(take);
                remaining -= take;
            }
            proposal.getAsJsonObject("choices").add("numeric_choices", vector);
            return proposal;
        }
        if (context.has("numeric_min") && context.has("numeric_max")
                && "structural_decision".equals(first.get("action_type").getAsString())) {
            proposal.getAsJsonObject("choices").addProperty("numeric_choice", context.get("numeric_min").getAsInt());
            return proposal;
        }
        String cls = legal.get("decision_class").getAsString();
        if ("priority".equals(cls)) {
            for (JsonObject action : actions) {
                if (label(action).contains("Play ")) {
                    return proposal(legal, action);
                }
            }
            for (JsonObject action : actions) {
                if ("pass_priority".equals(type(action))) {
                    return proposal(legal, action);
                }
            }
        }
        if ("mana_payment".equals(cls)) {
            for (JsonObject action : actions) {
                if ("mana_pool".equals(type(action))
                        && action.getAsJsonObject("metadata").getAsJsonObject("xmage_option_metadata")
                        .get("advances_payment").getAsBoolean()) {
                    return proposal(legal, action);
                }
            }
            for (JsonObject action : actions) {
                if ("mana_ability".equals(type(action))) {
                    return proposal(legal, action);
                }
            }
        }
        int min = legal.getAsJsonObject("decision").get("minimum_selections").getAsInt();
        if (min == 0 && legal.getAsJsonObject("decision").get("maximum_selections").getAsInt() > 1) {
            JsonObject none = proposal(legal, first);
            none.addProperty("legal_action_id", "");
            none.addProperty("action_type", "structural_decision");
            none.getAsJsonObject("choices").add("selected_option_ids", new JsonArray());
            return none;
        }
        return proposal;
    }

    static String key(JsonObject action) {
        return type(action) + "|" + XmageFullGameReplay.normalizeLabel(label(action));
    }

    static String type(JsonObject action) {
        return action.getAsJsonObject("metadata").get("option_type").getAsString();
    }

    static String label(JsonObject action) {
        JsonObject metadata = action.getAsJsonObject("metadata");
        return metadata.has("label") ? metadata.get("label").getAsString() : "";
    }

    static JsonObject proposal(JsonObject legal, JsonObject action) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "pilot-" + legal.get("decision_offset").getAsLong());
        proposal.addProperty("actor_id", action.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", action.get("action_id").getAsString());
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", legal.get("decision_id").getAsString());
        choices.addProperty("decision_offset", legal.get("decision_offset").getAsLong());
        proposal.add("choices", choices);
        return proposal;
    }

    static Path writeTemp(String prefix, JsonObject document) throws IOException {
        Path file = Files.createTempFile(prefix, ".json");
        Files.writeString(file, document.toString(), StandardCharsets.UTF_8);
        file.toFile().deleteOnExit();
        return file;
    }
}
