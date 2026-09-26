package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
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
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageStateObservationTest {

    @Test
    void realStartedGameProducesTruthfulReadOnlySnapshot()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageGameManager manager = new XmageGameManager(importer);

        XmageGameManager.CreateResult created =
                manager.createCommanderGame(
                        "b4a-test/state",
                        handles,
                        0,
                        40
                );

        assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.snapshotState(created.gameHandle())
        );

        manager.startGame(created.gameHandle());

        XmageGameManager.StateSnapshot first =
                manager.snapshotState(created.gameHandle());
        XmageGameManager.StateSnapshot second =
                manager.snapshotState(created.gameHandle());

        assertEquals("b4a-test/state", first.gameId());
        assertNotNull(first.engineGameId());
        assertEquals(1L, first.stateObservationOffset());
        assertEquals(2L, second.stateObservationOffset());

        JsonObject state = first.state();
        assertEquals("b4a-test/state", state.get("game_id").getAsString());
        assertTrue(state.get("seed").isJsonNull());
        assertTrue(state.get("rng_counter").isJsonNull());
        assertEquals("in_progress", state.get("status").getAsString());
        assertEquals(1, state.get("turn_number").getAsInt());
        assertEquals("beginning", state.get("phase").getAsString());
        assertEquals("upkeep", state.get("step").getAsString());
        assertNotNull(state.get("active_player_id"));
        assertNotNull(state.get("priority_player_id"));

        JsonArray players = state.getAsJsonArray("players");
        assertEquals(4, players.size());
        for (int seat = 0; seat < players.size(); seat++) {
            JsonObject player = players.get(seat).getAsJsonObject();
            assertEquals(seat, player.get("seat").getAsInt());
            assertEquals(40, player.get("life").getAsInt());
            assertEquals(0, player.get("poison_counters").getAsInt());
            assertFalse(player.get("has_lost").getAsBoolean());

            JsonObject zones = player.getAsJsonObject("zones");
            assertEquals(7, zones.getAsJsonArray("hand").size());
            assertEquals(91, zones.getAsJsonArray("library").size());
            assertEquals(2, zones.getAsJsonArray("command").size());
            assertEquals(0, zones.getAsJsonArray("battlefield").size());
            assertEquals(0, zones.getAsJsonArray("graveyard").size());
            assertEquals(0, zones.getAsJsonArray("exile").size());
        }

        assertEquals(0, state.getAsJsonArray("stack").size());
        assertEquals(0, state.getAsJsonArray("legal_actions").size());
        assertEquals(0, state.getAsJsonArray("winner_ids").size());
        assertEquals(2, state.get("event_sequence").getAsInt());
    }

    private static List<String> importCopies(
            XmageDeckImporter importer,
            RuntimeDeck deck,
            int count
    ) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported =
                    importer.importCommanderDeck(
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
