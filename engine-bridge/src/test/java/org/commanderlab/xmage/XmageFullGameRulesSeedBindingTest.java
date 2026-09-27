package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderFreeForAll;
import mage.game.mulligan.MulliganType;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS213 Rules-RNG binding: every credited full-game session binds the
 * explicit orchestration seed to the native per-game Rules RNG before
 * start/init, arms the fail-closed explicit-seed requirement, and reports a
 * live binding proof. RandomUtil is retired as Rules authority.
 */
class XmageFullGameRulesSeedBindingTest {

    private static final long BINDING_SEED = 9788L;

    @Test
    void sessionBindsExplicitRulesSeedWithLiveProof() throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, loadRogShaiRuntimeDeck(), 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws213-seed-binding",
                handles,
                0,
                40,
                BINDING_SEED,
                importer
        );

        // Proof is available immediately at creation (bound in constructor).
        JsonObject created = session.rulesSeedBindingPayload();
        assertEquals(BINDING_SEED, created.get("explicit_seed").getAsLong());
        assertEquals(BINDING_SEED, created.get("rules_seed").getAsLong());
        assertTrue(created.get("rules_seed_matches").getAsBoolean());
        assertTrue(created.get("rules_seed_explicit").getAsBoolean());
        assertTrue(created.get("seed_supported").getAsBoolean());

        JsonObject started = session.start();
        JsonObject binding = started.getAsJsonObject("rules_seed_binding");
        assertEquals(BINDING_SEED, binding.get("rules_seed").getAsLong());
        assertTrue(binding.get("rules_seed_explicit").getAsBoolean());
        assertTrue(binding.get("seed_supported").getAsBoolean());
        // Initial shuffle, choosing-player pick and opening hands consume the
        // bound stream during start: accounting must be non-zero and truthful.
        assertTrue(binding.get("rules_random_calls").getAsLong() > 0);
    }

    @Test
    void sameSeedTwinsOpenIdentically() throws Exception {
        JsonObject first = openFirstDecision(BINDING_SEED, "ws213-twin-a");
        JsonObject second = openFirstDecision(BINDING_SEED, "ws213-twin-b");
        // Native UUID identities differ per game by design; the semantically
        // relevant opening (decision class and actor seat) must reproduce.
        assertEquals(
                first.get("decision_class").getAsString(),
                second.get("decision_class").getAsString()
        );
        assertEquals(
                first.get("seat").getAsInt(),
                second.get("seat").getAsInt()
        );
    }

    @Test
    void unboundGameWithRequiredSeedFailsClosedBeforeAnyConsumption() {
        CommanderFreeForAll game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                40,
                7
        );
        // GameImpl.start only enters init with players present; credited
        // sessions always carry four, so the negative control does too.
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        for (int seat = 0; seat < 4; seat++) {
            game.addPlayer(
                    new XmageFullGamePlayer("ws213-unbound-" + seat,
                            mage.constants.RangeOfInfluence.ALL, controller),
                    new mage.cards.decks.Deck()
            );
        }
        game.setRequireExplicitSeed(true);
        long callsBefore = game.getRulesRandomCalls();
        IllegalStateException failure = assertThrows(
                IllegalStateException.class,
                () -> game.start(UUID.randomUUID())
        );
        assertTrue(failure.getMessage().contains("requires an explicit Rules seed"));
        // Fail-closed before the initial shuffle: no Rules consumption happened.
        assertEquals(callsBefore, game.getRulesRandomCalls());
    }

    @Test
    void productionSessionRetiredRandomUtilAuthority() throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        String text = Files.readString(
                Path.of(repoRoot, "engine-bridge", "src", "main", "java",
                        "org", "commanderlab", "xmage", "XmageFullGameSession.java"),
                StandardCharsets.UTF_8
        );
        assertTrue(text.contains("setRulesSeed(seed)"));
        assertTrue(text.contains("setRequireExplicitSeed(true)"));
        // Prose may name the retired mechanism; code must not use it.
        assertTrue(!text.contains("import mage.util.RandomUtil"),
                "RandomUtil import must not remain in the credited session path");
        assertTrue(!text.contains("RandomUtil."),
                "RandomUtil code use must not remain in the credited session path");
    }

    private static JsonObject openFirstDecision(long seed, String gameId) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, loadRogShaiRuntimeDeck(), 4);
        XmageFullGameSession session = new XmageFullGameSession(
                gameId, handles, 0, 40, seed, importer
        );
        session.start();
        for (int step = 0; step < 30; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (!payload.get("decision").isJsonNull()) {
                return payload.getAsJsonObject("decision");
            }
        }
        throw new IllegalStateException("no opening decision observed for " + gameId);
    }

    private static List<String> importCopies(XmageDeckImporter importer, RuntimeDeck deck, int count) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deck.deckId(), deck.deckHash(), deck.mainboard(), deck.commanders()
            );
            handles.add(imported.deckHandle());
        }
        return List.copyOf(handles);
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck() throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        JsonObject root = JsonParser.parseString(
                Files.readString(
                        Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize(),
                        StandardCharsets.UTF_8
                )
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
