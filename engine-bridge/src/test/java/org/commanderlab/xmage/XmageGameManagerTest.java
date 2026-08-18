package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.constants.PhaseStep;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageGameManagerTest {

    @Test
    void createsThenStartsRealFourPlayerCommanderGame()
            throws Exception {

        XmageDeckImporter importer =
                new XmageDeckImporter();

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        List<String> handles =
                importCopies(
                        importer,
                        deck,
                        4
                );

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.CreateResult created =
                manager.createCommanderGame(
                        "b3-test/four-player-commander",
                        handles,
                        0,
                        40
                );

        assertTrue(
                created.gameHandle()
                        .startsWith("xmage-game-")
        );

        assertEquals(
                "b3-test/four-player-commander",
                created.gameId()
        );

        assertEquals(
                4,
                created.playerCount()
        );

        assertEquals(
                0,
                created.startingPlayerSeat()
        );

        Game game =
                manager.requireGame(
                        created.gameHandle()
                );

        assertInstanceOf(
                CommanderFreeForAll.class,
                game
        );

        assertEquals(
                4,
                game.getPlayers().size()
        );

        /*
         * CREATE is deliberately distinct from START.
         */
        assertNull(
                game.getStartingPlayerId()
        );

        assertFalse(
                game.isPaused()
        );

        XmageGameManager.StartResult started =
                manager.startGame(
                        created.gameHandle()
                );

        assertEquals(
                created.gameHandle(),
                started.gameHandle()
        );

        assertNotNull(
                started.startingPlayerId()
        );

        assertEquals(
                4,
                started.playerCount()
        );

        assertEquals(
                1,
                started.turnNumber()
        );

        assertTrue(
                started.paused()
        );

        assertTrue(
                game.isPaused()
        );

        assertEquals(
                started.startingPlayerId(),
                game.getStartingPlayerId()
                        .toString()
        );

        for (Player player
                : game.getPlayers().values()) {

            assertEquals(
                    40,
                    player.getLife()
            );

            assertEquals(
                    7,
                    player.getHand().size()
            );
        }

        assertEquals(
                1,
                manager.storedGameCount()
        );
    }

    @Test
    void pausedStartedGameIsActuallyResumable()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter importer =
                new XmageDeckImporter();

        List<String> handles =
                importCopies(
                        importer,
                        deck,
                        4
                );

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.CreateResult created =
                manager.createCommanderGame(
                        "b3-test/resume",
                        handles,
                        0,
                        40
                );

        manager.startGame(
                created.gameHandle()
        );

        Game game =
                manager.requireGame(
                        created.gameHandle()
                );

        assertTrue(
                game.isPaused()
        );

        assertEquals(
                1,
                game.getState()
                        .getTurnNum()
        );

        /*
         * Technical lifecycle probe only:
         *
         * move the next pause boundary to turn 2 UPKEEP and let XMage resume
         * the exact same Game object. StubPlayer performs no gameplay choices.
         *
         * This is not gameplay-quality evidence. It proves only that the B3
         * handoff state is a valid Game.resume() continuation point.
         */
        game.getOptions().stopOnTurn = 2;
        game.getOptions().stopAtStep =
                PhaseStep.UPKEEP;

        game.resume();

        assertTrue(
                game.isPaused()
        );

        assertEquals(
                2,
                game.getState()
                        .getTurnNum()
        );
    }

    @Test
    void requestedStartingSeatAndLifeAreHonored()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter importer =
                new XmageDeckImporter();

        List<String> handles =
                importCopies(
                        importer,
                        deck,
                        3
                );

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.CreateResult created =
                manager.createCommanderGame(
                        "b3-test/options",
                        handles,
                        2,
                        35
                );

        Game game =
                manager.requireGame(
                        created.gameHandle()
                );

        List<Player> players =
                new ArrayList<>(
                        game.getPlayers().values()
                );

        String requestedStartingId =
                players.get(2)
                        .getId()
                        .toString();

        XmageGameManager.StartResult started =
                manager.startGame(
                        created.gameHandle()
                );

        assertEquals(
                requestedStartingId,
                started.startingPlayerId()
        );

        for (Player player
                : game.getPlayers().values()) {

            assertEquals(
                    35,
                    player.getLife()
            );
        }
    }

    @Test
    void supportsThreeAndFivePlayerCommanderStart()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        for (int playerCount : List.of(3, 5)) {
            XmageDeckImporter importer =
                    new XmageDeckImporter();

            List<String> handles =
                    importCopies(
                            importer,
                            deck,
                            playerCount
                    );

            XmageGameManager manager =
                    new XmageGameManager(importer);

            XmageGameManager.CreateResult created =
                    manager.createCommanderGame(
                            "b3-test/"
                                    + playerCount
                                    + "-player",
                            handles,
                            0,
                            40
                    );

            XmageGameManager.StartResult started =
                    manager.startGame(
                            created.gameHandle()
                    );

            assertEquals(
                    playerCount,
                    started.playerCount()
            );

            assertTrue(
                    started.paused()
            );

            assertEquals(
                    playerCount,
                    manager.requireGame(
                            created.gameHandle()
                    ).getPlayers().size()
            );
        }
    }

    @Test
    void startingSameGameTwiceFailsClosed()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter importer =
                new XmageDeckImporter();

        List<String> handles =
                importCopies(
                        importer,
                        deck,
                        2
                );

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.CreateResult created =
                manager.createCommanderGame(
                        "b3-test/start-twice",
                        handles,
                        0,
                        40
                );

        manager.startGame(
                created.gameHandle()
        );

        XmageGameManager.GameException error =
                assertThrows(
                        XmageGameManager.GameException.class,
                        () -> manager.startGame(
                                created.gameHandle()
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "GAME_ALREADY_STARTED"
                        )
        );
    }

    @Test
    void duplicateDeckHandleFailsClosed()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter importer =
                new XmageDeckImporter();

        String handle =
                importCopies(
                        importer,
                        deck,
                        1
                ).get(0);

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.GameException error =
                assertThrows(
                        XmageGameManager.GameException.class,
                        () -> manager
                                .createCommanderGame(
                                        "b3-test/duplicate",
                                        List.of(
                                                handle,
                                                handle
                                        ),
                                        0,
                                        40
                                )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "DUPLICATE_DECK_HANDLE"
                        )
        );

        assertEquals(
                0,
                manager.storedGameCount()
        );
    }

    @Test
    void unknownDeckHandleFailsClosed() {
        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.GameException error =
                assertThrows(
                        XmageGameManager.GameException.class,
                        () -> manager
                                .createCommanderGame(
                                        "b3-test/unknown",
                                        List.of(
                                                "xmage-deck-missing-a",
                                                "xmage-deck-missing-b"
                                        ),
                                        0,
                                        40
                                )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "DECK_HANDLE_RESOLUTION_FAILED"
                        )
        );

        assertEquals(
                0,
                manager.storedGameCount()
        );
    }

    @Test
    void invalidGameParametersFailClosed()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        for (int playerCount : List.of(1, 6)) {
            XmageDeckImporter importer =
                    new XmageDeckImporter();

            List<String> handles =
                    importCopies(
                            importer,
                            deck,
                            playerCount
                    );

            XmageGameManager manager =
                    new XmageGameManager(importer);

            XmageGameManager.GameException error =
                    assertThrows(
                            XmageGameManager.GameException.class,
                            () -> manager
                                    .createCommanderGame(
                                            "b3-test/bad-count-"
                                                    + playerCount,
                                            handles,
                                            0,
                                            40
                                    )
                    );

            assertTrue(
                    error.getMessage()
                            .contains(
                                    "INVALID_PLAYER_COUNT"
                            )
            );
        }

        XmageDeckImporter importer =
                new XmageDeckImporter();

        List<String> handles =
                importCopies(
                        importer,
                        deck,
                        2
                );

        XmageGameManager manager =
                new XmageGameManager(importer);

        assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.createCommanderGame(
                        "b3-test/bad-seat",
                        handles,
                        2,
                        40
                )
        );

        assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.createCommanderGame(
                        "b3-test/bad-life",
                        handles,
                        0,
                        0
                )
        );
    }

    @Test
    void consumedDeckHandlesCannotCreateSecondGame()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter importer =
                new XmageDeckImporter();

        List<String> handles =
                importCopies(
                        importer,
                        deck,
                        2
                );

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.CreateResult first =
                manager.createCommanderGame(
                        "b3-test/first",
                        handles,
                        0,
                        40
                );

        assertNotNull(
                manager.requireGame(
                        first.gameHandle()
                )
        );

        XmageGameManager.GameException error =
                assertThrows(
                        XmageGameManager.GameException.class,
                        () -> manager
                                .createCommanderGame(
                                        "b3-test/reuse",
                                        handles,
                                        0,
                                        40
                                )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "DECK_HANDLE_ALREADY_IN_USE"
                        )
        );

        assertEquals(
                1,
                manager.storedGameCount()
        );
    }

    @Test
    void unknownGameHandleFailsClosed() {
        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageGameManager manager =
                new XmageGameManager(importer);

        XmageGameManager.GameException error =
                assertThrows(
                        XmageGameManager.GameException.class,
                        () -> manager.requireGame(
                                "xmage-game-does-not-exist"
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "UNKNOWN_GAME_HANDLE"
                        )
        );
    }

    private static List<String> importCopies(
            XmageDeckImporter importer,
            RuntimeDeck deck,
            int count
    ) {
        List<String> handles =
                new ArrayList<>(count);

        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported =
                    importer.importCommanderDeck(
                            deck.deckId(),
                            deck.deckHash(),
                            deck.mainboard(),
                            deck.commanders()
                    );

            handles.add(
                    imported.deckHandle()
            );
        }

        return List.copyOf(handles);
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck()
            throws IOException {

        String repoRoot =
                System.getProperty(
                        "commanderlab.repoRoot"
                );

        if (repoRoot == null
                || repoRoot.isBlank()) {
            throw new IllegalStateException(
                    "commanderlab.repoRoot is missing"
            );
        }

        Path path =
                Path.of(
                        repoRoot,
                        "data",
                        "decks",
                        "rogshai_current.json"
                ).normalize();

        JsonObject root =
                JsonParser.parseString(
                        Files.readString(
                                path,
                                StandardCharsets.UTF_8
                        )
                ).getAsJsonObject();

        JsonArray cards =
                root.getAsJsonArray("cards");

        List<String> mainboard =
                new ArrayList<>();

        List<String> commanders =
                new ArrayList<>();

        cards.forEach(element -> {
            JsonObject card =
                    element.getAsJsonObject();

            String name =
                    card.get("oracle_name")
                            .getAsString();

            int quantity =
                    card.get("quantity")
                            .getAsInt();

            String zone =
                    card.get("zone")
                            .getAsString();

            List<String> target;

            if ("main".equals(zone)) {
                target = mainboard;
            } else if ("commander".equals(zone)) {
                target = commanders;
            } else {
                throw new IllegalStateException(
                        "Unexpected zone: "
                                + zone
                );
            }

            for (int copy = 0; copy < quantity; copy++) {
                target.add(name);
            }
        });

        assertEquals(
                98,
                mainboard.size()
        );

        assertEquals(
                2,
                commanders.size()
        );

        return new RuntimeDeck(
                root.get("deck_id")
                        .getAsString(),
                root.get("deck_hash")
                        .getAsString(),
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