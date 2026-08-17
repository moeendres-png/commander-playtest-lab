package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.decks.Deck;
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

class XmageDeckImporterTest {

    @Test
    void importsConcreteRogShaiAsRealXmageCommanderDeck()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportResult result =
                importer.importCommanderDeck(
                        deck.deckId(),
                        deck.deckHash(),
                        deck.mainboard(),
                        deck.commanders()
                );

        assertNotNull(result.deckHandle());
        assertFalse(result.deckHandle().isBlank());
        assertTrue(
                result.deckHandle()
                        .startsWith("xmage-deck-")
        );

        assertEquals(
                deck.deckId(),
                result.deckId()
        );

        assertEquals(
                deck.deckHash(),
                result.deckHash()
        );

        assertEquals(
                98,
                result.mainboardCount()
        );

        assertEquals(
                2,
                result.commanderCount()
        );

        Deck realDeck =
                importer.requireDeck(
                        result.deckHandle()
                );

        assertNotNull(realDeck);

        assertEquals(
                98,
                realDeck.getMaindeckCards().size()
        );

        assertEquals(
                2,
                realDeck.getSideboard().size()
        );

        assertEquals(
                1,
                importer.storedDeckCount()
        );
    }

    @Test
    void repeatedImportsReceiveUniqueHandles()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportResult first =
                importer.importCommanderDeck(
                        deck.deckId(),
                        deck.deckHash(),
                        deck.mainboard(),
                        deck.commanders()
                );

        XmageDeckImporter.ImportResult second =
                importer.importCommanderDeck(
                        deck.deckId(),
                        deck.deckHash(),
                        deck.mainboard(),
                        deck.commanders()
                );

        assertNotEquals(
                first.deckHandle(),
                second.deckHandle()
        );

        assertNotNull(
                importer.requireDeck(
                        first.deckHandle()
                )
        );

        assertNotNull(
                importer.requireDeck(
                        second.deckHandle()
                )
        );

        assertEquals(
                2,
                importer.storedDeckCount()
        );
    }

    @Test
    void handlesAreNotAcceptedByAnotherImporterInstance()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        XmageDeckImporter firstImporter =
                new XmageDeckImporter();

        XmageDeckImporter.ImportResult result =
                firstImporter.importCommanderDeck(
                        deck.deckId(),
                        deck.deckHash(),
                        deck.mainboard(),
                        deck.commanders()
                );

        XmageDeckImporter secondImporter =
                new XmageDeckImporter();

        XmageDeckImporter.ImportException error =
                assertThrows(
                        XmageDeckImporter.ImportException.class,
                        () -> secondImporter.requireDeck(
                                result.deckHandle()
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains("UNKNOWN_DECK_HANDLE")
        );
    }

    @Test
    void unknownMechanicalCardNameFailsClosed()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        List<String> mainboard =
                new ArrayList<>(deck.mainboard());

        mainboard.set(
                0,
                "Commander Lab Definitely Missing Card"
        );

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportException error =
                assertThrows(
                        XmageDeckImporter.ImportException.class,
                        () -> importer.importCommanderDeck(
                                deck.deckId(),
                                deck.deckHash(),
                                mainboard,
                                deck.commanders()
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains("UNKNOWN_CARD_NAME")
        );

        assertEquals(
                0,
                importer.storedDeckCount()
        );
    }

    @Test
    void invalidCommanderDeckSizeFailsClosed()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        List<String> mainboard =
                new ArrayList<>(deck.mainboard());

        mainboard.remove(0);

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportException error =
                assertThrows(
                        XmageDeckImporter.ImportException.class,
                        () -> importer.importCommanderDeck(
                                deck.deckId(),
                                deck.deckHash(),
                                mainboard,
                                deck.commanders()
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains("INVALID_DECK_SIZE")
        );

        assertEquals(
                0,
                importer.storedDeckCount()
        );
    }

    @Test
    void importsValidSingleCommanderKykarDeck()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        List<String> mainboard =
                new ArrayList<>(deck.mainboard());

        List<String> commanders =
                new ArrayList<>(deck.commanders());

        assertTrue(
                mainboard.remove(
                        "Kykar, Wind's Fury"
                )
        );

        mainboard.addAll(commanders);
        commanders.clear();

        commanders.add(
                "Kykar, Wind's Fury"
        );

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportResult result =
                importer.importCommanderDeck(
                        "b2-test/single-commander-kykar",
                        "1111111111111111111111111111111111111111111111111111111111111111",
                        mainboard,
                        commanders
                );

        assertEquals(
                99,
                result.mainboardCount()
        );

        assertEquals(
                1,
                result.commanderCount()
        );

        Deck realDeck =
                importer.requireDeck(
                        result.deckHandle()
                );

        assertEquals(
                99,
                realDeck.getMaindeckCards().size()
        );

        assertEquals(
                1,
                realDeck.getSideboard().size()
        );
    }

    @Test
    void invalidRograkhKykarPartnerPairFailsClosed()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        List<String> mainboard =
                new ArrayList<>(deck.mainboard());

        List<String> commanders =
                new ArrayList<>(deck.commanders());

        assertTrue(
                mainboard.remove(
                        "Kykar, Wind's Fury"
                )
        );

        assertTrue(
                commanders.remove(
                        "Ishai, Ojutai Dragonspeaker"
                )
        );

        mainboard.add(
                "Ishai, Ojutai Dragonspeaker"
        );

        commanders.add(
                "Kykar, Wind's Fury"
        );

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportException error =
                assertThrows(
                        XmageDeckImporter.ImportException.class,
                        () -> importer.importCommanderDeck(
                                "b2-test/invalid-rograkh-kykar",
                                "2222222222222222222222222222222222222222222222222222222222222222",
                                mainboard,
                                commanders
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "COMMANDER_VALIDATION_FAILED"
                        )
        );

        assertEquals(
                0,
                importer.storedDeckCount()
        );
    }

    @Test
    void invalidNonCommanderCardFailsClosed()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        List<String> mainboard =
                new ArrayList<>(deck.mainboard());

        List<String> commanders =
                new ArrayList<>(deck.commanders());

        assertTrue(
                mainboard.remove("Plains")
        );

        mainboard.addAll(commanders);
        commanders.clear();
        commanders.add("Plains");

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportException error =
                assertThrows(
                        XmageDeckImporter.ImportException.class,
                        () -> importer.importCommanderDeck(
                                "b2-test/invalid-plains-commander",
                                "3333333333333333333333333333333333333333333333333333333333333333",
                                mainboard,
                                commanders
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "COMMANDER_VALIDATION_FAILED"
                        )
        );

        assertEquals(
                0,
                importer.storedDeckCount()
        );
    }

    @Test
    void threeCommandersFailClosedBeforeXmageLoad()
            throws Exception {

        RuntimeDeck deck =
                loadRogShaiRuntimeDeck();

        List<String> mainboard =
                new ArrayList<>(deck.mainboard());

        List<String> commanders =
                new ArrayList<>(deck.commanders());

        assertTrue(
                mainboard.remove(
                        "Kykar, Wind's Fury"
                )
        );

        commanders.add(
                "Kykar, Wind's Fury"
        );

        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportException error =
                assertThrows(
                        XmageDeckImporter.ImportException.class,
                        () -> importer.importCommanderDeck(
                                "b2-test/three-commanders",
                                "4444444444444444444444444444444444444444444444444444444444444444",
                                mainboard,
                                commanders
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains(
                                "INVALID_COMMANDER_COUNT"
                        )
        );
    }

    @Test
    void unknownHandleFailsClosed() {
        XmageDeckImporter importer =
                new XmageDeckImporter();

        XmageDeckImporter.ImportException error =
                assertThrows(
                        XmageDeckImporter.ImportException.class,
                        () -> importer.requireDeck(
                                "xmage-deck-does-not-exist"
                        )
                );

        assertTrue(
                error.getMessage()
                        .contains("UNKNOWN_DECK_HANDLE")
        );
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck()
            throws IOException {

        String repoRoot =
                System.getProperty(
                        "commanderlab.repoRoot"
                );

        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException(
                    "commanderlab.repoRoot system property is missing"
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

        String deckId =
                root.get("deck_id").getAsString();

        String deckHash =
                root.get("deck_hash").getAsString();

        JsonArray cards =
                root.getAsJsonArray("cards");

        List<String> mainboard =
                new ArrayList<>();

        List<String> commanders =
                new ArrayList<>();

        cards.forEach(element -> {
            JsonObject card =
                    element.getAsJsonObject();

            String oracleName =
                    card.get("oracle_name")
                            .getAsString();

            int quantity =
                    card.get("quantity")
                            .getAsInt();

            String zone =
                    card.get("zone")
                            .getAsString();

            if (quantity < 1) {
                throw new IllegalStateException(
                        "Invalid normalized quantity for "
                                + oracleName
                );
            }

            List<String> destination;

            if ("main".equals(zone)) {
                destination = mainboard;
            } else if ("commander".equals(zone)) {
                destination = commanders;
            } else {
                throw new IllegalStateException(
                        "Unexpected normalized zone: "
                                + zone
                );
            }

            for (int copy = 0; copy < quantity; copy++) {
                destination.add(oracleName);
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

        assertEquals(
                100,
                mainboard.size()
                        + commanders.size()
        );

        return new RuntimeDeck(
                deckId,
                deckHash,
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