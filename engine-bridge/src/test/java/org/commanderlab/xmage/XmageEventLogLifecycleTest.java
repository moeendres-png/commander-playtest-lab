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
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageEventLogLifecycleTest {

    @Test
    void eventLogLinksRealPriorityActionAndCleanupAllowsSecondGame()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);

        List<String> firstHandles = importCopies(importer, deck, 4);
        XmageGameManager.CreateResult first = manager.createCommanderGame(
                "b4d-test/first",
                firstHandles,
                0,
                40,
                true
        );
        manager.startGame(first.gameHandle());

        XmageGameManager.EventLogSnapshot started = manager.exportEventLog(
                first.gameHandle(),
                0L
        );
        assertEquals(2L, started.latestEventOffset());
        assertEquals(2, started.totalEvents());
        assertEquals("game_created", event(started.log(), 0).get("event_type").getAsString());
        assertEquals("game_started", event(started.log(), 1).get("event_type").getAsString());
        assertEquals(64, started.log().get("log_sha256").getAsString().length());

        XmageGameManager.StateSnapshot beforeState = manager.snapshotState(first.gameHandle());
        assertEquals(2L, beforeState.state().get("event_sequence").getAsLong());

        XmageGameManager.LegalActionsSnapshot before = manager.legalActions(first.gameHandle());
        JsonObject pass = uniqueAction(before, "pass_priority");
        String preHash = manager.stateHash(first.gameHandle());
        Game game = manager.requireGame(first.gameHandle());
        XmageActionExecutor.ExecutionResult executed = XmageActionExecutor.passPriority(
                game,
                before,
                before.decisionId(),
                before.actorId(),
                pass.get("action_id").getAsString()
        );
        String postHash = manager.stateHash(first.gameHandle());
        manager.recordExternalAction(first.gameHandle(), executed, preHash, postHash);

        XmageGameManager.EventLogSnapshot afterPass = manager.exportEventLog(
                first.gameHandle(),
                2L
        );
        assertEquals(3L, afterPass.latestEventOffset());
        assertEquals(1, afterPass.totalEvents());
        JsonObject priorityEvent = event(afterPass.log(), 0);
        assertEquals("priority_passed", priorityEvent.get("event_type").getAsString());
        assertEquals(before.actorId(), priorityEvent.get("actor_id").getAsString());
        assertEquals(64, priorityEvent.get("pre_state_hash").getAsString().length());
        assertEquals(64, priorityEvent.get("post_state_hash").getAsString().length());
        assertEquals(
                before.decisionId(),
                priorityEvent.getAsJsonObject("payload").get("decision_id").getAsString()
        );
        assertEquals(
                pass.get("action_id").getAsString(),
                priorityEvent.getAsJsonObject("payload").get("action_id").getAsString()
        );

        XmageGameManager.ShutdownResult firstShutdown = manager.shutdownGame(first.gameHandle());
        assertEquals(4L, firstShutdown.finalEventOffset());
        assertEquals(4, firstShutdown.releasedDeckHandleCount());
        assertEquals(0, firstShutdown.storedGameCount());
        assertEquals(
                "game_shutdown",
                event(firstShutdown.finalLog(), 3).get("event_type").getAsString()
        );
        assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.requireGame(first.gameHandle())
        );

        List<String> secondHandles = importCopies(importer, deck, 4);
        XmageGameManager.CreateResult second = manager.createCommanderGame(
                "b4d-test/second",
                secondHandles,
                1,
                40,
                false
        );
        manager.startGame(second.gameHandle());
        assertEquals(1, manager.storedGameCount());
        XmageGameManager.ShutdownResult secondShutdown = manager.shutdownGame(second.gameHandle());
        assertEquals(0, secondShutdown.storedGameCount());
        assertEquals(3L, secondShutdown.finalEventOffset());
        assertFalse(secondShutdown.finalLog().getAsJsonArray("events").isEmpty());
    }

    private static JsonObject event(JsonObject log, int index) {
        return log.getAsJsonArray("events").get(index).getAsJsonObject();
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
