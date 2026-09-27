package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.io.IOException;
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

class XmageActionSubmissionTest {

    @Test
    void realPriorityPassesReachAndCastRograkhWithStaleProtection()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        assertTrue(deck.commanders().contains("Rograkh, Son of Rohgahh"));

        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "b4c-test/rograkh",
                handles,
                0,
                40,
                true
        );
        manager.startGame(created.gameHandle());
        Game game = manager.requireGame(created.gameHandle());

        XmageGameManager.LegalActionsSnapshot first = manager.legalActions(created.gameHandle());
        JsonObject firstPass = uniqueAction(first, "pass_priority");
        XmageActionExecutor.passPriority(
                game,
                first,
                first.decisionId(),
                first.actorId(),
                firstPass.get("action_id").getAsString()
        );
        XmageGameManager.LegalActionsSnapshot afterFirst = manager.legalActions(created.gameHandle());
        assertNotEquals(first.decisionId(), afterFirst.decisionId());
        assertThrows(
                XmageActionExecutor.ActionException.class,
                () -> XmageActionExecutor.passPriority(
                        game,
                        afterFirst,
                        first.decisionId(),
                        first.actorId(),
                        firstPass.get("action_id").getAsString()
                )
        );

        boolean cast = false;
        for (int iteration = 0; iteration < 64; iteration++) {
            XmageGameManager.LegalActionsSnapshot current = manager.legalActions(created.gameHandle());
            List<JsonObject> commanders = current.actions().stream()
                    .filter(action -> "cast_commander".equals(action.get("action_type").getAsString()))
                    .filter(action -> action.getAsJsonObject("metadata").get("submission_ready").getAsBoolean())
                    .filter(action -> !action.getAsJsonObject("metadata")
                            .get("choice_control_required").getAsBoolean())
                    .toList();

            if (!commanders.isEmpty()) {
                assertEquals(1, commanders.size());
                JsonObject action = commanders.get(0);
                JsonObject proposal = proposal(current, action);
                XmageActionExecutor.ExecutionResult executed = XmageActionExecutor.submitAction(
                        game,
                        current,
                        current.decisionId(),
                        proposal
                );
                assertEquals("cast_commander", executed.actionType());
                assertEquals("Rograkh, Son of Rohgahh", executed.sourceName());
                assertFalse(game.getStack().isEmpty());

                XmageGameManager.LegalActionsSnapshot afterCast =
                        manager.legalActions(created.gameHandle());
                assertNotEquals(current.decisionId(), afterCast.decisionId());
                assertThrows(
                        XmageActionExecutor.ActionException.class,
                        () -> XmageActionExecutor.submitAction(
                                game,
                                afterCast,
                                current.decisionId(),
                                proposal
                        )
                );
                cast = true;
                break;
            }

            JsonObject pass = uniqueAction(current, "pass_priority");
            XmageActionExecutor.passPriority(
                    game,
                    current,
                    current.decisionId(),
                    current.actorId(),
                    pass.get("action_id").getAsString()
            );
        }

        assertTrue(cast, "B4-C did not reach a real submission-ready Rograkh cast");
    }

    private static JsonObject uniqueAction(
            XmageGameManager.LegalActionsSnapshot snapshot,
            String actionType
    ) {
        List<JsonObject> matches = snapshot.actions().stream()
                .filter(action -> actionType.equals(action.get("action_type").getAsString()))
                .toList();
        assertEquals(1, matches.size());
        return matches.get(0);
    }

    private static JsonObject proposal(
            XmageGameManager.LegalActionsSnapshot snapshot,
            JsonObject action
    ) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "b4c-test-proposal");
        proposal.addProperty("actor_id", snapshot.actorId());
        proposal.addProperty("legal_action_id", action.get("action_id").getAsString());
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        proposal.addProperty("source_object_id", action.get("source_object_id").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        proposal.add("choices", new JsonObject());
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "b4c-java-regression");
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

        Path path = Path.of(
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
