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
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageStateObservationTest {

    @Test
    void realStartedGameProducesPrincipalScopedSnapshots()
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
                () -> manager.snapshotState(created.gameHandle(), "p1")
        );

        manager.startGame(created.gameHandle());

        List<String> livePlayerIds = XmageSeating.playersInSeatOrder(
                        manager.requireGame(created.gameHandle()))
                .stream()
                .map(player -> player.getId().toString())
                .toList();

        XmageGameManager.StateSnapshot p1 =
                manager.snapshotState(created.gameHandle(), "p1");
        XmageGameManager.StateSnapshot p2 =
                manager.snapshotState(created.gameHandle(), "p2");

        assertEquals("b4a-test/state", p1.gameId());
        assertNotNull(p1.engineGameId());
        assertEquals(1L, p1.stateObservationOffset());
        assertEquals(2L, p2.stateObservationOffset());
        assertEquals("p1", p1.observerPlayerId());
        assertEquals(livePlayerIds.get(0), p1.observerEnginePlayerId());
        assertEquals(0, p1.observerSeat());
        assertEquals("p2", p2.observerPlayerId());
        assertEquals(livePlayerIds.get(1), p2.observerEnginePlayerId());
        assertEquals(1, p2.observerSeat());
        assertNotEquals(p1.state(), p2.state(), "different principals need different views");

        JsonObject state = p1.state();
        assertEquals("b4a-test/state", state.get("game_id").getAsString());
        assertTrue(state.get("seed").isJsonNull());
        assertTrue(state.get("rng_counter").isJsonNull());
        assertEquals("in_progress", state.get("status").getAsString());
        assertEquals(1, state.get("turn_number").getAsInt());
        assertEquals("beginning", state.get("phase").getAsString());
        assertEquals("upkeep", state.get("step").getAsString());

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
            assertAllHidden(zones.getAsJsonArray("library"), 91);
            assertEquals(2, zones.getAsJsonArray("command").size());
            assertEquals(0, zones.getAsJsonArray("battlefield").size());
            assertEquals(0, zones.getAsJsonArray("graveyard").size());
            assertEquals(0, zones.getAsJsonArray("exile").size());

            if (seat == 0) {
                assertEquals(livePlayerIds.get(0), player.get("player_id").getAsString());
                assertNoHidden(zones.getAsJsonArray("hand"), 7);
                assertTrue(player.getAsJsonObject("mana_pool").size() > 0);
            } else {
                assertEquals("op-" + seat, player.get("player_id").getAsString());
                assertAllHidden(zones.getAsJsonArray("hand"), 7);
                assertEquals(0, player.getAsJsonObject("mana_pool").size());
            }
        }

        JsonArray p2Players = p2.state().getAsJsonArray("players");
        assertEquals("op-0", p2Players.get(0).getAsJsonObject().get("player_id").getAsString());
        assertEquals(
                livePlayerIds.get(1),
                p2Players.get(1).getAsJsonObject().get("player_id").getAsString()
        );
        assertAllHidden(
                p2Players.get(0).getAsJsonObject().getAsJsonObject("zones").getAsJsonArray("hand"),
                7
        );
        assertNoHidden(
                p2Players.get(1).getAsJsonObject()
                        .getAsJsonObject("zones")
                        .getAsJsonArray("hand"),
                7
        );

        assertEquals(0, state.getAsJsonArray("stack").size());
        assertEquals(0, state.getAsJsonArray("legal_actions").size());
        assertEquals(0, state.getAsJsonArray("winner_ids").size());
        assertEquals(2, state.get("event_sequence").getAsInt());
    }

    @Test
    void unknownBlankAndCrossGameObserverIdsFailClosed()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);

        XmageGameManager.CreateResult first = manager.createCommanderGame(
                "b4a-test/observer-first",
                importCopies(importer, deck, 2),
                0,
                40
        );
        manager.startGame(first.gameHandle());

        assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.snapshotState(first.gameHandle(), "")
        );
        assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.snapshotState(first.gameHandle(), "unknown-principal")
        );
        assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.snapshotState(first.gameHandle(), "p3")
        );

        XmageGameManager.CreateResult second = manager.createCommanderGame(
                "b4a-test/observer-second",
                importCopies(importer, deck, 2),
                1,
                40
        );
        manager.startGame(second.gameHandle());
        String foreignPlayerId = manager.requireGame(second.gameHandle())
                .getPlayers()
                .values()
                .iterator()
                .next()
                .getId()
                .toString();

        XmageGameManager.GameException foreign = assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.snapshotState(first.gameHandle(), foreignPlayerId)
        );
        assertTrue(foreign.getMessage().contains("UNKNOWN_OBSERVER_PLAYER_ID"));
    }

    private static void assertAllHidden(JsonArray values, int expectedCount) {
        assertEquals(expectedCount, values.size());
        for (var element : values) {
            assertEquals("<hidden>", element.getAsString());
        }
    }

    private static void assertNoHidden(JsonArray values, int expectedCount) {
        assertEquals(expectedCount, values.size());
        for (var element : values) {
            assertNotEquals("<hidden>", element.getAsString());
        }
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
