package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Commander-Lab #441 decision (c): the generic lane reads the engine's own
 * normalized constructed state at the first pregame decision, so the Lab can
 * compare it with a record's requested state.
 *
 * <p>The read is an orchestration channel (the AF09 precedent): refused on a
 * launch without an orchestration key, and hidden content (each seat's library
 * and hand) leaves only as an HMAC under that key. Seats are named by seat
 * number; no card name of a hidden zone and no object identity leaves the
 * engine.</p>
 */
class XmageConstructedStateTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final byte[] KEY = new byte[32];

    @AfterEach
    void principalLaunch() {
        XmageRulesRngResultTape.keyForTests(null);
    }

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

    private static XmageGameManager startedAtFirstDecision(XmageGameManager manager, XmageDeckImporter importer,
            String tag, String odd, String[] handle) {
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                tag, decks(importer, tag, odd), 0, 40, true);
        manager.startGame(created.gameHandle());
        assertEquals("mulligan", manager.legalActions(created.gameHandle()).decisionKind(),
                "read at the first pregame decision, before anything is answered");
        handle[0] = created.gameHandle();
        return manager;
    }

    private static JsonObject player(JsonObject state, String pid) {
        for (JsonElement element : state.getAsJsonArray("players")) {
            if (pid.equals(element.getAsJsonObject().get("player_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        throw new AssertionError("no player " + pid);
    }

    /** The digest computed independently, as the Lab computes it from the record. */
    private static String expected(byte[] key, String seat, String... nameTabCount) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        List<String> tokens = new ArrayList<>(List.of(
                XmageGameManager.CONSTRUCTED_STATE_SCHEMA, "library_and_hand", seat));
        tokens.addAll(List.of(nameTabCount));
        for (String token : tokens) {
            mac.update(token.getBytes(StandardCharsets.UTF_8));
            mac.update((byte) '\n');
        }
        return HexFormat.of().formatHex(mac.doFinal());
    }

    @Test
    void aLaunchWithoutAnOrchestrationKeyIsRefused() {
        XmageRulesRngResultTape.keyForTests(null);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        String[] handle = new String[1];
        startedAtFirstDecision(manager, importer, "constructed-nokey", null, handle);
        XmageGameManager.GameException refused = assertThrows(XmageGameManager.GameException.class,
                () -> manager.constructedState(handle[0]));
        assertTrue(refused.getMessage().startsWith("ORCHESTRATION_CHANNEL_NOT_ENABLED"));
    }

    @Test
    void theConstructedStateIsTheRequestedNaturalGameStart() throws Exception {
        XmageRulesRngResultTape.keyForTests(KEY);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        String[] handle = new String[1];
        startedAtFirstDecision(manager, importer, "constructed-4p", null, handle);

        JsonObject state = manager.constructedState(handle[0]);
        assertEquals(XmageGameManager.CONSTRUCTED_STATE_SCHEMA, state.get("schema").getAsString());
        assertEquals("orchestration_keyed_digests", state.get("observation_scope").getAsString());
        assertEquals(0, state.get("stack_size").getAsInt());
        assertEquals(4, state.getAsJsonArray("players").size());
        for (int seat = 1; seat <= 4; seat++) {
            JsonObject player = player(state, "P" + seat);
            assertEquals(seat, player.get("seat").getAsInt());
            assertEquals(40, player.get("life").getAsInt());
            assertEquals(0, player.get("poison").getAsInt());
            assertFalse(player.get("lost").getAsBoolean());
            assertFalse(player.get("left").getAsBoolean());
            assertEquals(7, player.get("hand_size").getAsInt(), "opening hand drawn");
            assertEquals(92, player.get("library_size").getAsInt());
            assertEquals(expected(KEY, "P" + seat, "Mountain\t99"),
                    player.get("library_and_hand_digest").getAsString(),
                    "library and hand together are the 99-card main deck");
            assertEquals(0, player.get("battlefield_size").getAsInt());
            assertEquals(0, player.get("graveyard_size").getAsInt());
            assertEquals(0, player.get("exile_size").getAsInt());
            assertEquals(1, player.getAsJsonArray("commanders").size());
            JsonObject commander = player.getAsJsonArray("commanders").get(0).getAsJsonObject();
            assertEquals(ROGRAKH, commander.get("card_identity").getAsString());
            assertEquals("P" + seat, commander.get("owner").getAsString());
            assertEquals("command", commander.get("zone").getAsString());
            assertEquals(0, commander.get("prior_command_zone_cast_count").getAsInt());
        }
        // No hidden card name, order or identity leaves the engine.
        String text = state.toString();
        assertFalse(text.contains("Mountain"), "no hidden card name may appear: " + text);
        assertFalse(text.matches("(?s).*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-.*"),
                "no object or player UUID may appear: " + text);
    }

    @Test
    void aSubstituteCardChangesTheDigestAndAnotherKeyCannotTestAGuess() throws Exception {
        XmageRulesRngResultTape.keyForTests(KEY);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        String[] handle = new String[1];
        startedAtFirstDecision(manager, importer, "constructed-odd", "Lightning Bolt", handle);
        JsonObject state = manager.constructedState(handle[0]);
        String odd = player(state, "P2").get("library_and_hand_digest").getAsString();
        assertNotEquals(expected(KEY, "P2", "Mountain\t99"), odd, "a substitute deck is not equal");
        assertEquals(expected(KEY, "P2", "Lightning Bolt\t1", "Mountain\t98"), odd);
        assertEquals(expected(KEY, "P1", "Mountain\t99"),
                player(state, "P1").get("library_and_hand_digest").getAsString());
        byte[] other = new byte[32];
        other[0] = 1;
        assertNotEquals(expected(other, "P2", "Lightning Bolt\t1", "Mountain\t98"), odd,
                "without the launch key a guess cannot be tested");
    }

    @Test
    void theProtocolSurfaceDeclaresTheOrchestrationScope() {
        JsonObject capabilities = XmageProvider.capabilitiesPayload().getAsJsonObject("capabilities");
        assertTrue(capabilities.get("constructed_state_supported").getAsBoolean());
        assertEquals("orchestration_keyed_digests_refused_without_launch_key",
                capabilities.get("constructed_state_scope").getAsString());
    }
}
