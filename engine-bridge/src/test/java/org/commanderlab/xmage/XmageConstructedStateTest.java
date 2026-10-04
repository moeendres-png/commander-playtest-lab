package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Commander-Lab #441 decision (c): the generic lane emits the engine's own
 * normalized constructed state, read from the native game objects at the first
 * pregame decision, so the Lab can compare it with a record's requested state.
 *
 * <p>The state names seats by seat number and reports zones as card-name
 * multisets only: no library order and no object identities leave the engine.
 * A deck the record did not request shows up as a different multiset, so the
 * comparison cannot be satisfied by a substitute deck.</p>
 */
class XmageConstructedStateTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    private static List<String> decks(XmageDeckImporter importer, String tag, String odd) {
        List<String> handles = new ArrayList<>();
        for (int seat = 1; seat <= 4; seat++) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            if (odd != null && seat == 2) {
                mainboard.set(0, odd);
            }
            handles.add(importer.importCommanderDeck(
                    tag + "-P" + seat, tag + "-hash-" + seat, mainboard, List.of(ROGRAKH))
                    .deckHandle());
        }
        return handles;
    }

    private static JsonObject player(JsonObject state, String pid) {
        for (JsonElement element : state.getAsJsonArray("players")) {
            if (pid.equals(element.getAsJsonObject().get("player_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        throw new AssertionError("no player " + pid);
    }

    private static int count(JsonObject counts, String name) {
        return counts.has(name) ? counts.get(name).getAsInt() : 0;
    }

    @Test
    void theConstructedStateIsTheRequestedNaturalGameStart() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "constructed-4p", decks(importer, "constructed-4p", null), 0, 40, true);
        manager.startGame(created.gameHandle());
        assertEquals("mulligan", manager.legalActions(created.gameHandle()).decisionKind(),
                "read at the first pregame decision, before anything is answered");

        JsonObject state = manager.constructedState(created.gameHandle());
        assertEquals(XmageGameManager.CONSTRUCTED_STATE_SCHEMA, state.get("schema").getAsString());
        assertEquals(0, state.get("stack_size").getAsInt());
        assertEquals(4, state.getAsJsonArray("players").size());
        for (int seat = 1; seat <= 4; seat++) {
            JsonObject player = player(state, "P" + seat);
            assertEquals(seat, player.get("seat").getAsInt());
            assertEquals(40, player.get("life").getAsInt());
            assertEquals(0, player.get("poison").getAsInt());
            assertFalse(player.get("lost").getAsBoolean());
            assertFalse(player.get("left").getAsBoolean());
            int mountains = count(player.getAsJsonObject("library_card_counts"), "Mountain")
                    + count(player.getAsJsonObject("hand_card_counts"), "Mountain");
            assertEquals(99, mountains, "library and hand are the 99-card main deck");
            assertEquals(1, player.getAsJsonObject("library_card_counts").size());
            assertEquals(7, player.get("hand_size").getAsInt(), "opening hand drawn");
            assertEquals(92, player.get("library_size").getAsInt());
            assertEquals(0, player.getAsJsonObject("battlefield_card_counts").size());
            assertEquals(0, player.getAsJsonObject("graveyard_card_counts").size());
            assertEquals(0, player.getAsJsonObject("exile_card_counts").size());
            assertEquals(1, player.getAsJsonArray("commanders").size());
            JsonObject commander = player.getAsJsonArray("commanders").get(0).getAsJsonObject();
            assertEquals(ROGRAKH, commander.get("card_identity").getAsString());
            assertEquals("P" + seat, commander.get("owner").getAsString());
            assertEquals("command", commander.get("zone").getAsString());
            assertEquals(0, commander.get("prior_command_zone_cast_count").getAsInt());
        }
        // No identities or order leave the engine: only names and counts.
        String text = state.toString();
        assertFalse(text.matches("(?s).*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-.*"),
                "no object or player UUID may appear: " + text);
    }

    @Test
    void aSubstituteCardInTheDeckIsVisibleInTheMultiset() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "constructed-odd", decks(importer, "constructed-odd", "Lightning Bolt"), 0, 40, true);
        manager.startGame(created.gameHandle());
        JsonObject player = player(manager.constructedState(created.gameHandle()), "P2");
        int bolts = count(player.getAsJsonObject("library_card_counts"), "Lightning Bolt")
                + count(player.getAsJsonObject("hand_card_counts"), "Lightning Bolt");
        int mountains = count(player.getAsJsonObject("library_card_counts"), "Mountain")
                + count(player.getAsJsonObject("hand_card_counts"), "Mountain");
        assertEquals(1, bolts);
        assertEquals(98, mountains);
    }

    @Test
    void theProtocolSurfaceDeclaresAndServesTheConstructedState() {
        JsonObject capabilities = XmageProvider.capabilitiesPayload().getAsJsonObject("capabilities");
        assertTrue(capabilities.get("constructed_state_supported").getAsBoolean());
    }
}
