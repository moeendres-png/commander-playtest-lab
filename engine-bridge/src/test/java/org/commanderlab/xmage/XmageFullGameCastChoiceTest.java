package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.abilities.SpellAbility;
import mage.cards.Card;
import mage.game.GameCommanderImpl;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageFullGameCastChoiceTest {

    @Test
    void realSolRingCastChoiceUsesXmageLegalSpellAbilityWithoutParentFallback()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws07-real-cast-choice",
                handles,
                0,
                40,
                7017L,
                importer
        );

        GameCommanderImpl game = field(session, "game", GameCommanderImpl.class);
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players = (List<XmageFullGamePlayer>) field(
                session,
                "players",
                List.class
        );
        XmageFullGameDecisionController controller = field(
                session,
                "controller",
                XmageFullGameDecisionController.class
        );
        XmageFullGamePlayer player = players.get(0);
        Card solRing = player.getLibrary().getCards(game).stream()
                .filter(card -> "Sol Ring".equals(card.getName()))
                .findFirst()
                .orElseThrow(() -> new AssertionError("real RogShai deck did not contain Sol Ring"));

        game.getState().setValue("PlayFromNotOwnHandZone" + solRing.getId(), Boolean.TRUE);
        try {
            SpellAbility chosen = player.chooseAbilityForCast(solRing, game, false);
            assertNotNull(chosen);
            assertEquals(solRing.getId(), chosen.getSourceId());
            assertNull(controller.pendingDecision());
            assertNull(controller.terminalFailure());
        } finally {
            game.getState().setValue("PlayFromNotOwnHandZone" + solRing.getId(), null);
        }

        assertFalse(solRing.isLand(game));
    }

    /**
     * #747: XMage lists no castable spell ability for a card it still asks about (seen
     * with Wear // Tear). Its own HumanPlayer then falls back to the card's spell
     * ability; the bridge does the same with a logged forced move and keeps the game.
     */
    @Test
    void castChoiceWithNoCastableAbilityFallsBackLikeXmage() throws Exception {
        Fixture fixture = fixture("747-cast-fallback");
        Card solRing = fixture.player().getLibrary().getCards(fixture.game()).stream()
                .filter(card -> "Sol Ring".equals(card.getName()))
                .findFirst()
                .orElseThrow(() -> new AssertionError("real RogShai deck did not contain Sol Ring"));

        // From the library, without a play-from permission, nothing is castable.
        SpellAbility chosen = fixture.player().chooseAbilityForCast(solRing, fixture.game(), false);

        assertNotNull(chosen);
        assertEquals(solRing.getSpellAbility().getId(), chosen.getId());
        assertNull(fixture.controller().terminalFailure());
        assertNull(fixture.controller().pendingDecision());
        assertTrue(hasForcedMove(fixture.controller(), "choice"));
    }

    /**
     * #747: XMage passes an empty effect map when every competing replacement effect
     * lacks a source ability; its own HumanPlayer answers 0 and the engine applies its
     * first effect. The bridge does the same with a logged forced move.
     */
    @Test
    void replacementChoiceWithNoListedEffectAppliesXmagesFirst() throws Exception {
        Fixture fixture = fixture("747-empty-replacement");

        int index = fixture.player().chooseReplacementEffect(
                new LinkedHashMap<>(), new LinkedHashMap<>(), fixture.game());

        assertEquals(0, index);
        assertNull(fixture.controller().terminalFailure());
        assertNull(fixture.controller().pendingDecision());
        assertTrue(hasForcedMove(fixture.controller(), "replacement_effect"));
    }

    private static boolean hasForcedMove(XmageFullGameDecisionController controller, String decisionClass) {
        JsonArray transcript = controller.transcript();
        for (JsonElement element : transcript) {
            JsonObject event = element.getAsJsonObject();
            if ("forced_move".equals(event.get("event_type").getAsString())
                    && decisionClass.equals(
                            event.getAsJsonObject("payload").get("decision_class").getAsString())) {
                return true;
            }
        }
        return false;
    }

    private static Fixture fixture(String gameId) throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(gameId, handles, 0, 40, 7017L, importer);
        GameCommanderImpl game = field(session, "game", GameCommanderImpl.class);
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players = (List<XmageFullGamePlayer>) field(session, "players", List.class);
        XmageFullGameDecisionController controller = field(
                session, "controller", XmageFullGameDecisionController.class);
        return new Fixture(game, players.get(0), controller);
    }

    private record Fixture(
            GameCommanderImpl game,
            XmageFullGamePlayer player,
            XmageFullGameDecisionController controller
    ) {
    }

    private static <T> T field(Object target, String name, Class<T> type)
            throws ReflectiveOperationException {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return type.cast(field.get(target));
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
        Path path = Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize();
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
