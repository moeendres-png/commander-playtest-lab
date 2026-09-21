package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * FULL107 transport spike (executor workstream): scripted decision drive
 * through the mulligan phase of a live 4P game using ONLY projected legal
 * actions.
 *
 * <p>Selection rule mirrors fixture decision scripts: match exactly one
 * provider-offered action per decision (fail closed on zero or multiple
 * matches — no first/random/default fallback). Every submission must carry
 * an explicit {@code next_actions_status} (never silent), and the game must
 * advance past mulligan to priority. Uses real RogShai decks on the pinned
 * engine; seed 424242 aligns with the FULL107 manifest seed authority.
 * Self-contained (no shared test helpers) to avoid touching sealed tests.</p>
 */
class XmageFullGameMulliganDriveTest {

    @Test
    void scriptedKeepDriveResolvesMulliganPhaseWithExplicitStatus() throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "full107-mulligan-drive", handles, 0, 40, 424242L, importer);
        session.start();

        List<String> resolvedDecisions = new ArrayList<>();
        for (int step = 0; step < 12; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("choose_object".equals(decisionClass)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                // Deterministic setup rule (not a fallback): the choosing actor
                // selects itself as starting player; fail closed otherwise.
                JsonObject self = singleSelfAction(legal, actorId);
                JsonObject started = session.submitAction(genericProposal(
                        "full107-drive-start-" + step, actorId,
                        self.get("action_id").getAsString(),
                        self.get("action_type").getAsString()));
                assertEquals(pending.get("decision_id").getAsString(),
                        started.get("executed_decision_id").getAsString());
                assertTrue(started.has("next_actions_status"));
                continue;
            }
            if (!"mulligan".equals(decisionClass)) {
                break;
            }
            JsonObject keep = singleKeep(legal);
            JsonObject after = session.submitAction(genericProposal(
                    "full107-drive-" + step,
                    legal.get("actor_id").getAsString(),
                    keep.get("action_id").getAsString(),
                    keep.get("action_type").getAsString()));
            assertEquals(pending.get("decision_id").getAsString(),
                    after.get("executed_decision_id").getAsString());
            assertTrue(after.has("next_actions_status"),
                    "submitAction must report explicit next_actions_status");
            String status = after.get("next_actions_status").getAsString();
            assertTrue(status.equals("projected") || status.equals("no_pending_decision"),
                    "unexpected next_actions_status: " + status);
            resolvedDecisions.add(pending.get("decision_id").getAsString());
        }

        assertTrue(resolvedDecisions.size() >= 4,
                "expected all four seats to resolve mulligan, got " + resolvedDecisions.size());

        JsonObject payload = session.pendingDecisionPayload();
        assertTrue(!payload.get("decision").isJsonNull(), "game must continue past mulligan");
        assertEquals("priority",
                payload.getAsJsonObject("decision").get("decision_class").getAsString());
    }

    private static JsonObject singleSelfAction(JsonObject legal, String actorId) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (action.get("action_id").getAsString().endsWith(":" + actorId)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "expected exactly one self action (fail closed)");
        return matches.get(0);
    }

    private static JsonObject singleKeep(JsonObject legal) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!"mulligan".equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if ("keep".equals(optionType)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "expected exactly one keep action (fail closed)");
        return matches.get(0);
    }

    private static JsonObject genericProposal(
            String proposalId, String actorId, String actionId, String actionType) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "full107-mulligan-drive");
        return proposal;
    }

    private static List<String> importCopies(
            XmageDeckImporter importer, RuntimeDeck deck, int count) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deck.deckId(), deck.deckHash(), deck.mainboard(), deck.commanders());
            handles.add(imported.deckHandle());
        }
        return List.copyOf(handles);
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck() throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        java.nio.file.Path path = java.nio.file.Path.of(
                repoRoot, "data", "decks", "rogshai_current.json").normalize();
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
        return new RuntimeDeck(
                root.get("deck_id").getAsString(),
                root.get("deck_hash").getAsString(),
                List.copyOf(mainboard),
                List.copyOf(commanders));
    }

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders) {
    }
}
