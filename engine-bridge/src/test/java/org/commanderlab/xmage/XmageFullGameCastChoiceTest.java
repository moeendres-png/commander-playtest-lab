package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.abilities.SpellAbility;
import mage.cards.Card;
import mage.game.CommanderFreeForAll;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;

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

        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
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
