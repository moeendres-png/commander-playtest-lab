package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.constants.RangeOfInfluence;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS204 actual-card generic submission on the dedicated full-game lane.
 *
 * <p>Uses real RogShai decks on the pinned engine. Every selection is an
 * offered native option projected through
 * {@link XmageFullGameActionProjection}; XMage executes natively. Negative
 * controls prove stale/wrong/unknown submissions fail closed without
 * advancing the native decision.</p>
 */
class XmageFullGameGenericActionSubmissionTest {

    @Test
    void realMulliganKeepThroughGenericBoundaryAdvancesWithNegativeControls()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws204-generic-mulligan",
                handles,
                0,
                40,
                7017L,
                importer
        );
        session.start();

        JsonObject first = waitForDecision(session, "mulligan", 30);
        JsonObject legal = session.legalActionsPayload();
        assertEquals(first.get("decision_id").getAsString(), legal.get("decision_id").getAsString());
        assertTrue(legal.getAsJsonArray("actions").size() >= 2);
        assertFalse(legal.get("global_capability_promoted").getAsBoolean());
        assertTrue(legal.get("decision_scoped").getAsBoolean());

        String decisionId = legal.get("decision_id").getAsString();
        String actorId = legal.get("actor_id").getAsString();
        JsonObject keep = singleActionOfType(legal, "mulligan", "keep");
        String keepActionId = keep.get("action_id").getAsString();

        // Wrong actor must fail closed without advancing.
        JsonObject wrongActor = genericProposal("ws204-wrong", "intruder-actor", keepActionId, "mulligan");
        assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.submitAction(wrongActor)
        );
        assertEquals(decisionId, session.legalActionsPayload().get("decision_id").getAsString());

        // Unknown option must fail closed without advancing.
        JsonObject unknown = genericProposal("ws204-unknown", actorId, decisionId + ":ghost-option", "mulligan");
        XmageFullGameDecisionController.DecisionException unknownFailure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.submitAction(unknown)
        );
        assertTrue(unknownFailure.getMessage().contains("ILLEGAL_ACTION"));
        assertEquals(decisionId, session.legalActionsPayload().get("decision_id").getAsString());

        // Valid keep advances the native decision.
        JsonObject valid = genericProposal("ws204-keep", actorId, keepActionId, "mulligan");
        JsonObject after = session.submitAction(valid);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
        assertEquals(keepActionId, after.get("executed_action_id").getAsString());

        // Replay of the consumed decision is stale.
        XmageFullGameDecisionController.DecisionException replay = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.submitAction(valid)
        );
        assertTrue(replay.getMessage().contains("STALE_DECISION"));
    }

    @Test
    void realPriorityPassThroughGenericBoundaryAdvancesWithStaleProtection()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws204-generic-priority",
                handles,
                0,
                40,
                7017L,
                importer
        );
        session.start();

        answerUntil(session, "mulligan", "keep", 8);
        JsonObject legal = waitForDecision(session, "priority", 60);
        String decisionId = legal.get("decision_id").getAsString();
        String actorId = legal.get("actor_id").getAsString();
        JsonObject pass = singleActionOfType(session.legalActionsPayload(), "pass_priority", null);
        String passActionId = pass.get("action_id").getAsString();

        JsonObject valid = genericProposal("ws204-pass", actorId, passActionId, "pass_priority");
        JsonObject after = session.submitAction(valid);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());

        JsonObject stale = genericProposal("ws204-stale", actorId, passActionId, "pass_priority");
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.submitAction(stale)
        );
        assertTrue(failure.getMessage().contains("STALE_DECISION"));
    }

    @Test
    void realCleanupDiscardThroughGenericBoundaryUnblocksCensusStopPoint()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws204-generic-discard",
                handles,
                0,
                40,
                7017L,
                importer
        );
        session.start();

        int answered = 0;
        boolean discardAnswered = false;
        for (int step = 0; step < 80; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            JsonArray actions = legal.getAsJsonArray("actions");
            assertTrue(actions.size() > 0, "generic projection must not fabricate empty offers");
            assertEquals(pending.get("decision_id").getAsString(), legal.get("decision_id").getAsString());

            String actionId;
            String actionType;
            if ("mulligan".equals(decisionClass)) {
                JsonObject keep = singleActionOfType(legal, "mulligan", "keep");
                actionId = keep.get("action_id").getAsString();
                actionType = "mulligan";
            } else if ("priority".equals(decisionClass)) {
                JsonObject pass = singleActionOfType(legal, "pass_priority", null);
                actionId = pass.get("action_id").getAsString();
                actionType = "pass_priority";
            } else if ("declare_attacker".equals(decisionClass)) {
                JsonObject hold = singleActionOfType(legal, "declare_attackers", "hold_attacker");
                actionId = hold.get("action_id").getAsString();
                actionType = "declare_attackers";
            } else if ("declare_blocker".equals(decisionClass)) {
                // Zero blockers: empty selection is the Rules-neutral reachability answer.
                JsonObject proposal = genericProposal("ws204-empty-block", actorId, "", "declare_blockers");
                JsonArray empty = new JsonArray();
                proposal.getAsJsonObject("choices").add("selected_option_ids", empty);
                // Empty selection requires no legal_action_id binding; use choices-only form.
                JsonObject emptyProposal = new JsonObject();
                emptyProposal.addProperty("proposal_id", "ws204-empty-block");
                emptyProposal.addProperty("actor_id", actorId);
                emptyProposal.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
                emptyProposal.addProperty("action_type", "structural_decision");
                emptyProposal.add("target_ids", new JsonArray());
                emptyProposal.add("selected_modes", new JsonArray());
                JsonObject choices = new JsonObject();
                choices.add("selected_option_ids", empty);
                choices.add("ordering", new JsonArray());
                emptyProposal.add("choices", choices);
                session.submitAction(emptyProposal);
                answered++;
                continue;
            } else if ("choose_object".equals(decisionClass)
                    && pending.get("prompt").getAsString().contains("starting player")) {
                actionId = actions.get(0).getAsJsonObject().get("action_id").getAsString();
                actionType = actions.get(0).getAsJsonObject().get("action_type").getAsString();
            } else if ("choose_object".equals(decisionClass)) {
                // Turn-1 cleanup discard: the sealed census stop point. Answering
                // any single offered hand card through the generic boundary proves
                // B4-D transport beyond pass/keep without claiming behavior credit.
                JsonObject first = actions.get(0).getAsJsonObject();
                actionId = first.get("action_id").getAsString();
                actionType = first.get("action_type").getAsString();
                discardAnswered = true;
            } else {
                break;
            }
            session.submitAction(genericProposal("ws204-step-" + step, actorId, actionId, actionType));
            answered++;
            if (discardAnswered) {
                break;
            }
        }
        assertTrue(discardAnswered, "generic boundary must answer the census cleanup discard");
        assertTrue(answered >= 38, "must advance at least through the sealed 37-decision prefix");
    }

    @Test
    void concedeRemainsExplicitlyFailClosed() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "ws204-concede",
                RangeOfInfluence.ALL,
                controller
        );
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> player.concede(null)
        );
        assertTrue(failure.getMessage().contains("OUT_OF_SCOPE_DECISION"));
    }

    private static void answerUntil(
            XmageFullGameSession session,
            String decisionClass,
            String optionType,
            int budget
    ) {
        for (int step = 0; step < budget; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                return;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            if (!decisionClass.equals(pending.get("decision_class").getAsString())) {
                return;
            }
            JsonObject legal = session.legalActionsPayload();
            JsonObject action = singleActionOfType(legal, actionTypeFor(optionType), optionType);
            session.submitAction(genericProposal(
                    "ws204-fill-" + step,
                    legal.get("actor_id").getAsString(),
                    action.get("action_id").getAsString(),
                    action.get("action_type").getAsString()
            ));
        }
    }

    private static String actionTypeFor(String optionType) {
        if ("keep".equals(optionType) || "mulligan".equals(optionType)) {
            return "mulligan";
        }
        return optionType;
    }

    private static JsonObject waitForDecision(
            XmageFullGameSession session,
            String decisionClass,
            int budget
    ) {
        for (int step = 0; step < budget; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (!payload.get("decision").isJsonNull()
                    && decisionClass.equals(
                            payload.getAsJsonObject("decision").get("decision_class").getAsString())) {
                return session.legalActionsPayload();
            }
            JsonObject pending = payload.get("decision").isJsonNull()
                    ? null : payload.getAsJsonObject("decision");
            if (pending == null) {
                break;
            }
            String currentClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("mulligan".equals(currentClass)) {
                JsonObject keep = singleActionOfType(legal, "mulligan", "keep");
                session.submitAction(genericProposal(
                        "ws204-wait-" + step, actorId,
                        keep.get("action_id").getAsString(), "mulligan"));
            } else if ("choose_object".equals(currentClass)
                    && pending.get("prompt").getAsString().contains("starting player")) {
                JsonArray actions = legal.getAsJsonArray("actions");
                JsonObject first = actions.get(0).getAsJsonObject();
                session.submitAction(genericProposal(
                        "ws204-wait-" + step, actorId,
                        first.get("action_id").getAsString(),
                        first.get("action_type").getAsString()));
            } else {
                break;
            }
        }
        JsonObject legal = session.legalActionsPayload();
        assertEquals(decisionClass, legal.get("decision_class").getAsString());
        return legal;
    }

    private static JsonObject singleActionOfType(JsonObject legal, String actionType, String optionType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            if (optionType != null) {
                JsonObject metadata = action.getAsJsonObject("metadata");
                String actual = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                        ? metadata.get("option_type").getAsString() : "";
                if (!optionType.equals(actual)) {
                    continue;
                }
            }
            matches.add(action);
        }
        assertEquals(1, matches.size(), "expected exactly one " + actionType + "/" + optionType);
        return matches.get(0);
    }

    private static JsonObject genericProposal(
            String proposalId,
            String actorId,
            String actionId,
            String actionType
    ) {
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
        proposal.addProperty("policy_name", "ws204-generic-regression");
        return proposal;
    }

    private static List<String> importCopies(
            XmageDeckImporter importer,
            RuntimeDeck deck,
            int count
    ) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deck.deckId(),
                    deck.deckHash(),
                    deck.mainboard(),
                    deck.commanders()
            );
            handles.add(imported.deckHandle());
        }
        return List.copyOf(handles);
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck()
            throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        java.nio.file.Path path = java.nio.file.Path.of(
                repoRoot,
                "data",
                "decks",
                "rogshai_current.json"
        ).normalize();
        JsonObject root = JsonParser.parseString(
                Files.readString(path, StandardCharsets.UTF_8)
        ).getAsJsonObject();
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
                List.copyOf(commanders)
        );
    }

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders
    ) {
    }
}
