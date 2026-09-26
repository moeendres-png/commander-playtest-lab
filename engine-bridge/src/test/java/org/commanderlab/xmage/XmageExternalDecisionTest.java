package org.commanderlab.xmage;

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
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageExternalDecisionTest {

    @Test
    void realFirstPriorityProducesStableFailClosedLegalActions()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageGameManager manager = new XmageGameManager(importer);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "b4b-test/priority",
                handles,
                0,
                40,
                true
        );
        assertTrue(created.externalControl());

        XmageGameManager.StartResult started = manager.startGame(created.gameHandle());
        assertTrue(started.externalControl());
        assertTrue(started.paused());
        assertEquals(1, started.turnNumber());

        Game game = manager.requireGame(created.gameHandle());
        assertEquals("UPKEEP", game.getTurnStepType().name());
        assertNotNull(game.getPriorityPlayerId());

        XmageGameManager.LegalActionsSnapshot first = manager.legalActions(created.gameHandle());
        XmageGameManager.LegalActionsSnapshot second = manager.legalActions(created.gameHandle());

        assertEquals("priority", first.decisionKind());
        assertEquals(game.getPriorityPlayerId().toString(), first.actorId());
        assertEquals(first.decisionOffset(), second.decisionOffset());
        assertEquals(first.decisionId(), second.decisionId());
        assertEquals(
                first.actions().stream().map(JsonObject::toString).toList(),
                second.actions().stream().map(JsonObject::toString).toList()
        );

        assertTrue(
                first.actions().stream().anyMatch(
                        action -> "pass_priority".equals(
                                action.get("action_type").getAsString()
                        )
                )
        );
        assertTrue(
                first.actions().stream().allMatch(
                        action -> first.actorId().equals(
                                action.get("actor_id").getAsString()
                        )
                )
        );
        assertTrue(
                first.actions().stream().map(
                        action -> action.get("action_id").getAsString()
                ).distinct().count() == first.actions().size()
        );

        for (JsonObject action : first.actions()) {
            assertEquals(64, action.get("action_id").getAsString().length());
            assertTrue(action.has("metadata"));
            assertTrue(action.has("choices_schema"));
            assertTrue(action.has("cost"));
        }

        /*
         * B4-B proves the first real priority decision class only. Advancing
         * through upkeep to main phase and proving a Rograkh cast belongs to
         * B4-C, where PASS_PRIORITY is actually submitted to XMage.
         */
        assertFalse(first.decisionId().isBlank());
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
