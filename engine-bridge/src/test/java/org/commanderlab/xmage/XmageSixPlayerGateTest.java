package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Owned six-player gate (workstream cpl/xmage-six-player-20260921).
 *
 * <p>Six-player Commander construction/start through the real entrypoint
 * (40 life, 7-card hands, paused turn 1), plus fail-closed creation at
 * seven handles (INVALID_PLAYER_COUNT, zero stored games).</p>
 */
class XmageSixPlayerGateTest {

    @Test
    void supportsSixPlayerCommanderStart() throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 6);
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "b3-test/six-player-commander", handles, 0, 40);
        assertEquals(6, created.playerCount());
        assertEquals(0, created.startingPlayerSeat());
        XmageGameManager.StartResult started = manager.startGame(created.gameHandle());
        assertEquals(6, started.playerCount());
        assertTrue(started.paused());
        assertEquals(1, started.turnNumber());
        Game game = manager.requireGame(created.gameHandle());
        assertEquals(6, game.getPlayers().size());
        for (Player player : game.getPlayers().values()) {
            assertEquals(40, player.getLife());
            assertEquals(7, player.getHand().size());
        }
        assertEquals(1, manager.storedGameCount());
    }

    @Test
    void sevenPlayerCreationFailsClosed() throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 7);
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.GameException error = assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.createCommanderGame(
                        "b3-test/seven-player", handles, 0, 40));
        assertTrue(error.getMessage().contains("INVALID_PLAYER_COUNT"));
        assertEquals(0, manager.storedGameCount());
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

    private static RuntimeDeck loadRogShaiRuntimeDeck() throws Exception {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        Path path = Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize();
        JsonObject root = JsonParser.parseString(
                Files.readString(path, StandardCharsets.UTF_8)).getAsJsonObject();
        JsonArray cards = root.getAsJsonArray("cards");
        List<String> mainboard = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        for (int i = 0; i < cards.size(); i++) {
            JsonObject card = cards.get(i).getAsJsonObject();
            String name = card.get("oracle_name").getAsString();
            int quantity = card.get("quantity").getAsInt();
            List<String> target = "commander".equals(card.get("zone").getAsString())
                    ? commanders : mainboard;
            for (int copy = 0; copy < quantity; copy++) {
                target.add(name);
            }
        }
        assertEquals(98, mainboard.size());
        assertEquals(2, commanders.size());
        return new RuntimeDeck(root.get("deck_id").getAsString(),
                root.get("deck_hash").getAsString(),
                List.copyOf(mainboard), List.copyOf(commanders));
    }

    private record RuntimeDeck(String deckId, String deckHash, List<String> mainboard,
            List<String> commanders) {
    }
}
